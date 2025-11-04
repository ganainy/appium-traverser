#!/usr/bin/env python3
"""
Test suite for allowed external packages management system.

This test verifies that the CRUD operations work correctly across both
CLI and programmatic interfaces, with proper validation and persistence.
"""

import pytest
import logging
import tempfile
import os
from typing import List

# Test the new architecture directly
from core.allowed_packages_service import AllowedPackagesService
from infrastructure.allowed_packages_adapter import AllowedPackagesAdapter
from config.config import Config


class TestAllowedPackagesManager:
    """Test the AllowedPackagesManager class."""
    
    @pytest.fixture
    def config(self):
        """Create a test config instance."""
        return Config()
    
    @pytest.fixture
    def manager(self, config):
        """Create a manager instance for testing using the new architecture."""
        import logging
        logger = logging.getLogger("test")
        adapter = AllowedPackagesAdapter(config, logger)
        return AllowedPackagesService(adapter, logger)
    
    def test_add_valid_package(self, manager):
        """Test adding a valid package."""
        manager.clear()
        result = manager.add("com.google.android.gms")
        assert result is True
        assert manager.exists("com.google.android.gms")
    
    def test_add_invalid_package_empty(self, manager):
        """Test adding an empty package name."""
        result = manager.add("")
        assert result is False
    
    def test_add_invalid_package_format(self, manager):
        """Test adding a package with invalid format."""
        result = manager.add("invalid-package-name")
        assert result is False
    
    def test_add_duplicate_package(self, manager):
        """Test adding a duplicate package."""
        manager.clear()
        manager.add("com.example.app")
        result = manager.add("com.example.app")  # Should succeed (idempotent)
        assert result is True
        assert manager.get_count() == 1
    
    def test_remove_package(self, manager):
        """Test removing a package."""
        manager.clear()
        manager.add("com.google.android.gms")
        result = manager.remove("com.google.android.gms")
        assert result is True
        assert not manager.exists("com.google.android.gms")
    
    def test_remove_nonexistent_package(self, manager):
        """Test removing a package that doesn't exist."""
        manager.clear()
        result = manager.remove("com.nonexistent.package")
        assert result is False
    
    def test_update_package(self, manager):
        """Test updating (renaming) a package."""
        manager.clear()
        manager.add("com.old.package")
        result = manager.update("com.old.package", "com.new.package")
        assert result is True
        assert not manager.exists("com.old.package")
        assert manager.exists("com.new.package")
    
    def test_update_nonexistent_package(self, manager):
        """Test updating a package that doesn't exist."""
        manager.clear()
        result = manager.update("com.nonexistent.package", "com.new.package")
        assert result is False
    
    def test_update_to_existing_package(self, manager):
        """Test updating to a name that already exists."""
        manager.clear()
        manager.add("com.pkg1")
        manager.add("com.pkg2")
        result = manager.update("com.pkg1", "com.pkg2")
        assert result is False
    
    def test_clear_packages(self, manager):
        """Test clearing all packages."""
        manager.clear()
        manager.add("com.pkg1")
        manager.add("com.pkg2")
        assert manager.get_count() == 2
        result = manager.clear()
        assert result is True
        assert manager.get_count() == 0
    
    def test_set_all_packages(self, manager):
        """Test setting all packages at once."""
        manager.clear()
        packages = ["com.pkg1", "com.pkg2", "com.pkg3"]
        result = manager.set_all(packages)
        assert result is True
        assert manager.get_count() == 3
        assert manager.get_all() == packages
    
    def test_set_all_with_duplicates(self, manager):
        """Test setting packages with duplicates (should deduplicate)."""
        manager.clear()
        packages = ["com.pkg1", "com.pkg2", "com.pkg1"]
        result = manager.set_all(packages)
        assert result is True
        assert manager.get_count() == 2
    
    def test_set_all_with_invalid(self, manager):
        """Test setting packages with invalid ones (should skip invalid)."""
        manager.clear()
        packages = ["com.pkg1", "invalid-name", "com.pkg2"]
        result = manager.set_all(packages)
        assert result is True
        assert manager.get_count() == 2
        assert "com.pkg1" in manager.get_all()
        assert "com.pkg2" in manager.get_all()
    
    def test_get_count(self, manager):
        """Test getting package count."""
        manager.clear()
        assert manager.get_count() == 0
        manager.add("com.pkg1")
        assert manager.get_count() == 1
        manager.add("com.pkg2")
        assert manager.get_count() == 2
    
    def test_exists(self, manager):
        """Test checking if package exists."""
        manager.clear()
        manager.add("com.example.app")
        assert manager.exists("com.example.app") is True
        assert manager.exists("com.nonexistent.app") is False
    
    def test_to_dict(self, manager):
        """Test converting to dictionary."""
        manager.clear()
        manager.add("com.pkg1")
        manager.add("com.pkg2")
        result = manager.to_dict()
        assert "total" in result
        assert "packages" in result
        assert result["total"] == 2
        assert len(result["packages"]) == 2
    
    def test_get_all_empty(self, manager):
        """Test getting all packages when list is empty."""
        manager.clear()
        result = manager.get_all()
        assert result == []
    
    def test_whitespace_handling(self, manager):
        """Test that whitespace is properly handled."""
        manager.clear()
        result = manager.add("  com.example.app  ")
        assert result is True
        assert manager.exists("com.example.app") is True
    
    def test_package_validation_rules(self):
        """Test all package name validation rules."""
        # Valid names
        valid_names = [
            "com.google.android.gms",
            "com.android.chrome",
            "org.mozilla.firefox",
            "com.microsoft.emmx",
            "com.example.app_name",
            "a.b.c",
            "package123.app456.test789",
        ]
        
        for name in valid_names:
            assert AllowedPackagesService._is_valid_package_name(name) is True, f"{name} should be valid"
        
        # Invalid names
        invalid_names = [
            "",
            ".com.example.app",
            "com.example.app.",
            "com..example.app",
            "com.Example.app",
            "com-example-app",
            "com.example.app-name",
            "com.example.app name",
            "com.example.app@domain",
        ]
        
        for name in invalid_names:
            assert AllowedPackagesService._is_valid_package_name(name) is False, f"{name} should be invalid"


