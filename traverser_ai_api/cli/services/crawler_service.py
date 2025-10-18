#!/usr/bin/env python3
"""
Crawler service for managing crawl processes and lifecycle.
"""

import errno
import logging
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from traverser_ai_api.cli.shared.context import CLIContext

# Import shared orchestrator components
try:
    from traverser_ai_api.cli.core.adapters import create_process_backend
    from traverser_ai_api.cli.core.controller import CrawlerOrchestrator
except ImportError:
    # Fallback for direct execution
    from traverser_ai_api.core.adapters import create_process_backend
    from traverser_ai_api.core.controller import CrawlerOrchestrator


class CrawlerService:
    """Service for managing crawler processes."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
        
        # Get paths from config
        config_service = self.context.services.get("config")
        if config_service:
            self.api_dir = os.path.dirname(os.path.abspath(__file__))
            self.base_dir = config_service.get_config_value("BASE_DIR") or self.api_dir
            self.pid_file_path = os.path.join(self.base_dir, "crawler.pid")
            self.shutdown_flag_path = config_service.get_config_value("SHUTDOWN_FLAG_PATH") or os.path.join(
                self.base_dir, "crawler_shutdown.flag"
            )
            self.pause_flag_path = config_service.get_config_value("PAUSE_FLAG_PATH") or os.path.join(
                self.base_dir, "crawler_pause.flag"
            )
        else:
            self.logger.error("Config service not available")
            raise RuntimeError("Config service is required")
        
        # Initialize shared orchestrator
        config = config_service.config
        backend = create_process_backend(use_qt=False)  # CLI uses subprocess backend
        self.orchestrator = CrawlerOrchestrator(config, backend)
        
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
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is running.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if running, False otherwise
        """
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError as err:
            return err.errno == errno.EPERM
        return True
    
    def start_crawler(self) -> bool:
        """Start the crawler process.
        
        Returns:
            True if started successfully, False otherwise
        """
        # Use the shared orchestrator to start the crawler
        success = self.orchestrator.start_crawler()
        
        if success:
            self.logger.info("Crawler started successfully via shared orchestrator")
            
            # Start output monitoring for CLI
            self.orchestrator.register_callback('log', self._handle_log_output)
            self.orchestrator.register_callback('step', self._handle_step_output)
            self.orchestrator.register_callback('action', self._handle_action_output)
            self.orchestrator.register_callback('screenshot', self._handle_screenshot_output)
            self.orchestrator.register_callback('status', self._handle_status_output)
            self.orchestrator.register_callback('focus', self._handle_focus_output)
            self.orchestrator.register_callback('end', self._handle_end_output)
            
            # Wait for the crawler process to complete (blocking)
            self._wait_for_crawler()
        else:
            self.logger.error("Failed to start crawler via shared orchestrator")
        
        return success
    
    def _wait_for_crawler(self):
        """Wait for the crawler process to complete."""
        self.logger.info("Waiting for crawler to complete...")
        
        # Get the backend process
        backend = self.orchestrator.backend
        
        # Wait for the process to finish
        if hasattr(backend, 'process') and backend.process:
            try:
                return_code = backend.process.wait()
                self.logger.info(f"Crawler process exited with code {return_code}")
            except Exception as e:
                self.logger.error(f"Error waiting for crawler: {e}")
    
    def _handle_log_output(self, message: str):
        """Handle log output from the crawler."""
        print(message)
    
    def _handle_step_output(self, step_num: int):
        """Handle step output from the crawler."""
        self.logger.debug(f"Crawler step: {step_num}")
    
    def _handle_action_output(self, action: str):
        """Handle action output from the crawler."""
        self.logger.debug(f"Crawler action: {action}")
    
    def _handle_screenshot_output(self, path: str):
        """Handle screenshot output from the crawler."""
        self.logger.debug(f"Crawler screenshot: {path}")
    
    def _handle_status_output(self, status: str):
        """Handle status output from the crawler."""
        self.logger.debug(f"Crawler status: {status}")
    
    def _handle_focus_output(self, focus_data: str):
        """Handle focus output from the crawler."""
        self.logger.debug(f"Crawler focus: {focus_data}")
    
    def _handle_end_output(self, end_status: str):
        """Handle end output from the crawler."""
        self.logger.info(f"Crawler finished with status: {end_status}")
    
    def stop_crawler(self) -> bool:
        """Stop the crawler process.
        
        Returns:
            True if signal sent successfully, False otherwise
        """
        self.logger.debug("Signaling crawler to stop...")
        
        # Use the shared orchestrator to stop the crawler
        success = self.orchestrator.stop_crawler()
        
        if success:
            self.logger.info("Crawler stop signal sent via shared orchestrator")
        else:
            self.logger.error("Failed to send crawler stop signal via shared orchestrator")
        
        return success
    
    def pause_crawler(self) -> bool:
        """Pause the crawler process.
        
        Returns:
            True if paused successfully, False otherwise
        """
        self.logger.debug("Signaling crawler to pause...")
        
        # Use the shared orchestrator to pause the crawler
        success = self.orchestrator.pause_crawler()
        
        if success:
            self.logger.info("Crawler pause signal sent via shared orchestrator")
        else:
            self.logger.error("Failed to send crawler pause signal via shared orchestrator")
        
        return success
    
    def resume_crawler(self) -> bool:
        """Resume the crawler process.
        
        Returns:
            True if resumed successfully, False otherwise
        """
        self.logger.debug("Signaling crawler to resume...")
        
        # Use the shared orchestrator to resume the crawler
        success = self.orchestrator.resume_crawler()
        
        if success:
            self.logger.info("Crawler resume signal sent via shared orchestrator")
        else:
            self.logger.error("Failed to send crawler resume signal via shared orchestrator")
        
        return success
    
    def get_status(self) -> dict:
        """Get crawler status.
        
        Returns:
            Dictionary with status information
        """
        # Use the shared orchestrator to get status
        orchestrator_status = self.orchestrator.get_status()
        
        # Convert to the format expected by CLI
        status = {
            "process": "Unknown",
            "state": "Unknown",
            "target_app": orchestrator_status["app_package"],
            "output_dir": orchestrator_status["output_dir"]
        }
        
        # Check process status
        if orchestrator_status["is_running"]:
            pid = orchestrator_status["process_id"]
            if pid:
                status["process"] = f"Running (PID {pid}, CLI-managed)"
            else:
                status["process"] = "Running (CLI-managed)"
        else:
            status["process"] = "Stopped"
        
        # Check execution state
        if orchestrator_status["is_paused"]:
            status["state"] = "Paused (pause flag is present)"
        else:
            status["state"] = "Running"
        
        return status
    
    def _monitor_crawler_output(self):
        """Monitor crawler output and log it."""
        if not self.crawler_process or not self.crawler_process.stdout:
            return
            
        pid = self.crawler_process.pid
        try:
            for line in iter(self.crawler_process.stdout.readline, ""):
                print(line, end="")
            rc = self.crawler_process.wait()
            self.logger.debug(f"Crawler (PID {pid}) exited with code {rc}.")
        except Exception as e:
            self.logger.error(f"Error monitoring crawler (PID {pid}): {e}", exc_info=True)
        finally:
            self._cleanup_pid_file_if_matches(pid)
            if self.crawler_process and self.crawler_process.pid == pid:
                self.crawler_process = None
    
    def _cleanup_pid_file_if_matches(self, pid_to_check: Optional[int]):
        """Clean up PID file if it matches the given PID.
        
        Args:
            pid_to_check: PID to check against
        """
        pid_file = Path(self.pid_file_path)
        if pid_file.exists():
            try:
                pid_in_file = int(pid_file.read_text().strip())
                if (
                    pid_to_check is not None
                    and pid_in_file == pid_to_check
                    and not self._is_process_running(pid_in_file)
                ) or (
                    pid_to_check is None and not self._is_process_running(pid_in_file)
                ):
                    pid_file.unlink()
                    self.logger.debug(
                        f"Removed PID file: {pid_file} (contained PID: {pid_in_file})"
                    )
            except (ValueError, OSError, Exception) as e:
                self.logger.warning(
                    f"Error during PID file cleanup for {pid_file}: {e}. Removing if invalid."
                )
                try:
                    pid_file.unlink()
                except OSError:
                    pass