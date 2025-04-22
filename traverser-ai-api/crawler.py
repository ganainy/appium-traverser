import logging
import time
import os
from typing import Optional, Tuple, List, Dict, Any

# Import local modules
import config
import utils
from ai_assistant import AIAssistant
from appium_driver import AppiumDriver
from state_manager import CrawlingState, ScreenRepresentation
from database import DatabaseManager
from selenium.webdriver.remote.webelement import WebElement
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException

class AppCrawler:
    """Orchestrates the AI-driven app crawling process."""

    def __init__(self):
        self.config_dict = {k: getattr(config, k) for k in dir(config) if not k.startswith('_')}
        self.driver = AppiumDriver(config.APPIUM_SERVER_URL, self.config_dict)
        self.ai_assistant = AIAssistant(config.GEMINI_API_KEY, config.AI_MODEL_NAME, config.AI_SAFETY_SETTINGS)
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
                     try:
                         # Check if the initially found element is editable
                         element_class = original_element.get_attribute('class')
                         editable_classes = ['edittext', 'textfield', 'input', 'autocomplete']
                         if element_class and any(editable_tag in element_class.lower() for editable_tag in editable_classes):
                             is_editable = True
                             logging.debug(f"Initial element (Class: {element_class}) is directly editable.")
                         else:
                             logging.debug(f"Initial element (Class: {element_class}) is not directly editable. Checking parent...")
                             # --- Attempt to find editable parent ---
                             try:
                                 # Use XPath to select the parent node
                                 parent_element = original_element.find_element(AppiumBy.XPATH, "..")
                                 if parent_element:
                                     # --- Add more detailed logging ---
                                     logging.debug(f"Found parent element. Attempting to get class attribute...")
                                     parent_class = parent_element.get_attribute('class')
                                     if parent_class:
                                         logging.debug(f"Parent class found: '{parent_class}'. Checking if editable...")
                                         parent_class_lower = parent_class.lower()
                                         is_parent_editable = any(editable_tag in parent_class_lower for editable_tag in editable_classes)
                                         logging.debug(f"Editable tags check result for parent: {is_parent_editable}")
                                         # --- End detailed logging ---
                                         if is_parent_editable: # Use the result of the check
                                             logging.info(f"Using editable parent element (Class: {parent_class}) for INPUT action.")
                                             target_element = parent_element # Use the parent as the target
                                             is_editable = True
                                         else:
                                             logging.debug(f"Parent element class '{parent_class}' is not in editable list: {editable_classes}.")
                                     else:
                                         logging.debug("Could not retrieve class attribute from parent element.")
                                         # Parent found, but couldn't get class. Treat as not editable for safety.
                                 else:
                                     # This case should not happen if find_element succeeded without error, but good to have.
                                     logging.debug("Parent element found via XPath '..' but is None/False.")
                             except NoSuchElementException:
                                 logging.warning("No parent element found via XPath '..'.")
                             except Exception as parent_err:
                                 # Log the specific error encountered during parent processing
                                 logging.warning(f"Error finding or checking parent element: {parent_err}", exc_info=True) # Add exc_info
                             # --- End parent check ---

                         # If neither original nor parent is suitable, fail the mapping
                         if not is_editable:
                             # Ensure element_class has a value for the log message
                             log_element_class = element_class if element_class else "Unknown/Error"
                             logging.warning(f"AI suggested INPUT, but neither element (Class: {log_element_class}) nor its parent is editable for identifier '{target_identifier}'. Skipping action mapping.")
                             self.consecutive_map_failures += 1
                             return None # Mapping fails

                     except Exception as e:
                         logging.warning(f"Error during element class validation for INPUT: {e}. Proceeding cautiously.")
                 # --- End refactored validation ---

                 # Return tuple: (action_type, final_target_element, input_text_or_None)
                 return (action, target_element, input_text if action == "input" else None)
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


    def _check_termination(self, step_count: int) -> bool:
        """Checks if crawling should terminate."""
        if step_count >= config.MAX_CRAWL_STEPS:
            logging.info(f"Termination: Reached max step count ({config.MAX_CRAWL_STEPS}).")
            return True
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
        """Starts and manages the crawling loop."""
        logging.info("--- Starting AI App Crawler ---")
        start_time = time.time()
        run_successful = False # Flag to track if the main loop starts

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
                return
            logging.info("Appium driver connection successful.")

            # --- Initialization successful ---
            run_successful = True
            self.previous_composite_hash = None
            self._last_action_description = "START"

            # --- Main Crawling Loop ---
            max_steps = getattr(config, 'MAX_CRAWL_STEPS', 100)
            for step in range(max_steps):
                current_step_number = step + 1
                logging.info(f"\n--- Step {current_step_number}/{max_steps} ---")

                # 0. Ensure Correct App Context
                if not self._ensure_in_app():
                    logging.critical("Cannot ensure app context. Stopping crawl.")
                    break

                # 1. Get Current State
                state_data = self._get_current_state()
                if state_data is None:
                    logging.warning(f"Failed get state step {current_step_number}, fallback: BACK.")
                    self.driver.press_back_button(); time.sleep(config.WAIT_AFTER_ACTION);
                    self._last_action_description = f"GET_STATE_FAIL_BACK (Step {current_step_number})"
                    self.previous_composite_hash = None; continue

                screenshot_bytes, page_source = state_data
                xml_hash = utils.calculate_xml_hash(page_source) or "xml_hash_error"
                visual_hash = utils.calculate_visual_hash(screenshot_bytes) or "visual_hash_error"
                if "error" in xml_hash or "error" in visual_hash:
                     logging.error(f"Hash error (XML:{xml_hash}, Vis:{visual_hash}). Fallback: BACK.")
                     self.driver.press_back_button(); time.sleep(config.WAIT_AFTER_ACTION);
                     self._last_action_description = f"HASH_ERROR_BACK (Step {current_step_number})"
                     self.previous_composite_hash = None; continue

                # --- CHANGE 1: Calculate initial hash, but rely on state_manager's result ---
                initial_composite_hash = f"{xml_hash}_{visual_hash}"
                logging.debug(f"Calculated initial hash for step {current_step_number}: {initial_composite_hash}")

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
                    self._last_action_description = f"STATE_MGR_SCREEN_ERR_BACK (Step {current_step_number})"
                    self.previous_composite_hash = None; continue

                # Logging the retrieved screen info
                logging.info(f"Current Screen: ID={current_screen_repr.id}, Hash={definitive_composite_hash}") # Use definitive hash

                # 3. Record Transition (using previous step's hash and current definitive hash)
                if self.previous_composite_hash is not None:
                     try: self.state_manager.add_transition(self.previous_composite_hash, self._last_action_description, definitive_composite_hash)
                     except Exception as trans_err: logging.error(f"Error adding transition: {trans_err}", exc_info=True)

                # 4. Check Termination
                if self._check_termination(current_step_number): break

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
                    logging.error(f"AI fail step {current_step_number}. Fallback: BACK.")
                    self.consecutive_ai_failures += 1; fallback_ok = self.driver.press_back_button();
                    self._last_action_description = f"AI_FAIL_BACK (Step {current_step_number})"
                    if not fallback_ok: self.consecutive_exec_failures += 1
                    time.sleep(config.WAIT_AFTER_ACTION);
                    self.previous_composite_hash = definitive_composite_hash # Use definitive hash
                    continue
                else:
                    self.consecutive_ai_failures = 0
                    action_type_sugg = ai_suggestion.get('action', '??'); target_id_sugg = ai_suggestion.get('target_identifier', 'N/A')
                    # Description of the action *to be taken* in this step
                    self._last_action_description = f"{action_type_sugg}: '{target_id_sugg}' (Step {current_step_number})"


                # 9. Map AI Suggestion
                mapped_action = self._map_ai_to_action(ai_suggestion)

                # 10. Handle Mapping Failure
                if mapped_action is None:
                    # Increment counter if not already done by an exception in _map_ai_to_action
                    # (This check prevents double counting if _map_ai_to_action returned None explicitly)
                    if not ai_suggestion or ai_suggestion.get("action") in ["click", "input"]: # Only increment if it was a mapping attempt that failed
                         # Check if the counter wasn't already incremented by _map_ai_to_action itself
                         # This logic might need refinement depending on exactly how failures are counted internally
                         pass # Assuming _map_ai_to_action handles its own failure count increment

                    logging.error(f"Map fail step {current_step_number}. Fallback: BACK.")
                    # --- Add keyboard check for double back ---
                    keyboard_shown = False
                    try:
                        keyboard_shown = self.driver.is_keyboard_shown()
                        logging.debug(f"Keyboard shown before fallback BACK: {keyboard_shown}")
                    except Exception as key_err:
                        logging.warning(f"Could not check keyboard status: {key_err}")

                    self.driver.press_back_button() # Press back once regardless
                    self._last_action_description = f"MAP_FAIL_BACK (Step {current_step_number})"
                    if keyboard_shown:
                        logging.info("Keyboard was shown, pressing BACK a second time for navigation.")
                        time.sleep(0.5) # Small delay before second back press
                        self.driver.press_back_button()
                        self._last_action_description = f"MAP_FAIL_KEYBOARD_DOUBLE_BACK (Step {current_step_number})"
                    # --- End keyboard check ---

                    time.sleep(config.WAIT_AFTER_ACTION)
                    self.previous_composite_hash = None # Reset hash to force re-evaluation after fallback
                    if self._check_termination(current_step_number): break # Check termination after failure
                    continue # Skip to next step after fallback

                # 11. SAVE ANNOTATED SCREENSHOT (Optional)
                self._save_annotated_screenshot(screenshot_bytes, current_step_number, current_screen_repr.id, ai_suggestion)

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
            if current_step_number < max_steps :
                 logging.info(f"Crawling loop terminated at step {current_step_number} before reaching max steps ({max_steps}).")
            else:
                 logging.info(f"Crawling loop finished after reaching max steps ({max_steps}).")


        except KeyboardInterrupt:
             logging.warning("Crawling interrupted by user (KeyboardInterrupt).")
             run_successful = False
        except Exception as e:
            logging.critical(f"An uncaught exception occurred during crawling setup or loop: {e}", exc_info=True)
            run_successful = False
        finally:
            # --- Cleanup ---
            logging.info("--- Crawling Finished / Cleaning Up ---")
            duration = time.time() - start_time
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