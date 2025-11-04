#!/usr/bin/env python3
"""
Contract test for core API compliance.

This test verifies that the core layer maintains expected interface contracts
and behaves consistently across different usage scenarios.
"""


import pytest
from typing import Dict, Any
from unittest.mock import patch
from core.crawler import CrawlerSession
from core.parser import ParsedData

def test_configuration_contract():
    """Test Configuration class maintains its contract."""
    from core.config import Configuration

    # Test constructor contract
    config = Configuration(
        name="Test Config",
        settings={"max_depth": 5, "timeout": 60, "platform": "android"}
    )

    # Verify attributes exist and have correct types
    assert hasattr(config, 'config_id')
    assert hasattr(config, 'name')
    assert hasattr(config, 'settings')
    assert hasattr(config, 'created_at')
    assert hasattr(config, 'updated_at')
    assert hasattr(config, 'is_default')

    assert isinstance(config.config_id, str)
    assert isinstance(config.name, str)
    assert isinstance(config.settings, dict)
    assert config.name == "Test Config"
    assert config.settings["max_depth"] == 5

    # Test validation contract
    assert hasattr(config, 'validate')
    config.validate()  # Should not raise

    # Test serialization contract
    assert hasattr(config, 'to_dict')
    dict_result = config.to_dict()
    assert isinstance(dict_result, dict)
    assert 'config_id' in dict_result
    assert 'name' in dict_result
    assert 'settings' in dict_result

    # Test deserialization contract
    assert hasattr(Configuration, 'from_dict')
    recreated = Configuration.from_dict(dict_result)
    assert isinstance(recreated, Configuration)
    assert recreated.config_id == config.config_id
    assert recreated.name == config.name

def test_crawler_session_contract():
    """Test CrawlerSession class maintains its contract."""
    from core.crawler import CrawlerSession
    from core.config import Configuration

    config = Configuration(
        name="Test Config",
        settings={"max_depth": 5, "timeout": 60, "platform": "android"}
    )

    # Test constructor contract
    session = CrawlerSession(config, "test-session-id")

    # Verify attributes exist and have correct types
    assert hasattr(session, 'session_id')
    assert hasattr(session, 'config_id')
    assert hasattr(session, 'status')
    assert hasattr(session, 'progress')
    assert hasattr(session, 'start_time')
    assert hasattr(session, 'end_time')
    assert hasattr(session, 'results')
    assert hasattr(session, 'error_message')

    assert isinstance(session.session_id, str)
    assert isinstance(session.config_id, str)
    assert isinstance(session.status, str)
    assert isinstance(session.progress, float)
    assert isinstance(session.results, list)

    assert session.session_id == "test-session-id"
    assert session.config_id == config.config_id
    assert session.status == "pending"
    assert session.progress == 0.0

    # Test validation contract
    assert hasattr(session, 'validate')
    session.validate()  # Should not raise

    # Test state transition contract
    assert hasattr(session, 'start')
    assert hasattr(session, 'complete')
    assert hasattr(session, 'fail')
    assert hasattr(session, 'stop')

    # Test state transitions
    session.start()
    assert session.status == "running"
    assert session.start_time is not None

    session.complete()
    assert session.status == "completed"
    assert session.end_time is not None

def test_parsed_data_contract():
    """Test ParsedData class maintains its contract."""
    from core.parser import ParsedData

    # Test constructor contract
    data = ParsedData(
        session_id="test-session",
        element_type="button",
        identifier="test-button",
        bounding_box={"top_left": [10, 20], "bottom_right": [30, 40]},
        properties={"text": "Click me"},
        confidence_score=0.95
    )

    # Verify attributes exist and have correct types
    assert hasattr(data, 'data_id')
    assert hasattr(data, 'session_id')
    assert hasattr(data, 'element_type')
    assert hasattr(data, 'identifier')
    assert hasattr(data, 'bounding_box')
    assert hasattr(data, 'properties')
    assert hasattr(data, 'confidence_score')
    assert hasattr(data, 'timestamp')

    assert isinstance(data.data_id, str)
    assert isinstance(data.session_id, str)
    assert isinstance(data.element_type, str)
    assert isinstance(data.identifier, str)
    assert isinstance(data.bounding_box, dict)
    assert isinstance(data.properties, dict)
    assert isinstance(data.confidence_score, float)

    assert data.session_id == "test-session"
    assert data.element_type == "button"
    assert data.identifier == "test-button"
    assert data.confidence_score == 0.95

    # Test validation contract
    assert hasattr(data, 'validate')
    data.validate()  # Should not raise

