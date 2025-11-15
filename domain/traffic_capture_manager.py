# traffic_capture_manager.py
import asyncio  # For async wrappers
import logging
import os
import re
import subprocess
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

# Assuming AppiumDriver is type hinted correctly
if TYPE_CHECKING:
    from infrastructure.appium_driver import AppiumDriver

# Import your main Config class
try:
    from config.app_config import Config  # Adjust path as necessary
except ImportError:
    from config.app_config import Config  # Adjust path as necessary

class TrafficCaptureManager:
    def __init__(self, driver: 'AppiumDriver', app_config: Config):
        """
        Initialize the TrafficCaptureManager.

        Args:
            driver (AppiumDriver): An instance of the AppiumDriver wrapper.
            app_config (Config): The main application Config object instance.
        """
        self.driver = driver
        self.cfg = app_config
        self.traffic_capture_enabled: bool = bool(self.cfg.get('ENABLE_TRAFFIC_CAPTURE')) # Get from cfg

        self.pcap_filename_on_device: Optional[str] = None
        self.local_pcap_file_path: Optional[str] = None
        self._is_currently_capturing: bool = False # Internal flag

        if self.traffic_capture_enabled:
            # Validate necessary configs for PCAPdroid
            required_pcap_configs = [
                'APP_PACKAGE', 'TRAFFIC_CAPTURE_OUTPUT_DIR', 'WAIT_AFTER_ACTION',
                'PCAPDROID_PACKAGE', 'DEVICE_PCAP_DIR' 
                # PCAPDROID_ACTIVITY is optional - will be constructed if not provided
                # PCAPDROID_API_KEY is optional but recommended
                # Device PCAP cleanup is always enabled by default
            ]
            for cfg_key in required_pcap_configs:
                if self.cfg.get(cfg_key) is None:
                    # Allow DEVICE_PCAP_DIR to be None and default later
                    if cfg_key == 'DEVICE_PCAP_DIR' and self.cfg.get(cfg_key) is None:
                        continue
                    raise ValueError(f"TrafficCaptureManager: Required config '{cfg_key}' not found or is None.")
            
            # Construct PCAPDROID_ACTIVITY if not provided
            # According to PCAPdroid API docs: https://github.com/emanuele-f/PCAPdroid/blob/master/docs/app_api.md
            # The correct activity is: com.emanuelef.remote_capture/.activities.CaptureCtrl
            if not self.cfg.get('PCAPDROID_ACTIVITY'):
                pcapdroid_package = self.cfg.get('PCAPDROID_PACKAGE')
                if pcapdroid_package:
                    # Default PCAPdroid activity format: package_name/.activities.CaptureCtrl
                    default_activity = f"{pcapdroid_package}/.activities.CaptureCtrl"
                    logging.debug(f"PCAPDROID_ACTIVITY not set, using default: {default_activity}")
                    # Set it in config for this session (doesn't persist)
                    self.cfg.set('PCAPDROID_ACTIVITY', default_activity)
            
            logging.debug("TrafficCaptureManager initialized and enabled.")
        else:
            logging.debug("TrafficCaptureManager initialized but traffic capture is DISABLED in config.")

    async def _run_adb_command_async(self, command_list: List[str], suppress_stderr: bool = False) -> Tuple[str, int]:
        """
        Async helper to run ADB commands. Wraps synchronous subprocess call.
        """
        # Ensure adb path is correct, consider making it configurable if not in PATH
        # For simplicity, assuming 'adb' is in PATH
        adb_executable = self.cfg.get('ADB_EXECUTABLE_PATH', 'adb') 
        try:
            full_command = [adb_executable] + command_list
            
            logging.debug(f"--- Running ADB for Capture (async_wrapper): {' '.join(full_command)}")
            
            # Using asyncio.to_thread to run the blocking subprocess.run in a separate thread
            def run_sync_subprocess():
                return subprocess.run(
                    full_command,
                    capture_output=True,
                    text=True,
                    check=False,
                    encoding='utf-8',
                    errors='replace',
                )
            
            result = await asyncio.to_thread(run_sync_subprocess)

            if result.stdout:
                logging.debug(f"--- ADB STDOUT (Capture):\n{result.stdout.strip()}")
            if result.stderr and not suppress_stderr:
                logging.error(f"--- ADB STDERR (Capture):\n{result.stderr.strip()}")
            # Combine stdout and stderr for error detection (stderr often contains error messages)
            # ADB 'am start' may return 0 even if activity doesn't exist, but stderr will have the error
            combined_output = result.stdout.strip()
            if result.stderr:
                combined_output += "\n" + result.stderr.strip()
            return combined_output, result.returncode
        except FileNotFoundError:
            logging.error(f"ADB command ('{adb_executable}') not found. Ensure ADB is in PATH or ADB_EXECUTABLE_PATH is configured.")
            return "ADB_NOT_FOUND", -1
        except Exception as e:
            logging.error(f"Exception in _run_adb_command_async: {e}", exc_info=True)
            return str(e), -1
            
    def is_capturing(self) -> bool:
        """Returns the internal state of whether capture is thought to be active."""
        return self._is_currently_capturing

    async def start_capture_async(self, filename_template: Optional[str] = None, run_id: Optional[int] = None, step_num: Optional[int] = None) -> bool:
        """Starts PCAPdroid traffic capture using the official API."""
        if not self.traffic_capture_enabled:
            logging.debug("Traffic capture disabled by config, not starting.")
            return False
        if self._is_currently_capturing:
            logging.warning("Traffic capture already started by this manager.")
            return True # Or False if it's an error to call start again

        target_app_package = str(self.cfg.get('APP_PACKAGE'))
        # PCAPdroid activity usually constructed like: com.example/.Activity
        pcapdroid_activity = str(self.cfg.get('PCAPDROID_ACTIVITY'))
        
        sanitized_package = re.sub(r'[^\w.-]+', '_', target_app_package)
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        if filename_template:
            # Replace placeholders like {run_id}, {step_num}, {timestamp}, {package}
            self.pcap_filename_on_device = filename_template.format(
                run_id=run_id or "X", 
                step_num=step_num or "Y", 
                timestamp=timestamp, 
                package=sanitized_package
            )
        else: # Default naming if template not provided
            self.pcap_filename_on_device = f"{sanitized_package}_run{run_id or 'X'}_step{step_num or 'Y'}_{timestamp}.pcap"


        # This is where the final PCAP file will be saved locally after pulling
        # --- MODIFIED PATH RESOLUTION ---
        # Resolve the path *now*, when the function is called, not in __init__.
        # We trust the config system to have resolved this path by this point.
        traffic_capture_dir = None
        try:
            # Trust the TRAFFIC_CAPTURE_OUTPUT_DIR property to return the fully resolved path
            traffic_capture_dir = str(self.cfg.TRAFFIC_CAPTURE_OUTPUT_DIR)
        except Exception as e:
            logging.error(f"Could not resolve self.cfg.TRAFFIC_CAPTURE_OUTPUT_DIR: {e}. Falling back.")
            
        if not traffic_capture_dir:
            try:
                # Fallback: Try to build it from SESSION_DIR manually
                session_dir = str(self.cfg.SESSION_DIR)
                # We check for template chars here as a *fallback* sanity check, not as the primary logic.
                if session_dir and '{' not in session_dir:
                    traffic_capture_dir = os.path.join(session_dir, 'traffic_captures')
                else:
                    logging.warning(f"Could not use SESSION_DIR as fallback (might be unresolved): {session_dir}")
                    traffic_capture_dir = None
            except Exception as e:
                logging.warning(f"Could not get SESSION_DIR as fallback: {e}")

        # Final hardcoded fallback if all else fails
        if not traffic_capture_dir:
            logging.error("All path resolution attempts failed, using hardcoded 'output_data/traffic_captures' fallback. Paths are not configured correctly.")
            traffic_capture_dir = os.path.join('output_data', 'traffic_captures')
        
        # Ensure the path is absolute (os.path.join may not be if base is relative)
        traffic_capture_dir = os.path.abspath(traffic_capture_dir)
        os.makedirs(traffic_capture_dir, exist_ok=True)
            
        self.local_pcap_file_path = os.path.join(traffic_capture_dir, self.pcap_filename_on_device)
        # --- END MODIFIED BLOCK ---

        logging.debug(f"Attempting to start traffic capture for app: {target_app_package}")
        logging.debug(f"PCAPdroid filename on device (pcap_name extra): {self.pcap_filename_on_device}")
        logging.debug(f"Local save path after pull: {self.local_pcap_file_path}")
        logging.debug("Ensure PCAPdroid is installed, granted remote control & VPN permissions.")

        # According to PCAPdroid API docs: https://github.com/emanuele-f/PCAPdroid/blob/master/docs/app_api.md
        # Command format: adb shell am start -e action [ACTION] -e api_key [API_KEY] -e [SETTINGS] -n com.emanuelef.remote_capture/.activities.CaptureCtrl
        # The pcap_name is just the filename (not full path), file will be saved to Download/PCAPdroid/
        pcap_filename_only = os.path.basename(self.pcap_filename_on_device)
        
        start_command_args = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'start',
            '-e', 'pcap_dump_mode', 'pcap_file',
            '-e', 'app_filter', target_app_package,
            '-e', 'pcap_name', pcap_filename_only,  # Just filename, not full path
        ]
        
        if self.cfg.get('PCAPDROID_TLS_DECRYPTION', False):
            start_command_args.extend(['-e', 'tls_decryption', 'true'])

        if self.cfg.get('PCAPDROID_API_KEY'):
            start_command_args.extend(['-e', 'api_key', str(self.cfg.get('PCAPDROID_API_KEY'))])
            logging.debug("Using PCAPdroid API key.")
        else:
            logging.warning("PCAPDROID_API_KEY not configured. User consent on device may be required.")

        stdout, retcode = await self._run_adb_command_async(start_command_args)

        # Check both return code and stderr for errors
        # ADB 'am start' may return 0 even if activity doesn't exist, but stderr will have the error
        if retcode != 0:
            logging.error(f"Failed to send PCAPdroid 'start' command. ADB retcode: {retcode}. Output: {stdout}")
            self.pcap_filename_on_device = None
            self.local_pcap_file_path = None
            self._is_currently_capturing = False
            return False
        
        # Also check stdout/stderr for error messages even if retcode is 0
        error_indicators = ['Error', 'error', 'does not exist', 'Activity class', 'Unable to resolve']
        if any(indicator in stdout for indicator in error_indicators):
            logging.error(f"PCAPdroid 'start' command failed (error in output). Output: {stdout}")
            self.pcap_filename_on_device = None
            self.local_pcap_file_path = None
            self._is_currently_capturing = False
            return False

        logging.info(f"PCAPdroid 'start' command sent successfully for {target_app_package}. Capture should be initializing.")
        self._is_currently_capturing = True
        
        # Wait for PCAPdroid to initialize (configurable)
        init_wait = float(self.cfg.get('PCAPDROID_INIT_WAIT', 3.0)) # Default 3s
        if init_wait > 0:
            logging.debug(f"Waiting {init_wait}s for PCAPdroid to initialize capture...")
            await asyncio.sleep(init_wait)
        return True

    async def stop_capture_and_pull_async(self, run_id: int, step_num: int) -> Optional[str]:
        """Stops PCAPdroid capture, pulls the file, and optionally cleans up."""
        if not self.traffic_capture_enabled:
            logging.debug("Traffic capture not enabled, skipping stop/pull.")
            return None
        if not self._is_currently_capturing or not self.pcap_filename_on_device:
            logging.warning("Traffic capture not started by this manager or filename not set. Cannot stop/pull.")
            return None

        pcapdroid_activity = str(self.cfg.get('PCAPDROID_ACTIVITY'))

        logging.debug("Attempting to stop PCAPdroid traffic capture...")
        # According to PCAPdroid API docs: use -n with activity name and -e action stop
        stop_command_args = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'stop'
        ]
        if self.cfg.get('PCAPDROID_API_KEY'):
            stop_command_args.extend(['-e', 'api_key', str(self.cfg.get('PCAPDROID_API_KEY'))])

        stdout_stop, retcode_stop = await self._run_adb_command_async(stop_command_args, suppress_stderr=True)
        self._is_currently_capturing = False # Assume stopped even if command had issues, to allow cleanup

        if retcode_stop != 0:
            logging.warning(f"PCAPdroid 'stop' command may have failed. ADB retcode: {retcode_stop}. Output: {stdout_stop}. Proceeding with pull attempt.")
        else:
            logging.debug("PCAPdroid 'stop' command sent successfully.")

        # Wait for file finalization (configurable)
        finalize_wait = float(self.cfg.get('PCAPDROID_FINALIZE_WAIT', 2.0)) # Default 2s
        if finalize_wait > 0:
            logging.debug(f"Waiting {finalize_wait}s for PCAP file finalization...")
            await asyncio.sleep(finalize_wait)

        # --- Pull the file ---
        if not self.local_pcap_file_path: # Should have been set in start_capture
            logging.error("Local PCAP file path not set. Cannot pull.")
            return None
            
        # Default PCAPdroid directory on device where pcap_name is saved
        device_pcap_base_dir = str(self.cfg.get('DEVICE_PCAP_DIR')) # e.g., "/sdcard/Download/PCAPdroid"
        device_pcap_full_path = os.path.join(device_pcap_base_dir, self.pcap_filename_on_device).replace("\\", "/")
        
        logging.debug(f"Attempting to pull PCAP file: '{device_pcap_full_path}' to '{self.local_pcap_file_path}'")
        pull_command_args = ['pull', device_pcap_full_path, self.local_pcap_file_path]
        stdout_pull, retcode_pull = await self._run_adb_command_async(pull_command_args)

        if retcode_pull != 0:
            logging.error(f"Failed to pull PCAP file '{device_pcap_full_path}'. ADB retcode: {retcode_pull}. Output: {stdout_pull}")
            logging.error("  Check if PCAPdroid started, if file exists on device (adb shell ls -l %s), and ADB permissions.", device_pcap_base_dir)
            return None # Failed to pull

        if os.path.exists(self.local_pcap_file_path):
            if os.path.getsize(self.local_pcap_file_path) > 0:
                logging.debug(f"PCAP file pulled successfully: {os.path.abspath(self.local_pcap_file_path)}")
                # Always cleanup device PCAP file after successful pull
                await self._cleanup_device_pcap_file_async(device_pcap_full_path)
                return os.path.abspath(self.local_pcap_file_path)
            else:
                logging.warning(f"PCAP file pulled to '{self.local_pcap_file_path}' but it is EMPTY.")
                # Always cleanup device PCAP file even if empty
                await self._cleanup_device_pcap_file_async(device_pcap_full_path)
                return os.path.abspath(self.local_pcap_file_path) # Return path even if empty
        else:
            logging.error(f"ADB pull command for '{device_pcap_full_path}' seemed to succeed, but local file '{self.local_pcap_file_path}' not found.")
            return None
            
    async def _cleanup_device_pcap_file_async(self, device_pcap_full_path: str):
        """Deletes the PCAP file from the device."""
        logging.debug(f"Cleaning up device PCAP file: {device_pcap_full_path}")
        rm_command_args = ['shell', 'rm', device_pcap_full_path]
        stdout_rm, retcode_rm = await self._run_adb_command_async(rm_command_args, suppress_stderr=True)
        if retcode_rm == 0:
            logging.debug(f"Device PCAP file '{device_pcap_full_path}' deleted successfully.")
        else:
            logging.warning(f"Failed to delete device PCAP file '{device_pcap_full_path}'. ADB retcode: {retcode_rm}. Output: {stdout_rm}")

    async def get_capture_status_async(self) -> Dict[str, Any]:
        """Gets the current capture status using PCAPdroid API (limited by ADB interaction)."""
        if not self.traffic_capture_enabled:
            return {"status": "disabled", "running": False, "error": "Traffic capture not enabled by config."}

        pcapdroid_activity = str(self.cfg.get('PCAPDROID_ACTIVITY'))

        logging.debug("Querying PCAPdroid capture status...")
        # According to PCAPdroid API docs: use -n with activity name and -e action get_status
        status_command_args = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'get_status'
        ]
        if self.cfg.get('PCAPDROID_API_KEY'):
            status_command_args.extend(['-e', 'api_key', str(self.cfg.get('PCAPDROID_API_KEY'))])

        stdout, retcode = await self._run_adb_command_async(status_command_args)

        if retcode != 0:
            logging.error(f"Failed to send 'get_status' command to PCAPdroid. ADB retcode: {retcode}. Output: {stdout}")
            return {"status": "error", "running": self._is_currently_capturing, "error_message": f"ADB command failed: {stdout}"}

        # Directly parsing complex status from 'am start' stdout is unreliable.
        # The 'running' status here is based on our manager's internal flag.
        # True status would require monitoring broadcast intents or logcat.
        logging.debug("PCAPdroid 'get_status' command sent. Output (may not be full status): %s", stdout)
        return {"status": "query_sent", "running": self._is_currently_capturing, "raw_output": stdout}