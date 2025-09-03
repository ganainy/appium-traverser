#!/usr/bin/env python3
# ui/crawler_manager.py - Crawler process management for the UI controller

import os
import logging
import sys
import re
from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, QProcess, QTimer, Slot, Signal


class CrawlerManager(QObject):
    """Manages the crawler process for the Appium Crawler Controller."""
    
    # Signals
    step_updated = Signal(int)
    action_updated = Signal(str)
    screenshot_updated = Signal(str)
    
    def __init__(self, main_controller):
        """
        Initialize the crawler manager.
        
        Args:
            main_controller: The main UI controller
        """
        super().__init__()
        self.main_controller = main_controller
        self.config = main_controller.config
        self.crawler_process: Optional[QProcess] = None
        self.step_count = 0
        self.last_action = "None"
        self.current_screenshot = None
        self._shutdown_flag_file_path = self.config.SHUTDOWN_FLAG_PATH
        self.shutdown_timer = QTimer(self)
        self.shutdown_timer.setSingleShot(True)
        self.shutdown_timer.timeout.connect(self.force_stop_crawler_on_timeout)
    
    def update_progress(self):
        """Update the progress bar based on the current step count."""
        if self.main_controller.config_widgets['CRAWL_MODE'].currentText() == 'steps':
            max_steps = self.main_controller.config_widgets['MAX_CRAWL_STEPS'].value()
            self.main_controller.progress_bar.setRange(0, max_steps if max_steps > 0 else 0)
            if max_steps > 0:
                self.main_controller.progress_bar.setValue(min(self.step_count, max_steps))
        else:
            # For time-based crawl, use indeterminate progress bar
            self.main_controller.progress_bar.setRange(0, 0)
    
    @Slot()
    def start_crawler(self):
        """Start the crawler process."""
        # Check if app package is selected
        app_package = getattr(self.config, 'APP_PACKAGE', None)
        if not app_package:
            self.main_controller.log_message(
                "ERROR: No target app selected. Please scan for and select a health app before starting the crawler.",
                'red'
            )
            return
            
        # Check if the required dependencies are installed for the selected AI provider
        try:
            from traverser_ai_api.model_adapters import check_dependencies
        except ImportError:
            try:
                from model_adapters import check_dependencies
            except ImportError:
                self.main_controller.log_message(
                    "ERROR: Could not import model_adapters module. Please check your installation.",
                    'red'
                )
                return
                
        ai_provider = getattr(self.config, 'AI_PROVIDER', 'gemini').lower()
        deps_installed, error_msg = check_dependencies(ai_provider)
        
        if not deps_installed:
            self.main_controller.log_message(
                f"ERROR: Missing dependencies for {ai_provider} provider. {error_msg}",
                'red'
            )
            return
            
        if self._shutdown_flag_file_path and os.path.exists(self._shutdown_flag_file_path):
            try:
                os.remove(self._shutdown_flag_file_path)
                self.main_controller.log_message("Removed existing shutdown flag.", 'blue')
            except Exception as e:
                self.main_controller.log_message(
                    f"Warning: Could not remove existing shutdown flag: {e}", 'orange'
                )

        if hasattr(self.main_controller, 'log_output'):
            self.main_controller.log_message("Starting crawler...", 'blue')
        else:
            logging.debug("Starting crawler...")

        if not self.crawler_process or self.crawler_process.state() == QProcess.ProcessState.NotRunning:
            # Configure and start the process
            self.crawler_process = QProcess()
            self.crawler_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            self.crawler_process.readyReadStandardOutput.connect(self.read_stdout)
            self.crawler_process.finished.connect(self.handle_process_finished)
            self.crawler_process.errorOccurred.connect(self.handle_process_error)
            
            # Reset tracking variables
            self.step_count = 0
            self.last_action = "None"
            self.current_screenshot = None
            
            # Update UI
            self.main_controller.step_label.setText("Step: 0")
            self.main_controller.last_action_label.setText("Last Action: None")
            self.main_controller.status_label.setText("Status: Starting...")
            self.main_controller.progress_bar.setValue(0)
            self.main_controller.start_btn.setEnabled(False)
            self.main_controller.stop_btn.setEnabled(True)
            
            # Use the same Python executable that's running this script
            python_exe = sys.executable
            script_path = os.path.join(self.config.BASE_DIR, "main.py")
            
            # Start the process
            self.main_controller.log_message(f"Starting crawler with: {python_exe} {script_path}", 'blue')
            self.crawler_process.start(python_exe, [script_path])
            self.update_progress()
        else:
            self.main_controller.log_message("Crawler is already running.", 'orange')
    
    @Slot()
    def stop_crawler(self) -> None:
        """Stop the crawler process, trying graceful shutdown first."""
        if self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running:
            self.main_controller.log_message("Stopping crawler...", 'blue')
            self.main_controller.status_label.setText("Status: Stopping...")
            
            # Create shutdown flag for graceful termination
            try:
                with open(self._shutdown_flag_file_path, 'w') as f:
                    f.write("shutdown requested")
                self.main_controller.log_message("Created shutdown flag. Waiting for crawler to exit...", 'blue')
                
                # Start a timer to force termination if graceful shutdown takes too long
                self.shutdown_timer.start(10000)  # 10 seconds timeout
            except Exception as e:
                self.main_controller.log_message(f"Error creating shutdown flag: {e}", 'red')
                # Fallback to termination
                self.crawler_process.terminate()
                self.main_controller.log_message("Terminated crawler process.", 'orange')
        else:
            self.main_controller.log_message("No crawler process running.", 'orange')
    
    @Slot()
    def force_stop_crawler_on_timeout(self) -> None:
        """Force stop the crawler process if it doesn't respond to graceful shutdown."""
        if self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running:
            self.main_controller.log_message("Crawler did not exit gracefully. Forcing termination...", 'red')
            self.crawler_process.kill()
        else:
            self.main_controller.log_message("Crawler process already exited.", 'green')
    
    @Slot(int, QProcess.ExitStatus)
    def handle_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle the crawler process finishing."""
        self.shutdown_timer.stop()
        if self._shutdown_flag_file_path and os.path.exists(self._shutdown_flag_file_path):
            try:
                os.remove(self._shutdown_flag_file_path)
                self.main_controller.log_message("Removed shutdown flag.", 'blue')
            except Exception as e:
                self.main_controller.log_message(f"Warning: Could not remove shutdown flag: {e}", 'orange')
        
        status_text = f"Finished. Exit code: {exit_code}"
        if exit_status == QProcess.ExitStatus.CrashExit:
            status_text = f"Crashed. Exit code: {exit_code}"
        
        final_msg = f"Status: {status_text}"
        if hasattr(self.main_controller, 'log_output'):
            self.main_controller.log_message(f"Crawler process {status_text}", 'blue')
        else:
            logging.debug(f"Crawler process {status_text}")
        
        if hasattr(self.main_controller, 'status_label'):
            self.main_controller.status_label.setText(final_msg)
        
        if hasattr(self.main_controller, 'start_btn'):
            self.main_controller.start_btn.setEnabled(True)
        
        if hasattr(self.main_controller, 'stop_btn'):
            self.main_controller.stop_btn.setEnabled(False)
        
        if hasattr(self.main_controller, 'progress_bar'):
            self.main_controller.progress_bar.setRange(0, 100)
            self.main_controller.progress_bar.setValue(100 if exit_status == QProcess.ExitStatus.NormalExit else 0)
        
        self.crawler_process = None
    
    @Slot(QProcess.ProcessError)
    def handle_process_error(self, error: QProcess.ProcessError):
        """Handle crawler process errors."""
        try:
            error_name = {
                QProcess.ProcessError.FailedToStart: "Failed to start",
                QProcess.ProcessError.Crashed: "Crashed",
                QProcess.ProcessError.Timedout: "Timed out",
                QProcess.ProcessError.ReadError: "Read error",
                QProcess.ProcessError.WriteError: "Write error",
                QProcess.ProcessError.UnknownError: "Unknown error"
            }.get(error, f"Error code: {error}")
        except Exception:
            error_name = f"Error code: {error}"
        
        error_message = f"Crawler process error: {error_name}"
        output_details = ""
        
        try:
            if self.crawler_process:
                output_details = bytes(self.crawler_process.readAllStandardOutput().data()).decode('utf-8', errors='replace')
        except Exception as e:
            logging.error(f"Could not read process output: {e}")
            
        if output_details:
            error_message += f"\nProcess output: {output_details}"
        
        self.main_controller.log_message(error_message, 'red')
        logging.error(error_message)
        
        # Cleanup
        if self.crawler_process:
            try:
                if self.crawler_process.state() == QProcess.ProcessState.Running:
                    self.crawler_process.kill()
                    self.main_controller.log_message("Killed crawler process.", 'orange')
            except Exception as e:
                logging.error(f"Error killing process: {e}")
        
        self.crawler_process = None
        self.main_controller.start_btn.setEnabled(True)
        self.main_controller.stop_btn.setEnabled(False)
        self.main_controller.status_label.setText(f"Status: Error ({error_name})")
        self.main_controller.progress_bar.setRange(0, 100)
        self.main_controller.progress_bar.setValue(0)
    
    @Slot()
    def read_stdout(self) -> None:
        """Handle stdout from the crawler process."""
        if not self.crawler_process:
            return
        
        raw_data = self.crawler_process.readAllStandardOutput().data()
        if not raw_data:
            return
            
        try:
            output = bytes(raw_data).decode('utf-8', errors='replace')
            
            # Display the raw output in the log
            self.main_controller.log_message(output.strip())
            
            # Check for UI_STEP_PREFIX:step
            step_match = re.search(r'UI_STEP:(\d+)', output)
            if step_match:
                self.step_count = int(step_match.group(1))
                self.main_controller.step_label.setText(f"Step: {self.step_count}")
                self.update_progress()
            
            # Check for UI_ACTION_PREFIX:action
            action_match = re.search(r'UI_ACTION:(.*?)($|\n)', output)
            if action_match:
                self.last_action = action_match.group(1).strip()
                self.main_controller.last_action_label.setText(f"Last Action: {self.last_action}")
            
            # Check for UI_SCREENSHOT_PREFIX:path
            screenshot_match = re.search(r'UI_SCREENSHOT:(.*?)($|\n)', output)
            if screenshot_match:
                screenshot_path = screenshot_match.group(1).strip()
                if os.path.exists(screenshot_path):
                    self.current_screenshot = screenshot_path
                    self.main_controller.update_screenshot(screenshot_path)
                    
            # Check for UI_STATUS_PREFIX:status
            status_match = re.search(r'UI_STATUS:(.*?)($|\n)', output)
            if status_match:
                status_text = status_match.group(1).strip()
                self.main_controller.status_label.setText(f"Status: {status_text}")
                
            # Check for UI_END_PREFIX:reason
            end_match = re.search(r'UI_END:(.*?)($|\n)', output)
            if end_match:
                end_reason = end_match.group(1).strip()
                self.main_controller.log_message(f"Crawler ended: {end_reason}", 'orange')
        except Exception as e:
            self.main_controller.log_message(f"Error processing crawler output: {e}", 'red')
            logging.error(f"Error processing crawler output: {e}")
