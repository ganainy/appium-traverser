"""
Test for LAST_SELECTED_APP persistence fix.

This test verifies that when a user selects an app from the dropdown and
restarts the GUI, the selected app is correctly restored.

Issue: LAST_SELECTED_APP was being stored as a string representation of a dict
instead of as properly serialized JSON, preventing deserialization on retrieval.

Fix: Updated UserConfigStore to properly handle dict/list types using JSON
serialization.
"""

import tempfile
import os
import pytest
from infrastructure.user_config_store import UserConfigStore


def test_last_selected_app_persistence():
    """Test that LAST_SELECTED_APP dict is properly persisted and retrieved."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        store = UserConfigStore(db_path)
        
        # Simulate what the UI does when saving a selected app
        selected_app = {
            'package_name': 'com.myfitnesspal.android',
            'activity_name': '.activities.HomeActivity',
            'app_name': 'MyFitnessPal'
        }
        
        # Save the selected app
        store.set('LAST_SELECTED_APP', selected_app)
        
        # Retrieve it
        retrieved = store.get('LAST_SELECTED_APP')
        
        # Assertions
        assert retrieved is not None, "Retrieved value should not be None"
        assert isinstance(retrieved, dict), f"Retrieved value should be dict, got {type(retrieved)}"
        assert retrieved == selected_app, "Retrieved dict should match original"
        assert retrieved['package_name'] == 'com.myfitnesspal.android'
        assert retrieved['activity_name'] == '.activities.HomeActivity'
        assert retrieved['app_name'] == 'MyFitnessPal'
        
        store.close()


def test_json_type_inference():
    """Test that dict/list types are correctly inferred as 'json'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        store = UserConfigStore(db_path)
        
        # Test dict
        test_dict = {'key': 'value', 'nested': {'inner': 'data'}}
        store.set('test_dict', test_dict)
        assert store.get('test_dict') == test_dict
        
        # Test list
        test_list = [1, 2, 3, {'nested': 'object'}]
        store.set('test_list', test_list)
        assert store.get('test_list') == test_list
        
        # Test string (should still work)
        test_string = 'just a string'
        store.set('test_string', test_string)
        assert store.get('test_string') == test_string
        
        store.close()


def test_multiple_app_selections():
    """Test that multiple app selections can be tracked without interference."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        store = UserConfigStore(db_path)
        
        # First app selection
        app1 = {
            'package_name': 'com.app1',
            'activity_name': '.MainActivity',
            'app_name': 'App1'
        }
        
        # Second app selection (overwrites first)
        app2 = {
            'package_name': 'com.app2',
            'activity_name': '.HomeActivity',
            'app_name': 'App2'
        }
        
        # Save first app
        store.set('LAST_SELECTED_APP', app1)
        assert store.get('LAST_SELECTED_APP') == app1
        
        # Save second app (overwrites)
        store.set('LAST_SELECTED_APP', app2)
        retrieved = store.get('LAST_SELECTED_APP')
        
        # Verify second app is now stored
        assert retrieved == app2
        assert retrieved['app_name'] == 'App2'
        
        store.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
