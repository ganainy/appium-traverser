#!/usr/bin/env python3
"""
Crawler service for managing crawl processes and lifecycle.
"""

import errno
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

from cli.shared.context import ApplicationContext
from cli.constants.keys import (
    PROCESS_STATUS_KEY, PROCESS_ID_KEY, STATE_KEY,
    TARGET_APP_KEY, OUTPUT_DIR_KEY
)
from cli.constants.messages import (
    CRAWLER_STATUS_STOPPED, CRAWLER_STATUS_UNKNOWN,
    CRAWLER_STATUS_ERROR, CRAWLER_STATUS_RUNNING
)
from core.controller import CrawlerOrchestrator
from core.adapters import create_process_backend


class CrawlerService:
    """Service for managing crawler processes using core interface."""
    
    def __init__(self, context: ApplicationContext):
        """Initialize the crawler service."""
        self.context = context
        self.logger = logging.getLogger(__name__)
        self.orchestrator = None
        self.backend = None
        
    def _initialize_if_needed(self) -> bool:
        """Initialize orchestrator if not already initialized.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        if self.orchestrator:
            return True
        
        try:
            # Set up orchestrator and backend
            self.backend = create_process_backend()
            self.orchestrator = CrawlerOrchestrator(self.context.config, self.backend)
            self.logger.info("Crawler service initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize crawler service: {e}")
            return False
    
    def start_crawler(
        self,
        generate_pdf_after_run: bool = False,
        feature_flags: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Start the crawler process.
        
        Args:
            generate_pdf_after_run: Whether to generate PDF report after crawler completes
            feature_flags: Optional dict of feature flags to override config (e.g., {'ENABLE_TRAFFIC_CAPTURE': True})
            
        Returns:
            True if started successfully, False otherwise
        """
        try:
            # Apply feature flag overrides to config if provided
            if feature_flags:
                for flag_name, flag_value in feature_flags.items():
                    self.context.config.set(flag_name, flag_value)
                    self.logger.info(f"Applied feature flag override: {flag_name} = {flag_value}")
            
            # Initialize if needed
            if not self._initialize_if_needed():
                return False
            
            # Now we know orchestrator exists
            success = self.orchestrator.start_crawler()
            
            # Handle post-run tasks if requested
            # Run in main thread to avoid SQLite threading issues
            if success and generate_pdf_after_run:
                # Wait for crawler to complete, then run post-run tasks in main thread
                self.logger.info("Waiting for crawler to complete...")
                while self.backend.is_process_running():
                    time.sleep(2)  # Check every 2 seconds
                
                self.logger.info("Crawler completed. Running post-run tasks...")
                
                # Get analysis service
                analysis_service = self.context.services.get("analysis")
                if not analysis_service:
                    self.logger.warning("Analysis service not available for post-run tasks.")
                else:
                    # Wait a moment for filesystem to catch up, then find latest session
                    # Retry multiple times with increasing delays in case the directory/database is still being created
                    session_info = None
                    max_attempts = 10
                    for attempt in range(max_attempts):
                        if attempt > 0:
                            # Progressive delay: 1s, 2s, 3s, etc. up to 5s max
                            delay = min(attempt, 5)
                            time.sleep(delay)
                        session_info = analysis_service.find_latest_session_dir()
                        if session_info:
                            break
                        if attempt < max_attempts - 1:
                            self.logger.debug(f"Attempt {attempt + 1}/{max_attempts}: Session directory not found yet, retrying in {min(attempt + 1, 5)}s...")
                    
                    if not session_info:
                        self.logger.error("Could not find latest session directory for post-run tasks after retries. The database file may not have been created yet, or the session may not have written any data.")
                    else:
                        session_dir, db_path = session_info
                        self.logger.info(f"Found latest session: {session_dir}")
                        
                        # Run PDF generation if requested
                        if generate_pdf_after_run:
                            self.logger.info("Generating PDF report...")
                            # Parse session directory to get target info
                            from utils.paths import SessionPathManager
                            target_info = SessionPathManager.parse_session_dir(Path(session_dir), self.context.config)
                            if target_info:
                                pdf_success, pdf_result = analysis_service.generate_analysis_pdf(target_info)
                                if pdf_success:
                                    pdf_path = pdf_result.get("pdf_path", "Unknown")
                                    self.logger.info(f"PDF generation completed successfully. PDF saved to: {pdf_path}")
                                else:
                                    error = pdf_result.get("error", "Unknown error")
                                    self.logger.error(f"PDF generation failed: {error}")
                            else:
                                self.logger.error("Could not parse session directory for PDF generation.")
            
            return success
        except Exception as e:
            self.logger.error(f"Failed to start crawler: {e}")
            return False
    
    def stop_crawler(self) -> bool:
        """Stop the crawler process.
        
        Returns:
            True if signal sent successfully, False otherwise
        """
        try:
            # Not failing if not initialized, just return False
            if not self.orchestrator:
                self.logger.warning("Crawler orchestrator not initialized, considering stopped")
                return False
                
            return self.orchestrator.stop_crawler()
        except Exception as e:
            self.logger.error(f"Failed to stop crawler: {e}")
            return False
    
    def pause_crawler(self) -> bool:
        """Pause the crawler process.
        
        Returns:
            True if paused successfully, False otherwise
        """
        try:
            # Initialize if needed
            if not self._initialize_if_needed():
                return False
            
            # Now we know orchestrator exists
            return self.orchestrator.pause_crawler()
        except Exception as e:
            self.logger.error(f"Failed to pause crawler: {e}")
            return False
    
    def resume_crawler(self) -> bool:
        """Resume the crawler process.
        
        Returns:
            True if resumed successfully, False otherwise
        """
        try:
            # Initialize if needed
            if not self._initialize_if_needed():
                return False
            
            # Now we know orchestrator exists
            return self.orchestrator.resume_crawler()
        except Exception as e:
            self.logger.error(f"Failed to resume crawler: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get crawler status.
        
        Returns:
            Dictionary with raw status information
        """
        try:
            # Not failing if not initialized, return stopped status
            if not self.orchestrator:
                return {
                    PROCESS_STATUS_KEY: CRAWLER_STATUS_STOPPED,
                    PROCESS_ID_KEY: None,
                    STATE_KEY: CRAWLER_STATUS_UNKNOWN,
                    TARGET_APP_KEY: None,
                    OUTPUT_DIR_KEY: None
                }
                
            status = self.orchestrator.get_status()
            
            if status:
                # Return raw status data without formatting
                return {
                    PROCESS_STATUS_KEY: CRAWLER_STATUS_RUNNING,
                    PROCESS_ID_KEY: status.get("process_id"),
                    STATE_KEY: status.get("state", CRAWLER_STATUS_RUNNING),
                    TARGET_APP_KEY: status.get("app_package"),
                    OUTPUT_DIR_KEY: status.get("output_dir")
                }
            else:
                return {
                    PROCESS_STATUS_KEY: CRAWLER_STATUS_STOPPED,
                    PROCESS_ID_KEY: None,
                    STATE_KEY: CRAWLER_STATUS_UNKNOWN,
                    TARGET_APP_KEY: None,
                    OUTPUT_DIR_KEY: None
                }
        except Exception as e:
            self.logger.error(f"Failed to get crawler status: {e}")
            return {
                PROCESS_STATUS_KEY: CRAWLER_STATUS_ERROR,
                PROCESS_ID_KEY: None,
                STATE_KEY: CRAWLER_STATUS_UNKNOWN,
                TARGET_APP_KEY: None,
                OUTPUT_DIR_KEY: None
            }
    
    def cleanup(self):
        """Clean up any resources before shutdown."""
        self.logger.info("Cleaning up crawler service...")
        try:
            # Save references since we'll be clearing them
            orchestrator = self.orchestrator
            backend = self.backend
            
            if orchestrator:
                try:
                    orchestrator.stop_crawler()
                except Exception as e:
                    self.logger.error(f"Error stopping orchestrator: {e}")
                    
            if backend:
                try:
                    backend.stop_process()
                except Exception as e:
                    self.logger.error(f"Error stopping backend process: {e}")
            
            # Clear references only after successful cleanup 
            self.orchestrator = None
            self.backend = None
                
            self.logger.info("Crawler service cleanup complete")
        except Exception as e:
            self.logger.error(f"Error during crawler service cleanup: {e}")
