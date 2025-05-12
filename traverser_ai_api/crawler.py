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
        self.action_mapper = ActionMapper(self.driver, self.element_finding_strategies, self.config_dict) # Pass config_dict

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


    def perform_full_cleanup(self):
        logging.info("Performing full cleanup sequence...")

        # 1. Stop and Pull Traffic Capture File
        try:
            if self.traffic_capture_enabled and self.traffic_capture_manager and self.traffic_capture_manager.pcap_filename_on_device:
                logging.info("Attempting to stop and pull traffic capture...")
                if self.traffic_capture_manager.stop_traffic_capture():
                    logging.info("Traffic capture stopped successfully via full_cleanup.")
                    if self.traffic_capture_manager.pull_traffic_capture_file():
                        logging.info("Traffic capture file pulled successfully via full_cleanup.")
                        if self.config_dict.get('CLEANUP_DEVICE_PCAP_FILE', False):
                            self.traffic_capture_manager.cleanup_device_pcap_file()
                    else:
                        logging.error("Failed to pull traffic capture file during full_cleanup.")
                else:
                    logging.warning("Failed to stop traffic capture cleanly during full_cleanup. Attempting to pull anyway.")
                    if self.traffic_capture_manager.pcap_filename_on_device and self.traffic_capture_manager.local_pcap_file_path:
                        if self.traffic_capture_manager.pull_traffic_capture_file():
                            logging.info("Traffic capture file pulled (after stop command issue) via full_cleanup.")
                            if self.config_dict.get('CLEANUP_DEVICE_PCAP_FILE', False):
                                self.traffic_capture_manager.cleanup_device_pcap_file()
                        else:
                            logging.error("Failed to pull traffic capture file (after stop command issue) during full_cleanup.")
                    else:
                        logging.info("Skipping pull after failed stop, as necessary info for pull might be missing (e.g. pcap_filename_on_device or local_pcap_file_path not set).")
            elif not self.traffic_capture_enabled:
                logging.info("Traffic capture was not enabled. Skipping traffic cleanup.")
            elif not self.traffic_capture_manager:
                logging.warning("TrafficCaptureManager not initialized. Skipping traffic cleanup.")
            elif not (self.traffic_capture_manager.pcap_filename_on_device if self.traffic_capture_manager else False):
                 logging.info("Traffic capture was enabled but pcap_filename_on_device not set (capture might not have started). Skipping traffic cleanup.")
        except Exception as e_traffic:
            logging.error(f"Error during traffic capture cleanup: {e_traffic}", exc_info=True)
        
        # 2. Disconnect Appium Driver
        try:
            if self.driver:
                logging.info("Attempting to disconnect Appium driver...")
                self.driver.disconnect()
                logging.info("Appium driver disconnected successfully.")
            else:
                logging.info("Appium driver instance not found. Skipping disconnect.")
        except Exception as e_driver:
            logging.error(f"Error during Appium driver disconnect: {e_driver}", exc_info=True)
        
        # 3. Close Database
        try:
            if self.db_manager:
                logging.info("Attempting to close database connection...")
                self.db_manager.close()
                logging.info("Database connection closed successfully.")
            else:
                logging.info("Database manager instance not found. Skipping DB close.")
        except Exception as e_db:
            logging.error(f"Error during database close: {e_db}", exc_info=True)
            
        try:
            if self.screen_state_manager:
                logging.info(f"Full cleanup: Total unique screens discovered: {self.screen_state_manager.get_total_screens()}")
                logging.info(f"Full cleanup: Total transitions recorded in DB: {self.screen_state_manager.get_total_transitions()}")
            else:
                logging.info("Screen state manager not available for final stats.")
        except Exception as e_stats:
            logging.error(f"Error retrieving final stats: {e_stats}", exc_info=True)
            
        logging.info("Crawler full cleanup finished.")


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

            # Ensure database is connected
            if self.db_manager:
                try:
                    logging.info("Attempting to connect to the database...")
                    # Assuming connect() is idempotent or handles already connected state
                    self.db_manager.connect() 
                    logging.info("Database connection successful or already established.")
                except Exception as e_db_connect:
                    logging.critical(f"Failed to connect to the database: {e_db_connect}. Stopping crawler.", exc_info=True)
                    print(f"{UI_END_PREFIX} FAILURE_DB_CONNECT: {str(e_db_connect)}")
                    # perform_full_cleanup will be called in the outer finally block
                    return 
            else:
                logging.critical("Database manager (self.db_manager) is not initialized. Stopping crawler.")
                print(f"{UI_END_PREFIX} FAILURE_DB_MANAGER_MISSING")
                # perform_full_cleanup will be called in the outer finally block
                return

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
                if not self.screen_state_manager.load_from_db():
                    logging.warning("Failed to load existing run data from DB, starting fresh. Will use current foreground app state.")
                    # Initialize with the (now confirmed) target app's activity and package
                    current_activity = self.driver.get_current_activity()
                    current_package = self.driver.get_current_package()
                    if current_package != self.config_dict.get("APP_PACKAGE"):
                        logging.warning(f"Current foreground app ({current_package}/{current_activity}) does not match target ({self.config_dict.get('APP_PACKAGE')}). Will initialize SSM with target config.")
                        current_activity = self.config_dict.get("APP_ACTIVITY")
                        current_package = self.config_dict.get("APP_PACKAGE")
                    self.screen_state_manager.initialize_run(current_activity, current_package)
                else:
                    logging.info(f"Successfully loaded some data from DB. Current step from DB: {self.screen_state_manager.current_step_number}")
                    # Check if the loaded run's package information is valid, if not, re-initialize with current target.
                    if not self.screen_state_manager.app_package or not self.screen_state_manager.start_activity:
                        logging.warning(f"Loaded run from DB but app_package ('{self.screen_state_manager.app_package}') or start_activity ('{self.screen_state_manager.start_activity}') is missing. Re-initializing SSM with current target app details.")
                        current_activity = self.config_dict.get("APP_ACTIVITY")
                        current_package = self.config_dict.get("APP_PACKAGE")
                        self.screen_state_manager.initialize_run(current_activity, current_package)
                        logging.info("Step number reset to 0 due to re-initialization of SSM with current target app details.")
                    elif self.screen_state_manager.app_package != self.config_dict.get("APP_PACKAGE"):
                        logging.warning(f"Loaded run's package ({self.screen_state_manager.app_package}) does not match current target ({self.config_dict.get('APP_PACKAGE')}). Re-initializing SSM with current target app details.")
                        current_activity = self.config_dict.get("APP_ACTIVITY")
                        current_package = self.config_dict.get("APP_PACKAGE")
                        self.screen_state_manager.initialize_run(current_activity, current_package)
                        logging.info("Step number reset to 0 due to mismatch with current target app.")
                    else:
                        logging.info(f"SSM retains loaded app_package='{self.screen_state_manager.app_package}' and start_activity='{self.screen_state_manager.start_activity}'.")

            else: # Starting a fresh run
                logging.info("Starting a fresh run (CONTINUE_EXISTING_RUN is False).")
                if self.db_manager:
                    self.db_manager.initialize_db() # Clear and init DB for a fresh run
                else:
                    logging.warning("DB Manager not available, cannot initialize DB for fresh run.")
                # Initialize with the (now confirmed) target app's activity and package
                current_activity = self.driver.get_current_activity()
                current_package = self.driver.get_current_package()
                if current_package != self.config_dict.get("APP_PACKAGE"):
                    logging.warning(f"Current foreground app ({current_package}/{current_activity}) does not match target ({self.config_dict.get('APP_PACKAGE')}). Initializing SSM with target config.")
                    current_activity = self.config_dict.get("APP_ACTIVITY")
                    current_package = self.config_dict.get("APP_PACKAGE")
                self.screen_state_manager.initialize_run(current_activity, current_package)
            # ---
            # Ensure app_package and start_activity in screen_state_manager are now correctly set from target config if they were None
            if not self.screen_state_manager.app_package:
                self.screen_state_manager.app_package = self.config_dict.get("APP_PACKAGE")
                logging.info(f"SSM app_package was None, set to target: {self.screen_state_manager.app_package}")
            if not self.screen_state_manager.start_activity: # start_activity can be tricky if not well-defined for target
                self.screen_state_manager.start_activity = self.config_dict.get("APP_ACTIVITY")
                logging.info(f"SSM start_activity was None, set to target: {self.screen_state_manager.start_activity}")

            logging.info(f"Crawler initialized. Using Start Activity: '{self.screen_state_manager.start_activity}', App Package: '{self.screen_state_manager.app_package}' for the run.")
            print(f"{UI_STATUS_PREFIX} RUNNING") # UI Update

            start_time = time.time()
            steps_taken = 0

            while True:
                # --- Shutdown Flag Check (Beginning of Step) ---
                shutdown_flag_path = self.config_dict.get('SHUTDOWN_FLAG_PATH')
                if shutdown_flag_path and os.path.exists(shutdown_flag_path):
                    logging.info(f"Shutdown flag detected at path '{shutdown_flag_path}' at the beginning of a step. Stopping crawl.")
                    print(f"{UI_END_PREFIX} SHUTDOWN_FLAG_DETECTED")
                    break
                # ---

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

                # --- Shutdown Flag Check (After AI Interaction) ---
                if shutdown_flag_path and os.path.exists(shutdown_flag_path):
                    logging.info(f"Shutdown flag detected at path '{shutdown_flag_path}' after AI interaction. Stopping crawl.")
                    print(f"{UI_END_PREFIX} SHUTDOWN_FLAG_DETECTED_POST_AI")
                    break
                # ---

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

                # Unpack mapped_action, now potentially with a fourth element (action_mode)
                action_mode_sugg = None # Default to None
                if len(mapped_action) == 4:
                    action_type_sugg, target_obj_sugg, input_text_sugg, action_mode_sugg = mapped_action
                    logging.info(f"Mapped action (with mode): Type='{action_type_sugg}', Target='{target_obj_sugg}', Input='{input_text_sugg}', Mode='{action_mode_sugg}'")
                elif len(mapped_action) == 3:
                    action_type_sugg, target_obj_sugg, input_text_sugg = mapped_action
                    # action_mode_sugg remains None as set by default
                    logging.info(f"Mapped action (no mode): Type='{action_type_sugg}', Target='{target_obj_sugg}', Input='{input_text_sugg}'")
                else:
                    logging.error(f"Unexpected number of values in mapped_action: {len(mapped_action)}. Expected 3 or 4. Value: {mapped_action}")
                    # Fallback or error handling if mapped_action is not 3 or 4 elements
                    self.driver.perform_action("back", None)
                    self._last_action_description = "BACK (unexpected mapping result fallback)"
                    self.screen_state_manager.increment_step(self._last_action_description, "auto_back_map_unpack_fail", None, None, None, None, None, None)
                    steps_taken += 1
                    continue
                
                # --- UI Update for Action ---
                action_desc_for_ui = f"{action_type_sugg}"
                if isinstance(target_obj_sugg, WebElement):
                    try: # Safely get text or content-desc for UI
                        logging.debug("Attempting to get element text for UI description.")
                        el_text = target_obj_sugg.text
                        logging.debug(f"Element text for UI: '{el_text}'")

                        logging.debug("Attempting to get element content-desc for UI description.")
                        el_cd = target_obj_sugg.get_attribute('content-desc')
                        logging.debug(f"Element content-desc for UI: '{el_cd}'")

                        logging.debug("Attempting to get element id for UI description.")
                        el_id = target_obj_sugg.id # This might be the problematic access if element is stale
                        logging.debug(f"Element id for UI: '{el_id}'")
                        
                        ui_target_id = el_text if el_text else el_cd if el_cd else el_id if el_id else "element"
                        action_desc_for_ui += f" on '{ui_target_id}'"
                    except StaleElementReferenceException as sere:
                        logging.warning(f"StaleElementReferenceException generating UI action description: {str(sere)}")
                        action_desc_for_ui += " on [stale element]"
                    except Exception as e_ui_desc:
                        logging.error(f"Unexpected {type(e_ui_desc).__name__} generating UI action description: {str(e_ui_desc)}", exc_info=True)
                        action_desc_for_ui += " on [error accessing element]"
                elif isinstance(target_obj_sugg, str): # For scroll actions
                    action_desc_for_ui += f" {target_obj_sugg}"
                if input_text_sugg:
                    action_desc_for_ui += f" with text '{input_text_sugg}'"
                
                logging.info(f"Preparing to print UI action update: {action_desc_for_ui}") # Added log
                try:
                    # First try to encode as ASCII, replacing unsupported chars with '?'
                    safe_desc = ''.join(char if ord(char) < 128 else '?' for char in action_desc_for_ui)
                    print(f"{UI_ACTION_PREFIX} {safe_desc}")
                except Exception as e:
                    # If that fails, fall back to an even more basic representation
                    logging.warning(f"Error printing action description: {e}")
                    print(f"{UI_ACTION_PREFIX} [Action with unprintable characters]")
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

        except KeyboardInterrupt:
            logging.warning("KeyboardInterrupt caught within Crawler.run(). Cleanup will proceed in finally block.")
            # Allow finally block to handle cleanup
            print(f"{UI_END_PREFIX} INTERRUPTED_KEYBOARD") # UI Update
        except SystemExit as se:
            logging.warning(f"SystemExit caught in Crawler.run(): {se}. Cleanup will proceed in finally block.")
            print(f"{UI_END_PREFIX} INTERRUPTED_SYSTEM_EXIT: {str(se)}") # UI Update
        except Exception as e:
            logging.critical(f"An unhandled exception occurred during crawling: {e}", exc_info=True)
            print(f"{UI_END_PREFIX} FAILURE_UNHANDLED_EXCEPTION: {str(e)}") # UI Update
        finally:
            logging.info("Crawler.run() is now in its finally block.")
            self.perform_full_cleanup()