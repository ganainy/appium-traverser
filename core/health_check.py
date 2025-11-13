"""
Health check and validation service for system components and configuration.

This module provides comprehensive health checking and validation services used by both
CLI and UI interfaces to verify dependencies, services, and configuration before
starting the crawler.
"""

import logging
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from config.app_config import Config

from cli.constants import messages as MSG
from cli.constants import keys as KEYS
from cli.services.process_utils import run_subprocess as cli_run_subprocess

# Default Service URLs - now imported from config.urls
from config.urls import ServiceURLs
from config.numeric_constants import (
    DEFAULT_AI_PROVIDER,
    APPIUM_STATUS_TIMEOUT,
    MCP_STATUS_TIMEOUT,
    MOBSF_STATUS_TIMEOUT,
    OLLAMA_API_TIMEOUT,
    OLLAMA_CLI_TIMEOUT,
)
DEFAULT_APPIUM_URL = ServiceURLs.APPIUM
DEFAULT_MOBSF_URL = ServiceURLs.MOBSF
DEFAULT_OLLAMA_URL = ServiceURLs.OLLAMA

# Module-level dictionary for all user-facing validation messages
VALIDATION_MESSAGES = {
    "APPIUM_FAIL": "❌ Appium server is not running or not accessible",
    "APPIUM_SUCCESS": "is running ✅",
    "APPIUM_NOT_ACCESSIBLE": "is not accessible ❌",
    "MOBSF_WARN": "⚠️ MobSF server is not running (optional)",
    "TARGET_APP_MISSING": "❌ No target app selected (use: python run_cli.py apps select <index_or_package>)",
    "MISSING_CONFIG": "❌ Missing required configuration: {key}",
    "OLLAMA_NOT_RUNNING": "❌ Ollama service is not running",
    "OLLAMA_URL_NOT_SET": "⚠️ Ollama base URL not set (using default localhost:11434)",
    "GEMINI_API_KEY_MISSING": "❌ Gemini API key is not set (check GEMINI_API_KEY in .env file)",
    "OPENROUTER_API_KEY_MISSING": "❌ OpenRouter API key is not set (check OPENROUTER_API_KEY in .env file)",
    "PCAPDROID_API_KEY_MISSING": "❌ PCAPdroid API key is not set (check PCAPDROID_API_KEY in .env file)",
    "MOBSF_API_KEY_MISSING": "❌ MobSF API key is not set (check MOBSF_API_KEY in .env file)",
    "SERVICE_URL_TEMPLATE": "{service} server at {url}",
    "API_KEYS_ISSUES": "API keys: {issues} issue(s), {warnings} warning(s)",
    "API_KEYS_ALL_GOOD": "API keys: All required keys present ✅",
    "TARGET_APP_TEMPLATE": "Target app: {package}",
    "TARGET_APP_NOT_SELECTED": "Target app: Not selected ❌",
    "OLLAMA_SERVICE": "Ollama service",
    "MOBSF_NOT_ACCESSIBLE": " is not accessible ⚠️",
    "AI_MODEL_NOT_SELECTED": "❌ No AI model selected. Please select a model before starting a crawl (use: python run_cli.py <provider> select-model <model>)"
}


