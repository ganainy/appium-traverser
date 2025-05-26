#!/usr/bin/env python3
"""
CLI Controller for Appium Crawler
Replaces the GUI with a command-line interface while maintaining full functionality.
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
from typing import Optional, Dict, Any, List
from pathlib import Path

# Import config module for defaults
import config


class CLIController:
    """Command-line controller for the Appium Crawler."""

    def __init__(self):
        """Initialize the CLI controller."""
        self.api_dir = os.path.dirname(__file__)
        self.output_data_dir = os.path.join(self.api_dir, "output_data")
        self.config_file_path = os.path.join(self.api_dir, "user_config.json")
        self.find_app_info_script_path = os.path.join(self.api_dir, "find_app_info.py")
        
        # Initialize configuration
        self.user_config: Dict[str, Any] = {}
        self.current_health_app_list_file: Optional[str] = None
        self.health_apps_data: List[Dict[str, Any]] = []
        
        # Process management
        self.crawler_process: Optional[subprocess.Popen] = None
        self.find_apps_process: Optional[subprocess.Popen] = None
        self._shutdown_flag_file_path: Optional[str] = None
        
        # Setup directories
        self._setup_directories()
        
        # Setup shutdown flag path
        self._setup_shutdown_flag()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_directories(self):
        """Create required output directories."""
        required_dirs = {"app_info", "screenshots", "database_output", "traffic_captures"}
        for subdir in required_dirs:
            dir_path = os.path.join(self.output_data_dir, subdir)
            try:
                os.makedirs(dir_path, exist_ok=True)
            except OSError as e:
                raise RuntimeError(f"Failed to create required directory {dir_path}: {e}")

    def _setup_shutdown_flag(self):
        """Setup the shutdown flag file path."""
        if config and hasattr(config, '__file__') and config.__file__:
            try:
                config_module_dir_path = os.path.dirname(os.path.abspath(config.__file__))
                self._shutdown_flag_file_path = os.path.join(config_module_dir_path, "crawler_shutdown.flag")
                logging.info(f"Shutdown flag path configured: {self._shutdown_flag_file_path}")
            except Exception as e:
                logging.error(f"Error determining shutdown flag path: {e}")
                self._shutdown_flag_file_path = None
        else:
            logging.warning("Config module not found. Graceful shutdown via flag disabled.")
            self._shutdown_flag_file_path = None

    def _signal_handler(self, signum, frame):
        """Handle SIGINT and SIGTERM signals."""
        print(f"\n\nReceived signal {signum}. Shutting down gracefully...")
        self.stop_crawler()
        sys.exit(0)

    def load_config(self) -> bool:
        """Load configuration from JSON file."""
        if not os.path.exists(self.config_file_path):
            print("No existing configuration found. Loading defaults from config.py")
            self._load_defaults_from_config()
            return False

        try:
            with open(self.config_file_path, 'r') as f:
                self.user_config = json.load(f)
            
            # Load health app list file path
            self.current_health_app_list_file = self.user_config.get('CURRENT_HEALTH_APP_LIST_FILE')
            
            # Auto-load health apps if a file path is available
            if self.current_health_app_list_file and os.path.exists(self.current_health_app_list_file):
                self._load_health_apps_from_file(self.current_health_app_list_file)
            
            print("Configuration loaded successfully.")
            return True
        except Exception as e:
            print(f"Error loading configuration: {e}")
            self._load_defaults_from_config()
            return False

    def _load_defaults_from_config(self):
        """Load default configuration values from config.py module."""
        # Define all configuration keys that need to be managed
        config_keys = [
            'APPIUM_SERVER_URL', 'TARGET_DEVICE_UDID', 'NEW_COMMAND_TIMEOUT', 'APPIUM_IMPLICIT_WAIT',
            'APP_PACKAGE', 'APP_ACTIVITY', 'DEFAULT_MODEL_TYPE', 'USE_CHAT_MEMORY', 'MAX_CHAT_HISTORY',
            'XML_SNIPPET_MAX_LEN', 'CRAWL_MODE', 'MAX_CRAWL_STEPS', 'MAX_CRAWL_DURATION_SECONDS',
            'WAIT_AFTER_ACTION', 'STABILITY_WAIT', 'APP_LAUNCH_WAIT_TIME', 'VISUAL_SIMILARITY_THRESHOLD',            'ALLOWED_EXTERNAL_PACKAGES', 'MAX_CONSECUTIVE_AI_FAILURES', 'MAX_CONSECUTIVE_MAP_FAILURES',
            'MAX_CONSECUTIVE_EXEC_FAILURES', 'ENABLE_XML_CONTEXT', 'ENABLE_TRAFFIC_CAPTURE',
            'PCAPDROID_API_KEY', 'CLEANUP_DEVICE_PCAP_FILE', 'CONTINUE_EXISTING_RUN'
        ]
        
        missing_configs = []
        self.user_config = {}
        
        for key in config_keys:
            if hasattr(config, key):
                value = getattr(config, key)
                if value is not None:
                    self.user_config[key] = value
                else:
                    missing_configs.append(f"{key} (None value)")
            else:
                missing_configs.append(key)

        if missing_configs:
            logging.warning(f"Missing or invalid config keys: {missing_configs}")

    def save_config(self, config_updates: Optional[Dict[str, Any]] = None) -> bool:
        """Save configuration to JSON file."""
        if config_updates:
            self.user_config.update(config_updates)
        
        # Save health app list path
        self.user_config['CURRENT_HEALTH_APP_LIST_FILE'] = self.current_health_app_list_file
        
        try:
            with open(self.config_file_path, 'w') as f:
                json.dump(self.user_config, f, indent=4)
            print("Configuration saved successfully.")
            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False

    def show_config(self, filter_key: Optional[str] = None):
        """Display current configuration."""
        if not self.user_config:
            print("No configuration loaded.")
            return

        print("\n=== Current Configuration ===")
        for key, value in sorted(self.user_config.items()):
            if filter_key and filter_key.lower() not in key.lower():
                continue
            if isinstance(value, list):
                print(f"{key}: {', '.join(map(str, value))}")
            else:
                print(f"{key}: {value}")
        print("=" * 30)

    def set_config(self, key: str, value: str) -> bool:
        """Set a configuration value."""
        original_value = value
        parsed_value: Any = value
        
        # Check if key exists and try to parse value based on existing type
        if key in self.user_config:
            existing_value = self.user_config[key]
            if isinstance(existing_value, bool):
                parsed_value = original_value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(existing_value, int):
                try:
                    parsed_value = int(original_value)
                except ValueError:
                    print(f"Error: '{original_value}' is not a valid integer for {key}")
                    return False
            elif isinstance(existing_value, list):
                parsed_value = [item.strip() for item in original_value.split(',') if item.strip()]
            else:
                parsed_value = original_value
        else:
            # For new keys, try to infer type from the value
            print(f"Warning: '{key}' is not a recognized configuration key. Adding as string.")
            # Try to parse as boolean
            if original_value.lower() in ('true', 'false', '1', '0', 'yes', 'no', 'on', 'off'):
                parsed_value = original_value.lower() in ('true', '1', 'yes', 'on')
            # Try to parse as integer
            elif original_value.isdigit() or (original_value.startswith('-') and original_value[1:].isdigit()):
                try:
                    parsed_value = int(original_value)
                except ValueError:
                    parsed_value = original_value  # Keep as string
            # Check if it looks like a list
            elif ',' in original_value:
                parsed_value = [item.strip() for item in original_value.split(',') if item.strip()]
            else:
                parsed_value = original_value
        
        self.user_config[key] = parsed_value
        print(f"Set {key} = {parsed_value}")
        return True

    def scan_apps(self, force_rescan: bool = False) -> bool:
        """Scan for health-related apps on the device."""
        if not force_rescan and self.current_health_app_list_file and os.path.exists(self.current_health_app_list_file):
            print(f"Using cached health app list: {self.current_health_app_list_file}")
            return self._load_health_apps_from_file(self.current_health_app_list_file)

        if not os.path.exists(self.find_app_info_script_path):
            print(f"Error: find_app_info.py script not found at {self.find_app_info_script_path}")
            return False

        print("Starting health app scan...")
        
        try:
            # Run the app discovery script
            result = subprocess.run(
                [sys.executable, '-u', self.find_app_info_script_path, '--mode', 'discover'],
                cwd=self.api_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                print(f"App scan failed with exit code {result.returncode}")
                if result.stderr:
                    print(f"Error output: {result.stderr}")
                return False
            
            # Look for the cache file path in the output
            output_lines = result.stdout.split('\n')
            cache_file_line = next(
                (line for line in output_lines if "Cache file generated at:" in line),
                None
            )
            
            if not cache_file_line:
                print("Error: Could not find cache file path in scan output")
                return False
            
            # Extract cache file path
            cache_file_path = cache_file_line.split("Cache file generated at:", 1)[1].strip()
            if not os.path.exists(cache_file_path):
                print(f"Error: Cache file not found at {cache_file_path}")
                return False
            
            # Load the results
            self.current_health_app_list_file = cache_file_path
            return self._load_health_apps_from_file(cache_file_path)
            
        except subprocess.TimeoutExpired:
            print("App scan timed out after 5 minutes")
            return False
        except Exception as e:
            print(f"Error during app scan: {e}")
            return False

    def _load_health_apps_from_file(self, file_path: str) -> bool:
        """Load health apps from a JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.health_apps_data = data.get('apps', []) if isinstance(data, dict) else data

            if not self.health_apps_data:
                print("No health-related apps found in the scan results.")
                return False

            print(f"Successfully loaded {len(self.health_apps_data)} health apps from {file_path}")
            return True
            
        except Exception as e:
            print(f"Error loading health apps from file {file_path}: {e}")
            return False

    def list_apps(self):
        """List available health apps."""
        if not self.health_apps_data:
            print("No health apps loaded. Run scan first.")
            return

        print(f"\n=== Available Health Apps ({len(self.health_apps_data)}) ===")
        for i, app in enumerate(self.health_apps_data):
            app_name = app.get('app_name', 'Unknown')
            package_name = app.get('package_name', 'Unknown')
            activity_name = app.get('activity_name', 'Unknown')
            print(f"{i+1:2d}. {app_name}")
            print(f"     Package: {package_name}")
            print(f"     Activity: {activity_name}")
            print()

    def select_app(self, app_identifier: str) -> bool:
        """Select an app by name or index."""
        if not self.health_apps_data:
            print("No health apps loaded. Run scan first.")
            return False

        selected_app = None
        
        # Try to parse as index first
        try:
            index = int(app_identifier) - 1  # Convert to 0-based index
            if 0 <= index < len(self.health_apps_data):
                selected_app = self.health_apps_data[index]
        except ValueError:
            # Not an index, search by name or package
            for app in self.health_apps_data:
                if (app_identifier.lower() in app.get('app_name', '').lower() or 
                    app_identifier.lower() in app.get('package_name', '').lower()):
                    selected_app = app
                    break

        if not selected_app:
            print(f"App '{app_identifier}' not found.")
            return False

        # Update configuration
        app_package = selected_app.get('package_name', '')
        app_activity = selected_app.get('activity_name', '')
        app_name = selected_app.get('app_name', app_package)

        if not app_package or not app_activity:
            print(f"Warning: Selected app {app_name} is missing package or activity information")
            return False

        self.user_config['APP_PACKAGE'] = app_package
        self.user_config['APP_ACTIVITY'] = app_activity
        
        # Save the selected app info
        self.user_config['LAST_SELECTED_APP'] = {
            'package_name': app_package,
            'activity_name': app_activity,
            'app_name': app_name
        }

        print(f"Selected app: {app_name} ({app_package})")
        return True

    def start_crawler(self) -> bool:
        """Start the crawler process."""
        # Clean up any existing shutdown flag
        if self._shutdown_flag_file_path and os.path.exists(self._shutdown_flag_file_path):
            try:
                os.remove(self._shutdown_flag_file_path)
                print("Removed existing shutdown flag.")
            except OSError as e:
                print(f"Warning: Could not remove existing shutdown flag: {e}")

        # Validate configuration
        if not self.user_config.get('APP_PACKAGE') or not self.user_config.get('APP_ACTIVITY'):
            print("Error: APP_PACKAGE and APP_ACTIVITY must be set. Select an app first.")
            return False

        if self.crawler_process and self.crawler_process.poll() is None:
            print("Crawler is already running.")
            return False

        # Save current configuration
        self.save_config()

        print("Starting crawler...")
        
        try:
            # Start the crawler process
            module_to_run = "traverser_ai_api.main"
            working_dir = os.path.dirname(self.api_dir)
            
            self.crawler_process = subprocess.Popen(
                [sys.executable, '-u', '-m', module_to_run],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            print(f"Crawler started with PID {self.crawler_process.pid}")
            print("Use Ctrl+C to stop the crawler gracefully.")
            
            # Start monitoring thread
            monitor_thread = threading.Thread(target=self._monitor_crawler_output, daemon=True)
            monitor_thread.start()
            
            return True
            
        except Exception as e:
            print(f"Error starting crawler: {e}")
            return False

    def _monitor_crawler_output(self):
        """Monitor crawler output in a separate thread."""
        if not self.crawler_process or not self.crawler_process.stdout:
            return

        step_count = 0
        
        try:
            for line in iter(self.crawler_process.stdout.readline, ''):
                if not line:
                    break
                    
                line = line.strip()
                if not line:
                    continue

                # Print all output
                print(line)
                
                # Parse special UI markers for status updates
                if line.startswith("UI_STEP:"):
                    step_num = line.split(":", 1)[1].strip()
                    step_count = int(step_num)
                    print(f">>> Step: {step_num}")
                elif line.startswith("UI_STATUS:"):
                    status = line.split(":", 1)[1].strip()
                    print(f">>> Status: {status}")
                elif line.startswith("UI_ACTION:"):
                    action = line.split(":", 1)[1].strip()
                    print(f">>> Last Action: {action}")
                elif line.startswith("UI_SCREENSHOT:"):
                    screenshot_path = line.split(":", 1)[1].strip()
                    print(f">>> Screenshot saved: {screenshot_path}")
                elif line.startswith("UI_END:"):
                    end_reason = line.split(":", 1)[1].strip()
                    print(f">>> Crawl ended: {end_reason}")
                    
        except Exception as e:
            print(f"Error monitoring crawler output: {e}")

    def stop_crawler(self) -> bool:
        """Stop the crawler process gracefully."""
        if not self.crawler_process or self.crawler_process.poll() is not None:
            print("Crawler is not running.")
            return True

        print("Stopping crawler...")
        
        # Try graceful shutdown first using flag
        if self._shutdown_flag_file_path:
            try:
                with open(self._shutdown_flag_file_path, 'w') as f:
                    f.write("stop")
                print("Shutdown signal sent via flag. Waiting for graceful shutdown...")
                
                # Wait up to 15 seconds for graceful shutdown
                try:
                    self.crawler_process.wait(timeout=15)
                    print("Crawler stopped gracefully.")
                    self._cleanup_after_stop()
                    return True
                except subprocess.TimeoutExpired:
                    print("Graceful shutdown timed out. Terminating...")
                    
            except Exception as e:
                print(f"Error creating shutdown flag: {e}")

        # Force termination
        try:
            self.crawler_process.terminate()
            try:
                self.crawler_process.wait(timeout=7)
                print("Crawler terminated.")
            except subprocess.TimeoutExpired:
                print("Termination timed out. Killing process...")
                self.crawler_process.kill()
                self.crawler_process.wait()
                print("Crawler killed.")
                
            self._cleanup_after_stop()
            return True
            
        except Exception as e:
            print(f"Error stopping crawler: {e}")
            return False

    def _cleanup_after_stop(self):
        """Clean up after stopping the crawler."""
        if self._shutdown_flag_file_path and os.path.exists(self._shutdown_flag_file_path):
            try:
                os.remove(self._shutdown_flag_file_path)
            except OSError as e:
                print(f"Warning: Could not remove shutdown flag: {e}")
        
        self.crawler_process = None

    def status(self):
        """Show current status."""
        print("\n=== Crawler Status ===")
        
        # Crawler process status
        if self.crawler_process and self.crawler_process.poll() is None:
            print(f"Crawler: Running (PID: {self.crawler_process.pid})")
        else:
            print("Crawler: Stopped")
        
        # Configuration status
        if self.user_config.get('APP_PACKAGE') and self.user_config.get('APP_ACTIVITY'):
            app_name = self.user_config.get('LAST_SELECTED_APP', {}).get('app_name', 'Unknown')
            print(f"Target App: {app_name} ({self.user_config['APP_PACKAGE']})")
        else:
            print("Target App: Not selected")
        
        # Health apps status
        if self.health_apps_data:
            print(f"Health Apps: {len(self.health_apps_data)} loaded")
        else:
            print("Health Apps: None loaded")
        
        print("=" * 22)


def create_parser():
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="CLI Controller for Appium Crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scan-apps                    # Scan for health apps
  %(prog)s --list-apps                    # List available apps
  %(prog)s --select-app "Blood Donation"  # Select app by name
  %(prog)s --select-app 1                 # Select app by index
  %(prog)s --start                        # Start crawler
  %(prog)s --stop                         # Stop crawler
  %(prog)s --status                       # Show status
  %(prog)s --show-config                  # Show configuration
  %(prog)s --set-config CRAWL_MODE=time   # Set config value
  %(prog)s --save-config                  # Save configuration
        """
    )

    # App management commands
    app_group = parser.add_argument_group('app management')
    app_group.add_argument('--scan-apps', action='store_true',
                          help='Scan device for health-related apps')
    app_group.add_argument('--list-apps', action='store_true',
                          help='List available health apps')
    app_group.add_argument('--select-app', metavar='NAME_OR_INDEX',
                          help='Select app by name or index')

    # Crawler control commands
    crawler_group = parser.add_argument_group('crawler control')
    crawler_group.add_argument('--start', action='store_true',
                              help='Start the crawler')
    crawler_group.add_argument('--stop', action='store_true',
                              help='Stop the crawler')
    crawler_group.add_argument('--status', action='store_true',
                              help='Show current status')

    # Configuration commands
    config_group = parser.add_argument_group('configuration')
    config_group.add_argument('--show-config', metavar='FILTER',
                             nargs='?', const='',
                             help='Show configuration (optionally filtered)')
    config_group.add_argument('--set-config', metavar='KEY=VALUE',
                             action='append',
                             help='Set configuration value (can be used multiple times)')
    config_group.add_argument('--save-config', action='store_true',
                             help='Save current configuration')

    # Global options
    parser.add_argument('--force-rescan', action='store_true',
                       help='Force rescan even if cached results exist')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')

    return parser


def main():
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create controller
    controller = CLIController()
    
    # Load configuration
    controller.load_config()

    # Execute commands
    try:
        # App management commands
        if args.scan_apps:
            if not controller.scan_apps(force_rescan=args.force_rescan):
                sys.exit(1)

        if args.list_apps:
            controller.list_apps()

        if args.select_app:
            if not controller.select_app(args.select_app):
                sys.exit(1)

        # Configuration commands
        if args.show_config is not None:
            controller.show_config(args.show_config if args.show_config else None)

        if args.set_config:
            for config_item in args.set_config:
                if '=' not in config_item:
                    print(f"Error: Invalid config format '{config_item}'. Use KEY=VALUE")
                    sys.exit(1)
                key, value = config_item.split('=', 1)
                if not controller.set_config(key, value):
                    sys.exit(1)

        if args.save_config:
            if not controller.save_config():
                sys.exit(1)

        # Crawler control commands
        if args.status:
            controller.status()

        if args.start:
            if not controller.start_crawler():
                sys.exit(1)
            # Wait for the process to complete
            try:
                if controller.crawler_process:
                    controller.crawler_process.wait()
            except KeyboardInterrupt:
                print("\nInterrupted by user. Stopping crawler...")
                controller.stop_crawler()

        if args.stop:
            if not controller.stop_crawler():
                sys.exit(1)

        # If no commands specified, show help
        if not any([args.scan_apps, args.list_apps, args.select_app, args.start, 
                   args.stop, args.status, args.show_config is not None, 
                   args.set_config, args.save_config]):
            parser.print_help()

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        controller.stop_crawler()
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        logging.exception("Unexpected error")
        sys.exit(1)


if __name__ == '__main__':
    main()
