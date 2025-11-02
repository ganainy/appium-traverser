"""
Tests for apps command functionality.
"""

import argparse
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import json

import pytest

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from cli.commands.apps import (
        ScanAllAppsCommand,
        ScanHealthAppsCommand,
        ListAllAppsCommand,
        ListHealthAppsCommand,
        SelectAppCommand,
        ShowSelectedAppCommand,
        AppsCommandGroup
    )
    from cli.commands.base import CommandResult
    from cli.shared.context import CLIContext
except ImportError as e:
    try:
        from traverser_ai_api.cli.commands.apps import (
            ScanAllAppsCommand,
            ScanHealthAppsCommand,
            ListAllAppsCommand,
            ListHealthAppsCommand,
            SelectAppCommand,
            ShowSelectedAppCommand,
            AppsCommandGroup
        )
        from traverser_ai_api.cli.commands.base import CommandResult
        from traverser_ai_api.cli.shared.context import CLIContext
    except ImportError as e2:
        pytest.skip(f"Apps command modules not available: {e2}", allow_module_level=True)


@pytest.mark.cli
def test_scan_all_apps_command_properties():
    """Test ScanAllAppsCommand properties."""
    command = ScanAllAppsCommand()
    
    assert command.name == "scan-all"
    assert "Scan device and cache ALL installed apps" in command.description
    # Note: requires_device and requires_app attributes don't exist in current implementation


@pytest.mark.cli
def test_scan_all_apps_command_run_success(cli_context, sample_app_data: dict):
    """Test successful scan all apps command."""
    command = ScanAllAppsCommand()
    args = Mock()
    
    # Mock app scan service
    mock_app_scan_service = Mock()
    mock_app_scan_service.scan_all_apps.return_value = (True, "/tmp/cache.json")
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert "Successfully scanned all apps" in result.message
    mock_app_scan_service.scan_all_apps.assert_called_once()


@pytest.mark.cli
def test_scan_health_apps_command_run_success(cli_context, sample_app_data: dict):
    """Test successful scan health apps command."""
    command = ScanHealthAppsCommand()
    args = Mock()
    
    # Mock app scan service
    mock_app_scan_service = Mock()
    health_apps = [app for app in sample_app_data['apps'] if app['is_health_app']]
    mock_app_scan_service.scan_health_apps.return_value = (True, "/tmp/health_cache.json")
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert "Successfully scanned health apps" in result.message
    mock_app_scan_service.scan_health_apps.assert_called_once()


@pytest.mark.cli
def test_list_all_apps_command_run_success(cli_context, sample_app_data: dict):
    """Test successful list all apps command."""
    command = ListAllAppsCommand()
    args = Mock()
    
    # Mock app scan service
    mock_app_scan_service = Mock()
    mock_app_scan_service.resolve_latest_cache_file.return_value = "/tmp/cache.json"
    mock_app_scan_service.load_apps_from_file.return_value = (True, sample_app_data['apps'])
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert "Listed" in result.message


@pytest.mark.cli
def test_list_health_apps_command_run_success(cli_context, sample_app_data: dict):
    """Test successful list health apps command."""
    command = ListHealthAppsCommand()
    args = Mock()
    
    # Mock app scan service
    mock_app_scan_service = Mock()
    health_apps = [app for app in sample_app_data['apps'] if app['is_health_app']]
    mock_app_scan_service.get_current_health_apps.return_value = health_apps
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert "Listed" in result.message


@pytest.mark.cli
def test_select_app_command_by_index(cli_context, sample_app_data: dict):
    """Test select app command by index."""
    command = SelectAppCommand()
    args = Mock()
    args.app_identifier = "0"
    
    # Mock app scan service
    mock_app_scan_service = Mock()
    selected_app = sample_app_data['apps'][0]
    mock_app_scan_service.select_app.return_value = (True, selected_app)
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert selected_app['app_name'] in result.message
    mock_app_scan_service.select_app.assert_called_once_with("0")


@pytest.mark.cli
def test_select_app_command_by_name(cli_context, sample_app_data: dict):
    """Test select app command by name."""
    command = SelectAppCommand()
    args = Mock()
    args.app_identifier = "Example App 1"
    
    # Mock app scan service
    mock_app_scan_service = Mock()
    selected_app = sample_app_data['apps'][0]
    mock_app_scan_service.select_app.return_value = (True, selected_app)
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert selected_app['app_name'] in result.message
    mock_app_scan_service.select_app.assert_called_once_with("Example App 1")


@pytest.mark.cli
def test_select_app_command_no_selection(cli_context):
    """Test select app command with no selection provided."""
    command = SelectAppCommand()
    args = Mock()
    args.app_identifier = None
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "App scan service not available" in result.message


