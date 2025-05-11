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
from .screen_state_manager import ScreenStateManager, ScreenRepresentation # Correct import
from .database import DatabaseManager
from selenium.webdriver.remote.webelement import WebElement
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, InvalidSelectorException
from .action_mapper import ActionMapper # Added import
from .traffic_capture_manager import TrafficCaptureManager # Added import
from .action_executor import ActionExecutor # Added import
from .app_context_manager import AppContextManager # Added import
from .screenshot_annotator import ScreenshotAnnotator # Added import

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

        self.screen_state_manager = ScreenStateManager(self.db_manager, self.driver, self.config_dict)

        # Failure counters
        self.consecutive_ai_failures = 0
        self.consecutive_map_failures = 0

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

        # Initialize ActionMapper
        self.action_mapper = ActionMapper(self.driver, self.element_finding_strategies)

        # --- Traffic Capture Manager ---
        self.traffic_capture_enabled = getattr(config, 'ENABLE_TRAFFIC_CAPTURE', False)
        self.traffic_capture_manager = TrafficCaptureManager(
            self.driver,
            self.config_dict,
            self.traffic_capture_enabled
        )
        # --- End Traffic Capture Manager ---

        # Initialize ActionExecutor
        self.action_executor = ActionExecutor(self.driver, self.config_dict)

        # Initialize AppContextManager
        self.app_context_manager = AppContextManager(self.driver, self.config_dict)

        # Initialize ScreenshotAnnotator
        self.screenshot_annotator = ScreenshotAnnotator(self.driver, config) # Pass the config module


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

    def _check_termination(self) -> bool:
        """Checks if crawling should terminate based on failure conditions."""
        # Removed step count check - handled in run() loop based on CRAWL_MODE
        if self.consecutive_ai_failures >= config.MAX_CONSECUTIVE_AI_FAILURES:
            logging.error(f"Termination: Exceeded max consecutive AI failures ({config.MAX_CONSECUTIVE_AI_FAILURES}).")
            return True
        if self.consecutive_map_failures >= config.MAX_CONSECUTIVE_MAP_FAILURES:
            logging.error(f"Termination: Exceeded max consecutive mapping failures ({config.MAX_CONSECUTIVE_MAP_FAILURES}).")
            return True
        if self.action_executor.consecutive_exec_failures >= config.MAX_CONSECUTIVE_EXEC_FAILURES:
            logging.error(f"Termination: Exceeded max consecutive execution failures ({config.MAX_CONSECUTIVE_EXEC_FAILURES}).")
            return True
        # TODO: Add state repetition check using screen_state_manager.visited_screen_hashes
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
                if not self.traffic_capture_manager.start_traffic_capture(): # Updated to use TrafficCaptureManager
                    logging.warning("Failed to start traffic capture. Continuing without it.")
                    # Optionally, decide if this is a critical failure
                else:
                    logging.info("Traffic capture started successfully.")
            # --- End Start Traffic Capture ---


            # --- Ensure Target App is Launched using AppContextManager ---
            if not self.app_context_manager.launch_and_verify_app():
                logging.critical("App context manager failed to launch and verify the target application. Stopping.")
                print(f"{UI_END_PREFIX} FAILURE_APP_LAUNCH_CONTEXT_MANAGER")
                # Attempt to stop traffic capture before exiting
                if self.traffic_capture_enabled:
                    self.traffic_capture_manager.stop_traffic_capture()
                return
            logging.info("Target application launched and verified by AppContextManager.")
            # --- End Ensure Target App is Launched ---

            # Corrected: Removed self.config_dict from ScreenStateManager constructor call
            
            # --- Load or Initialize Run ---
            if config.CONTINUE_EXISTING_RUN:
                logging.info("Attempting to continue existing run...")
                # When continuing, we assume the app state is where we left off, or will be handled by existing logic.
                # No explicit re-launch here, but ensure screen_state_manager loads correctly.
                if not self.screen_state_manager.load_from_db():
                    logging.warning("Failed to load existing run, starting fresh. Will use current foreground app state.")
                    # If load fails, initialize with whatever is current, which should be target app due to above check
                    self.screen_state_manager.initialize_run(self.driver.get_current_activity(), self.driver.get_current_package())
                else:
                    logging.info(f"Successfully loaded run. Current step: {self.screen_state_manager.current_step_number}")
                    # Optional: Add a check here if the loaded state's package matches target_pkg
                    if self.screen_state_manager.app_package != self.config_dict.get("APP_PACKAGE"):
                        logging.warning(f"Loaded run's package ({self.screen_state_manager.app_package}) does not match target ({self.config_dict.get('APP_PACKAGE')}). This might lead to issues.")

            else: # Starting a fresh run
                logging.info("Starting a fresh run (CONTINUE_EXISTING_RUN is False).")
                self.db_manager.initialize_db() # Clear and init DB for a fresh run
                # Initialize with the (now confirmed) target app's activity and package
                self.screen_state_manager.initialize_run(self.driver.get_current_activity(), self.driver.get_current_package())
            # ---
            logging.info(f"Crawler initialized. Starting activity: {self.screen_state_manager.start_activity}, App package: {self.screen_state_manager.app_package}")
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

                logging.info(f"\\n--- Step {self.screen_state_manager.current_step_number} ---")
                
                # --- Ensure in correct app context before getting state ---
                if not self.app_context_manager.ensure_in_app():
                    logging.error("Failed to ensure app context. This might lead to incorrect state or actions.")
                    print(f"{UI_STATUS_PREFIX} WARNING_APP_CONTEXT_LOST")

                current_state_tuple = self.screen_state_manager.get_current_state()
                if not current_state_tuple:
                    logging.error("Failed to get current screen state. Cannot continue step.")
                    self.action_executor.consecutive_exec_failures += 1
                    if self._check_termination():
                        logging.error("Terminating due to inability to get current state and max exec failures.")
                        print(f"{UI_END_PREFIX} FAILURE_GET_STATE_TERMINATION")
                        break
                    time.sleep(config.WAIT_AFTER_ACTION) # Wait before retrying or next step
                    continue # Skip to next iteration, hoping state recovers
                screenshot_bytes, page_source = current_state_tuple
                current_activity = self.driver.get_current_activity()
                current_package = self.driver.get_current_package()

                # --- Check if outside allowed packages ---
                if current_package != self.screen_state_manager.app_package and current_package not in config.ALLOWED_EXTERNAL_PACKAGES:
                    logging.warning(f"Outside target app ({current_package}) and not in allowed external packages. Attempting to go back.")
                    self.driver.perform_action("back", None)
                    self._last_action_description = "BACK (auto due to off-app)"
                    self.screen_state_manager.increment_step(self._last_action_description, "auto_back_off_app", None, None, None, None, None, None)
                    steps_taken += 1
                    time.sleep(config.WAIT_AFTER_ACTION)
                    continue
                # ---

                # --- Calculate Hashes ---
                xml_hash = utils.calculate_xml_hash(page_source) if page_source else "no_xml_hash"
                visual_hash = utils.calculate_visual_hash(screenshot_bytes) if screenshot_bytes else "no_visual_hash"

                # --- Add/Get Screen Representation ---
                screen_rep, is_new_screen = self.screen_state_manager.add_or_get_screen_representation(
                    xml_hash, visual_hash, screenshot_bytes
                )
                if not screen_rep:
                    logging.error("Could not get or create screen representation. Critical error.")
                    print(f"{UI_END_PREFIX} FAILURE_SCREEN_REP") # UI Update
                    break
                # --- UI Update for Step and Screenshot ---
                print(f"{UI_STEP_PREFIX} {self.screen_state_manager.current_step_number}")
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
                
                history_for_screen = self.screen_state_manager.get_action_history(current_screen_hash) # Correct method & arg
                max_prompt_history = getattr(config, 'MAX_CHAT_HISTORY', 10) # Length for prompt history
                previous_actions_for_prompt = history_for_screen[-max_prompt_history:]
                
                current_visit_count = self.screen_state_manager.get_visit_count(current_screen_hash) # Correct way to get visit count

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
                    self.screen_state_manager.increment_step(self._last_action_description, "auto_back_ai_fail", None, None, None, None, None, None)
                    steps_taken += 1
                    continue
                self.consecutive_ai_failures = 0 # Reset on success
                logging.info(f"AI Suggestion: {ai_suggestion_json}")

                # --- Save Annotated Screenshot using ScreenshotAnnotator ---
                if screenshot_bytes and screen_rep and ai_suggestion_json:
                    self.screenshot_annotator.save_annotated_screenshot(
                        original_screenshot_bytes=screenshot_bytes,
                        step=self.screen_state_manager.current_step_number,
                        screen_id=screen_rep.id,
                        ai_suggestion=ai_suggestion_json
                    )
                # ---

                # --- Map AI suggestion to executable action ---
                mapped_action = self.action_mapper.map_ai_to_action(ai_suggestion_json) # Use ActionMapper instance
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
                    self.screen_state_manager.increment_step(self._last_action_description, "auto_back_map_fail", None, None, None, None, None, None)
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
                action_successful = self.action_executor.execute_action(mapped_action)

                if not action_successful:
                    logging.error(f"Failed to execute action: {action_type_sugg}")
                    if self._check_termination():
                        logging.critical("Max consecutive execution failures reached. Stopping crawl.")
                        print(f"{UI_END_PREFIX} FAILURE_MAX_EXEC_FAIL") # UI Update
                        break
                    # Fallback for execution failure
                    if current_package == self.screen_state_manager.app_package or current_package in config.ALLOWED_EXTERNAL_PACKAGES:
                        self.driver.perform_action("back", None)
                        self._last_action_description = "BACK (execution failure fallback)" # For overall tracking
                        # Log this specific fallback step
                        self.screen_state_manager.increment_step(
                            action_description=self._last_action_description,
                            action_type="auto_back_exec_fail", 
                            target_identifier=None, target_element_id=None, 
                            target_center_x=None, target_center_y=None, 
                            input_text=None, ai_raw_output=None
                        )
                    else: 
                        self._last_action_description = "NO_ACTION (execution failure, already off-app)"
                        self.screen_state_manager.increment_step(
                            action_description=self._last_action_description,
                            action_type="no_action_exec_fail_off_app",
                            target_identifier=None, target_element_id=None,
                            target_center_x=None, target_center_y=None,
                            input_text=None, ai_raw_output=None
                        )
                    steps_taken +=1 
                    continue 
                
                # If action was successful, use the pre-action gathered details for DB
                self._last_action_description = _last_action_description_for_db 

                self.screen_state_manager.increment_step(
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
            if self.traffic_capture_enabled and self.traffic_capture_manager.pcap_filename_on_device:
                if self.traffic_capture_manager.stop_traffic_capture(): # Updated to use TrafficCaptureManager
                    logging.info("Traffic capture stopped.")
                    if self.traffic_capture_manager.pull_traffic_capture_file(): # Updated to use TrafficCaptureManager
                        logging.info("Traffic capture file pulled.")
                        if self.config_dict.get('CLEANUP_DEVICE_PCAP_FILE', False): # Changed from getattr
                            self.traffic_capture_manager.cleanup_device_pcap_file() # Updated to use TrafficCaptureManager
                    else:
                        logging.error("Failed to pull traffic capture file.")
                else:
                    logging.warning("Failed to stop traffic capture cleanly. May attempt to pull anyway.")
                    # Attempt pull even if stop failed, as file might exist
                    if self.traffic_capture_manager.pull_traffic_capture_file(): # Updated to use TrafficCaptureManager
                        logging.info("Traffic capture file pulled (after stop command issue).")
                        if self.config_dict.get('CLEANUP_DEVICE_PCAP_FILE', False): # Changed from getattr
                            self.traffic_capture_manager.cleanup_device_pcap_file() # Updated to use TrafficCaptureManager
                    else:
                        logging.error("Failed to pull traffic capture file (after stop command issue).")
            # --- End Stop and Pull Traffic Capture ---
            self.driver.disconnect()
            self.db_manager.close()
            logging.info(f"Total unique screens discovered: {self.screen_state_manager.get_total_screens()}") # MODIFIED
            logging.info(f"Total transitions recorded in DB: {self.screen_state_manager.get_total_transitions()}") # MODIFIED
            logging.info("Crawler run finished and cleaned up.")