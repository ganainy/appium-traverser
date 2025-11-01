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
from typing import Optional

from traverser_ai_api.cli.shared.context import CLIContext
from traverser_ai_api.interfaces.cli import CLICrawlerInterface, create_cli_interface


class CrawlerService:
    """Service for managing crawler processes using core interface."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
        
        # Get config from context
        config_service = self.context.services.get("config")
        if config_service:
            # Convert config service config to dict for CLI interface
            config_dict = {
                "name": "CLI Crawler Config",
                "settings": {
                    "max_depth": config_service.get_config_value("MAX_DEPTH", 10),
                    "timeout": config_service.get_config_value("TIMEOUT", 300),
                    "platform": config_service.get_config_value("PLATFORM", "android")
                }
            }
            self.cli_interface = create_cli_interface(config_dict)
            self.logger.info("CLI Crawler Interface initialized")
        else:
            self.logger.error("Config service not available")
            raise RuntimeError("Config service is required")
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.warning(
            f"\nSignal {signal.Signals(signum).name} received. Initiating crawler shutdown..."
        )
        self.stop_crawler()
        sys.exit(0)
    
    def start_crawler(self) -> bool:
        """Start the crawler process.
        
        Returns:
            True if started successfully, False otherwise
        """
        try:
            session_id = self.cli_interface.start_crawler_session()
            if session_id:
                self.logger.info(f"Crawler session started: {session_id}")
                return True
            else:
                self.logger.error("Failed to start crawler session")
                return False
        except Exception as e:
            self.logger.error(f"Failed to start crawler: {e}")
            return False
    
    def stop_crawler(self) -> bool:
        """Stop the crawler process.
        
        Returns:
            True if signal sent successfully, False otherwise
        """
        try:
            success = self.cli_interface.stop_crawler_session()
            if success:
                self.logger.info("Crawler session stopped successfully")
            else:
                self.logger.error("Failed to stop crawler session")
            return success
        except Exception as e:
            self.logger.error(f"Failed to stop crawler: {e}")
            return False
    
    def pause_crawler(self) -> bool:
        """Pause the crawler process.
        
        Returns:
            True if paused successfully, False otherwise
        """
        self.logger.warning("Pause/resume not implemented in core interface yet")
        return False
    
    def resume_crawler(self) -> bool:
        """Resume the crawler process.
        
        Returns:
            True if resumed successfully, False otherwise
        """
        self.logger.warning("Pause/resume not implemented in core interface yet")
        return False
    
    def get_status(self) -> dict:
        """Get crawler status.
        
        Returns:
            Dictionary with status information
        """
        try:
            status = self.cli_interface.get_session_status()
            if status:
                # Convert to the format expected by CLI
                cli_status = {
                    "process": f"Running (Session {status['session_id']})",
                    "state": status["status"],
                    "target_app": "Unknown",  # Not available in core interface yet
                    "output_dir": "Unknown"   # Not available in core interface yet
                }
                return cli_status
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
