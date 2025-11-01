#!/usr/bin/env python3
"""
Integration test for CLI using core modules.

This test verifies that the CLI interface can successfully import and use
the core modules from the layered architecture.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

# Test that CLI can import core modules
def test_cli_can_import_core_modules():
    """Test that CLI can import all core modules without errors."""
    try:
        from traverser_ai_api.core.config import Configuration
        from traverser_ai_api.core.storage import Storage
        from traverser_ai_api.core.crawler import CrawlerSession, Crawler
        from traverser_ai_api.core.parser import ParsedData, parse_raw_data
    except ImportError as e:
        pytest.fail(f"CLI failed to import core modules: {e}")

def test_cli_can_create_core_instances():
    """Test that CLI can create instances of core classes."""
    from traverser_ai_api.core.config import Configuration
    from traverser_ai_api.core.storage import Storage
    from traverser_ai_api.core.crawler import CrawlerSession, Crawler
    from traverser_ai_api.core.parser import ParsedData

    # Test Configuration creation with required settings
    config = Configuration(
        config_id="test-cli-config",
        name="CLI Test Config",
        settings={
            "max_depth": 5,
            "timeout": 60,
            "platform": "android"
        }
    )
    assert config.config_id == "test-cli-config"
    assert config.name == "CLI Test Config"
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
    session = CrawlerSession(config, "test-cli-session")
    assert session.session_id == "test-cli-session"
    assert session.config_id == "test-cli-config"
    assert session.status == "pending"

    # Test ParsedData creation
    parsed_data = ParsedData(
        session_id="test-cli-session",
        element_type="button",
        identifier="test-button",
        bounding_box={"top_left": [10, 20], "bottom_right": [30, 40]}
    )
    assert parsed_data.session_id == "test-cli-session"
    assert parsed_data.element_type == "button"
    assert parsed_data.identifier == "test-button"

def test_cli_core_validation_works():
    """Test that core validation works in CLI context."""
    from traverser_ai_api.core.config import Configuration
    from traverser_ai_api.core.parser import ParsedData

    # Test Configuration validation with proper settings
    config = Configuration(
        config_id="test-cli-config",
        name="CLI Test Config",
        settings={
            "max_depth": 5,
            "timeout": 60,
            "platform": "android"
        }
    )
    config.validate()  # Should not raise

    # Test ParsedData validation
    parsed_data = ParsedData(
        session_id="test-cli-session",
        element_type="button",
        identifier="test-button",
        bounding_box={"top_left": [10, 20], "bottom_right": [30, 40]}
    )
    parsed_data.validate()  # Should not raise

def test_cli_core_storage_operations():
    """Test that core storage operations work in CLI context."""
    from traverser_ai_api.core.config import Configuration
    from traverser_ai_api.core.storage import Storage
    import tempfile
    import os
    import time

    # Create temp database with unique name
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()  # Close the file handle

    storage = None
    try:
        storage = Storage(temp_db_path)

        # Test saving configuration
        config = Configuration(
            config_id="test-cli-config",
            name="CLI Test Config",
            settings={
                "max_depth": 5,
                "timeout": 60,
                "platform": "android"
            }
        )
        storage.save_configuration(config)

        # Test retrieving configuration
        retrieved = storage.get_configuration("test-cli-config")
        assert retrieved is not None
        assert retrieved.config_id == "test-cli-config"
        assert retrieved.name == "CLI Test Config"

    finally:
        # Clean up
        if storage:
            del storage  # Try to release any references
        # Give it a moment for file handles to be released
        time.sleep(0.1)
        try:
            os.unlink(temp_db_path)
        except OSError:
            pass  # Ignore if file is still locked

def test_cli_core_crawler_operations():
    """Test that core crawler operations work in CLI context."""
    from traverser_ai_api.core.crawler import CrawlerSession, Crawler
    from traverser_ai_api.core.config import Configuration

    # Setup config with required settings
    config = Configuration(
        config_id="test-cli-config",
        name="CLI Test Config",
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

def test_cli_core_parser_operations():
    """Test that core parser operations work in CLI context."""
    from traverser_ai_api.core.parser import parse_raw_data

    # Test parsing empty data (current implementation returns empty list)
    result = parse_raw_data({})
    assert isinstance(result, list)
    assert len(result) == 0

def test_cli_core_error_handling():
    """Test that core error handling works in CLI context."""
    from traverser_ai_api.core.config import Configuration
    from traverser_ai_api.core.parser import ParsedData

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