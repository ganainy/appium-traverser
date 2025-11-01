import os
import json
import tempfile
import shutil
import sqlite3
import pytest
from traverser_ai_api.core.user_storage import UserConfigStore
from traverser_ai_api.migrations.migrate_to_sqlite import migrate_user_config_json_to_sqlite

def create_sample_user_config(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)

def test_migration_script_migrates_preferences(tmp_path):
    # Setup: create a sample user_config.json
    sample_data = {
        "max_tokens": 1234,
        "temperature": 0.55,
        "enable_image_context": False,
        "focus_areas": ["nav", "content"],
        "openai_api_key": "sk-should-not-migrate"
    }
    user_config_path = tmp_path / "user_config.json"
    create_sample_user_config(user_config_path, sample_data)

    # Patch the migration script to use our temp user_config.json
    store = UserConfigStore(db_path=str(tmp_path / "config.db"))
    result = migrate_user_config_json_to_sqlite(store, json_path=str(user_config_path))
    # Check migration result
    assert result['migrated_count'] >= 3  # max_tokens, temperature, enable_image_context
    assert "openai_api_key" in result['skipped_secrets']
    # Check that focus areas were migrated
    focus_areas = store.get_focus_areas()
    assert any(fa['area'] == "nav" for fa in focus_areas)
    assert any(fa['area'] == "content" for fa in focus_areas)
    # Check that values are in SQLite
    assert store.get("max_tokens") == 1234
    assert store.get("temperature") == 0.55
    assert store.get("enable_image_context") is False
    # Check backup file exists
    assert os.path.exists(str(tmp_path / "user_config.json.bak"))

def test_migration_script_idempotent(tmp_path):
    sample_data = {"foo": "bar"}
    user_config_path = tmp_path / "user_config.json"
    with open(user_config_path, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f)
    store = UserConfigStore(db_path=str(tmp_path / "config.db"))
    from traverser_ai_api.migrations.migrate_to_sqlite import migrate_user_config_json_to_sqlite
    migrate_user_config_json_to_sqlite(store, json_path=str(user_config_path))
    # Run again, should not error or duplicate
    migrate_user_config_json_to_sqlite(store, json_path=str(user_config_path))
    assert store.get("foo") == "bar"
