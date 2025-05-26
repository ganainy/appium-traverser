import logging
import os
import re
import subprocess
import time
from typing import List, Tuple, Optional

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException

# Assuming 'traverser_ai_api.config' would handle loading .env variables
# For example, it might load PCAPDROID_API_KEY into the config_dict
from traverser_ai_api import config

class TrafficCaptureManager:
    def __init__(self, driver, config_dict: dict, traffic_capture_enabled: bool):
        self.driver = driver  # This is an instance of AppiumDriverWrapper
        self.config_dict = config_dict
        self.traffic_capture_enabled = traffic_capture_enabled
        self.pcap_filename_on_device: Optional[str] = None
        self.local_pcap_file_path: Optional[str] = None

    def _run_adb_command_for_capture(self, command_list: List[str], suppress_stderr: bool = False) -> Tuple[str, int]:
        """
        Helper to run ADB commands specifically for traffic capture.
        """
        try:
            adb_command = ['adb'] + command_list
            logging.info(f"--- Running ADB for Capture: {' '.join(adb_command)}")
            result = subprocess.run(
                adb_command,
                capture_output=True,
                text=True,
                check=False,  # Do not raise error, handle manually
                encoding='utf-8',
                errors='ignore',
            )
            if result.stdout:
                logging.debug(f"--- ADB STDOUT (Capture):\n{result.stdout.strip()}")
            if result.stderr and not suppress_stderr:
                logging.error(f"--- ADB STDERR (Capture):\n{result.stderr.strip()}")
            return result.stdout.strip(), result.returncode
        except FileNotFoundError:
            logging.error("ADB command not found. Ensure ADB is in PATH.")
            return "ADB_NOT_FOUND", -1
        except Exception as e:
            logging.error(f"Exception in _run_adb_command_for_capture: {e}")
            return str(e), -1

    def start_traffic_capture(self) -> bool:
        """Starts PCAPdroid traffic capture for the target application using the official API."""
        if not self.traffic_capture_enabled:
            return False

        driver_available_for_ui = self.driver and self.driver.driver
        if not driver_available_for_ui:
            logging.warning("Appium driver not connected at the start of start_traffic_capture. UI interaction for PCAPdroid dialogs will be skipped.")

        # Check required config values
        try:
            target_app_package = self.config_dict['APP_PACKAGE']
            traffic_capture_output_dir = self.config_dict['TRAFFIC_CAPTURE_OUTPUT_DIR']
            wait_after_action = self.config_dict['WAIT_AFTER_ACTION']
        except KeyError as e:
            logging.error(f"{str(e)} not configured. Cannot start traffic capture.")
            return False

        pcapdroid_activity = "com.emanuelef.remote_capture/.activities.CaptureCtrl"
        sanitized_package = re.sub(r'[^\w.-]+', '_', target_app_package)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.pcap_filename_on_device = f"{sanitized_package}_{timestamp}.pcap"

        # Determine device PCAP directory for logging (PCAPdroid saves to its own directory)
        # Default is /sdcard/Download/PCAPdroid/ as per PCAPdroid >= 1.6.0
        device_pcap_dir_for_logging = self.config_dict.get('DEVICE_PCAP_DIR', "/sdcard/Download/PCAPdroid")
        expected_device_pcap_full_path = os.path.join(device_pcap_dir_for_logging, self.pcap_filename_on_device).replace("\\", "/")

        os.makedirs(traffic_capture_output_dir, exist_ok=True)
        self.local_pcap_file_path = os.path.join(traffic_capture_output_dir, self.pcap_filename_on_device)

        logging.info(f"Attempting to start traffic capture. PCAP file: {self.pcap_filename_on_device}")
        logging.info(f"Expected device save path (used for pull/cleanup reference): {expected_device_pcap_full_path}") #
        logging.info(f"Local save path: {self.local_pcap_file_path}") #

        logging.info("\n" + "="*50)
        logging.info("PCAPDROID TRAFFIC CAPTURE (Official API):") #
        logging.info(f"Ensure PCAPdroid is installed and has been granted remote control & VPN permissions.") #
        logging.info(f"Targeting app: {target_app_package}") #
        logging.info("If this is the first time or permissions were reset, you MAY need to:") #
        logging.info("  1. Approve 'shell'/'remote control' permission for PCAPdroid on the device.") #
        logging.info("  2. Approve VPN connection request from PCAPdroid on the device.") #
        logging.info("  3. Consider setting up an API key to skip permission prompts.") #
        logging.info("Check PCAPdroid notifications on device if capture doesn't start.") #
        logging.info("="*50 + "\n")

        start_command = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'start',
            '-e', 'pcap_dump_mode', 'pcap_file',
            '-e', 'app_filter', target_app_package,
            '-e', 'pcap_name', self.pcap_filename_on_device,
            '-e', 'tls_decryption', 'true' #
        ]

        api_key = self.config_dict.get('PCAPDROID_API_KEY') #
        if api_key:
            start_command.extend(['-e', 'api_key', api_key]) #
            logging.info("Using API key for PCAPdroid authentication.") #
        else:
            logging.info("No API key configured. User consent may be required.") #

        stdout, retcode = self._run_adb_command_for_capture(start_command)

        if retcode != 0:
            logging.error(f"Failed to send PCAPdroid 'start' command. ADB retcode: {retcode}. Output: {stdout}") #
            return False

        logging.info(f"PCAPdroid 'start' command sent successfully. Capture should be initializing for {target_app_package}.") #

        if driver_available_for_ui:
            time.sleep(2)
            try:
                logging.info("Checking for PCAPdroid VPN confirmation dialog to click 'ALLOW'...") #
                allow_button = None
                try:
                    logging.debug("Attempting to find 'ALLOW' button by exact text (uppercase)...") #
                    allow_button = self.driver.driver.find_element(AppiumBy.XPATH, "//*[@text='ALLOW']") #
                except NoSuchElementException:
                    logging.debug("'ALLOW' (uppercase) button not found. Trying 'Allow' (title case)...") #
                    try:
                        allow_button = self.driver.driver.find_element(AppiumBy.XPATH, "//*[@text='Allow']") #
                    except NoSuchElementException:
                        logging.debug("'Allow' (title case) button not found. Trying by common Android ID 'android:id/button1'...") #
                        try:
                            allow_button = self.driver.driver.find_element(AppiumBy.ID, "android:id/button1") #
                        except NoSuchElementException:
                            logging.info("PCAPdroid 'ALLOW' button not found by text or common ID. Assuming already permitted or dialog not present.") #

                if allow_button and allow_button.is_displayed():
                    logging.info("PCAPdroid 'ALLOW' button found. Attempting to click...") #
                    allow_button.click() #
                    logging.info("Clicked PCAPdroid 'ALLOW' button successfully.") #
                    time.sleep(1.5) #
                elif allow_button:
                    logging.info("PCAPdroid 'ALLOW' button was found but is not currently displayed. Proceeding...") #
                else:
                    # This log was "PCAPdroid 'ALLOW' button was not found. Proceeding, assuming it's not needed or already handled."
                    # The more specific one from the try-except is better if it reached there.
                    pass # Already logged if not found by any means

            except Exception as e:
                logging.warning(f"An error occurred while trying to find and click the PCAPdroid 'ALLOW' button: {e}. Capture might fail if permission is required and was not granted.") #
        else:
            logging.warning("Appium driver not available for PCAPdroid 'ALLOW' button interaction. Skipping.") #

        time.sleep(wait_after_action) #
        return True

    def stop_traffic_capture(self) -> bool:
        """Stops PCAPdroid traffic capture using the official API."""
        if not self.traffic_capture_enabled or not self.pcap_filename_on_device:
            logging.debug("Traffic capture was not enabled or not started by this manager. Skipping stop.") #
            return False

        driver_available_for_ui = self.driver and self.driver.driver
        if not driver_available_for_ui:
            logging.warning("Appium driver not connected at the start of stop_traffic_capture. UI interaction for PCAPdroid dialogs will be skipped.") #

        try:
            wait_after_action = self.config_dict['WAIT_AFTER_ACTION'] #
        except KeyError as e:
            logging.error(f"{str(e)} not configured. Cannot stop traffic capture.") #
            return False

        pcapdroid_activity = "com.emanuelef.remote_capture/.activities.CaptureCtrl" #
        logging.info("Attempting to stop PCAPdroid traffic capture using official API...") #

        stop_command = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'stop' #
        ]

        api_key = self.config_dict.get('PCAPDROID_API_KEY') #
        if api_key:
            stop_command.extend(['-e', 'api_key', api_key]) #
            logging.info("Using API key for PCAPdroid stop command.") #

        stdout, retcode = self._run_adb_command_for_capture(stop_command, suppress_stderr=True) #

        if retcode != 0:
            logging.warning(f"Failed to send 'stop' command to PCAPdroid. ADB retcode: {retcode}. Output: {stdout}. Will attempt to pull file anyway.") #

        logging.info("PCAPdroid 'stop' command sent. Checking for confirmation dialog...") #

        if driver_available_for_ui:
            time.sleep(1.5) #
            try:
                logging.info("Checking for PCAPdroid VPN disconnect confirmation dialog...") #
                confirm_button = None
                button_texts_to_try = ["OK", "DISCONNECT", "ALLOW", "Allow", "Ok"] #

                for btn_text in button_texts_to_try:
                    try:
                        logging.debug(f"Attempting to find disconnect confirmation button by text: '{btn_text}'") #
                        confirm_button = self.driver.driver.find_element(AppiumBy.XPATH, f"//*[@text='{btn_text}']") #
                        if confirm_button and confirm_button.is_displayed():
                            logging.info(f"Found disconnect confirmation button with text: '{btn_text}'") #
                            break
                        else:
                            confirm_button = None
                    except NoSuchElementException:
                        logging.debug(f"Disconnect confirmation button with text '{btn_text}' not found.") #
                        continue
                
                if not confirm_button:
                    logging.debug("Disconnect confirmation button not found by text. Trying by common Android ID 'android:id/button1'...") #
                    try:
                        confirm_button = self.driver.driver.find_element(AppiumBy.ID, "android:id/button1") #
                        if not (confirm_button and confirm_button.is_displayed()): #
                            confirm_button = None
                    except NoSuchElementException:
                        logging.debug("Disconnect confirmation button not found by 'android:id/button1'.") #
                
                if not confirm_button:
                    logging.debug("Trying by common Android ID 'android:id/button2'...") #
                    try:
                        confirm_button = self.driver.driver.find_element(AppiumBy.ID, "android:id/button2") #
                        if not (confirm_button and confirm_button.is_displayed()): #
                            confirm_button = None
                    except NoSuchElementException:
                        logging.debug("Disconnect confirmation button not found by 'android:id/button2'.") #

                if confirm_button and confirm_button.is_displayed():
                    logging.info(f"Disconnect confirmation button found (text: '{confirm_button.text if hasattr(confirm_button, 'text') else 'N/A'}', id: '{confirm_button.id}'). Attempting to click...") #
                    confirm_button.click() #
                    logging.info("Clicked PCAPdroid disconnect confirmation button successfully.") #
                    time.sleep(1.0) #
                elif confirm_button:
                    logging.info("Disconnect confirmation button was found but is not currently displayed. Proceeding...") #
                else:
                    logging.info("PCAPdroid disconnect confirmation button was not found. Proceeding, assuming it's not needed or already handled.") #

            except Exception as e:
                logging.warning(f"An error occurred while trying to find and click the PCAPdroid disconnect confirmation button: {e}.") #
        else:
            logging.warning("Appium driver not available for PCAPdroid disconnect confirmation. Skipping UI interaction.") #
        
        if retcode != 0:
            logging.warning(f"Original ADB 'stop' command had failed (retcode: {retcode}). Traffic capture might not have stopped cleanly on device.") #
            return False # Return False if ADB command failed, regardless of UI interaction outcome

        logging.info("PCAPdroid 'stop' sequence completed. Waiting for file finalization...") #
        time.sleep(wait_after_action) #
        return True

    def pull_traffic_capture_file(self) -> bool:
        """Pulls the PCAP file from the device.
        
        Note: Since PCAPdroid 1.6.0, PCAP files are saved to Download/PCAPdroid/ directory by default.
        """
        if not self.traffic_capture_enabled or not self.pcap_filename_on_device or not self.local_pcap_file_path:
            logging.debug("Cannot pull PCAP file: capture not enabled, filename not set, or local path not set.") #
            return False

        # Default PCAPdroid directory
        device_pcap_dir = "/sdcard/Download/PCAPdroid" #
        
        # Use custom directory from config if provided
        if 'DEVICE_PCAP_DIR' in self.config_dict: #
            device_pcap_dir = self.config_dict['DEVICE_PCAP_DIR'] #
            logging.info(f"Using custom PCAP directory: {device_pcap_dir}") #
        else:
            logging.info(f"Using default PCAPdroid directory: {device_pcap_dir}") #

        device_pcap_full_path = os.path.join(device_pcap_dir, self.pcap_filename_on_device).replace("\\", "/") #
        logging.info(f"Attempting to pull PCAP file: {device_pcap_full_path} to {self.local_pcap_file_path}") #

        pull_command = ['pull', device_pcap_full_path, self.local_pcap_file_path] #
        stdout, retcode = self._run_adb_command_for_capture(pull_command)

        if retcode != 0:
            logging.error(f"Failed to pull PCAP file '{device_pcap_full_path}'. ADB retcode: {retcode}. Output: {stdout}") #
            logging.error("Possible reasons: Capture didn't start, no traffic, incorrect path, or storage issues.") #
            logging.info(f"  Manually check with: adb shell ls -l {device_pcap_dir}") #
            return False

        if os.path.exists(self.local_pcap_file_path):
            if os.path.getsize(self.local_pcap_file_path) > 0: #
                logging.info(f"PCAP file pulled successfully to: {os.path.abspath(self.local_pcap_file_path)}") #
                return True
            else:
                logging.warning(f"PCAP file pulled to '{self.local_pcap_file_path}' but it is EMPTY (0 bytes).") #
                return True 
        else:
            logging.error(f"ADB pull command seemed to succeed for '{device_pcap_full_path}', but local file '{self.local_pcap_file_path}' not found.") #
            return False
            
    def cleanup_device_pcap_file(self):
        """Deletes the PCAP file from the device if configured."""
        try:
            cleanup_enabled = self.config_dict['CLEANUP_DEVICE_PCAP_FILE'] #
        except KeyError:
            logging.info("CLEANUP_DEVICE_PCAP_FILE not configured. Skipping cleanup.") #
            return

        if not self.traffic_capture_enabled or not self.pcap_filename_on_device or not cleanup_enabled: #
            return

        device_pcap_dir = "/sdcard/Download/PCAPdroid" #
        if 'DEVICE_PCAP_DIR' in self.config_dict: #
            device_pcap_dir = self.config_dict['DEVICE_PCAP_DIR'] #

        device_pcap_full_path = os.path.join(device_pcap_dir, self.pcap_filename_on_device).replace("\\", "/") #
        logging.info(f"Cleaning up device PCAP file: {device_pcap_full_path}") #
        rm_command = ['shell', 'rm', device_pcap_full_path] #
        stdout, retcode = self._run_adb_command_for_capture(rm_command, suppress_stderr=True) #
        if retcode == 0:
            logging.info(f"Device PCAP file '{device_pcap_full_path}' deleted successfully.") #
        else:
            logging.warning(f"Failed to delete device PCAP file '{device_pcap_full_path}'. ADB retcode: {retcode}. Output: {stdout}") #

    def get_capture_status(self) -> dict:
        """Gets the current capture status using the official PCAPdroid API.
        
        Returns:
            dict: Contains version_name, version_code, running status, and capture stats if available
        """
        if not self.traffic_capture_enabled:
            return {"error": "Traffic capture not enabled"} #

        pcapdroid_activity = "com.emanuelef.remote_capture/.activities.CaptureCtrl" #
        logging.info("Querying PCAPdroid capture status...") #
        
        status_command = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'get_status' #
        ]

        api_key = self.config_dict.get('PCAPDROID_API_KEY') #
        if api_key:
            status_command.extend(['-e', 'api_key', api_key]) #

        stdout, retcode = self._run_adb_command_for_capture(status_command)

        if retcode != 0:
            logging.error(f"Failed to get PCAPdroid status. ADB retcode: {retcode}. Output: {stdout}") #
            return {"error": f"Failed to get status: {stdout}"} #

        # Note: The actual status from PCAPdroid is typically returned via a broadcast intent result,
        # which is complex to capture directly with subprocess.run. 
        # This simplified version just confirms the command was sent.
        # For a full implementation, one might need to monitor logcat for PCAPdroid's response
        # or use a more advanced ADB interaction method.
        logging.info("PCAPdroid status query sent successfully.") #
        return {"status": "query_sent", "output": stdout} #