def test_storage_contract():
    """Test Storage class maintains its contract."""
    from core.storage import Storage
    from core.config import Configuration
    import tempfile
    import os
    import time

    # Create temp database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()

    storage = None
    try:
        storage = Storage(temp_db_path)

        # Verify constructor contract
        assert hasattr(storage, 'db_path')
        assert storage.db_path == temp_db_path

        # Test configuration operations contract
        config = Configuration(
            name="Test Config",
            settings={"max_depth": 5, "timeout": 60, "platform": "android"}
        )

        assert hasattr(storage, 'save_configuration')
        storage.save_configuration(config)

        assert hasattr(storage, 'get_configuration')
        retrieved = storage.get_configuration(config.config_id)
        assert retrieved is not None
        assert retrieved.config_id == config.config_id

        # Test session operations contract
        session = CrawlerSession(config, "test-session")

        assert hasattr(storage, 'save_session')
        storage.save_session(session)

        # Test parsed data operations contract
        parsed_data = ParsedData(
            session_id="test-session",
            element_type="button",
            identifier="test-button",
            bounding_box={"top_left": [10, 20], "bottom_right": [30, 40]}
        )

        assert hasattr(storage, 'save_parsed_data')
        storage.save_parsed_data([parsed_data])

        assert hasattr(storage, 'get_session_results')
        results = storage.get_session_results("test-session")
        assert isinstance(results, list)

    finally:
        if storage:
            del storage
        time.sleep(0.1)
        try:
            os.unlink(temp_db_path)
        except OSError:
            pass

def test_crawler_contract():
    """Test Crawler class maintains its contract."""
    from core.crawler import Crawler
    from core.config import Configuration

    config = Configuration(
        name="Test Config",
        settings={"max_depth": 5, "timeout": 60, "platform": "android"}
    )

    # Test constructor contract
    crawler = Crawler(config)

    assert hasattr(crawler, 'config')
    assert crawler.config == config

    # Test session operations contract
    assert hasattr(crawler, 'start_session')
    session = crawler.start_session()
    assert session is not None

    assert hasattr(crawler, 'get_status')
    status = crawler.get_status(session.session_id)
    assert status is not None

    assert hasattr(crawler, 'stop_session')
    stopped = crawler.stop_session(session.session_id)
    assert stopped is not None

    # Missing sessions should now raise an error instead of being recreated
    with pytest.raises(ValueError):
        crawler.get_status("missing-session")

def test_parser_contract():
    """Test parser module maintains its contract."""
    from core.parser import parse_raw_data

    # Test function contract
    assert callable(parse_raw_data)

    result = parse_raw_data({})
    assert isinstance(result, list)

    # Test with sample data
    sample_data = {
        "elements": [
            {
                "type": "button",
                "id": "test-btn",
                "bounds": {"top_left": [0, 0], "bottom_right": [100, 50]}
            }
        ]
    }

    result = parse_raw_data(sample_data)
    assert isinstance(result, list)

def test_core_module_imports_contract():
    """Test that all core modules can be imported and have expected exports."""
    # Test config module
    import core
    assert hasattr(core, 'config')
    from core import config
    assert hasattr(config, 'Configuration')

    # Test storage module
    assert hasattr(core, 'storage')
    from core import storage
    assert hasattr(storage, 'Storage')

    # Test crawler module
    assert hasattr(core, 'crawler')
    from core import crawler
    assert hasattr(crawler, 'Crawler')
    assert hasattr(crawler, 'CrawlerSession')

    # Test parser module
    assert hasattr(core, 'parser')
    from core import parser
    assert hasattr(parser, 'ParsedData')
    assert hasattr(parser, 'parse_raw_data')

def test_error_handling_contract():
    """Test that error handling maintains contract across core modules."""
    from core.config import Configuration
    from core.parser import ParsedData

    # Test Configuration error contract
    config = Configuration(
        name="",  # Invalid
        settings={"max_depth": 5, "timeout": 60, "platform": "android"}
    )

    with pytest.raises(ValueError):
        config.validate()

    # Test ParsedData error contract
    data = ParsedData(
        session_id="test",
        element_type="invalid",  # Invalid type
        identifier="test",
        bounding_box={"top_left": [10, 20], "bottom_right": [30, 40]}
    )

    with pytest.raises(ValueError):
        data.validate()

