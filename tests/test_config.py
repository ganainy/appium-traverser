"""
This test module verifies the behavior of the `Config` class. It checks:
- Setting and retrieving configuration values, including type coercion.
- That environment variable overrides are respected.
- That default values are returned when keys are missing.
"""
import os
import tempfile
import pytest
from config.config import Config, LOG_LEVEL
from infrastructure.user_config_store import UserConfigStore

def test_set_and_get_config_value():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch config to use a temp SQLite DB
        db_path = os.path.join(tmpdir, "test_config.db")
        store = UserConfigStore(db_path)
        config = Config(user_store=store)
        config.set("test_key", "test_value")
        assert config.get("test_key") == "test_value"
        assert config.get("nonexistent", "default") == "default"
        store.close()

def test_config_type_coercion():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        store = UserConfigStore(db_path)
        config = Config(user_store=store)
        config.set("int_key", 123)
        config.set("float_key", 3.14)
        config.set("bool_key", True)
        assert config.get("int_key") == 123
        assert config.get("float_key") == pytest.approx(3.14)
        assert config.get("bool_key") is True
        store.close()

def test_config_env_override(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        store = UserConfigStore(db_path)
        config = Config(user_store=store)
        monkeypatch.setenv("MY_ENV_KEY", "env_value")
        assert config.get("MY_ENV_KEY") == "env_value"
        store.close()


def test_reset_settings_restores_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        store = UserConfigStore(db_path)
        config = Config(user_store=store)

        config.set("LOG_LEVEL", "DEBUG")
        assert config.get("LOG_LEVEL") == "DEBUG"

        config.reset_settings()

        assert config.get("LOG_LEVEL") == LOG_LEVEL
        store.close()
