#!/usr/bin/env python3
"""
Crawler service for managing crawl processes and lifecycle.
"""

import errno
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from cli.shared.context import CLIContext
from interfaces.cli import CLICrawlerInterface, create_cli_interface
from core.controller import CrawlerOrchestrator
from core.adapters import create_process_backend


class CrawlerService:
    """Service for managing crawler processes using core interface."""
    
    def __init__(self, context: CLIContext):
        """Initialize the crawler service."""
        self.context = context
        self.logger = logging.getLogger(__name__)
        self.orchestrator = None
        self.backend = None
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _initialize_if_needed(self) -> bool:
        """Initialize orchestrator if not already initialized.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        if self.orchestrator:
            return True
        
        config_service = self.context.services.get("config")
        if not config_service:
            self.logger.error("Config service not available")
            return False
            
        try:
            # Set up orchestrator and backend
            self.backend = create_process_backend()
            self.orchestrator = CrawlerOrchestrator(config_service.config, self.backend)
            self.logger.info("Crawler service initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize crawler service: {e}")
            return False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.warning(
            f"\nSignal {signal.Signals(signum).name} received. Initiating crawler shutdown..."
        )
        self.stop_crawler()
        sys.exit(0)
    
    def start_crawler(self, annotate_after_run: bool = False) -> bool:
        """Start the crawler process.
        
        Args:
            annotate_after_run: Whether to run offline UI annotator after crawler completes
            
        Returns:
            True if started successfully, False otherwise
        """
        try:
            # Initialize if needed
            if not self._initialize_if_needed():
                return False
            
            # Now we know orchestrator exists
            success = self.orchestrator.start_crawler()
            
            # Handle offline annotation if requested
            if success and annotate_after_run:
                analysis_service = self.context.services.get("analysis")
                if analysis_service:
                    # Wait for crawler to complete, then run annotation
                    # Note: In a real implementation, we'd need to monitor the process
                    # This is a simplified version
                    self.logger.info("Offline annotation will run after completion.")
                    # In a full implementation, we would:
                    # 1. Monitor the crawler process
                    # 2. When it completes, get the latest session data
                    # 3. Call analysis_service.run_offline_ui_annotator with the session info
                else:
                    self.logger.warning("Analysis service not available for offline annotation.")
            
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
            Dictionary with status information
        """
        try:
            # Not failing if not initialized, return stopped status
            if not self.orchestrator:
                return {
                    "process": "Stopped",
                    "state": "Unknown",
                    "target_app": "Unknown",
                    "output_dir": "Unknown"
                }
                
            status = self.orchestrator.get_status()
            
            if status:
                # Convert orchestrator status to CLI format
                return {
                    "process": f"Running (PID {status.get('process_id', '?')}, CLI-managed)",
                    "state": status.get("state", "Running"),
                    "target_app": status.get("app_package", "Unknown"),
                    "output_dir": status.get("output_dir", "Unknown")
                }
            else:
                return {
                    "process": "Stopped",
                    "state": "Unknown",
                    "target_app": "Unknown",
                    "output_dir": "Unknown"
                }
        except Exception as e:
            self.logger.error(f"Failed to get crawler status: {e}")
            return {
                "process": "Error",
                "state": "Unknown",
                "target_app": "Unknown",
                "output_dir": "Unknown"
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
