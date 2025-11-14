#!/usr/bin/env python3
"""
Analysis service for managing crawl analysis and reporting.

This service provides functionality to:
- Discover and list analysis targets from crawl data
- Retrieve targets by index or package name
- List runs for specific targets
- Generate PDF analysis reports
- Get analysis summaries with metrics

The service works with SQLite databases containing crawl session data and integrates
with the RunAnalyzer from domain.analysis_viewer for detailed analysis operations.
"""


import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cli.shared.context import ApplicationContext
from cli.shared.command_result import CommandResult
from cli.constants import keys as CKeys
from cli.constants import messages as CMsg
from utils.paths import SessionPathManager

# SQL queries for analysis service
SQL_SELECT_LATEST_RUN_ID = "SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1"
SQL_SELECT_ANY_RUN_ID = "SELECT run_id FROM runs LIMIT 1"


class AnalysisService:
    """Service for managing analysis of crawl data.
    
    Provides methods to discover, query, and analyze crawl session data stored in
    SQLite databases. Supports target discovery, run listing, PDF report generation,
    and summary metrics extraction.
    """
    
    def __init__(self, context: ApplicationContext):
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
        output_data_dir = self.context.config.get(CKeys.CONFIG_OUTPUT_DATA_DIR)
        if not output_data_dir:
            if not quiet:
                self.logger.error(CMsg.ERR_OUTPUT_DATA_DIR_NOT_CONFIGURED)
            return False

        db_output_root = Path(output_data_dir)
        if not db_output_root.is_dir():
            if not quiet:
                self.logger.error(CMsg.ERR_OUTPUT_DIRECTORY_NOT_FOUND.format(db_output_root=db_output_root))
            return False

        self.discovered_analysis_targets = []
        target_idx = 1
        # Use config directly
        for session_dir in db_output_root.iterdir():
            if not session_dir.is_dir():
                continue
            target_info = SessionPathManager.parse_session_dir(session_dir, self.context.config)
            if target_info:
                target_info[CKeys.KEY_INDEX] = target_idx  
                self.discovered_analysis_targets.append(target_info)
                target_idx += 1
        return True
    
    def list_analysis_targets(self) -> Tuple[bool, List[Dict]]:
        """List all available analysis targets.
        
        Returns:
            Tuple of (success, targets_list)
        """
        if not self.discover_analysis_targets(quiet=True):
            self.logger.error(CMsg.ERR_ANALYSIS_TARGET_DISCOVERY_FAILED)
            return False, []
        
        if not self.discovered_analysis_targets:
            return True, []
        
        return True, self.discovered_analysis_targets
    
    def get_target_by_index(self, index: int) -> Optional[Dict]:
        """Get analysis target by index.
        
        Args:
            index: Target index
            
        Returns:
            Target dictionary or None if not found
        """
        if not self.discover_analysis_targets(quiet=True):
            self.logger.error(CMsg.ERR_COULD_NOT_DISCOVER_ANALYSIS_TARGETS)
            return None
        
        selected_target = next(
            (
                t
                for t in self.discovered_analysis_targets
                if t[CKeys.KEY_INDEX] == index
            ),
            None,
        )
        if not selected_target:
            self.logger.error(CMsg.ERR_TARGET_INDEX_NOT_FOUND.format(index=index))
        return selected_target
    
    def get_target_by_package(self, package_name: str) -> Optional[Dict]:
        """Get analysis target by package name.
        
        Args:
            package_name: Target package name
            
        Returns:
            Target dictionary or None if not found
        """
        if not self.discover_analysis_targets(quiet=True):
            self.logger.error(CMsg.ERR_COULD_NOT_DISCOVER_ANALYSIS_TARGETS)
            return None
        
        selected_target = next(
            (
                t
                for t in self.discovered_analysis_targets
                if t[CKeys.KEY_APP_PACKAGE] == package_name
            ),
            None,
        )
        if not selected_target:
            self.logger.error(CMsg.ERR_TARGET_APP_PACKAGE_NOT_FOUND.format(package=package_name))
        return selected_target
    
    def list_runs_for_target(self, target: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """List runs for a specific analysis target.
        
        Args:
            target: Target dictionary containing target information
            
        Returns:
            Tuple of (success, data) where data contains:
            - target_info: dict with target information
            - runs: list of run dictionaries
            - message: optional message
        """
        if not target:
            return False, {CKeys.KEY_ERROR: CMsg.ERR_TARGET_NOT_FOUND}
        
        try:
            from domain.analysis_viewer import RunAnalyzer
        except ImportError as e:
            self.logger.error(CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e))
            return False, {CKeys.KEY_ERROR: CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e)}
        
        output_data_dir = self.context.config.get(CKeys.CONFIG_OUTPUT_DATA_DIR)
        if not output_data_dir:
            self.logger.error(CMsg.ERR_OUTPUT_DATA_DIR_NOT_CONFIGURED)
            return False, {CKeys.KEY_ERROR: CMsg.ERR_OUTPUT_DATA_DIR_NOT_CONFIGURED}
        
        try:
            analyzer = RunAnalyzer(
                db_path=target[CKeys.KEY_DB_PATH],
                output_data_dir=output_data_dir,
                app_package_for_run=target[CKeys.KEY_APP_PACKAGE],
            )
            runs_result = analyzer.list_runs()
            
            # Prepare the response data
            response_data = {
                CKeys.KEY_TARGET_INFO: {
                    CKeys.KEY_INDEX: target[CKeys.KEY_INDEX],
                    CKeys.KEY_APP_PACKAGE: target[CKeys.KEY_APP_PACKAGE],
                    CKeys.KEY_DB_FILENAME: target[CKeys.KEY_DB_FILENAME]
                },
                CKeys.KEY_RUNS: runs_result.get(CKeys.KEY_RUNS, []),
                CKeys.KEY_MESSAGE: runs_result.get(CKeys.KEY_MESSAGE, "")
            }
            
            return runs_result["success"], response_data
        except FileNotFoundError:
            error_msg = CMsg.ERR_DATABASE_FILE_NOT_FOUND.format(operation="listing runs", db_path=target[CKeys.KEY_DB_PATH])
            self.logger.error(error_msg)
            return False, {CKeys.KEY_ERROR: error_msg}
        except Exception as e:
            error_msg = CMsg.ERR_ERROR_DURING_OPERATION.format(operation="listing runs for", app_package=target[CKeys.KEY_APP_PACKAGE], run_id="N/A", error=e)
            self.logger.error(error_msg, exc_info=True)
            return False, {CKeys.KEY_ERROR: error_msg}
    
    def generate_analysis_pdf(
        self,
        target: Dict[str, Any],
        pdf_output_name: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Generate PDF report for a target.
        
        Args:
            target: Target dictionary containing target information
            pdf_output_name: Optional custom PDF filename
            
        Returns:
            Tuple of (success, data) where data contains:
            - pdf_path: path to generated PDF (if successful)
            - error: error message (if unsuccessful)
        """
        if not target:
            return False, {CKeys.KEY_ERROR: CMsg.ERR_TARGET_NOT_FOUND}
        
        try:
            from domain.analysis_viewer import XHTML2PDF_AVAILABLE, RunAnalyzer
        except ImportError as e:
            self.logger.error(CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e))
            return False, {CKeys.KEY_ERROR: CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e)}
        
        if not XHTML2PDF_AVAILABLE:
            error_msg = CMsg.ERR_XHTML2PDF_NOT_AVAILABLE
            self.logger.error(error_msg)
            return False, {CKeys.KEY_ERROR: error_msg}
        
        output_data_dir = self.context.config.get(CKeys.CONFIG_OUTPUT_DATA_DIR)
        if not output_data_dir:
            self.logger.error(CMsg.ERR_OUTPUT_DATA_DIR_NOT_CONFIGURED)
            return False, {CKeys.KEY_ERROR: CMsg.ERR_OUTPUT_DATA_DIR_NOT_CONFIGURED}
        
        # Determine run ID (latest or only one)
        actual_run_id = self._determine_run_id(target[CKeys.KEY_DB_PATH])
        if actual_run_id is None:
            error_msg = CMsg.ERR_FAILED_TO_DETERMINE_RUN_ID.format(operation="PDF generation", app_package=target[CKeys.KEY_APP_PACKAGE])
            self.logger.error(error_msg)
            return False, {CKeys.KEY_ERROR: error_msg}
        
        # Create output directory using SessionPathManager
        analysis_reports_dir = SessionPathManager.get_reports_dir(target[CKeys.KEY_SESSION_DIR])
        analysis_reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate PDF path using SessionPathManager
        final_pdf_path = str(SessionPathManager.get_pdf_report_path(
            analysis_reports_dir,
            target[CKeys.KEY_APP_PACKAGE],
            pdf_output_name
        ))
        
        self.logger.debug(
            f"Generating PDF for Target: {target[CKeys.KEY_APP_PACKAGE]}, Run ID: {actual_run_id}, Output: {final_pdf_path}"
        )
        
        try:
            analyzer = RunAnalyzer(
                db_path=target[CKeys.KEY_DB_PATH],
                output_data_dir=output_data_dir,
                app_package_for_run=target[CKeys.KEY_APP_PACKAGE],
            )
            pdf_result = analyzer.analyze_run_to_pdf(actual_run_id, final_pdf_path)
            
            if pdf_result[CKeys.KEY_SUCCESS]:
                return True, {CKeys.KEY_PDF_PATH: final_pdf_path}
            else:
                return False, {CKeys.KEY_ERROR: pdf_result.get(CKeys.KEY_ERROR, "Unknown error generating PDF")}
        except FileNotFoundError:
            error_msg = CMsg.ERR_DATABASE_FILE_NOT_FOUND.format(operation="PDF generation", db_path=target[CKeys.KEY_DB_PATH])
            self.logger.error(error_msg)
            return False, {CKeys.KEY_ERROR: error_msg}
        except Exception as e:
            error_msg = CMsg.ERR_ERROR_DURING_OPERATION.format(operation="generating PDF for", app_package=target[CKeys.KEY_APP_PACKAGE], run_id=actual_run_id, error=e)
            self.logger.error(error_msg, exc_info=True)
            return False, {CKeys.KEY_ERROR: error_msg}
    
    def get_analysis_summary(self, target: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Get summary metrics for a target.
        
        Args:
            target: Target dictionary containing target information
            
        Returns:
            Tuple of (success, data) where data contains:
            - run_info: dictionary with basic run information
            - metrics: dictionary with calculated metrics
            - error: error message (if unsuccessful)
        """
        if not target:
            return False, {CKeys.KEY_ERROR: CMsg.ERR_TARGET_NOT_FOUND}
        
        try:
            from domain.analysis_viewer import RunAnalyzer
        except ImportError as e:
            self.logger.error(CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e))
            return False, {CKeys.KEY_ERROR: CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e)}
        
        output_data_dir = self.context.config.get(CKeys.CONFIG_OUTPUT_DATA_DIR)
        if not output_data_dir:
            self.logger.error(CMsg.ERR_OUTPUT_DATA_DIR_NOT_CONFIGURED)
            return False, {CKeys.KEY_ERROR: CMsg.ERR_OUTPUT_DATA_DIR_NOT_CONFIGURED}
        
        # Determine run ID (latest or only one)
        actual_run_id = self._determine_run_id(target[CKeys.KEY_DB_PATH])
        if actual_run_id is None:
            error_msg = CMsg.ERR_FAILED_TO_DETERMINE_RUN_ID.format(operation="summary", app_package=target[CKeys.KEY_APP_PACKAGE])
            self.logger.error(error_msg)
            return False, {CKeys.KEY_ERROR: error_msg}
        
        try:
            analyzer = RunAnalyzer(
                db_path=target[CKeys.KEY_DB_PATH],
                output_data_dir=output_data_dir,
                app_package_for_run=target[CKeys.KEY_APP_PACKAGE],
            )
            summary_result = analyzer.get_run_summary(actual_run_id)
            
            if summary_result[CKeys.KEY_SUCCESS]:
                return True, {
                    CKeys.KEY_RUN_INFO: summary_result[CKeys.KEY_RUN_INFO],
                    CKeys.KEY_METRICS: summary_result[CKeys.KEY_METRICS]
                }
            else:
                return False, {CKeys.KEY_ERROR: summary_result.get(CKeys.KEY_ERROR, "Unknown error")}
        except FileNotFoundError:
            error_msg = CMsg.ERR_DATABASE_FILE_NOT_FOUND.format(operation="summary", db_path=target[CKeys.KEY_DB_PATH])
            self.logger.error(error_msg)
            return False, {CKeys.KEY_ERROR: error_msg}
        except Exception as e:
            error_msg = CMsg.ERR_ERROR_DURING_OPERATION.format(operation="getting summary for", app_package=target[CKeys.KEY_APP_PACKAGE], run_id=actual_run_id, error=e)
            self.logger.error(error_msg, exc_info=True)
            return False, {CKeys.KEY_ERROR: error_msg}
    
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
            cursor_temp.execute(SQL_SELECT_LATEST_RUN_ID)
            latest_run_row = cursor_temp.fetchone()
            
            if latest_run_row and latest_run_row[0] is not None:
                actual_run_id = latest_run_row[0]
                self.logger.debug(
                    CMsg.MSG_USING_RUN_ID_LATEST.format(run_id=actual_run_id)
                )
            else:
                # Fallback: get any run_id
                cursor_temp.execute(SQL_SELECT_ANY_RUN_ID)
                any_run_row = cursor_temp.fetchone()
                
                if any_run_row and any_run_row[0] is not None:
                    actual_run_id = any_run_row[0]
                    self.logger.warning(
                        CMsg.MSG_USING_RUN_ID_FIRST_AVAILABLE.format(run_id=actual_run_id)
                    )
                else:
                    self.logger.error(CMsg.MSG_NO_RUNS_FOUND)
                    conn_temp.close()
                    return None
            
            conn_temp.close()
            return actual_run_id
            
        except sqlite3.Error as e:
            self.logger.error(CMsg.ERR_DATABASE_ERROR_DETERMINING_RUN_ID.format(error=e))
            return None
    
    def find_latest_session_dir(self) -> Optional[Tuple[str, str]]:
        """Find the latest session directory by modification timestamp.
        
        Scans the sessions directory and returns the session with the greatest
        modification timestamp along with its database path.
        
        Returns:
            Tuple of (session_dir, db_path) if found, None otherwise
        """
        output_data_dir = self.context.config.get(CKeys.CONFIG_OUTPUT_DATA_DIR)
        if not output_data_dir:
            self.logger.error(CMsg.ERR_OUTPUT_DATA_DIR_NOT_CONFIGURED)
            return None
        
        sessions_dir = Path(output_data_dir) / "sessions"
        if not sessions_dir.is_dir():
            self.logger.error(f"Sessions directory not found: {sessions_dir}")
            return None
        
        candidates = []
        session_dirs_found = []
        for session_dir in sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            # Resolve to absolute path
            session_dir = session_dir.resolve()
            session_dirs_found.append(str(session_dir))
            
            # Try to parse the session directory to get target info
            target_info = SessionPathManager.parse_session_dir(session_dir, self.context.config)
            db_path = None
            
            if target_info:
                db_path = target_info.get(CKeys.KEY_DB_PATH)
            
            # If parsing failed or no db_path, try to find database file directly
            if not db_path:
                self.logger.debug(f"Could not get db_path from parsing, trying direct search for: {session_dir}")
                # Look for database files in common locations
                db_candidates = []
                # Check database subdirectory
                db_dir = session_dir / "database"
                if db_dir.is_dir():
                    db_candidates.extend(db_dir.glob("*_crawl_data.db"))
                # If no database found, we can't use this session
                if not db_candidates:
                    self.logger.debug(f"No database file found in {session_dir}")
                    continue
                # Use the first database file found
                db_path = str(db_candidates[0])
                
            db_path_obj = Path(db_path)
            if not db_path_obj.exists():
                self.logger.debug(f"Database file does not exist: {db_path} (for session: {session_dir})")
                continue
            
            # Use modification time of the session directory
            try:
                mtime = os.path.getmtime(session_dir)
                candidates.append((mtime, str(session_dir), db_path))
                self.logger.debug(f"Found valid session: {session_dir} with db: {db_path}")
            except OSError as e:
                self.logger.warning(f"Could not get mtime for {session_dir}: {e}")
                continue
        
        if not candidates:
            # If no sessions with databases found, log which directories were checked
            self.logger.warning(
                f"No valid session directories with database files found. "
                f"Found {len(session_dirs_found)} session directories, but none contain database files. "
                f"This may happen if the crawler run was very short and didn't write any data. "
                f"Session directories: {session_dirs_found[:3]}{'...' if len(session_dirs_found) > 3 else ''}"
            )
            return None
        
        # Sort by modification time (descending) and return the latest
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, session_dir, db_path = candidates[0]
        self.logger.info(f"Selected latest session: {session_dir} (mtime: {candidates[0][0]})")
        return (session_dir, db_path)
    
