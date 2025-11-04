#!/usr/bin/env python3
"""
Adapter for allowed packages persistence using the config system.

This adapter implements the PackagesPersistence protocol and handles
the specifics of loading and saving packages from/to the config,
including data cleanup and format handling.
"""

import logging
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from config.config import Config


class AllowedPackagesAdapter:
    """
    Adapter for persisting allowed packages using the config system.
    
    This adapter handles the specifics of the config persistence layer,
    including data cleanup and format handling.
    """
    
    def __init__(self, config: "Config", logger: Optional[logging.Logger] = None):
        """
        Initialize the adapter with a config instance.
        
        Args:
            config: Configuration object for persistence
            logger: Optional logger instance
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
    
    def load_packages(self) -> List[str]:
        """
        Load packages from the config, handling various data formats and cleanup.
        
        Returns:
            List of package names
        """
        try:
            packages = self.config.get('ALLOWED_EXTERNAL_PACKAGES')
            if packages is None:
                return []
            if isinstance(packages, list):
                # Clean up any corrupted entries (JSON strings in list)
                cleaned = []
                for pkg in packages:
                    if isinstance(pkg, str):
                        # Check if this might be a JSON string (starts with [ or {)
                        pkg_stripped = pkg.strip()
                        if pkg_stripped.startswith('[') or pkg_stripped.startswith('{'):
                            # This looks like corrupted/serialized data, skip it
                            self.logger.warning(f"Detected and skipping corrupted package data: {pkg_stripped[:50]}...")
                            continue
                        cleaned.append(pkg)
                    else:
                        # Non-string item in list, convert to string
                        pkg_str = str(pkg).strip()
                        if pkg_str and not (pkg_str.startswith('[') or pkg_str.startswith('{')):
                            cleaned.append(pkg_str)
                return cleaned
            if isinstance(packages, str):
                # Handle comma or newline separated strings
                return [pkg.strip() for pkg in packages.split('\n') if pkg.strip()]
            return []
        except Exception as e:
            self.logger.error(f"Failed to load packages from config: {e}")
            return []
    
    def save_packages(self, packages: List[str]) -> bool:
        """
        Save packages to the config.
        
        Args:
            packages: List of package names to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            self.config.set('ALLOWED_EXTERNAL_PACKAGES', packages)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save packages to config: {e}")
            return False