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

try:
    from traverser_ai_api.config import Config
except ImportError:
    # Handle direct execution for testing
    from config import Config


class ValidationService:
    """Service for validating crawler dependencies and configuration."""
    
    def __init__(self, config: Config):
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
            all_issues.append("❌ Appium server is not running or not accessible")
        
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
            all_issues.append("❌ No target app selected")
        
        # Check optional MobSF server
        mobsf_running = self._check_mobsf_server()
        if not mobsf_running:
            all_warnings.append("⚠️ MobSF server is not running (optional)")
        
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
        appium_url = getattr(self.config, 'APPIUM_SERVER_URL', 'http://127.0.0.1:4723')
        details['appium'] = {
            'running': appium_running,
            'url': appium_url,
            'required': True,
            'message': f"Appium server at {appium_url}" + (" is running ✅" if appium_running else " is not accessible ❌")
        }
        
        # MobSF status (optional)
        mobsf_running = self._check_mobsf_server()
        mobsf_url = getattr(self.config, 'MOBSF_API_URL', 'http://localhost:8000/api/v1')
        mobsf_enabled = getattr(self.config, 'ENABLE_MOBSF_ANALYSIS', False)
        details['mobsf'] = {
            'running': mobsf_running,
            'url': mobsf_url,
            'required': False,
            'enabled': mobsf_enabled,
            'message': f"MobSF server at {mobsf_url}" + (" is running ✅" if mobsf_running else " is not accessible ⚠️")
        }
        
        # AI Provider status
        ai_provider = getattr(self.config, 'AI_PROVIDER', 'gemini').lower()
        if ai_provider == 'ollama':
            ollama_running = self._check_ollama_service()
            details['ollama'] = {
                'running': ollama_running,
                'required': True,
                'message': "Ollama service" + (" is running ✅" if ollama_running else " is not running ❌")
            }
        
        # API Keys status
        api_issues, api_warnings = self._check_api_keys_and_env()
        all_api_messages = api_issues + api_warnings
        details['api_keys'] = {
            'valid': len(api_issues) == 0,
            'issues': all_api_messages,
            'required': True,
            'message': f"API keys: {len(api_issues)} issue(s), {len(api_warnings)} warning(s)" if all_api_messages else "API keys: All required keys present ✅"
        }
        
        # Target app
        app_package = getattr(self.config, 'APP_PACKAGE', None)
        details['target_app'] = {
            'selected': app_package is not None,
            'package': app_package,
            'required': True,
            'message': f"Target app: {app_package}" if app_package else "Target app: Not selected ❌"
        }
        
        return details
    
    def _check_appium_server(self) -> bool:
        """Check if Appium server is running and accessible."""
        try:
            appium_url = getattr(self.config, 'APPIUM_SERVER_URL', 'http://127.0.0.1:4723')
            # Try to connect to Appium status endpoint with shorter timeout
            response = requests.get(f"{appium_url}/status", timeout=3)
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
            mobsf_url = getattr(self.config, 'MOBSF_API_URL', 'http://localhost:8000/api/v1')
            # Try to connect to MobSF API with shorter timeout
            response = requests.get(f"{mobsf_url}/server_status", timeout=3)
            if response.status_code == 200:
                return True
        except Exception as e:
            self.logger.debug(f"MobSF server check failed: {e}")
        
        return False
    
    def _check_ollama_service(self) -> bool:
        """Check if Ollama service is running using HTTP API first, then subprocess fallback."""
        # First try HTTP API check (fast and non-blocking)
        ollama_url = getattr(self.config, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        
        try:
            # Try to connect to Ollama API endpoint with shorter timeout
            response = requests.get(f"{ollama_url}/api/tags", timeout=1.5)
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
                                timeout=2,
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
        ai_provider = getattr(self.config, 'AI_PROVIDER', 'gemini').lower()
        
        if ai_provider == 'ollama':
            if not self._check_ollama_service():
                issues.append("❌ Ollama service is not running")
            if not getattr(self.config, 'OLLAMA_BASE_URL', None):
                warnings.append("⚠️ Ollama base URL not set (using default localhost:11434)")
        
        return issues, warnings
    
    def _check_api_keys_and_env(self) -> Tuple[List[str], List[str]]:
        """Check if required API keys and environment variables are provided.
        
        Returns:
            Tuple of (blocking_issues, warnings)
        """
        issues = []
        warnings = []
        ai_provider = getattr(self.config, 'AI_PROVIDER', 'gemini').lower()
        
        if ai_provider == 'gemini':
            if not getattr(self.config, 'GEMINI_API_KEY', None):
                issues.append("❌ Gemini API key is not set (check GEMINI_API_KEY in .env file)")
        
        elif ai_provider == 'openrouter':
            if not getattr(self.config, 'OPENROUTER_API_KEY', None):
                issues.append("❌ OpenRouter API key is not set (check OPENROUTER_API_KEY in .env file)")
        
        elif ai_provider == 'ollama':
            if not getattr(self.config, 'OLLAMA_BASE_URL', None):
                warnings.append("⚠️ Ollama base URL not set (using default localhost:11434)")
        
        # Check PCAPdroid API key if traffic capture is enabled
        if getattr(self.config, 'ENABLE_TRAFFIC_CAPTURE', False):
            if not getattr(self.config, 'PCAPDROID_API_KEY', None):
                issues.append("❌ PCAPdroid API key is not set (check PCAPDROID_API_KEY in .env file)")
        
        # Check MobSF API key if MobSF analysis is enabled
        if getattr(self.config, 'ENABLE_MOBSF_ANALYSIS', False):
            if not getattr(self.config, 'MOBSF_API_KEY', None):
                issues.append("❌ MobSF API key is not set (check MOBSF_API_KEY in .env file)")
        
        return issues, warnings
    
    def check_dependencies(self, ai_provider: str) -> Tuple[bool, str]:
        """
        Check if dependencies are installed for the specified AI provider.
        
        Args:
            ai_provider: The AI provider to check dependencies for
            
        Returns:
            Tuple of (dependencies_installed, error_message)
        """
        try:
            from traverser_ai_api.model_adapters import check_dependencies
        except ImportError:
            try:
                from model_adapters import check_dependencies
            except ImportError:
                return False, "Could not import model_adapters module"
        
        return check_dependencies(ai_provider)