@pytest.mark.cli
def test_show_selected_app_command_with_selection(cli_context, sample_app_data: dict):
    """Test show selected app command when app is selected."""
    command = ShowSelectedAppCommand()
    args = Mock()
    
    # Mock config service (ShowSelectedAppCommand uses config service, not app_scan)
    mock_config_service = Mock()
    selected_app = sample_app_data['apps'][0]
    mock_config_service.get_config_value.side_effect = lambda key, default=None: {
        "LAST_SELECTED_APP": selected_app,
        "APP_PACKAGE": selected_app['package_name'],
        "APP_ACTIVITY": selected_app.get('activity_name', 'MainActivity')
    }.get(key, default)
    cli_context.services.register("config", mock_config_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert selected_app['app_name'] in result.message


@pytest.mark.cli
def test_show_selected_app_command_no_selection(cli_context):
    """Test show selected app command when no app is selected."""
    command = ShowSelectedAppCommand()
    args = Mock()
    
    # Mock config service (ShowSelectedAppCommand uses config service, not app_scan)
    mock_config_service = Mock()
    mock_config_service.get_config_value.return_value = None
    cli_context.services.register("config", mock_config_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "No app selected" in result.message


@pytest.mark.cli
def test_apps_command_group():
    """Test AppsCommandGroup."""
    group = AppsCommandGroup()
    
    assert group.name == "apps"
    assert "App management" in group.description
    
    commands = group.get_commands()
    assert len(commands) == 6
    
    command_names = [cmd.name for cmd in commands]
    expected_names = ["scan-all", "scan-health", "list-all", "list-health", "select", "show-selected"]
    for name in expected_names:
        assert name in command_names


@pytest.mark.cli
def test_scan_apps_command_no_device(cli_context):
    """Test scan apps command when no device is available."""
    command = ScanAllAppsCommand()
    args = Mock()
    
    # Mock app scan service to return failure
    mock_app_scan_service = Mock()
    mock_app_scan_service.scan_all_apps.return_value = (False, None)
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "Failed to scan apps" in result.message


@pytest.mark.cli
def test_list_apps_command_no_cache(cli_context):
    """Test list apps command when no cache exists."""
    command = ListAllAppsCommand()
    args = Mock()
    
    # Mock app scan service to return no cache file
    mock_app_scan_service = Mock()
    mock_app_scan_service.resolve_latest_cache_file.return_value = None
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "No all-apps cache found" in result.message


@pytest.mark.cli
def test_select_app_command_invalid_index(cli_context):
    """Test select app command with invalid index."""
    command = SelectAppCommand()
    args = Mock()
    args.app_identifier = "999"
    
    # Mock app scan service
    mock_app_scan_service = Mock()
    mock_app_scan_service.select_app.return_value = (False, None)
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "Failed to select app: 999" in result.message


@pytest.mark.cli
def test_select_app_command_app_not_found(cli_context):
    """Test select app command when app is not found."""
    command = SelectAppCommand()
    args = Mock()
    args.app_identifier = "Nonexistent App"
    
    # Mock app scan service
    mock_app_scan_service = Mock()
    mock_app_scan_service.select_app.return_value = (False, None)
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "Failed to select app: Nonexistent App" in result.message


@pytest.mark.cli
def test_apps_command_with_service_unavailable(cli_context):
    """Test apps command when service is unavailable."""
    command = ListAllAppsCommand()
    args = Mock()
    
    # Don't register app scan service
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "not available" in result.message.lower()
    assert result.exit_code == 1


@pytest.mark.cli
def test_apps_command_with_exception(cli_context):
    """Test apps command with unexpected exception."""
    command = ListAllAppsCommand()
    args = Mock()
    
    # Mock app scan service to raise unexpected exception
    mock_app_scan_service = Mock()
    mock_app_scan_service.resolve_latest_cache_file.side_effect = Exception("Unexpected error")
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    # The command doesn't wrap exceptions, so it should propagate
    with pytest.raises(Exception) as exc_info:
        result = command.run(args, cli_context)
    
    assert "Unexpected error" in str(exc_info.value)


@pytest.mark.cli
def test_scan_health_apps_command_no_health_apps(cli_context):
    """Test scan health apps command when no health apps found."""
    command = ScanHealthAppsCommand()
    args = Mock()
    
    # Mock app scan service
    mock_app_scan_service = Mock()
    mock_app_scan_service.scan_health_apps.return_value = (True, "/tmp/health_cache.json")
    cli_context.services.register("app_scan", mock_app_scan_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert "Successfully scanned health apps" in result.message
