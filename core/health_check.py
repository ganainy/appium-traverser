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
    from config.config import Config

# Try to import CLI constants, but make them optional for backward compatibility
try:
    from cli.constants import messages as MSG
    from cli.constants import keys as KEYS
    from cli.constants import config as CFG
    from cli.services.process_utils import run_subprocess as cli_run_subprocess
    CLI_CONSTANTS_AVAILABLE = True
except ImportError:
    CLI_CONSTANTS_AVAILABLE = False
    # Fallback values if CLI constants not available
    MSG = None
    KEYS = None
    CFG = None
    cli_run_subprocess = None

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
        service_name = self._get_service_name('appium')
        services[service_name] = appium_status
        
        # Check MCP server health
        mcp_status = self.check_mcp_server_health()
        service_name = self._get_service_name('mcp')
        services[service_name] = mcp_status
        
        # Check MobSF server
        mobsf_status = self.check_mobsf_server()
        service_name = self._get_service_name('mobsf')
        services[service_name] = mobsf_status
        
        # Check Ollama service if needed
        ai_provider = self.config.get("AI_PROVIDER", DEFAULT_AI_PROVIDER).lower()
        if ai_provider == 'ollama':
            ollama_status = self.check_ollama_service()
            service_name = self._get_service_name('ollama')
            services[service_name] = ollama_status
        
        # Check PCAPdroid (always show as separate service)
        pcapdroid_status = self.check_pcapdroid()
        service_name = self._get_service_name('pcapdroid')
        services[service_name] = pcapdroid_status
        
        # Check API keys and environment
        api_issues, api_warnings = self.check_api_keys_and_env()
        service_name = self._get_service_name('api_keys')
        if api_issues:
            services[service_name] = {
                self._get_status_key('status'): self._get_status_value('error'),
                self._get_status_key('message'): '; '.join(api_issues)
            }
        elif api_warnings:
            services[service_name] = {
                self._get_status_key('status'): self._get_status_value('warning'),
                self._get_status_key('message'): '; '.join(api_warnings)
            }
        else:
            ok_message = self._get_message('ok') if CLI_CONSTANTS_AVAILABLE else VALIDATION_MESSAGES["API_KEYS_ALL_GOOD"]
            services[service_name] = {
                self._get_status_key('status'): self._get_status_value('running'),
                self._get_status_key('message'): ok_message
            }
        
        # Check target app
        # Use get() to properly check user store, env vars, and defaults in order
        app_package = self.config.get("APP_PACKAGE", None)
        service_name = self._get_service_name('target_app')
        if app_package:
            selected_msg = self._get_message('selected', app_package=app_package) if CLI_CONSTANTS_AVAILABLE else f"Selected: {app_package}"
            services[service_name] = {
                self._get_status_key('status'): self._get_status_value('running'),
                self._get_status_key('message'): selected_msg
            }
        else:
            no_app_msg = self._get_message('no_app') if CLI_CONSTANTS_AVAILABLE else VALIDATION_MESSAGES["TARGET_APP_NOT_SELECTED"]
            services[service_name] = {
                self._get_status_key('status'): self._get_status_value('error'),
                self._get_status_key('message'): no_app_msg
            }
        
        return services
    
    def check_appium_server(self) -> Dict[str, str]:
        """Check Appium server status and return detailed status dict."""
        try:
            appium_url = self._get_appium_url().rstrip('/')
            status_path = self._get_path('appium_status')
            timeout = self._get_timeout('appium_status')
            response = requests.get(f"{appium_url}{status_path}", timeout=timeout)
            
            http_ok = self._get_http_code('ok')
            if response.status_code == http_ok:
                status_data = response.json()
                ready_key = self._get_json_key('ready')
                value_key = self._get_json_key('value')
                ready = (
                    status_data.get(ready_key, False) or
                    status_data.get(value_key, {}).get(ready_key, False)
                )
                if ready:
                    reachable_msg = self._get_message('reachable', url=appium_url) if CLI_CONSTANTS_AVAILABLE else VALIDATION_MESSAGES["APPIUM_SUCCESS"]
                    return {
                        self._get_status_key('status'): self._get_status_value('running'),
                        self._get_status_key('message'): reachable_msg
                    }
                else:
                    not_ready_msg = self._get_message('not_ready', url=appium_url) if CLI_CONSTANTS_AVAILABLE else VALIDATION_MESSAGES["APPIUM_NOT_ACCESSIBLE"]
                    return {
                        self._get_status_key('status'): self._get_status_value('warning'),
                        self._get_status_key('message'): not_ready_msg
                    }
            else:
                http_msg = self._get_message('http', code=response.status_code, url=appium_url) if CLI_CONSTANTS_AVAILABLE else f"HTTP {response.status_code} at {appium_url}"
                return {
                    self._get_status_key('status'): self._get_status_value('error'),
                    self._get_status_key('message'): http_msg
                }
        except Exception as e:
            appium_url = self._get_appium_url()
            conn_fail_msg = self._format_connection_error(e, "Appium Server", appium_url)
            return {
                self._get_status_key('status'): self._get_status_value('error'),
                self._get_status_key('message'): conn_fail_msg
            }
    
    def check_mcp_server_health(self) -> Dict[str, str]:
        """Check MCP server health status using /health and /ready endpoints."""
        try:
            mcp_url = self._get_mcp_url()
            base_url = mcp_url.rstrip('/mcp').rstrip('/')
            ready_path = self._get_path('mcp_ready')
            health_path = self._get_path('mcp_health')
            timeout = self._get_timeout('mcp_status')
            http_ok = self._get_http_code('ok')
            http_unavailable = self._get_http_code('service_unavailable')
            
            try:
                response = requests.get(f"{base_url}{ready_path}", timeout=timeout)
                if response.status_code == http_ok:
                    ready_data = response.json()
                    # Extract from details if present, otherwise try top-level
                    if "details" in ready_data:
                        details = ready_data["details"]
                    else:
                        details = ready_data
                    uptime_key = self._get_json_key('uptime_ms')
                    tools_key = self._get_json_key('registered_tools')
                    active_key = self._get_json_key('active_invocations')
                    uptime_ms = details.get("uptimeMs", details.get(uptime_key, 0)) or 0
                    registered_tools = details.get("registeredTools", details.get(tools_key, 0)) or 0
                    active_invocations = details.get("activeInvocations", details.get(active_key, 0)) or 0
                    
                    if CLI_CONSTANTS_AVAILABLE:
                        ready_msg = self._get_message('ready', url=base_url, tools=registered_tools, active=active_invocations, uptime=uptime_ms)
                    else:
                        ready_msg = VALIDATION_MESSAGES["MCP_RUNNING"].format(url=base_url)
                    
                    return {
                        self._get_status_key('status'): self._get_status_value('running'),
                        self._get_status_key('message'): ready_msg
                    }
                elif response.status_code == http_unavailable:
                    not_ready_msg = self._get_message('not_ready_unavailable', url=base_url) if CLI_CONSTANTS_AVAILABLE else VALIDATION_MESSAGES["MCP_NOT_ACCESSIBLE"].format(url=base_url)
                    return {
                        self._get_status_key('status'): self._get_status_value('warning'),
                        self._get_status_key('message'): not_ready_msg
                    }
                else:
                    http_msg = self._get_message('http', code=response.status_code, url=f"{base_url}{ready_path}") if CLI_CONSTANTS_AVAILABLE else f"HTTP {response.status_code}"
                    return {
                        self._get_status_key('status'): self._get_status_value('error'),
                        self._get_status_key('message'): http_msg
                    }
            except requests.exceptions.Timeout:
                try:
                    response = requests.get(f"{base_url}{health_path}", timeout=timeout)
                    if response.status_code == http_ok:
                        health_data = response.json()
                        uptime_key = self._get_json_key('uptime_ms')
                        uptime_ms = health_data.get(uptime_key, 0)
                        health_alive_msg = self._get_message('health_alive', url=base_url, uptime=uptime_ms) if CLI_CONSTANTS_AVAILABLE else VALIDATION_MESSAGES["MCP_NOT_ACCESSIBLE"].format(url=base_url)
                        return {
                            self._get_status_key('status'): self._get_status_value('warning'),
                            self._get_status_key('message'): health_alive_msg
                        }
                    else:
                        http_msg = self._get_message('http', code=response.status_code, url=f"{base_url}{health_path}") if CLI_CONSTANTS_AVAILABLE else f"HTTP {response.status_code}"
                        return {
                            self._get_status_key('status'): self._get_status_value('error'),
                            self._get_status_key('message'): http_msg
                        }
                except Exception as health_error:
                    health_fail_msg = self._format_connection_error(health_error, "MCP Server", base_url)
                    return {
                        self._get_status_key('status'): self._get_status_value('error'),
                        self._get_status_key('message'): health_fail_msg
                    }
        except Exception as e:
            mcp_url = self._get_mcp_url()
            base_url = mcp_url.rstrip('/mcp').rstrip('/') if mcp_url else "unknown"
            mcp_fail_msg = self._format_connection_error(e, "MCP Server", base_url)
            return {
                self._get_status_key('status'): self._get_status_value('error'),
                self._get_status_key('message'): mcp_fail_msg
            }
    
    def check_mobsf_server(self) -> Dict[str, str]:
        """Check MobSF server status and return detailed status dict."""
        # Only check MobSF if analysis is enabled
        if not self.config.get("ENABLE_MOBSF_ANALYSIS", False):
            return {
                self._get_status_key('status'): self._get_status_value('warning'),
                self._get_status_key('message'): "MobSF analysis is disabled (optional feature)"
            }
        
        try:
            mobsf_url = self._get_mobsf_url()
            status_path = self._get_path('mobsf_status')
            timeout = self._get_timeout('mobsf_status')
            http_ok = self._get_http_code('ok')
            response = requests.get(f"{mobsf_url}{status_path}", timeout=timeout)
            if response.status_code == http_ok:
                reachable_msg = self._get_message('reachable', url=mobsf_url) if CLI_CONSTANTS_AVAILABLE else VALIDATION_MESSAGES["APPIUM_SUCCESS"]
                return {
                    self._get_status_key('status'): self._get_status_value('running'),
                    self._get_status_key('message'): reachable_msg
                }
            else:
                http_msg = self._get_message('http', code=response.status_code, url=mobsf_url) if CLI_CONSTANTS_AVAILABLE else f"HTTP {response.status_code}"
                return {
                    self._get_status_key('status'): self._get_status_value('warning'),
                    self._get_status_key('message'): http_msg
                }
        except Exception as e:
            mobsf_url = self._get_mobsf_url()
            conn_fail_msg = self._format_connection_error(e, "MobSF Server", mobsf_url)
            return {
                self._get_status_key('status'): self._get_status_value('warning'),
                self._get_status_key('message'): conn_fail_msg
            }
    
    def check_ollama_service(self) -> Dict[str, str]:
        """Check Ollama service status and return detailed status dict."""
        ollama_url = self._get_ollama_url()
        tags_path = self._get_path('ollama_tags')
        timeout = self._get_timeout('ollama_api')
        http_ok = self._get_http_code('ok')
        
        try:
            response = requests.get(f"{ollama_url}{tags_path}", timeout=timeout)
            if response.status_code == http_ok:
                api_reachable_msg = self._get_message('api_reachable', url=ollama_url) if CLI_CONSTANTS_AVAILABLE else VALIDATION_MESSAGES["APPIUM_SUCCESS"]
                return {
                    self._get_status_key('status'): self._get_status_value('running'),
                    self._get_status_key('message'): api_reachable_msg
                }
        except Exception:
            pass
        
        # Fallback to subprocess check
        try:
            cli_timeout = self._get_timeout('ollama_cli')
            if cli_run_subprocess:
                result = cli_run_subprocess(
                    ["ollama", "list"],
                    timeout=cli_timeout,
                    capture_output=True
                )
            else:
                result = subprocess.run(
                    ['ollama', 'list'],
                    capture_output=True,
                    text=True,
                    timeout=cli_timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
            
            if result.returncode == 0:
                cli_msg = self._get_message('cli_accessible') if CLI_CONSTANTS_AVAILABLE else "CLI accessible"
                return {
                    self._get_status_key('status'): self._get_status_value('running'),
                    self._get_status_key('message'): cli_msg
                }
            else:
                cli_not_msg = self._get_message('cli_not_accessible') if CLI_CONSTANTS_AVAILABLE else "CLI not accessible"
                return {
                    self._get_status_key('status'): self._get_status_value('error'),
                    self._get_status_key('message'): cli_not_msg
                }
        except Exception:
            not_accessible_msg = self._get_message('not_accessible', url=ollama_url) if CLI_CONSTANTS_AVAILABLE else VALIDATION_MESSAGES["OLLAMA_NOT_RUNNING"]
            return {
                self._get_status_key('status'): self._get_status_value('error'),
                self._get_status_key('message'): not_accessible_msg
            }
    
    def check_pcapdroid(self) -> Dict[str, str]:
        """Check PCAPdroid traffic capture status and return detailed status dict."""
        if self.config.get("ENABLE_TRAFFIC_CAPTURE", False):
            if not self.config.get("PCAPDROID_API_KEY", None):
                missing_key_msg = self._get_message('missing_key', key="API key", env="PCAPDROID_API_KEY") if CLI_CONSTANTS_AVAILABLE else "API key not set (check PCAPDROID_API_KEY in .env)"
                return {
                    self._get_status_key('status'): self._get_status_value('warning'),
                    self._get_status_key('message'): missing_key_msg
                }
            else:
                return {
                    self._get_status_key('status'): self._get_status_value('running'),
                    self._get_status_key('message'): "PCAPDroid API key is configured (traffic capture enabled)"
                }
        else:
            return {
                self._get_status_key('status'): self._get_status_value('warning'),
                self._get_status_key('message'): "PCAPDroid traffic capture is disabled (optional feature)"
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
        api_issues, api_warnings = self._check_api_keys_and_env()
        all_issues.extend(api_issues)
        all_warnings.extend(api_warnings)
        
        # Check target app is selected
        if not self.config.get('APP_PACKAGE', None):
            all_issues.append(VALIDATION_MESSAGES["TARGET_APP_MISSING"])
        
        # Check required configuration by iterating over default constants
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
            Dictionary with service status details (legacy format for UI compatibility)
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
        api_issues, api_warnings = self._check_api_keys_and_env()
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
        
        # MCP status - use check_mcp_server_health for consistency
        mcp_status = self.check_mcp_server_health()
        mcp_running = mcp_status.get(self._get_status_key('status')) == self._get_status_value('running')
        mcp_url = self.config.get('MCP_SERVER_URL', DEFAULT_MCP_URL)
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
    
    # ========== Internal Helper Methods ==========
    
    def _check_appium_server(self) -> bool:
        """Check if Appium server is running and accessible."""
        try:
            appium_url = self.config.get('APPIUM_SERVER_URL', DEFAULT_APPIUM_URL)
            response = requests.get(f"{appium_url}/status", timeout=DEFAULT_HTTP_TIMEOUT)
            if response.status_code == 200:
                status_data = response.json()
                if status_data.get('ready', False) or status_data.get('value', {}).get('ready', False):
                    return True
        except Exception as e:
            self.logger.debug(f"Appium server check failed: {e}")
        return False
    
    def _check_mobsf_server(self) -> bool:
        """Check if MobSF server is running and accessible."""
        try:
            mobsf_url = self.config.get('MOBSF_API_URL', DEFAULT_MOBSF_URL)
            response = requests.get(f"{mobsf_url}/server_status", timeout=DEFAULT_HTTP_TIMEOUT)
            if response.status_code == 200:
                return True
        except Exception as e:
            self.logger.debug(f"MobSF server check failed: {e}")
        return False
    
    def _check_ollama_service(self) -> bool:
        """Check if Ollama service is running using HTTP API first, then subprocess fallback."""
        ollama_url = self.config.get('OLLAMA_BASE_URL', DEFAULT_OLLAMA_URL)
        
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=OLLAMA_API_TIMEOUT)
            if response.status_code == 200:
                self.logger.debug("Ollama service detected via HTTP API")
                return True
        except requests.RequestException as e:
            self.logger.debug(f"Ollama HTTP API check failed: {e}")
        except Exception as e:
            self.logger.debug(f"Unexpected error during Ollama HTTP check: {e}")
        
        # Fallback to subprocess check
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
        ai_provider = self.config.get('AI_PROVIDER', DEFAULT_AI_PROVIDER).lower()
        
        provider_config = self.AI_PROVIDER_REQUIREMENTS.get(ai_provider)
        if not provider_config:
            warnings.append(f"Unknown AI provider: {ai_provider}")
            return issues, warnings
        
        service_check_method = provider_config.get('service_check')
        if service_check_method:
            check_method = getattr(self, service_check_method)
            if not check_method():
                issues.append(VALIDATION_MESSAGES["OLLAMA_NOT_RUNNING"])
        
        if ai_provider == 'ollama' and not self.config.get('OLLAMA_BASE_URL', None):
            warnings.append(VALIDATION_MESSAGES["OLLAMA_URL_NOT_SET"])
        
        return issues, warnings
    
    def check_api_keys_and_env(self) -> Tuple[List[str], List[str]]:
        """
        Check if required API keys and environment variables are provided.
        
        Returns:
            Tuple of (blocking_issues, warnings)
        """
        issues = []
        warnings = []
        ai_provider = self.config.get("AI_PROVIDER", DEFAULT_AI_PROVIDER).lower()
        
        if ai_provider == 'gemini':
            if not self.config.get("GEMINI_API_KEY", None):
                if CLI_CONSTANTS_AVAILABLE:
                    issues.append(self._get_message('missing_key', key="Gemini API key", env="GEMINI_API_KEY"))
                else:
                    issues.append(VALIDATION_MESSAGES["GEMINI_API_KEY_MISSING"])
        elif ai_provider == 'openrouter':
            if not self.config.get("OPENROUTER_API_KEY", None):
                if CLI_CONSTANTS_AVAILABLE:
                    issues.append(self._get_message('missing_key', key="OpenRouter API key", env="OPENROUTER_API_KEY"))
                else:
                    issues.append(VALIDATION_MESSAGES["OPENROUTER_API_KEY_MISSING"])
        
        # Note: PCAPdroid API key is checked separately in check_pcapdroid() to avoid duplication
        # Check MobSF API key if MobSF analysis is enabled
        if self.config.get('ENABLE_MOBSF_ANALYSIS', False):
            if not self.config.get('MOBSF_API_KEY', None):
                if CLI_CONSTANTS_AVAILABLE:
                    issues.append(self._get_message('missing_key', key="API key", env="MOBSF_API_KEY"))
                else:
                    issues.append("API key not set (check MOBSF_API_KEY in .env)")
        
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
        """Get list of required configuration keys."""
        return [
            "APPIUM_SERVER_URL",
            "AI_PROVIDER",
            "APP_PACKAGE",
            "ENABLE_TRAFFIC_CAPTURE",
            "PCAPDROID_API_KEY",
            "ENABLE_MOBSF_ANALYSIS",
            "MOBSF_API_KEY"
        ]
    
    # ========== Helper methods for CLI constants compatibility ==========
    
    def _get_service_name(self, service: str) -> str:
        """Get service name, using CLI constants if available."""
        if CLI_CONSTANTS_AVAILABLE:
            service_map = {
                'appium': KEYS.SERVICE_APPIUM,
                'mcp': KEYS.SERVICE_MCP,
                'mobsf': KEYS.SERVICE_MOBSF,
                'ollama': KEYS.SERVICE_OLLAMA,
                'pcapdroid': KEYS.SERVICE_PCAPDROID,
                'api_keys': KEYS.SERVICE_API_KEYS,
                'target_app': KEYS.SERVICE_TARGET_APP
            }
            return service_map.get(service, service)
        return service
    
    def _get_status_key(self, key: str) -> str:
        """Get status key name, using CLI constants if available."""
        if CLI_CONSTANTS_AVAILABLE:
            key_map = {
                'status': KEYS.STATUS_KEY_STATUS,
                'message': KEYS.STATUS_KEY_MESSAGE
            }
            return key_map.get(key, key)
        return key
    
    def _get_status_value(self, value: str) -> str:
        """Get status value, using CLI constants if available."""
        if CLI_CONSTANTS_AVAILABLE:
            value_map = {
                'running': KEYS.STATUS_RUNNING,
                'warning': KEYS.STATUS_WARNING,
                'error': KEYS.STATUS_ERROR
            }
            return value_map.get(value, value)
        return value
    
    def _get_path(self, path_type: str) -> str:
        """Get path constant, using CLI constants if available."""
        if CLI_CONSTANTS_AVAILABLE:
            path_map = {
                'appium_status': KEYS.APPIUM_STATUS_PATH,
                'mcp_ready': KEYS.MCP_READY_PATH,
                'mcp_health': KEYS.MCP_HEALTH_PATH,
                'mobsf_status': KEYS.MOBSF_STATUS_PATH,
                'ollama_tags': KEYS.OLLAMA_TAGS_PATH
            }
            return path_map.get(path_type, '/status')
        # Fallback paths
        path_fallbacks = {
            'appium_status': '/status',
            'mcp_ready': '/ready',
            'mcp_health': '/health',
            'mobsf_status': '/server_status',
            'ollama_tags': '/api/tags'
        }
        return path_fallbacks.get(path_type, '/status')
    
    def _get_timeout(self, timeout_type: str) -> float:
        """Get timeout value, using CLI constants if available."""
        if CLI_CONSTANTS_AVAILABLE:
            timeout_map = {
                'appium_status': CFG.APPIUM_STATUS_TIMEOUT,
                'mcp_status': CFG.MCP_STATUS_TIMEOUT,
                'mobsf_status': CFG.MOBSF_STATUS_TIMEOUT,
                'ollama_api': CFG.OLLAMA_API_TIMEOUT,
                'ollama_cli': CFG.OLLAMA_CLI_TIMEOUT
            }
            return timeout_map.get(timeout_type, DEFAULT_HTTP_TIMEOUT)
        # Fallback timeouts
        timeout_fallbacks = {
            'appium_status': DEFAULT_HTTP_TIMEOUT,
            'mcp_status': DEFAULT_HTTP_TIMEOUT,
            'mobsf_status': DEFAULT_HTTP_TIMEOUT,
            'ollama_api': OLLAMA_API_TIMEOUT,
            'ollama_cli': OLLAMA_SUBPROC_TIMEOUT
        }
        return timeout_fallbacks.get(timeout_type, DEFAULT_HTTP_TIMEOUT)
    
    def _get_http_code(self, code_type: str) -> int:
        """Get HTTP code constant, using CLI constants if available."""
        if CLI_CONSTANTS_AVAILABLE:
            code_map = {
                'ok': KEYS.HTTP_CODE_OK,
                'service_unavailable': KEYS.HTTP_CODE_SERVICE_UNAVAILABLE
            }
            return code_map.get(code_type, 200)
        # Fallback codes
        code_fallbacks = {
            'ok': 200,
            'service_unavailable': 503
        }
        return code_fallbacks.get(code_type, 200)
    
    def _get_json_key(self, key_type: str) -> str:
        """Get JSON key constant, using CLI constants if available."""
        if CLI_CONSTANTS_AVAILABLE:
            key_map = {
                'ready': KEYS.JSON_KEY_READY,
                'value': KEYS.JSON_KEY_VALUE,
                'uptime_ms': KEYS.JSON_KEY_UPTIME_MS,
                'registered_tools': KEYS.JSON_KEY_REGISTERED_TOOLS,
                'active_invocations': KEYS.JSON_KEY_ACTIVE_INVOCATIONS
            }
            return key_map.get(key_type, key_type)
        return key_type
    
    def _get_message(self, msg_type: str, **kwargs) -> str:
        """Get message from CLI constants if available."""
        if not CLI_CONSTANTS_AVAILABLE:
            return ""
        msg_map = {
            'ok': MSG.PRECHECK_STATUS_MESSAGE_OK,
            'selected': MSG.PRECHECK_STATUS_MESSAGE_SELECTED,
            'no_app': MSG.PRECHECK_STATUS_MESSAGE_NO_APP,
            'reachable': MSG.PRECHECK_STATUS_MESSAGE_REACHABLE,
            'not_ready': MSG.PRECHECK_STATUS_MESSAGE_NOT_READY,
            'http': MSG.PRECHECK_STATUS_MESSAGE_HTTP,
            'conn_fail': MSG.PRECHECK_STATUS_MESSAGE_CONN_FAIL,
            'ready': MSG.PRECHECK_STATUS_MESSAGE_READY,
            'not_ready_unavailable': MSG.PRECHECK_STATUS_MESSAGE_NOT_READY_UNAVAILABLE,
            'health_alive': MSG.PRECHECK_STATUS_MESSAGE_HEALTH_ALIVE,
            'health_fail': MSG.PRECHECK_STATUS_MESSAGE_HEALTH_FAIL,
            'mcp_fail': MSG.PRECHECK_STATUS_MESSAGE_MCP_FAIL,
            'cli_accessible': MSG.PRECHECK_STATUS_MESSAGE_CLI_ACCESSIBLE,
            'cli_not_accessible': MSG.PRECHECK_STATUS_MESSAGE_CLI_NOT_ACCESSIBLE,
            'not_accessible': MSG.PRECHECK_STATUS_MESSAGE_NOT_ACCESSIBLE,
            'api_reachable': MSG.PRECHECK_STATUS_MESSAGE_API_REACHABLE,
            'missing_key': MSG.PRECHECK_STATUS_MESSAGE_MISSING_KEY,
            'not_running_port': MSG.PRECHECK_STATUS_MESSAGE_NOT_RUNNING_PORT
        }
        msg_template = msg_map.get(msg_type, "")
        return msg_template.format(**kwargs) if msg_template else ""
    
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
            if CLI_CONSTANTS_AVAILABLE:
                return self._get_message('not_running_port', port=port)
            else:
                return f"Not running on port {port}"
        else:
            # Fallback to generic message
            if CLI_CONSTANTS_AVAILABLE:
                return self._get_message('not_accessible', url=url)
            else:
                return f"Not accessible at {url}"
    
    def _get_appium_url(self) -> str:
        """Get Appium URL from config."""
        return self.config.get('CONFIG_APPIUM_SERVER_URL') or self.config.get('APPIUM_SERVER_URL', DEFAULT_APPIUM_URL)
    
    def _get_mcp_url(self) -> str:
        """Get MCP URL from config."""
        return self.config.get('CONFIG_MCP_SERVER_URL') or self.config.get('MCP_SERVER_URL', DEFAULT_MCP_URL)
    
    def _get_mobsf_url(self) -> str:
        """Get MobSF URL from config."""
        return self.config.get('CONFIG_MOBSF_API_URL') or self.config.get('MOBSF_API_URL', DEFAULT_MOBSF_URL)
    
    def _get_ollama_url(self) -> str:
        """Get Ollama URL from config."""
        return self.config.get('CONFIG_OLLAMA_BASE_URL') or self.config.get('OLLAMA_BASE_URL', DEFAULT_OLLAMA_URL)

