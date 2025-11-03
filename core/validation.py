"""
Shared validation utilities for crawler pre-flight checks.

This module provides validation services used by both CLI and UI interfaces
to verify dependencies and configuration before starting the crawler.
"""

import logging
import subprocess
import sys
from typing import Any, Dict, List, Tuple

import requests

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from config.config import Config

from cli.commands.services_check import PrecheckCommand

# Default Service URLs
DEFAULT_APPIUM_URL = 'http://127.0.0.1:4723'
DEFAULT_MOBSF_URL = 'http://localhost:8000/api/v1'
DEFAULT_OLLAMA_URL = 'http://localhost:11434'
DEFAULT_MCP_URL = 'http://localhost:3000/mcp'

# Default Timeouts
DEFAULT_HTTP_TIMEOUT = 3.0
OLLAMA_API_TIMEOUT = 1.5
OLLAMA_SUBPROC_TIMEOUT = 2.0

# Default Settings
DEFAULT_AI_PROVIDER = 'gemini'

# Module-level dictionary for all user-facing validation messages
VALIDATION_MESSAGES = {
    "APPIUM_FAIL": "❌ Appium server is not running or not accessible",
    "APPIUM_SUCCESS": "is running ✅",
    "APPIUM_NOT_ACCESSIBLE": "is not accessible ❌",
    "MOBSF_WARN": "⚠️ MobSF server is not running (optional)",
    "TARGET_APP_MISSING": "❌ No target app selected",
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
    "MCP_RUNNING": "MCP server at {url} is running ✅",
    "MCP_NOT_ACCESSIBLE": "MCP server at {url} is not accessible ⚠️",
    "OLLAMA_SERVICE": "Ollama service",
    "MOBSF_NOT_ACCESSIBLE": " is not accessible ⚠️"
}


