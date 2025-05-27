#!/usr/bin/env python3
"""
CLI Controller for Appium Crawler
Uses the centralized Config class.
"""

import sys
import os
import logging # For bootstrap logging
import json
import argparse
import subprocess
import signal
import time
import threading
from typing import Optional, Dict, Any, List
from pathlib import Path

# --- Imports for Config and Logging Utilities ---
try:
    # Assuming Config class is in config.py (which also contains default values)
    from config import Config
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import 'Config' class from config.py: {e}\n")
    sys.stderr.write("Ensure config.py exists and contains the Config class definition.\n")
    sys.exit(1)

try:
    # Assuming logging utilities and SCRIPT_START_TIME are in utils.py
    from utils import SCRIPT_START_TIME, LoggerManager, ElapsedTimeFormatter
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import logging utilities from utils.py: {e}\n")
    sys.stderr.write("Ensure utils.py exists and contains SCRIPT_START_TIME, LoggerManager, and ElapsedTimeFormatter.\n")
    # Basic SCRIPT_START_TIME fallback if utils.py is missing, though logging will be unformatted.
    if 'SCRIPT_START_TIME' not in globals():
        SCRIPT_START_TIME = time.time() 
    sys.exit(1)


class CLIController:
    """Command-line controller for the Appium Crawler."""

    def __init__(self, app_config_instance: Config):
        """Initialize the CLI controller with a Config instance."""
        self.cfg = app_config_instance
        self.api_dir = os.path.dirname(os.path.abspath(__file__)) # Directory of this cli_controller.py
        
        # Path to the find_app_info.py script, relative to this CLI controller script.
        # Consider making this path configurable via cfg if its location varies.
        self.find_app_info_script_path = os.path.join(self.api_dir, "find_app_info.py")

        self.health_apps_data: List[Dict[str, Any]] = []

        # Module to run for the crawler
        self.module_to_run = "traverser_ai_api.main"

        # Process management
        self.crawler_process: Optional[subprocess.Popen] = None
        # self.find_apps_process is not used in the provided code, can be removed if not needed.

        self._setup_cli_specific_directories()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Auto-load health apps if a file path is available in config during initialization
        if self.cfg.CURRENT_HEALTH_APP_LIST_FILE and os.path.exists(self.cfg.CURRENT_HEALTH_APP_LIST_FILE):
            logging.info(f"Attempting to auto-load health apps from: {self.cfg.CURRENT_HEALTH_APP_LIST_FILE}")
            self._load_health_apps_from_file(self.cfg.CURRENT_HEALTH_APP_LIST_FILE)
        else:
            logging.info("No pre-existing health app list file found in configuration or file does not exist.")

    def _setup_cli_specific_directories(self):
        """Create directories specifically needed by the CLI tool, if any,
           that are not covered by the main application's output structure defined in Config."""
        # Most output directories (logs, screenshots, db) are now resolved and created by 
        # the Config class or the main script part that uses cfg.
        # This method is for any directories *only* used by the CLI tool itself.
        # For example, if find_app_info.py (when run by CLI) saves output to a location
        # not managed by the main cfg.OUTPUT_DATA_DIR structure.
        # If all outputs are within cfg.OUTPUT_DATA_DIR, this method might be minimal.
        
        # Example: If `find_app_info_script_path` generates temporary files in a specific subdir of `api_dir`
        # scan_temp_dir = os.path.join(self.api_dir, "cli_scan_temp")
        # try:
        #     os.makedirs(scan_temp_dir, exist_ok=True)
        #     logging.debug(f"Ensured CLI-specific temp directory exists: {scan_temp_dir}")
        # except OSError as e:
        #     logging.warning(f"Could not create CLI-specific temp directory {scan_temp_dir}: {e}")
        pass # Currently, no CLI-specific directories seem explicitly needed beyond what cfg manages.


    def _signal_handler(self, signum, frame):
        """Handle SIGINT and SIGTERM signals."""
        logging.warning(f"\nSignal {signal.Signals(signum).name} received. Initiating graceful shutdown...")
        self.stop_crawler()
        # Perform any other CLI specific cleanup if necessary before exiting
        logging.info("CLI shutdown complete.")
        sys.exit(0)

    def save_all_changes(self) -> bool:
        """Explicitly save the current state of cfg to user_config.json."""
        logging.info("Attempting to save all current configuration settings...")
        try:
            self.cfg.save_user_config() # This handles saving relevant parts of cfg
            # No direct return value from save_user_config, success is logged by it.
            return True # Assume success if no exception
        except Exception as e:
            logging.error(f"Failed to save configuration via CLIController: {e}", exc_info=True)
            return False


    def show_config(self, filter_key: Optional[str] = None):
        """Display current configuration from the cfg object."""
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
        """Set a configuration value using cfg.update_setting_and_save."""
        logging.info(f"CLI attempting to set config: {key} = '{value_str}'")
        try:
            # update_setting_and_save within Config class handles type conversion and saving
            self.cfg.update_setting_and_save(key, value_str) 
            # Confirmation is logged by Config class's _update_attribute method
            return True
        except Exception as e:
            logging.error(f"CLI failed to set config for {key}: {e}", exc_info=True)
            return False


    def scan_apps(self, force_rescan: bool = False) -> bool:
        """Scan for health-related apps on the device."""
        if not force_rescan and self.cfg.CURRENT_HEALTH_APP_LIST_FILE and os.path.exists(self.cfg.CURRENT_HEALTH_APP_LIST_FILE):
            logging.info(f"Using cached health app list: {self.cfg.CURRENT_HEALTH_APP_LIST_FILE}")
            return self._load_health_apps_from_file(self.cfg.CURRENT_HEALTH_APP_LIST_FILE)

        if not os.path.exists(self.find_app_info_script_path):
            logging.error(f"find_app_info.py script not found at {self.find_app_info_script_path}")
            return False

        logging.info("Starting health app scan via find_app_info.py...")
        try:
            # Ensure the CWD for find_app_info.py is where it expects to be (e.g., its own directory or project root)
            # self.api_dir is the directory of cli_controller.py
            process_cwd = self.api_dir 
            logging.debug(f"Running find_app_info.py from CWD: {process_cwd}")

            result = subprocess.run(
                [sys.executable, '-u', self.find_app_info_script_path, '--mode', 'discover'],
                cwd=process_cwd, 
                capture_output=True, text=True, timeout=300, check=False # check=False to handle non-zero exit manually
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
                logging.error(f"Cache file reported by script not found at configured path: {cache_file_path}")
                return False
            
            # Update the config with the new cache file path and save it
            self.cfg.update_setting_and_save('CURRENT_HEALTH_APP_LIST_FILE', cache_file_path)
            return self._load_health_apps_from_file(cache_file_path) # Reloads data into self.health_apps_data

        except subprocess.TimeoutExpired:
            logging.error("App scan timed out after 5 minutes.")
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred during app scan: {e}", exc_info=True)
            return False

    def _load_health_apps_from_file(self, file_path: str) -> bool:
        """Load health apps from a JSON file into self.health_apps_data."""
        logging.debug(f"Loading health apps from file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Data can be a list of apps, or a dict with an 'apps' key
            if isinstance(data, dict):
                self.health_apps_data = data.get('apps', [])
            elif isinstance(data, list):
                self.health_apps_data = data
            else:
                logging.warning(f"Unexpected data structure in health app file: {file_path}. Expected list or dict with 'apps' key.")
                self.health_apps_data = []
                return False

            if not self.health_apps_data:
                logging.info(f"No health-related apps found or loaded from {file_path}.")
                # Not necessarily an error, could be an empty list
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
        """List available health apps from self.health_apps_data."""
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
        """Select an app by name or index, updating the central cfg."""
        if not self.health_apps_data:
            logging.error("No health apps loaded. Run 'scan-apps' first.")
            return False

        selected_app: Optional[Dict[str, Any]] = None
        try:
            index = int(app_identifier) - 1 # User provides 1-based index
            if 0 <= index < len(self.health_apps_data):
                selected_app = self.health_apps_data[index]
        except ValueError: # Not an integer, try matching by name or package
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
        app_name = selected_app.get('app_name', app_package if app_package else "Unknown App")

        if not app_package or not app_activity:
            logging.error(f"Selected app '{app_name}' is missing required package_name or activity_name.")
            return False

        logging.info(f"Selecting app: '{app_name}' (Package: {app_package}, Activity: {app_activity})")
        self.cfg.update_setting_and_save('APP_PACKAGE', app_package)
        self.cfg.update_setting_and_save('APP_ACTIVITY', app_activity)
        self.cfg.update_setting_and_save('LAST_SELECTED_APP', {
            'package_name': app_package,
            'activity_name': app_activity,
            'app_name': app_name
        })
        return True

    def start_crawler(self) -> bool:
        """Start the main crawler process."""
        if not self.cfg.SHUTDOWN_FLAG_PATH:
            logging.error("Shutdown flag path is not configured in the Config object. Cannot start crawler.")
            return False
            
        if os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
            logging.warning(f"Removing existing shutdown flag: {self.cfg.SHUTDOWN_FLAG_PATH}")
            try: os.remove(self.cfg.SHUTDOWN_FLAG_PATH)
            except OSError as e: logging.error(f"Could not remove existing shutdown flag: {e}")

        if not self.cfg.APP_PACKAGE or not self.cfg.APP_ACTIVITY:
            logging.error("APP_PACKAGE and APP_ACTIVITY must be set in config. Select an app first using 'select-app'.")
            return False

        if self.crawler_process and self.crawler_process.poll() is None:
            logging.warning("Crawler process appears to be already running.")
            return False # Or return True if this is acceptable

        logging.info("Starting crawler process with current configuration...")
        # All config changes should ideally be saved when they are made (e.g., via update_setting_and_save).
        # If an explicit overall save is needed before starting, uncomment:
        # self.cfg.save_user_config()

        try:
            # This assumes your main crawler logic is in 'traverser_ai_api.main'
            # and can be run as a module.
            module_to_run = "traverser_ai_api.main" 
            # The CWD should be the project root directory, one level up from self.api_dir
            # if self.api_dir is where cli_controller.py and find_app_info.py are.
            project_root_dir = Path(self.api_dir).parent.resolve().as_posix()
            logging.debug(f"Attempting to start crawler module '{module_to_run}' from CWD: '{project_root_dir}'")

            # Using sys.executable ensures the same Python interpreter is used.
            # -u for unbuffered output. -m to run library module as a script.            # Set PYTHONPATH environment variable to include the project root
            env = os.environ.copy()
            env['PYTHONPATH'] = project_root_dir
            self.crawler_process = subprocess.Popen(
                [sys.executable, '-u', self.api_dir + os.sep + 'main.py'],  # Run main.py directly
                cwd=project_root_dir,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,  # Combine stdout and stderr
                text=True, bufsize=1, universal_newlines=True,  # Line-buffered
                encoding='utf-8', errors='replace',  # Explicit encoding
                env=env  # Pass the modified environment
            )
            logging.info(f"Crawler process started with PID {self.crawler_process.pid}. Monitoring output...")
            threading.Thread(target=self._monitor_crawler_output, daemon=True).start()
            return True
        except FileNotFoundError:
            logging.error(f"Could not find Python interpreter '{sys.executable}' or module '{module_to_run}'. Ensure paths are correct.") # type: ignore
            return False
        except Exception as e:
            logging.error(f"Failed to start crawler process: {e}", exc_info=True)
            return False

    def _monitor_crawler_output(self):
        """Monitor and print crawler output in a separate thread."""
        if not self.crawler_process or not self.crawler_process.stdout:
            logging.error("Crawler process or its stdout not available for monitoring.")
            return
        try:
            for line in iter(self.crawler_process.stdout.readline, ''): # Read line by line
                if not line:  # EOF
                    break 
                print(line, end='') # Print the line, maintaining original newlines
            self.crawler_process.stdout.close() # Close the stream
            return_code = self.crawler_process.wait() # Wait for process to terminate
            logging.info(f"Crawler process exited with code {return_code}.")
        except Exception as e:
            logging.error(f"Error monitoring crawler output: {e}", exc_info=True)
        finally:
            logging.info("Crawler output monitoring thread finished.")


    def stop_crawler(self) -> bool:
        """Stop the crawler process gracefully using the shutdown flag, then escalate if needed."""
        if not self.crawler_process or self.crawler_process.poll() is not None:
            logging.info("Crawler is not currently running.")
            # Clean up flag if it somehow exists and process is not running
            if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
                 try: os.remove(self.cfg.SHUTDOWN_FLAG_PATH); logging.debug("Cleaned up stale shutdown flag.")
                 except OSError: pass
            return True

        logging.info("Attempting to stop crawler...")
        shutdown_flag_created = False
        if self.cfg.SHUTDOWN_FLAG_PATH:
            try:
                with open(self.cfg.SHUTDOWN_FLAG_PATH, 'w') as f: f.write("stop")
                shutdown_flag_created = True
                logging.info(f"Shutdown flag created at {self.cfg.SHUTDOWN_FLAG_PATH}. Waiting for graceful shutdown (timeout: 15s)...")
                self.crawler_process.wait(timeout=15)
                logging.info("Crawler process stopped gracefully via flag.")
            except subprocess.TimeoutExpired:
                logging.warning("Graceful shutdown via flag timed out. Escalating to SIGTERM...")
                self.crawler_process.terminate() # Send SIGTERM
                try:
                    self.crawler_process.wait(timeout=7)
                    logging.info("Crawler process terminated (SIGTERM).")
                except subprocess.TimeoutExpired:
                    logging.warning("SIGTERM timed out. Escalating to SIGKILL...")
                    self.crawler_process.kill() # Send SIGKILL
                    self.crawler_process.wait() # Wait for kill to complete
                    logging.info("Crawler process killed (SIGKILL).")
            except Exception as e: # Catch errors related to flag creation or initial wait
                logging.error(f"Error during shutdown flag handling or initial wait: {e}. Attempting direct termination.", exc_info=True)
                if self.crawler_process.poll() is None: self.crawler_process.terminate() # Try SIGTERM
        else: # No shutdown flag path configured
            logging.warning("No SHUTDOWN_FLAG_PATH configured in cfg. Attempting direct SIGTERM.")
            self.crawler_process.terminate()
            try:
                self.crawler_process.wait(timeout=7)
                logging.info("Crawler process terminated (SIGTERM).")
            except subprocess.TimeoutExpired:
                logging.warning("SIGTERM timed out. Escalating to SIGKILL...")
                self.crawler_process.kill()
                self.crawler_process.wait()
                logging.info("Crawler process killed (SIGKILL).")
        
        self._cleanup_after_stop(shutdown_flag_created)
        return True

    def _cleanup_after_stop(self, flag_was_created:bool):
        """Clean up the shutdown flag file if it was created by this stop attempt."""
        if flag_was_created and self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
            try:
                os.remove(self.cfg.SHUTDOWN_FLAG_PATH)
                logging.debug(f"Removed shutdown flag: {self.cfg.SHUTDOWN_FLAG_PATH}")
            except OSError as e:
                logging.warning(f"Could not remove shutdown flag {self.cfg.SHUTDOWN_FLAG_PATH}: {e}")
        self.crawler_process = None # Clear the process reference

    def status(self):
        """Show current operational status."""
        print("\n=== CLI Crawler Status ===")
        if self.crawler_process and self.crawler_process.poll() is None:
            print(f"  Crawler Process: Running (PID: {self.crawler_process.pid})")
        else:
            print("  Crawler Process: Stopped")
        
        last_selected = self.cfg.LAST_SELECTED_APP
        if self.cfg.APP_PACKAGE and self.cfg.APP_ACTIVITY:
            app_name_display = last_selected.get('app_name', 'N/A') if isinstance(last_selected, dict) else 'N/A'
            print(f"  Target App:      '{app_name_display}' ({self.cfg.APP_PACKAGE})")
        else:
            print("  Target App:      Not Selected")
        
        if self.health_apps_data:
            print(f"  Health Apps:     {len(self.health_apps_data)} app(s) loaded from '{Path(self.cfg.CURRENT_HEALTH_APP_LIST_FILE).name if self.cfg.CURRENT_HEALTH_APP_LIST_FILE else 'N/A'}'")
        else:
            print(f"  Health Apps:     None loaded (last checked file: '{self.cfg.CURRENT_HEALTH_APP_LIST_FILE or 'N/A'}')")
        print(f"  Log Level:       {self.cfg.LOG_LEVEL}")
        print(f"  Shutdown Flag:   {self.cfg.SHUTDOWN_FLAG_PATH or 'Not Configured'}")
        print("========================")


def create_parser() -> argparse.ArgumentParser:
    """Creates the argument parser for the CLI."""
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
    # ... (rest of your create_parser function, ensure it's here) ...
    # For brevity, I'll use a simplified version of your parser definition.
    # Ensure you use your full parser definition.
    app_group = parser.add_argument_group('App Management')
    app_group.add_argument('--scan-apps', action='store_true', help='Scan device for health-related apps and update config.')
    app_group.add_argument('--list-apps', action='store_true', help='List available health apps from the last scan.')
    app_group.add_argument('--select-app', metavar='APP_NAME_OR_INDEX', help='Select app by name or 1-based index to set as target.')

    crawler_group = parser.add_argument_group('Crawler Control')
    crawler_group.add_argument('--start', action='store_true', help='Start the crawler with current configuration.')
    crawler_group.add_argument('--stop', action='store_true', help='Stop the running crawler.')
    crawler_group.add_argument('--status', action='store_true', help='Show current status of the CLI controller and crawler.')

    config_group = parser.add_argument_group('Configuration Management')
    config_group.add_argument('--show-config', metavar='FILTER_KEY', nargs='?', const='', help='Show current configuration (optionally filter by key).')
    config_group.add_argument('--set-config', metavar='KEY=VALUE', action='append', help='Set a configuration value (e.g., MAX_CRAWL_STEPS=100). For lists, use comma-separated values.')
    config_group.add_argument('--save-config', action='store_true', help='Explicitly save all current config settings to user_config.json.')
    
    parser.add_argument('--force-rescan', action='store_true', help='Force app rescan even if a cached list exists.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose DEBUG logging for the CLI session.')
    return parser

# Need textwrap for the epilog in create_parser
import textwrap

def main_cli():
    """Main entry point for the CLI application."""
    parser = create_parser()
    args = parser.parse_args()

    # --- Bootstrap Logging (minimal, before full logger setup) ---
    # SCRIPT_START_TIME is imported from utils
    bootstrap_log_level = 'DEBUG' if args.verbose else 'INFO'
    logging.basicConfig(
        level=bootstrap_log_level,
        format=f"%(asctime)s [{SCRIPT_START_TIME:.0f}] [%(levelname)s] %(message)s (bootstrap)",
        datefmt='%H:%M:%S'
    )
    logging.info("CLI Bootstrap logging initialized.")

    # --- Configuration Setup ---
    _cli_script_dir = os.path.dirname(os.path.abspath(__file__))
    # Assumes config.py (with defaults and Config class) is in the same directory as cli_controller.py
    DEFAULT_CONFIG_MODULE_PATH_CLI = os.path.join(_cli_script_dir, 'config.py') 
    USER_CONFIG_JSON_PATH_CLI = os.path.join(_cli_script_dir, "user_config.json")

    try:
        cli_cfg = Config(
            defaults_module_path=DEFAULT_CONFIG_MODULE_PATH_CLI,
            user_config_json_path=USER_CONFIG_JSON_PATH_CLI
        )
        # Define and set the shutdown flag path on the cfg instance
        # This path is relative to where config.py (defaults module) is located.
        cli_cfg.SHUTDOWN_FLAG_PATH = os.path.join(cli_cfg.BASE_DIR, "crawler_shutdown.flag")
        logging.debug(f"Config object initialized. Shutdown flag path: {cli_cfg.SHUTDOWN_FLAG_PATH}")

    except Exception as e:
        logging.critical(f"Failed to initialize Config object for CLI: {e}", exc_info=True)
        sys.exit(100)

    # --- Setup Full Application Logging ---
    logger_manager_cli = LoggerManager()
    # Determine final log directory (ensure cfg.OUTPUT_DATA_DIR is valid)
    _log_base_dir_cli = cli_cfg.OUTPUT_DATA_DIR if cli_cfg.OUTPUT_DATA_DIR and os.path.isdir(os.path.dirname(cli_cfg.OUTPUT_DATA_DIR)) else _cli_script_dir
    _final_log_dir_cli = os.path.join(_log_base_dir_cli, "logs", "cli") # Separate CLI logs
    os.makedirs(_final_log_dir_cli, exist_ok=True)
    _final_log_file_path_cli = os.path.join(_final_log_dir_cli, f"cli_{cli_cfg.LOG_FILE_NAME}")
    
    effective_log_level = 'DEBUG' if args.verbose else cli_cfg.LOG_LEVEL
    
    root_logger_cli = logger_manager_cli.setup_logging(
        log_level_str=effective_log_level, 
        log_file=_final_log_file_path_cli
    )
    root_logger_cli.info(f"CLI Application Logging Initialized. Level: {effective_log_level}. File: '{_final_log_file_path_cli}'")
    if args.verbose and cli_cfg.LOG_LEVEL.upper() != 'DEBUG':
        root_logger_cli.info(f"CLI session is verbose (DEBUG), but app default LOG_LEVEL is {cli_cfg.LOG_LEVEL}.")


    # --- Initialize and Run CLIController ---
    controller = CLIController(app_config_instance=cli_cfg)
    
    action_taken = False
    exit_code = 0
    try:
        if args.scan_apps:
            action_taken = True
            if not controller.scan_apps(force_rescan=args.force_rescan): exit_code = 1
        if args.list_apps and exit_code == 0: # Proceed if previous actions succeeded
            action_taken = True
            controller.list_apps()
        if args.select_app and exit_code == 0:
            action_taken = True
            if not controller.select_app(args.select_app): exit_code = 1
        if args.show_config is not None and exit_code == 0:
            action_taken = True
            controller.show_config(args.show_config if args.show_config else None)
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
        if args.status and exit_code == 0:
            action_taken = True
            controller.status()
        if args.start and exit_code == 0:
            action_taken = True
            if not controller.start_crawler(): 
                exit_code = 1
            else: # If crawler started, wait for it or interruption
                try:
                    if controller.crawler_process: controller.crawler_process.wait()
                    logging.info("Crawler process finished.")
                except KeyboardInterrupt:
                    logging.info("User interrupted crawl. Stopping crawler...")
                    controller.stop_crawler()
                    exit_code = 130 # Interrupted
        if args.stop: # Can be called independently
            action_taken = True # Considered an action even if crawler wasn't running
            if not controller.stop_crawler(): exit_code = 1

        if not action_taken and exit_code == 0: # No command was given
            parser.print_help()
        
        if exit_code != 0:
             logging.error(f"CLI command failed with exit code {exit_code}.")

    except KeyboardInterrupt:
        logging.info("CLI operation interrupted by user.")
        if controller.crawler_process and controller.crawler_process.poll() is None:
            controller.stop_crawler()
        exit_code = 130 # Standard for SIGINT
    except Exception as e:
        logging.critical(f"An unexpected error occurred in CLI: {e}", exc_info=True)
        exit_code = 1
    finally:
        logging.info(f"CLI session finished with exit_code: {exit_code}")
        sys.exit(exit_code)

if __name__ == '__main__':
    # SCRIPT_START_TIME is imported from utils and set when utils.py is loaded.
    main_cli()