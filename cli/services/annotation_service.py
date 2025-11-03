#!/usr/bin/env python3
"""
Annotation service for managing UI element annotation operations.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from cli.shared.context import CLIContext
from cli.constants import keys as CKeys


class AnnotationService:
    """Service for managing UI element annotation operations."""
    
    def __init__(self, context: CLIContext):
        """
        Initialize annotation service.
        
        Args:
            context: CLI context
        """
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def run_offline_annotator(self, session_dir: str, db_path: str) -> bool:
        """Run offline UI annotator for a session.
        
        Args:
            session_dir: Session directory path
            db_path: Database file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the ConfigService to retrieve the project root
            # Config is now directly accessible via context.config
            if not config_service:
                self.logger.error("Config service not available")
                return False
                
            # Get project root from config instead of brittle path calculation
            project_root = self.context.config.get(CKeys.PROJECT_ROOT)
            if not project_root:
                self.logger.error("PROJECT_ROOT is not configured.")
                return False
                
            script_path = str(Path(project_root) / "tools" / "ui_element_annotator.py")
            screenshots_dir = str(Path(session_dir) / "screenshots")
            out_dir = str(Path(session_dir) / "annotated_screenshots")
            
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