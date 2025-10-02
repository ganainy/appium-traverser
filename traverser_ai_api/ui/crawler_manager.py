#!/usr/bin/env python3
# ui/crawler_manager.py - Crawler process management for the UI controller

import os
import logging
import sys
import re
import requests
import subprocess
from typing import Optional, Dict, Any, List, Tuple
from PySide6.QtCore import QObject, QProcess, QTimer, Slot, Signal, QThread, QRunnable, QThreadPool
from PySide6.QtWidgets import QApplication


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
        self.crawler_process: Optional[QProcess] = None
        self.step_count = 0
        self.last_action = "None"
        self.current_screenshot = None
        self._shutdown_flag_file_path = self.config.SHUTDOWN_FLAG_PATH
        self.shutdown_timer = QTimer(self)
        self.shutdown_timer.setSingleShot(True)
        self.shutdown_timer.timeout.connect(self.force_stop_crawler_on_timeout)
        
        # Initialize thread pool for async validation
        self.thread_pool = QThreadPool()
        self.validation_worker = None
    
    def validate_pre_crawl_requirements(self) -> Tuple[bool, List[str]]:
        """
        Validate all pre-crawl requirements before starting the crawler.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        warnings = []
        
        # 1. Check Appium server
        if not self._check_appium_server():
            issues.append("❌ Appium server is not running or not accessible")
        
        # 2. Check Ollama (if selected as AI provider)
        ai_provider = getattr(self.config, 'AI_PROVIDER', 'gemini').lower()
        if ai_provider == 'ollama':
            if not self._check_ollama_service():
                issues.append("❌ Ollama service is not running")
        
        # 3. Check API keys and required environment variables
        api_issues, api_warnings = self._check_api_keys_and_env()
        issues.extend(api_issues)
        warnings.extend(api_warnings)
        
        # 4. Check target app is selected
        if not getattr(self.config, 'APP_PACKAGE', None):
            issues.append("❌ No target app selected")
        
        # Combine issues and warnings for display
        all_messages = issues + warnings
        
        return len(issues) == 0, all_messages
    
    def _check_appium_server(self) -> bool:
        """Check if Appium server is running and accessible."""
        try:
            appium_url = getattr(self.config, 'APPIUM_SERVER_URL', 'http://127.0.0.1:4723')
            # Try to connect to Appium status endpoint with shorter timeout
            response = requests.get(f"{appium_url}/status", timeout=3)
            if response.status_code == 200:
                status_data = response.json()
                # Check for 'ready' field, handling both direct and nested formats
                if status_data.get('ready', False) or status_data.get('value', {}).get('ready', False):
                    return True
        except Exception as e:
            logging.debug(f"Appium server check failed: {e}")
        
        return False
    
    def _check_mobsf_server(self) -> bool:
        """Check if MobSF server is running and accessible."""
        try:
            mobsf_url = getattr(self.config, 'MOBSF_API_URL', 'http://localhost:8000/api/v1')
            # Try to connect to MobSF API with shorter timeout
            response = requests.get(f"{mobsf_url}/server_status", timeout=3)
            if response.status_code == 200:
                return True
        except Exception as e:
            logging.debug(f"MobSF server check failed: {e}")
        
        return False
    
    def _check_ollama_service(self) -> bool:
        """Check if Ollama service is running using HTTP API first, then subprocess fallback."""
        # First try HTTP API check (fast and non-blocking)
        ollama_url = getattr(self.config, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        
        try:
            # Try to connect to Ollama API endpoint with shorter timeout
            response = requests.get(f"{ollama_url}/api/tags", timeout=1.5)
            if response.status_code == 200:
                logging.debug("Ollama service detected via HTTP API")
                return True
        except requests.RequestException as e:
            logging.debug(f"Ollama HTTP API check failed: {e}")
        except Exception as e:
            logging.debug(f"Unexpected error during Ollama HTTP check: {e}")
        
        # Fallback to subprocess check if HTTP fails
        try:
            result = subprocess.run(['ollama', 'list'],
                                capture_output=True,
                                text=True,
                                timeout=2,  # Reduced from 3 seconds
                                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            if result.returncode == 0:
                logging.debug("Ollama service detected via subprocess")
                return True
        except subprocess.TimeoutExpired:
            logging.debug("Ollama subprocess check timed out")
        except FileNotFoundError:
            logging.debug("Ollama executable not found")
        except subprocess.SubprocessError as e:
            logging.debug(f"Ollama subprocess check failed: {e}")
        except Exception as e:
            logging.debug(f"Unexpected error during Ollama subprocess check: {e}")
        
        logging.debug("Ollama service not detected")
        return False
    
    def _check_api_keys_and_env(self) -> Tuple[List[str], List[str]]:
        """Check if required API keys and environment variables are provided.
        
        Returns:
            Tuple of (blocking_issues, warnings)
        """
        issues = []
        warnings = []
        ai_provider = getattr(self.config, 'AI_PROVIDER', 'gemini').lower()
        
        if ai_provider == 'gemini':
            if not getattr(self.config, 'GEMINI_API_KEY', None):
                issues.append("❌ Gemini API key is not set (check GEMINI_API_KEY in .env file)")
        
        elif ai_provider == 'openrouter':
            if not getattr(self.config, 'OPENROUTER_API_KEY', None):
                issues.append("❌ OpenRouter API key is not set (check OPENROUTER_API_KEY in .env file)")
        
        elif ai_provider == 'ollama':
            if not getattr(self.config, 'OLLAMA_BASE_URL', None):
                warnings.append("⚠️ Ollama base URL not set (using default localhost:11434)")
        
        # Check PCAPdroid API key if traffic capture is enabled
        if getattr(self.config, 'ENABLE_TRAFFIC_CAPTURE', False):
            if not getattr(self.config, 'PCAPDROID_API_KEY', None):
                issues.append("❌ PCAPdroid API key is not set (check PCAPDROID_API_KEY in .env file)")
        
        # Check MobSF API key if MobSF analysis is enabled
        if getattr(self.config, 'ENABLE_MOBSF_ANALYSIS', False):
            if not getattr(self.config, 'MOBSF_API_KEY', None):
                issues.append("❌ MobSF API key is not set (check MOBSF_API_KEY in .env file)")
        
        return issues, warnings
    
    def get_service_status_details(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed status information about all services.
        
        Returns:
            Dictionary with service status details
        """
        details = {}
        
        # Appium status
        appium_running = self._check_appium_server()
        appium_url = getattr(self.config, 'APPIUM_SERVER_URL', 'http://127.0.0.1:4723')
        details['appium'] = {
            'running': appium_running,
            'url': appium_url,
            'required': True,
            'message': f"Appium server at {appium_url}" + (" is running ✅" if appium_running else " is not accessible ❌")
        }
        
        # MobSF status (always check, but mark as optional)
        mobsf_running = self._check_mobsf_server()
        mobsf_url = getattr(self.config, 'MOBSF_API_URL', 'http://localhost:8000/api/v1')
        mobsf_enabled = getattr(self.config, 'ENABLE_MOBSF_ANALYSIS', False)
        details['mobsf'] = {
            'running': mobsf_running,
            'url': mobsf_url,
            'required': False,  # MobSF is now optional
            'enabled': mobsf_enabled,
            'message': f"MobSF server at {mobsf_url}" + (" is running ✅" if mobsf_running else " is not accessible ⚠️")
        }
        
        # Ollama status
        ai_provider = getattr(self.config, 'AI_PROVIDER', 'gemini').lower()
        if ai_provider == 'ollama':
            ollama_running = self._check_ollama_service()
            details['ollama'] = {
                'running': ollama_running,
                'required': True,
                'message': "Ollama service" + (" is running ✅" if ollama_running else " is not running ❌")
            }
        
        # API Keys status
        api_issues, api_warnings = self._check_api_keys_and_env()
        all_api_messages = api_issues + api_warnings
        details['api_keys'] = {
            'valid': len(api_issues) == 0,  # Only blocking issues make it invalid
            'issues': all_api_messages,
            'required': True,
            'message': f"API keys: {len(api_issues)} issue(s), {len(api_warnings)} warning(s)" if all_api_messages else "API keys: All required keys present ✅"
        }
        
        # Target app
        app_package = getattr(self.config, 'APP_PACKAGE', None)
        details['target_app'] = {
            'selected': app_package is not None,
            'package': app_package,
            'required': True,
            'message': f"Target app: {app_package}" if app_package else "Target app: Not selected ❌"
        }
        
        return details
    
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
        app_package = getattr(self.config, 'APP_PACKAGE', None)
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
        
        # Create and start validation worker
        self.validation_worker = ValidationWorker(self)
        self.validation_worker.signals.validation_completed.connect(self._on_validation_completed)
        self.validation_worker.signals.validation_error.connect(self._on_validation_error)
        
        # Start the worker in the thread pool
        self.thread_pool.start(self.validation_worker)
    
    @Slot(bool, list, dict)
    def _on_validation_completed(self, is_valid: bool, messages: List[str], status_details: Dict[str, Any]):
        """Handle validation completion."""
        # Separate blocking issues from warnings
        blocking_issues = [msg for msg in messages if msg.startswith("❌")]
        warnings = [msg for msg in messages if msg.startswith("⚠️")]

        if not is_valid:
            self.main_controller.log_message("❌ Pre-crawl validation failed:", 'red')
            for issue in blocking_issues:
                self.main_controller.log_message(f"   {issue}", 'red')
        elif warnings:
            self.main_controller.log_message("⚠️ Pre-crawl validation completed with warnings:", 'orange')
        else:
            self.main_controller.log_message("✅ All pre-crawl checks passed!", 'green')

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
        self.main_controller.log_message(f"❌ Validation error: {error_message}", 'red')
        logging.error(f"Validation error: {error_message}")
    
    def _display_validation_details(self, status_details: Dict[str, Any]):
        """Display detailed validation status."""
        try:
            self.main_controller.log_message("🔍 Pre-Crawl Validation Details:", 'blue')
            self.main_controller.log_message("=" * 50, 'blue')
            
            for service_name, details in status_details.items():
                if service_name == 'mobsf':
                    # Special handling for MobSF - use warning icon for non-required service
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
            
        # Continue with the rest of the start_crawler logic
        # Ensure output session directories are created just-in-time for this run
        try:
            self.config._resolve_all_paths(create_session_dirs=True)
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
                
            # Check for UI_FOCUS_PREFIX:focus_info
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
