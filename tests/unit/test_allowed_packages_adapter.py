#!/usr/bin/env python3
"""
Test suite for the allowed packages adapter.

Tests the persistence layer implementation with the config system.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import logging

from infrastructure.allowed_packages_adapter import AllowedPackagesAdapter


class TestAllowedPackagesAdapter:
    """Test the allowed packages adapter."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config instance."""
        config = Mock()
        config.get = Mock()
        config.set = Mock()
        return config
    
    @pytest.fixture
    def adapter(self, mock_config):
        """Create an adapter instance with mock config."""
        logger = logging.getLogger("test")
        return AllowedPackagesAdapter(mock_config, logger)
    
    def test_load_packages_none(self, adapter, mock_config):
        """Test loading packages when config returns None."""
        mock_config.get.return_value = None
        result = adapter.load_packages()
        assert result == []
        mock_config.get.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES')
    
    def test_load_packages_empty_list(self, adapter, mock_config):
        """Test loading packages when config returns empty list."""
        mock_config.get.return_value = []
        result = adapter.load_packages()
        assert result == []
        mock_config.get.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES')
    
    def test_load_packages_valid_list(self, adapter, mock_config):
        """Test loading packages when config returns valid list."""
        packages = ["com.pkg1", "com.pkg2", "com.pkg3"]
        mock_config.get.return_value = packages
        result = adapter.load_packages()
        assert result == packages
        mock_config.get.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES')
    
    def test_load_packages_with_corrupted_data(self, adapter, mock_config):
        """Test loading packages with corrupted data in list."""
        packages = ["com.pkg1", '["corrupted"]', "com.pkg2", '{"also": "corrupted"}', 123]
        mock_config.get.return_value = packages
        result = adapter.load_packages()
        assert result == ["com.pkg1", "com.pkg2", "123"]
        mock_config.get.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES')
    
    def test_load_packages_string_newline_separated(self, adapter, mock_config):
        """Test loading packages when config returns newline-separated string."""
        packages_str = "com.pkg1\ncom.pkg2\ncom.pkg3"
        mock_config.get.return_value = packages_str
        result = adapter.load_packages()
        assert result == ["com.pkg1", "com.pkg2", "com.pkg3"]
        mock_config.get.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES')
    
    def test_load_packages_string_with_empty_lines(self, adapter, mock_config):
        """Test loading packages when config returns string with empty lines."""
        packages_str = "com.pkg1\n\ncom.pkg2\n  \ncom.pkg3\n"
        mock_config.get.return_value = packages_str
        result = adapter.load_packages()
        assert result == ["com.pkg1", "com.pkg2", "com.pkg3"]
        mock_config.get.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES')
    
    def test_load_packages_unexpected_type(self, adapter, mock_config):
        """Test loading packages when config returns unexpected type."""
        mock_config.get.return_value = 12345
        result = adapter.load_packages()
        assert result == []
        mock_config.get.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES')
    
    def test_load_packages_exception(self, adapter, mock_config):
        """Test loading packages when config raises exception."""
        mock_config.get.side_effect = Exception("Config error")
        result = adapter.load_packages()
        assert result == []
        mock_config.get.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES')
    
    def test_save_packages_success(self, adapter, mock_config):
        """Test saving packages successfully."""
        packages = ["com.pkg1", "com.pkg2", "com.pkg3"]
        mock_config.set.return_value = None
        result = adapter.save_packages(packages)
        assert result is True
        mock_config.set.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES', packages)
    
    def test_save_packages_exception(self, adapter, mock_config):
        """Test saving packages when config raises exception."""
        packages = ["com.pkg1", "com.pkg2", "com.pkg3"]
        mock_config.set.side_effect = Exception("Config error")
        result = adapter.save_packages(packages)
        assert result is False
        mock_config.set.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES', packages)
    
    def test_save_packages_empty_list(self, adapter, mock_config):
        """Test saving empty packages list."""
        packages = []
        mock_config.set.return_value = None
        result = adapter.save_packages(packages)
        assert result is True
        mock_config.set.assert_called_once_with('ALLOWED_EXTERNAL_PACKAGES', packages)
    
    @patch('infrastructure.allowed_packages_adapter.logging.getLogger')
    def test_logger_initialization(self, mock_get_logger, mock_config):
        """Test that logger is properly initialized."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        adapter = AllowedPackagesAdapter(mock_config)
        
        mock_get_logger.assert_called_once_with('infrastructure.allowed_packages_adapter')
        assert adapter.logger == mock_logger
    
    def test_custom_logger(self, mock_config):
        """Test that custom logger is used when provided."""
        custom_logger = Mock()
        adapter = AllowedPackagesAdapter(mock_config, custom_logger)
        assert adapter.logger == custom_logger