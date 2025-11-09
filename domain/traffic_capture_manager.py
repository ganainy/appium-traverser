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
    from config.config import Config  # Adjust path as necessary
except ImportError:
    from config.config import Config  # Adjust path as necessary

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
                'PCAPDROID_PACKAGE', 'PCAPDROID_ACTIVITY', 'DEVICE_PCAP_DIR' 
                # PCAPDROID_API_KEY is optional but recommended
                # CLEANUP_DEVICE_PCAP_FILE is optional
            ]
            for cfg_key in required_pcap_configs:
                if self.cfg.get(cfg_key) is None:
                    # Allow DEVICE_PCAP_DIR to be None and default later
                    if cfg_key == 'DEVICE_PCAP_DIR' and self.cfg.get(cfg_key) is None:
                        continue
                    raise ValueError(f"TrafficCaptureManager: Required config '{cfg_key}' not found or is None.")
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
            
            # subprocess.run is blocking, use asyncio.to_thread for non-blocking behavior in async context
            # Or, for simpler cases where the ADB command is quick, direct run might be acceptable,
            # but true async would use asyncio.create_subprocess_shell or a library.
            # For now, let's simulate with a direct run as it's simpler to integrate.
            # If these ADB commands are long-running, proper async subprocess is better.
            
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
            return result.stdout.strip(), result.returncode
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
        self.local_pcap_file_path = os.path.join(
            str(self.cfg.get('TRAFFIC_CAPTURE_OUTPUT_DIR')), 
            self.pcap_filename_on_device
        )
        os.makedirs(str(self.cfg.get('TRAFFIC_CAPTURE_OUTPUT_DIR')), exist_ok=True)

        logging.debug(f"Attempting to start traffic capture for app: {target_app_package}")
        logging.debug(f"PCAPdroid filename on device (pcap_name extra): {self.pcap_filename_on_device}")
        logging.debug(f"Local save path after pull: {self.local_pcap_file_path}")
        logging.debug("Ensure PCAPdroid is installed, granted remote control & VPN permissions.")

        start_command_args = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'start',
            '-e', 'pcap_dump_mode', 'pcap_file', # As per documentation
            '-e', 'app_filter', target_app_package,
            '-e', 'pcap_name', self.pcap_filename_on_device, # This sets filename in Download/PCAPdroid/
            # Optional: enable TLS decryption if PCAPdroid is set up for it (requires root/special setup)
            # '-e', 'tls_decryption', 'true' # Add to config if desired
        ]
        if self.cfg.get('PCAPDROID_TLS_DECRYPTION', False): # Example config flag
            start_command_args.extend(['-e', 'tls_decryption', 'true'])

        if self.cfg.get('PCAPDROID_API_KEY'):
            start_command_args.extend(['-e', 'api_key', str(self.cfg.get('PCAPDROID_API_KEY'))])
            logging.debug("Using PCAPdroid API key.")
        else:
            logging.warning("PCAPDROID_API_KEY not configured. User consent on device may be required.")

        stdout, retcode = await self._run_adb_command_async(start_command_args)

        if retcode != 0:
            logging.error(f"Failed to send PCAPdroid 'start' command. ADB retcode: {retcode}. Output: {stdout}")
            self.pcap_filename_on_device = None # Reset on failure
            self.local_pcap_file_path = None
            self._is_currently_capturing = False
            return False

        logging.debug(f"PCAPdroid 'start' command sent successfully for {target_app_package}. Capture should be initializing.")
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
        stop_command_args = ['shell', 'am', 'start', '-n', pcapdroid_activity, '-e', 'action', 'stop']
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
                if bool(self.cfg.get('CLEANUP_DEVICE_PCAP_FILE')):
                    await self._cleanup_device_pcap_file_async(device_pcap_full_path)
                return os.path.abspath(self.local_pcap_file_path)
            else:
                logging.warning(f"PCAP file pulled to '{self.local_pcap_file_path}' but it is EMPTY.")
                # Still try cleanup if configured, as an empty file might have been created
                if bool(self.cfg.get('CLEANUP_DEVICE_PCAP_FILE')):
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
        status_command_args = ['shell', 'am', 'start', '-n', pcapdroid_activity, '-e', 'action', 'get_status']
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
