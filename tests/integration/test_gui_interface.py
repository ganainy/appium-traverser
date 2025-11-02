#!/usr/bin/env python3
"""
Integration test for GUI using core modules.

This test verifies that the GUI interface can successfully import and use
the core modules from the layered architecture.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

# Test that GUI can import core modules
def test_gui_can_import_core_modules():
    """Test that GUI can import all core modules without errors."""
    try:
        from core.config import Configuration
        from core.storage import Storage
        from core.crawler import CrawlerSession, Crawler
        from core.parser import ParsedData, parse_raw_data
    except ImportError as e:
        pytest.fail(f"GUI failed to import core modules: {e}")

def test_gui_can_create_core_instances():
    """Test that GUI can create instances of core classes."""
    from core.config import Configuration
    from core.storage import Storage
    from core.crawler import CrawlerSession, Crawler
    from core.parser import ParsedData

    # Test Configuration creation with required settings
    config = Configuration(
        config_id="test-gui-config",
        name="GUI Test Config",
        settings={
            "max_depth": 5,
            "timeout": 60,
            "platform": "android"
        }
    )
    assert config.config_id == "test-gui-config"
    assert config.name == "GUI Test Config"
    assert config.settings["max_depth"] == 5

    # Test Storage creation with temp database
    import tempfile
    import os
    import time
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()

    storage = None
    try:
        storage = Storage(temp_db_path)
        assert storage.db_path == temp_db_path
    finally:
        if storage:
            del storage
        time.sleep(0.1)
        try:
            os.unlink(temp_db_path)
        except OSError:
            pass

    # Test CrawlerSession creation
    session = CrawlerSession(config, "test-gui-session")
    assert session.session_id == "test-gui-session"
    assert session.config_id == "test-gui-config"
    assert session.status == "pending"

    # Test ParsedData creation
    parsed_data = ParsedData(
        session_id="test-gui-session",
        element_type="button",
        identifier="test-button",
        bounding_box={"top_left": [10, 20], "bottom_right": [30, 40]}
    )
    assert parsed_data.session_id == "test-gui-session"
    assert parsed_data.element_type == "button"
    assert parsed_data.identifier == "test-button"

def test_gui_core_validation_works():
    """Test that core validation works in GUI context."""
    from core.config import Configuration
    from core.parser import ParsedData

    # Test Configuration validation with proper settings
    config = Configuration(
        config_id="test-gui-config",
        name="GUI Test Config",
        settings={
            "max_depth": 5,
            "timeout": 60,
            "platform": "android"
        }
    )
    config.validate()  # Should not raise

    # Test ParsedData validation
    parsed_data = ParsedData(
        session_id="test-gui-session",
        element_type="button",
        identifier="test-button",
        bounding_box={"top_left": [10, 20], "bottom_right": [30, 40]}
    )
    parsed_data.validate()  # Should not raise

def test_gui_core_storage_operations():
    """Test that core storage operations work in GUI context."""
    from core.config import Configuration
    from core.storage import Storage
    import tempfile
    import os
    import time

    # Create temp database with unique name
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()

    storage = None
    try:
        storage = Storage(temp_db_path)

        # Test saving configuration
        config = Configuration(
            config_id="test-gui-config",
            name="GUI Test Config",
            settings={
                "max_depth": 5,
                "timeout": 60,
                "platform": "android"
            }
        )
        storage.save_configuration(config)

        # Test retrieving configuration
        retrieved = storage.get_configuration("test-gui-config")
        assert retrieved is not None
        assert retrieved.config_id == "test-gui-config"
        assert retrieved.name == "GUI Test Config"

    finally:
        if storage:
            del storage
        time.sleep(0.1)
        try:
            os.unlink(temp_db_path)
        except OSError:
            pass

def test_gui_core_crawler_operations():
    """Test that core crawler operations work in GUI context."""
    from core.crawler import CrawlerSession, Crawler
    from core.config import Configuration

    # Setup config with required settings
    config = Configuration(
        config_id="test-gui-config",
        name="GUI Test Config",
        settings={
            "max_depth": 5,
            "timeout": 60,
            "platform": "android"
        }
    )

    # Create crawler
    crawler = Crawler(config)

    # Test session operations
    session = crawler.start_session()
    assert session is not None
    assert isinstance(session, CrawlerSession)
    assert session.status == "pending"

    # Test get status
    status_session = crawler.get_status(session.session_id)
    assert status_session is not None
    assert isinstance(status_session, CrawlerSession)
    assert status_session.session_id == session.session_id

    # Test stop session
    stopped_session = crawler.stop_session(session.session_id)
    assert stopped_session is not None
    assert isinstance(stopped_session, CrawlerSession)
    assert stopped_session.status == "stopped"

def test_gui_core_parser_operations():
    """Test that core parser operations work in GUI context."""
    from core.parser import parse_raw_data

    # Test parsing empty data (current implementation returns empty list)
    result = parse_raw_data({})
    assert isinstance(result, list)
    assert len(result) == 0

def test_gui_core_error_handling():
    """Test that core error handling works in GUI context."""
    from core.config import Configuration
    from core.parser import ParsedData

    # Test Configuration validation error - empty name
    config = Configuration(
        name="",  # Invalid: empty name
        settings={
            "max_depth": 5,
            "timeout": 60,
            "platform": "android"
        }
    )

    with pytest.raises(ValueError, match="Configuration name must be a non-empty string"):
        config.validate()

    # Test ParsedData validation error
    parsed_data = ParsedData(
        session_id="test-session",
        element_type="invalid_type",  # Invalid element type
        identifier="test",
        bounding_box={"top_left": [10, 20], "bottom_right": [30, 40]}
    )

    with pytest.raises(ValueError, match="Invalid element type"):
        parsed_data.validate()

def test_gui_interface_can_be_imported():
    """Test that GUI interface can be imported without errors."""
    try:
        from interfaces.gui import GUICrawlerInterface, create_gui_interface
    except ImportError as e:
        pytest.fail(f"GUI interface failed to import: {e}")


def test_gui_interface_initialization():
    """Test that GUI interface can be initialized."""
    from interfaces.gui import GUICrawlerInterface

    interface = GUICrawlerInterface()
    assert interface is not None
    assert interface.config is None
    assert interface.storage is None
    assert interface.crawler is None
    assert interface.current_session is None


def test_gui_interface_core_initialization():
    """Test that GUI interface can initialize core modules."""
    from interfaces.gui import GUICrawlerInterface

    config_data = {
        "name": "Test GUI Config",
        "settings": {
            "max_depth": 5,
            "timeout": 60,
            "platform": "android"
        }
    }

    interface = GUICrawlerInterface(config_data)
    success = interface.initialize_core()

    assert success is True
    assert interface.config is not None
    assert interface.storage is not None
    assert interface.crawler is not None
    assert interface.config.name == "Test GUI Config"


def test_gui_interface_default_initialization():
    """Test that GUI interface can initialize with default config."""
    from interfaces.gui import GUICrawlerInterface

    interface = GUICrawlerInterface()
    success = interface.initialize_core()

    assert success is True
    assert interface.config is not None
    assert interface.storage is not None
    assert interface.crawler is not None
    assert interface.config.name == "default"
    assert interface.config.is_default is True


def test_gui_interface_session_operations():
    """Test that GUI interface session operations work."""
    from interfaces.gui import GUICrawlerInterface

    interface = GUICrawlerInterface()
    interface.initialize_core()

    # Start session
    session_id = interface.start_crawler_session()
    assert session_id is not None
    assert interface.current_session is not None
    assert interface.current_session.session_id == session_id

    # Get status
    status = interface.get_session_status()
    assert status is not None
    assert status["session_id"] == session_id
    assert status["status"] == "pending"

    # Stop session
    success = interface.stop_crawler_session()
    assert success is True

    # Verify stopped
    status = interface.get_session_status()
    assert status is not None
    assert status["status"] == "stopped"


def test_gui_interface_configuration_operations():
    """Test that GUI interface configuration operations work."""
    from interfaces.gui import GUICrawlerInterface

    interface = GUICrawlerInterface()
    interface.initialize_core()

    # Save configuration
    success = interface.save_configuration()
    assert success is True

    # Load configuration
    assert interface.config is not None
    config_id = interface.config.config_id
    success = interface.load_configuration(config_id)
    assert success is True


def test_gui_interface_error_handling():
    """Test that GUI interface handles errors gracefully."""
    from interfaces.gui import GUICrawlerInterface

    interface = GUICrawlerInterface()

    # Test operations without initialization
    assert interface.start_crawler_session() is None
    assert interface.get_session_status() is None
    assert interface.stop_crawler_session() is False
    assert interface.get_session_results() is None
    assert interface.save_configuration() is False
    assert interface.load_configuration("nonexistent") is False


def test_gui_convenience_functions():
    """Test GUI convenience functions."""
    from interfaces.gui import create_gui_interface, start_gui_session, get_gui_status, stop_gui_session

    # Create interface
    interface = create_gui_interface()
    assert interface is not None

    # Start session
    session_id = start_gui_session(interface)
    assert session_id is not None

    # Get status
    status = get_gui_status(interface)
    assert status is not None

    # Stop session
    success = stop_gui_session(interface)
    assert success is True