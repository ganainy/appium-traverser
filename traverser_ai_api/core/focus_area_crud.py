"""
Shared CRUD logic for Focus Areas.
Used by both CLI and GUI interfaces.

Usage examples:
    from traverser_ai_api.core.focus_area_crud import add_focus_area, list_focus_areas
    add_focus_area('My Area', 'Description')
    all_areas = list_focus_areas()
    update_focus_area(1, name='New Name')
    remove_focus_area(1)
"""
from typing import List, Optional
from datetime import datetime
import threading


# Storage backend: JSON file (can be replaced with SQLite if needed)
import os
import json

_focus_areas = []
_focus_areas_lock = threading.Lock()
_STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'focus_areas.json')

def _load_focus_areas():
    global _focus_areas
    if os.path.exists(_STORAGE_PATH):
        with open(_STORAGE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            _focus_areas = [FocusArea(**fa) for fa in data]
    else:
        _focus_areas = []

def _save_focus_areas():
    with open(_STORAGE_PATH, 'w', encoding='utf-8') as f:
        json.dump([fa.to_dict() for fa in _focus_areas], f, indent=2)


class FocusArea:
    """
    Data model for a Focus Area.
    Fields:
        id (int): Unique identifier
        name (str): Name (unique, required)
        description (str): Optional description
        created_at (datetime): Creation timestamp
        updated_at (datetime): Last update timestamp
    """
    def __init__(self, id: int, name: str, description: Optional[str] = None, created_at: Optional[str] = None, updated_at: Optional[str] = None):
        self.id = id
        self.name = name
        self.description = description or ""
        self.created_at = datetime.fromisoformat(created_at) if created_at else datetime.utcnow()
        self.updated_at = datetime.fromisoformat(updated_at) if updated_at else datetime.utcnow()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

# CRUD API


def list_focus_areas() -> List[dict]:
    """
    List all focus areas.
    Returns:
        List of dicts representing focus areas.
    """
    with _focus_areas_lock:
        _load_focus_areas()
        return [fa.to_dict() for fa in _focus_areas]


def add_focus_area(name: str, description: Optional[str] = None) -> dict:
    """
    Add a new focus area.
    Args:
        name: Name of the focus area (must be unique)
        description: Optional description
    Returns:
        Dict representing the new focus area.
    Raises:
        ValueError if name is not unique or max areas reached.
    """
    with _focus_areas_lock:
        _load_focus_areas()
        if len(_focus_areas) >= 10:
            raise ValueError("Maximum of 10 focus areas allowed.")
        if any(fa.name == name for fa in _focus_areas):
            raise ValueError("Focus area name must be unique.")
        new_id = max([fa.id for fa in _focus_areas], default=0) + 1
        fa = FocusArea(new_id, name, description)
        _focus_areas.append(fa)
        _save_focus_areas()
        return fa.to_dict()


def remove_focus_area(id: int) -> None:
    """
    Remove a focus area by id.
    Args:
        id: Focus area id
    Raises:
        ValueError if not found.
    """
    with _focus_areas_lock:
        _load_focus_areas()
        idx = next((i for i, fa in enumerate(_focus_areas) if fa.id == id), None)
        if idx is None:
            raise ValueError("Focus area not found.")
        del _focus_areas[idx]
        _save_focus_areas()


def update_focus_area(id: int, name: Optional[str] = None, description: Optional[str] = None) -> dict:
    """
    Update a focus area by id.
    Args:
        id: Focus area id
        name: New name (optional, must be unique if provided)
        description: New description (optional)
    Returns:
        Dict representing the updated focus area.
    Raises:
        ValueError if not found or name not unique.
    """
    with _focus_areas_lock:
        _load_focus_areas()
        fa = next((fa for fa in _focus_areas if fa.id == id), None)
        if fa is None:
            raise ValueError("Focus area not found.")
        if name and name != fa.name and any(other.name == name for other in _focus_areas):
            raise ValueError("Focus area name must be unique.")
        if name:
            fa.name = name
        if description is not None:
            fa.description = description
        fa.updated_at = datetime.utcnow()
        _save_focus_areas()
        return fa.to_dict()
