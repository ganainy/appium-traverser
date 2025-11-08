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

        # Test get_session_results contract (returns empty list for now)
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


def test_error_handling_contract():
    """Test that error handling maintains contract across core modules."""
    from core.config import Configuration

    # Test Configuration error contract
    config = Configuration(
        name="",  # Invalid
        settings={"max_depth": 5, "timeout": 60, "platform": "android"}
    )

    with pytest.raises(ValueError):
        config.validate()

