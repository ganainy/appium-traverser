"""
Service check commands for CLI operations.
"""

import argparse
from typing import Any, Dict, List, Tuple

import requests

from traverser_ai_api.cli.commands.base import CommandHandler, CommandResult
from traverser_ai_api.cli.shared.context import CLIContext


class PrecheckCommand(CommandHandler):
    """Command to run pre-crawl service checks."""
    
    @property
    def name(self) -> str:
        return "precheck-services"
    
    @property
    def description(self) -> str:
        return "Run pre-crawl validation checks for services and configuration"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        telemetry = context.services.get("telemetry")
        
        services_status = self._check_all_services(context)
        telemetry.print_status_table(services_status)
        
        # Determine overall status
        issues = [s for s in services_status.values() if s.get('status') == 'error']
        warnings = [s for s in services_status.values() if s.get('status') == 'warning']
        
        if not issues and not warnings:
            telemetry.print_success("All pre-crawl checks passed!")
            return CommandResult(success=True, message="All checks passed")
        elif not issues:
            telemetry.print_warning("Pre-crawl validation completed with warnings")
            return CommandResult(success=True, message="Checks passed with warnings")
        else:
            telemetry.print_error("Pre-crawl validation failed")
            return CommandResult(success=False, message="Some checks failed", exit_code=1)
    
    def _check_all_services(self, context: CLIContext) -> Dict[str, Dict[str, Any]]:
        """Check all services and return status dictionary."""
        services = {}
        config = context.config
        
        # Check Appium server
        appium_status = self._check_appium_server(config)
        services['Appium Server'] = appium_status
        
        # Check MobSF server
        mobsf_status = self._check_mobsf_server(config)
        services['MobSF Server'] = mobsf_status
        
        # Check Ollama service if needed
        ai_provider = getattr(config, "AI_PROVIDER", "gemini").lower()
        if ai_provider == "ollama":
            ollama_status = self._check_ollama_service(config)
            services['Ollama Service'] = ollama_status
        
        # Check API keys and environment
        api_issues, api_warnings = self._check_api_keys_and_env(config)
        if api_issues:
            services['API Keys'] = {'status': 'error', 'message': '; '.join(api_issues)}
        elif api_warnings:
            services['API Keys'] = {'status': 'warning', 'message': '; '.join(api_warnings)}
        else:
            services['API Keys'] = {'status': 'running', 'message': 'All required API keys configured'}
        
        # Check target app
        app_package = getattr(config, "APP_PACKAGE", None)
        if app_package:
            services['Target App'] = {'status': 'running', 'message': f'Selected: {app_package}'}
        else:
            services['Target App'] = {'status': 'error', 'message': 'No app selected'}
        
        return services
    
    def _check_appium_server(self, config) -> Dict[str, str]:
        """Check Appium server status."""
        try:
            appium_url = getattr(config, "MCP_SERVER_URL", "http://127.0.0.1:4723")
            response = requests.get(f"{appium_url}/status", timeout=3)
            if response.status_code == 200:
                status_data = response.json()
                ready = (
                    status_data.get("ready", False) or 
                    status_data.get("value", {}).get("ready", False)
                )
                if ready:
                    return {'status': 'running', 'message': f'Reachable at {appium_url}'}
                else:
                    return {'status': 'warning', 'message': f'Not ready at {appium_url}'}
            else:
                return {'status': 'error', 'message': f'HTTP {response.status_code} at {appium_url}'}
        except Exception as e:
            return {'status': 'error', 'message': f'Connection failed: {str(e)}'}
    
    def _check_mobsf_server(self, config) -> Dict[str, str]:
        """Check MobSF server status."""
        try:
            mobsf_url = getattr(config, "MOBSF_API_URL", "http://localhost:8000/api/v1")
            response = requests.get(f"{mobsf_url}/server_status", timeout=3)
            if response.status_code == 200:
                return {'status': 'running', 'message': f'Reachable at {mobsf_url}'}
            else:
                return {'status': 'warning', 'message': f'HTTP {response.status_code} at {mobsf_url}'}
        except Exception as e:
            return {'status': 'warning', 'message': f'Connection failed: {str(e)}'}
    
    def _check_ollama_service(self, config) -> Dict[str, str]:
        """Check Ollama service status."""
        ollama_url = getattr(config, "OLLAMA_BASE_URL", "http://localhost:11434")
        
        # Try HTTP API first
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=1.5)
            if response.status_code == 200:
                return {'status': 'running', 'message': f'API reachable at {ollama_url}'}
        except Exception:
            pass
        
        # Try CLI command
        try:
            from traverser_ai_api.cli.services.process_utils import ProcessUtils
            result = ProcessUtils.run_subprocess(
                ["ollama", "list"],
                timeout=2,
                capture_output=True
            )
            if result.returncode == 0:
                return {'status': 'running', 'message': 'CLI accessible'}
            else:
                return {'status': 'error', 'message': 'CLI not accessible'}
        except Exception:
            return {'status': 'error', 'message': f'Not accessible at {ollama_url}'}
    
    def _check_api_keys_and_env(self, config) -> Tuple[List[str], List[str]]:
        """Check API keys and environment variables."""
        issues = []
        warnings = []
        
        ai_provider = getattr(config, "AI_PROVIDER", "gemini").lower()
        
        if ai_provider == "gemini":
            if not getattr(config, "GEMINI_API_KEY", None):
                issues.append("Gemini API key not set (check GEMINI_API_KEY in .env)")
        elif ai_provider == "openrouter":
            if not getattr(config, "OPENROUTER_API_KEY", None):
                issues.append("OpenRouter API key not set (check OPENROUTER_API_KEY in .env)")
        elif ai_provider == "ollama":
            if not getattr(config, "OLLAMA_BASE_URL", None):
                warnings.append("Ollama base URL not set (using default localhost:11434)")
        
        # Check traffic capture API key
        if getattr(config, "ENABLE_TRAFFIC_CAPTURE", False):
            if not getattr(config, "PCAPDROID_API_KEY", None):
                issues.append("PCAPDroid API key not set (check PCAPDROID_API_KEY in .env)")
        
        # Check MobSF API key
        if getattr(config, "ENABLE_MOBSF_ANALYSIS", False):
            if not getattr(config, "MOBSF_API_KEY", None):
                issues.append("MobSF API key not set (check MOBSF_API_KEY in .env)")
        
        return issues, warnings
