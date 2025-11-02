"""
Package management service for CLI operations.
"""

import logging
from typing import List

from cli.shared.context import CLIContext


class PackagesService:
    """Service for managing allowed external packages operations."""
    
    def __init__(self, context: CLIContext):
        """
        Initialize packages service.
        
        Args:
            context: CLI context
        """
        self.context = context
        self.config = context.config
        # Import here to avoid circular imports
        from infrastructure.allowed_packages_manager import AllowedPackagesManager
        self.manager = AllowedPackagesManager(self.config)
        self.logger = logging.getLogger(__name__)
    
    def list_packages(self) -> List[str]:
        """
        List all allowed external packages.
        
        Returns:
            List of package names
        """
        return self.manager.get_all()
    
    def add_package(self, package_name: str) -> bool:
        """
        Add a package to allowed external packages.
        
        Args:
            package_name: Package name to add
            
        Returns:
            True if successful, False otherwise
        """
        return self.manager.add(package_name)
    
    def remove_package(self, package_name: str) -> bool:
        """
        Remove a package from allowed external packages.
        
        Args:
            package_name: Package name to remove
            
        Returns:
            True if successful, False otherwise
        """
        return self.manager.remove(package_name)
    
    def update_package(self, old_name: str, new_name: str) -> bool:
        """
        Update (rename) an allowed external package.
        
        Args:
            old_name: Current package name
            new_name: New package name
            
        Returns:
            True if successful, False otherwise
        """
        return self.manager.update(old_name, new_name)
    
    def clear_packages(self) -> bool:
        """
        Clear all allowed external packages.
        
        Returns:
            True if successful, False otherwise
        """
        return self.manager.clear()
    
    def get_package_count(self) -> int:
        """
        Get the number of allowed packages.
        
        Returns:
            Number of packages
        """
        return self.manager.get_count()
