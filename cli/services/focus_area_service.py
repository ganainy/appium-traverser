#!/usr/bin/env python3
"""
Focus area service for managing privacy focus areas.
"""

import logging
from typing import Dict, List, Optional, Tuple

from cli.constants import keys as KEYS
from cli.constants import config as CONFIG
from cli.constants import messages as MSG
from cli.shared.context import CLIContext
from cli.shared.service_names import DATABASE_SERVICE


class FocusAreaService:
    """Service for managing privacy focus areas."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def get_focus_areas(self) -> List[Dict]:
        """Get current focus areas from database.
        
        Returns:
            List of focus area dictionaries
        """
        try:
            db_service = self.context.services.get(DATABASE_SERVICE)
            if not db_service:
                self.logger.error(MSG.DATABASE_SERVICE_NOT_AVAILABLE)
                return []
            
            # Query focus areas from database
            areas = db_service.query_focus_areas()
            return areas if isinstance(areas, list) else []
        except Exception as e:
            self.logger.error(f"Failed to load focus areas from database: {e}")
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
        
        Args:
            id_or_name: Focus area ID or name
            enabled: Whether to enable the focus area
            
        Returns:
            Tuple of (success, message)
        """
        areas = self.get_focus_areas()
        idx = self._find_focus_area_index(id_or_name)
        
        if idx is None:
            error_msg = MSG.FOCUS_AREA_NOT_FOUND.format(id_or_name=id_or_name)
            self.logger.error(error_msg)
            return False, error_msg
        
        area_id = areas[idx].get(KEYS.FOCUS_AREA_ID)
        
        try:
            db_service = self.context.services.get(DATABASE_SERVICE)
            if db_service:
                db_service.update_focus_area_enabled(area_id, enabled)
                success_msg = MSG.FOCUS_AREA_SET_ENABLED.format(
                    name=areas[idx].get(KEYS.FOCUS_AREA_NAME, id_or_name),
                    enabled=enabled
                )
                return True, success_msg
            else:
                error_msg = MSG.DATABASE_SERVICE_NOT_AVAILABLE
                self.logger.error(error_msg)
                return False, error_msg
        except Exception as e:
            error_msg = MSG.FAILED_TO_UPDATE_FOCUS_AREA.format(error=e)
            self.logger.error(error_msg)
            return False, error_msg
    
    def move_focus_area(self, from_index_str: str, to_index_str: str) -> Tuple[bool, Optional[str]]:
        """Reorder focus areas.
        
        Args:
            from_index_str: Source index (1-based)
            to_index_str: Target index (1-based)
            
        Returns:
            Tuple of (success, message)
        """
        areas = self.get_focus_areas()
        try:
            from_idx = int(from_index_str) - 1
            to_idx = int(to_index_str) - 1
        except ValueError:
            error_msg = MSG.INDEXES_MUST_BE_INTEGERS
            self.logger.error(error_msg)
            return False, error_msg
        
        if not (0 <= from_idx < len(areas)) or not (0 <= to_idx < len(areas)):
            error_msg = MSG.INDEX_OUT_OF_RANGE
            self.logger.error(error_msg)
            return False, error_msg
        
        item = areas.pop(from_idx)
        areas.insert(to_idx, item)
        
        try:
            db_service = self.context.services.get(DATABASE_SERVICE)
            if db_service:
                # Update priorities in database
                for i, area in enumerate(areas):
                    db_service.update_focus_area_priority(area.get(KEYS.FOCUS_AREA_ID), i)
                success_msg = MSG.FOCUS_AREA_MOVED.format(position=to_idx+1)
                return True, success_msg
            else:
                error_msg = MSG.DATABASE_SERVICE_NOT_AVAILABLE
                self.logger.error(error_msg)
                return False, error_msg
        except Exception as e:
            error_msg = MSG.FAILED_TO_REORDER_FOCUS_AREAS.format(error=e)
            self.logger.error(error_msg)
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
            priority: Focus area priority
            enabled: Whether the focus area is enabled
            
        Returns:
            Tuple of (success, message)
        """
        areas = self.get_focus_areas()
        
        # Check for duplicate title
        for area in areas:
            if area.get(KEYS.FOCUS_AREA_NAME, "").lower() == title.lower():
                error_msg = MSG.FOCUS_AREA_ALREADY_EXISTS.format(title=title)
                return False, error_msg
        
        try:
            db_service = self.context.services.get(DATABASE_SERVICE)
            if db_service:
                db_service.create_focus_area(
                    name=title,
                    description=description,
                    priority=priority,
                    enabled=enabled
                )
                success_msg = MSG.FOCUS_AREA_ADDED.format(title=title)
                return True, success_msg
            else:
                error_msg = MSG.DATABASE_SERVICE_NOT_AVAILABLE
                self.logger.error(error_msg)
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
            priority: New priority (optional)
            enabled: New enabled state (optional)
            
        Returns:
            Tuple of (success, message)
        """
        areas = self.get_focus_areas()
        idx = self._find_focus_area_index(id_or_name)
        
        if idx is None:
            error_msg = MSG.FOCUS_AREA_NOT_FOUND.format(id_or_name=id_or_name)
            return False, error_msg
        
        area = areas[idx]
        area_id = area.get(KEYS.FOCUS_AREA_ID)
        
        try:
            db_service = self.context.services.get(DATABASE_SERVICE)
            if db_service:
                db_service.update_focus_area(
                    area_id,
                    name=title,
                    description=description,
                    priority=priority,
                    enabled=enabled
                )
                success_msg = MSG.FOCUS_AREA_UPDATED.format(name=area.get(KEYS.FOCUS_AREA_NAME, 'Unknown'))
                return True, success_msg
            else:
                error_msg = MSG.DATABASE_SERVICE_NOT_AVAILABLE
                self.logger.error(error_msg)
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
        areas = self.get_focus_areas()
        idx = self._find_focus_area_index(id_or_name)
        
        if idx is None:
            error_msg = MSG.FOCUS_AREA_NOT_FOUND.format(id_or_name=id_or_name)
            return False, error_msg
        
        removed_area = areas[idx]
        area_id = removed_area.get(KEYS.FOCUS_AREA_ID)
        
        try:
            db_service = self.context.services.get(DATABASE_SERVICE)
            if db_service:
                db_service.delete_focus_area(area_id)
                success_msg = MSG.FOCUS_AREA_REMOVED.format(name=removed_area.get(KEYS.FOCUS_AREA_NAME, 'Unknown'))
                return True, success_msg
            else:
                error_msg = MSG.DATABASE_SERVICE_NOT_AVAILABLE
                self.logger.error(error_msg)
                return False, error_msg
        except Exception as e:
            error_msg = MSG.ERROR_REMOVING_FOCUS_AREA.format(error=e)
            return False, error_msg
    
