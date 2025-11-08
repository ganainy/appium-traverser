"""
Health check service for validating system components and configuration.
"""

import requests
from typing import Any, Dict, List, Tuple

from cli.shared.context import CLIContext
from cli.constants import messages as MSG
from cli.constants import keys as KEYS
from cli.constants import config as CFG
from cli.services.process_utils import run_subprocess


class HealthCheckService:
    """Service for checking the health of various system components."""
    
    def __init__(self, context: CLIContext):
        """Initialize the health check service with context."""
        self.context = context
        self.config = context.config
    
    def check_all_services(self) -> Dict[str, Dict[str, Any]]:
        """Check all services and return status dictionary."""
        services = {}
        
        # Check Appium server
        appium_status = self.check_appium_server()
        services[KEYS.SERVICE_APPIUM] = appium_status
        
        # Check MCP server health
        mcp_status = self.check_mcp_server_health()
        services[KEYS.SERVICE_MCP] = mcp_status
        
        # Check MobSF server
        mobsf_status = self.check_mobsf_server()
        services[KEYS.SERVICE_MOBSF] = mobsf_status
        
        # Check Ollama service if needed
        ai_provider = self.config.get("AI_PROVIDER", KEYS.AI_PROVIDER_GEMINI).lower()
        if ai_provider == KEYS.AI_PROVIDER_OLLAMA:
            ollama_status = self.check_ollama_service()
            services[KEYS.SERVICE_OLLAMA] = ollama_status
        
        # Check PCAPdroid (always show as separate service)
        pcapdroid_status = self.check_pcapdroid()
        services[KEYS.SERVICE_PCAPDROID] = pcapdroid_status
        
        # Check API keys and environment
        api_issues, api_warnings = self.check_api_keys_and_env()
        if api_issues:
            services[KEYS.SERVICE_API_KEYS] = {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR, KEYS.STATUS_KEY_MESSAGE: '; '.join(api_issues)}
        elif api_warnings:
            services[KEYS.SERVICE_API_KEYS] = {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING, KEYS.STATUS_KEY_MESSAGE: '; '.join(api_warnings)}
        else:
            services[KEYS.SERVICE_API_KEYS] = {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_OK}
        
        # Check target app
        app_package = self.config.get("APP_PACKAGE", None)
        if app_package:
            services[KEYS.SERVICE_TARGET_APP] = {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_SELECTED.format(app_package=app_package)}
        else:
            services[KEYS.SERVICE_TARGET_APP] = {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_NO_APP}
        
        return services
    
    def check_appium_server(self) -> Dict[str, str]:
        """Check Appium server status."""
        try:
            appium_url = self.config.CONFIG_APPIUM_SERVER_URL.rstrip('/')
            response = requests.get(f"{appium_url}{KEYS.APPIUM_STATUS_PATH}", timeout=CFG.APPIUM_STATUS_TIMEOUT)
            if response.status_code == KEYS.HTTP_CODE_OK:
                status_data = response.json()
                ready = (
                    status_data.get(KEYS.JSON_KEY_READY, False) or
                    status_data.get(KEYS.JSON_KEY_VALUE, {}).get(KEYS.JSON_KEY_READY, False)
                )
                if ready:
                    return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_REACHABLE.format(url=appium_url)}
                else:
                    return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_NOT_READY.format(url=appium_url)}
            else:
                return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_HTTP.format(code=response.status_code, url=appium_url)}
        except Exception as e:
            return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_CONN_FAIL.format(error=str(e))}
    
    def check_mcp_server_health(self) -> Dict[str, str]:
        """Check MCP server health status using /health and /ready endpoints."""
        try:
            mcp_url = self.config.CONFIG_MCP_SERVER_URL
            base_url = mcp_url.rstrip('/mcp').rstrip('/')
            try:
                response = requests.get(f"{base_url}{KEYS.MCP_READY_PATH}", timeout=CFG.MCP_STATUS_TIMEOUT)
                if response.status_code == KEYS.HTTP_CODE_OK:
                    ready_data = response.json()
                    # The /ready endpoint returns {ready: true, details: {...}}
                    # Extract from details if present, otherwise try top-level
                    if "details" in ready_data:
                        details = ready_data["details"]
                    else:
                        # Fallback to top-level if details key doesn't exist
                        details = ready_data
                    uptime_ms = details.get("uptimeMs", details.get(KEYS.JSON_KEY_UPTIME_MS, 0)) or 0
                    registered_tools = details.get("registeredTools", details.get(KEYS.JSON_KEY_REGISTERED_TOOLS, 0)) or 0
                    active_invocations = details.get("activeInvocations", details.get(KEYS.JSON_KEY_ACTIVE_INVOCATIONS, 0)) or 0
                    return {
                        KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING,
                        KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_READY.format(
                            url=base_url,
                            tools=registered_tools,
                            active=active_invocations,
                            uptime=uptime_ms
                        )
                    }
                elif response.status_code == KEYS.HTTP_CODE_SERVICE_UNAVAILABLE:
                    return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_NOT_READY_UNAVAILABLE.format(url=base_url)}
                else:
                    return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_HTTP.format(code=response.status_code, url=f"{base_url}{KEYS.MCP_READY_PATH}")}
            except requests.exceptions.Timeout:
                try:
                    response = requests.get(f"{base_url}{KEYS.MCP_HEALTH_PATH}", timeout=CFG.MCP_STATUS_TIMEOUT)
                    if response.status_code == KEYS.HTTP_CODE_OK:
                        health_data = response.json()
                        uptime_ms = health_data.get(KEYS.JSON_KEY_UPTIME_MS, 0)
                        return {
                            KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING,
                            KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_HEALTH_ALIVE.format(url=base_url, uptime=uptime_ms)
                        }
                    else:
                        return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_HTTP.format(code=response.status_code, url=f"{base_url}{KEYS.MCP_HEALTH_PATH}")}
                except Exception as health_error:
                    return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_HEALTH_FAIL.format(error=str(health_error))}
        except Exception as e:
            return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_MCP_FAIL.format(error=str(e))}
    
    def check_mobsf_server(self) -> Dict[str, str]:
        """Check MobSF server status."""
        # Only check MobSF if analysis is enabled
        if not self.config.get("ENABLE_MOBSF_ANALYSIS", False):
            return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING, KEYS.STATUS_KEY_MESSAGE: "MobSF analysis is disabled (optional feature)"}
        
        try:
            mobsf_url = self.config.CONFIG_MOBSF_API_URL
            response = requests.get(f"{mobsf_url}{KEYS.MOBSF_STATUS_PATH}", timeout=CFG.MOBSF_STATUS_TIMEOUT)
            if response.status_code == KEYS.HTTP_CODE_OK:
                return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_REACHABLE.format(url=mobsf_url)}
            else:
                return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_HTTP.format(code=response.status_code, url=mobsf_url)}
        except Exception as e:
            return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_CONN_FAIL.format(error=str(e))}
    
    def check_ollama_service(self) -> Dict[str, str]:
        """Check Ollama service status."""
        ollama_url = self.config.CONFIG_OLLAMA_BASE_URL
        try:
            response = requests.get(f"{ollama_url}{KEYS.OLLAMA_TAGS_PATH}", timeout=CFG.OLLAMA_API_TIMEOUT)
            if response.status_code == KEYS.HTTP_CODE_OK:
                return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_API_REACHABLE.format(url=ollama_url)}
        except Exception:
            pass
        try:
            result = run_subprocess(
                ["ollama", "list"],
                timeout=CFG.OLLAMA_CLI_TIMEOUT,
                capture_output=True
            )
            if result.returncode == 0:
                return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_CLI_ACCESSIBLE}
            else:
                return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_CLI_NOT_ACCESSIBLE}
        except Exception:
            return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_ERROR, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_NOT_ACCESSIBLE.format(url=ollama_url)}
    
    def check_pcapdroid(self) -> Dict[str, str]:
        """Check PCAPdroid traffic capture status."""
        if self.config.get("ENABLE_TRAFFIC_CAPTURE", False):
            if not self.config.get("PCAPDROID_API_KEY", None):
                return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING, KEYS.STATUS_KEY_MESSAGE: MSG.PRECHECK_STATUS_MESSAGE_MISSING_KEY.format(key="PCAPDroid API key", env="PCAPDROID_API_KEY")}
            else:
                return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_RUNNING, KEYS.STATUS_KEY_MESSAGE: "PCAPDroid API key is configured (traffic capture enabled)"}
        else:
            return {KEYS.STATUS_KEY_STATUS: KEYS.STATUS_WARNING, KEYS.STATUS_KEY_MESSAGE: "PCAPDroid traffic capture is disabled (optional feature)"}
    
    def check_api_keys_and_env(self) -> Tuple[List[str], List[str]]:
        """Check API keys and environment variables."""
        issues = []
        warnings = []
        
        ai_provider = self.config.get("AI_PROVIDER", KEYS.AI_PROVIDER_GEMINI).lower()
        
        if ai_provider == KEYS.AI_PROVIDER_GEMINI:
            if not self.config.get("GEMINI_API_KEY", None):
                issues.append(MSG.PRECHECK_STATUS_MESSAGE_MISSING_KEY.format(key="Gemini API key", env="GEMINI_API_KEY"))
        elif ai_provider == KEYS.AI_PROVIDER_OPENROUTER:
            if not self.config.get("OPENROUTER_API_KEY", None):
                issues.append(MSG.PRECHECK_STATUS_MESSAGE_MISSING_KEY.format(key="OpenRouter API key", env="OPENROUTER_API_KEY"))
        
        return issues, warnings