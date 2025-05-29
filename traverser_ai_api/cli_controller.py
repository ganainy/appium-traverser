#!/usr/bin/env python3
"""
CLI Controller for Appium Crawler
Uses the centralized Config class.
"""

import sys
import os
import logging 
import json
import argparse
import subprocess
import signal
import time
import threading
import errno # For PID checking
from typing import Optional, Dict, Any, List
from pathlib import Path

# --- Imports for Config and Logging Utilities ---
try:
    from config import Config
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import 'Config' class from config.py: {e}\n")
    sys.stderr.write("Ensure config.py exists and contains the Config class definition.\n")
    sys.exit(1)

try:
    from utils import SCRIPT_START_TIME, LoggerManager, ElapsedTimeFormatter
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import logging utilities from utils.py: {e}\n")
    sys.stderr.write("Ensure utils.py exists and contains SCRIPT_START_TIME, LoggerManager, and ElapsedTimeFormatter.\n")
    if 'SCRIPT_START_TIME' not in globals():
        SCRIPT_START_TIME = time.time() 
    sys.exit(1)

# Need textwrap for the epilog in create_parser, import early
import textwrap


class CLIController:
    """Command-line controller for the Appium Crawler."""

    def __init__(self, app_config_instance: Config):
        self.cfg = app_config_instance
        self.api_dir = os.path.dirname(os.path.abspath(__file__))
        self.find_app_info_script_path = os.path.join(self.api_dir, "find_app_info.py")
        self.health_apps_data: List[Dict[str, Any]] = []
        
        if not self.cfg.BASE_DIR or not os.path.isdir(self.cfg.BASE_DIR):
            fallback_dir = self.api_dir if os.path.isdir(self.api_dir) else os.getcwd()
            logging.warning(f"cfg.BASE_DIR ('{self.cfg.BASE_DIR}') is not a valid directory. Using fallback directory ('{fallback_dir}') for PID file.")
            self.pid_file_path = os.path.join(fallback_dir, "crawler.pid")
        else:
            self.pid_file_path = os.path.join(self.cfg.BASE_DIR, "crawler.pid")
        logging.debug(f"PID file will be managed at: {self.pid_file_path}")

        self.crawler_process: Optional[subprocess.Popen] = None

        self._setup_cli_specific_directories()

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        if self.cfg.CURRENT_HEALTH_APP_LIST_FILE and os.path.exists(self.cfg.CURRENT_HEALTH_APP_LIST_FILE):
            logging.info(f"Attempting to auto-load health apps from: {self.cfg.CURRENT_HEALTH_APP_LIST_FILE}")
            self._load_health_apps_from_file(self.cfg.CURRENT_HEALTH_APP_LIST_FILE)
        else:
            logging.info("No pre-existing health app list file found in configuration or file does not exist.")

    def _setup_cli_specific_directories(self):
        pass

    def _is_process_running(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError as err:
            if err.errno == errno.ESRCH: 
                return False # No such process
            elif err.errno == errno.EPERM: 
                return True # Permission denied means process exists
            else: 
                # Other OS error
                logging.debug(f"Unknown OSError when checking PID {pid}: {err}")
                return False # Can't determine, assume not running for safety
        except Exception as e: # Catch any other exception
            logging.debug(f"Exception when checking PID {pid}: {e}")
            return False
        return True # Signal 0 sent successfully, process exists

    def _signal_handler(self, signum, frame):
        logging.warning(f"\nSignal {signal.Signals(signum).name} received by CLI. Initiating crawler shutdown via flag...")
        self.stop_crawler() # This will now create the flag
        # If this CLI instance is managing the crawler_process directly,
        # the monitor thread for that process should handle its termination.
        # If stop_crawler also attempts to join/wait, it might conflict.
        # For now, stop_crawler just sets the flag.
        logging.info("CLI shutdown signal handled. Crawler (if running) should stop.")
        sys.exit(0) # Exit CLI

    def save_all_changes(self) -> bool:
        logging.info("Attempting to save all current configuration settings...")
        try:
            self.cfg.save_user_config()
            return True
        except Exception as e:
            logging.error(f"Failed to save configuration via CLIController: {e}", exc_info=True)
            return False

    def show_config(self, filter_key: Optional[str] = None):
        config_to_display = self.cfg._get_user_savable_config() 
        print("\n=== Current Configuration (via CLIController) ===")
        if not config_to_display:
            print("No configuration settings available to display.")
        for key, value in sorted(config_to_display.items()):
            if filter_key and filter_key.lower() not in key.lower():
                continue
            if isinstance(value, list):
                print(f"  {key}: {', '.join(map(str, value))}")
            else:
                print(f"  {key}: {value}")
        print("===============================================")

    def set_config_value(self, key: str, value_str: str) -> bool:
        logging.info(f"CLI attempting to set config: {key} = '{value_str}'")
        try:
            self.cfg.update_setting_and_save(key, value_str) 
            return True
        except Exception as e:
            logging.error(f"CLI failed to set config for {key}: {e}", exc_info=True)
            return False

    def scan_apps(self, force_rescan: bool = False) -> bool:
        if not force_rescan and self.cfg.CURRENT_HEALTH_APP_LIST_FILE and os.path.exists(self.cfg.CURRENT_HEALTH_APP_LIST_FILE):
            logging.info(f"Using cached health app list: {self.cfg.CURRENT_HEALTH_APP_LIST_FILE}")
            return self._load_health_apps_from_file(self.cfg.CURRENT_HEALTH_APP_LIST_FILE)

        if not os.path.exists(self.find_app_info_script_path):
            logging.error(f"find_app_info.py script not found at {self.find_app_info_script_path}")
            return False

        logging.info("Starting health app scan via find_app_info.py...")
        try:
            process_cwd = self.api_dir 
            logging.debug(f"Running find_app_info.py from CWD: {process_cwd}")
            result = subprocess.run(
                [sys.executable, '-u', self.find_app_info_script_path, '--mode', 'discover'],
                cwd=process_cwd, 
                capture_output=True, text=True, timeout=300, check=False
            )
            logging.debug(f"find_app_info.py stdout:\n{result.stdout}")
            logging.debug(f"find_app_info.py stderr:\n{result.stderr}")

            if result.returncode != 0:
                logging.error(f"App scan script failed with exit code {result.returncode}.\nStderr: {result.stderr}")
                return False
            
            output_lines = result.stdout.splitlines()
            cache_file_line = next((line for line in output_lines if "Cache file generated at:" in line), None)
            if not cache_file_line:
                logging.error(f"Could not find cache file path in scan output.\nStdout: {result.stdout}")
                return False
            
            cache_file_path = cache_file_line.split("Cache file generated at:", 1)[1].strip()
            if not os.path.exists(cache_file_path):
                # The script might output a path relative to its own location if not absolute
                potential_abs_path = os.path.join(self.api_dir, cache_file_path)
                if not os.path.exists(potential_abs_path):
                    logging.error(f"Cache file reported by script not found at '{cache_file_path}' or '{potential_abs_path}'")
                    return False
                cache_file_path = potential_abs_path
                logging.debug(f"Resolved cache file path to: {cache_file_path}")

            self.cfg.update_setting_and_save('CURRENT_HEALTH_APP_LIST_FILE', cache_file_path)
            return self._load_health_apps_from_file(cache_file_path)
        except subprocess.TimeoutExpired:
            logging.error("App scan timed out after 5 minutes.")
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred during app scan: {e}", exc_info=True)
            return False

    def _load_health_apps_from_file(self, file_path: str) -> bool:
        logging.debug(f"Loading health apps from file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict): # Assuming new format {"apps": [...]}
                self.health_apps_data = data.get('apps', [])
            elif isinstance(data, list): # Support old list format
                self.health_apps_data = data
            else:
                logging.warning(f"Unexpected data structure in health app file: {file_path}.")
                self.health_apps_data = []
                return False
            if not self.health_apps_data:
                logging.info(f"No health-related apps found or loaded from {file_path}.")
            else:
                logging.info(f"Successfully loaded {len(self.health_apps_data)} health apps from {file_path}")
            return True
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in health app file {file_path}: {e}")
            self.health_apps_data = []
            return False
        except Exception as e:
            logging.error(f"Error loading health apps from file {file_path}: {e}", exc_info=True)
            self.health_apps_data = []
            return False

    def list_apps(self):
        if not self.health_apps_data:
            logging.info("No health apps loaded. Run 'scan-apps' or ensure 'CURRENT_HEALTH_APP_LIST_FILE' in config points to a valid file.")
            return
        print(f"\n=== Available Health Apps ({len(self.health_apps_data)}) ===")
        for i, app in enumerate(self.health_apps_data):
            app_name = app.get('app_name', 'N/A')
            package_name = app.get('package_name', 'N/A')
            activity_name = app.get('activity_name', 'N/A')
            print(f"{i+1:2d}. App Name: {app_name}\n     Package:  {package_name}\n     Activity: {activity_name}\n")
        print("===================================")

    def select_app(self, app_identifier: str) -> bool:
        if not self.health_apps_data:
            logging.error("No health apps loaded. Run 'scan-apps' first.")
            return False
        selected_app: Optional[Dict[str, Any]] = None
        try:
            index = int(app_identifier) - 1
            if 0 <= index < len(self.health_apps_data):
                selected_app = self.health_apps_data[index]
        except ValueError:
            app_identifier_lower = app_identifier.lower()
            for app in self.health_apps_data:
                if (app_identifier_lower in app.get('app_name', '').lower() or
                    app_identifier_lower == app.get('package_name', '').lower()):
                    selected_app = app
                    break
        if not selected_app:
            logging.error(f"App '{app_identifier}' not found in the loaded list.")
            return False
        app_package = selected_app.get('package_name')
        app_activity = selected_app.get('activity_name')
        app_name = selected_app.get('app_name', app_package if app_package else "Unknown App") # Default app_name
        if not app_package or not app_activity:
            logging.error(f"Selected app '{app_name}' is missing required package_name or activity_name.")
            return False
        logging.info(f"Selecting app: '{app_name}' (Package: {app_package}, Activity: {app_activity})")
        self.cfg.update_setting_and_save('APP_PACKAGE', app_package)
        self.cfg.update_setting_and_save('APP_ACTIVITY', app_activity)
        # Store more comprehensive info if available
        self.cfg.update_setting_and_save('LAST_SELECTED_APP', {
            'package_name': app_package, 'activity_name': app_activity, 'app_name': app_name
        })
        return True

    def start_crawler(self) -> bool:
        if not self.cfg.SHUTDOWN_FLAG_PATH:
            logging.error("Shutdown flag path is not configured (cfg.SHUTDOWN_FLAG_PATH). Cannot start crawler.")
            return False
        # Ensure no shutdown flag from a previous run is present
        if os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
            logging.warning(f"Removing existing shutdown flag: {self.cfg.SHUTDOWN_FLAG_PATH} before starting.")
            try:
                os.remove(self.cfg.SHUTDOWN_FLAG_PATH)
            except OSError as e:
                logging.error(f"Could not remove existing shutdown flag: {e}. Start aborted.")
                return False

        main_script_path = os.path.join(self.api_dir, 'main.py') 

        if os.path.exists(self.pid_file_path):
            try:
                with open(self.pid_file_path, 'r') as pf:
                    pid_str = pf.read().strip()
                    if not pid_str: # Empty PID file
                        logging.warning(f"PID file {self.pid_file_path} is empty. Removing.")
                        os.remove(self.pid_file_path)
                    else:
                        pid = int(pid_str)
                        if self._is_process_running(pid):
                            logging.warning(f"Crawler process seems to be already running with PID {pid} (from PID file: {self.pid_file_path}). If this is incorrect, remove the PID file and any shutdown flag.")
                            return False
                        else: 
                            logging.info(f"Stale PID file found ({self.pid_file_path} for PID {pid}). Process not running. Removing PID file.")
                            os.remove(self.pid_file_path)
            except (ValueError, OSError) as e:
                logging.warning(f"Error processing PID file {self.pid_file_path}: {e}. Removing if exists.")
                if os.path.exists(self.pid_file_path):
                    try: os.remove(self.pid_file_path)
                    except OSError: pass # Ignore error if removal fails here
        
        if self.crawler_process and self.crawler_process.poll() is None:
            logging.warning(f"Crawler process (managed by this CLI instance) already running with PID {self.crawler_process.pid}. Start aborted.")
            return False

        if not self.cfg.APP_PACKAGE or not self.cfg.APP_ACTIVITY:
            logging.error("APP_PACKAGE and APP_ACTIVITY must be set. Select an app using 'select-app'.")
            return False

        logging.info("Starting crawler process with current configuration...")
        try:
            project_root_dir = Path(self.api_dir).parent.resolve().as_posix()
            logging.debug(f"Attempting to start crawler script '{main_script_path}' from CWD: '{project_root_dir}'")

            env = os.environ.copy()
            current_pythonpath = env.get('PYTHONPATH', '')
            # Prepend project root to PYTHONPATH to help with relative imports in the crawler process
            env['PYTHONPATH'] = project_root_dir + os.pathsep + current_pythonpath
            
            # The main.py script will be responsible for its own detailed logging.
            # This Popen captures stdout/stderr for the CLI to display.
            self.crawler_process = subprocess.Popen(
                [sys.executable, '-u', main_script_path], # -u for unbuffered output
                cwd=project_root_dir, # Run from project root
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, # Combine stderr into stdout
                text=True, bufsize=1, universal_newlines=True, # Line buffered
                encoding='utf-8', errors='replace', env=env
            )
            try:
                with open(self.pid_file_path, 'w') as pf:
                    pf.write(str(self.crawler_process.pid))
                logging.info(f"Crawler process started with PID {self.crawler_process.pid}. PID written to {self.pid_file_path}.")
            except IOError as e:
                # Crawler started, but PID file could not be written. Stop might not find it easily.
                logging.error(f"Failed to write PID file {self.pid_file_path}: {e}. Crawler started, but --stop might need manual PID if it relies on this file and main.py doesn't create its own.")

            # Start a thread to monitor and print the crawler's output
            threading.Thread(target=self._monitor_crawler_output, daemon=True).start()
            return True
        except FileNotFoundError: 
            logging.error(f"Python interpreter '{sys.executable}' not found. Cannot start crawler.")
            return False
        except Exception as e:
            logging.error(f"Failed to start crawler process (script: {main_script_path}): {e}", exc_info=True)
            # Clean up PID file if process definitely didn't start or Popen failed critically
            if self.crawler_process is None and os.path.exists(self.pid_file_path):
                 # Check if the PID in the file (if any) matches a failed attempt vs a pre-existing one
                 # For simplicity, if Popen failed and self.crawler_process is None, we assume the PID file might be ours and stale.
                 # This needs careful handling if multiple CLIs could try to start.
                 # However, start_crawler already has PID check logic at the beginning.
                 pass # Let the initial check in start_crawler or status handle stale PID files.
            return False

    def _monitor_crawler_output(self):
        if not self.crawler_process or not self.crawler_process.stdout:
            logging.debug("Monitor: Crawler process or its stdout not available for current CLI instance.")
            return
        
        process_pid = self.crawler_process.pid # Capture PID for logging in case self.crawler_process is cleared

        try:
            # Read and print output line by line
            for line in iter(self.crawler_process.stdout.readline, ''):
                if not line: break # EOF
                print(line, end='') # Print line as it comes
            # self.crawler_process.stdout.close() # Not strictly necessary, Popen.wait() handles pipe closure.
            return_code = self.crawler_process.wait() # Wait for the process to complete
            logging.info(f"Crawler process PID {process_pid} exited with code {return_code}.")
        except Exception as e:
            # This could be due to pipe issues or other errors during monitoring
            logging.error(f"Error monitoring crawler output for PID {process_pid}: {e}", exc_info=True)
        finally:
            logging.info(f"Crawler output monitoring thread for PID {process_pid} finished.")
            # The crawler (main.py) should ideally remove its own PID file.
            # This cleanup is a fallback or for cases where main.py crashes hard.
            self._cleanup_pid_file_if_matches(process_pid)
            # Clear the process object if it's the one we were monitoring and it has exited
            if self.crawler_process and self.crawler_process.pid == process_pid:
                 self.crawler_process = None


    def stop_crawler(self) -> bool:
        logging.info("Attempting to signal crawler to stop via shutdown flag...")
        if not self.cfg.SHUTDOWN_FLAG_PATH:
            logging.error("SHUTDOWN_FLAG_PATH is not configured. Cannot signal crawler to stop.")
            return False

        pid_in_file: Optional[int] = None
        pid_source_info = "No PID identified"

        if self.crawler_process and self.crawler_process.poll() is None:
            pid_in_file = self.crawler_process.pid
            pid_source_info = f"PID {pid_in_file} (managed by this CLI instance)"
            logging.info(f"Signaling active crawler process {pid_source_info}.")
        elif os.path.exists(self.pid_file_path):
            try:
                with open(self.pid_file_path, 'r') as pf:
                    pid_str = pf.read().strip()
                if pid_str:
                    pid_in_file = int(pid_str)
                    pid_source_info = f"PID {pid_in_file} (from PID file: {self.pid_file_path})"
                    if self._is_process_running(pid_in_file):
                        logging.info(f"Found running crawler process {pid_source_info}.")
                    else:
                        logging.info(f"Stale PID file found for {pid_source_info}. Process not running. Flag will be set anyway.")
                        # The crawler won't pick up the flag if not running. start_crawler should clean the flag.
                        # self._cleanup_pid_file_if_matches(pid_in_file) # Clean up stale PID file
                else: # PID file is empty
                    logging.warning(f"PID file {self.pid_file_path} is empty. Flag will be set anyway.")
                    pid_source_info = f"Empty PID file at {self.pid_file_path}"
                    if os.path.exists(self.pid_file_path): 
                        try: 
                            os.remove(self.pid_file_path)
                        except OSError: 
                            pass

            except (ValueError, OSError) as e:
                logging.warning(f"Error reading PID from {self.pid_file_path}: {e}. Flag will be set anyway.")
                pid_source_info = f"Error reading PID file {self.pid_file_path}"
        else:
            pid_source_info = "No CLI-managed process and no PID file found"
            logging.info(f"{pid_source_info}. Flag will be set for any running crawler.")

        try:
            with open(self.cfg.SHUTDOWN_FLAG_PATH, 'w') as f:
                f.write("stop") 
            logging.info(f"Shutdown flag created at: {self.cfg.SHUTDOWN_FLAG_PATH}.")
            
            if pid_in_file and self._is_process_running(pid_in_file):
                 logging.info(f"Crawler process {pid_source_info} should detect this flag and initiate a graceful shutdown.")
            elif pid_in_file : # PID was identified but process not running
                 logging.info(f"Process {pid_source_info} was not running. Flag set; crawler (if restarted) or next run will see it.")
                 self._cleanup_pid_file_if_matches(pid_in_file) # Clean up if confirmed stale
            else: # No PID identified
                 logging.info("If a crawler instance is running, it should detect this flag.")
            
            # The crawler process is responsible for its own shutdown and cleanup of the flag/PID file.
            # CLI's job is to set the flag.
            return True
        except Exception as e:
            logging.error(f"Failed to create shutdown flag at {self.cfg.SHUTDOWN_FLAG_PATH}: {e}", exc_info=True)
            return False


    def _cleanup_pid_file_if_matches(self, pid_to_check: Optional[int]):
        # This function is called by the monitor thread when a CLI-managed process exits,
        # or can be called by status/start if a stale PID file is found.
        if os.path.exists(self.pid_file_path):
            pid_in_file_str = ""
            try:
                pid_in_file = -1
                with open(self.pid_file_path, 'r') as pf:
                    pid_in_file_str = pf.read().strip()
                
                if not pid_in_file_str: # Empty PID file
                    logging.debug(f"PID file {self.pid_file_path} is empty during cleanup check. Removing.")
                    os.remove(self.pid_file_path)
                    return

                pid_in_file = int(pid_in_file_str)
                
                # Check if the process in the PID file is actually running
                process_in_pid_file_is_running = self._is_process_running(pid_in_file)
                
                should_remove = False
                if pid_to_check is not None: # Specific PID to check (e.g., from a process that just exited)
                    if pid_in_file == pid_to_check:
                        if not process_in_pid_file_is_running: # The specific process we cared about is gone
                            should_remove = True
                            logging.debug(f"PID file for exited PID {pid_to_check} matches. Removing PID file.")
                        # else: It matches, but it's somehow still running? Or _is_process_running is unreliable. Log.
                        #    logging.warning(f"PID file matches PID {pid_to_check}, but it's unexpectedly still reported as running.")
                    # else: PID file is for a different process, don't touch it based on pid_to_check.
                elif not process_in_pid_file_is_running: # General cleanup: PID in file is for a non-running process (stale)
                    should_remove = True
                    logging.debug(f"PID {pid_in_file} from PID file is not running (stale). Removing PID file.")
                
                if should_remove:
                    os.remove(self.pid_file_path)
                    logging.info(f"Removed PID file: {self.pid_file_path} (contained PID: {pid_in_file})")
                else:
                    logging.debug(f"PID file {self.pid_file_path} (for PID {pid_in_file}) not removed: "
                                  f"pid_to_check={pid_to_check}, process_in_pid_file_is_running={process_in_pid_file_is_running}")

            except ValueError: # Invalid content in PID file
                logging.warning(f"Invalid content '{pid_in_file_str}' in PID file {self.pid_file_path} during cleanup. Removing.")
                try: os.remove(self.pid_file_path)
                except OSError as e_rem: logging.warning(f"Could not remove invalid PID file: {e_rem}")
            except OSError as e: # Error during file operations
                logging.warning(f"OSError during PID file cleanup for {self.pid_file_path}: {e}")
            except Exception as e_gen:
                 logging.error(f"Unexpected error during _cleanup_pid_file_if_matches: {e_gen}", exc_info=True)


    def _cleanup_after_stop(self, flag_was_created:bool, stopped_pid: Optional[int]):
        # This method's role changes. The crawler itself handles flag removal.
        # The crawler (main.py) should handle PID file removal on its exit.
        # This CLI method is mostly for internal CLI state.
        logging.debug(f"_cleanup_after_stop called by CLI (flag_created: {flag_was_created}, pid_context: {stopped_pid}). Crawler manages its own flag/PID cleanup.")
        
        # If the CLI was managing a specific crawler_process instance and it was associated with stopped_pid,
        # and we are sure it's stopped, we can clear self.crawler_process.
        # However, the _monitor_crawler_output thread is better suited to clear self.crawler_process
        # when the Popen object actually terminates.
        if self.crawler_process and stopped_pid is not None and self.crawler_process.pid == stopped_pid:
            # If we are very sure it's stopped (e.g. poll() is not None), then we can clear.
            # if self.crawler_process.poll() is not None:
            #    self.crawler_process = None
            # But it's safer to let the monitor thread do this.
            pass


    def status(self):
        print("\n=== CLI Crawler Status ===")
        active_pid: Optional[int] = None
        pid_file_path_to_report = self.pid_file_path # Could be from config or fallback
        status_message = "  Crawler Process: Unknown (check logs)" # Default
        pid_file_status_note = ""


        if self.crawler_process and self.crawler_process.poll() is None:
            active_pid = self.crawler_process.pid
            status_message = f"  Crawler Process: Running (PID: {active_pid}, managed by current CLI instance)"
            pid_file_status_note = f"(PID file: {pid_file_path_to_report})"
        elif os.path.exists(pid_file_path_to_report): 
            pid_from_file_str = ""
            try:
                with open(pid_file_path_to_report, 'r') as pf:
                    pid_from_file_str = pf.read().strip()
                if not pid_from_file_str: 
                     status_message = f"  Crawler Process: PID file ({pid_file_path_to_report}) is empty. Assuming stopped."
                     pid_file_status_note = "(Action: Consider removing empty PID file)"
                     # Optionally remove it here if desired, but be cautious
                     # try: 
                     #     os.remove(pid_file_path_to_report)
                     #     logging.info(f"Removed empty PID file during status check: {pid_file_path_to_report}")
                     # except OSError as e: logging.warning(f"Could not remove empty PID file {pid_file_path_to_report}: {e}")
                else:
                    pid_from_file = int(pid_from_file_str)
                    if self._is_process_running(pid_from_file):
                        active_pid = pid_from_file
                        status_message = f"  Crawler Process: Running (PID: {active_pid} from PID file)"
                        pid_file_status_note = f"(PID file: {pid_file_path_to_report})"
                    else:
                        status_message = f"  Crawler Process: Stale PID file (PID {pid_from_file} not running)."
                        pid_file_status_note = f"(PID file: {pid_file_path_to_report})"
                        # Optionally remove stale PID file
                        # try: 
                        #     os.remove(pid_file_path_to_report)
                        #     logging.info(f"Removed stale PID file during status check: {pid_file_path_to_report}")
                        # except OSError as e:
                        #     logging.warning(f"Could not remove stale PID file {pid_file_path_to_report} during status check: {e}")
            except ValueError: # Invalid content
                 status_message = f"  Crawler Process: Invalid content in PID file ('{pid_from_file_str}')."
                 pid_file_status_note = f"(PID file: {pid_file_path_to_report})"
                 # Optionally remove
            except OSError as e: # Read error
                status_message = f"  Crawler Process: Error reading PID file: {e}"
                pid_file_status_note = f"(PID file: {pid_file_path_to_report})"
        else: # No CLI managed process, no PID file
            status_message = "  Crawler Process: Stopped (no active CLI-managed process or PID file)"
        
        print(status_message)
        if pid_file_status_note : print(f"                     {pid_file_status_note}")
        
        last_selected = self.cfg.LAST_SELECTED_APP
        if self.cfg.APP_PACKAGE and self.cfg.APP_ACTIVITY:
            app_name_display = last_selected.get('app_name', 'N/A') if isinstance(last_selected, dict) else self.cfg.APP_PACKAGE
            print(f"  Target App:      '{app_name_display}' ({self.cfg.APP_PACKAGE})")
        else:
            print("  Target App:      Not Selected")
        
        if self.health_apps_data:
            print(f"  Health Apps:     {len(self.health_apps_data)} app(s) loaded from '{Path(self.cfg.CURRENT_HEALTH_APP_LIST_FILE).name if self.cfg.CURRENT_HEALTH_APP_LIST_FILE and os.path.exists(self.cfg.CURRENT_HEALTH_APP_LIST_FILE) else 'N/A'}'")
        else:
            health_list_file = self.cfg.CURRENT_HEALTH_APP_LIST_FILE
            file_status = "N/A"
            if health_list_file:
                file_status = f"'{Path(health_list_file).name}' (exists: {os.path.exists(health_list_file)})"
            print(f"  Health Apps:     None loaded (source file: {file_status})")

        print(f"  Log Level:       {self.cfg.LOG_LEVEL}")
        shutdown_flag_status = "Not Configured"
        if self.cfg.SHUTDOWN_FLAG_PATH:
            shutdown_flag_status = f"{self.cfg.SHUTDOWN_FLAG_PATH} (exists: {os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH)})"
        print(f"  Shutdown Flag:   {shutdown_flag_status}")
        print(f"  PID File Path:   {pid_file_path_to_report}") # Show the actual path used
        print("========================")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI Controller for Appium Crawler.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
Examples:
  %(prog)s status
  %(prog)s scan-apps
  %(prog)s list-apps
  %(prog)s select-app "Your App Name"  # Or use index: %(prog)s select-app 1
  %(prog)s show-config
  %(prog)s set-config MAX_CRAWL_STEPS=50
  %(prog)s set-config ALLOWED_EXTERNAL_PACKAGES="com.example.one,com.example.two"
  %(prog)s save-config                 # Explicitly save any pending changes to user_config.json
  %(prog)s start
  %(prog)s stop
        """)
    )
    app_group = parser.add_argument_group('App Management')
    app_group.add_argument('--scan-apps', action='store_true', help='Scan device for health-related apps and update config.')
    app_group.add_argument('--list-apps', action='store_true', help='List available health apps from the last scan.')
    app_group.add_argument('--select-app', metavar='APP_NAME_OR_INDEX', help='Select app by name or 1-based index to set as target.')

    crawler_group = parser.add_argument_group('Crawler Control')
    crawler_group.add_argument('--start', action='store_true', help='Start the crawler with current configuration.')
    crawler_group.add_argument('--stop', action='store_true', help='Signal the running crawler to stop gracefully via a flag.')
    crawler_group.add_argument('--status', action='store_true', help='Show current status of the CLI controller and crawler.')

    config_group = parser.add_argument_group('Configuration Management')
    config_group.add_argument('--show-config', metavar='FILTER_KEY', nargs='?', const='', help='Show current configuration (optionally filter by key).')
    config_group.add_argument('--set-config', metavar='KEY=VALUE', action='append', help='Set a configuration value (e.g., MAX_CRAWL_STEPS=100). For lists, use comma-separated values.')
    config_group.add_argument('--save-config', action='store_true', help='Explicitly save all current config settings to user_config.json.')
    
    parser.add_argument('--force-rescan', action='store_true', help='Force app rescan even if a cached list exists.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose DEBUG logging for the CLI session.')
    return parser

def main_cli():
    parser = create_parser()
    args = parser.parse_args()

    bootstrap_log_level = 'DEBUG' if args.verbose else 'INFO'
    
    existing_root_handlers = logging.root.handlers[:]
    for handler in existing_root_handlers:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=bootstrap_log_level,
        format=f"%(asctime)s [{SCRIPT_START_TIME:.0f}] [%(levelname)s] %(message)s (bootstrap)",
        datefmt='%H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)] 
    )
    logging.info("CLI Bootstrap logging initialized.")

    _cli_script_dir = os.path.dirname(os.path.abspath(__file__))
    DEFAULT_CONFIG_MODULE_PATH_CLI = os.path.join(_cli_script_dir, 'config.py') 
    USER_CONFIG_JSON_PATH_CLI = os.path.join(_cli_script_dir, "user_config.json")

    try:
        cli_cfg = Config(
            defaults_module_path=DEFAULT_CONFIG_MODULE_PATH_CLI,
            user_config_json_path=USER_CONFIG_JSON_PATH_CLI
        )
        # Ensure SHUTDOWN_FLAG_PATH has a default if not in user_config.json
        # This might be better placed in Config class default_config or __init__
        if not cli_cfg.SHUTDOWN_FLAG_PATH: # Check if it's None or empty
             default_flag_path = os.path.join(cli_cfg.BASE_DIR or _cli_script_dir, "crawler_shutdown.flag")
             cli_cfg.SHUTDOWN_FLAG_PATH = default_flag_path # Set it on the instance
             # No need to save here, it's a runtime default if not configured
             logging.info(f"SHUTDOWN_FLAG_PATH was not set, using default: {default_flag_path}")
        logging.debug(f"Config object initialized. Shutdown flag path: {cli_cfg.SHUTDOWN_FLAG_PATH}")

    except Exception as e:
        logging.critical(f"Failed to initialize Config object for CLI: {e}", exc_info=True)
        sys.exit(100)

    logger_manager_cli = LoggerManager() 
    
    _log_base_dir_cli = _cli_script_dir 
    if cli_cfg.OUTPUT_DATA_DIR:
        output_data_parent = os.path.dirname(cli_cfg.OUTPUT_DATA_DIR) if cli_cfg.OUTPUT_DATA_DIR else None
        if output_data_parent and os.path.isdir(output_data_parent): 
            _log_base_dir_cli = cli_cfg.OUTPUT_DATA_DIR
        elif cli_cfg.OUTPUT_DATA_DIR and not output_data_parent : # OUTPUT_DATA_DIR is a root path like "output_data"
            _log_base_dir_cli = cli_cfg.OUTPUT_DATA_DIR # Use it directly
        else: # Parent does not exist or OUTPUT_DATA_DIR is not suitable
            logging.warning(f"Parent of cfg.OUTPUT_DATA_DIR ('{output_data_parent}') is not valid or OUTPUT_DATA_DIR itself ('{cli_cfg.OUTPUT_DATA_DIR}') is problematic. CLI logs will be in script directory.")
            
    _final_log_dir_cli = os.path.join(_log_base_dir_cli, "logs", "cli") 
    
    try:
        os.makedirs(_final_log_dir_cli, exist_ok=True)
    except OSError as e:
        logging.error(f"Failed to create CLI log directory '{_final_log_dir_cli}': {e}. Using script directory for logs.")
        _final_log_dir_cli = _cli_script_dir 
        try: os.makedirs(_final_log_dir_cli, exist_ok=True)
        except OSError as e_fallback: logging.critical(f"Failed to create fallback CLI log directory '{_final_log_dir_cli}': {e_fallback}")


    _final_log_file_path_cli = os.path.join(_final_log_dir_cli, f"cli_{cli_cfg.LOG_FILE_NAME}")
    
    effective_log_level_str = 'DEBUG' if args.verbose else str(cli_cfg.LOG_LEVEL).upper()
    
    for handler in logging.root.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout: 
            logging.root.removeHandler(handler)
            break 
            
    root_logger_cli = logger_manager_cli.setup_logging(
        log_level_str=effective_log_level_str, 
        log_file=_final_log_file_path_cli,
    )
    root_logger_cli.info(f"CLI Application Logging Initialized. Level: {effective_log_level_str}. File: '{_final_log_file_path_cli}'")
    if args.verbose and str(cli_cfg.LOG_LEVEL).upper() != 'DEBUG':
        root_logger_cli.info(f"CLI session is verbose (--verbose), but app default LOG_LEVEL is {cli_cfg.LOG_LEVEL}.")

    controller = CLIController(app_config_instance=cli_cfg)
    
    action_taken = False
    exit_code = 0
    try:
        if args.scan_apps:
            action_taken = True
            if not controller.scan_apps(force_rescan=args.force_rescan): exit_code = 1
        if args.list_apps and exit_code == 0:
            action_taken = True
            controller.list_apps()
        if args.select_app and exit_code == 0:
            action_taken = True
            if not controller.select_app(args.select_app): exit_code = 1
        if args.show_config is not None and exit_code == 0: # nargs='?' means it's present if --show-config is used
            action_taken = True
            controller.show_config(args.show_config if args.show_config else None) # Pass actual value or None
        if args.set_config and exit_code == 0:
            action_taken = True
            for config_item in args.set_config:
                if '=' not in config_item:
                    logging.error(f"Invalid config format '{config_item}'. Use KEY=VALUE"); exit_code = 1; break
                key, value_str = config_item.split('=', 1)
                if not controller.set_config_value(key, value_str): exit_code = 1; break
        if args.save_config and exit_code == 0:
            action_taken = True
            if not controller.save_all_changes(): exit_code = 1
        
        if args.status: 
            action_taken = True
            controller.status() 
        
        if args.start: 
            action_taken = True
            if exit_code == 0: # Only start if previous config commands were successful
                if not controller.start_crawler(): 
                    exit_code = 1 # Start command itself failed
                else: 
                    # If start_crawler returns True, it means Popen succeeded.
                    # Now wait for the process if it's managed by this CLI instance.
                    try:
                        if controller.crawler_process: 
                            # This wait will block until the crawler process (main.py) finishes.
                            # The _monitor_crawler_output thread will print its output.
                            controller.crawler_process.wait() 
                            # At this point, the crawler process has exited.
                            # The monitor thread should have logged its exit code and cleaned up the PID file.
                            if controller.crawler_process: # Should be None if monitor cleaned up
                                if controller.crawler_process.returncode != 0:
                                     logging.warning(f"Crawler process finished with non-zero exit code: {controller.crawler_process.returncode}")
                                     # exit_code = controller.crawler_process.returncode # Or just 1
                                else:
                                     logging.info("Crawler process finished successfully.")
                            # else: # Monitor already handled it.
                        else: # Should not happen if start_crawler returned True and set it.
                            logging.warning("start_crawler reported success but crawler_process is not set in CLI.")
                    except KeyboardInterrupt: 
                        logging.info("User interrupted crawl waiting period (Ctrl+C in CLI while crawler runs). Signaling crawler to stop...")
                        controller.stop_crawler() # Signal the running crawler via flag
                        # Wait a bit for the crawler to shut down after flagging
                        if controller.crawler_process :
                            try: controller.crawler_process.wait(timeout=10) # brief wait
                            except subprocess.TimeoutExpired: logging.warning("Crawler did not exit quickly after SIGINT+flag.")
                        exit_code = 130 # Standard exit code for SIGINT
                    except Exception as e_wait:
                        logging.error(f"Error while waiting for crawler process: {e_wait}", exc_info=True)
                        exit_code = 1
            else:
                 logging.error("Cannot start crawler due to previous configuration errors.")

        if args.stop: 
            action_taken = True 
            if not controller.stop_crawler(): # stop_crawler now just creates a flag
                # This means flag creation failed.
                if exit_code == 0 : exit_code = 1 
            else:
                # Flag creation was successful. Crawler should handle its own stop.
                logging.info("Stop signal (flag) sent to crawler successfully.")


        if not action_taken and exit_code == 0: 
            parser.print_help()
        
        if exit_code != 0 and action_taken : 
             logging.error(f"CLI command processing encountered an error or a sub-command failed (exit_code: {exit_code}).")

    except KeyboardInterrupt:
        logging.info("CLI operation interrupted by user (Ctrl+C at CLI level).")
        # If a crawler process was started by this CLI instance and is still running, signal it.
        if hasattr(controller, 'crawler_process') and controller.crawler_process and controller.crawler_process.poll() is None:
            logging.info("Attempting to signal managed crawler process to stop due to CLI interruption...")
            controller.stop_crawler() # This will set the flag
        exit_code = 130 # Standard exit code for Ctrl+C
    except Exception as e: # Catch-all for unexpected errors in the CLI logic
        logging.critical(f"An unexpected error occurred in CLI: {e}", exc_info=True)
        exit_code = 1
    finally:
        # Ensure any managed subprocess is truly gone or waited for if CLI is exiting.
        # This is tricky if the user Ctrl+C'd the 'start' command's wait().
        # The _signal_handler for the CLI tries to stop_crawler.
        if hasattr(controller, 'crawler_process') and controller.crawler_process and controller.crawler_process.poll() is None:
            logging.info("CLI exiting; ensuring managed crawler process is aware or handled.")
            # At this point, stop_crawler (flag) should have been called if it was a graceful exit or SIGINT.
            # If it's an unexpected CLI crash, the crawler might be orphaned but flag might not be set.
            # For robustness, one last attempt to set flag if exiting due to error.
            if exit_code !=0 and exit_code != 130 : # not a clean exit or SIGINT
                controller.stop_crawler()

        logging.info(f"CLI session finished with exit_code: {exit_code}")
        sys.exit(exit_code)

if __name__ == '__main__':
    main_cli()