"""
This file provides shared pytest fixtures for the test suite. It includes:
- Temporary directory and configuration fixtures for test isolation.
- Project root path setup for import resolution.
- Conditional imports and mocks for CLI and config dependencies.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import Generator, Dict, Any

import pytest

# Add project root to sys.path for imports (avoid changing CWD)
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# Try to import from traverser_ai_api package first, but delay Config import to fixture
try:
    from cli.shared.context import CLIContext, ServiceRegistry
    from utils.utils import LoggerManager
    CLI_AVAILABLE = True
except ImportError:
    CLIContext = None  # type: ignore
    ServiceRegistry = None  # type: ignore
    LoggerManager = None  # type: ignore
    CLI_AVAILABLE = False


@pytest.fixture(scope="session", autouse=True)
def restore_cwd():
    """Restore original working directory after tests."""
    yield
    # No need to restore CWD since we're not changing it anymore
    pass


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_config(temp_dir: Path) -> Mock:
    """Create a mock configuration object."""
    from config.config import Config
    config = Mock(spec=Config)
    config.APP_PACKAGE = "com.example.testapp"
    config.APP_ACTIVITY = "com.example.testapp.MainActivity"
    config.BASE_DIR = str(temp_dir)
    config.OUTPUT_DATA_DIR = str(temp_dir / "output")
    config.LOG_DIR = str(temp_dir / "logs")
    config.LOG_FILE_NAME = "test.log"
    config.SHUTDOWN_FLAG_PATH = str(temp_dir / "shutdown.flag")
    config.PAUSE_FLAG_PATH = str(temp_dir / "pause.flag")
    config.AI_PROVIDER = "gemini"
    config.GEMINI_API_KEY = "test_key_12345"
    config.ENABLE_TRAFFIC_CAPTURE = False
    config.ENABLE_MOBSF_ANALYSIS = False
    config.DEFAULTS_MODULE_PATH = str(temp_dir / "config.py")
    config.USER_CONFIG_JSON_PATH = str(temp_dir / "user_config.json")
    # Add get_value method for compatibility with config service
    config.get_value = lambda key, default=None: {
        "APP_PACKAGE": config.APP_PACKAGE,
        "APP_ACTIVITY": config.APP_ACTIVITY,
        "BASE_DIR": config.BASE_DIR,
        "OUTPUT_DATA_DIR": config.OUTPUT_DATA_DIR,
        "LOG_DIR": config.LOG_DIR,
        "SHUTDOWN_FLAG_PATH": config.SHUTDOWN_FLAG_PATH,
        "PAUSE_FLAG_PATH": config.PAUSE_FLAG_PATH,
        "AI_PROVIDER": config.AI_PROVIDER,
        "GEMINI_API_KEY": config.GEMINI_API_KEY,
        "ENABLE_TRAFFIC_CAPTURE": config.ENABLE_TRAFFIC_CAPTURE,
        "ENABLE_MOBSF_ANALYSIS": config.ENABLE_MOBSF_ANALYSIS
    }.get(key, default)
    return config


@pytest.fixture
def mock_logger_manager(temp_dir: Path) -> Mock:
    """Create a mock logger manager."""
    logger_manager = Mock(spec=LoggerManager)
    logger_manager.setup_logging = Mock()
    return logger_manager


@pytest.fixture
def cli_context(mock_config: Mock, mock_logger_manager: Mock, temp_dir: Path):
    """Create a CLI context with mocked dependencies."""
    if not CLI_AVAILABLE or CLIContext is None or ServiceRegistry is None:
        pytest.skip("CLI modules not available")
    
    # Create a temporary context with mocked dependencies
    context = CLIContext.__new__(CLIContext)  # type: ignore
    context.verbose = False
    context._config = mock_config
    context._logger_manager = mock_logger_manager
    context._services = ServiceRegistry()  # type: ignore
    context._log_level = "WARNING"
    
    # Register a mock config service
    mock_config_service = Mock()
    mock_config_service.get_config_value = lambda key, default=None: {
        "BASE_DIR": str(temp_dir),
        "OUTPUT_DATA_DIR": str(temp_dir / "output"),
        "LOG_DIR": str(temp_dir / "logs"),
        "SHUTDOWN_FLAG_PATH": str(temp_dir / "shutdown.flag"),
        "PAUSE_FLAG_PATH": str(temp_dir / "pause.flag"),
        "APP_PACKAGE": "com.example.testapp",
        "APP_ACTIVITY": "com.example.testapp.MainActivity"
    }.get(key, default)
    context._services.register("config", mock_config_service)
    
    # Ensure output directories exist
    os.makedirs(mock_config.OUTPUT_DATA_DIR, exist_ok=True)
    os.makedirs(mock_config.LOG_DIR, exist_ok=True)
    
    return context


@pytest.fixture
def mock_registry():
    """Create a mock command registry with proper dict attributes."""
    registry = Mock()
    registry.groups = {}
    registry.standalone_commands = {}
    return registry


@pytest.fixture
def mock_args() -> Mock:
    """Create mock command line arguments."""
    args = Mock()
    args.verbose = False
    args.command = "test"
    return args


@pytest.fixture
def sample_app_data() -> Dict[str, Any]:
    """Sample app data for testing."""
    return {
        "apps": [
            {
                "package_name": "com.example.app1",
                "app_name": "Example App 1",
                "version": "1.0.0",
                "is_health_app": True
            },
            {
                "package_name": "com.example.app2",
                "app_name": "Example App 2",
                "version": "2.0.0",
                "is_health_app": False
            }
        ]
    }


@pytest.fixture
def sample_focus_areas() -> Dict[str, Any]:
    """Sample focus areas data for testing."""
    return {
        "focus_areas": [
            {
                "name": "Login Area",
                "bounds": {"x1": 0, "y1": 0, "x2": 200, "y2": 100},
                "description": "Login form area"
            },
            {
                "name": "Dashboard",
                "bounds": {"x1": 0, "y1": 100, "x2": 300, "y2": 400},
                "description": "Main dashboard area"
            }
        ]
    }


@pytest.fixture
def mock_crawler_orchestrator() -> Mock:
    """Create a mock crawler orchestrator."""
    orchestrator = Mock()
    orchestrator.prepare_plan.return_value = Mock(
        app_package="com.example.testapp",
        app_activity="com.example.testapp.MainActivity",
        validation_passed=True,
        validation_messages=[]
    )
    orchestrator.start_crawler.return_value = True
    orchestrator.stop_crawler.return_value = True
    orchestrator.pause_crawler.return_value = True
    orchestrator.resume_crawler.return_value = True
    orchestrator.get_status.return_value = {
        "is_running": False,
        "process_id": None,
        "app_package": "com.example.testapp",
        "app_activity": "com.example.testapp.MainActivity"
    }
    return orchestrator


@pytest.fixture
def mock_backend() -> Mock:
    """Create a mock process backend."""
    backend = Mock()
    backend.start_process.return_value = True
    backend.stop_process.return_value = True
    backend.is_process_running.return_value = False
    backend.get_process_id.return_value = 12345
    return backend
