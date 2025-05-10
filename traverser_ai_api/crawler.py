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
from selenium.common.exceptions import NoSuchElementException, InvalidSelectorException # Added InvalidSelectorException

# --- Import for traffic capture ---
import subprocess
import sys
# --- End import for traffic capture ---

class AppCrawler:
    """Orchestrates the AI-driven app crawling process."""

    def __init__(self):
        self.config_dict = {k: getattr(config, k) for k in dir(config) if not k.startswith('_')}
        self.driver = AppiumDriver(config.APPIUM_SERVER_URL, self.config_dict)
        # Update AI Assistant initialization to use default model type
        self.ai_assistant = AIAssistant(
            api_key=config.GEMINI_API_KEY,
            model_name=getattr(config, 'DEFAULT_MODEL_TYPE', 'pro-vision'),
            safety_settings=config.AI_SAFETY_SETTINGS
        )
        self.db_manager = DatabaseManager(config.DB_NAME)
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

        target_app_package = self.config_dict.get('APP_PACKAGE')
        if not target_app_package:
            logging.error("TARGET_APP_PACKAGE not configured. Cannot start traffic capture.")
            return False

        # Sanitize package name for filename
        sanitized_package = re.sub(r'[^\w\-.]+', '_', target_app_package)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.pcap_filename_on_device = f"{sanitized_package}_{timestamp}.pcap"
        
        # Use config attributes for paths
        device_pcap_dir = getattr(config, 'DEVICE_PCAP_DIR', '/sdcard/Download/PCAPdroid')
        traffic_capture_output_dir = getattr(config, 'TRAFFIC_CAPTURE_OUTPUT_DIR', 'traffic_captures')

        device_pcap_full_path = os.path.join(device_pcap_dir, self.pcap_filename_on_device).replace("\\", "/")

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
        
        # ---- Automate clicking PCAPdroid "ALLOW" button ----
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
        # ---- End of PCAPdroid "ALLOW" button automation ----

        # Wait for capture to fully initialize after potential dialog interaction
        # The original wait was: time.sleep(getattr(config, 'WAIT_AFTER_ACTION', 2.0) * 2)
        # We've already waited ~2s for dialog + 1.5s after click.
        # Let's use the configured wait time here.
        time.sleep(getattr(config, 'WAIT_AFTER_ACTION', 2.0)) 
        return True

    def _stop_traffic_capture(self) -> bool:
        """Stops PCAPdroid traffic capture."""
        if not self.traffic_capture_enabled or not self.pcap_filename_on_device:
            logging.debug("Traffic capture was not enabled or not started by this crawler instance. Skipping stop.")
            return False

        logging.info("Attempting to stop PCAPdroid traffic capture...")
        pcapdroid_activity = getattr(config, 'PCAPDROID_ACTIVITY', 'com.emanuelef.remote_capture/.activities.CaptureCtrl')
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
        # This dialog might say "OK", "Disconnect", "Allow" depending on Android version/PCAPdroid version
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
        # ---- End of PCAPdroid disconnect confirmation automation ----
        
        if retcode != 0: # Now, after attempting dialog click, we can return based on original ADB command result
            logging.warning(f"Original ADB 'stop' command had failed (retcode: {retcode}). Traffic capture might not have stopped cleanly on device.")
            return False

        logging.info("PCAPdroid 'stop' sequence completed. Waiting for file finalization...")
        time.sleep(getattr(config, 'WAIT_AFTER_ACTION', 2.0)) # Use configured wait, default 2s, was 3s
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
        if not self.traffic_capture_enabled or not self.pcap_filename_on_device or not getattr(config, 'CLEANUP_DEVICE_PCAP_FILE', False):
            return

        device_pcap_dir = getattr(config, 'DEVICE_PCAP_DIR', '/sdcard/Download/PCAPdroid')
        device_pcap_full_path = os.path.join(device_pcap_dir, self.pcap_filename_on_device).replace("\\", "/")
        logging.info(f"Cleaning up device PCAP file: {device_pcap_full_path}")
        rm_command = ['shell', 'rm', device_pcap_full_path]
        stdout, retcode = self._run_adb_command_for_capture(rm_command, suppress_stderr=True)
        if retcode == 0:
            logging.info(f"Device PCAP file '{device_pcap_full_path}' deleted successfully.")
        else:
            logging.warning(f"Failed to delete device PCAP file '{device_pcap_full_path}'. ADB retcode: {retcode}. Output: {stdout}")

    def _get_element_center(self, element: WebElement) -> Optional[Tuple[int, int]]:
        """Safely gets the center coordinates of a WebElement."""
        if not element: return None
        try:
            loc = element.location # Dictionary {'x': ..., 'y': ...}
            size = element.size   # Dictionary {'width': ..., 'height': ...}
            if loc and size and 'x' in loc and 'y' in loc and 'width' in size and 'height' in size:
                 center_x = loc['x'] + size['width'] // 2
                 center_y = loc['y'] + size['height'] // 2
                 return (center_x, center_y)
            else:
                 logging.warning(f"Could not get valid location/size for element: {element.id if hasattr(element,'id') else 'Unknown ID'}")
                 return None
        except Exception as e:
            logging.error(f"Error getting element center coordinates: {e}")
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
        time.sleep(getattr(config, 'STABILITY_WAIT', 1.0)) # Wait for UI stability
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
        """Starts and manages the crawling loop based on configured mode (steps or time)."""
        logging.info("--- Starting AI App Crawler ---")
        crawl_start_time = time.time() # Record start time for time-based crawling
        run_successful = False # Flag to track if the main loop starts
        capture_started_successfully = False # Flag for traffic capture

        # --- Get Crawl Mode Configuration ---
        crawl_mode = getattr(config, 'CRAWL_MODE', 'steps').lower()
        max_steps = getattr(config, 'MAX_CRAWL_STEPS', 100)
        max_duration_seconds = getattr(config, 'MAX_CRAWL_DURATION_SECONDS', 600)

        if crawl_mode == 'steps':
            logging.info(f"Running in 'steps' mode. Max steps: {max_steps}")
        elif crawl_mode == 'time':
            logging.info(f"Running in 'time' mode. Max duration: {max_duration_seconds} seconds")
        else:
            logging.warning(f"Unknown CRAWL_MODE '{crawl_mode}'. Defaulting to 'steps' mode with max steps: {max_steps}")
            crawl_mode = 'steps'

        # --- Setup ---
        try:
            # 1. Connect DB first
            logging.info("Connecting to database...")
            if not self.db_manager.connect():
                 logging.critical("Failed to connect to database. Aborting run.")
                 return

            logging.info("Database connection successful.")

            # 2. Initialize StateManager *after* DB connection
            logging.info("Initializing State Manager...")
            try:
                self.state_manager = CrawlingState(self.db_manager)
                logging.info("State Manager initialized and loaded state from DB.")
            except Exception as sm_init_err:
                 logging.critical(f"Failed to initialize State Manager: {sm_init_err}", exc_info=True)
                 if self.db_manager: self.db_manager.close()
                 return

            # 3. Connect Appium Driver
            logging.info("Connecting to Appium driver...")
            if not self.driver.connect():
                logging.critical("Failed to establish Appium connection. Aborting run.")
                if self.db_manager: self.db_manager.close()
                return ########## ADDED RETURN HERE
            logging.info("Appium driver connection successful.")

            # --- Start Traffic Capture (if enabled) ---
            if self.traffic_capture_enabled:
                logging.info("Traffic capture is ENABLED in config.")
                if self._start_traffic_capture():
                    capture_started_successfully = True
                    logging.info("Traffic capture initiated.")
                else:
                    logging.warning("Failed to start traffic capture. Crawling will continue without it.")
                    # Optionally, decide if this is a critical failure:
                    # if config.REQUIRE_TRAFFIC_CAPTURE_TO_RUN:
                    #     logging.critical("Traffic capture failed and is required. Aborting run.")
                    #     if self.db_manager: self.db_manager.close()
                    #     if self.driver: self.driver.disconnect()
                    #     return
            else:
                logging.info("Traffic capture is DISABLED in config.")
            # --- End Traffic Capture Start ---


            # --- Initialization successful ---
            run_successful = True
            self.previous_composite_hash = None
            self._last_action_description = "START"
            step_count = 0 # Initialize step counter

            # --- Main Crawling Loop (modified for time/step modes) ---
            while True: # Loop indefinitely until a break condition is met
                step_count += 1
                current_time = time.time()
                elapsed_time = current_time - crawl_start_time

                # --- Check Termination Conditions (Mode Dependent) ---
                if crawl_mode == 'steps':
                    if step_count > max_steps:
                        logging.info(f"Termination: Reached max step count ({max_steps}).")
                        break
                    logging.info(f"\\n--- Step {step_count}/{max_steps} ---")
                elif crawl_mode == 'time':
                    if elapsed_time > max_duration_seconds:
                        logging.info(f"Termination: Reached max duration ({elapsed_time:.1f}s / {max_duration_seconds}s). Total steps: {step_count-1}")
                        break
                    logging.info(f"\\n--- Step {step_count} (Time: {elapsed_time:.1f}s / {max_duration_seconds}s) ---")

                # Check failure-based termination (common to both modes)
                if self._check_termination(): # Call the updated method (checks failures only)
                    break

                # 0. Ensure Correct App Context
                if not self._ensure_in_app():
                    logging.critical("Cannot ensure app context. Stopping crawl.")
                    break

                # 1. Get Current State
                state_data = self._get_current_state()
                if state_data is None:
                    logging.warning(f"Failed get state step {step_count}, fallback: BACK.")
                    self.driver.press_back_button(); time.sleep(config.WAIT_AFTER_ACTION);
                    self._last_action_description = f"GET_STATE_FAIL_BACK (Step {step_count})"
                    self.previous_composite_hash = None; continue

                screenshot_bytes, page_source = state_data
                xml_hash = utils.calculate_xml_hash(page_source) or "xml_hash_error"
                visual_hash = utils.calculate_visual_hash(screenshot_bytes) or "visual_hash_error"
                if "error" in xml_hash or "error" in visual_hash:
                     logging.error(f"Hash error (XML:{xml_hash}, Vis:{visual_hash}). Fallback: BACK.")
                     self.driver.press_back_button(); time.sleep(config.WAIT_AFTER_ACTION);
                     self._last_action_description = f"HASH_ERROR_BACK (Step {step_count})"
                     self.previous_composite_hash = None; continue

                # --- CHANGE 1: Calculate initial hash, but rely on state_manager's result ---
                initial_composite_hash = f"{xml_hash}_{visual_hash}"
                logging.debug(f"Calculated initial hash for step {step_count}: {initial_composite_hash}")

                # 2. Add/Get Screen Representation (Handles similarity)
                try:
                    if not self.state_manager: raise RuntimeError("StateManager not initialized!")
                    # This call returns the ScreenRepresentation for the *actual* state being used
                    # (either new or the visually similar existing one)
                    current_screen_repr = self.state_manager.add_or_get_screen(
                        xml_hash, visual_hash, screenshot_bytes
                    )
                    if not current_screen_repr: raise RuntimeError("add_or_get_screen returned None")

                    # --- CHANGE 2: Get the definitive hash *from the returned object* ---
                    # This hash will be correct whether it's a new screen or a similar match
                    definitive_composite_hash = current_screen_repr.get_composite_hash()
                    logging.info(f"Using definitive hash: {definitive_composite_hash} (Screen ID: {current_screen_repr.id})")
                    # --------------------------------------------------------------------

                except Exception as screen_err:
                    logging.error(f"Error add/get screen: {screen_err}. Fallback: BACK.", exc_info=True)
                    self.driver.press_back_button(); time.sleep(config.WAIT_AFTER_ACTION);
                    self._last_action_description = f"STATE_MGR_SCREEN_ERR_BACK (Step {step_count})"
                    self.previous_composite_hash = None; continue

                # Logging the retrieved screen info
                logging.info(f"Current Screen: ID={current_screen_repr.id}, Hash={definitive_composite_hash}") # Use definitive hash

                # 3. Record Transition (using previous step's hash and current definitive hash)
                if self.previous_composite_hash is not None:
                     try: self.state_manager.add_transition(self.previous_composite_hash, self._last_action_description, definitive_composite_hash)
                     except Exception as trans_err: logging.error(f"Error adding transition: {trans_err}", exc_info=True)

                # 4. Check Termination
                if self._check_termination(): break # Corrected: _check_termination no longer takes step_count

                # --- CHANGE 3: Use definitive_composite_hash for history and visit count ---
                # 5. Get Action History for Current Screen
                action_history = self.state_manager.get_action_history(definitive_composite_hash)
                logging.debug(f"Action history for screen {current_screen_repr.id} (Hash: {definitive_composite_hash}): {action_history}")

                # 6. Get Visit Count for Current Screen (for Loop Detection)
                current_visit_count = self.state_manager.get_visit_count(definitive_composite_hash)
                logging.info(f"Visit count for {definitive_composite_hash}: {current_visit_count}") # Use definitive hash

                # 7. Get AI Action Suggestion (Passing correct hash and count)
                xml_for_ai = utils.simplify_xml_for_ai(page_source, config.XML_SNIPPET_MAX_LEN) if getattr(config, 'ENABLE_XML_CONTEXT', True) else ""
                ai_suggestion = self.ai_assistant.get_next_action(
                    screenshot_bytes, xml_for_ai, action_history, config.AVAILABLE_ACTIONS,
                    current_visit_count,  # Pass the correct count
                    definitive_composite_hash # Pass the correct hash
                )
                # ---------------------------------------------------------------------------

                # 8. Handle AI Failure
                if ai_suggestion is None:
                    logging.error(f"AI fail step {step_count}. Fallback: BACK.")
                    self.consecutive_ai_failures += 1; fallback_ok = self.driver.press_back_button();
                    self._last_action_description = f"AI_FAIL_BACK (Step {step_count})"
                    if not fallback_ok: self.consecutive_exec_failures += 1
                    time.sleep(config.WAIT_AFTER_ACTION);
                    self.previous_composite_hash = definitive_composite_hash # Use definitive hash
                    continue
                else:
                    self.consecutive_ai_failures = 0
                    action_type_sugg = ai_suggestion.get('action', '??'); target_id_sugg = ai_suggestion.get('target_identifier', 'N/A')
                    # Description of the action *to be taken* in this step
                    self._last_action_description = f"{action_type_sugg}: '{target_id_sugg}' (Step {step_count})"


                # 9. Map AI Suggestion
                mapped_action = self._map_ai_to_action(ai_suggestion)

                # 10. Handle Mapping Failure
                if mapped_action is None:
                    # Increment counter if not already done by an exception in _map_ai_to_action
                    # (This check prevents double counting if _map_ai_to_action returned None explicitly)
                    pass # Assuming _map_ai_to_action handles its own failure count increment

                    logging.error(f"Map fail step {step_count}. Fallback: BACK.")
                    # --- Add keyboard check for double back ---
                    keyboard_shown = False
                    try:
                        keyboard_shown = self.driver.is_keyboard_shown()
                        logging.debug(f"Keyboard shown before fallback BACK: {keyboard_shown}")
                    except Exception as key_err:
                        logging.warning(f"Could not check keyboard status: {key_err}")

                    self.driver.press_back_button() # Press back once regardless
                    self._last_action_description = f"MAP_FAIL_BACK (Step {step_count})"
                    if keyboard_shown:
                        logging.info("Keyboard was shown, pressing BACK a second time for navigation.")
                        time.sleep(0.5) # Small delay before second back press
                        self.driver.press_back_button()
                        self._last_action_description = f"MAP_FAIL_KEYBOARD_DOUBLE_BACK (Step {step_count})"
                    # --- End keyboard check ---

                    time.sleep(config.WAIT_AFTER_ACTION)
                    self.previous_composite_hash = None # Reset hash to force re-evaluation after fallback
                    if self._check_termination(): break # Check termination after failure
                    continue # Skip to next step after fallback

                # 11. SAVE ANNOTATED SCREENSHOT (Optional)
                self._save_annotated_screenshot(screenshot_bytes, step_count, current_screen_repr.id, ai_suggestion)

                # 12. Execute Action
                execution_success = self._execute_action(mapped_action)

                # 13. Wait After Action
                time.sleep(config.WAIT_AFTER_ACTION)

                # --- CHANGE 4: Update previous_composite_hash with the definitive hash ---
                # 14. Update Previous State Hash for *Next* Iteration
                self.previous_composite_hash = definitive_composite_hash
                # ----------------------------------------------------------------------

            # --- End of Loop ---
            # Check if loop finished due to max steps or early termination
            if step_count < max_steps : # Corrected: current_step_number to step_count
                 logging.info(f"Crawling loop terminated at step {step_count} before reaching max steps ({max_steps}).") # Corrected: current_step_number to step_count
            else:
                 logging.info(f"Crawling loop finished after reaching max steps ({max_steps}).")


        except KeyboardInterrupt:
             logging.warning("Crawling interrupted by user (KeyboardInterrupt).")
             run_successful = False
        except Exception as e:
            logging.critical(f"An uncaught exception occurred during crawling setup or loop: {e}", exc_info=True)
            run_successful = False
        finally:
            # --- Stop and Pull Traffic Capture (if started) ---
            if capture_started_successfully: # Only if it was successfully started
                logging.info("Stopping and processing traffic capture data...")
                self._stop_traffic_capture() # Attempt to stop
                if self._pull_traffic_capture_file(): # Attempt to pull
                    if getattr(config, 'CLEANUP_DEVICE_PCAP_FILE', False):
                        self._cleanup_device_pcap_file() # Cleanup if pull was successful and configured
                else:
                    logging.warning("Failed to pull the traffic capture file. It might still be on the device.")
            elif self.traffic_capture_enabled and not capture_started_successfully:
                logging.info("Traffic capture was enabled but did not start successfully, so no capture data to process.")
            # --- End Traffic Capture Stop/Pull ---

            # --- Original Cleanup ---
            logging.info("--- Crawling Finished / Cleaning Up ---")
            duration = time.time() - crawl_start_time # Corrected: start_time to crawl_start_time
            logging.info(f"Total duration: {duration:.2f} seconds")
            if self.state_manager:
                try:
                    total_screens = self.state_manager.get_total_screens()
                    total_transitions = self.state_manager.get_total_transitions()
                    logging.info(f"Discovered {total_screens} unique screen states (in memory).")
                    logging.info(f"Recorded approximately {total_transitions} transitions in DB.")
                except Exception as report_err:
                    logging.error(f"Error generating final report stats: {report_err}")
            elif run_successful:
                 logging.error("State manager was not available for final reporting despite run starting.")
            else:
                 logging.info("Setup did not complete fully, final stats may be inaccurate.")

            if self.driver: self.driver.disconnect()
            if self.db_manager: self.db_manager.close()
            logging.info("--- Cleanup Complete ---")

if __name__ == "__main__":
    # Basic logging setup
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    crawler = AppCrawler()
    crawler.run()