"""
This test module verifies CRUD operations for focus areas in the core module. It checks:
- Adding, listing, updating, and removing focus areas.
- Enforcing unique names and maximum allowed focus areas.
- Proper cleanup before and after each test.
"""
import os
import tempfile
import pytest
from cli.services.focus_area_service import FocusAreaService
from cli.shared.context import CLIContext
from infrastructure.user_config_store import UserConfigStore
from config.config import Config


@pytest.fixture
def temp_config():
    """Create a temporary config with a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_config.db")
        user_store = UserConfigStore(db_path=db_path)
        config = Config()
        config._user_store = user_store
        context = CLIContext()
        context.config = config
        service = FocusAreaService(context)
        yield service, user_store
        user_store.close()


def setup_function():
    # Clean up before each test - no longer needed as we use temp databases
    pass


def teardown_function():
    # Clean up after each test - no longer needed as we use temp databases
    pass


def test_add_and_get_focus_area(temp_config):
    service, user_store = temp_config
    success, msg = service.add_focus_area('Test', 'desc')
    assert success is True
    areas = service.get_focus_areas()
    assert len(areas) == 1
    assert areas[0]['name'] == 'Test'
    assert areas[0]['description'] == 'desc'


def test_add_focus_area_unique_name(temp_config):
    service, user_store = temp_config
    success, msg = service.add_focus_area('A')
    assert success is True
    success, msg = service.add_focus_area('A')
    assert success is False
    assert 'unique' in msg.lower() or 'already' in msg.lower()


def test_max_focus_areas(temp_config):
    service, user_store = temp_config
    for i in range(10):
        success, msg = service.add_focus_area(f'fa{i}')
        assert success is True
    success, msg = service.add_focus_area('overflow')
    assert success is False
    assert 'maximum' in msg.lower() or 'max' in msg.lower()


def test_remove_focus_area(temp_config):
    service, user_store = temp_config
    success, msg = service.add_focus_area('ToRemove')
    assert success is True
    areas = service.get_focus_areas()
    area_id = areas[0]['id']
    success, msg = service.remove_focus_area(str(area_id))
    assert success is True
    assert service.get_focus_areas() == []


def test_update_focus_area(temp_config):
    service, user_store = temp_config
    success, msg = service.add_focus_area('ToUpdate', 'desc')
    assert success is True
    areas = service.get_focus_areas()
    area_id = areas[0]['id']
    success, msg = service.edit_focus_area(str(area_id), 'Updated', 'newdesc')
    assert success is True
    all_fa = service.get_focus_areas()
    assert all_fa[0]['name'] == 'Updated'
    assert all_fa[0]['description'] == 'newdesc'
