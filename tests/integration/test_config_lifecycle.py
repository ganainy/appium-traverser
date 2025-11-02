import os
import tempfile
import pytest
import json
from traverser_ai_api.config import Config
from traverser_ai_api.core.user_storage import UserConfigStore

@pytest.fixture
def temp_config_env(tmp_path):
    # Setup SQLite DB with test data
    sample_data = {
        "max_tokens": 2048,
        "temperature": 0.7,
        "enable_image_context": True,
        "focus_areas": ["test", "integration"]
    }
    db_path = tmp_path / "config.db"
    store = UserConfigStore(db_path=str(db_path))
    for key, value in sample_data.items():
        if key == "focus_areas":
            for area in value:
                store.add_focus_area(area)
        else:
            store.set_config(key, value)
    yield str(db_path)

def test_config_lifecycle_integration(temp_config_env):
    db_path = temp_config_env
    config = Config()
    # Patch config to use temp DB
    config._user_store = UserConfigStore(db_path)
    # Validate config loads from SQLite
    assert config.get("max_tokens") == 2048
    assert config.get("temperature") == 0.7
    assert config.get("enable_image_context") is True
    # Update config and persist
    config.set("max_tokens", 4096)
    assert config.get("max_tokens") == 4096
    # Focus area CRUD
    config._user_store.add_focus_area("new_area")
    assert "new_area" in config.FOCUS_AREAS
    config._user_store.remove_focus_area("new_area")
    assert "new_area" not in config.FOCUS_AREAS
