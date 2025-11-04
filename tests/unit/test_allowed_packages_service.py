#!/usr/bin/env python3
"""
Test suite for the core allowed packages service.

Tests the business logic without any persistence dependencies.
"""

import pytest
from unittest.mock import Mock, MagicMock
import logging

from core.allowed_packages_service import AllowedPackagesService, PackagesPersistence


class MockPersistence(PackagesPersistence):
    """Mock persistence implementation for testing."""
    
    def __init__(self):
        self.packages = []
        self.save_should_fail = False
    
    def load_packages(self):
        return self.packages.copy()
    
    def save_packages(self, packages):
        if self.save_should_fail:
            return False
        self.packages = packages.copy()
        return True


class TestAllowedPackagesService:
    """Test the core allowed packages service."""
    
    @pytest.fixture
    def mock_persistence(self):
        """Create a mock persistence implementation."""
        return MockPersistence()
    
    @pytest.fixture
    def service(self, mock_persistence):
        """Create a service instance with mock persistence."""
        logger = logging.getLogger("test")
        return AllowedPackagesService(mock_persistence, logger)
    
    def test_add_valid_package(self, service, mock_persistence):
        """Test adding a valid package."""
        result = service.add("com.google.android.gms")
        assert result is True
        assert service.exists("com.google.android.gms")
        assert mock_persistence.packages == ["com.google.android.gms"]
    
    def test_add_invalid_package_empty(self, service, mock_persistence):
        """Test adding an empty package name."""
        result = service.add("")
        assert result is False
        assert len(mock_persistence.packages) == 0
    
    def test_add_invalid_package_format(self, service, mock_persistence):
        """Test adding a package with invalid format."""
        result = service.add("invalid-package-name")
        assert result is False
        assert len(mock_persistence.packages) == 0
    
    def test_add_duplicate_package(self, service, mock_persistence):
        """Test adding a duplicate package."""
        service.add("com.example.app")
        result = service.add("com.example.app")  # Should succeed (idempotent)
        assert result is True
        assert service.get_count() == 1
        assert mock_persistence.packages == ["com.example.app"]
    
    def test_remove_package(self, service, mock_persistence):
        """Test removing a package."""
        service.add("com.google.android.gms")
        result = service.remove("com.google.android.gms")
        assert result is True
        assert not service.exists("com.google.android.gms")
        assert len(mock_persistence.packages) == 0
    
    def test_remove_nonexistent_package(self, service, mock_persistence):
        """Test removing a package that doesn't exist."""
        result = service.remove("com.nonexistent.package")
        assert result is False
    
    def test_update_package(self, service, mock_persistence):
        """Test updating (renaming) a package."""
        service.add("com.old.package")
        result = service.update("com.old.package", "com.new.package")
        assert result is True
        assert not service.exists("com.old.package")
        assert service.exists("com.new.package")
        assert mock_persistence.packages == ["com.new.package"]
    
    def test_update_nonexistent_package(self, service, mock_persistence):
        """Test updating a package that doesn't exist."""
        result = service.update("com.nonexistent.package", "com.new.package")
        assert result is False
    
    def test_update_to_existing_package(self, service, mock_persistence):
        """Test updating to a name that already exists."""
        service.add("com.pkg1")
        service.add("com.pkg2")
        result = service.update("com.pkg1", "com.pkg2")
        assert result is False
        assert mock_persistence.packages == ["com.pkg1", "com.pkg2"]
    
    def test_clear_packages(self, service, mock_persistence):
        """Test clearing all packages."""
        service.add("com.pkg1")
        service.add("com.pkg2")
        assert service.get_count() == 2
        result = service.clear()
        assert result is True
        assert service.get_count() == 0
        assert len(mock_persistence.packages) == 0
    
    def test_set_all_packages(self, service, mock_persistence):
        """Test setting all packages at once."""
        packages = ["com.pkg1", "com.pkg2", "com.pkg3"]
        result = service.set_all(packages)
        assert result is True
        assert service.get_count() == 3
        assert service.get_all() == packages
        assert mock_persistence.packages == packages
    
    def test_set_all_with_duplicates(self, service, mock_persistence):
        """Test setting packages with duplicates (should deduplicate)."""
        packages = ["com.pkg1", "com.pkg2", "com.pkg1"]
        result = service.set_all(packages)
        assert result is True
        assert service.get_count() == 2
        assert mock_persistence.packages == ["com.pkg1", "com.pkg2"]
    
    def test_set_all_with_invalid(self, service, mock_persistence):
        """Test setting packages with invalid ones (should skip invalid)."""
        packages = ["com.pkg1", "invalid-name", "com.pkg2"]
        result = service.set_all(packages)
        assert result is True
        assert service.get_count() == 2
        assert "com.pkg1" in service.get_all()
        assert "com.pkg2" in service.get_all()
        assert mock_persistence.packages == ["com.pkg1", "com.pkg2"]
    
    def test_get_count(self, service, mock_persistence):
        """Test getting package count."""
        assert service.get_count() == 0
        service.add("com.pkg1")
        assert service.get_count() == 1
        service.add("com.pkg2")
        assert service.get_count() == 2
    
    def test_exists(self, service, mock_persistence):
        """Test checking if package exists."""
        service.add("com.example.app")
        assert service.exists("com.example.app") is True
        assert service.exists("com.nonexistent.app") is False
    
    def test_to_dict(self, service, mock_persistence):
        """Test converting to dictionary."""
        service.add("com.pkg1")
        service.add("com.pkg2")
        result = service.to_dict()
        assert "total" in result
        assert "packages" in result
        assert result["total"] == 2
        assert len(result["packages"]) == 2
    
    def test_get_all_empty(self, service, mock_persistence):
        """Test getting all packages when list is empty."""
        result = service.get_all()
        assert result == []
    
    def test_whitespace_handling(self, service, mock_persistence):
        """Test that whitespace is properly handled."""
        result = service.add("  com.example.app  ")
        assert result is True
        assert service.exists("com.example.app") is True
        assert mock_persistence.packages == ["com.example.app"]
    
    def test_persistence_failure_on_save(self, service, mock_persistence):
        """Test handling of persistence save failures."""
        mock_persistence.save_should_fail = True
        result = service.add("com.example.app")
        assert result is False
        assert service.get_count() == 0
    
    def test_persistence_failure_on_load(self, service, mock_persistence):
        """Test handling of persistence load failures."""
        # Mock load to raise an exception
        mock_persistence.load_packages = Mock(side_effect=Exception("Load failed"))
        result = service.get_all()
        assert result == []
    
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