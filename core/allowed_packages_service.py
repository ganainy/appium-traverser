#!/usr/bin/env python3
"""
Core service for allowed external packages management.

Contains pure business logic for CRUD operations on allowed packages
without any persistence dependencies. This service can be used by both
CLI and GUI interfaces.
"""

import logging
from typing import List, Optional, Dict, Any, Protocol


class PackagesPersistence(Protocol):
    """Protocol for persistence layer implementations."""
    
    def load_packages(self) -> List[str]:
        """Load packages from persistence."""
        ...
    
    def save_packages(self, packages: List[str]) -> bool:
        """Save packages to persistence."""
        ...


class AllowedPackagesService:
    """Core service for managing allowed external packages."""
    
    def __init__(self, persistence: PackagesPersistence, logger: Optional[logging.Logger] = None):
        """
        Initialize the allowed packages service.
        
        Args:
            persistence: Persistence layer implementation
            logger: Optional logger instance
        """
        self.persistence = persistence
        self.logger = logger or logging.getLogger(__name__)
    
    def get_all(self) -> List[str]:
        """
        Get all allowed external packages.
        
        Returns:
            List of package names
        """
        try:
            return self.persistence.load_packages()
        except Exception as e:
            self.logger.error(f"Failed to get allowed packages: {e}")
            return []
    
    def add(self, package_name: str) -> bool:
        """
        Add a package to the allowed list.
        
        Args:
            package_name: Package name (e.g., com.example.app)
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            package_name = package_name.strip()
            if not package_name:
                self.logger.warning("Cannot add empty package name")
                return False
            
            if not self._is_valid_package_name(package_name):
                self.logger.warning(f"Invalid package name format: {package_name}")
                return False
            
            packages = self.get_all()
            if package_name in packages:
                self.logger.info(f"Package {package_name} already in allowed list")
                return True  # Already exists, consider it a success
            
            packages.append(package_name)
            if self.persistence.save_packages(packages):
                self.logger.info(f"Added package: {package_name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to add package {package_name}: {e}")
            return False
    
    def remove(self, package_name: str) -> bool:
        """
        Remove a package from the allowed list.
        
        Args:
            package_name: Package name to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        try:
            package_name = package_name.strip()
            packages = self.get_all()
            
            if package_name not in packages:
                self.logger.warning(f"Package {package_name} not found in allowed list")
                return False
            
            packages.remove(package_name)
            if self.persistence.save_packages(packages):
                self.logger.info(f"Removed package: {package_name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to remove package {package_name}: {e}")
            return False
    
    def update(self, old_package_name: str, new_package_name: str) -> bool:
        """
        Update (rename) a package in the allowed list.
        
        Args:
            old_package_name: Current package name
            new_package_name: New package name
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            old_package_name = old_package_name.strip()
            new_package_name = new_package_name.strip()
            
            if not new_package_name:
                self.logger.warning("Cannot update to empty package name")
                return False
            
            if not self._is_valid_package_name(new_package_name):
                self.logger.warning(f"Invalid package name format: {new_package_name}")
                return False
            
            packages = self.get_all()
            
            if old_package_name not in packages:
                self.logger.warning(f"Package {old_package_name} not found in allowed list")
                return False
            
            if new_package_name in packages:
                self.logger.warning(f"Package {new_package_name} already exists in allowed list")
                return False
            
            idx = packages.index(old_package_name)
            packages[idx] = new_package_name
            if self.persistence.save_packages(packages):
                self.logger.info(f"Updated package: {old_package_name} -> {new_package_name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to update package {old_package_name}: {e}")
            return False
    
    def clear(self) -> bool:
        """
        Clear all allowed external packages.
        
        Returns:
            True if cleared successfully, False otherwise
        """
        try:
            if self.persistence.save_packages([]):
                self.logger.info("Cleared all allowed packages")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to clear allowed packages: {e}")
            return False
    
    def set_all(self, packages: List[str]) -> bool:
        """
        Replace all allowed packages with a new list.
        
        Args:
            packages: List of package names
            
        Returns:
            True if set successfully, False otherwise
        """
        try:
            if not isinstance(packages, list):
                self.logger.error(f"Packages must be a list, got: {type(packages)} = {repr(packages)}")
                return False
            
            # Validate all packages
            validated_packages = []
            for pkg in packages:
                # Debug: log what we're processing
                if not isinstance(pkg, str):
                    self.logger.warning(f"Package item is not a string, got {type(pkg)}: {repr(pkg)}")
                    pkg = str(pkg)  # Convert to string if needed
                
                pkg = pkg.strip()
                if not pkg:
                    continue
                    
                if not self._is_valid_package_name(pkg):
                    self.logger.warning(f"Skipping invalid package name: {pkg}")
                    continue
                if pkg not in validated_packages:  # Avoid duplicates
                    validated_packages.append(pkg)
            
            if self.persistence.save_packages(validated_packages):
                self.logger.info(f"Set allowed packages to {len(validated_packages)} items")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to set allowed packages: {e}")
            return False
    
    def exists(self, package_name: str) -> bool:
        """
        Check if a package is in the allowed list.
        
        Args:
            package_name: Package name to check
            
        Returns:
            True if package exists in allowed list, False otherwise
        """
        return package_name.strip() in self.get_all()
    
    def get_count(self) -> int:
        """
        Get the number of allowed packages.
        
        Returns:
            Number of allowed packages
        """
        return len(self.get_all())
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Get allowed packages as a dictionary representation.
        
        Returns:
            Dictionary with packages info
        """
        packages = self.get_all()
        return {
            'total': len(packages),
            'packages': packages,
        }
    
    @staticmethod
    def _is_valid_package_name(package_name: str) -> bool:
        """
        Validate package name format.
        
        A valid Android package name contains lowercase letters, digits, underscores,
        and dots, with dots separating components. Example: com.example.app
        
        Args:
            package_name: Package name to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not package_name:
            return False
        
        # Package name should not be empty
        if not isinstance(package_name, str):
            return False
        
        # Android package names typically follow this pattern:
        # - Lowercase letters, digits, underscores
        # - Separated by dots
        # - Cannot start or end with dot
        # - Cannot have consecutive dots
        
        import re
        
        # Allow alphanumeric, underscore, and dot
        if not re.match(r'^[a-z0-9._]+$', package_name):
            return False
        
        # Cannot start or end with dot
        if package_name.startswith('.') or package_name.endswith('.'):
            return False
        
        # Cannot have consecutive dots
        if '..' in package_name:
            return False
        
        return True