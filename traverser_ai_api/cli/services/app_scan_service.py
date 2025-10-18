#!/usr/bin/env python3
"""
App scanning service for discovering and managing installed applications.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..shared.context import CLIContext


class AppScanService:
    """Service for scanning and managing installed applications."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
        self.api_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Path to find_app_info.py script
        self.find_app_info_script_path = os.path.join(
            self.api_dir, "..", "..", "find_app_info.py"
        )
    
    def scan_all_apps(self, force_rescan: bool = False) -> Tuple[bool, Optional[str]]:
        """Scan and cache ALL apps (no AI filtering).
        
        Args:
            force_rescan: Force rescan even if cache exists
            
        Returns:
            Tuple of (success, cache_file_path)
        """
        self.logger.debug("Starting ALL apps scan (no AI filter)...")
        try:
            # Import find_app_info module
            sys.path.insert(0, os.path.dirname(self.find_app_info_script_path))
            import find_app_info as fai
            
            output_path, result_data = fai.generate_app_info_cache(
                perform_ai_filtering_on_this_call=False
            )
            
            if not output_path:
                self.logger.error("All-apps scan did not produce a cache file.")
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
        self.logger.debug("Starting HEALTH apps scan (AI filter)...")
        try:
            # Import find_app_info module
            sys.path.insert(0, os.path.dirname(self.find_app_info_script_path))
            import find_app_info as fai
            
            output_path, result_data = fai.generate_app_info_cache(
                perform_ai_filtering_on_this_call=True
            )
            
            if not output_path:
                self.logger.error("Health-apps scan did not produce a cache file.")
                return False, None
                
            self.logger.info(f"Cache file generated at: {output_path}")
            
            # Update config with health app list file
            config_service = self.context.services.get("config")
            if config_service:
                config_service.set_value("CURRENT_HEALTH_APP_LIST_FILE", output_path)
                config_service.save()
            
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
        self.logger.debug(f"Loading apps from: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Unified schema: require 'health_apps'; accept raw list format if provided
            if isinstance(data, dict):
                if isinstance(data.get("health_apps"), list):
                    apps = data.get("health_apps", [])
                else:
                    apps = []
            elif isinstance(data, list):
                # Raw list format
                apps = data
            else:
                apps = []
                
            self.logger.debug(f"Loaded {len(apps)} apps from {file_path}")
            return True, apps
            
        except Exception as e:
            self.logger.error(f"Error loading apps from {file_path}: {e}", exc_info=True)
            return False, []
    
    def resolve_latest_cache_file(self, suffix: str) -> Optional[str]:
        """Find the most recent device-specific app info cache.
        
        Args:
            suffix: Cache suffix ('all' or 'health_filtered')
            
        Returns:
            Path to latest cache file or None
        """
        try:
            config_service = self.context.services.get("config")
            if not config_service:
                return None
                
            out_dir = config_service.get_value("APP_INFO_OUTPUT_DIR") or os.path.join(
                self.api_dir, "..", "..", "output_data", "app_info"
            )
            
            if suffix == "all":
                pattern = os.path.join(out_dir, "device_*_all_apps.json")
            elif suffix == "health_filtered":
                pattern = os.path.join(out_dir, "device_*_filtered_health_apps.json")
            else:
                self.logger.debug(f"Unsupported suffix '{suffix}' for cache resolution")
                return None
            
            import glob
            candidates = glob.glob(pattern)
            if not candidates:
                self.logger.debug(f"No cache files found for pattern: {pattern}")
                return None
                
            latest = max(candidates, key=lambda p: os.path.getmtime(p))
            self.logger.debug(f"Resolved latest cache file for '{suffix}': {latest}")
            return latest
            
        except Exception as e:
            self.logger.error(f"Failed to resolve latest cache file for '{suffix}': {e}", exc_info=True)
            return None
    
    def get_current_health_apps(self) -> List[Dict]:
        """Get current health apps from cache.
        
        Returns:
            List of health app dictionaries
        """
        config_service = self.context.services.get("config")
        if not config_service:
            return []
            
        # Try configured path first
        cache_path = config_service.get_value("CURRENT_HEALTH_APP_LIST_FILE")
        if cache_path and os.path.exists(cache_path):
            success, apps = self.load_apps_from_file(cache_path)
            if success:
                return apps
        
        # Fallback to latest health_filtered cache
        fallback = self.resolve_latest_cache_file("health_filtered")
        if fallback and os.path.exists(fallback):
            success, apps = self.load_apps_from_file(fallback)
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
            self.logger.error("No health apps loaded. Run scan-health-apps first.")
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
                    app_identifier_lower in app.get("app_name", "").lower()
                    or app_identifier_lower == app.get("package_name", "").lower()
                ):
                    selected_app = app
                    break
        
        if not selected_app:
            self.logger.error(f"App '{app_identifier}' not found.")
            return False, None
        
        # Validate required fields
        pkg = selected_app.get("package_name")
        act = selected_app.get("activity_name")
        name = selected_app.get("app_name", "Unknown")
        
        if not pkg or not act:
            self.logger.error(f"Selected app '{name}' missing package/activity.")
            return False, None
        
        # Save to config
        config_service = self.context.services.get("config")
        if config_service:
            config_service.set_value("APP_PACKAGE", pkg)
            config_service.set_value("APP_ACTIVITY", act)
            config_service.set_value(
                "LAST_SELECTED_APP",
                {"package_name": pkg, "activity_name": act, "app_name": name},
            )
            config_service.save()
        
        return True, selected_app