#!/usr/bin/env python3
"""
Import/Export service for managing focus areas data.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from cli.constants import keys as KEYS
from cli.constants import messages as MSG
from cli.shared.context import CLIContext
from cli.shared.service_names import DATABASE_SERVICE


class ImportExportService:
    """Service for importing and exporting focus areas data."""
    
    def __init__(self, focus_area_service):
        """Initialize the ImportExportService.
        
        Args:
            focus_area_service: An instance of FocusAreaService
        """
        self.focus_area_service = focus_area_service
        self.logger = logging.getLogger(__name__)
    
    def import_focus_areas(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Import focus areas from a JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Tuple of (success, message)
        """
        if not os.path.exists(file_path):
            error_msg = f"Error: File '{file_path}' not found."
            return False, error_msg
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                imported_areas = json.load(f)
            
            if not isinstance(imported_areas, list):
                error_msg = "Error: Import file must contain a JSON array of focus areas."
                return False, error_msg
            
            # Validate structure
            for i, area in enumerate(imported_areas):
                if not isinstance(area, dict):
                    error_msg = f"Error: Item {i+1} is not a valid focus area object."
                    return False, error_msg
                if KEYS.FOCUS_AREA_NAME not in area:
                    error_msg = f"Error: Item {i+1} missing required '{KEYS.FOCUS_AREA_NAME}' field."
                    return False, error_msg
            
            # Get database service from focus_area_service's context
            db_service = self.focus_area_service.context.services.get(DATABASE_SERVICE)
            if not db_service:
                error_msg = MSG.DATABASE_SERVICE_NOT_AVAILABLE
                self.logger.error(error_msg)
                return False, error_msg
            
            # Import each area into database
            imported_count = 0
            for area in imported_areas:
                try:
                    db_service.create_focus_area(
                        name=area.get(KEYS.FOCUS_AREA_NAME),
                        description=area.get(KEYS.FOCUS_AREA_DESCRIPTION, ""),
                        priority=area.get(KEYS.FOCUS_AREA_PRIORITY, 999),
                        enabled=area.get(KEYS.FOCUS_AREA_ENABLED, True)
                    )
                    imported_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to import focus area '{area.get(KEYS.FOCUS_AREA_NAME)}': {e}")
            
            success_msg = f"Successfully imported {imported_count} focus areas from '{file_path}'"
            return imported_count > 0, success_msg
                
        except json.JSONDecodeError as e:
            error_msg = f"Error parsing JSON file: {e}"
            return False, error_msg
        except Exception as e:
            error_msg = f"Error importing focus areas: {e}"
            return False, error_msg
    
    def export_focus_areas(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Export focus areas to a JSON file.
        
        Args:
            file_path: Path to output JSON file
            
        Returns:
            Tuple of (success, message)
        """
        areas = self.focus_area_service.get_focus_areas()
        
        if not areas:
            error_msg = "No focus areas to export."
            return False, error_msg
        
        try:
            # Create directory if it doesn't exist
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(areas, f, indent=2, ensure_ascii=False)
            
            success_msg = f"Successfully exported {len(areas)} focus areas to '{file_path}'"
            return True, success_msg
        except Exception as e:
            error_msg = f"Error exporting focus areas: {e}"
            return False, error_msg