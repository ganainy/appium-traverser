"""
Tests for CLI entry point functionality.
"""

import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pytest
from unittest.mock import ANY

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from traverser_ai_api.cli.main import run, _register_commands
    from traverser_ai_api.cli.commands.base import CommandRegistry
    from traverser_ai_api.cli.shared.context import CLIContext
except ImportError as e:
    pytest.skip(f"CLI modules not available: {e}", allow_module_level=True)


@pytest.mark.cli
def test_run_with_help_argument():
    """Test CLI run with --help argument."""
    with pytest.raises(SystemExit) as excinfo:
        run(['--help'])
    assert excinfo.value.code == 0


@pytest.mark.cli
def test_run_with_invalid_command():
    """Test CLI run with invalid command."""
    with pytest.raises(SystemExit) as excinfo:
        run(['invalid-command'])
    assert excinfo.value.code == 2


@pytest.mark.cli
def test_run_keyboard_interrupt():
    """Test CLI run with keyboard interrupt."""
    with patch('traverser_ai_api.cli.main.build_parser') as mock_build_parser:
        mock_parser = Mock()
        mock_build_parser.return_value = mock_parser
        
        # Mock parser to raise KeyboardInterrupt
        mock_parser.parse_args.side_effect = KeyboardInterrupt()
        
        result = run()
        assert result == 130


@pytest.mark.cli
def test_run_unexpected_exception():
    """Test CLI run with unexpected exception."""
    with patch('traverser_ai_api.cli.main.build_parser') as mock_build_parser:
        mock_parser = Mock()
        mock_build_parser.return_value = mock_parser
        
        # Mock parser to raise unexpected exception
        mock_parser.parse_args.side_effect = Exception("Unexpected error")
        
        result = run()
        assert result == 1


@pytest.mark.cli
def test_register_commands():
    """Test command registration."""
    registry = CommandRegistry()
    
    # Should register commands without errors
    _register_commands(registry)
    
    # Check that groups were registered
    assert len(registry.groups) > 0
    
    # Check that standalone commands were registered
    assert len(registry.standalone_commands) > 0
    
    # Verify expected groups exist
    group_names = list(registry.groups.keys())
    expected_groups = ['device', 'apps', 'crawler', 'focus']
    for group in expected_groups:
        assert group in group_names


@pytest.mark.cli
def test_register_commands_import_error():
    """Test command registration with import error."""
    with patch('traverser_ai_api.cli.main.logging') as mock_logging:
        with patch('sys.exit') as mock_exit:
            # Mock import to raise ImportError
            with patch('builtins.__import__', side_effect=ImportError("Test error")):
                try:
                    registry = CommandRegistry()
                    _register_commands(registry)
                except SystemExit:
                    pass  # Expected
                
                # Should log error and exit
                mock_logging.error.assert_called()
                mock_exit.assert_called_with(1)


@pytest.mark.cli
def test_run_successful_command_execution():
    """Test successful command execution."""
    with patch('traverser_ai_api.cli.main.build_parser') as mock_build_parser:
        with patch('traverser_ai_api.cli.main.CLIContext') as mock_context_class:
            # Setup mocks
            mock_parser = Mock()
            mock_args = Mock()
            mock_args.verbose = False
            mock_args.command = 'show-config'
            
            mock_parser.parse_args.return_value = mock_args
            mock_build_parser.return_value = mock_parser
            
            # Mock context
            mock_context = Mock()
            mock_context_class.return_value = mock_context
            
            # Mock command handler
            mock_handler = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.message = "Success"
            mock_result.exit_code = 0
            mock_handler.run.return_value = mock_result
            
            # Mock all services to avoid initialization issues
            with patch('traverser_ai_api.cli.services.config_service.ConfigService'):
                with patch('traverser_ai_api.cli.services.device_service.DeviceService'):
                    with patch('traverser_ai_api.cli.services.app_scan_service.AppScanService'):
                        with patch('traverser_ai_api.cli.services.crawler_service.CrawlerService'):
                            with patch('traverser_ai_api.cli.services.analysis_service.AnalysisService'):
                                with patch('traverser_ai_api.cli.services.focus_area_service.FocusAreaService'):
                                    with patch('traverser_ai_api.cli.services.openrouter_service.OpenRouterService'):
                                        # Mock registry
                                        with patch('traverser_ai_api.cli.main.CommandRegistry') as mock_registry_class:
                                            mock_registry = Mock()
                                            mock_registry.groups = {}  # Make groups a dict instead of Mock
                                            mock_registry.standalone_commands = {}  # Make standalone_commands a dict
                                            mock_registry_class.return_value = mock_registry
                                            mock_registry.get_command_handler.return_value = mock_handler
                                            
                                            # Run CLI
                                            result = run(['show-config'])
                                        
                                        # Verify successful execution
                                        assert result == 0
                                        mock_handler.run.assert_called_once_with(mock_args, mock_context)