class ValidationService:
    """Service for validating crawler dependencies and configuration."""
    
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
        self.config = config
        self.logger = logging.getLogger(__name__)
    
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
        api_issues, api_warnings = self._check_api_keys_and_env()
        all_issues.extend(api_issues)
        all_warnings.extend(api_warnings)
        
        # Check target app is selected
        if not getattr(self.config, 'APP_PACKAGE', None):
            all_issues.append(VALIDATION_MESSAGES["TARGET_APP_MISSING"])
        
        # Check required configuration by iterating over default constants
        required_keys = self._get_required_config_keys()
        for key in required_keys:
            if not getattr(self.config, key, None):
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
        appium_url = getattr(self.config, 'APPIUM_SERVER_URL', DEFAULT_APPIUM_URL)
        appium_base_msg = VALIDATION_MESSAGES["SERVICE_URL_TEMPLATE"].format(service="Appium", url=appium_url)
        details['appium'] = {
            'running': appium_running,
            'url': appium_url,
            'required': True,
            'message': appium_base_msg + (VALIDATION_MESSAGES["APPIUM_SUCCESS"] if appium_running else VALIDATION_MESSAGES["APPIUM_NOT_ACCESSIBLE"])
        }
        
        # MobSF status (optional)
        mobsf_running = self._check_mobsf_server()
        mobsf_url = getattr(self.config, 'MOBSF_API_URL', DEFAULT_MOBSF_URL)
        mobsf_enabled = getattr(self.config, 'ENABLE_MOBSF_ANALYSIS', False)
        mobsf_base_msg = VALIDATION_MESSAGES["SERVICE_URL_TEMPLATE"].format(service="MobSF", url=mobsf_url)
        details['mobsf'] = {
            'running': mobsf_running,
            'url': mobsf_url,
            'required': False,
            'enabled': mobsf_enabled,
            'message': mobsf_base_msg + (VALIDATION_MESSAGES["APPIUM_SUCCESS"] if mobsf_running else VALIDATION_MESSAGES["MOBSF_NOT_ACCESSIBLE"])
        }
        
        # AI Provider status
        ai_provider = getattr(self.config, 'AI_PROVIDER', DEFAULT_AI_PROVIDER).lower()
        if ai_provider == 'ollama':
            ollama_running = self._check_ollama_service()
            details['ollama'] = {
                'running': ollama_running,
                'required': True,
                'message': VALIDATION_MESSAGES["OLLAMA_SERVICE"] + (VALIDATION_MESSAGES["APPIUM_SUCCESS"] if ollama_running else VALIDATION_MESSAGES["OLLAMA_NOT_RUNNING"])
            }
        
        # API Keys status
        api_issues, api_warnings = self._check_api_keys_and_env()
        all_api_messages = api_issues + api_warnings
        details['api_keys'] = {
            'valid': len(api_issues) == 0,
            'issues': all_api_messages,
            'required': True,
            'message': VALIDATION_MESSAGES["API_KEYS_ISSUES"].format(issues=len(api_issues), warnings=len(api_warnings)) if all_api_messages else VALIDATION_MESSAGES["API_KEYS_ALL_GOOD"]
        }
        
        # Target app
        app_package = getattr(self.config, 'APP_PACKAGE', None)
        details['target_app'] = {
            'selected': app_package is not None,
            'package': app_package,
            'required': True,
            'message': VALIDATION_MESSAGES["TARGET_APP_TEMPLATE"].format(package=app_package) if app_package else VALIDATION_MESSAGES["TARGET_APP_NOT_SELECTED"]
        }
        
        # MCP status
        cmd = PrecheckCommand()
        mcp_status = cmd._check_mcp_server_health(self.config)
        mcp_running = mcp_status['status'] == 'running'
        mcp_url = getattr(self.config, 'MCP_SERVER_URL', DEFAULT_MCP_URL)
        if mcp_running:
            message = VALIDATION_MESSAGES["MCP_RUNNING"].format(url=mcp_url)
        else:
            message = VALIDATION_MESSAGES["MCP_NOT_ACCESSIBLE"].format(url=mcp_url)
        details['mcp'] = {
            'running': mcp_running,
            'url': mcp_url,
            'required': False,
            'message': message
        }
        
        return details
    
    def _check_appium_server(self) -> bool:
        """Check if Appium server is running and accessible."""
        try:
            appium_url = getattr(self.config, 'APPIUM_SERVER_URL', DEFAULT_APPIUM_URL)
            # Try to connect to Appium status endpoint with shorter timeout
            response = requests.get(f"{appium_url}/status", timeout=DEFAULT_HTTP_TIMEOUT)
            if response.status_code == 200:
                status_data = response.json()
                # Check for 'ready' field, handling both direct and nested formats
                if status_data.get('ready', False) or status_data.get('value', {}).get('ready', False):
                    return True
        except Exception as e:
            self.logger.debug(f"Appium server check failed: {e}")
        
        return False
    
    def _check_mobsf_server(self) -> bool:
        """Check if MobSF server is running and accessible."""
        try:
            mobsf_url = getattr(self.config, 'MOBSF_API_URL', DEFAULT_MOBSF_URL)
            # Try to connect to MobSF API with shorter timeout
            response = requests.get(f"{mobsf_url}/server_status", timeout=DEFAULT_HTTP_TIMEOUT)
            if response.status_code == 200:
                return True
        except Exception as e:
            self.logger.debug(f"MobSF server check failed: {e}")
        
        return False
    
    def _check_ollama_service(self) -> bool:
        """Check if Ollama service is running using HTTP API first, then subprocess fallback."""
        # First try HTTP API check (fast and non-blocking)
        ollama_url = getattr(self.config, 'OLLAMA_BASE_URL', DEFAULT_OLLAMA_URL)
        
        try:
            # Try to connect to Ollama API endpoint with shorter timeout
            response = requests.get(f"{ollama_url}/api/tags", timeout=OLLAMA_API_TIMEOUT)
            if response.status_code == 200:
                self.logger.debug("Ollama service detected via HTTP API")
                return True
        except requests.RequestException as e:
            self.logger.debug(f"Ollama HTTP API check failed: {e}")
        except Exception as e:
            self.logger.debug(f"Unexpected error during Ollama HTTP check: {e}")
        
        # Fallback to subprocess check if HTTP fails
        try:
            result = subprocess.run(['ollama', 'list'],
                                capture_output=True,
                                text=True,
                                timeout=OLLAMA_SUBPROC_TIMEOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            if result.returncode == 0:
                self.logger.debug("Ollama service detected via subprocess")
                return True
        except subprocess.TimeoutExpired:
            self.logger.debug("Ollama subprocess check timed out")
        except FileNotFoundError:
            self.logger.debug("Ollama executable not found")
        except subprocess.SubprocessError as e:
            self.logger.debug(f"Ollama subprocess check failed: {e}")
        except Exception as e:
            self.logger.debug(f"Unexpected error during Ollama subprocess check: {e}")
        
        self.logger.debug("Ollama service not detected")
        return False
    
    def _check_ai_provider(self) -> Tuple[List[str], List[str]]:
        """Check AI provider specific requirements."""
        issues = []
        warnings = []
        ai_provider = getattr(self.config, 'AI_PROVIDER', DEFAULT_AI_PROVIDER).lower()
        
        # Get provider requirements from dictionary
        provider_config = self.AI_PROVIDER_REQUIREMENTS.get(ai_provider)
        if not provider_config:
            # Unknown provider, add a warning
            warnings.append(f"Unknown AI provider: {ai_provider}")
            return issues, warnings
        
        # Check if service is running if required
        service_check_method = provider_config.get('service_check')
        if service_check_method:
            check_method = getattr(self, service_check_method)
            if not check_method():
                issues.append(VALIDATION_MESSAGES["OLLAMA_NOT_RUNNING"])
        
        # Check for optional URL setting
        if ai_provider == 'ollama' and not getattr(self.config, 'OLLAMA_BASE_URL', None):
            warnings.append(VALIDATION_MESSAGES["OLLAMA_URL_NOT_SET"])
        
        return issues, warnings
    
    def _check_api_keys_and_env(self) -> Tuple[List[str], List[str]]:
        """Check if required API keys and environment variables are provided.
        
        Returns:
            Tuple of (blocking_issues, warnings)
        """
        issues = []
        warnings = []
        ai_provider = getattr(self.config, 'AI_PROVIDER', DEFAULT_AI_PROVIDER).lower()
        
        # Get provider requirements from dictionary
        provider_config = self.AI_PROVIDER_REQUIREMENTS.get(ai_provider)
        if not provider_config:
            # Unknown provider, add a warning
            warnings.append(f"Unknown AI provider: {ai_provider}")
            return issues, warnings
        
        # Check required keys for the provider
        required_keys = provider_config.get('required_keys', [])
        for key in required_keys:
            if not getattr(self.config, key, None):
                message_key = provider_config.get('message_key')
                if message_key:
                    issues.append(VALIDATION_MESSAGES[message_key])
        
        # Check for optional URL setting for ollama
        if ai_provider == 'ollama' and not getattr(self.config, 'OLLAMA_BASE_URL', None):
            warnings.append(VALIDATION_MESSAGES["OLLAMA_URL_NOT_SET"])
        
        # Check PCAPdroid API key if traffic capture is enabled
        if getattr(self.config, 'ENABLE_TRAFFIC_CAPTURE', False):
            if not getattr(self.config, 'PCAPDROID_API_KEY', None):
                issues.append(VALIDATION_MESSAGES["PCAPDROID_API_KEY_MISSING"])
        
        # Check MobSF API key if MobSF analysis is enabled
        if getattr(self.config, 'ENABLE_MOBSF_ANALYSIS', False):
            if not getattr(self.config, 'MOBSF_API_KEY', None):
                issues.append(VALIDATION_MESSAGES["MOBSF_API_KEY_MISSING"])
        
        return issues, warnings
    
    def check_dependencies(self, ai_provider: str) -> Tuple[bool, str]:
        """
        Check if dependencies are installed for the specified AI provider.
        
        Args:
            ai_provider: The AI provider to check dependencies for
            
        Returns:
            Tuple of (dependencies_installed, error_message)
        """
        # Direct import from domain.model_adapters
        from domain.model_adapters import check_dependencies
        
        return check_dependencies(ai_provider)
    
    def _get_required_config_keys(self) -> List[str]:
        """
        Get list of required configuration keys from config module.
        
        Returns:
            List of required configuration keys
        """
        # Import config module to access required keys list
        import config.config as config_module
        
        # Define the required configuration keys directly
        # This makes the validation module independent of config module internals
        required_keys = [
            "APPIUM_SERVER_URL",
            "AI_PROVIDER",
            "APP_PACKAGE",
            "ENABLE_TRAFFIC_CAPTURE",
            "PCAPDROID_API_KEY",
            "ENABLE_MOBSF_ANALYSIS",
            "MOBSF_API_KEY"
        ]
        
        return required_keys
