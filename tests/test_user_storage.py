"""
This test module verifies the behavior of the `UserConfigStore` class for user configuration persistence. It checks:
- Setting and retrieving string, int, float, and boolean values.
- CRUD operations for user focus areas.
- That duplicate focus areas raise errors.
"""
import os
import tempfile
import sqlite3
import pytest
from infrastructure.user_config_store import UserConfigStore

def test_set_and_get_string():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        store = UserConfigStore(db_path)
        store.set("username", "alice")
        assert store.get("username") == "alice"
        assert store.get("nonexistent", "default") == "default"
        store.close()

def test_set_and_get_int():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        store = UserConfigStore(db_path)
        store.set("age", 42)
        assert store.get("age") == 42
        store.close()

def test_set_and_get_float():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        store = UserConfigStore(db_path)
        store.set("score", 3.14)
        assert store.get("score") == pytest.approx(3.14)
        store.close()

def test_set_and_get_bool():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        store = UserConfigStore(db_path)
        store.set("is_active", True)
        assert store.get("is_active") is True
        store.set("is_active", False)
        assert store.get("is_active") is False
        store.close()

def test_focus_area_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        store = UserConfigStore(db_path)
        # Add
        store.add_focus_area("Login")
        areas = store.get_focus_areas()
        assert any(a["area"] == "Login" for a in areas)
        # Remove
        store.remove_focus_area("Login")
        areas = store.get_focus_areas()
        assert not any(a["area"] == "Login" for a in areas)
        store.close()

def test_add_duplicate_focus_area_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        store = UserConfigStore(db_path)
        store.add_focus_area("Settings")
        with pytest.raises(ValueError):
            store.add_focus_area("Settings")
        store.close()