@pytest.mark.cli
def test_run_command_execution_with_failure():
    """Test command execution with failure."""
    with patch('traverser_ai_api.cli.main.build_parser') as mock_build_parser:
        with patch('traverser_ai_api.cli.main.CLIContext') as mock_context_class:
            # Setup mocks
            mock_parser = Mock()
            mock_args = Mock()
            mock_args.verbose = False
            mock_args.command = 'invalid-command'
            
            mock_parser.parse_args.return_value = mock_args
            mock_build_parser.return_value = mock_parser
            
            # Mock context
            mock_context = Mock()
            mock_context_class.return_value = mock_context
            
            # Mock all services to avoid initialization issues
            with patch('traverser_ai_api.cli.services.config_service.ConfigService'):
                with patch('traverser_ai_api.cli.services.device_service.DeviceService'):
                    with patch('traverser_ai_api.cli.services.app_scan_service.AppScanService'):
                        with patch('traverser_ai_api.cli.services.crawler_service.CrawlerService'):
                            with patch('traverser_ai_api.cli.services.analysis_service.AnalysisService'):
                                with patch('traverser_ai_api.cli.services.focus_area_service.FocusAreaService'):
                                    with patch('traverser_ai_api.cli.services.openrouter_service.OpenRouterService'):
                                        # Mock registry with no handler
                                        with patch('traverser_ai_api.cli.main.CommandRegistry') as mock_registry_class:
                                            mock_registry = Mock()
                                            mock_registry.groups = {}  # Make groups a dict instead of Mock
                                            mock_registry.standalone_commands = {}  # Make standalone_commands a dict
                                            mock_registry_class.return_value = mock_registry
                                            mock_registry.get_command_handler.return_value = None
                                            
                                            with patch('sys.stdout') as mock_stdout:
                                                # Run CLI
                                                result = run(['invalid-command'])
                                            
                                            # Should print help and exit with 1
                                            assert result == 1
                                            mock_parser.print_help.assert_called_once()


@pytest.mark.cli
def test_run_with_verbose_flag():
    """Test CLI run with verbose flag."""
    with patch('traverser_ai_api.cli.main.build_parser') as mock_build_parser:
        with patch('traverser_ai_api.cli.main.CLIContext') as mock_context_class:
            # Setup mocks
            mock_parser = Mock()
            mock_args = Mock()
            mock_args.verbose = True
            mock_args.command = 'show-config'
            
            mock_parser.parse_args.return_value = mock_args
            mock_build_parser.return_value = mock_parser
            
            # Mock context
            mock_context = Mock()
            mock_context_class.return_value = mock_context
            
            # Mock command handler
            mock_handler = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.message = "Verbose success"
            mock_result.exit_code = 0
            mock_handler.run.return_value = mock_result
            
            # Mock all services to avoid initialization issues
            with patch('traverser_ai_api.cli.services.config_service.ConfigService'):
                with patch('traverser_ai_api.cli.services.device_service.DeviceService'):
                    with patch('traverser_ai_api.cli.services.app_scan_service.AppScanService'):
                        with patch('traverser_ai_api.cli.services.crawler_service.CrawlerService'):
                            with patch('traverser_ai_api.cli.services.analysis_service.AnalysisService'):
                                with patch('traverser_ai_api.cli.services.focus_area_service.FocusAreaService'):
                                    with patch('traverser_ai_api.cli.services.openrouter_service.OpenRouterService'):
                                        # Mock registry
                                        with patch('traverser_ai_api.cli.main.CommandRegistry') as mock_registry_class:
                                            mock_registry = Mock()
                                            mock_registry.groups = {}  # Make groups a dict instead of Mock
                                            mock_registry.standalone_commands = {}  # Make standalone_commands a dict
                                            mock_registry_class.return_value = mock_registry
                                            mock_registry.get_command_handler.return_value = mock_handler
                                            
                                            # Run CLI with verbose
                                            result = run(['--verbose', 'show-config'])
                                        
                                        # Verify context was created with verbose=True
                                        mock_context_class.assert_called_once_with(verbose=True)
                                        assert result == 0


@pytest.mark.cli
def test_run_services_registration():
    """Test that services are properly registered."""
    with patch('traverser_ai_api.cli.main.build_parser') as mock_build_parser:
        with patch('traverser_ai_api.cli.main.CLIContext') as mock_context_class:
            # Setup mocks
            mock_parser = Mock()
            mock_args = Mock()
            mock_args.verbose = False
            mock_args.command = 'show-config'
            
            mock_parser.parse_args.return_value = mock_args
            mock_build_parser.return_value = mock_parser
            
            # Mock context with services registry
            mock_context = Mock()
            mock_services = Mock()
            mock_context.services = mock_services
            mock_context_class.return_value = mock_context
            
            # Mock command handler
            mock_handler = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.message = "Success"
            mock_result.exit_code = 0
            mock_handler.run.return_value = mock_result
            
            # Mock _register_commands to avoid the len() issue
            with patch('traverser_ai_api.cli.main._register_commands'):
                # Mock registry
                with patch('traverser_ai_api.cli.main.CommandRegistry') as mock_registry_class:
                    mock_registry = Mock()
                    mock_registry.groups = {}  # Make groups a dict instead of Mock
                    mock_registry.standalone_commands = {}  # Make standalone_commands a dict
                    mock_registry_class.return_value = mock_registry
                    mock_registry.get_command_handler.return_value = mock_handler
                    
                    # Mock config service to provide proper paths
                    with patch('traverser_ai_api.cli.services.config_service.ConfigService'):
                        # Mock CrawlerService to avoid path issues
                        with patch('traverser_ai_api.cli.services.crawler_service.CrawlerService'):
                            # Run CLI
                            result = run(['show-config'])
                        
                        # Verify services were registered
                        expected_services = [
                            'telemetry', 'config', 'device', 'app_scan',
                            'crawler', 'analysis', 'focus', 'openrouter'
                        ]
                        
                        for service_name in expected_services:
                            mock_services.register.assert_any_call(service_name, ANY)
                        
                        assert result == 0