class ValidationService:
    """
    Unified service for validating crawler dependencies, configuration, and health checks.
    
    Provides both validation (boolean + messages) and health check (detailed status dict)
    interfaces for use by CLI and UI.
    """
    
    # Dictionary mapping AI providers to their requirements
    AI_PROVIDER_REQUIREMENTS = {
        'gemini': {
            'required_keys': ['GEMINI_API_KEY'],
            'service_check': None,
            'message_key': 'GEMINI_API_KEY_MISSING'
        },
        'openrouter': {
            'required_keys': ['OPENROUTER_API_KEY'],
            'service_check': None,
            'message_key': 'OPENROUTER_API_KEY_MISSING'
        },
        'ollama': {
            'required_keys': [],
            'service_check': '_check_ollama_service',
            'message_key': 'OLLAMA_URL_NOT_SET'
        }
    }
    
    def __init__(self, config: "Config"):
        """Initialize the validation/health check service with config.
        
        Args:
            config: Configuration instance (can be used by both CLI and UI)
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    # ========== Health Check Interface ==========
    
    def check_all_services(self) -> Dict[str, Dict[str, Any]]:
        """
        Check all services and return detailed status dictionary.
        
        Returns:
            Dictionary mapping service names to their status information.
            Each status dict contains 'status' and 'message' keys.
        """
        services = {}
        
        # Check Appium server
        appium_status = self.check_appium_server()
        services[KEYS.SERVICE_APPIUM] = appium_status
        
        # Check MobSF server
        mobsf_status = self.check_mobsf_server()
        services[KEYS.SERVICE_MOBSF] = mobsf_status
        
        # Check Ollama service if needed
        ai_provider = self.config.get("AI_PROVIDER", DEFAULT_AI_PROVIDER).lower()
        if ai_provider == 'ollama':
            ollama_status = self.check_ollama_service()
            services[KEYS.SERVICE_OLLAMA] = ollama_status
        
        # Check PCAPdroid (always show as separate service)
        pcapdroid_status = self.check_pcapdroid()
        services[KEYS.SERVICE_PCAPDROID] = pcapdroid_status
        
        # Check API keys and environment
        api_issues, api_warnings = self.check_api_keys_and_env()
        if api_issues:
            services[KEYS.SERVICE_API_KEYS] = {
                KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR,
                KEYS.STATUS_KEY_MESSAGE: '; '.join(api_issues)
            }
        elif api_warnings:
            services[KEYS.SERVICE_API_KEYS] = {
                KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING,
                KEYS.STATUS_KEY_MESSAGE: '; '.join(api_warnings)
            }
        else:
            services[KEYS.SERVICE_API_KEYS] = {
                KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING,
                KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_OK
            }
        
        # Check target app
        # Use get() to properly check user store, env vars, and defaults in order
        app_package = self.config.get("APP_PACKAGE", None)
        if app_package:
            services[KEYS.SERVICE_TARGET_APP] = {
                KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING,
                KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_SELECTED.format(app_package=app_package)
            }
        else:
            services[KEYS.SERVICE_TARGET_APP] = {
                KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR,
                KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_NO_APP
            }
        
        return services
    
    def check_appium_server(self) -> Dict[str, str]:
        """Check Appium server status and return detailed status dict."""
        try:
            appium_url = self._get_appium_url().rstrip('/')
            response = requests.get(f"{appium_url}{KEYS.APPIUM_STATUS_PATH}", timeout=APPIUM_STATUS_TIMEOUT)
            
            if response.status_code == KEYS.HTTP_CODE_OK:
                status_data = response.json()
                ready = (
                    status_data.get(KEYS.JSON_KEY_READY, False) or
                    status_data.get(KEYS.JSON_KEY_VALUE, {}).get(KEYS.JSON_KEY_READY, False)
                )
                if ready:
                    return {
                        KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING,
                        KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_REACHABLE.format(url=appium_url)
                    }
                else:
                    return {
                        KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING,
                        KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_NOT_READY.format(url=appium_url)
                    }
            else:
                return {
                    KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR,
                    KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_HTTP.format(code=response.status_code, url=appium_url)
                }
        except Exception as e:
            appium_url = self._get_appium_url()
            conn_fail_msg = self._format_connection_error(e, "Appium Server", appium_url)
            return {
                KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR,
                KEYS.STATUS_KEY_MESSAGE: conn_fail_msg
            }
    
    def check_mobsf_server(self) -> Dict[str, str]:
        """Check MobSF server status and return detailed status dict."""
        # Only check MobSF if analysis is enabled
        if not self.config.get("ENABLE_MOBSF_ANALYSIS", False):
            return {
                KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING,
                KEYS.STATUS_KEY_MESSAGE: "MobSF analysis is disabled (optional feature)"
            }
        
        try:
            mobsf_url = self._get_mobsf_url()
            response = requests.get(f"{mobsf_url}{KEYS.MOBSF_STATUS_PATH}", timeout=MOBSF_STATUS_TIMEOUT)
            if response.status_code == KEYS.HTTP_CODE_OK:
                return {
                    KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING,
                    KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_REACHABLE.format(url=mobsf_url)
                }
            else:
                return {
                    KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING,
                    KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_HTTP.format(code=response.status_code, url=mobsf_url)
                }
        except Exception as e:
            mobsf_url = self._get_mobsf_url()
            conn_fail_msg = self._format_connection_error(e, "MobSF Server", mobsf_url)
            return {
                KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING,
                KEYS.STATUS_KEY_MESSAGE: conn_fail_msg
            }
    
    def check_ollama_service(self) -> Dict[str, str]:
        """Check Ollama service status and return detailed status dict."""
        ollama_url = self._get_ollama_url()
        
        try:
            response = requests.get(f"{ollama_url}{KEYS.OLLAMA_TAGS_PATH}", timeout=OLLAMA_API_TIMEOUT)
            if response.status_code == KEYS.HTTP_CODE_OK:
                return {
                    KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING,
                    KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_API_REACHABLE.format(url=ollama_url)
                }
        except Exception:
            pass
        
        # Fallback to subprocess check
        try:
            result = cli_run_subprocess(
                ["ollama", "list"],
                timeout=OLLAMA_CLI_TIMEOUT,
                capture_output=True
            )
            
            if result.returncode == 0:
                return {
                    KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING,
                    KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_CLI_ACCESSIBLE
                }
            else:
                return {
                    KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR,
                    KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_CLI_NOT_ACCESSIBLE
                }
        except Exception:
            return {
                KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR,
                KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_NOT_ACCESSIBLE.format(url=ollama_url)
            }
    
    def check_pcapdroid(self) -> Dict[str, str]:
        """Check PCAPdroid traffic capture status and return detailed status dict."""
        if self.config.get("ENABLE_TRAFFIC_CAPTURE", False):
            if not self.config.get("PCAPDROID_API_KEY", None):
                return {
                    KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING,
                    KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_MISSING_KEY.format(key="API key", env="PCAPDROID_API_KEY")
                }
            else:
                return {
                    KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING,
                    KEYS.STATUS_KEY_MESSAGE: "PCAPdroid API key is configured (traffic capture enabled)"
                }
        else:
            return {
                KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING,
                KEYS.STATUS_KEY_MESSAGE: "PCAPdroid traffic capture is disabled (optional feature)"
            }
    
    # ========== Validation Interface (original ValidationService methods) ==========
    
    def validate_all(self) -> Tuple[bool, List[str]]:
        """
        Perform all validation checks.
        
        Returns:
            Tuple of (is_valid, list_of_messages)
        """
        all_issues = []
        all_warnings = []
        
        # Check Appium server
        if not self._check_appium_server():
            all_issues.append(VALIDATION_MESSAGES["APPIUM_FAIL"])
        
        # Check AI provider dependencies
        ai_issues, ai_warnings = self._check_ai_provider()
        all_issues.extend(ai_issues)
        all_warnings.extend(ai_warnings)
        
        # Check API keys and environment variables
        api_issues, api_warnings = self.check_api_keys_and_env()
        all_issues.extend(api_issues)
        all_warnings.extend(api_warnings)
        
        # Check target app is selected
        if not self.config.get('APP_PACKAGE', None):
            all_issues.append(VALIDATION_MESSAGES["TARGET_APP_MISSING"])
        
        # Check required configuration by iterating over default constants
        # Note: APP_PACKAGE is checked separately above with a better message
        # Note: _get_required_config_keys() already conditionally includes
        # PCAPDROID_API_KEY and MOBSF_API_KEY based on feature flags
        required_keys = self._get_required_config_keys()
        for key in required_keys:
            if not self.config.get(key, None):
                all_issues.append(VALIDATION_MESSAGES["MISSING_CONFIG"].format(key=key))
        
        # Check optional MobSF server
        mobsf_running = self._check_mobsf_server()
        if not mobsf_running:
            all_warnings.append(VALIDATION_MESSAGES["MOBSF_WARN"])
        
        # Combine all messages
        all_messages = all_issues + all_warnings
        
        return len(all_issues) == 0, all_messages
    
    def get_service_status_details(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed status information about all services.
        
        Returns:
            Dictionary with service status details
        """
        details = {}
        
        # Appium status
        appium_running = self._check_appium_server()
        appium_url = self.config.get('APPIUM_SERVER_URL', DEFAULT_APPIUM_URL)
        appium_base_msg = VALIDATION_MESSAGES["SERVICE_URL_TEMPLATE"].format(service="Appium", url=appium_url)
        details['appium'] = {
            'running': appium_running,
            'url': appium_url,
            'required': True,
            'message': appium_base_msg + (VALIDATION_MESSAGES["APPIUM_SUCCESS"] if appium_running else VALIDATION_MESSAGES["APPIUM_NOT_ACCESSIBLE"])
        }
        
        # MobSF status (optional)
        mobsf_running = self._check_mobsf_server()
        mobsf_url = self.config.get('MOBSF_API_URL', DEFAULT_MOBSF_URL)
        mobsf_enabled = self.config.get('ENABLE_MOBSF_ANALYSIS', False)
        mobsf_base_msg = VALIDATION_MESSAGES["SERVICE_URL_TEMPLATE"].format(service="MobSF", url=mobsf_url)
        details['mobsf'] = {
            'running': mobsf_running,
            'url': mobsf_url,
            'required': False,
            'enabled': mobsf_enabled,
            'message': mobsf_base_msg + (VALIDATION_MESSAGES["APPIUM_SUCCESS"] if mobsf_running else VALIDATION_MESSAGES["MOBSF_NOT_ACCESSIBLE"])
        }
        
        # AI Provider status
        ai_provider = self.config.get('AI_PROVIDER', DEFAULT_AI_PROVIDER).lower()
        if ai_provider == 'ollama':
            ollama_running = self._check_ollama_service()
            details['ollama'] = {
                'running': ollama_running,
                'required': True,
                'message': VALIDATION_MESSAGES["OLLAMA_SERVICE"] + (VALIDATION_MESSAGES["APPIUM_SUCCESS"] if ollama_running else VALIDATION_MESSAGES["OLLAMA_NOT_RUNNING"])
            }
        
        # API Keys status
        api_issues, api_warnings = self.check_api_keys_and_env()
        all_api_messages = api_issues + api_warnings
        details['api_keys'] = {
            'valid': len(api_issues) == 0,
            'issues': all_api_messages,
            'required': True,
            'message': VALIDATION_MESSAGES["API_KEYS_ISSUES"].format(issues=len(api_issues), warnings=len(api_warnings)) if all_api_messages else VALIDATION_MESSAGES["API_KEYS_ALL_GOOD"]
        }
        
        # Target app
        app_package = self.config.get('APP_PACKAGE', None)
        details['target_app'] = {
            'selected': app_package is not None,
            'package': app_package,
            'required': True,
            'message': VALIDATION_MESSAGES["TARGET_APP_TEMPLATE"].format(package=app_package) if app_package else VALIDATION_MESSAGES["TARGET_APP_NOT_SELECTED"]
        }
        
        return details
    
    # ========== Internal Helper Methods ==========
    
    def _check_appium_server(self) -> bool:
        """Check if Appium server is running and accessible."""
        try:
            appium_url = self.config.get('APPIUM_SERVER_URL', DEFAULT_APPIUM_URL)
            response = requests.get(f"{appium_url}{KEYS.APPIUM_STATUS_PATH}", timeout=APPIUM_STATUS_TIMEOUT)
            if response.status_code == KEYS.HTTP_CODE_OK:
                status_data = response.json()
                if status_data.get(KEYS.JSON_KEY_READY, False) or status_data.get(KEYS.JSON_KEY_VALUE, {}).get(KEYS.JSON_KEY_READY, False):
                    return True
        except Exception as e:
            self.logger.debug(f"Appium server check failed: {e}")
        return False
    
    def _check_mobsf_server(self) -> bool:
        """Check if MobSF server is running and accessible."""
        try:
            mobsf_url = self.config.get('MOBSF_API_URL', DEFAULT_MOBSF_URL)
            response = requests.get(f"{mobsf_url}{KEYS.MOBSF_STATUS_PATH}", timeout=MOBSF_STATUS_TIMEOUT)
            if response.status_code == KEYS.HTTP_CODE_OK:
                return True
        except Exception as e:
            self.logger.debug(f"MobSF server check failed: {e}")
        return False
    
    def _check_ollama_service(self) -> bool:
        """Check if Ollama service is running using HTTP API first, then subprocess fallback."""
        ollama_url = self.config.get('OLLAMA_BASE_URL', DEFAULT_OLLAMA_URL)
        
        try:
            response = requests.get(f"{ollama_url}{KEYS.OLLAMA_TAGS_PATH}", timeout=OLLAMA_API_TIMEOUT)
            if response.status_code == KEYS.HTTP_CODE_OK:
                self.logger.debug("Ollama service detected via HTTP API")
                return True
        except requests.RequestException as e:
            self.logger.debug(f"Ollama HTTP API check failed: {e}")
        except Exception as e:
            self.logger.debug(f"Unexpected error during Ollama HTTP check: {e}")
        
        # Fallback to subprocess check
        try:
            result = cli_run_subprocess(
                ['ollama', 'list'],
                timeout=OLLAMA_CLI_TIMEOUT,
                capture_output=True
            )
            if result.returncode == 0:
                self.logger.debug("Ollama service detected via subprocess")
                return True
        except Exception as e:
            self.logger.debug(f"Ollama subprocess check failed: {e}")
        
        self.logger.debug("Ollama service not detected")
        return False
    
    def _check_ai_provider(self) -> Tuple[List[str], List[str]]:
        """Check AI provider specific requirements using provider registry."""
        from domain.providers.registry import ProviderRegistry
        
        issues = []
        warnings = []
        ai_provider = self.config.get('AI_PROVIDER', DEFAULT_AI_PROVIDER)
        
        strategy = ProviderRegistry.get_by_name(ai_provider)
        if not strategy:
            warnings.append(f"Unknown AI provider: {ai_provider}")
            return issues, warnings
        
        # Validate provider configuration
        is_valid, error_msg = strategy.validate_config(self.config)
        if not is_valid and error_msg:
            issues.append(error_msg)
        
        # Check dependencies
        deps_ok, deps_msg = strategy.check_dependencies()
        if not deps_ok:
            issues.append(deps_msg)
        
        # Check service availability (Ollama-specific)
        if strategy.provider.value == 'ollama':
            if not self._check_ollama_service():
                issues.append(VALIDATION_MESSAGES["OLLAMA_NOT_RUNNING"])
            if not self.config.get('OLLAMA_BASE_URL', None):
                warnings.append(VALIDATION_MESSAGES["OLLAMA_URL_NOT_SET"])
        
        # Check if AI model is selected
        model_type = self.config.get('DEFAULT_MODEL_TYPE', None)
        if not model_type or (isinstance(model_type, str) and model_type.strip() == ''):
            issues.append(VALIDATION_MESSAGES["AI_MODEL_NOT_SELECTED"])
        
        return issues, warnings
    
    def check_api_keys_and_env(self) -> Tuple[List[str], List[str]]:
        """
        Check if required API keys and environment variables are provided.
        
        Returns:
            Tuple of (blocking_issues, warnings)
        """
        issues = []
        warnings = []
        ai_provider = self.config.get("AI_PROVIDER", DEFAULT_AI_PROVIDER)
        
        # Use provider strategy to check API keys
        from domain.providers.registry import ProviderRegistry
        strategy = ProviderRegistry.get_by_name(ai_provider)
        if strategy:
            is_valid, error_msg = strategy.validate_config(self.config)
            if not is_valid and error_msg:
                # Try to get a more user-friendly message
                key_name = strategy.get_api_key_name()
                issues.append(MSG.PRECHECK_STATUS_MESSAGE_MISSING_KEY.format(key=key_name.replace('_', ' ').title(), env=key_name))
        
        # Note: PCAPdroid API key is checked separately in check_pcapdroid() to avoid duplication
        # Check MobSF API key if MobSF analysis is enabled - but make it a warning, not blocking
        if self.config.get('ENABLE_MOBSF_ANALYSIS', False):
            if not self.config.get('MOBSF_API_KEY', None):
                warnings.append(MSG.PRECHECK_STATUS_MESSAGE_MISSING_KEY.format(key="API key", env="MOBSF_API_KEY"))
        
        return issues, warnings
    
    def check_dependencies(self, ai_provider: str) -> Tuple[bool, str]:
        """
        Check if dependencies are installed for the specified AI provider.
        
        Args:
            ai_provider: The AI provider to check dependencies for
            
        Returns:
            Tuple of (dependencies_installed, error_message)
        """
        from domain.model_adapters import check_dependencies
        return check_dependencies(ai_provider)
    
    def _get_required_config_keys(self) -> List[str]:
        """Get list of required configuration keys.
        
        Note: 
        - APPIUM_SERVER_URL has a hardcoded default (http://127.0.0.1:4723) so it's not required
        - PCAPDROID_API_KEY and MOBSF_API_KEY are optional and not included
        here even when features are enabled, as they should be warnings, not
        blocking issues. The crawler can run without them.
        """
        keys = [
            "AI_PROVIDER"
        ]
        
        # Note: We intentionally do NOT include:
        # - APPIUM_SERVER_URL: Has hardcoded default (http://127.0.0.1:4723) in ServiceURLs.APPIUM
        # - APP_PACKAGE: Checked separately above with a better message that includes the command
        # - PCAPDROID_API_KEY or MOBSF_API_KEY: Optional features, checked separately as warnings
        
        return keys
    
    def _extract_port_from_error(self, error_str: str, default_port: Optional[int] = None) -> Optional[int]:
        """
        Extract port number from connection error message.
        
        Args:
            error_str: Error message string
            default_port: Default port to return if extraction fails
            
        Returns:
            Port number or default_port if not found
        """
        import re
        # Try to extract port from patterns like "port=4723" or "port:4723"
        match = re.search(r'port[=:](\d+)', error_str, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return default_port
    
    def _format_connection_error(self, error: Exception, service_name: str, url: str) -> str:
        """
        Format connection error into a shorter, user-friendly message.
        
        Args:
            error: Exception object
            service_name: Name of the service (e.g., "Appium Server", "MCP Server")
            url: Service URL
            
        Returns:
            Formatted error message
        """
        error_str = str(error)
        port = self._extract_port_from_error(error_str)
        
        # Try to extract port from URL if not found in error
        if port is None:
            import re
            url_match = re.search(r':(\d+)', url)
            if url_match:
                try:
                    port = int(url_match.group(1))
                except ValueError:
                    pass
        
        if port:
            return MSG.PRECHECK_STATUS_MESSAGE_NOT_RUNNING_PORT.format(port=port)
        else:
            return MSG.PRECHECK_STATUS_MESSAGE_NOT_ACCESSIBLE.format(url=url)
    
    def _get_appium_url(self) -> str:
        """Get Appium URL from config."""
        return self.config.get('CONFIG_APPIUM_SERVER_URL') or self.config.get('APPIUM_SERVER_URL', DEFAULT_APPIUM_URL)
    
    def _get_mobsf_url(self) -> str:
        """Get MobSF URL from config."""
        return self.config.get('CONFIG_MOBSF_API_URL') or self.config.get('MOBSF_API_URL', DEFAULT_MOBSF_URL)
    
    def _get_ollama_url(self) -> str:
        """Get Ollama URL from config."""
        return self.config.get('CONFIG_OLLAMA_BASE_URL') or self.config.get('OLLAMA_BASE_URL', DEFAULT_OLLAMA_URL)

