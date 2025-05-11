
import logging
import os
import re
import subprocess
import time
from typing import List, Tuple, Optional

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException

# Assuming 'config' is a module or object accessible for path configurations
# If not, these might need to be passed in or handled differently.
# For now, we'll try to use a global 'config' if available, or default.
try:
    from traverser_ai_api import config # Or your actual config module
except ImportError:
    config = type('Config', (object,), {
        'DEVICE_PCAP_DIR': '/sdcard/Download/PCAPdroid',
        'TRAFFIC_CAPTURE_OUTPUT_DIR': 'traffic_captures',
        'PCAPDROID_ACTIVITY': 'com.emanuelef.remote_capture/.activities.CaptureCtrl'
    })

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
                check=False, # Do not raise error, handle manually
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
        """Starts PCAPdroid traffic capture for the target application."""
        if not self.traffic_capture_enabled:
            return False

        driver_available_for_ui = self.driver and self.driver.driver
        if not driver_available_for_ui:
            logging.warning("Appium driver not connected at the start of start_traffic_capture. UI interaction for PCAPdroid dialogs will be skipped.")

        target_app_package = self.config_dict.get('APP_PACKAGE')
        if not target_app_package:
            logging.error("TARGET_APP_PACKAGE not configured. Cannot start traffic capture.")
            return False

        sanitized_package = re.sub(r'[^\w.-]+', '_', target_app_package)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.pcap_filename_on_device = f"{sanitized_package}_{timestamp}.pcap"
        
        device_pcap_dir = self.config_dict.get('DEVICE_PCAP_DIR', getattr(config, 'DEVICE_PCAP_DIR'))
        traffic_capture_output_dir = self.config_dict.get('TRAFFIC_CAPTURE_OUTPUT_DIR', getattr(config, 'TRAFFIC_CAPTURE_OUTPUT_DIR'))

        device_pcap_full_path = os.path.join(device_pcap_dir, self.pcap_filename_on_device).replace("\\", "/")

        os.makedirs(traffic_capture_output_dir, exist_ok=True)
        self.local_pcap_file_path = os.path.join(traffic_capture_output_dir, self.pcap_filename_on_device)

        logging.info(f"Attempting to start traffic capture. PCAP file: {self.pcap_filename_on_device}")
        logging.info(f"Expected device save path: {device_pcap_full_path}")
        logging.info(f"Local save path: {self.local_pcap_file_path}")

        pcapdroid_activity = self.config_dict.get('PCAPDROID_ACTIVITY', getattr(config, 'PCAPDROID_ACTIVITY'))

        start_command = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'start',
            '-e', 'pcap_dump_mode', 'pcap_file',
            '-e', 'app_filter', target_app_package,
            '-e', 'pcap_name', self.pcap_filename_on_device,
            '-e', 'tls_decryption', 'true'
        ]
        
        logging.info("\n" + "="*50)
        logging.info("PCAPDROID TRAFFIC CAPTURE:")
        logging.info(f"Ensure PCAPdroid is installed and has been granted remote control & VPN permissions.")
        logging.info(f"Targeting app: {target_app_package}")
        logging.info("If this is the first time or permissions were reset, you MAY need to:")
        logging.info("  1. Approve 'shell'/'remote control' permission for PCAPdroid on the device.")
        logging.info("  2. Approve VPN connection request from PCAPdroid on the device.")
        logging.info("Check PCAPdroid notifications on device if capture doesn't start.")
        logging.info("="*50 + "\n")

        stdout, retcode = self._run_adb_command_for_capture(start_command)

        if retcode != 0:
            logging.error(f"Failed to send PCAPdroid 'start' command. ADB retcode: {retcode}. Output: {stdout}")
            return False
        
        logging.info(f"PCAPdroid 'start' command sent. Capture should be initializing for {target_app_package}.")
        
        if driver_available_for_ui:
            time.sleep(2) 
            try:
                logging.info("Checking for PCAPdroid VPN confirmation dialog to click 'ALLOW'...")
                allow_button = None
                try:
                    logging.debug("Attempting to find 'ALLOW' button by exact text (uppercase)...")
                    allow_button = self.driver.driver.find_element(AppiumBy.XPATH, "//*[@text='ALLOW']")
                except NoSuchElementException:
                    logging.debug("'ALLOW' (uppercase) button not found. Trying 'Allow' (title case)...")
                    try:
                        allow_button = self.driver.driver.find_element(AppiumBy.XPATH, "//*[@text='Allow']")
                    except NoSuchElementException:
                        logging.debug("'Allow' (title case) button not found. Trying by common Android ID 'android:id/button1'...")
                        try:
                            allow_button = self.driver.driver.find_element(AppiumBy.ID, "android:id/button1")
                        except NoSuchElementException:
                            logging.info("PCAPdroid 'ALLOW' button not found by text or common ID. Assuming already permitted or dialog not present.")

                if allow_button and allow_button.is_displayed():
                    logging.info("PCAPdroid 'ALLOW' button found. Attempting to click...")
                    allow_button.click()
                    logging.info("Clicked PCAPdroid 'ALLOW' button successfully.")
                    time.sleep(1.5)
                elif allow_button:
                    logging.info("PCAPdroid 'ALLOW' button was found but is not currently displayed. Proceeding...")
                else:
                    logging.info("PCAPdroid 'ALLOW' button was not found. Proceeding, assuming it's not needed or already handled.")

            except Exception as e:
                logging.warning(f"An error occurred while trying to find and click the PCAPdroid 'ALLOW' button: {e}. Capture might fail if permission is required and was not granted.")
        else:
            logging.warning("Appium driver not available for PCAPdroid 'ALLOW' button interaction. Skipping.")

        time.sleep(self.config_dict.get('WAIT_AFTER_ACTION', 2.0))
        return True

    def stop_traffic_capture(self) -> bool:
        """Stops PCAPdroid traffic capture."""
        if not self.traffic_capture_enabled or not self.pcap_filename_on_device:
            logging.debug("Traffic capture was not enabled or not started by this manager. Skipping stop.")
            return False

        driver_available_for_ui = self.driver and self.driver.driver
        if not driver_available_for_ui:
            logging.warning("Appium driver not connected at the start of stop_traffic_capture. UI interaction for PCAPdroid dialogs will be skipped.")

        logging.info("Attempting to stop PCAPdroid traffic capture...")
        pcapdroid_activity = self.config_dict.get('PCAPDROID_ACTIVITY', getattr(config, 'PCAPDROID_ACTIVITY'))
        stop_command = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'stop'
        ]
        stdout, retcode = self._run_adb_command_for_capture(stop_command, suppress_stderr=True)

        if retcode != 0:
            logging.warning(f"Failed to send 'stop' command to PCAPdroid. ADB retcode: {retcode}. Output: {stdout}. Will attempt to pull file anyway.")

        logging.info("PCAPdroid 'stop' command sent. Checking for confirmation dialog...")

        if driver_available_for_ui:
            time.sleep(1.5)
            try:
                logging.info("Checking for PCAPdroid VPN disconnect confirmation dialog...")
                confirm_button = None
                button_texts_to_try = ["OK", "DISCONNECT", "ALLOW", "Allow", "Ok"]

                for btn_text in button_texts_to_try:
                    try:
                        logging.debug(f"Attempting to find disconnect confirmation button by text: '{btn_text}'")
                        confirm_button = self.driver.driver.find_element(AppiumBy.XPATH, f"//*[@text='{btn_text}']")
                        if confirm_button and confirm_button.is_displayed():
                            logging.info(f"Found disconnect confirmation button with text: '{btn_text}'")
                            break
                        else:
                            confirm_button = None
                    except NoSuchElementException:
                        logging.debug(f"Disconnect confirmation button with text '{btn_text}' not found.")
                        continue
                
                if not confirm_button:
                    logging.debug("Disconnect confirmation button not found by text. Trying by common Android ID 'android:id/button1'...")
                    try:
                        confirm_button = self.driver.driver.find_element(AppiumBy.ID, "android:id/button1")
                        if not (confirm_button and confirm_button.is_displayed()):
                            confirm_button = None
                    except NoSuchElementException:
                        logging.debug("Disconnect confirmation button not found by 'android:id/button1'.")
                
                if not confirm_button:
                    logging.debug("Trying by common Android ID 'android:id/button2'...")
                    try:
                        confirm_button = self.driver.driver.find_element(AppiumBy.ID, "android:id/button2")
                        if not (confirm_button and confirm_button.is_displayed()):
                            confirm_button = None
                    except NoSuchElementException:
                        logging.debug("Disconnect confirmation button not found by 'android:id/button2'.")

                if confirm_button and confirm_button.is_displayed():
                    logging.info(f"Disconnect confirmation button found (text: '{confirm_button.text if hasattr(confirm_button, 'text') else 'N/A'}', id: '{confirm_button.id}'). Attempting to click...")
                    confirm_button.click()
                    logging.info("Clicked PCAPdroid disconnect confirmation button successfully.")
                    time.sleep(1.0)
                elif confirm_button:
                    logging.info("Disconnect confirmation button was found but is not currently displayed. Proceeding...")
                else:
                    logging.info("PCAPdroid disconnect confirmation button was not found. Proceeding, assuming it's not needed or already handled.")

            except Exception as e:
                logging.warning(f"An error occurred while trying to find and click the PCAPdroid disconnect confirmation button: {e}.")
        else:
            logging.warning("Appium driver not available for PCAPdroid disconnect confirmation. Skipping UI interaction.")
        
        if retcode != 0:
            logging.warning(f"Original ADB 'stop' command had failed (retcode: {retcode}). Traffic capture might not have stopped cleanly on device.")
            return False # Return False if ADB command failed, regardless of UI interaction outcome

        logging.info("PCAPdroid 'stop' sequence completed. Waiting for file finalization...")
        time.sleep(self.config_dict.get('WAIT_AFTER_ACTION', 2.0))
        return True

    def pull_traffic_capture_file(self) -> bool:
        """Pulls the PCAP file from the device."""
        if not self.traffic_capture_enabled or not self.pcap_filename_on_device or not self.local_pcap_file_path:
            logging.debug("Cannot pull PCAP file: capture not enabled, filename not set, or local path not set.")
            return False

        device_pcap_dir = self.config_dict.get('DEVICE_PCAP_DIR', getattr(config, 'DEVICE_PCAP_DIR'))
        device_pcap_full_path = os.path.join(device_pcap_dir, self.pcap_filename_on_device).replace("\\", "/")
        logging.info(f"Attempting to pull PCAP file: {device_pcap_full_path} to {self.local_pcap_file_path}")

        pull_command = ['pull', device_pcap_full_path, self.local_pcap_file_path]
        stdout, retcode = self._run_adb_command_for_capture(pull_command)

        if retcode != 0:
            logging.error(f"Failed to pull PCAP file '{device_pcap_full_path}'. ADB retcode: {retcode}. Output: {stdout}")
            logging.error("Possible reasons: Capture didn't start, no traffic, incorrect path, or storage issues.")
            logging.info(f"  Manually check with: adb shell ls -l {device_pcap_dir}")
            return False

        if os.path.exists(self.local_pcap_file_path):
            if os.path.getsize(self.local_pcap_file_path) > 0:
                logging.info(f"PCAP file pulled successfully to: {os.path.abspath(self.local_pcap_file_path)}")
                return True
            else:
                logging.warning(f"PCAP file pulled to '{self.local_pcap_file_path}' but it is EMPTY (0 bytes).")
                return True 
        else:
            logging.error(f"ADB pull command seemed to succeed for '{device_pcap_full_path}', but local file '{self.local_pcap_file_path}' not found.")
            return False
            
    def cleanup_device_pcap_file(self):
        """Deletes the PCAP file from the device if configured."""
        if not self.traffic_capture_enabled or not self.pcap_filename_on_device or not self.config_dict.get('CLEANUP_DEVICE_PCAP_FILE', False):
            return

        device_pcap_dir = self.config_dict.get('DEVICE_PCAP_DIR', getattr(config, 'DEVICE_PCAP_DIR'))
        device_pcap_full_path = os.path.join(device_pcap_dir, self.pcap_filename_on_device).replace("\\", "/")
        logging.info(f"Cleaning up device PCAP file: {device_pcap_full_path}")
        rm_command = ['shell', 'rm', device_pcap_full_path]
        stdout, retcode = self._run_adb_command_for_capture(rm_command, suppress_stderr=True)
        if retcode == 0:
            logging.info(f"Device PCAP file '{device_pcap_full_path}' deleted successfully.")
        else:
            logging.warning(f"Failed to delete device PCAP file '{device_pcap_full_path}'. ADB retcode: {retcode}. Output: {stdout}")

