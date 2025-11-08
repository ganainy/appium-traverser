#!/usr/bin/env python3
"""
App scanning service for discovering and managing installed Android applications.

Handles scanning (all apps or AI-filtered health apps), caching, and app selection.
App dictionaries contain: app_name, package_name, activity_name.
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
    JSON_KEY_APPS,
    APP_NAME,
    PACKAGE_NAME,
    ACTIVITY_NAME,
    IS_HEALTH_APP,
    FILE_PATTERN_DEVICE_APP_INFO,
    DEFAULT_UNKNOWN
)
from cli.constants.messages import (
    ERR_ALL_APPS_SCAN_NO_CACHE,
    ERR_HEALTH_APPS_SCAN_NO_CACHE,
    ERR_APP_INFO_OUTPUT_DIR_NOT_CONFIGURED,
    ERR_NO_APP_CACHE_FOUND,
    ERR_FAILED_TO_LOAD_APPS_FROM_CACHE_WITH_ERROR,
    ERR_NO_HEALTH_APPS_LOADED,
    ERR_APP_NOT_FOUND,
    ERR_SELECTED_APP_MISSING_PACKAGE_ACTIVITY,
    DEBUG_STARTING_ALL_APPS_SCAN,
    DEBUG_STARTING_HEALTH_APPS_SCAN,
    DEBUG_NO_CACHE_FILES_FOUND,
    DEBUG_RESOLVED_LATEST_CACHE_FILE
)
from domain.find_app_info import generate_app_info_cache


class AppScanService:
    """Service for scanning and managing installed Android applications."""
    
    def __init__(self, context: CLIContext):
        """Initialize the AppScanService.
        
        Args:
            context: CLI context containing services and configuration
        """
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def scan_apps(self, force_rescan: bool = False) -> Tuple[bool, Optional[str]]:
        """Scan and cache all installed apps with AI health filtering.
        
        Creates a unified cache file with all apps, each marked with is_health_app flag.
        AI filtering is always enabled to identify health-related apps.
        
        Args:
            force_rescan: If True, force a new scan even if cache exists. 
                         If False, return existing cache if available.
            
        Returns:
            Tuple of (success, cache_file_path)
            
        Note:
            Cache file contains unified 'apps' list with is_health_app flags (true/false/null).
            Cache file path is stored in configuration as current health app list.
        """
        # Check for existing cache if not forcing rescan
        if not force_rescan:
            existing_cache = self.resolve_latest_cache_file()
            if existing_cache and os.path.exists(existing_cache):
                # Validate the cache has the unified format
                try:
                    with open(existing_cache, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and JSON_KEY_APPS in data and isinstance(data[JSON_KEY_APPS], list):
                        self.logger.info(f"Using existing cache file: {existing_cache}")
                        # Update config with existing cache file
                        config_service = self.context.services.get(SERVICE_CONFIG)
                        if config_service:
                            config_service.set(CONFIG_CURRENT_HEALTH_APP_LIST_FILE, existing_cache)
                        return True, existing_cache
                except Exception as e:
                    self.logger.warning(f"Existing cache file is invalid, will rescan: {e}")
                    # Fall through to generate new cache
        
        # Perform new scan (either forced or no valid cache found)
        self.logger.debug(DEBUG_STARTING_ALL_APPS_SCAN)
        if force_rescan:
            self.logger.info("Force rescan requested, generating new cache...")
        
        try:
            output_path, result_data = generate_app_info_cache()
            
            if not output_path:
                self.logger.error(ERR_ALL_APPS_SCAN_NO_CACHE)
                return False, None
                
            self.logger.info(f"Cache file generated at: {output_path}")
            
            # Update config with health app list file
            config_service = self.context.services.get(SERVICE_CONFIG)
            if config_service:
                config_service.set(CONFIG_CURRENT_HEALTH_APP_LIST_FILE, output_path)
            
            return True, output_path
            
        except Exception as e:
            self.logger.error(f"Error during app scan: {e}", exc_info=True)
            return False, None
    
    def load_apps_from_file(self, file_path: str) -> Tuple[bool, List[Dict]]:
        """Load apps from cache file.

        Args:
            file_path: Path to cache file

        Returns:
            Tuple of (success, apps_list)
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Require unified list structure
            if not isinstance(data, dict) or JSON_KEY_APPS not in data or not isinstance(data[JSON_KEY_APPS], list):
                self.logger.error(f"Cache file {file_path} does not contain unified 'apps' list. Expected format with 'apps' key containing list of apps with 'is_health_app' flags.")
                return False, []
            
            # Return health apps by default (is_health_app == True)
            unified_apps = data[JSON_KEY_APPS]
            health_apps = [app for app in unified_apps if app.get(IS_HEALTH_APP) is True]
            return True, health_apps
            
        except Exception as e:
            self.logger.error(f"Error loading apps from {file_path}: {e}")
            return False, []
    
    def resolve_latest_cache_file(self) -> Optional[str]:
        """Find the most recent device-specific app info cache file.

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

            # Use unified file pattern
            pattern = os.path.join(out_dir, FILE_PATTERN_DEVICE_APP_INFO)

            import glob
            candidates = glob.glob(pattern)
            if not candidates:
                self.logger.debug(DEBUG_NO_CACHE_FILES_FOUND.format(pattern=pattern))
                return None

            latest = max(candidates, key=lambda p: os.path.getmtime(p))
            self.logger.debug(DEBUG_RESOLVED_LATEST_CACHE_FILE.format(app_type="unified", latest=latest))
            return latest

        except Exception as e:
            self.logger.error(f"Failed to resolve latest cache file: {e}", exc_info=True)
            return None
    
    def _load_unified_apps_from_cache(self) -> Tuple[bool, List[Dict], Optional[str]]:
        """Helper method to load the unified apps list from the latest cache file.
        
        Returns:
            Tuple of (success, unified_apps_list, error_message)
        """
        cache_path = self.resolve_latest_cache_file()
        if not cache_path:
            return False, [], ERR_NO_APP_CACHE_FOUND
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Require unified list structure
            if not isinstance(data, dict) or JSON_KEY_APPS not in data or not isinstance(data[JSON_KEY_APPS], list):
                return False, [], f"Cache file does not contain unified 'apps' list. Expected format with 'apps' key containing list of apps with 'is_health_app' flags."
            
            unified_apps = data[JSON_KEY_APPS]
            return True, unified_apps, None
            
        except Exception as e:
            return False, [], ERR_FAILED_TO_LOAD_APPS_FROM_CACHE_WITH_ERROR.format(error=e)
    
    def get_current_health_apps(self) -> List[Dict]:
        """Get current health apps from cache.
        
        Returns:
            List of health app dictionaries (app_name, package_name, activity_name, is_health_app)
        """
        config_service = self.context.services.get(SERVICE_CONFIG)
        if not config_service:
            return []
            
        # Try configured path first
        cache_path = config_service.get_config_value(CONFIG_CURRENT_HEALTH_APP_LIST_FILE)
        if cache_path and os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Require unified list structure
                if not isinstance(data, dict) or JSON_KEY_APPS not in data or not isinstance(data[JSON_KEY_APPS], list):
                    self.logger.error(f"Cache file {cache_path} does not contain unified 'apps' list. Expected format with 'apps' key containing list of apps with 'is_health_app' flags.")
                    return []
                
                unified_apps = data[JSON_KEY_APPS]
                # Filter to only health apps (is_health_app == True)
                health_apps = [app for app in unified_apps if app.get(IS_HEALTH_APP) is True]
                return health_apps
            except Exception as e:
                self.logger.error(f"Error loading health apps from {cache_path}: {e}")
        
        return []
    
    def select_app(self, app_identifier: str) -> Tuple[bool, Optional[Dict]]:
        """Select an app by index (1-based), name, or package identifier.
        
        Args:
            app_identifier: App index, name (partial match), or package (exact match)
            
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
            Apps list includes all apps with is_health_app flags (true, false, or null)
        """
        success, unified_apps, error = self._load_unified_apps_from_cache()
        if not success:
            return False, [], error
        return True, unified_apps, None
    
    def get_health_cached_apps(self) -> Tuple[bool, List[Dict], Optional[str]]:
        """Get health apps from the latest cache file.
        
        Returns:
            Tuple of (success, apps_list, error_message)
            Apps list includes only apps where is_health_app == True
        """
        success, unified_apps, error = self._load_unified_apps_from_cache()
        if not success:
            return False, [], error
        
        # Filter to only health apps
        health_apps = [app for app in unified_apps if app.get(IS_HEALTH_APP) is True]
        return True, health_apps, None
