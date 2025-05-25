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
    def __init__(self, config_dict: dict):
        """Initialize the AppCrawler with configuration.
        Args:
            config_dict (dict): Configuration dictionary with all necessary settings.
        """
        self.config_dict = config_dict

        # Store original config values in an instance variable instead of module level
        self._original_config_values = {}
        
        # Update the local config module with values from config_dict
        # This ensures all imported modules use the same config values
        for key, value in config_dict.items():
            current_value = getattr(config, key, None)
            if current_value is not None:  # Only store and update if the attribute exists
                self._original_config_values[key] = current_value
                if value is not None:  # Only set if the new value is not None
                    setattr(config, key, value)
        
        # Get required Appium configuration
        appium_url = config_dict.get('APPIUM_SERVER_URL')
        if not appium_url:
            raise ValueError("APPIUM_SERVER_URL is required in configuration")
        
        new_command_timeout = config_dict.get('NEW_COMMAND_TIMEOUT')
        if new_command_timeout is None: # Check for None as 0 is a valid timeout
            raise ValueError("NEW_COMMAND_TIMEOUT is required in configuration")
        self.config_dict['NEW_COMMAND_TIMEOUT'] = new_command_timeout

        appium_implicit_wait = config_dict.get('APPIUM_IMPLICIT_WAIT')
        if appium_implicit_wait is None: # Check for None as 0 is a valid wait
            raise ValueError("APPIUM_IMPLICIT_WAIT is required in configuration")
        self.config_dict['APPIUM_IMPLICIT_WAIT'] = appium_implicit_wait
        
        # Get required values for AI and state management
        gemini_api_key = config_dict.get('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required in configuration")

        model_type = config_dict.get('DEFAULT_MODEL_TYPE')
        if not model_type:
            raise ValueError("DEFAULT_MODEL_TYPE is required in configuration")

        # Safety settings can be None, but must be explicitly in config if used
        safety_settings = config_dict.get('AI_SAFETY_SETTINGS')
        if safety_settings is None:
            raise ValueError("AI_SAFETY_SETTINGS is required in configuration")

        # Ensure required values for database and state management
        db_name = str(config_dict.get('DB_NAME', ''))
        if not db_name:
            raise ValueError("DB_NAME is required in configuration")

        self.driver = AppiumDriver(appium_url, config_dict)
        # Update AI Assistant initialization with proper type handling
        self.ai_assistant = AIAssistant(
            api_key=gemini_api_key,
            model_name=model_type,
            safety_settings=safety_settings
        )
        self.db_manager = DatabaseManager(db_name)
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
        print(f"{UI_STATUS_PREFIX} INITIALIZING")

        try:
            # Connect to Appium first
            self.driver.connect()
            logging.info("Appium driver connected successfully before traffic capture initiation.")

            # Ensure database is connected
            if not self.db_manager:
                logging.critical("Database manager not initialized. Stopping crawler.")
                print(f"{UI_END_PREFIX} FAILURE_DB_MANAGER_MISSING")
                return

            try:
                self.db_manager.connect()
                logging.info("Database connection successful.")
            except Exception as e_db_connect:
                logging.critical(f"Failed to connect to database: {e_db_connect}.", exc_info=True)
                print(f"{UI_END_PREFIX} FAILURE_DB_CONNECT: {str(e_db_connect)}")
                return

            # Start Traffic Capture if enabled
            if self.traffic_capture_enabled:
                if not self.traffic_capture_manager.start_traffic_capture():
                    logging.warning("Failed to start traffic capture. Continuing without it.")
                else:
                    logging.info("Traffic capture started successfully.")

            # Launch and verify target app
            if not self.app_context_manager.launch_and_verify_app():
                logging.critical("Failed to launch and verify target application.")
                print(f"{UI_END_PREFIX} FAILURE_APP_LAUNCH_CONTEXT_MANAGER")
                if self.traffic_capture_enabled:
                    self.traffic_capture_manager.stop_traffic_capture()
                return

            logging.info("Target application launched and verified.")

            # Load or Initialize Run State
            if config.CONTINUE_EXISTING_RUN and self.screen_state_manager.load_from_db():
                logging.info(f"Loaded existing run. Current step: {self.screen_state_manager.current_step_number}")
                # Validate loaded state matches current target
                if not (self.screen_state_manager.app_package and self.screen_state_manager.start_activity):
                    self._reinitialize_state_with_target()
                elif self.screen_state_manager.app_package != str(self.config_dict.get("APP_PACKAGE", "")):
                    self._reinitialize_state_with_target()
            else:
                # Start fresh run
                logging.info("Starting fresh run.")
                if self.db_manager:
                    self.db_manager.initialize_db()
                self._reinitialize_state_with_target()

            # Ensure state manager has required values
            if not self.screen_state_manager.app_package:
                self.screen_state_manager.app_package = str(self.config_dict.get("APP_PACKAGE", ""))
            if not self.screen_state_manager.start_activity:
                self.screen_state_manager.start_activity = str(self.config_dict.get("APP_ACTIVITY", ""))

            logging.info(f"Using Activity: '{self.screen_state_manager.start_activity}', Package: '{self.screen_state_manager.app_package}'")
            print(f"{UI_STATUS_PREFIX} RUNNING")

            # Main crawl loop
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
                logging.info(f"Getting AI suggestion for screen: {screen_rep.id} (Hash: {screen_rep.get_composite_hash()})")
                
                # Get screen context and history
                xml_snippet = None
                if getattr(config, 'ENABLE_XML_CONTEXT', False) and page_source:
                    max_len = getattr(config, 'XML_SNIPPET_MAX_LEN', 30000)
                    xml_snippet = utils.simplify_xml_for_ai(page_source, max_len=max_len)

                current_screen_hash = screen_rep.get_composite_hash()
                history_for_screen = self.screen_state_manager.get_action_history(current_screen_hash)
                max_prompt_history = getattr(config, 'MAX_CHAT_HISTORY', 10)
                previous_actions = history_for_screen[-max_prompt_history:]
                current_visit_count = self.screen_state_manager.get_visit_count(current_screen_hash)

                # Get AI suggestion using type-safe helper
                ai_suggestion_json = self.get_ai_next_action(
                    screenshot_bytes=screenshot_bytes,
                    xml_snippet=xml_snippet,
                    previous_actions=previous_actions,
                    visit_count=current_visit_count,
                    screen_hash=current_screen_hash
                )

                # --- Handle shutdown flag
                if shutdown_flag_path and os.path.exists(shutdown_flag_path):
                    logging.info("Shutdown flag detected after AI interaction.")
                    print(f"{UI_END_PREFIX} SHUTDOWN_FLAG_DETECTED_POST_AI")
                    break

                # Handle AI failure
                if not ai_suggestion_json:
                    logging.error("AI failed to provide suggestion.")
                    self.consecutive_ai_failures += 1
                    if self.consecutive_ai_failures >= config.MAX_CONSECUTIVE_AI_FAILURES:
                        logging.critical("Max consecutive AI failures reached.")
                        print(f"{UI_END_PREFIX} FAILURE_MAX_AI_FAIL")
                        break

                    # Fallback: go back
                    self.driver.perform_action("back", None)
                    self._last_action_description = "BACK (AI failure fallback)"
                    self.screen_state_manager.increment_step(
                        self._last_action_description, "auto_back_ai_fail",
                        None, None, None, None, None, None
                    )
                    steps_taken += 1
                    continue

                self.consecutive_ai_failures = 0  # Reset on success
                logging.info(f"AI Suggestion: {ai_suggestion_json}")

                # Update screenshot with AI suggestion
                if screenshot_bytes and screen_rep:
                    self.screenshot_annotator.save_annotated_screenshot(
                        original_screenshot_bytes=screenshot_bytes,
                        step=self.screen_state_manager.current_step_number,
                        screen_id=screen_rep.id,
                        ai_suggestion=ai_suggestion_json
                    )

                # Map AI suggestion to action
                mapped_action = self.action_mapper.map_ai_to_action(ai_suggestion_json)
                if not mapped_action:
                    logging.error("Failed to map AI suggestion to executable action.")
                    self.consecutive_map_failures += 1
                    if self.consecutive_map_failures >= config.MAX_CONSECUTIVE_MAP_FAILURES:
                        logging.critical("Max consecutive mapping failures reached.")
                        print(f"{UI_END_PREFIX} FAILURE_MAX_MAP_FAIL")
                        break

                    # Fallback: go back
                    self.driver.perform_action("back", None)
                    self._last_action_description = "BACK (mapping failure fallback)"
                    self.screen_state_manager.increment_step(
                        self._last_action_description, "auto_back_map_fail",
                        None, None, None, None, None, None
                    )
                    steps_taken += 1
                    continue

                self.consecutive_map_failures = 0  # Reset on success

                # Unpack mapped action using type-safe helper
                action_type_sugg, target_obj_sugg, input_text_sugg, action_mode_sugg = \
                    self.handle_mapped_action(mapped_action)
                
                if not action_type_sugg:  # Invalid mapped action
                    logging.error("Invalid mapped action structure")
                    self.driver.perform_action("back", None)
                    self._last_action_description = "BACK (invalid mapping structure)"
                    self.screen_state_manager.increment_step(
                        self._last_action_description, "auto_back_map_invalid",
                        None, None, None, None, None, None
                    )
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

                # Handle execution failure with config-based fallback
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
                    steps_taken += 1
                    # Get wait time from config
                    wait_time = getattr(config, 'WAIT_AFTER_ACTION')
                    if wait_time is None:
                        raise ValueError("WAIT_AFTER_ACTION must be defined in config")
                    time.sleep(wait_time)  # Wait before retrying
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
                wait_time = getattr(config, 'WAIT_AFTER_ACTION')
                if wait_time is None:
                    raise ValueError("WAIT_AFTER_ACTION must be defined in config")
                time.sleep(wait_time)  # Wait for UI to settle

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

    def initialize_state_manager(self, activity: Optional[str], package: Optional[str]) -> None:
        """Helper to safely initialize state manager with type checking."""
        if not activity or not package:
            raise ValueError("Both activity and package must be provided")
        self.screen_state_manager.initialize_run(str(activity), str(package))    
    
    def get_ai_next_action(self, screenshot_bytes: bytes, xml_snippet: Optional[str], 
                        previous_actions: List[str], visit_count: int, screen_hash: str) -> Optional[Dict[str, Any]]:
        """Helper to safely get AI next action with type checking.
        
        Returns:
            Optional[Dict[str, Any]]: The AI suggestion as a dictionary, or None if the AI assistant fails to provide a suggestion.
        """
        try:
            suggestion = self.ai_assistant.get_next_action(
                screenshot_bytes=screenshot_bytes, 
                xml_context=xml_snippet or "",
                previous_actions=previous_actions,
                available_actions=config.AVAILABLE_ACTIONS,
                current_screen_visit_count=visit_count,
                current_composite_hash=screen_hash
            )
            return suggestion
        except Exception as e:
            logging.error(f"Error getting AI next action: {e}", exc_info=True)
            return None

    def handle_mapped_action(self, mapped_action: Any) -> Tuple[Optional[str], Optional[Any], Optional[str], Optional[str]]:
        """Helper to safely handle mapped action with type checking."""
        if not mapped_action:
            logging.warning("Received empty mapped action")
            return None, None, None, None
        
        action_mode_sugg = None
        if isinstance(mapped_action, (list, tuple)):
            if len(mapped_action) >= 3:
                action_type_sugg = mapped_action[0]
                target_obj_sugg = mapped_action[1]
                input_text_sugg = mapped_action[2]
                if len(mapped_action) > 3:
                    action_mode_sugg = mapped_action[3]
                return action_type_sugg, target_obj_sugg, input_text_sugg, action_mode_sugg
            else:
                logging.error(f"Mapped action has wrong number of elements: {len(mapped_action)}")
                return None, None, None, None
        else:
            logging.error(f"Mapped action is not list/tuple: {type(mapped_action)}")
            return None, None, None, None

    def _reinitialize_state_with_target(self) -> None:
        """Helper method to reinitialize state manager with current target app details."""
        current_activity = self.driver.get_current_activity()
        current_package = self.driver.get_current_package()
        
        if not current_activity or not current_package:
            raise ValueError("Could not get current activity and package from driver")
        
        # If current app doesn't match target, use configured values
        if current_package != str(self.config_dict.get("APP_PACKAGE", "")):
            current_activity = str(self.config_dict.get("APP_ACTIVITY", ""))
            current_package = str(self.config_dict.get("APP_PACKAGE", ""))
        
        logging.info(f"Reinitializing state with activity='{current_activity}', package='{current_package}'")
        self.initialize_state_manager(current_activity, current_package)
        logging.info("State reinitialized with current target app details")