class TestPackagesService:
    """Test the CLI packages service."""
    
    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        from cli.services.packages_service import PackagesService
        from cli.shared.context import CLIContext
        
        context = CLIContext()
        return PackagesService(context)
    
    def test_service_list_packages(self, service):
        """Test listing packages via service."""
        service.manager.clear()
        service.manager.add("com.pkg1")
        service.manager.add("com.pkg2")
        packages = service.list_packages()
        assert len(packages) == 2
    
    def test_service_add_package(self, service):
        """Test adding package via service."""
        service.manager.clear()
        result = service.add_package("com.example.app")
        assert result is True
    
    def test_service_remove_package(self, service):
        """Test removing package via service."""
        service.manager.clear()
        service.manager.add("com.example.app")
        result = service.remove_package("com.example.app")
        assert result is True
    
    def test_service_clear_packages(self, service):
        """Test clearing packages via service."""
        service.manager.clear()
        service.manager.add("com.pkg1")
        result = service.clear_packages()
        assert result is True
        assert service.get_package_count() == 0


def test_integration_persistence():
    """Test that packages persist across manager instances."""
    config = Config()
    import logging
    logger = logging.getLogger("test")
    
    # Create first manager instance
    adapter1 = AllowedPackagesAdapter(config, logger)
    manager1 = AllowedPackagesService(adapter1, logger)
    manager1.clear()
    manager1.add("com.persistent.package")
    
    # Create a new manager with same config
    adapter2 = AllowedPackagesAdapter(config, logger)
    manager2 = AllowedPackagesService(adapter2, logger)
    assert manager2.exists("com.persistent.package") is True


def test_new_architecture_direct_usage():
    """Test that the new architecture works when used directly."""
    from core.allowed_packages_service import AllowedPackagesService
    from infrastructure.allowed_packages_adapter import AllowedPackagesAdapter
    from config.config import Config
    
    config = Config()
    import logging
    logger = logging.getLogger("test")
    adapter = AllowedPackagesAdapter(config, logger)
    manager = AllowedPackagesService(adapter, logger)
    
    # Test that it behaves like the old manager
    assert manager.clear() is True
    assert manager.add("com.test.package") is True
    assert manager.exists("com.test.package") is True
    assert manager.get_count() == 1


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
