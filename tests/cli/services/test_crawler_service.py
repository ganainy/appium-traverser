"""
Tests for crawler service functionality.
"""

import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

import pytest

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
api_dir = project_root / "traverser_ai_api"
sys.path.insert(0, str(api_dir))

try:
    from traverser_ai_api.cli.services.crawler_service import CrawlerService
    from traverser_ai_api.cli.commands.base import CommandResult
    from traverser_ai_api.cli.shared.context import CLIContext
    from traverser_ai_api.core.controller import CrawlerOrchestrator
    from traverser_ai_api.core.adapters import create_process_backend
except ImportError as e:
    pytest.skip(f"Crawler service module not available: {e}", allow_module_level=True)


@pytest.mark.cli
def test_crawler_service_init(cli_context: CLIContext):
    """Test CrawlerService initialization."""
    service = CrawlerService(cli_context)
    
    assert service.context == cli_context
    assert service.orchestrator is None
    assert service.backend is None


@pytest.mark.cli
def test_crawler_service_start_crawler_success(cli_context, mock_crawler_orchestrator: Mock):
    """Test successful crawler start."""
    service = CrawlerService(cli_context)
    service.orchestrator = mock_crawler_orchestrator
    
    result = service.start_crawler()
    
    assert result is True
    mock_crawler_orchestrator.start_crawler.assert_called_once()


@pytest.mark.cli
def test_crawler_service_start_crawler_failure(cli_context, mock_crawler_orchestrator: Mock):
    """Test failed crawler start."""
    service = CrawlerService(cli_context)
    service.orchestrator = mock_crawler_orchestrator
    
    # Mock orchestrator to return failure
    mock_crawler_orchestrator.start_crawler.return_value = False
    
    result = service.start_crawler()
    
    assert result is False


@pytest.mark.cli
def test_crawler_service_stop_crawler_success(cli_context, mock_crawler_orchestrator: Mock):
    """Test successful crawler stop."""
    service = CrawlerService(cli_context)
    service.orchestrator = mock_crawler_orchestrator
    
    # Mock orchestrator as running
    mock_crawler_orchestrator.stop_crawler.return_value = True
    
    result = service.stop_crawler()
    
    assert result is True
    mock_crawler_orchestrator.stop_crawler.assert_called_once()


@pytest.mark.cli
def test_crawler_service_stop_crawler_not_running(cli_context, mock_crawler_orchestrator: Mock):
    """Test crawler stop when not running."""
    service = CrawlerService(cli_context)
    service.orchestrator = mock_crawler_orchestrator
    
    # Mock orchestrator as not running
    mock_crawler_orchestrator.stop_crawler.return_value = False
    
    result = service.stop_crawler()
    
    assert result is False


@pytest.mark.cli
def test_crawler_service_pause_crawler_success(cli_context, mock_crawler_orchestrator: Mock):
    """Test successful crawler pause."""
    service = CrawlerService(cli_context)
    service.orchestrator = mock_crawler_orchestrator
    
    result = service.pause_crawler()
    
    assert result is True
    mock_crawler_orchestrator.pause_crawler.assert_called_once()


@pytest.mark.cli
def test_crawler_service_resume_crawler_success(cli_context, mock_crawler_orchestrator: Mock):
    """Test successful crawler resume."""
    service = CrawlerService(cli_context)
    service.orchestrator = mock_crawler_orchestrator
    
    result = service.resume_crawler()
    
    assert result is True
    mock_crawler_orchestrator.resume_crawler.assert_called_once()


@pytest.mark.cli
def test_crawler_service_get_status(cli_context, mock_crawler_orchestrator: Mock):
    """Test get crawler status."""
    service = CrawlerService(cli_context)
    service.orchestrator = mock_crawler_orchestrator
    
    # Mock status
    mock_status = {
        "is_running": True,
        "process_id": 12345,
        "app_package": "com.example.app",
        "app_activity": "com.example.app.MainActivity",
        "uptime": "00:10:30"
    }
    mock_crawler_orchestrator.get_status.return_value = mock_status
    
    result = service.get_status()
    
    assert isinstance(result, dict)
    assert result["process"] == "Running (PID 12345, CLI-managed)"
    assert result["target_app"] == "com.example.app"
    mock_crawler_orchestrator.get_status.assert_called_once()


# Note: CrawlerService initializes orchestrator in __init__, so initialize/validate tests
# are not applicable to the current implementation


@pytest.mark.cli
def test_crawler_service_cleanup(cli_context: CLIContext, mock_crawler_orchestrator: Mock):
    """Test service cleanup."""
    service = CrawlerService(cli_context)
    service.orchestrator = mock_crawler_orchestrator
    service.backend = Mock()
    
    service.cleanup()
    
    mock_crawler_orchestrator.stop_crawler.assert_called_once()
    service.backend.stop_process.assert_called_once()
    assert service.orchestrator is None
    assert service.backend is None


@pytest.mark.cli
def test_crawler_service_cleanup_not_running(cli_context: CLIContext, mock_crawler_orchestrator: Mock):
    """Test service cleanup when not running."""
    service = CrawlerService(cli_context)
    service.orchestrator = mock_crawler_orchestrator
    service.backend = Mock()
    
    # Mock orchestrator as not running
    mock_crawler_orchestrator.stop_crawler.return_value = False
    
    service.cleanup()
    
    mock_crawler_orchestrator.stop_crawler.assert_called_once()
    # Should still cleanup backend even if orchestrator wasn't running
    service.backend.stop_process.assert_called_once()


# Note: get_logs, validate_prerequisites, and initialize methods are not implemented
# in the current CrawlerService, so these tests are omitted
