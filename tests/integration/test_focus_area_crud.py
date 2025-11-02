import os
import pytest
from interfaces.cli import CLICrawlerInterface
from interfaces.gui import GUICrawlerInterface
from core import focus_area_crud

TEST_JSON = os.path.join(os.path.dirname(focus_area_crud.__file__), 'focus_areas.json')

def setup_function():
    if os.path.exists(TEST_JSON):
        os.remove(TEST_JSON)
    with focus_area_crud._focus_areas_lock:
        focus_area_crud._focus_areas = []

def teardown_function():
    if os.path.exists(TEST_JSON):
        os.remove(TEST_JSON)
    with focus_area_crud._focus_areas_lock:
        focus_area_crud._focus_areas = []

def test_cli_focus_area_crud():
    cli = CLICrawlerInterface()
    fa = cli.cli_add_focus_area('cli1', 'desc')
    assert fa is not None and fa['name'] == 'cli1'
    all_fa = cli.cli_list_focus_areas()
    assert any(f['name'] == 'cli1' for f in all_fa)
    updated = cli.cli_update_focus_area(fa['id'], name='cli1-upd', description='d2')
    assert updated is not None and updated['name'] == 'cli1-upd'
    removed = cli.cli_remove_focus_area(fa['id'])
    assert removed is True
    assert not cli.cli_list_focus_areas()

def test_gui_focus_area_crud():
    gui = GUICrawlerInterface()
    fa = gui.gui_add_focus_area('gui1', 'desc')
    assert fa is not None and fa['name'] == 'gui1'
    all_fa = gui.gui_list_focus_areas()
    assert any(f['name'] == 'gui1' for f in all_fa)
    updated = gui.gui_update_focus_area(fa['id'], name='gui1-upd', description='d2')
    assert updated is not None and updated['name'] == 'gui1-upd'
    removed = gui.gui_remove_focus_area(fa['id'])
    assert removed is True
    assert not gui.gui_list_focus_areas()
