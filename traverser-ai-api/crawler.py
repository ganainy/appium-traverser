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


class AppCrawler:
    """Orchestrates the AI-driven app crawling process."""

    def __init__(self):
        self.config_dict = {k: getattr(config, k) for k in dir(config) if not k.startswith('_')}
        self.driver = AppiumDriver(config.APPIUM_SERVER_URL, self.config_dict)
        self.ai_assistant = AIAssistant(config.GEMINI_API_KEY, config.AI_MODEL_NAME, config.AI_SAFETY_SETTINGS)
        self.db_manager = DatabaseManager(config.DB_NAME)
        self.state_manager = CrawlingState(self.db_manager)
        self._last_action_target_coords: Optional[Tuple[int, int]] = None # Store coords for annotation

        # Failure counters
        self.consecutive_ai_failures = 0
        self.consecutive_map_failures = 0
        self.consecutive_exec_failures = 0


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


    def _get_current_state(self) -> Optional[Tuple[bytes, str]]:
        """Gets the current screenshot bytes and page source."""
        time.sleep(config.STABILITY_WAIT) # Wait for UI to settle
        screenshot_bytes = self.driver.get_screenshot_bytes()
        page_source = self.driver.get_page_source()

        if screenshot_bytes is None or page_source is None:
            logging.error("Failed to get current screen state (screenshot or XML).")
            return None
        return screenshot_bytes, page_source

        """Finds the best matching WebElement based on AI's text description."""
        if not description or not candidate_elements:
            return None

        logging.debug(f"Attempting to find element matching description: '{description}' among {len(candidate_elements)} candidates.")
        best_match_element = None
        highest_score = 0
        description_lower = description.lower()

        # Attributes to check for matching keywords
        attrs_to_check = ['text', 'content-desc', 'resource-id', 'hint']

        for element in candidate_elements:
            try:
                # Optimization: Skip elements clearly not visible/interactive?
                # if not element.is_displayed(): continue

                attrs = self.driver.get_element_attributes(element, attrs_to_check)
                current_score = 0

                # Score based on matches in key attributes
                text = attrs.get('text', '')
                desc = attrs.get('content-desc', '')
                rid = attrs.get('resource-id', '')
                hint = attrs.get('hint', '')

                # Prioritize exact/substring matches in primary text/desc
                if text and text.lower() in description_lower: current_score += 5
                elif desc and desc.lower() in description_lower: current_score += 5
                elif text and description_lower in text.lower(): current_score += 3 # Reverse match
                elif desc and description_lower in desc.lower(): current_score += 3

                # Check hints and resource IDs
                if hint and hint.lower() in description_lower: current_score += 2
                if rid and rid.split('/')[-1].lower() in description_lower: current_score += 1 # Match last part of RID

                # Boost score if keywords match (e.g., "button" description and Button class)
                # This requires getting the 'class' attribute as well
                # class_name = self.driver.get_element_attributes(element, ['class']).get('class', '')
                # if "button" in description_lower and "button" in class_name.lower(): current_score += 1
                # if "input" in description_lower and ("edittext" in class_name.lower() or "textfield" in class_name.lower()): current_score += 1

                # Check if this is the best match so far
                if current_score > highest_score:
                    highest_score = current_score
                    best_match_element = element
                    logging.debug(f"New best match found (Score: {highest_score}): Element attrs: {attrs}")

            except Exception as e:
                logging.warning(f"Error processing candidate element during mapping: {e}", exc_info=False)
                continue # Skip problematic element


        if best_match_element:
            logging.info(f"Mapped description '{description}' to element (Best Score: {highest_score}).")
            # You might want to log the attributes of the chosen element here for confirmation
        else:
            logging.warning(f"Could not find a suitable element matching description: '{description}'.")

        return best_match_element



    def _map_ai_to_action(self, ai_suggestion: dict) -> Optional[Tuple[str, Optional[Any], Optional[str]]]:
        """
        Maps the AI's JSON suggestion to an executable action tuple.
        Uses Bounding Box ONLY for clicks and to identify input field location.
        Stores target coordinates for annotation. NO LONGER USES DESCRIPTION MATCHING.
        Returns: (action_type, target_object_or_info, input_text_or_none)
        """
        action = ai_suggestion.get("action")
        target_desc = ai_suggestion.get("target_description") # Still useful for logging/history
        bbox = ai_suggestion.get("target_bounding_box") # CRITICAL for this approach
        logging.info(f"Raw BBox from AI: {bbox}")
        input_text = ai_suggestion.get("input_text")
        self._last_action_target_coords = None # Reset before mapping

        if not action:
            logging.error("AI suggestion missing 'action'. Cannot map.")
            return None

        # --- Actions requiring coordinates (Click, Input-Tap) ---
        if action in ["click", "input"]:
            if not bbox:
                logging.error(f"AI suggestion for '{action}' requires 'target_bounding_box', but it's missing or null. Cannot map.")
                return None # Mapping fails if no BBox

            try:
                # Validate coordinates (basic check for being within 0-1)
                tl_x, tl_y = bbox["top_left"]
                br_x, br_y = bbox["bottom_right"]
                if not all(0.0 <= coord <= 1.0 for coord in [tl_x, tl_y, br_x, br_y]):
                     raise ValueError(f"Normalized coordinates out of range (0-1): {bbox}")

                window_size = self.driver.get_window_size()
                if not window_size:
                    raise ValueError("Window size not available for BBox mapping") # Treat as mapping failure

                width = window_size['width']
                height = window_size['height']

                # Calculate absolute center coordinates for tapping
                center_x_norm = (tl_x + br_x) / 2
                center_y_norm = (tl_y + br_y) / 2
                abs_center_x = int(center_x_norm * width)
                abs_center_y = int(center_y_norm * height)

                # Store coordinates for annotation
                self._last_action_target_coords = (abs_center_x, abs_center_y)

                # Map to specific action types
                if action == "click":
                    logging.info(f"Mapping action '{action}' using BBox to coordinates: ({abs_center_x}, {abs_center_y})")
                    # Return 'tap_coords' action type
                    return ("tap_coords", (abs_center_x, abs_center_y), None)

                elif action == "input":
                    if input_text is None: # Should have text for input action
                         logging.warning(f"AI suggestion for 'input' action is missing 'input_text'. Using default.")
                         input_text = "default_text" # Or handle as error: return None

                    logging.info(f"Mapping action '{action}' using BBox tap at ({abs_center_x}, {abs_center_y}) and ADB text input.")
                    # Return a new action type 'input_by_keys'
                    # Target contains dict with coords for initial tap and text for ADB
                    target_info = {"coords": (abs_center_x, abs_center_y), "text": input_text}
                    return ("input_by_keys", target_info, None) # Text is part of target_info now

            except (KeyError, IndexError, TypeError, ValueError) as e:
                logging.error(f"Error processing bounding box {bbox} for action '{action}': {e}. Cannot map.")
                return None # Mapping fails

        # --- Actions NOT requiring coordinates/BBox ---
        elif action == "scroll_down":
             window_size = self.driver.get_window_size()
             if window_size: # Set coords for annotation if possible
                 self._last_action_target_coords = (window_size['width'] // 2, window_size['height'] // 2)
             return ("scroll", "down", None)
        elif action == "scroll_up":
             window_size = self.driver.get_window_size()
             if window_size: # Set coords for annotation if possible
                 self._last_action_target_coords = (window_size['width'] // 2, window_size['height'] // 2)
             return ("scroll", "up", None)
        elif action == "back":
             self._last_action_target_coords = None
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
        """Executes the mapped Appium action."""
        action_type, target, _ = mapped_action # Third element (text) is often None now or part of target
        success = False

        logging.info(f"Executing: {action_type.upper()} {'on/at '+str(target) if target else ''}")

        if action_type == "tap_coords" and isinstance(target, tuple) and len(target) == 2:
             # Target is the (x, y) tuple for simple taps (clicks)
             success = self.driver.tap_coordinates(target[0], target[1])

        # *** ADDED HANDLING for input_by_keys ***
        elif action_type == "input_by_keys" and isinstance(target, dict) and "coords" in target and "text" in target:
            coords = target["coords"]
            text_to_type = target["text"]
            logging.debug(f"Executing input_by_keys: Tap at {coords}, then type '{text_to_type}' via ADB.")

            # 1. Tap the coordinates first to focus the field
            tap_success = self.driver.tap_coordinates(coords[0], coords[1])
            if not tap_success:
                logging.error(f"Failed to tap coordinates {coords} before text input. Aborting input.")
                return False # Don't proceed if tap fails

            # 2. Wait briefly for keyboard to potentially appear/focus to settle
            time.sleep(0.7) # Small delay - adjust if needed

            # 3. Use the new driver method to type text via ADB
            type_success = self.driver.type_text_by_adb(text_to_type)
            success = type_success
            # Optional: Hide keyboard afterwards if needed
            if success:
                try:
                    if self.driver.is_keyboard_shown():
                        logging.debug("Hiding keyboard after input.")
                        self.driver.hide_keyboard()
                except Exception as kb_err:
                    logging.warning(f"Could not hide keyboard after input: {kb_err}")

        elif action_type == "scroll" and isinstance(target, str):
            # Target holds direction string "up" or "down"
            success = self.driver.scroll(direction=target)
        elif action_type == "back":
            success = self.driver.press_back_button()
        # Removed 'click' and 'input' cases that relied on WebElement target
        # elif action_type == "click" and isinstance(target, WebElement): ...
        # elif action_type == "input" and isinstance(target, WebElement): ...
        else:
            logging.error(f"Cannot execute unknown/invalid mapped action type: {action_type} with target: {target} (Type: {type(target)})")

        # Update failure counter based on overall success
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
        self.db_manager.connect() # Ensure DB is connected before state manager uses it

        # Initialize state manager *after* DB connection
        self.state_manager = CrawlingState(self.db_manager)

        if not self.driver.connect():
            logging.critical("Failed to establish Appium connection. Aborting.")
            self.db_manager.close()
            return

        current_screen_repr: Optional[ScreenRepresentation] = None
        previous_composite_hash: Optional[str] = None # Track previous state for transitions

        self._last_action_description: str = "START" # Initialize for potential first transition

        try:
            for step in range(config.MAX_CRAWL_STEPS):
                logging.info(f"\n--- Step {step + 1}/{config.MAX_CRAWL_STEPS} ---")

                if not self._ensure_in_app():
                    logging.critical("Cannot ensure app context. Stopping crawl.")
                    break # Stop the loop if we can't get back to the app

                # 1. Get Current State
                state_data = self._get_current_state()
                if state_data is None:
                    logging.warning("Failed to get current state, attempting back press...")
                    self.driver.press_back_button() # Try to recover
                    time.sleep(config.WAIT_AFTER_ACTION)
                    self._last_action_description = "GET_STATE_FAIL_FALLBACK_BACK" # Update description for next transition record
                    previous_composite_hash = None # Reset previous hash as state is uncertain
                    continue # Skip rest of this step

                screenshot_bytes, page_source = state_data # Keep original bytes
                xml_hash = utils.calculate_xml_hash(page_source)
                visual_hash = utils.calculate_visual_hash(screenshot_bytes)
                composite_hash = f"{xml_hash}_{visual_hash}"

                # 2. Add/Get Screen Representation & Save *Original* Screenshot
                current_screen_repr = self.state_manager.add_or_get_screen(
                    xml_hash, visual_hash, screenshot_bytes # Pass original bytes here
                )
                logging.info(f"Current Screen: ID={current_screen_repr.id}, Hash={composite_hash}")

                # 3. Record Transition (if not the first step)
                # Make sure previous_composite_hash is valid before recording
                if step > 0 and previous_composite_hash:
                     self.state_manager.add_transition(
                         previous_composite_hash,
                         self._last_action_description, # Description from previous step's action
                         composite_hash
                     )
                elif step == 0:
                     # Optionally record the entry point
                     # self.state_manager.add_transition("START", "LAUNCH", composite_hash)
                     pass


                # 4. Check Termination Conditions (before getting AI action)
                if self._check_termination(step + 1):
                    break

                # 5. Get Action History for Current Screen
                action_history = self.state_manager.get_action_history(composite_hash)
                logging.debug(f"Action history for screen {current_screen_repr.id} (Hash: {composite_hash}): {action_history}")

                # 6. Get AI Action Suggestion
                # Use config flag correctly
                xml_for_ai = utils.simplify_xml_for_ai(page_source, config.XML_SNIPPET_MAX_LEN) if getattr(config, 'ENABLE_XML_CONTEXT', True) else ""
                ai_suggestion = self.ai_assistant.get_next_action(
                    screenshot_bytes, xml_for_ai, action_history, config.AVAILABLE_ACTIONS
                )

                if ai_suggestion is None:
                    logging.error("AI failed to provide a suggestion.")
                    self.consecutive_ai_failures += 1
                    logging.info("Attempting fallback: Pressing BACK button.")
                    fallback_success = self.driver.press_back_button()
                    self._last_action_description = "AI_FAIL_FALLBACK_BACK" # Store description for next transition
                    if not fallback_success: self.consecutive_exec_failures += 1 # Count fallback failure too
                    time.sleep(config.WAIT_AFTER_ACTION)
                    previous_composite_hash = composite_hash # Update previous hash for next step
                    continue # Skip rest of this step
                else:
                    self.consecutive_ai_failures = 0
                    # Store description for next step's transition recording
                    action_type_sugg = ai_suggestion.get('action', 'UNKNOWN')
                    target_desc_sugg = ai_suggestion.get('target_description', 'N/A')
                    self._last_action_description = f"{action_type_sugg}: {target_desc_sugg}"


                # 7. Map AI Suggestion (This now also sets _last_action_target_coords)
                mapped_action = self._map_ai_to_action(ai_suggestion)

                if mapped_action is None:
                    logging.error("Failed to map AI suggestion to an executable action.")
                    self.consecutive_map_failures += 1
                    logging.info("Attempting fallback: Pressing BACK button.")
                    fallback_success = self.driver.press_back_button()
                    self._last_action_description += " (MAP_FAIL_FALLBACK_BACK)" # Update description
                    if not fallback_success: self.consecutive_exec_failures += 1
                    time.sleep(config.WAIT_AFTER_ACTION)
                    previous_composite_hash = composite_hash
                    continue # Skip rest of this step
                else:
                    self.consecutive_map_failures = 0
                    mapped_action_type = mapped_action[0]
                    if mapped_action_type == "click" and "tap_coords" not in self._last_action_description:
                        self._last_action_description = f"{action_type_sugg}: {target_desc_sugg} (Desc Lookup)"
                    elif mapped_action_type == "tap_coords":
                        self._last_action_description = f"{action_type_sugg}: {target_desc_sugg} (BBox Tap)"

                # 8. SAVE ANNOTATED SCREENSHOT (Before Execution)
                # Pass the original screenshot bytes captured at the start of the step
                self._save_annotated_screenshot(
                    original_screenshot_bytes=screenshot_bytes,
                    step=step + 1,
                    screen_id=current_screen_repr.id,
                    ai_suggestion=ai_suggestion
                )

                # 9. Execute Action
                execution_success = self._execute_action(mapped_action)
                # Failure counter updated inside _execute_action

                # 10. Wait for UI to potentially change
                time.sleep(config.WAIT_AFTER_ACTION)

                # 11. Update previous hash for the *next* loop iteration's transition recording
                previous_composite_hash = composite_hash

        except Exception as e:
            logging.critical(f"An uncaught exception occurred during crawling: {e}", exc_info=True)
        finally:
            # --- Cleanup ---
            logging.info("--- Crawling Finished ---")
            duration = time.time() - start_time
            logging.info(f"Total duration: {duration:.2f} seconds")
            logging.info(f"Discovered {self.state_manager.get_total_screens()} unique screen states.")
            logging.info(f"Recorded {self.state_manager.get_total_transitions()} transitions.")
            self.driver.disconnect()
            self.db_manager.close()
