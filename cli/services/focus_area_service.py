#!/usr/bin/env python3
"""
Focus area service for managing privacy focus areas.
"""

import json
import logging
import os
from typing import Dict, List, Optional

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
                self.logger.error("Database service not available")
                return []
            
            # Query focus areas from database
            areas = db_service.query_focus_areas()
            return areas if isinstance(areas, list) else []
        except Exception as e:
            self.logger.error(f"Failed to load focus areas from database: {e}")
            return []
    
    def list_focus_areas(self) -> List[Dict]:
        """List configured focus areas.
        
        Returns:
            List of focus area dictionaries with consistent properties
        """
        areas = self.get_focus_areas()
        processed_areas = []
        
        for i, area in enumerate(areas):
            # Create a new dictionary with consistent properties
            processed_area = {
                "id": area.get("id"),
                "display_name": area.get("title") or area.get("name") or f"Area {i+1}",
                "enabled": area.get("enabled", True),
                "priority": area.get("priority", i),
                "original_data": area  # Keep original data for reference if needed
            }
            processed_areas.append(processed_area)
        
        return processed_areas
    
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
                    str(area.get("title", "")).lower()
                    or str(area.get("name", "")).lower()
                ):
                    return i
        return None
    
    def set_focus_area_enabled(self, id_or_name: str, enabled: bool) -> bool:
        """Enable or disable a focus area.
        
        Args:
            id_or_name: Focus area ID or name
            enabled: Whether to enable the focus area
            
        Returns:
            True if successful, False otherwise
        """
        areas = self.get_focus_areas()
        idx = self._find_focus_area_index(id_or_name)
        
        if idx is None:
            self.logger.error(f"Focus area '{id_or_name}' not found.")
            return False
        
        area_id = areas[idx].get("id")
        
        try:
            db_service = self.context.services.get(DATABASE_SERVICE)
            if db_service:
                db_service.update_focus_area_enabled(area_id, enabled)
                print(
                    f"Focus area '{areas[idx].get('name', id_or_name)}' set enabled={enabled}"
                )
                return True
            else:
                self.logger.error("Database service not available")
                return False
        except Exception as e:
            self.logger.error(f"Failed to update focus area: {e}")
            return False
    
    def move_focus_area(self, from_index_str: str, to_index_str: str) -> bool:
        """Reorder focus areas.
        
        Args:
            from_index_str: Source index (1-based)
            to_index_str: Target index (1-based)
            
        Returns:
            True if successful, False otherwise
        """
        areas = self.get_focus_areas()
        try:
            from_idx = int(from_index_str) - 1
            to_idx = int(to_index_str) - 1
        except ValueError:
            self.logger.error("--from-index and --to-index must be integers (1-based)")
            return False
        
        if not (0 <= from_idx < len(areas)) or not (0 <= to_idx < len(areas)):
            self.logger.error("Index out of range for focus areas list")
            return False
        
        item = areas.pop(from_idx)
        areas.insert(to_idx, item)
        
        try:
            db_service = self.context.services.get(DATABASE_SERVICE)
            if db_service:
                # Update priorities in database
                for i, area in enumerate(areas):
                    db_service.update_focus_area_priority(area.get("id"), i)
                print(f"Moved focus area to position {to_idx+1}")
                return True
            else:
                self.logger.error("Database service not available")
                return False
        except Exception as e:
            self.logger.error(f"Failed to reorder focus areas: {e}")
            return False
    
    def add_focus_area(
        self, 
        title: str, 
        description: str = "", 
        priority: int = 999, 
        enabled: bool = True
    ) -> bool:
        """Add a new focus area.
        
        Args:
            title: Focus area title
            description: Focus area description
            priority: Focus area priority
            enabled: Whether the focus area is enabled
            
        Returns:
            True if successful, False otherwise
        """
        areas = self.get_focus_areas()
        
        # Check for duplicate title
        for area in areas:
            if area.get("name", "").lower() == title.lower():
                print(f"Error: Focus area with title '{title}' already exists.")
                return False
        
        try:
            db_service = self.context.services.get(DATABASE_SERVICE)
            if db_service:
                db_service.create_focus_area(
                    name=title,
                    description=description,
                    priority=priority,
                    enabled=enabled
                )
                print(f"✅ Successfully added focus area: {title}")
                return True
            else:
                self.logger.error("Database service not available")
                return False
        except Exception as e:
            print(f"Error adding focus area: {e}")
            return False
    
    def edit_focus_area(
        self,
        id_or_name: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        enabled: Optional[bool] = None
    ) -> bool:
        """Edit an existing focus area.
        
        Args:
            id_or_name: Focus area ID or name
            title: New title (optional)
            description: New description (optional)
            priority: New priority (optional)
            enabled: New enabled state (optional)
            
        Returns:
            True if successful, False otherwise
        """
        areas = self.get_focus_areas()
        idx = self._find_focus_area_index(id_or_name)
        
        if idx is None:
            print(f"Error: Focus area '{id_or_name}' not found.")
            return False
        
        area = areas[idx]
        area_id = area.get("id")
        
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
                print(f"✅ Successfully updated focus area: {area.get('name', 'Unknown')}")
                return True
            else:
                self.logger.error("Database service not available")
                return False
        except Exception as e:
            print(f"Error updating focus area: {e}")
            return False
    
    def remove_focus_area(self, id_or_name: str) -> bool:
        """Remove a focus area.
        
        Args:
            id_or_name: Focus area ID or name
            
        Returns:
            True if successful, False otherwise
        """
        areas = self.get_focus_areas()
        idx = self._find_focus_area_index(id_or_name)
        
        if idx is None:
            print(f"Error: Focus area '{id_or_name}' not found.")
            return False
        
        removed_area = areas[idx]
        area_id = removed_area.get("id")
        
        try:
            db_service = self.context.services.get(DATABASE_SERVICE)
            if db_service:
                db_service.delete_focus_area(area_id)
                print(f"✅ Successfully removed focus area: {removed_area.get('name', 'Unknown')}")
                return True
            else:
                self.logger.error("Database service not available")
                return False
        except Exception as e:
            print(f"Error removing focus area: {e}")
            return False
    
    def import_focus_areas(self, file_path: str) -> bool:
        """Import focus areas from a JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' not found.")
            return False
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                imported_areas = json.load(f)
            
            if not isinstance(imported_areas, list):
                print("Error: Import file must contain a JSON array of focus areas.")
                return False
            
            # Validate structure
            for i, area in enumerate(imported_areas):
                if not isinstance(area, dict):
                    print(f"Error: Item {i+1} is not a valid focus area object.")
                    return False
                if "name" not in area:
                    print(f"Error: Item {i+1} missing required 'name' field.")
                    return False
            
            db_service = self.context.services.get(DATABASE_SERVICE)
            if not db_service:
                self.logger.error("Database service not available")
                return False
            
            # Import each area into database
            imported_count = 0
            for area in imported_areas:
                try:
                    db_service.create_focus_area(
                        name=area.get("name"),
                        description=area.get("description", ""),
                        priority=area.get("priority", 999),
                        enabled=area.get("enabled", True)
                    )
                    imported_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to import focus area '{area.get('name')}': {e}")
            
            print(f"✅ Successfully imported {imported_count} focus areas from '{file_path}'")
            return imported_count > 0
                
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON file: {e}")
            return False
        except Exception as e:
            print(f"Error importing focus areas: {e}")
            return False
    
    def export_focus_areas(self, file_path: str) -> bool:
        """Export focus areas to a JSON file.
        
        Args:
            file_path: Path to output JSON file
            
        Returns:
            True if successful, False otherwise
        """
        areas = self.get_focus_areas()
        
        if not areas:
            print("No focus areas to export.")
            return False
        
        try:
            # Create directory if it doesn't exist
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(areas, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Successfully exported {len(areas)} focus areas to '{file_path}'")
            return True
        except Exception as e:
            print(f"Error exporting focus areas: {e}")
            return False
