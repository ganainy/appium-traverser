"""
This test module verifies CRUD operations for focus areas in the core module. It checks:
- Adding, listing, updating, and removing focus areas.
- Enforcing unique names and maximum allowed focus areas.
- Proper cleanup before and after each test.
"""
import os
import pytest
from cli.services import focus_area_service

TEST_JSON = os.path.join(os.path.dirname(focus_area_service.__file__), '..', '..', 'core', 'focus_areas.json')

def setup_function():
    # Clean up before each test
    if os.path.exists(TEST_JSON):
        os.remove(TEST_JSON)
    with focus_area_service._focus_areas_lock:
        focus_area_service._focus_areas = []

def teardown_function():
    # Clean up after each test
    if os.path.exists(TEST_JSON):
        os.remove(TEST_JSON)
    with focus_area_service._focus_areas_lock:
        focus_area_service._focus_areas = []

def test_add_and_get_focus_area():
    fa = focus_area_service.add_focus_area('Test', 'desc')
    assert fa['name'] == 'Test'
    all_fa = focus_area_service.get_focus_areas()
    assert len(all_fa) == 1
    assert all_fa[0]['name'] == 'Test'

def test_add_focus_area_unique_name():
    focus_area_service.add_focus_area('A')
    with pytest.raises(ValueError):
        focus_area_service.add_focus_area('A')

def test_max_focus_areas():
    for i in range(10):
        focus_area_service.add_focus_area(f'fa{i}')
    with pytest.raises(ValueError):
        focus_area_service.add_focus_area('overflow')

def test_remove_focus_area():
    fa = focus_area_service.add_focus_area('ToRemove')
    focus_area_service.remove_focus_area(fa['id'])
    assert focus_area_service.get_focus_areas() == []

def test_update_focus_area():
    fa = focus_area_service.add_focus_area('ToUpdate', 'desc')
    updated = focus_area_service.update_focus_area(fa['id'], name='Updated', description='newdesc')
    assert updated['name'] == 'Updated'
    assert updated['description'] == 'newdesc'
    all_fa = focus_area_service.get_focus_areas()
    assert all_fa[0]['name'] == 'Updated'
