#!/usr/bin/env python3
"""
Annotation service for managing UI element annotation operations.

This module provides the AnnotationService class, which runs the offline UI
annotator tool to overlay bounding boxes and UI element information onto
screenshots captured during app crawling.
"""

import logging
import subprocess
import sys
from pathlib import Path

from cli.shared.context import CLIContext
from cli.constants import keys as CKeys


class AnnotationService:
    """
    Service for managing offline UI element annotation operations.
    
    Executes the `ui_element_annotator.py` tool as a subprocess to generate
    annotated screenshots with bounding boxes and UI element information.
    """
    
    def __init__(self, context: CLIContext):
        """
        Initialize annotation service.
        
        Args:
            context: CLI context providing configuration and services
        """
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def run_offline_annotator(self, session_dir: str, db_path: str) -> bool:
        """
        Run the offline UI annotator tool for a crawl session.
        
        Executes `ui_element_annotator.py` to overlay bounding boxes onto screenshots
        using UI element data from the database.
        
        Args:
            session_dir: Path to the crawl session directory (contains 'screenshots' subdirectory)
            db_path: Path to the SQLite database file with UI element data
        
        Returns:
            True if annotation completed successfully, False otherwise
        """
        try:
            # Get project root from config 
            project_root = self.context.config.get(CKeys.PROJECT_ROOT)
            if not project_root:
                self.logger.error("PROJECT_ROOT is not configured.")
                return False
                
            screenshots_dir = str(Path(session_dir) / CKeys.DIR_SCREENSHOTS)
            out_dir = str(Path(session_dir) / CKeys.DIR_ANNOTATED_SCREENSHOTS)
            script_path = str(Path(project_root) / CKeys.DIR_TOOLS / "ui_element_annotator.py")
            
            cmd = [
                sys.executable,
                "-u",
                script_path,
                "--db-path",
                db_path,
                "--screens-dir",
                screenshots_dir,
                "--out-dir",
                out_dir,
            ]
            
            self.logger.debug(f"Running offline UI annotator: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info("Offline UI annotation completed successfully.")
                self.logger.debug(result.stdout)
                if result.stderr:
                    self.logger.debug(result.stderr)
                return True
            else:
                self.logger.error(
                    f"Offline UI annotation failed (code {result.returncode}). Output:\n{result.stdout}\n{result.stderr}"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to run offline UI annotator: {e}", exc_info=True)
            return False