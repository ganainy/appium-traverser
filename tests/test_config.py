import os
import tempfile
import pytest
from traverser_ai_api.config import Config

def test_set_and_get_config_value():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch config to use a temp SQLite DB
        db_path = os.path.join(tmpdir, "test_config.db")
        config = Config()
        config._user_store = config._user_store.__class__(db_path)
        config.set("test_key", "test_value")
        assert config.get("test_key") == "test_value"
        assert config.get("nonexistent", "default") == "default"

def test_config_type_coercion():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        config = Config()
        config._user_store = config._user_store.__class__(db_path)
        config.set("int_key", 123)
        config.set("float_key", 3.14)
        config.set("bool_key", True)
        assert config.get("int_key") == 123
        assert config.get("float_key") == pytest.approx(3.14)
        assert config.get("bool_key") is True

def test_config_env_override(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        config = Config()
        config._user_store = config._user_store.__class__(db_path)
        monkeypatch.setenv("MY_ENV_KEY", "env_value")
        assert config.get("MY_ENV_KEY") == "env_value"

def test_config_default_fallback():
    config = Config()
    assert config.get("output_dir") == config._defaults.output_dir
