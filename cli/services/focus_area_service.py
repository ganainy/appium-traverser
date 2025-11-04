#!/usr/bin/env python3
"""
Focus area service for managing privacy focus areas.
"""

import logging
import os
import json
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime, UTC

from cli.constants import keys as KEYS
from cli.constants import config as CONFIG
from cli.constants import messages as MSG
from cli.shared.context import CLIContext

# Storage backend: JSON file (can be replaced with SQLite if needed)
_DEFAULT_STORAGE_FILENAME = 'focus_areas.json'
_MAX_FOCUS_AREAS = 10
_STORAGE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'core', _DEFAULT_STORAGE_FILENAME)

# In-memory storage and threading
_focus_areas = []
_focus_areas_lock = threading.Lock()
_data_loaded = False

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
        self.created_at = datetime.fromisoformat(created_at) if created_at else datetime.now(UTC)
        self.updated_at = datetime.fromisoformat(updated_at) if updated_at else datetime.now(UTC)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

# CRUD API

def get_focus_areas() -> List[dict]:
    """Return all focus areas persisted on disk."""
    with _focus_areas_lock:
        global _data_loaded
        if not _data_loaded:
            _load_focus_areas()
            _data_loaded = True
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
        global _data_loaded
        if not _data_loaded:
            _load_focus_areas()
            _data_loaded = True
        if len(_focus_areas) >= _MAX_FOCUS_AREAS:
            raise ValueError(f"Maximum of {_MAX_FOCUS_AREAS} focus areas allowed.")
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
        global _data_loaded
        if not _data_loaded:
            _load_focus_areas()
            _data_loaded = True
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
        global _data_loaded
        if not _data_loaded:
            _load_focus_areas()
            _data_loaded = True
        fa = next((fa for fa in _focus_areas if fa.id == id), None)
        if fa is None:
            raise ValueError("Focus area not found.")
        if name and name != fa.name and any(other.name == name for other in _focus_areas):
            raise ValueError("Focus area name must be unique.")
        if name:
            fa.name = name
        if description is not None:
            fa.description = description
        fa.updated_at = datetime.now(UTC)
        _save_focus_areas()
        return fa.to_dict()

class FocusAreaService:
    """Service for managing privacy focus areas."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def get_focus_areas(self) -> List[Dict]:
        """Get current focus areas from core storage.
        
        Returns:
            List of focus area dictionaries
        """
        try:
            # Use core implementation instead of database
            areas = get_focus_areas()
            return areas if isinstance(areas, list) else []
        except Exception as e:
            self.logger.error(f"Failed to load focus areas from core storage: {e}")
            return []
    
    def _find_focus_area_index(self, id_or_name: str) -> Optional[int]:
        """Find focus area index by ID or name.
        
        Args:
            id_or_name: Focus area ID or name
            
        Returns:
            Index of focus area or None if not found
        """
        areas = self.get_focus_areas()
        try:
            idx = int(id_or_name) - 1
            if 0 <= idx < len(areas):
                return idx
        except ValueError:
            name_lower = id_or_name.strip().lower()
            for i, area in enumerate(areas):
                if name_lower in (
                    str(area.get(KEYS.FOCUS_AREA_TITLE, "")).lower()
                    or str(area.get(KEYS.FOCUS_AREA_NAME, "")).lower()
                ):
                    return i
        return None
    
    def set_focus_area_enabled(self, id_or_name: str, enabled: bool) -> Tuple[bool, Optional[str]]:
        """Enable or disable a focus area.
        
        Note: Core implementation doesn't support enable/disable, so this returns a message
        indicating that all focus areas are always enabled.
        
        Args:
            id_or_name: Focus area ID or name
            enabled: Whether to enable the focus area
            
        Returns:
            Tuple of (success, message)
        """
        # Core implementation doesn't support enable/disable functionality
        # All focus areas are always "enabled" in the core implementation
        success_msg = MSG.FOCUS_AREA_SET_ENABLED.format(
            name=id_or_name,
            enabled=True  # Core implementation always has areas enabled
        )
        return True, success_msg
    
    def move_focus_area(self, from_index_str: str, to_index_str: str) -> Tuple[bool, Optional[str]]:
        """Reorder focus areas.
        
        Note: Core implementation doesn't support reordering, so this returns a message
        indicating that focus areas maintain their creation order.
        
        Args:
            from_index_str: Source index (1-based)
            to_index_str: Target index (1-based)
            
        Returns:
            Tuple of (success, message)
        """
        # Core implementation doesn't support reordering
        # Focus areas are returned in creation order
        error_msg = "Core implementation doesn't support reordering focus areas. They maintain creation order."
        self.logger.warning(error_msg)
        return False, error_msg
    
    def add_focus_area(
        self,
        title: str,
        description: str = "",
        priority: int = CONFIG.DEFAULT_FOCUS_PRIORITY,
        enabled: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Add a new focus area.
        
        Args:
            title: Focus area title
            description: Focus area description
            priority: Focus area priority (ignored in core implementation)
            enabled: Whether the focus area is enabled (ignored in core implementation)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Use core implementation
            add_focus_area(title, description)
            success_msg = MSG.FOCUS_AREA_ADDED.format(title=title)
            return True, success_msg
        except ValueError as e:
            # Handle validation errors from core implementation
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = MSG.ERROR_ADDING_FOCUS_AREA.format(error=e)
            return False, error_msg
    
    def edit_focus_area(
        self,
        id_or_name: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        enabled: Optional[bool] = None
    ) -> Tuple[bool, Optional[str]]:
        """Edit an existing focus area.
        
        Args:
            id_or_name: Focus area ID or name
            title: New title (optional)
            description: New description (optional)
            priority: New priority (ignored in core implementation)
            enabled: New enabled state (ignored in core implementation)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Convert id_or_name to integer ID for core implementation
            area_id = int(id_or_name) if id_or_name.isdigit() else None
            if area_id is None:
                # Try to find by name
                areas = self.get_focus_areas()
                for area in areas:
                    if area.get('name', '').lower() == id_or_name.lower():
                        area_id = area.get('id')
                        break
                
                if area_id is None:
                    error_msg = MSG.FOCUS_AREA_NOT_FOUND.format(id_or_name=id_or_name)
                    return False, error_msg
            
            # Use core implementation
            update_focus_area(area_id, title, description)
            success_msg = MSG.FOCUS_AREA_UPDATED.format(name=title or id_or_name)
            return True, success_msg
        except ValueError as e:
            # Handle validation errors from core implementation
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = MSG.ERROR_UPDATING_FOCUS_AREA.format(error=e)
            return False, error_msg
    
    def remove_focus_area(self, id_or_name: str) -> Tuple[bool, Optional[str]]:
        """Remove a focus area.
        
        Args:
            id_or_name: Focus area ID or name
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Convert id_or_name to integer ID for core implementation
            area_id = int(id_or_name) if id_or_name.isdigit() else None
            if area_id is None:
                # Try to find by name
                areas = self.get_focus_areas()
                for area in areas:
                    if area.get('name', '').lower() == id_or_name.lower():
                        area_id = area.get('id')
                        break
                
                if area_id is None:
                    error_msg = MSG.FOCUS_AREA_NOT_FOUND.format(id_or_name=id_or_name)
                    return False, error_msg
            
            # Use core implementation
            remove_focus_area(area_id)
            success_msg = MSG.FOCUS_AREA_REMOVED.format(name=id_or_name)
            return True, success_msg
        except ValueError as e:
            # Handle validation errors from core implementation
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = MSG.ERROR_REMOVING_FOCUS_AREA.format(error=e)
            return False, error_msg
