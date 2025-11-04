#!/usr/bin/env python3
"""
App scanning service for discovering and managing installed applications.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cli.shared.context import CLIContext
from cli.constants.keys import (
    SERVICE_CONFIG,
    CONFIG_APP_INFO_OUTPUT_DIR,
    CONFIG_CURRENT_HEALTH_APP_LIST_FILE,
    CACHE_KEY_ALL,
    CACHE_KEY_HEALTH,
    CACHE_KEY_HEALTH_FILTERED,
    JSON_KEY_ALL_APPS,
    JSON_KEY_HEALTH_APPS,
    APP_NAME,
    PACKAGE_NAME,
    ACTIVITY_NAME,
    FILE_PATTERN_DEVICE_APP_INFO,
    DEFAULT_UNKNOWN
)
from cli.constants.messages import (
    ERR_ALL_APPS_SCAN_NO_CACHE,
    ERR_HEALTH_APPS_SCAN_NO_CACHE,
    ERR_APP_INFO_OUTPUT_DIR_NOT_CONFIGURED,
    ERR_NO_APP_CACHE_FOUND,
    ERR_FAILED_TO_LOAD_APPS_FROM_CACHE,
    ERR_FAILED_TO_LOAD_APPS_FROM_CACHE_WITH_ERROR,
    ERR_NO_HEALTH_APPS_LOADED,
    ERR_APP_NOT_FOUND,
    ERR_SELECTED_APP_MISSING_PACKAGE_ACTIVITY,
    DEBUG_STARTING_ALL_APPS_SCAN,
    DEBUG_STARTING_HEALTH_APPS_SCAN,
    DEBUG_NO_CACHE_FILES_FOUND,
    DEBUG_RESOLVED_LATEST_CACHE_FILE
)
from utils.app_scanner import generate_app_info_cache


class AppScanService:
    """Service for scanning and managing installed applications."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def scan_all_apps(self, force_rescan: bool = False) -> Tuple[bool, Optional[str]]:
        """Scan and cache ALL apps (no AI filtering).
        
        Args:
            force_rescan: Force rescan even if cache exists
            
        Returns:
            Tuple of (success, cache_file_path)
        """
        self.logger.debug(DEBUG_STARTING_ALL_APPS_SCAN)
        try:
            output_path, result_data = generate_app_info_cache(
                perform_ai_filtering_on_this_call=False
            )
            
            if not output_path:
                self.logger.error(ERR_ALL_APPS_SCAN_NO_CACHE)
                return False, None
                
            self.logger.info(f"Cache file generated at: {output_path}")
            return True, output_path
            
        except Exception as e:
            self.logger.error(f"Error during all-apps scan: {e}", exc_info=True)
            return False, None
    
    def scan_health_apps(self, force_rescan: bool = False) -> Tuple[bool, Optional[str]]:
        """Scan and cache AI-filtered health apps.
        
        Args:
            force_rescan: Force rescan even if cache exists
            
        Returns:
            Tuple of (success, cache_file_path)
        """
        self.logger.debug(DEBUG_STARTING_HEALTH_APPS_SCAN)
        try:
            output_path, result_data = generate_app_info_cache(
                perform_ai_filtering_on_this_call=True
            )
            
            if not output_path:
                self.logger.error(ERR_HEALTH_APPS_SCAN_NO_CACHE)
                return False, None
                
            self.logger.info(f"Cache file generated at: {output_path}")
            
            # Update config with health app list file
            config_service = self.context.services.get(SERVICE_CONFIG)
            if config_service:
                config_service.set(CONFIG_CURRENT_HEALTH_APP_LIST_FILE, output_path)
            
            return True, output_path
            
        except Exception as e:
            self.logger.error(f"Error during health-apps scan: {e}", exc_info=True)
            return False, None
    
    def load_apps_from_file(self, file_path: str) -> Tuple[bool, List[Dict]]:
        """Load apps from a cache file.

        Args:
            file_path: Path to cache file

        Returns:
            Tuple of (success, apps_list)
        """
        # Simplified to use the helper method with health apps as default
        success, apps, _ = self._get_cached_apps_by_key(CACHE_KEY_HEALTH, JSON_KEY_HEALTH_APPS)
        return success, apps
    
    def resolve_latest_cache_file(self, app_type: str) -> Optional[str]:
        """Find the most recent device-specific app info cache.

        Args:
            app_type: App type ('all' or 'health')

        Returns:
            Path to latest cache file or None
        """
        try:
            config_service = self.context.services.get(SERVICE_CONFIG)
            if not config_service:
                return None

            out_dir = config_service.get_config_value(CONFIG_APP_INFO_OUTPUT_DIR)
            if not out_dir:
                self.logger.error(ERR_APP_INFO_OUTPUT_DIR_NOT_CONFIGURED)
                return None

            # Use new merged file pattern
            pattern = os.path.join(out_dir, FILE_PATTERN_DEVICE_APP_INFO)

            import glob
            candidates = glob.glob(pattern)
            if not candidates:
                self.logger.debug(DEBUG_NO_CACHE_FILES_FOUND.format(pattern=pattern))
                return None

            latest = max(candidates, key=lambda p: os.path.getmtime(p))
            self.logger.debug(DEBUG_RESOLVED_LATEST_CACHE_FILE.format(app_type=app_type, latest=latest))
            return latest

        except Exception as e:
            self.logger.error(f"Failed to resolve latest cache file for '{app_type}': {e}", exc_info=True)
            return None
    
    def _get_cached_apps_by_key(self, cache_type: str, json_key: str) -> Tuple[bool, List[Dict], Optional[str]]:
        """Helper method to get cached apps by cache type and JSON key.
        
        Args:
            cache_type: Type of cache ('all' or 'health')
            json_key: JSON key to extract apps from ('all_apps' or 'health_apps')
            
        Returns:
            Tuple of (success, apps_list, error_message)
        """
        cache_path = self.resolve_latest_cache_file(cache_type)
        if not cache_path:
            return False, [], ERR_NO_APP_CACHE_FOUND
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if isinstance(data, dict) and json_key in data and isinstance(data[json_key], list):
                apps = data[json_key]
            else:
                # Fallback to default loading
                success, apps = self.load_apps_from_file(cache_path)
                if not success:
                    return False, [], ERR_FAILED_TO_LOAD_APPS_FROM_CACHE
            
            return True, apps, None
            
        except Exception as e:
            return False, [], ERR_FAILED_TO_LOAD_APPS_FROM_CACHE_WITH_ERROR.format(error=e)
    
    def get_current_health_apps(self) -> List[Dict]:
        """Get current health apps from cache.
        
        Returns:
            List of health app dictionaries
        """
        config_service = self.context.services.get(SERVICE_CONFIG)
        if not config_service:
            return []
            
        # Try configured path first
        cache_path = config_service.get_config_value(CONFIG_CURRENT_HEALTH_APP_LIST_FILE)
        if cache_path and os.path.exists(cache_path):
            success, apps = self.load_apps_from_file(cache_path)
            if success:
                return apps
        
                
        return []
    
    def select_app(self, app_identifier: str) -> Tuple[bool, Optional[Dict]]:
        """Select an app by index or name.
        
        Args:
            app_identifier: App index (1-based) or name/package
            
        Returns:
            Tuple of (success, selected_app_dict)
        """
        apps = self.get_current_health_apps()
        if not apps:
            self.logger.error(ERR_NO_HEALTH_APPS_LOADED)
            return False, None
        
        selected_app = None
        
        # Try to find by index first
        try:
            index = int(app_identifier) - 1
            if 0 <= index < len(apps):
                selected_app = apps[index]
        except ValueError:
            # Not an index, search by name or package
            app_identifier_lower = app_identifier.lower()
            for app in apps:
                if (
                    app_identifier_lower in app.get(APP_NAME, "").lower()
                    or app_identifier_lower == app.get(PACKAGE_NAME, "").lower()
                ):
                    selected_app = app
                    break
        
        if not selected_app:
            self.logger.error(ERR_APP_NOT_FOUND.format(app_identifier=app_identifier))
            return False, None
        
        # Validate required fields
        pkg = selected_app.get(PACKAGE_NAME)
        act = selected_app.get(ACTIVITY_NAME)
        name = selected_app.get(APP_NAME, DEFAULT_UNKNOWN)
        
        if not pkg or not act:
            self.logger.error(ERR_SELECTED_APP_MISSING_PACKAGE_ACTIVITY.format(name=name))
            return False, None
        
        return True, selected_app
    
    def get_all_cached_apps(self) -> Tuple[bool, List[Dict], Optional[str]]:
        """Get all apps from the latest cache file.
        
        Returns:
            Tuple of (success, apps_list, error_message)
        """
        return self._get_cached_apps_by_key(CACHE_KEY_ALL, JSON_KEY_ALL_APPS)
    
    def get_health_cached_apps(self) -> Tuple[bool, List[Dict], Optional[str]]:
        """Get health apps from the latest cache file.
        
        Returns:
            Tuple of (success, apps_list, error_message)
        """
        return self._get_cached_apps_by_key(CACHE_KEY_HEALTH, JSON_KEY_HEALTH_APPS)
