#!/usr/bin/env python3
"""
Analysis service for managing crawl analysis and reporting.
"""


import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cli.shared.context import CLIContext
from cli.shared.command_result import CommandResult
from cli.constants import keys as CKeys
from cli.constants import config as CConfig
from cli.constants import messages as CMsg
from utils.paths import SessionPathManager


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
        config_service = self.context.services.get(CKeys.SERVICE_CONFIG)
        if not config_service:
            self.logger.error(CMsg.ERR_CONFIG_SERVICE_NOT_AVAILABLE)
            return False

        output_data_dir = config_service.get_config_value(CKeys.CONFIG_OUTPUT_DATA_DIR)
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
        # Use the already fetched config_service
        for session_dir in db_output_root.iterdir():
            if not session_dir.is_dir():
                continue
            # Use the new robust parser!
            target_info = SessionPathManager.parse_session_dir(session_dir, config_service.config)
            if target_info:
                target_info[CKeys.KEY_INDEX] = target_idx  # type: ignore
                self.discovered_analysis_targets.append(target_info)  # type: ignore
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
            from analysis_viewer import RunAnalyzer
        except ImportError as e:
            self.logger.error(CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e))
            return False, {CKeys.KEY_ERROR: CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e)}
        
        config_service = self.context.services.get(CKeys.SERVICE_CONFIG)
        if not config_service:
            return False, {CKeys.KEY_ERROR: CMsg.ERR_CONFIG_SERVICE_NOT_AVAILABLE}
        
        output_data_dir = config_service.get_config_value(CKeys.CONFIG_OUTPUT_DATA_DIR)
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
            from analysis_viewer import XHTML2PDF_AVAILABLE, RunAnalyzer
        except ImportError as e:
            self.logger.error(CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e))
            return False, {CKeys.KEY_ERROR: CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e)}
        
        if not XHTML2PDF_AVAILABLE:
            error_msg = CMsg.ERR_XHTML2PDF_NOT_AVAILABLE
            self.logger.error(error_msg)
            return False, {CKeys.KEY_ERROR: error_msg}
        
        config_service = self.context.services.get(CKeys.SERVICE_CONFIG)
        if not config_service:
            return False, {CKeys.KEY_ERROR: CMsg.ERR_CONFIG_SERVICE_NOT_AVAILABLE}
        
        output_data_dir = config_service.get_config_value(CKeys.CONFIG_OUTPUT_DATA_DIR)
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
            from analysis_viewer import RunAnalyzer
        except ImportError as e:
            self.logger.error(CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e))
            return False, {CKeys.KEY_ERROR: CMsg.ERR_RUN_ANALYZER_IMPORT_FAILED.format(error=e)}
        
        config_service = self.context.services.get(CKeys.SERVICE_CONFIG)
        if not config_service:
            return False, {CKeys.KEY_ERROR: CMsg.ERR_CONFIG_SERVICE_NOT_AVAILABLE}
        
        output_data_dir = config_service.get_config_value(CKeys.CONFIG_OUTPUT_DATA_DIR)
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
            cursor_temp.execute(CConfig.SQL_SELECT_LATEST_RUN_ID)
            latest_run_row = cursor_temp.fetchone()
            
            if latest_run_row and latest_run_row[0] is not None:
                actual_run_id = latest_run_row[0]
                self.logger.debug(
                    CMsg.MSG_USING_RUN_ID_LATEST.format(run_id=actual_run_id)
                )
            else:
                # Fallback: get any run_id
                cursor_temp.execute(CConfig.SQL_SELECT_ANY_RUN_ID)
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
    
    def run_offline_ui_annotator(self, session_dir: str, db_path: str) -> bool:
        """Run offline UI annotator for a session.
        
        Args:
            session_dir: Session directory path
            db_path: Database file path
            
        Returns:
            True if successful, False otherwise
        """
        # Get the AnnotationService from the context
        annotation_service = self.context.services.get(CKeys.SERVICE_ANNOTATION)
        if not annotation_service:
            self.logger.error(CMsg.ERR_ANNOTATION_SERVICE_NOT_AVAILABLE)
            return False
            
        # Delegate to the AnnotationService
        return annotation_service.run_offline_annotator(session_dir, db_path)
