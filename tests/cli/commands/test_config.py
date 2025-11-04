"""
Tests for CLI configuration commands.
"""

import pytest
from unittest.mock import Mock, patch
from argparse import Namespace

from cli.commands.config import SetConfigCommand, ResetConfigCommand
from cli.shared.context import CLIContext


class TestSetConfigCommand:
    """Test cases for SetConfigCommand."""

    def test_run_with_valid_pairs(self):
        """Test SetConfigCommand.run with valid key=value pairs."""
        # Setup
        command = SetConfigCommand()
        args = Namespace(key_value_pairs=["KEY1=value1", "KEY2=value2"])
        
        mock_context = Mock(spec=CLIContext)
        mock_telemetry = Mock()
        mock_context.services.get.return_value = mock_telemetry
        
        # Mock ConfigService
        with patch('cli.services.config_service.ConfigService') as mock_config_service_class:
            mock_config_service = Mock()
            mock_config_service.set_and_save_from_pairs.return_value = True
            mock_config_service_class.return_value = mock_config_service
            
            # Execute
            result = command.run(args, mock_context)
            
            # Verify
            mock_config_service.set_and_save_from_pairs.assert_called_once_with(["KEY1=value1", "KEY2=value2"])
            assert result.success is True
            assert "Set 2/2 configuration values" in result.message
            assert result.exit_code == 0

    def test_run_with_invalid_pairs(self):
        """Test SetConfigCommand.run with invalid key=value pairs."""
        # Setup
        command = SetConfigCommand()
        args = Namespace(key_value_pairs=["KEY1=value1", "INVALID_FORMAT"])
        
        mock_context = Mock(spec=CLIContext)
        mock_telemetry = Mock()
        mock_context.services.get.return_value = mock_telemetry
        
        # Mock ConfigService
        with patch('cli.services.config_service.ConfigService') as mock_config_service_class:
            mock_config_service = Mock()
            mock_config_service.set_and_save_from_pairs.return_value = False
            mock_config_service_class.return_value = mock_config_service
            
            # Execute
            result = command.run(args, mock_context)
            
            # Verify
            mock_config_service.set_and_save_from_pairs.assert_called_once_with(["KEY1=value1", "INVALID_FORMAT"])
            assert result.success is False
            assert "Set 0/2 configuration values" in result.message
            assert result.exit_code == 1


class TestResetConfigCommand:
    """Test cases for ResetConfigCommand."""

    def test_run_success(self):
        command = ResetConfigCommand()
        args = Namespace()

        mock_context = Mock(spec=CLIContext)

        with patch('cli.services.config_service.ConfigService') as mock_config_service_class:
            mock_config_service = Mock()
            mock_config_service.reset_to_defaults.return_value = True
            mock_config_service_class.return_value = mock_config_service

            result = command.run(args, mock_context)

            mock_config_service.reset_to_defaults.assert_called_once_with()
            assert result.success is True
            assert result.message == "Configuration reset to defaults"
            assert result.exit_code == 0

    def test_run_failure(self):
        command = ResetConfigCommand()
        args = Namespace()

        mock_context = Mock(spec=CLIContext)

        with patch('cli.services.config_service.ConfigService') as mock_config_service_class:
            mock_config_service = Mock()
            mock_config_service.reset_to_defaults.return_value = False
            mock_config_service_class.return_value = mock_config_service

            result = command.run(args, mock_context)

            mock_config_service.reset_to_defaults.assert_called_once_with()
            assert result.success is False
            assert result.message == "Failed to reset configuration"
            assert result.exit_code == 1