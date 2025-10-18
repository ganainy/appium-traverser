#!/usr/bin/env python3
"""
Analysis service for managing crawl analysis and reporting.
"""

import logging
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..shared.context import CLIContext


class AnalysisService:
    """Service for managing analysis of crawl data."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
        self.discovered_analysis_targets: List[Dict[str, Any]] = []
    
    def discover_analysis_targets(self, quiet: bool = False) -> bool:
        """Discover analysis targets in output directory.
        
        Args:
            quiet: Suppress debug messages
            
        Returns:
            True if successful, False otherwise
        """
        config_service = self.context.services.get("config")
        if not config_service:
            self.logger.error("Config service not available")
            return False
        
        output_data_dir = config_service.get_value("OUTPUT_DATA_DIR")
        if not output_data_dir:
            if not quiet:
                self.logger.error("OUTPUT_DATA_DIR is not configured.")
            return False
        
        db_output_root = Path(output_data_dir)
        if not db_output_root.is_dir():
            if not quiet:
                self.logger.error(f"Output directory not found: {db_output_root}")
            return False
        
        self.discovered_analysis_targets = []
        target_idx = 1
        
        # Look for database files in session directories
        for session_dir in db_output_root.iterdir():
            if (
                session_dir.is_dir() and "_" in session_dir.name
            ):  # Session dirs have format device_package_timestamp
                db_dir = session_dir / "database"
                if db_dir.exists():
                    for db_file in db_dir.glob("*_crawl_data.db"):
                        # Extract app package from session directory name
                        session_parts = session_dir.name.split("_")
                        if len(session_parts) >= 2:
                            app_package_name = session_parts[
                                1
                            ]  # Second part is the app package
                            
                            self.discovered_analysis_targets.append(
                                {
                                    "index": target_idx,
                                    "app_package": app_package_name,
                                    "db_path": str(db_file.resolve()),
                                    "db_filename": db_file.name,
                                    "session_dir": str(session_dir),
                                }
                            )
                            target_idx += 1
        return True
    
    def list_analysis_targets(self) -> Tuple[bool, List[Dict]]:
        """List all available analysis targets.
        
        Returns:
            Tuple of (success, targets_list)
        """
        if not self.discover_analysis_targets(quiet=True):
            self.logger.error(
                "Could not discover analysis targets. Check OUTPUT_DATA_DIR and database_output structure."
            )
            return False, []
        
        config_service = self.context.services.get("config")
        if not config_service:
            return False, []
        
        output_data_dir = config_service.get_value("OUTPUT_DATA_DIR")
        if not output_data_dir:
            self.logger.error("OUTPUT_DATA_DIR is not set in the configuration.")
            return False, []
        
        db_output_root = Path(output_data_dir)
        
        if not self.discovered_analysis_targets:
            return True, []
        
        return True, self.discovered_analysis_targets
    
    def get_target_by_identifier(self, identifier: str, is_index: bool) -> Optional[Dict]:
        """Get analysis target by index or package name.
        
        Args:
            identifier: Target index or package name
            is_index: True if identifier is an index, False if package name
            
        Returns:
            Target dictionary or None if not found
        """
        if not self.discover_analysis_targets(quiet=True):
            self.logger.error("Could not discover analysis targets.")
            return None
        
        if is_index:
            try:
                target_index_val = int(identifier)
                selected_target = next(
                    (
                        t
                        for t in self.discovered_analysis_targets
                        if t["index"] == target_index_val
                    ),
                    None,
                )
                if not selected_target:
                    self.logger.error(f"Target index {identifier} not found.")
                return selected_target
            except ValueError:
                self.logger.error(f"Invalid target index: '{identifier}'. Must be a number.")
                return None
        else:
            selected_target = next(
                (
                    t
                    for t in self.discovered_analysis_targets
                    if t["app_package"] == identifier
                ),
                None,
            )
            if not selected_target:
                self.logger.error(f"Target app package '{identifier}' not found.")
            return selected_target
    
    def list_runs_for_target(self, target_identifier: str, is_index: bool) -> bool:
        """List runs for a specific analysis target.
        
        Args:
            target_identifier: Target index or package name
            is_index: True if identifier is an index, False if package name
            
        Returns:
            True if successful, False otherwise
        """
        selected_target = self.get_target_by_identifier(target_identifier, is_index)
        if not selected_target:
            return False
        
        try:
            from analysis_viewer import RunAnalyzer
        except ImportError as e:
            self.logger.error(f"Failed to import RunAnalyzer: {e}")
            return False
        
        config_service = self.context.services.get("config")
        if not config_service:
            return False
        
        output_data_dir = config_service.get_value("OUTPUT_DATA_DIR")
        if not output_data_dir:
            self.logger.error("OUTPUT_DATA_DIR is not configured.")
            return False
        
        print(
            f"\n--- Runs for Target {selected_target['index']}: {selected_target['app_package']} (DB: {selected_target['db_filename']}) ---"
        )
        try:
            analyzer = RunAnalyzer(
                db_path=selected_target["db_path"],
                output_data_dir=output_data_dir,
                app_package_for_run=selected_target["app_package"],
            )
            analyzer.list_runs()
            return True
        except FileNotFoundError:
            self.logger.error(
                f"Database file not found for target {selected_target['app_package']}: {selected_target['db_path']}"
            )
            print(f"Error: Database file not found: {selected_target['db_path']}")
            return False
        except Exception as e:
            self.logger.error(
                f"Error listing runs for target {selected_target['app_package']}: {e}",
                exc_info=True,
            )
            print(f"Error listing runs: {e}")
            return False
    
    def generate_analysis_pdf(
        self,
        target_identifier: str,
        is_index: bool,
        pdf_output_name: Optional[str] = None,
    ) -> bool:
        """Generate PDF report for a target.
        
        Args:
            target_identifier: Target index or package name
            is_index: True if identifier is an index, False if package name
            pdf_output_name: Optional custom PDF filename
            
        Returns:
            True if successful, False otherwise
        """
        selected_target = self.get_target_by_identifier(target_identifier, is_index)
        if not selected_target:
            return False
        
        try:
            from analysis_viewer import RunAnalyzer, XHTML2PDF_AVAILABLE
        except ImportError as e:
            self.logger.error(f"Failed to import analysis modules: {e}")
            return False
        
        if not XHTML2PDF_AVAILABLE:
            self.logger.error("PDF library (xhtml2pdf) not available.")
            print("Error: PDF library not available. Install with: pip install xhtml2pdf")
            return False
        
        config_service = self.context.services.get("config")
        if not config_service:
            return False
        
        output_data_dir = config_service.get_value("OUTPUT_DATA_DIR")
        if not output_data_dir:
            self.logger.error("OUTPUT_DATA_DIR is not configured.")
            return False
        
        # Determine run ID (latest or only one)
        actual_run_id = self._determine_run_id(selected_target["db_path"])
        if actual_run_id is None:
            self.logger.error(
                f"Failed to determine a run_id for PDF generation for target {selected_target['app_package']}."
            )
            return False
        
        # Create output directory
        analysis_reports_dir = Path(selected_target["session_dir"]) / "reports"
        analysis_reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        pdf_filename_suffix = (
            Path(pdf_output_name).name if pdf_output_name else "analysis.pdf"
        )
        final_pdf_filename = f"{selected_target['app_package']}_{pdf_filename_suffix}"
        final_pdf_path = str(analysis_reports_dir / final_pdf_filename)
        
        self.logger.debug(
            f"Generating PDF for Target: {selected_target['app_package']}, Run ID: {actual_run_id}, Output: {final_pdf_path}"
        )
        
        try:
            analyzer = RunAnalyzer(
                db_path=selected_target["db_path"],
                output_data_dir=output_data_dir,
                app_package_for_run=selected_target["app_package"],
            )
            analyzer.analyze_run_to_pdf(actual_run_id, final_pdf_path)
            return True
        except FileNotFoundError:
            self.logger.error(
                f"Database file not found for PDF generation: {selected_target['db_path']}"
            )
            print(f"Error: Database file not found: {selected_target['db_path']}")
            return False
        except Exception as e:
            self.logger.error(
                f"Error generating PDF for target {selected_target['app_package']}, run {actual_run_id}: {e}",
                exc_info=True,
            )
            print(f"Error generating PDF: {e}")
            return False
    
    def print_analysis_summary(self, target_identifier: str, is_index: bool) -> bool:
        """Print summary metrics for a target.
        
        Args:
            target_identifier: Target index or package name
            is_index: True if identifier is an index, False if package name
            
        Returns:
            True if successful, False otherwise
        """
        selected_target = self.get_target_by_identifier(target_identifier, is_index)
        if not selected_target:
            return False
        
        try:
            from analysis_viewer import RunAnalyzer
        except ImportError as e:
            self.logger.error(f"Failed to import RunAnalyzer: {e}")
            return False
        
        config_service = self.context.services.get("config")
        if not config_service:
            return False
        
        output_data_dir = config_service.get_value("OUTPUT_DATA_DIR")
        if not output_data_dir:
            self.logger.error("OUTPUT_DATA_DIR is not configured.")
            return False
        
        # Determine run ID (latest or only one)
        actual_run_id = self._determine_run_id(selected_target["db_path"])
        if actual_run_id is None:
            self.logger.error(
                f"Failed to determine a run_id for summary printing for target {selected_target['app_package']}."
            )
            return False
        
        try:
            analyzer = RunAnalyzer(
                db_path=selected_target["db_path"],
                output_data_dir=output_data_dir,
                app_package_for_run=selected_target["app_package"],
            )
            analyzer.print_run_summary(actual_run_id)
            return True
        except FileNotFoundError:
            self.logger.error(
                f"Database file not found for summary printing: {selected_target['db_path']}"
            )
            print(f"Error: Database file not found: {selected_target['db_path']}")
            return False
        except Exception as e:
            self.logger.error(
                f"Error printing summary for target {selected_target['app_package']}, run {actual_run_id}: {e}",
                exc_info=True,
            )
            print(f"Error printing summary: {e}")
            return False
    
    def _determine_run_id(self, db_path: str) -> Optional[int]:
        """Determine the run ID to use for analysis.
        
        Args:
            db_path: Path to database file
            
        Returns:
            Run ID or None if not found
        """
        try:
            conn_temp = sqlite3.connect(db_path)
            cursor_temp = conn_temp.cursor()
            
            # Try to get the highest run_id (latest)
            cursor_temp.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1")
            latest_run_row = cursor_temp.fetchone()
            
            if latest_run_row and latest_run_row[0] is not None:
                actual_run_id = latest_run_row[0]
                self.logger.debug(
                    f"Using Run ID: {actual_run_id} (latest/only)"
                )
            else:
                # Fallback: get any run_id
                cursor_temp.execute("SELECT run_id FROM runs LIMIT 1")
                any_run_row = cursor_temp.fetchone()
                
                if any_run_row and any_run_row[0] is not None:
                    actual_run_id = any_run_row[0]
                    self.logger.warning(
                        f"Could not determine latest run, using first available Run ID: {actual_run_id}"
                    )
                else:
                    self.logger.error("No runs found in the database.")
                    conn_temp.close()
                    return None
            
            conn_temp.close()
            return actual_run_id
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error determining run ID: {e}")
            return None
    
    def run_offline_ui_annotator(self, session_dir: str, db_path: str) -> bool:
        """Run offline UI annotator for a session.
        
        Args:
            session_dir: Session directory path
            db_path: Database file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
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