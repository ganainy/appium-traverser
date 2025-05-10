import logging
import time
import os
import re # Added re
from typing import Optional, Tuple, List, Dict, Any
from io import BytesIO # Added BytesIO
from PIL import Image # Added Image

# Import local modules
from . import config
from . import utils
from .ai_assistant import AIAssistant
from .appium_driver import AppiumDriver
from .state_manager import CrawlingState, ScreenRepresentation
from .database import DatabaseManager
from selenium.webdriver.remote.webelement import WebElement
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, InvalidSelectorException # Added InvalidSelectorException

# --- Import for traffic capture ---
import subprocess
import sys
# --- End import for traffic capture ---

# --- UI Communication Prefixes ---
UI_STATUS_PREFIX = "UI_STATUS:"
UI_STEP_PREFIX = "UI_STEP:"
UI_ACTION_PREFIX = "UI_ACTION:"
UI_SCREENSHOT_PREFIX = "UI_SCREENSHOT:"
UI_END_PREFIX = "UI_END:"
# --- End UI Communication Prefixes ---

class AppCrawler:
    """Orchestrates the AI-driven app crawling process."""

    def __init__(self, config_dict: dict): # Added config_dict parameter
        self.config_dict = config_dict # Use passed config_dict
        self.driver = AppiumDriver(self.config_dict.get('APPIUM_SERVER_URL'), self.config_dict) # Use .get for safety
        # Update AI Assistant initialization to use default model type
        self.ai_assistant = AIAssistant(
            api_key=self.config_dict.get('GEMINI_API_KEY'), # Use .get
            model_name=self.config_dict.get('DEFAULT_MODEL_TYPE', 'pro-vision'), # Use .get
            safety_settings=self.config_dict.get('AI_SAFETY_SETTINGS') # Use .get
        )
        self.db_manager = DatabaseManager(self.config_dict.get('DB_NAME')) # Use .get
        self.state_manager: Optional[CrawlingState] = None

        # Failure counters
        self.consecutive_ai_failures = 0
        self.consecutive_map_failures = 0
        self.consecutive_exec_failures = 0

        # State tracking variables used within run()
        self._last_action_description: str = "START"
        self.previous_composite_hash: Optional[str] = None

        # ---Initialize element finding strategy order ---
        # Each tuple: (key, appium_by_strategy_or_None, log_name)
        self.element_finding_strategies = [
            ('id', AppiumBy.ID, "ID"),
            ('acc_id', AppiumBy.ACCESSIBILITY_ID, "Accessibility ID"),
            ('xpath_exact', None, "XPath Exact Text"),
            ('xpath_contains', None, "XPath Contains")
        ]
        logging.info(f"Initial element finding strategy order: {[s[2] for s in self.element_finding_strategies]}")

        # --- Traffic Capture Members ---
        self.traffic_capture_enabled = getattr(config, 'ENABLE_TRAFFIC_CAPTURE', False)
        self.pcap_filename_on_device: Optional[str] = None
        self.local_pcap_file_path: Optional[str] = None
        # --- End Traffic Capture Members ---


    def _run_adb_command_for_capture(self, command_list: List[str], suppress_stderr: bool = False) -> Tuple[str, int]:
        """
        Helper to run ADB commands specifically for traffic capture.
        Simplified version of the one in capture_app_traffic.py.
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

    def _start_traffic_capture(self) -> bool:
        """Starts PCAPdroid traffic capture for the target application."""
        if not self.traffic_capture_enabled:
            return False

        # Ensure driver is connected for UI interactions with PCAPdroid dialogs
        # This check is a safeguard; run() should connect the driver beforehand.
        driver_available_for_ui = self.driver and self.driver.driver
        if not driver_available_for_ui:
            logging.warning("Appium driver not connected at the start of _start_traffic_capture. UI interaction for PCAPdroid dialogs will be skipped.")

        target_app_package = self.config_dict.get('APP_PACKAGE')
        if not target_app_package:
            logging.error("TARGET_APP_PACKAGE not configured. Cannot start traffic capture.")
            return False

        # Sanitize package name for filename
        sanitized_package = re.sub(r'[^\\w.-]+', '_', target_app_package) # Corrected regex
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.pcap_filename_on_device = f"{sanitized_package}_{timestamp}.pcap"
        
        # Use config attributes for paths
        device_pcap_dir = getattr(config, 'DEVICE_PCAP_DIR', '/sdcard/Download/PCAPdroid')
        traffic_capture_output_dir = getattr(config, 'TRAFFIC_CAPTURE_OUTPUT_DIR', 'traffic_captures')

        device_pcap_full_path = os.path.join(device_pcap_dir, self.pcap_filename_on_device).replace("\\\\", "/")

        # Prepare local path
        os.makedirs(traffic_capture_output_dir, exist_ok=True)
        self.local_pcap_file_path = os.path.join(traffic_capture_output_dir, self.pcap_filename_on_device)

        logging.info(f"Attempting to start traffic capture. PCAP file: {self.pcap_filename_on_device}")
        logging.info(f"Expected device save path: {device_pcap_full_path}")
        logging.info(f"Local save path: {self.local_pcap_file_path}")

        pcapdroid_activity = getattr(config, 'PCAPDROID_ACTIVITY', 'com.emanuelef.remote_capture/.activities.CaptureCtrl')

        start_command = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'start',
            '-e', 'pcap_dump_mode', 'pcap_file',
            '-e', 'app_filter', target_app_package,
            '-e', 'pcap_name', self.pcap_filename_on_device,
            '-e', 'tls_decryption', 'true' # Assuming CA cert is installed on device
        ]
        
        logging.info("\\n" + "="*50)
        logging.info("PCAPDROID TRAFFIC CAPTURE:")
        logging.info(f"Ensure PCAPdroid is installed and has been granted remote control & VPN permissions.")
        logging.info(f"Targeting app: {target_app_package}")
        logging.info("If this is the first time or permissions were reset, you MAY need to:")
        logging.info("  1. Approve 'shell'/'remote control' permission for PCAPdroid on the device.")
        logging.info("  2. Approve VPN connection request from PCAPdroid on the device.")
        logging.info("Check PCAPdroid notifications on device if capture doesn't start.")
        logging.info("="*50 + "\\n")

        stdout, retcode = self._run_adb_command_for_capture(start_command)

        if retcode != 0:
            logging.error(f"Failed to send PCAPdroid 'start' command. ADB retcode: {retcode}. Output: {stdout}")
            return False
        
        logging.info(f"PCAPdroid 'start' command sent. Capture should be initializing for {target_app_package}.")
        
        # ---- Automate clicking PCAPdroid "ALLOW" button ----
        if driver_available_for_ui: # Check if driver was available from the start of this method
            time.sleep(2) # Wait a bit for the dialog to appear
            try:
                logging.info("Checking for PCAPdroid VPN confirmation dialog to click 'ALLOW'...")
                allow_button = None
                # Try finding by uppercase text "ALLOW"
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
                            # This is a common ID for the positive button in Android dialogs
                            allow_button = self.driver.driver.find_element(AppiumBy.ID, "android:id/button1")
                        except NoSuchElementException:
                            logging.info("PCAPdroid 'ALLOW' button not found by text or common ID. Assuming already permitted or dialog not present.")

                if allow_button and allow_button.is_displayed():
                    logging.info("PCAPdroid 'ALLOW' button found. Attempting to click...")
                    allow_button.click()
                    logging.info("Clicked PCAPdroid 'ALLOW' button successfully.")
                    time.sleep(1.5) # Brief pause after click for UI to respond
                elif allow_button: # Found but not displayed
                    logging.info("PCAPdroid 'ALLOW' button was found but is not currently displayed. Proceeding...")
                else: # Not found by any means
                    logging.info("PCAPdroid 'ALLOW' button was not found. Proceeding, assuming it's not needed or already handled.")

            except Exception as e:
                logging.warning(f"An error occurred while trying to find and click the PCAPdroid 'ALLOW' button: {e}. Capture might fail if permission is required and was not granted.")
        else:
            logging.warning("Appium driver not available for PCAPdroid 'ALLOW' button interaction. Skipping.")
        # ---- End of PCAPdroid "ALLOW" button automation ----

        # Wait for capture to fully initialize after potential dialog interaction
        time.sleep(self.config_dict.get('WAIT_AFTER_ACTION', 2.0)) # Use config_dict
        return True

    def _stop_traffic_capture(self) -> bool:
        """Stops PCAPdroid traffic capture."""
        if not self.traffic_capture_enabled or not self.pcap_filename_on_device:
            logging.debug("Traffic capture was not enabled or not started by this crawler instance. Skipping stop.")
            return False

        # Ensure driver is connected for UI interactions with PCAPdroid dialogs
        # This check is a safeguard.
        driver_available_for_ui = self.driver and self.driver.driver
        if not driver_available_for_ui:
            logging.warning("Appium driver not connected at the start of _stop_traffic_capture. UI interaction for PCAPdroid dialogs will be skipped.")

        logging.info("Attempting to stop PCAPdroid traffic capture...")
        pcapdroid_activity = self.config_dict.get('PCAPDROID_ACTIVITY', 'com.emanuelef.remote_capture/.activities.CaptureCtrl') # Use config_dict
        stop_command = [
            'shell', 'am', 'start',
            '-n', pcapdroid_activity,
            '-e', 'action', 'stop'
        ]
        stdout, retcode = self._run_adb_command_for_capture(stop_command)

        if retcode != 0:
            logging.warning(f"Failed to send 'stop' command to PCAPdroid. ADB retcode: {retcode}. Output: {stdout}. Will attempt to pull file anyway.")
            # Even if stop command fails via ADB, the VPN dialog might still appear if PCAPdroid tries to stop.
            # So, we'll proceed to check for the dialog.
            # return False # Original: return False here

        logging.info("PCAPdroid 'stop' command sent. Checking for confirmation dialog...")

        # ---- Automate clicking PCAPdroid VPN disconnect confirmation ----
        if driver_available_for_ui: # Check if driver was available
            time.sleep(1.5) # Wait a bit for the dialog to appear
            try:
                logging.info("Checking for PCAPdroid VPN disconnect confirmation dialog...")
                confirm_button = None
                button_texts_to_try = ["OK", "DISCONNECT", "ALLOW", "Allow", "Ok"] # Common texts for such dialogs

                for btn_text in button_texts_to_try:
                    try:
                        logging.debug(f"Attempting to find disconnect confirmation button by text: '{btn_text}'")
                        confirm_button = self.driver.driver.find_element(AppiumBy.XPATH, f"//*[@text='{btn_text}']")
                        if confirm_button and confirm_button.is_displayed():
                            logging.info(f"Found disconnect confirmation button with text: '{btn_text}'")
                            break # Found a visible button
                        else:
                            confirm_button = None # Reset if found but not displayed
                    except NoSuchElementException:
                        logging.debug(f"Disconnect confirmation button with text '{btn_text}' not found.")
                        continue
                
                if not confirm_button:
                    logging.debug("Disconnect confirmation button not found by text. Trying by common Android ID 'android:id/button1'...")
                    try:
                        confirm_button = self.driver.driver.find_element(AppiumBy.ID, "android:id/button1") # Positive button
                        if not (confirm_button and confirm_button.is_displayed()):
                            confirm_button = None # Reset if not displayed
                    except NoSuchElementException:
                        logging.debug("Disconnect confirmation button not found by 'android:id/button1'.")
                
                if not confirm_button:
                    logging.debug("Trying by common Android ID 'android:id/button2' (sometimes used for 'Cancel' or 'OK')...")
                    try:
                        confirm_button = self.driver.driver.find_element(AppiumBy.ID, "android:id/button2") # Negative/neutral button
                        if not (confirm_button and confirm_button.is_displayed()):
                            confirm_button = None # Reset if not displayed
                    except NoSuchElementException:
                        logging.debug("Disconnect confirmation button not found by 'android:id/button2'.")


                if confirm_button and confirm_button.is_displayed():
                    logging.info(f"Disconnect confirmation button found (text: '{confirm_button.text if hasattr(confirm_button, 'text') else 'N/A'}', id: '{confirm_button.id}'). Attempting to click...")
                    confirm_button.click()
                    logging.info("Clicked PCAPdroid disconnect confirmation button successfully.")
                    time.sleep(1.0) # Brief pause after click
                elif confirm_button:
                    logging.info("Disconnect confirmation button was found but is not currently displayed. Proceeding...")
                else:
                    logging.info("PCAPdroid disconnect confirmation button was not found. Proceeding, assuming it's not needed or already handled.")

            except Exception as e:
                logging.warning(f"An error occurred while trying to find and click the PCAPdroid disconnect confirmation button: {e}. Capture stop process might be affected if confirmation was required.")
        else:
            logging.warning("Appium driver not available for PCAPdroid disconnect confirmation. Skipping UI interaction.")
        # ---- End of PCAPdroid disconnect confirmation automation ----
        
        if retcode != 0: # Now, after attempting dialog click, we can return based on original ADB command result
            logging.warning(f"Original ADB 'stop' command had failed (retcode: {retcode}). Traffic capture might not have stopped cleanly on device.")
            return False

        logging.info("PCAPdroid 'stop' sequence completed. Waiting for file finalization...")
        time.sleep(self.config_dict.get('WAIT_AFTER_ACTION', 2.0)) # Use config_dict, default 2s, was 3s
        return True

    def _pull_traffic_capture_file(self) -> bool:
        """Pulls the PCAP file from the device."""
        if not self.traffic_capture_enabled or not self.pcap_filename_on_device or not self.local_pcap_file_path:
            logging.debug("Cannot pull PCAP file: capture not enabled, filename not set, or local path not set.")
            return False

        device_pcap_dir = getattr(config, 'DEVICE_PCAP_DIR', '/sdcard/Download/PCAPdroid')
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
            
    def _cleanup_device_pcap_file(self):
        """Deletes the PCAP file from the device if configured."""
        if not self.traffic_capture_enabled or not self.pcap_filename_on_device or not self.config_dict.get('CLEANUP_DEVICE_PCAP_FILE', False): # Use config_dict
            return

        device_pcap_dir = self.config_dict.get('DEVICE_PCAP_DIR', '/sdcard/Download/PCAPdroid') # Use config_dict
        device_pcap_full_path = os.path.join(device_pcap_dir, self.pcap_filename_on_device).replace("\\\\", "/")
        logging.info(f"Cleaning up device PCAP file: {device_pcap_full_path}")
        rm_command = ['shell', 'rm', device_pcap_full_path]
        stdout, retcode = self._run_adb_command_for_capture(rm_command, suppress_stderr=True)
        if retcode == 0:
            logging.info(f"Device PCAP file '{device_pcap_full_path}' deleted successfully.")
        else:
            logging.warning(f"Failed to delete device PCAP file '{device_pcap_full_path}'. ADB retcode: {retcode}. Output: {stdout}")

    def _get_element_center(self, element: WebElement) -> Optional[Tuple[int, int]]:
        """Safely gets the center coordinates of a WebElement."""
        if not element: 
            logging.warning("Attempted to get center of a None element.")
            return None
        try:
            # Check if element is still valid before accessing properties
            if not element.is_displayed(): # is_displayed() can also raise StaleElementReferenceException
                logging.warning(f"Element (ID: {element.id if hasattr(element, 'id') else 'N/A'}) is not displayed. Cannot get center.")
                return None

            loc = element.location # Dictionary {'x': ..., 'y': ...}
            size = element.size   # Dictionary {'width': ..., 'height': ...}
            if loc and size and 'x' in loc and 'y' in loc and 'width' in size and 'height' in size:
                 center_x = loc['x'] + size['width'] // 2
                 center_y = loc['y'] + size['height'] // 2
                 return (center_x, center_y)
            else:
                 logging.warning(f"Could not get valid location/size for element: {element.id if hasattr(element,'id') else 'Unknown ID'}. Location: {loc}, Size: {size}")
                 return None
        except StaleElementReferenceException:
            logging.error(f"StaleElementReferenceException getting center for element (ID was: {element.id if hasattr(element, 'id') else 'N/A'}). Element is no longer attached to the DOM.", exc_info=True)
            return None
        except Exception as e:
            element_id_str = element.id if hasattr(element, 'id') else 'Unknown ID'
            logging.error(f"Error getting element center coordinates for element {element_id_str}: {e}", exc_info=True)
            return None

    def _find_element_by_ai_identifier(self, identifier: str) -> Optional[WebElement]:
        """
        Attempts to find a WebElement using the identifier provided by the AI,
        trying different strategies in a dynamically prioritized order.
        Promotes successful strategies and returns immediately upon finding a suitable element.
        """
        if not identifier or not self.driver or not self.driver.driver:
            logging.warning("Cannot find element: Invalid identifier or driver not available.")
            return None

        logging.info(f"Attempting to find element using identifier: '{identifier}'")
        total_start_time = time.perf_counter() # Start total timer

        # --- Iterate through strategies in current priority order ---
        for index, (strategy_key, appium_by, log_name) in enumerate(self.element_finding_strategies):
            element: Optional[WebElement] = None
            start_time = time.perf_counter() # Start timer for this strategy
            strategy_succeeded = False
            xpath_generated = "" # For logging invalid selectors

            try:
                # --- Execute find logic based on strategy_key ---
                if strategy_key in ['id', 'acc_id']:
                    logging.debug(f"Trying {log_name}: '{identifier}'")
                    element = self.driver.find_element(appium_by, identifier)

                elif strategy_key == 'xpath_exact':
                    # --- XPath Exact Text Logic (with quote handling) ---
                    if "'" in identifier and '"' in identifier:
                        parts = []
                        for i, part in enumerate(identifier.split("'")):
                            if '"' in part: parts.append(f"'{part}'")
                            elif part: parts.append(f'"{part}"')
                            if i < len(identifier.split("'")) - 1: parts.append("\"'\"")
                        xpath_text_expression = f"concat({','.join(filter(None, parts))})"
                    elif "'" in identifier: xpath_text_expression = f'"{identifier}"'
                    elif '"' in identifier: xpath_text_expression = f"'{identifier}'"
                    else: xpath_text_expression = f"'{identifier}'"
                    xpath_generated = f"//*[@text={xpath_text_expression}]"
                    # ----------------------------------------------------
                    logging.debug(f"Trying {log_name} (Quote Safe): {xpath_generated}")
                    element = self.driver.find_element(AppiumBy.XPATH, xpath_generated)

                elif strategy_key == 'xpath_contains':
                    # --- XPath Contains Logic (basic quote handling) ---
                    if "'" in identifier: xpath_safe_identifier = f'"{identifier}"'
                    else: xpath_safe_identifier = f"'{identifier}'"
                    xpath_generated = (f"//*[contains(@text, {xpath_safe_identifier}) or "
                                       f"contains(@content-desc, {xpath_safe_identifier}) or "
                                       f"contains(@resource-id, {xpath_safe_identifier})]")
                    # ---------------------------------------------------
                    logging.debug(f"Trying {log_name} (Basic Quote Handling): {xpath_generated}")
                    possible_elements = self.driver.driver.find_elements(AppiumBy.XPATH, xpath_generated)
                    found_count = len(possible_elements)
                    logging.debug(f"Found {found_count} potential elements via '{log_name}' XPath.")
                    # Filter results
                    for el in possible_elements:
                        try:
                            if el.is_displayed() and el.is_enabled():
                                element = el # Found a suitable one
                                break # Use the first suitable one
                        except Exception: continue # Ignore stale elements during check
                    if not element:
                         logging.debug(f"No suitable element found by '{log_name}' XPath after filtering.")
                # --- End of strategy-specific logic ---

                duration = time.perf_counter() - start_time # Calculate duration here after find attempt

                # --- Check if element is suitable and handle success ---
                if element and element.is_displayed() and element.is_enabled():
                    logging.info(f"Found element by {log_name}: '{identifier}' (took {duration:.4f}s)")
                    strategy_succeeded = True
                    # --- Promote the successful strategy ---
                    if index > 0: # No need to move if already first
                        promoted_strategy = self.element_finding_strategies.pop(index)
                        self.element_finding_strategies.insert(0, promoted_strategy)
                        logging.info(f"Promoted strategy '{log_name}' to the front. New order: {[s[2] for s in self.element_finding_strategies]}")
                    # --- Return immediately on success ---
                    return element
                elif element:
                    # Found but not suitable (e.g., not displayed/enabled)
                    logging.debug(f"Element found by {log_name} but not displayed/enabled (took {duration:.4f}s).")
                    # Do not promote, continue to next strategy

            except NoSuchElementException:
                duration = time.perf_counter() - start_time # Calculate duration
                logging.debug(f"Not found by {log_name} (took {duration:.4f}s).")
            except InvalidSelectorException as e:
                 duration = time.perf_counter() - start_time # Calculate duration
                 logging.warning(f"Invalid Selector Exception finding by {log_name} '{identifier}' (XPath: {xpath_generated}). Error: {e} (took {duration:.4f}s)")
            except Exception as e:
                duration = time.perf_counter() - start_time # Calculate duration
                logging.warning(f"Error finding by {log_name} '{identifier}' (took {duration:.4f}s): {e}")

            # If we reach here, the current strategy failed or found an unsuitable element.
            # Loop continues to the next strategy.

        # --- Final Result if loop completes without success ---
        total_duration = time.perf_counter() - total_start_time # Calculate total duration
        logging.warning(f"Could not find suitable element using identifier '{identifier}' with any strategy (total search time {total_duration:.4f}s). Current strategy order: {[s[2] for s in self.element_finding_strategies]}")
        return None # Return None if no strategy worked

    def _get_current_state(self) -> Optional[Tuple[bytes, str]]:
        """Gets the current screenshot bytes and page source."""
        # Add stability wait *before* getting state
        time.sleep(self.config_dict.get('STABILITY_WAIT', 1.0)) # Use config_dict # Wait for UI stability
        try:
            screenshot_bytes = self.driver.get_screenshot_bytes()
            page_source = self.driver.get_page_source()

            if screenshot_bytes is None or page_source is None:
                logging.error("Failed to get current screen state (screenshot or XML is None).")
                return None
            return screenshot_bytes, page_source
        except Exception as e:
            logging.error(f"Exception getting current state: {e}", exc_info=True)
            return None

    def _map_ai_to_action(self, ai_suggestion: dict) -> Optional[Tuple[str, Optional[Any], Optional[str]]]:
        """
        Maps the AI's JSON suggestion (using 'target_identifier') to an executable action tuple.
        Returns: (action_type, target_object_or_info, input_text_or_none)
                 where target_object_or_info is WebElement for click/input, or string for scroll.
        """
        action = ai_suggestion.get("action")
        target_identifier = ai_suggestion.get("target_identifier")
        input_text = ai_suggestion.get("input_text") # Needed for input action

        logging.info(f"Attempting to map AI suggestion: Action='{action}', Identifier='{target_identifier}', Input='{input_text}'")

        # --- Actions requiring element finding ---
        if action in ["click", "input"]:
            if not target_identifier:
                logging.error(f"AI suggestion for '{action}' requires 'target_identifier', but it's missing. Cannot map.")
                return None # Mapping fails if no identifier

            # Use the new helper method to find the element
            target_element = self._find_element_by_ai_identifier(target_identifier)

            if target_element:
                 logging.info(f"Successfully mapped AI identifier '{target_identifier}' to initial WebElement.")

                 # --- Refactored validation for INPUT actions ---
                 if action == "input":
                     original_element = target_element # Keep track of the originally found element
                     is_editable = False
                     element_class = None # Initialize element_class
                     final_target_element = original_element # Start with the original element

                     try:
                         # --- Get class of the initially found element ---
                         element_class = original_element.get_attribute('class')
                         logging.debug(f"Initial element found for INPUT: ID='{original_element.id}', Class='{element_class}', Identifier='{target_identifier}'")

                         # --- Check if the initially found element is directly editable ---
                         editable_classes = ['edittext', 'textfield', 'input', 'autocomplete', 'searchview'] # Added searchview
                         if element_class and any(editable_tag in element_class.lower() for editable_tag in editable_classes):
                             is_editable = True
                             logging.info(f"Initial element (Class: {element_class}) is directly editable. Using it for INPUT.")
                         else:
                             # --- If not directly editable, search upwards for an editable ancestor (up to 3 levels) ---
                             logging.info(f"Initial element (Class: {element_class}) is NOT directly editable. Searching upwards for an editable ancestor...")
                             current_ancestor = original_element
                             max_levels_to_check = 3
                             for level in range(1, max_levels_to_check + 1):
                                 try:
                                     # Use XPath to select the parent node
                                     parent_element = current_ancestor.find_element(AppiumBy.XPATH, "..") # Or use "parent::*"
                                     if parent_element:
                                         parent_class = parent_element.get_attribute('class')
                                         logging.debug(f"Checking ancestor level {level}: ID='{parent_element.id}', Class='{parent_class}'")

                                         # --- Check if this ancestor is editable ---
                                         if parent_class and any(editable_tag in parent_class.lower() for editable_tag in editable_classes):
                                             logging.info(f"Found editable ancestor at level {level} (Class: {parent_class}). Switching target for INPUT action.")
                                             final_target_element = parent_element # Use the editable ancestor
                                             is_editable = True
                                             break # Found a suitable ancestor, stop searching upwards
                                         else:
                                             # Ancestor not editable, move up to the next level
                                             current_ancestor = parent_element
                                     else:
                                         # Could not get class attribute, stop searching this branch
                                         logging.debug(f"Could not retrieve class attribute from ancestor at level {level}. Stopping upward search.")
                                         break
                                 except NoSuchElementException:
                                     logging.debug(f"No more parent elements found at level {level}. Stopping upward search.")
                                     break # Reached the top or an element without a parent in the hierarchy
                                 except Exception as parent_err:
                                     logging.error(f"Error finding or checking ancestor element at level {level}: {parent_err}", exc_info=True)
                                     break # Stop searching on error
                             # --- End ancestor search loop ---

                             if not is_editable:
                                 logging.warning(f"No editable ancestor found within {max_levels_to_check} levels for initial element (Class: {element_class}). Cannot perform INPUT.")

                         # --- Final check: If no suitable element was found (neither original nor ancestor) ---
                         if not is_editable:
                             logging.error(f"AI suggested INPUT for identifier '{target_identifier}', but neither the initially found element (Class: {element_class}) nor its ancestors (up to {max_levels_to_check} levels) were suitable/editable. Mapping failed.")
                             self.consecutive_map_failures += 1
                             return None # Mapping fails

                     except Exception as e:
                         # Catch errors getting attributes or during the checks
                         logging.error(f"Error during element class validation/ancestor check for INPUT action (Identifier: '{target_identifier}'): {e}", exc_info=True)
                         self.consecutive_map_failures += 1
                         return None # Mapping fails due to unexpected error

                     # --- If we passed validation, return the action with the potentially updated target element ---
                     logging.info(f"Mapping successful for INPUT. Using element ID: {final_target_element.id}")
                     return (action, final_target_element, input_text)
                 # --- End refactored validation ---

                 # --- If action was 'click', return the originally found element ---
                 logging.info(f"Mapping successful for CLICK. Using element ID: {target_element.id}")
                 return (action, target_element, None) # Input text is None for click

            else:
                 logging.error(f"Failed to find element using AI identifier: '{target_identifier}'. Cannot map action '{action}'.")
                 self.consecutive_map_failures += 1 # Count as a mapping failure
                 return None # Mapping fails

        # --- Actions NOT requiring element finding ---
        elif action == "scroll_down":
             return ("scroll", "down", None)
        elif action == "scroll_up":
             return ("scroll", "up", None)
        elif action == "back":
             return ("back", None, None)
        else:
            logging.error(f"Unknown action type from AI: {action}")
            return None


    def _save_annotated_screenshot(self,
                                   original_screenshot_bytes: bytes,
                                   step: int,
                                   screen_id: int,
                                   ai_suggestion: Optional[Dict[str, Any]]):
        """
        Takes the original screenshot, draws indicator based on AI's bbox center,
        and saves it WITH absolute bbox coordinates in the filename.

        Args:
            original_screenshot_bytes: The raw PNG bytes of the screen.
            step: The current crawl step number.
            screen_id: The database ID of the current screen state.
            ai_suggestion: The dictionary returned by the AI assistant, which
                           may contain 'target_bounding_box'.
        """
        if not original_screenshot_bytes:
            logging.debug("Skipping annotated screenshot: No original image provided.")
            return
        if not ai_suggestion:
            logging.debug("Skipping annotated screenshot: No AI suggestion provided.")
            return

        # --- Get Normalized BBOX from AI Suggestion ---
        bbox_data = ai_suggestion.get("target_bounding_box")
        action_type = ai_suggestion.get("action", "unknown") # Get action type for context

        if not bbox_data:
            logging.debug(f"Skipping annotated screenshot: AI suggestion for action '{action_type}' has no 'target_bounding_box'.")
            return # Nothing to annotate if no target bbox specified by AI

        logging.debug(f"Attempting annotation using AI bbox: {bbox_data}")

        try:
            # --- Extract Normalized Coords ---
            tl_x_norm, tl_y_norm = bbox_data["top_left"]
            br_x_norm, br_y_norm = bbox_data["bottom_right"]

            # --- Validate Normalized Coords ---
            if not all(isinstance(coord, (int, float)) and 0.0 <= coord <= 1.0 for coord in [tl_x_norm, tl_y_norm, br_x_norm, br_y_norm]):
                 raise ValueError(f"Normalized coordinates invalid or out of range [0.0, 1.0]: {bbox_data}")

            # --- Get Image Dimensions to Convert Coords ---
            # Option 1: Use Appium window size (faster if available and reliable)
            window_size = self.driver.get_window_size()
            if window_size and window_size.get('width') > 0 and window_size.get('height') > 0:
                 img_width = window_size['width']
                 img_height = window_size['height']
                 logging.debug(f"Using Appium window size for coord conversion: {img_width}x{img_height}")
            else:
                 # Option 2: Load image from bytes to get dimensions (fallback)
                 logging.debug("Appium window size unavailable or invalid, loading image from bytes to get dimensions.")
                 try:
                     with Image.open(BytesIO(original_screenshot_bytes)) as img:
                         img_width, img_height = img.size
                     if img_width <= 0 or img_height <= 0:
                          raise ValueError("Image dimensions from bytes are invalid.")
                     logging.debug(f"Using image dimensions from bytes: {img_width}x{img_height}")
                 except Exception as img_err:
                     logging.error(f"Failed to get image dimensions from bytes: {img_err}. Cannot proceed with annotation.")
                     return # Cannot convert coords without dimensions

            # --- Convert to Absolute Pixel Coords ---
            x1 = int(tl_x_norm * img_width)
            y1 = int(tl_y_norm * img_height)
            x2 = int(br_x_norm * img_width)
            y2 = int(br_y_norm * img_height)

            # Ensure correct order (x1<=x2, y1<=y2)
            if x1 > x2: x1, x2 = x2, x1
            if y1 > y2: y1, y2 = y2, y1

            # Clip coordinates to be strictly within image bounds
            x1 = max(0, min(x1, img_width - 1))
            y1 = max(0, min(y1, img_height - 1))
            x2 = max(0, min(x2, img_width - 1))
            y2 = max(0, min(y2, img_height - 1))

            # Basic check: if coords collapsed, maybe skip?
            if x1 >= x2 or y1 >= y2:
                logging.warning(f"Bounding box collapsed after conversion/clipping ({x1},{y1},{x2},{y2}). Skipping annotation.")
                return

            # --- Prepare Filename and Log Info ---
            filename_suffix = f"_bbox_{x1}_{y1}_{x2}_{y2}.png"
            target_log_info = f"bbox=({x1},{y1},{x2},{y2})" # Absolute coords

            # --- Calculate Center Point for Drawing ---
            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)
            draw_coords = (center_x, center_y) # Absolute coords

        except (KeyError, IndexError, TypeError, ValueError) as e:
            logging.error(f"Error processing AI bounding box {bbox_data}: {e}. Skipping annotation saving.")
            return
        except Exception as e: # Catch unexpected errors during coord processing
             logging.error(f"Unexpected error processing coordinates/dimensions: {e}", exc_info=True)
             return

        # --- Draw the Indicator (using the calculated absolute center point) ---
        annotated_bytes = None # Initialize
        try:
            logging.debug(f"Drawing indicator at center: {draw_coords}")
            # Assume utils.draw_indicator_on_image takes absolute coords
            annotated_bytes = utils.draw_indicator_on_image(
                original_screenshot_bytes,
                draw_coords # Pass calculated absolute center coordinates
            )
            if not annotated_bytes:
                 raise ValueError("draw_indicator_on_image returned None")

        except Exception as draw_err:
             logging.error(f"Error drawing indicator on image: {draw_err}", exc_info=True)
             # annotated_bytes remains None if drawing fails

        # --- Save the File ---
        if annotated_bytes:
            try:
                # Ensure config has the directory defined
                if not hasattr(config, 'ANNOTATED_SCREENSHOTS_DIR') or not config.ANNOTATED_SCREENSHOTS_DIR:
                    logging.error("Configuration error: 'ANNOTATED_SCREENSHOTS_DIR' not defined or empty in config.")
                    return # Cannot save without a directory path

                annotated_dir = config.ANNOTATED_SCREENSHOTS_DIR
                os.makedirs(annotated_dir, exist_ok=True) # Ensure directory exists

                # Construct filename with absolute bbox coordinates
                filename = f"annotated_step_{step}_screen_{screen_id}{filename_suffix}"
                filepath = os.path.join(annotated_dir, filename)

                # Write the annotated image bytes
                with open(filepath, "wb") as f:
                    f.write(annotated_bytes)

                logging.info(f"Saved annotated screenshot: {filepath} ({target_log_info})")

            except IOError as io_err:
                 logging.error(f"Failed to save annotated screenshot to {filepath}: {io_err}", exc_info=True)
            except Exception as e:
                 # Catch any other saving errors
                 filepath_str = filepath if 'filepath' in locals() else f"in {annotated_dir}"
                 logging.error(f"Unexpected error saving annotated screenshot {filepath_str}: {e}", exc_info=True)
        else:
            # This case occurs if drawing failed
            logging.warning("Skipping saving annotated screenshot because indicator drawing failed.")


    def _execute_action(self, mapped_action: Tuple[str, Optional[Any], Optional[str]]) -> bool:
        """Executes the mapped Appium action using WebElement targets for click/input."""
        action_type, target, input_text = mapped_action # Unpack all three
        success = False

        # Log target differently based on type
        if isinstance(target, WebElement):
             try:
                 target_log_info = f"Element (ID: {target.id})"
             except:
                 target_log_info = "Element (Stale?)"
        elif isinstance(target, str): # Scroll direction
             target_log_info = f"Direction: {target}"
        else: # Back action or others
             target_log_info = ""

        logging.info(f"Executing: {action_type.upper()} {target_log_info}")

        # --- Handle actions based on WebElement or specific info ---
        if action_type == "click" and isinstance(target, WebElement):
             success = self.driver.click_element(target)

        elif action_type == "input" and isinstance(target, WebElement) and isinstance(input_text, str):
             # Use the robust input method which includes clicking first
             success = self.driver.input_text_into_element(target, input_text)

        elif action_type == "scroll" and isinstance(target, str):
            # Target holds direction string "up" or "down"
            success = self.driver.scroll(direction=target)

        elif action_type == "back" and target is None:
            success = self.driver.press_back_button()

        # Removed tap_coords and input_by_keys as they are replaced
        else:
            logging.error(f"Cannot execute unknown/invalid mapped action type or target combination: {action_type} with target: {target_log_info} (Type: {type(target)})")


        # --- Update failure counter ---
        if success:
             self.consecutive_exec_failures = 0
             logging.info(f"Action {action_type.upper()} successful.")
        else:
             self.consecutive_exec_failures += 1
             logging.warning(f"Action {action_type.upper()} execution failed ({self.consecutive_exec_failures} consecutive).")
        return success





    def _ensure_in_app(self) -> bool:
        """Checks if the driver is focused on the target app or allowed external apps."""
        if not self.driver.driver: # Check if driver session is active
            logging.error("Driver not connected, cannot ensure app context.")
            return False

        context = self.driver.get_current_app_context()
        if not context:
            logging.error("Could not get current app context. Attempting relaunch as fallback.")
            self.driver.relaunch_app() # Try to recover
            time.sleep(2)
            context = self.driver.get_current_app_context() # Check again
            if not context:
                logging.critical("Failed to get app context even after relaunch attempt.")
                return False # Serious issue

        current_package, current_activity = context
        target_package = self.config_dict['APP_PACKAGE']
        allowed_packages = [target_package] + config.ALLOWED_EXTERNAL_PACKAGES

        logging.debug(f"Current app context: {current_package} / {current_activity}")

        if current_package in allowed_packages:
            logging.debug(f"App context OK (In {current_package}).")
            return True
        else:
            logging.warning(f"App context incorrect: In '{current_package}', expected one of {allowed_packages}. Attempting recovery.")
            # Try pressing back first
            self.driver.press_back_button()
            time.sleep(config.WAIT_AFTER_ACTION / 2) # Shorter wait after back

            # Check again
            context = self.driver.get_current_app_context()
            if context and context[0] in allowed_packages:
                logging.info("Recovery successful: Returned to target/allowed package after back press.")
                return True
            else:
                # Relaunch if back didn't work
                logging.warning("Recovery failed after back press. Relaunching target application.")
                self.driver.relaunch_app()
                time.sleep(config.WAIT_AFTER_ACTION) # Wait after relaunch
                # Check one last time
                context = self.driver.get_current_app_context()
                if context and context[0] in allowed_packages:
                    logging.info("Recovery successful: Relaunched target application.")
                    return True
                else:
                    current_pkg_after_relaunch = context[0] if context else "Unknown"
                    logging.error(f"Recovery failed: Could not return to target/allowed application. Still in '{current_pkg_after_relaunch}'.")
                    return False # Indicate failure to recover


    def _check_termination(self) -> bool:
        """Checks if crawling should terminate based on failure conditions."""
        # Removed step count check - handled in run() loop based on CRAWL_MODE
        if self.consecutive_ai_failures >= config.MAX_CONSECUTIVE_AI_FAILURES:
            logging.error(f"Termination: Exceeded max consecutive AI failures ({config.MAX_CONSECUTIVE_AI_FAILURES}).")
            return True
        if self.consecutive_map_failures >= config.MAX_CONSECUTIVE_MAP_FAILURES:
            logging.error(f"Termination: Exceeded max consecutive mapping failures ({config.MAX_CONSECUTIVE_MAP_FAILURES}).")
            return True
        if self.consecutive_exec_failures >= config.MAX_CONSECUTIVE_EXEC_FAILURES:
            logging.error(f"Termination: Exceeded max consecutive execution failures ({config.MAX_CONSECUTIVE_EXEC_FAILURES}).")
            return True
        # TODO: Add state repetition check using state_manager.visited_screen_hashes
        return False

    
    def run(self):
        """Main crawling loop."""
        logging.info("Starting crawler run...")
        print(f"{UI_STATUS_PREFIX} INITIALIZING") # UI Update

        try:
            # Connect to Appium FIRST to make self.driver.driver available
            self.driver.connect()
            logging.info("Appium driver connected successfully before traffic capture initiation.")

            # --- Start Traffic Capture (if enabled) ---
            if self.traffic_capture_enabled:
                if not self._start_traffic_capture(): # Now self.driver.driver should be available
                    logging.warning("Failed to start traffic capture. Continuing without it.")
                    # Optionally, decide if this is a critical failure
                else:
                    logging.info("Traffic capture started successfully.")
            # --- End Start Traffic Capture ---


            # --- Ensure Target App is Launched ---
            target_pkg = self.config_dict.get("PACKAGE") # Changed key from "app_package_name"
            target_activity = self.config_dict.get("ACTIVITY") # Changed key from "app_activity_name"

            if not target_pkg:
                logging.critical("Target app package name (PACKAGE) not found in configuration. Stopping.") # Updated log message
                print(f"{UI_END_PREFIX} CRITICAL_ERROR_NO_PACKAGE")
                return

            current_pkg = self.driver.get_current_package()
            current_activity = self.driver.get_current_activity()

            if current_pkg != target_pkg:
                logging.info(f"Target app {target_pkg} is not active (current: {current_pkg}). Attempting to launch.")
                self.driver.launch_app(target_pkg, target_activity)
                # Wait a bit for the app to launch and stabilize
                time.sleep(config.APP_LAUNCH_WAIT_TIME if hasattr(config, 'APP_LAUNCH_WAIT_TIME') else 5) 
                
                # Verify again
                current_pkg = self.driver.get_current_package()
                current_activity = self.driver.get_current_activity()
                if current_pkg != target_pkg:
                    logging.error(f"Failed to launch target app {target_pkg}. Current app is still {current_pkg}. Stopping.")
                    print(f"{UI_END_PREFIX} FAILURE_APP_LAUNCH")
                    # Attempt to stop traffic capture before exiting
                    if self.traffic_capture_enabled: # Removed self.pcap_process_pid check
                        self._stop_traffic_capture()
                    return 
                logging.info(f"Successfully launched target app: {target_pkg}/{current_activity}")
            else:
                logging.info(f"Target app {target_pkg} is already active.")
            # --- End Ensure Target App is Launched ---

            # Corrected: Removed self.config_dict from CrawlingState constructor call
            self.state_manager = CrawlingState(self.db_manager)
            
            # --- Load or Initialize Run ---
            if config.CONTINUE_EXISTING_RUN:
                logging.info("Attempting to continue existing run...")
                # When continuing, we assume the app state is where we left off, or will be handled by existing logic.
                # No explicit re-launch here, but ensure state_manager loads correctly.
                if not self.state_manager.load_from_db():
                    logging.warning("Failed to load existing run, starting fresh. Will use current foreground app state.")
                    # If load fails, initialize with whatever is current, which should be target app due to above check
                    self.state_manager.initialize_run(self.driver.get_current_activity(), self.driver.get_current_package())
                else:
                    logging.info(f"Successfully loaded run. Current step: {self.state_manager.current_step_number}")
                    # Optional: Add a check here if the loaded state's package matches target_pkg
                    if self.state_manager.app_package != target_pkg:
                        logging.warning(f"Loaded run's package ({self.state_manager.app_package}) does not match target ({target_pkg}). This might lead to issues.")

            else: # Starting a fresh run
                logging.info("Starting a fresh run (CONTINUE_EXISTING_RUN is False).")
                self.db_manager.initialize_db() # Clear and init DB for a fresh run
                # Initialize with the (now confirmed) target app's activity and package
                self.state_manager.initialize_run(self.driver.get_current_activity(), self.driver.get_current_package())
            # ---
            logging.info(f"Crawler initialized. Starting activity: {self.state_manager.start_activity}, App package: {self.state_manager.app_package}")
            print(f"{UI_STATUS_PREFIX} RUNNING") # UI Update

            start_time = time.time()
            steps_taken = 0

            while True:
                # --- Crawl Limit Checks ---
                if config.CRAWL_MODE == 'steps' and steps_taken >= config.MAX_CRAWL_STEPS:
                    logging.info(f"Reached max steps ({config.MAX_CRAWL_STEPS}). Stopping crawl.")
                    print(f"{UI_STATUS_PREFIX} MAX_STEPS_REACHED") # UI Update
                    break
                elif config.CRAWL_MODE == 'time':
                    elapsed_time = time.time() - start_time
                    if elapsed_time >= config.MAX_CRAWL_DURATION_SECONDS:
                        logging.info(f"Reached max duration ({config.MAX_CRAWL_DURATION_SECONDS}s). Stopping crawl.")
                        print(f"{UI_STATUS_PREFIX} MAX_DURATION_REACHED") # UI Update
                        break
                # ---

                logging.info(f"\\n--- Step {self.state_manager.current_step_number} ---")
                current_state_tuple = self._get_current_state()
                if not current_state_tuple:
                    logging.error("Failed to get current screen state. Cannot continue step.")
                    # Potentially increment a failure counter or attempt recovery
                    self.consecutive_exec_failures += 1
                    if self.consecutive_exec_failures >= config.MAX_CONSECUTIVE_EXEC_FAILURES:
                        logging.critical("Max consecutive execution failures reached. Stopping crawl.")
                        print(f"{UI_END_PREFIX} FAILURE_MAX_EXEC_FAIL") # UI Update
                        break
                    time.sleep(config.WAIT_AFTER_ACTION) # Wait before retrying or next step
                    continue # Skip to next iteration, hoping state recovers
                screenshot_bytes, page_source = current_state_tuple
                current_activity = self.driver.get_current_activity()
                current_package = self.driver.get_current_package()

                # --- Check if outside allowed packages ---
                if current_package != self.state_manager.app_package and current_package not in config.ALLOWED_EXTERNAL_PACKAGES:
                    logging.warning(f"Outside target app ({current_package}) and not in allowed external packages. Attempting to go back.")
                    self.driver.perform_action("back", None)
                    self._last_action_description = "BACK (auto due to off-app)"
                    self.state_manager.increment_step(self._last_action_description, "auto_back_off_app", None, None, None, None, None, None)
                    steps_taken += 1
                    time.sleep(config.WAIT_AFTER_ACTION)
                    continue
                # ---

                # --- Calculate Hashes ---
                xml_hash = utils.calculate_xml_hash(page_source) if page_source else "no_xml_hash"
                visual_hash = utils.calculate_visual_hash(screenshot_bytes) if screenshot_bytes else "no_visual_hash"

                # --- Add/Get Screen Representation ---
                screen_rep, is_new_screen = self.state_manager.add_or_get_screen_representation(
                    xml_hash, visual_hash, screenshot_bytes
                )
                if not screen_rep:
                    logging.error("Could not get or create screen representation. Critical error.")
                    print(f"{UI_END_PREFIX} FAILURE_SCREEN_REP") # UI Update
                    break
                # --- UI Update for Step and Screenshot ---
                print(f"{UI_STEP_PREFIX} {self.state_manager.current_step_number}")
                if screen_rep.annotated_screenshot_path:
                    print(f"{UI_SCREENSHOT_PREFIX} {os.path.abspath(screen_rep.annotated_screenshot_path)}")
                # ---

                # --- AI Interaction ---
                logging.info(f"Getting AI suggestion for screen: {screen_rep.id} (Composite Hash: {screen_rep.get_composite_hash()})")
                # Prepare XML snippet if enabled
                xml_snippet = None
                if getattr(config, 'ENABLE_XML_CONTEXT', False) and page_source:
                    max_len = getattr(config, 'XML_SNIPPET_MAX_LEN', 30000)
                    xml_snippet = utils.simplify_xml_for_ai(page_source, max_len=max_len) 
                
                current_screen_hash = screen_rep.get_composite_hash() # Get hash for use below
                
                history_for_screen = self.state_manager.get_action_history(current_screen_hash) # Correct method & arg
                max_prompt_history = getattr(config, 'MAX_CHAT_HISTORY', 10) # Length for prompt history
                previous_actions_for_prompt = history_for_screen[-max_prompt_history:]
                
                current_visit_count = self.state_manager.get_visit_count(current_screen_hash) # Correct way to get visit count

                # Use the new method in AIAssistant that handles model selection
                ai_suggestion_json = self.ai_assistant.get_next_action(
                    screenshot_bytes=screenshot_bytes, 
                    xml_context=xml_snippet,
                    previous_actions=previous_actions_for_prompt, # Use the prepared list
                    available_actions=config.AVAILABLE_ACTIONS,                    
                    current_screen_visit_count=current_visit_count, # Use correct visit count
                    current_composite_hash=current_screen_hash # Use the hash variable
                )

                if not ai_suggestion_json:
                    logging.error("AI failed to provide a suggestion.")
                    self.consecutive_ai_failures += 1
                    if self.consecutive_ai_failures >= config.MAX_CONSECUTIVE_AI_FAILURES:
                        logging.critical("Max consecutive AI failures reached. Stopping crawl.")
                        print(f"{UI_END_PREFIX} FAILURE_MAX_AI_FAIL") # UI Update
                        break
                    # Simple fallback: try to go back or pick a default action
                    self.driver.perform_action("back", None)
                    self._last_action_description = "BACK (AI failure fallback)"
                    self.state_manager.increment_step(self._last_action_description, "auto_back_ai_fail", None, None, None, None, None, None)
                    steps_taken += 1
                    continue
                self.consecutive_ai_failures = 0 # Reset on success
                logging.info(f"AI Suggestion: {ai_suggestion_json}")

                # --- Map AI suggestion to executable action ---
                mapped_action = self._map_ai_to_action(ai_suggestion_json)
                if not mapped_action:
                    logging.error("Failed to map AI suggestion to an executable action.")
                    self.consecutive_map_failures += 1
                    if self.consecutive_map_failures >= config.MAX_CONSECUTIVE_MAP_FAILURES:
                        logging.critical("Max consecutive mapping failures reached. Stopping crawl.")
                        print(f"{UI_END_PREFIX} FAILURE_MAX_MAP_FAIL") # UI Update
                        break
                    # Fallback for mapping failure
                    self.driver.perform_action("back", None)
                    self._last_action_description = "BACK (mapping failure fallback)"
                    self.state_manager.increment_step(self._last_action_description, "auto_back_map_fail", None, None, None, None, None, None)
                    steps_taken += 1
                    continue
                self.consecutive_map_failures = 0 # Reset on success

                action_type_sugg, target_obj_sugg, input_text_sugg = mapped_action
                # --- UI Update for Action ---
                action_desc_for_ui = f"{action_type_sugg}"
                if isinstance(target_obj_sugg, WebElement):
                    try: # Safely get text or content-desc for UI
                        el_text = target_obj_sugg.text
                        el_cd = target_obj_sugg.get_attribute('content-desc')
                        el_id = target_obj_sugg.id
                        ui_target_id = el_text if el_text else el_cd if el_cd else el_id if el_id else "element"
                        action_desc_for_ui += f" on '{ui_target_id}'"
                    except Exception:
                        action_desc_for_ui += " on [element]"
                elif isinstance(target_obj_sugg, str): # For scroll actions
                    action_desc_for_ui += f" {target_obj_sugg}"
                if input_text_sugg:
                    action_desc_for_ui += f" with text '{input_text_sugg}'"
                print(f"{UI_ACTION_PREFIX} {action_desc_for_ui}")
                # ---

                # --- Get element details *before* action for logging/DB ---
                # This needs to happen before perform_action, as the element might become stale.
                _last_action_description_for_db = utils.generate_action_description(
                    action_type_sugg, target_obj_sugg, input_text_sugg, ai_suggestion_json.get("target_identifier")
                )
                element_center_for_db = self._get_element_center(target_obj_sugg) if isinstance(target_obj_sugg, WebElement) else None
                center_x_for_db, center_y_for_db = element_center_for_db if element_center_for_db else (None, None)
                target_element_id_for_db = None
                if isinstance(target_obj_sugg, WebElement):
                    try:
                        target_element_id_for_db = target_obj_sugg.id
                    except StaleElementReferenceException:
                        logging.warning("Element became stale even before trying to get its ID for DB logging (pre-action).")
                        # target_element_id_for_db remains None
                # --- End pre-action detail gathering ---

                # --- Execute Action ---
                logging.info(f"Executing action: {action_type_sugg}, Target: {target_obj_sugg}, Input: {input_text_sugg}")
                action_successful = self.driver.perform_action(action_type_sugg, target_obj_sugg, input_text_sugg)

                if not action_successful:
                    logging.error(f"Failed to execute action: {action_type_sugg}")
                    self.consecutive_exec_failures += 1
                    if self.consecutive_exec_failures >= config.MAX_CONSECUTIVE_EXEC_FAILURES:
                        logging.critical("Max consecutive execution failures reached. Stopping crawl.")
                        print(f"{UI_END_PREFIX} FAILURE_MAX_EXEC_FAIL") # UI Update
                        break
                    # Fallback for execution failure
                    if current_package == self.state_manager.app_package or current_package in config.ALLOWED_EXTERNAL_PACKAGES:
                        self.driver.perform_action("back", None)
                        self._last_action_description = "BACK (execution failure fallback)" # For overall tracking
                        # Log this specific fallback step
                        self.state_manager.increment_step(
                            action_description=self._last_action_description,
                            action_type="auto_back_exec_fail", 
                            target_identifier=None, target_element_id=None, 
                            target_center_x=None, target_center_y=None, 
                            input_text=None, ai_raw_output=None
                        )
                    else: 
                        self._last_action_description = "NO_ACTION (execution failure, already off-app)"
                        self.state_manager.increment_step(
                            action_description=self._last_action_description,
                            action_type="no_action_exec_fail_off_app",
                            target_identifier=None, target_element_id=None,
                            target_center_x=None, target_center_y=None,
                            input_text=None, ai_raw_output=None
                        )
                    steps_taken +=1 
                    continue 
                self.consecutive_exec_failures = 0 # Reset on success
                
                # If action was successful, use the pre-action gathered details for DB
                self._last_action_description = _last_action_description_for_db 

                self.state_manager.increment_step(
                    action_description=self._last_action_description, # Use the description generated before action
                    action_type=action_type_sugg,
                    target_identifier=ai_suggestion_json.get("target_identifier"),
                    target_element_id=target_element_id_for_db, 
                    target_center_x=center_x_for_db, 
                    target_center_y=center_y_for_db, 
                    input_text=input_text_sugg,
                    ai_raw_output=str(ai_suggestion_json) 
                )
                # ---

                steps_taken += 1
                time.sleep(config.WAIT_AFTER_ACTION) # Wait for UI to settle

            # --- End of main loop ---
            logging.info("Crawling loop finished.")
            print(f"{UI_END_PREFIX} SUCCESS") # UI Update

        except Exception as e:
            logging.critical(f"An unhandled exception occurred during crawling: {e}", exc_info=True)
            print(f"{UI_END_PREFIX} FAILURE_UNHANDLED_EXCEPTION: {str(e)}") # UI Update
        finally:
            logging.info("Performing cleanup...")
            # --- Stop and Pull Traffic Capture File (if enabled and started) ---
            if self.traffic_capture_enabled and self.pcap_filename_on_device:
                if self._stop_traffic_capture():
                    logging.info("Traffic capture stopped.")
                    if self._pull_traffic_capture_file():
                        logging.info("Traffic capture file pulled.")
                        if getattr(config, 'CLEANUP_DEVICE_PCAP_FILE', False):
                            self._cleanup_device_pcap_file()
                    else:
                        logging.error("Failed to pull traffic capture file.")
                else:
                    logging.warning("Failed to stop traffic capture cleanly. May attempt to pull anyway.")
                    # Attempt pull even if stop failed, as file might exist
                    if self._pull_traffic_capture_file():
                        logging.info("Traffic capture file pulled (after stop command issue).")
                        if getattr(config, 'CLEANUP_DEVICE_PCAP_FILE', False):
                            self._cleanup_device_pcap_file()
                    else:
                        logging.error("Failed to pull traffic capture file (after stop command issue).")
            # --- End Stop and Pull Traffic Capture ---
            self.driver.disconnect()
            self.db_manager.close()
            logging.info("Crawler run finished and cleaned up.")