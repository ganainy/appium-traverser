#!/usr/bin/env python3
"""
MobSF service for managing MobSF security analysis operations.
"""

import logging
from typing import Dict, Any, Optional, Tuple

from cli.shared.context import CLIContext
from cli.constants import keys as KEYS


class MobSFService:
    """Service for managing MobSF security analysis operations."""
    
    def __init__(self, context: CLIContext):
        """Initialize the MobSF service."""
        self.context = context
        self.config = context.config
        self.logger = logging.getLogger(__name__)
        self._mobsf_manager = None
    
    def _get_mobsf_manager(self):
        """Get or create MobSFManager instance."""
        if self._mobsf_manager is None:
            try:
                from infrastructure.mobsf_manager import MobSFManager
                self._mobsf_manager = MobSFManager(self.config)
            except ImportError as e:
                self.logger.error(f"Failed to import MobSFManager: {e}")
                raise
        return self._mobsf_manager
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to MobSF server.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            import requests
            
            # Check if MobSF is enabled
            if not self.config.get(KEYS.CONFIG_ENABLE_MOBSF_ANALYSIS, False):
                return False, "MobSF analysis is not enabled. Enable it in config first."
            
            # Get API URL and key
            api_url = self.config.get(KEYS.CONFIG_MOBSF_API_URL)
            api_key = self.config.get(KEYS.CONFIG_MOBSF_API_KEY)
            
            if not api_url:
                return False, "MobSF API URL is not configured"
            if not api_key:
                return False, "MobSF API Key is not configured"
            
            # Test connection using /scans endpoint
            headers = {'Authorization': api_key}
            test_url = f"{api_url.rstrip('/')}/scans"
            
            try:
                response = requests.get(test_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    return True, f"MobSF connection successful! Server reachable at {api_url}"
                else:
                    return False, f"MobSF connection failed with status code: {response.status_code}"
            except requests.RequestException as e:
                return False, f"MobSF connection error: {e}"
                
        except Exception as e:
            self.logger.error(f"Error testing MobSF connection: {e}", exc_info=True)
            return False, f"Error testing MobSF connection: {str(e)}"
    
    def run_analysis(self, package_name: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Run MobSF security analysis for an app.
        
        Args:
            package_name: Package name to analyze. If None, uses configured APP_PACKAGE.
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Check if MobSF is enabled
            if not self.config.get(KEYS.CONFIG_ENABLE_MOBSF_ANALYSIS, False):
                return False, {"error": "MobSF analysis is not enabled. Enable it in config first."}
            
            # Get package name
            if not package_name:
                package_name = self.config.get(KEYS.CONFIG_APP_PACKAGE)
            
            if not package_name:
                return False, {"error": "No package name provided and APP_PACKAGE not configured"}
            
            # Get MobSF manager
            mobsf_manager = self._get_mobsf_manager()
            
            # Run complete scan
            self.logger.info(f"Starting MobSF analysis for package: {package_name}")
            success, result = mobsf_manager.perform_complete_scan(package_name)
            
            if success:
                self.logger.info("MobSF analysis completed successfully")
            else:
                self.logger.error(f"MobSF analysis failed: {result.get('error', 'Unknown error')}")
            
            return success, result
            
        except Exception as e:
            self.logger.error(f"Error running MobSF analysis: {e}", exc_info=True)
            return False, {"error": str(e)}

