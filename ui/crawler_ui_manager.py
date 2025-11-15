#!/usr/bin/env python3
# ui/crawler_manager.py - Crawler process management for the UI controller

import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QProcess, QRunnable, QThread, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

# Import shared orchestrator components
from core import get_process_backend, get_validation_service
from core.adapters import create_process_backend
from core.controller import CrawlerOrchestrator
from core.health_check import ValidationService
from cli.constants import keys as KEYS


class ValidationWorker(QRunnable):
    """Worker class to run validation checks asynchronously."""
    
    def __init__(self, crawler_manager):
        super().__init__()
        self.crawler_manager = crawler_manager
        self.signals = ValidationSignals()
    
    def run(self):
        """Run the validation checks in a background thread."""
        try:
            # Perform validation
            is_valid, messages = self.crawler_manager.validate_pre_crawl_requirements()
            
            # Get detailed status
            status_details = self.crawler_manager.get_service_status_details()
            
            # Emit results
            self.signals.validation_completed.emit(is_valid, messages, status_details)
            
        except Exception as e:
            logging.error(f"Error in validation worker: {e}")
            self.signals.validation_error.emit(str(e))


class ValidationSignals(QObject):
    """Signals for validation worker communication."""
    validation_completed = Signal(bool, list, dict)  # is_valid, messages, status_details
    validation_error = Signal(str)  # error_message


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
        self.step_count = 0
        self.last_action = "None"
        self.current_screenshot = None
        self.crawler_process = None
        self._shutdown_flag_file_path = self.config.SHUTDOWN_FLAG_PATH
        self.shutdown_timer = QTimer(self)
        self.shutdown_timer.setSingleShot(True)
        self.shutdown_timer.timeout.connect(self.force_stop_crawler_on_timeout)
        
        # Initialize shared orchestrator
        backend = create_process_backend(use_qt=True)  # UI uses Qt backend
        self.orchestrator = CrawlerOrchestrator(self.config, backend)
        
        # Initialize thread pool for async validation
        self.thread_pool = QThreadPool()
        self.validation_worker = None
        
        # Connect orchestrator signals to UI
        self._connect_orchestrator_signals()
    
    def _connect_orchestrator_signals(self):
        """Connect orchestrator output callbacks to UI signals."""
        # Register callbacks with the orchestrator
        self.orchestrator.register_callback('step', self._on_step_callback)
        self.orchestrator.register_callback('action', self._on_action_callback)
        self.orchestrator.register_callback('screenshot', self._on_screenshot_callback)
        self.orchestrator.register_callback('status', self._on_status_callback)
        self.orchestrator.register_callback('focus', self._on_focus_callback)
        self.orchestrator.register_callback('end', self._on_end_callback)
        self.orchestrator.register_callback('log', self._on_log_callback)
    
    def _on_step_callback(self, step_num: int):
        """Handle step callback from orchestrator."""
        self.step_count = step_num
        self.step_updated.emit(step_num)
        self.main_controller.step_label.setText(f"Step: {step_num}")
        self.update_progress()
    
    def _on_action_callback(self, action: str):
        """Handle action callback from orchestrator."""
        self.last_action = action
        self.action_updated.emit(action)
        self.main_controller.action_history.append(f"{action}")
        try:
            sb = self.main_controller.action_history.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
        except Exception:
            pass
    
    def _on_screenshot_callback(self, screenshot_path: str):
        """Handle screenshot callback from orchestrator."""
        if os.path.exists(screenshot_path):
            self.current_screenshot = screenshot_path
            self.screenshot_updated.emit(screenshot_path)
            self.main_controller.update_screenshot(screenshot_path)
    
    def _on_status_callback(self, status: str):
        """Handle status callback from orchestrator."""
        self.main_controller.status_label.setText(f"Status: {status}")
    
    def _on_focus_callback(self, focus_data: str):
        """Handle focus callback from orchestrator."""
        try:
            import json
            focus_data_dict = json.loads(focus_data)
            self.main_controller.log_action_with_focus(focus_data_dict)
        except Exception as e:
            self.main_controller.log_message(f"Error parsing focus data: {e}", "red")
            logging.error(f"Error parsing focus data: {e}")
    
    def _on_end_callback(self, end_status: str):
        """Handle end callback from orchestrator."""
        # Log the status but don't play audio here - let handle_process_finished handle it
        # This callback is just for logging purposes, not for determining completion
        self.main_controller.log_message(f"Final status: {end_status}", "blue")
    
    def _on_log_callback(self, message: str):
        """Handle log callback from orchestrator."""
        # Parse log level and color
        color = 'white'
        log_message = message
        
        prefixes = {
            '[INFO]': 'blue',
            'INFO:': 'blue',
            '[WARNING]': 'orange',
            'WARNING:': 'orange',
            '[ERROR]': 'red',
            'ERROR:': 'red',
            '[CRITICAL]': 'red',
            'CRITICAL:': 'red',
            '[DEBUG]': 'gray',
            'DEBUG:': 'gray',
        }
        
        for prefix, p_color in prefixes.items():
            if message.startswith(prefix):
                log_message = message[len(prefix):].lstrip()
                color = p_color
                break
        
        self.main_controller.log_message(log_message, color)
    
    def validate_pre_crawl_requirements(self) -> Tuple[bool, List[str]]:
        """
        Validate all pre-crawl requirements before starting the crawler.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        # Use ValidationService for validation
        health_service = ValidationService(self.config)
        services_status = health_service.check_all_services()
        
        issues = []
        warnings = []
        
        # Extract issues and warnings from service status
        for service_name, status in services_status.items():
            status_type = status.get(KEYS.STATUS_KEY_STATUS, '')
            message = status.get(KEYS.STATUS_KEY_MESSAGE, '')
            
            if status_type == KEYS.STATUS_ERROR:
                issues.append(f"❌ {service_name}: {message}")
            elif status_type == KEYS.STATUS_WARNING:
                warnings.append(f"⚠️ {service_name}: {message}")
        
        # Combine issues and warnings for display
        all_messages = issues + warnings
        
        return len(issues) == 0, all_messages
    
    # Removed duplicate health check methods - now using ValidationService
    # These methods were replaced by ValidationService to eliminate code duplication
    
    def get_service_status_details(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed status information about all services.
        
        Returns:
            Dictionary with service status details
        """
        # Use the shared validation service
        validation_service = get_validation_service(self.config)
        return validation_service.get_service_status_details()
    
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
        """Start the crawler process without validation checks."""
        self.main_controller.log_message("🚀 Starting crawler...", 'blue')

        # Check if app package is selected
        app_package = self.config.get('APP_PACKAGE', None)
        if not app_package:
            self.main_controller.log_message(
                "ERROR: No target app selected. Please scan for and select a health app before starting the crawler.",
                'red'
            )
            return

        self._start_crawler_process()

    @Slot()
    def perform_pre_crawl_validation(self):
        """Perform pre-crawl validation checks asynchronously."""
        self.main_controller.log_message("🔍 Performing pre-crawl validation checks...", 'blue')
        self.main_controller.log_message("⏳ Checking services (this may take a few seconds)...", 'blue')
        
        # Show loading overlay
        self.main_controller.show_busy("Validating services and requirements...")
        
        # Create and start validation worker
        self.validation_worker = ValidationWorker(self)
        self.validation_worker.signals.validation_completed.connect(self._on_validation_completed)
        self.validation_worker.signals.validation_error.connect(self._on_validation_error)
        
        # Start the worker in the thread pool
        self.thread_pool.start(self.validation_worker)
    
    @Slot(bool, list, dict)
    def _on_validation_completed(self, is_valid: bool, messages: List[str], status_details: Dict[str, Any]):
        """Handle validation completion."""
        # Hide loading overlay
        self.main_controller.hide_busy()
        
        # Separate blocking issues from warnings
        blocking_issues = [msg for msg in messages if msg.startswith("❌")]
        warnings = [msg for msg in messages if msg.startswith("⚠️")]

        # Show warnings if any
        if warnings:
            for warning in warnings:
                self.main_controller.log_message(f"   {warning}", 'orange')

        if blocking_issues:
            self.main_controller.log_message("", 'white')  # Empty line
            self.main_controller.log_message("⚠️ Some requirements are not met.", 'orange')
            self.main_controller.log_message("💡 You can still start the crawler, but it may fail if services are not available.", 'blue')
        elif warnings:
            self.main_controller.log_message("", 'white')  # Empty line
            self.main_controller.log_message("✅ Core requirements met. Warnings shown above.", 'green')

        # Show detailed status
        self._display_validation_details(status_details)
    
    @Slot(str)
    def _on_validation_error(self, error_message: str):
        """Handle validation error."""
        # Hide loading overlay
        self.main_controller.hide_busy()
        
        self.main_controller.log_message(f"❌ Validation error: {error_message}", 'red')
        logging.error(f"Validation error: {error_message}")
    
    def _display_validation_details(self, status_details: Dict[str, Any]):
        """Display detailed validation status."""
        try:
            self.main_controller.log_message("🔍 Pre-Crawl Validation Details:", 'blue')
            self.main_controller.log_message("=" * 50, 'blue')
            
            for service_name, details in status_details.items():
                if service_name in ['mobsf', 'mcp']:
                    # Special handling for optional services - use warning icon when not running
                    if details.get('running', False):
                        status_icon = "✅"
                        color = 'green'
                    else:
                        status_icon = "⚠️"
                        color = 'orange'
                    self.main_controller.log_message(f"{status_icon} {details['message']}", color)
                else:
                    # Standard handling for other services
                    status_icon = "✅" if details.get('running', details.get('valid', details.get('selected', False))) else "❌"
                    color = 'green' if details.get('running', details.get('valid', details.get('selected', False))) else 'red'
                    self.main_controller.log_message(f"{status_icon} {details['message']}", color)
                
                # Show additional details for API keys
                if service_name == 'api_keys' and details.get('issues'):
                    for issue in details['issues']:
                        self.main_controller.log_message(f"   {issue}", 'orange')
            
            self.main_controller.log_message("=" * 50, 'blue')
            
            # Count blocking issues (required services that are not running)
            blocking_issues = sum(1 for details in status_details.values() 
                                if details.get('required', True) and 
                                not details.get('running', details.get('valid', details.get('selected', False))))
            
            # Count warnings (non-required services that are not running)
            warnings = sum(1 for details in status_details.values() 
                          if not details.get('required', True) and 
                          not details.get('running', details.get('valid', details.get('selected', False))))
            
            if blocking_issues == 0 and warnings == 0:
                self.main_controller.log_message("🎉 All systems are ready for crawling!", 'green')
            elif blocking_issues == 0:
                self.main_controller.log_message(f"✅ Core requirements met. {warnings} warning(s) shown above.", 'green')
            else:
                self.main_controller.log_message(f"⚠️ {blocking_issues} blocking issue(s), {warnings} warning(s). You can still start the crawler.", 'orange')
                
        except Exception as e:
            self.main_controller.log_message(f"Error displaying validation details: {e}", 'red')
    
    def force_start_crawler(self):
        """Force start the crawler process without validation checks."""
        self.main_controller.log_message("⚠️ Force starting crawler without validation checks...", 'orange')
        self._start_crawler_process()
    
    def _start_crawler_process(self):
        """Internal method to start the actual crawler process."""
        # Check if AI model is selected
        model_type = self.config.get('DEFAULT_MODEL_TYPE', None)
        if not model_type or (isinstance(model_type, str) and model_type.strip() == ''):
            self.main_controller.log_message(
                "ERROR: No AI model selected. Please select an AI model before starting a crawl.",
                'red'
            )
            self.main_controller.log_message(
                "Use the model dropdown in the configuration panel or run: python run_cli.py <provider> select-model <model>",
                'red'
            )
            return
        
        # Check if the required dependencies are installed for the selected AI provider
        try:
            from domain.model_adapters import check_dependencies
        except ImportError:
            self.main_controller.log_message(
                "ERROR: Could not import model_adapters module. Please check your installation.",
                'red'
            )
            return
                
        ai_provider = self.config.get('AI_PROVIDER', 'gemini').lower()
        deps_installed, error_msg = check_dependencies(ai_provider)
        
        if not deps_installed:
            self.main_controller.log_message(
                f"ERROR: Missing dependencies for {ai_provider} provider. {error_msg}",
                'red'
            )
            return
            
        # Continue with the rest of the start_crawler logic
        # Ensure output session directories are created just-in-time for this run
        try:
            output_dir = self.config.get('OUTPUT_DATA_DIR', 'output_data')
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                self.main_controller.log_message(f"Created output directory: {output_dir}", 'blue')
        except Exception as e:
            self.main_controller.log_message(f"ERROR: Failed to prepare output directories: {e}", 'red')
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
            self.main_controller.action_history.clear()
            self.main_controller.status_label.setText("Status: Starting...")
            self.main_controller.progress_bar.setValue(0)
            self.main_controller.start_btn.setEnabled(False)
            self.main_controller.stop_btn.setEnabled(True)
            try:
                if hasattr(self.main_controller, 'generate_report_btn') and self.main_controller.generate_report_btn:
                    self.main_controller.generate_report_btn.setEnabled(False)
            except Exception:
                pass
            
            # Use the same Python executable that's running this script
            python_exe = sys.executable
            # Determine project root and set working directory
            from pathlib import Path
            from utils.paths import find_project_root
            project_root = str(find_project_root(Path(self.config.BASE_DIR)))
            self.crawler_process.setWorkingDirectory(project_root)
            
            # Choose entrypoint dynamically:
            # - Prefer package module (traverser_ai_api.main) if importable with -m
            # - Otherwise fall back to running a known script file (traverser_ai_api/main.py, main.py, run_cli.py)
            try:
                import importlib.util
            except Exception:
                importlib = None  # type: ignore
            
            module_to_run = None
            script_to_run = None
            
            try:
                if importlib and importlib.util.find_spec("traverser_ai_api.main"):
                    module_to_run = "traverser_ai_api.main"
            except Exception:
                pass
            
            if module_to_run is None:
                possible_scripts = [
                    os.path.join(project_root, "traverser_ai_api", "main.py"),
                    os.path.join(project_root, "main.py"),
                    os.path.join(project_root, "run_cli.py"),
                ]
                for p in possible_scripts:
                    if os.path.isfile(p):
                        script_to_run = p
                        break
            
            if module_to_run:
                self.main_controller.log_message(f"Starting crawler with: {python_exe} -m {module_to_run} crawler start", 'blue')
                # Start Python in unbuffered mode to stream stdout in real-time
                # Add 'crawler start' command to launch the crawler
                self.crawler_process.start(python_exe, ["-u", "-m", module_to_run, "crawler", "start"])
            elif script_to_run:
                self.main_controller.log_message(f"Starting crawler with: {python_exe} {script_to_run} crawler start", 'blue')
                # Run the script directly if module import is not available
                # Add 'crawler start' command to launch the crawler
                self.crawler_process.start(python_exe, ["-u", script_to_run, "crawler", "start"])
            else:
                self.main_controller.log_message(
                    "ERROR: Could not locate crawler entrypoint (traverser_ai_api.main or run_cli.py).",
                    'red'
                )
                return
            self.update_progress()
        else:
            self.main_controller.log_message("Crawler is already running.", 'orange')
    
    @Slot()
    def stop_crawler(self) -> None:
        """Stop the crawler process, trying graceful shutdown first."""
        if self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running:
            self.main_controller.log_message("Stopping crawler...", 'blue')
            self.main_controller.status_label.setText("Status: Stopping...")
            
            # DIAGNOSTIC: Check if shutdown flag path exists
            self.main_controller.log_message(f"DIAGNOSTIC: Shutdown flag path: {self._shutdown_flag_file_path}", 'blue')
            if os.path.exists(self._shutdown_flag_file_path):
                self.main_controller.log_message("DIAGNOSTIC: Shutdown flag already exists!", 'orange')
            
            # Create shutdown flag for graceful termination
            try:
                with open(self._shutdown_flag_file_path, 'w') as f:
                    f.write("shutdown requested")
                self.main_controller.log_message("Created shutdown flag. Waiting for crawler to exit...", 'blue')
                self.main_controller.log_message(f"DIAGNOSTIC: Shutdown flag created at: {self._shutdown_flag_file_path}", 'blue')
                
                # DIAGNOSTIC: Verify flag was created
                if os.path.exists(self._shutdown_flag_file_path):
                    self.main_controller.log_message("DIAGNOSTIC: Shutdown flag verified to exist", 'green')
                else:
                    self.main_controller.log_message("DIAGNOSTIC: ERROR - Shutdown flag not found after creation!", 'red')
                
                # Start a timer to force termination if graceful shutdown takes too long
                self.shutdown_timer.start(10000)  # 10 seconds timeout
                self.main_controller.log_message("DIAGNOSTIC: Started 10-second shutdown timer", 'blue')
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
        self.main_controller.log_message("DIAGNOSTIC: Shutdown timeout triggered - checking process state", 'orange')
        if self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running:
            self.main_controller.log_message("Crawler did not exit gracefully. Forcing termination...", 'red')
            self.main_controller.log_message(f"DIAGNOSTIC: Process PID: {self.crawler_process.processId()}", 'orange')
            self.main_controller.log_message(f"DIAGNOSTIC: Process state: {self.crawler_process.state()}", 'orange')
            
            # DIAGNOSTIC: Check if shutdown flag still exists
            if os.path.exists(self._shutdown_flag_file_path):
                self.main_controller.log_message("DIAGNOSTIC: Shutdown flag still exists - crawler not checking it!", 'red')
            else:
                self.main_controller.log_message("DIAGNOSTIC: Shutdown flag was removed - crawler ignoring it!", 'red')
            
            self.crawler_process.kill()
            self.main_controller.log_message("DIAGNOSTIC: Sent kill signal to process", 'red')
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

        # Enable report generation after finish
        try:
            if hasattr(self.main_controller, 'generate_report_btn') and self.main_controller.generate_report_btn:
                self.main_controller.generate_report_btn.setEnabled(True)
        except Exception:
            pass

        # Play audio alert based on exit status and exit code
        # This is the primary mechanism for detecting crawler completion
        try:
            if hasattr(self.main_controller, '_audio_alert'):
                # Success: Normal exit with exit code 0
                if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
                    self.main_controller._audio_alert('finish')
                # Error: Crash or non-zero exit code
                else:
                    self.main_controller._audio_alert('error')
        except Exception:
            pass

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

        # Play audio alert on error (double beep)
        try:
            if hasattr(self.main_controller, '_audio_alert'):
                self.main_controller._audio_alert('error')
        except Exception:
            pass
    
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
            
            for line in output.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue

                color = 'white'
                message = line
                
                prefixes = {
                    '[INFO]': 'blue',
                    'INFO:': 'blue',
                    '[WARNING]': 'orange',
                    'WARNING:': 'orange',
                    '[ERROR]': 'red',
                    'ERROR:': 'red',
                    '[CRITICAL]': 'red',
                    'CRITICAL:': 'red',
                    '[DEBUG]': 'gray',
                    'DEBUG:': 'gray',
                }

                for prefix, p_color in prefixes.items():
                    if line.startswith(prefix):
                        message = line[len(prefix):].lstrip()
                        color = p_color
                        break
                
                if not any(line.startswith(p) for p in ['UI_STEP:', 'UI_ACTION:', 'UI_SCREENSHOT:', 'UI_STATUS:', 'UI_FOCUS:', 'UI_END:']):
                    self.main_controller.log_message(message, color)

            # Check for UI_STEP_PREFIX:step (use last match if multiple found)
            step_matches = re.findall(r'UI_STEP:(\d+)', output)
            if step_matches:
                # Use the last step number in case of multiple matches
                self.step_count = int(step_matches[-1])
                self.main_controller.step_label.setText(f"Step: {self.step_count}")
                self.update_progress()
            
            # Check for UI_ACTION_PREFIX:action (handle multiple matches in case of buffered output)
            action_matches = re.findall(r'UI_ACTION:(.*?)(?:\n|$)', output)
            for action_text in action_matches:
                action_text = action_text.strip()
                if action_text:
                    self.last_action = action_text
                    self.main_controller.action_history.append(f"{action_text}")
                    try:
                        sb = self.main_controller.action_history.verticalScrollBar()
                        if sb:
                            sb.setValue(sb.maximum())
                    except Exception:
                        pass
            
            # Check for UI_SCREENSHOT_PREFIX:path (use last match if multiple found)
            screenshot_matches = re.findall(r'UI_SCREENSHOT:(.*?)(?:\n|$)', output)
            if screenshot_matches:
                # Use the last screenshot path in case of multiple matches
                screenshot_path = screenshot_matches[-1].strip()
                if screenshot_path and os.path.exists(screenshot_path):
                    self.current_screenshot = screenshot_path
                    self.main_controller.update_screenshot(screenshot_path)
                    
            # Check for UI_STATUS_PREFIX:status
            status_match = re.search(r'UI_STATUS:(.*?)($|\n)', output)
            if status_match:
                status_text = status_match.group(1).strip()
                self.main_controller.status_label.setText(f"Status: {status_text}")

            # Check for UI_END_PREFIX:final_status
            # Note: Audio alerts are handled by handle_process_finished based on exit code/status
            # This is just for logging purposes
            end_match = re.search(r'UI_END:(.*?)($|\n)', output)
            if end_match:
                final_status = end_match.group(1).strip()
                # Log final status line for visibility
                self.main_controller.log_message(f"Final status: {final_status}", 'blue')
                
            # Check for UI_FOCUS output lines
            focus_match = re.search(r'UI_FOCUS:(.*?)($|\n)', output)
            if focus_match:
                try:
                    focus_data_str = focus_match.group(1).strip()
                    # Parse the focus data as JSON for robustness
                    import json
                    focus_data = json.loads(focus_data_str)
                    
                    # Log the focus attribution
                    self.main_controller.log_action_with_focus(focus_data)
                except Exception as e:
                    self.main_controller.log_message(f"Error parsing focus data: {e}", 'red')
                    logging.error(f"Error parsing focus data: {e}")
        except Exception as e:
            self.main_controller.log_message(f"Error processing crawler output: {e}", 'red')
            logging.error(f"Error processing crawler output: {e}")
