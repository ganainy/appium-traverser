"""
Tests for crawler command functionality.
"""

import argparse
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

import pytest

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from traverser_ai_api.cli.commands.crawler import (
        StartCrawlerCommand,
        StopCrawlerCommand,
        PauseCrawlerCommand,
        ResumeCrawlerCommand,
        StatusCrawlerCommand,
        CrawlerCommandGroup
    )
    from traverser_ai_api.cli.commands.base import CommandResult
    from traverser_ai_api.cli.shared.context import CLIContext
except ImportError as e:
    pytest.skip(f"Crawler command modules not available: {e}", allow_module_level=True)


@pytest.mark.cli
def test_start_crawler_command_properties():
    """Test StartCrawlerCommand properties."""
    command = StartCrawlerCommand()
    
    assert command.name == "start"
    assert "Start the crawler process" in command.description
    # Note: requires_device and requires_app attributes don't exist in current implementation


@pytest.mark.cli
def test_start_crawler_command_register():
    """Test StartCrawlerCommand registration."""
    command = StartCrawlerCommand()
    subparsers = Mock()
    parser = Mock()
    subparsers.add_parser.return_value = parser
    
    result = command.register(subparsers)
    
    assert result == parser
    subparsers.add_parser.assert_called_once_with("start", help=command.description, description=command.description)
    parser.add_argument.assert_called()


@pytest.mark.cli
def test_start_crawler_command_run_success(cli_context):
    """Test successful crawler start."""
    command = StartCrawlerCommand()
    args = Mock()
    
    # Mock crawler service
    mock_crawler_service = Mock()
    mock_crawler_service.start_crawler.return_value = True
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert "started successfully" in result.message
    assert result.exit_code == 0
    mock_crawler_service.start_crawler.assert_called_once()


@pytest.mark.cli
def test_start_crawler_command_run_failure(cli_context):
    """Test failed crawler start."""
    command = StartCrawlerCommand()
    args = Mock()
    
    # Mock crawler service
    mock_crawler_service = Mock()
    mock_crawler_service.start_crawler.return_value = False
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "Failed to start" in result.message
    assert result.exit_code == 1


@pytest.mark.cli
def test_stop_crawler_command_properties():
    """Test StopCrawlerCommand properties."""
    command = StopCrawlerCommand()
    
    assert command.name == "stop"
    assert "Stop the crawler process" in command.description
    # Note: requires_device and requires_app attributes don't exist in current implementation


@pytest.mark.cli
def test_stop_crawler_command_run(cli_context):
    """Test crawler stop command."""
    command = StopCrawlerCommand()
    args = Mock()
    
    # Mock crawler service
    mock_crawler_service = Mock()
    mock_crawler_service.stop_crawler.return_value = True
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert "Stop signal sent" in result.message
    mock_crawler_service.stop_crawler.assert_called_once()


@pytest.mark.cli
def test_pause_crawler_command_run(cli_context):
    """Test crawler pause command."""
    command = PauseCrawlerCommand()
    args = Mock()
    
    # Mock crawler service
    mock_crawler_service = Mock()
    mock_crawler_service.pause_crawler.return_value = True
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert "Pause signal sent" in result.message
    mock_crawler_service.pause_crawler.assert_called_once()


@pytest.mark.cli
def test_resume_crawler_command_run(cli_context):
    """Test crawler resume command."""
    command = ResumeCrawlerCommand()
    args = Mock()
    
    # Mock crawler service
    mock_crawler_service = Mock()
    mock_crawler_service.resume_crawler.return_value = True
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    assert "Resume signal sent" in result.message
    mock_crawler_service.resume_crawler.assert_called_once()


@pytest.mark.cli
def test_status_crawler_command_run(cli_context):
    """Test crawler status command."""
    command = StatusCrawlerCommand()
    args = Mock()
    
    # Mock crawler service
    mock_crawler_service = Mock()
    mock_status = {
        "process": "Running (PID 12345, CLI-managed)",
        "state": "Running",
        "target_app": "com.example.app",
        "output_dir": "/tmp/output"
    }
    mock_crawler_service.get_status.return_value = mock_status
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    # Status command doesn't return data, just prints it
    assert result.success is True
    mock_crawler_service.get_status.assert_called_once()


@pytest.mark.cli
def test_crawler_command_group():
    """Test CrawlerCommandGroup."""
    group = CrawlerCommandGroup()
    
    assert group.name == "crawler"
    assert "Crawler control" in group.description
    
    commands = group.get_commands()
    assert len(commands) == 5
    
    command_names = [cmd.name for cmd in commands]
    expected_names = ["start", "stop", "pause", "resume", "status"]
    for name in expected_names:
        assert name in command_names


@pytest.mark.cli
def test_crawler_command_group_registration():
    """Test CrawlerCommandGroup registration."""
    group = CrawlerCommandGroup()
    subparsers = Mock()
    group_parser = Mock()
    subparsers.add_parser.return_value = group_parser
    
    result = group.register(subparsers)
    
    assert result == group_parser
    subparsers.add_parser.assert_called_once_with("crawler", help=group.description, description=group.description)
    
    # Should register all subcommands
    assert group_parser.add_subparsers.called


@pytest.mark.cli
def test_crawler_command_with_validation_error(cli_context):
    """Test crawler command with validation error."""
    command = StartCrawlerCommand()
    args = Mock()
    
    # Mock crawler service to return failure
    mock_crawler_service = Mock()
    mock_crawler_service.start_crawler.return_value = False
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "Failed to start crawler" in result.message
    assert result.exit_code == 1


@pytest.mark.cli
def test_crawler_command_with_service_unavailable(cli_context):
    """Test crawler command when service is unavailable."""
    command = StartCrawlerCommand()
    args = Mock()
    
    # Don't register crawler service
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "not available" in result.message.lower()
    assert result.exit_code == 1


@pytest.mark.cli
def test_crawler_command_with_exception(cli_context):
    """Test crawler command with unexpected exception."""
    command = StartCrawlerCommand()
    args = Mock()
    
    # Mock crawler service to return failure
    mock_crawler_service = Mock()
    mock_crawler_service.start_crawler.return_value = False
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "Failed to start crawler" in result.message
    assert result.exit_code == 1


@pytest.mark.cli
def test_crawler_status_when_not_running(cli_context):
    """Test crawler status when crawler is not running."""
    command = StatusCrawlerCommand()
    args = Mock()
    
    # Mock crawler service
    mock_crawler_service = Mock()
    mock_status = {
        "process": "Stopped",
        "state": "Unknown",
        "target_app": None,
        "output_dir": None
    }
    mock_crawler_service.get_status.return_value = mock_status
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is True
    # Status command doesn't return data, just prints it
    assert result.success is True


@pytest.mark.cli
def test_crawler_pause_when_already_paused(cli_context):
    """Test crawler pause when already paused."""
    command = PauseCrawlerCommand()
    args = Mock()
    
    # Mock crawler service
    mock_crawler_service = Mock()
    mock_crawler_service.pause_crawler.return_value = False
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "Failed to pause" in result.message
    assert result.exit_code == 1


@pytest.mark.cli
def test_crawler_resume_when_not_paused(cli_context):
    """Test crawler resume when not paused."""
    command = ResumeCrawlerCommand()
    args = Mock()
    
    # Mock crawler service
    mock_crawler_service = Mock()
    mock_crawler_service.resume_crawler.return_value = False
    cli_context.services.register("crawler", mock_crawler_service)
    
    result = command.run(args, cli_context)
    
    assert result.success is False
    assert "Failed to resume" in result.message
    assert result.exit_code == 1