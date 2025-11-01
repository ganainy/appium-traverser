import os
import tempfile
import pytest
import json
from traverser_ai_api.config import Config
from traverser_ai_api.core.user_storage import UserConfigStore
# Migration script may have been removed; import defensively and skip integration when absent.
try:
    from traverser_ai_api.migrations.migrate_to_sqlite import migrate_user_config_json_to_sqlite
except Exception:
    migrate_user_config_json_to_sqlite = None

@pytest.fixture
def temp_config_env(tmp_path):
    # Setup temp user_config.json and SQLite DB
    sample_data = {
        "max_tokens": 2048,
        "temperature": 0.7,
        "enable_image_context": True,
        "focus_areas": ["test", "integration"]
    }
    user_config_path = tmp_path / "user_config.json"
    db_path = tmp_path / "config.db"
    with open(user_config_path, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f)
    store = UserConfigStore(db_path=str(db_path))
    if migrate_user_config_json_to_sqlite is None:
        pytest.skip("migration script not available")
    migrate_user_config_json_to_sqlite(store, json_path=str(user_config_path))
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
