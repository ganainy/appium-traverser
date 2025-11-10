#!/usr/bin/env python3
"""
Focus area service for managing privacy focus areas.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, UTC

from cli.constants import keys as KEYS
from cli.constants import messages as MSG
from cli.shared.context import CLIContext

_MAX_FOCUS_AREAS = 10

class FocusAreaService:
    """Service for managing privacy focus areas using UserConfigStore."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.config = context.config
        self.logger = logging.getLogger(__name__)
        # Get UserConfigStore from config
        self._user_store = self.config._user_store
    
    def get_focus_areas(self) -> List[Dict]:
        """Get current focus areas from storage.
        
        Returns:
            List of focus area dictionaries
        """
        try:
            areas = self._user_store.get_focus_areas_full()
            return areas if isinstance(areas, list) else []
        except Exception as e:
            self.logger.error(f"Failed to load focus areas from storage: {e}")
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
                area_name = area.get(KEYS.FOCUS_AREA_NAME, "") or area.get(KEYS.FOCUS_AREA_TITLE, "")
                if name_lower == area_name.lower():
                    return i
        return None
    
    def set_focus_area_enabled(self, id_or_name: str, enabled: bool) -> Tuple[bool, Optional[str]]:
        """Enable or disable a focus area.
        
        Note: Current implementation doesn't support enable/disable, so this returns a message
        indicating that all focus areas are always enabled.
        
        Args:
            id_or_name: Focus area ID or name
            enabled: Whether to enable the focus area
            
        Returns:
            Tuple of (success, message)
        """
        # Current implementation doesn't support enable/disable functionality
        # All focus areas are always "enabled"
        success_msg = MSG.FOCUS_AREA_SET_ENABLED.format(
            name=id_or_name,
            enabled=True
        )
        return True, success_msg
    
    def move_focus_area(self, from_index_str: str, to_index_str: str) -> Tuple[bool, Optional[str]]:
        """Reorder focus areas.
        
        Note: Current implementation doesn't support reordering, so this returns a message
        indicating that focus areas maintain their creation order.
        
        Args:
            from_index_str: Source index (1-based)
            to_index_str: Target index (1-based)
            
        Returns:
            Tuple of (success, message)
        """
        # Current implementation doesn't support reordering
        # Focus areas are returned in creation order
        error_msg = "Current implementation doesn't support reordering focus areas. They maintain creation order."
        self.logger.warning(error_msg)
        return False, error_msg
    
    def add_focus_area(
        self,
        title: str,
        description: str = "",
        priority: int = KEYS.DEFAULT_FOCUS_PRIORITY,
        enabled: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Add a new focus area.
        
        Args:
            title: Focus area title
            description: Focus area description
            priority: Focus area priority (ignored in current implementation)
            enabled: Whether the focus area is enabled (ignored in current implementation)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            areas = self.get_focus_areas()
            if len(areas) >= _MAX_FOCUS_AREAS:
                error_msg = f"Maximum of {_MAX_FOCUS_AREAS} focus areas allowed."
                return False, error_msg
            
            # Use UserConfigStore to add focus area
            self._user_store.add_focus_area_full(title, description)
            success_msg = MSG.FOCUS_AREA_ADDED.format(title=title)
            return True, success_msg
        except ValueError as e:
            # Handle validation errors
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = MSG.ERROR_ADDING_FOCUS_AREA.format(error=e)
            self.logger.error(f"Failed to add focus area: {e}")
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
            priority: New priority (ignored in current implementation)
            enabled: New enabled state (ignored in current implementation)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Convert id_or_name to integer ID
            area_id = int(id_or_name) if id_or_name.isdigit() else None
            if area_id is None:
                # Try to find by name
                areas = self.get_focus_areas()
                for area in areas:
                    area_name = area.get(KEYS.FOCUS_AREA_NAME, "") or area.get(KEYS.FOCUS_AREA_TITLE, "")
                    if area_name.lower() == id_or_name.lower():
                        area_id = area.get('id')
                        break
                
                if area_id is None:
                    error_msg = MSG.FOCUS_AREA_NOT_FOUND.format(id_or_name=id_or_name)
                    return False, error_msg
            
            # Use UserConfigStore to update focus area
            self._user_store.update_focus_area_full(area_id, title, description)
            success_msg = MSG.FOCUS_AREA_UPDATED.format(name=title or id_or_name)
            return True, success_msg
        except ValueError as e:
            # Handle validation errors
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = MSG.ERROR_UPDATING_FOCUS_AREA.format(error=e)
            self.logger.error(f"Failed to update focus area: {e}")
            return False, error_msg
    
    def remove_focus_area(self, id_or_name: str) -> Tuple[bool, Optional[str]]:
        """Remove a focus area.
        
        Args:
            id_or_name: Focus area ID or name
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Convert id_or_name to integer ID
            area_id = int(id_or_name) if id_or_name.isdigit() else None
            if area_id is None:
                # Try to find by name
                areas = self.get_focus_areas()
                for area in areas:
                    area_name = area.get(KEYS.FOCUS_AREA_NAME, "") or area.get(KEYS.FOCUS_AREA_TITLE, "")
                    if area_name.lower() == id_or_name.lower():
                        area_id = area.get('id')
                        break
                
                if area_id is None:
                    error_msg = MSG.FOCUS_AREA_NOT_FOUND.format(id_or_name=id_or_name)
                    return False, error_msg
            
            # Use UserConfigStore to remove focus area
            self._user_store.remove_focus_area_full(area_id)
            success_msg = MSG.FOCUS_AREA_REMOVED.format(name=id_or_name)
            return True, success_msg
        except ValueError as e:
            # Handle validation errors
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = MSG.ERROR_REMOVING_FOCUS_AREA.format(error=e)
            self.logger.error(f"Failed to remove focus area: {e}")
            return False, error_msg
