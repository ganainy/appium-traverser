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

    def _find_element_by_description(self, description: str, candidate_elements: List[WebElement]) -> Optional[WebElement]:
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
        Prioritizes Bounding Box for clicks, falls back to description matching.
        Stores target coordinates for annotation.
        Returns: (action_type, target_object_or_info, input_text)
        """
        action = ai_suggestion.get("action")
        target_desc = ai_suggestion.get("target_description")
        bbox = ai_suggestion.get("target_bounding_box") # Get bbox data
        input_text = ai_suggestion.get("input_text")
        self._last_action_target_coords = None # Reset before mapping

        if not action:
            logging.error("AI suggestion missing 'action'. Cannot map.")
            return None

        # --- Prioritize Bounding Box for CLICK actions ---
        if action == "click" and bbox:
            try:
                # Validate coordinates (basic check for being within 0-1)
                tl_x, tl_y = bbox["top_left"]
                br_x, br_y = bbox["bottom_right"]
                if not all(0.0 <= coord <= 1.0 for coord in [tl_x, tl_y, br_x, br_y]):
                     raise ValueError(f"Normalized coordinates out of range (0-1): {bbox}")

                window_size = self.driver.get_window_size()
                if not window_size:
                    logging.error("Cannot map bounding box: Failed to get window size.")
                    # Do not return None yet, fall through to description matching
                    raise ValueError("Window size not available for BBox mapping")


                width = window_size['width']
                height = window_size['height']

                # Calculate absolute center coordinates for tapping
                center_x_norm = (tl_x + br_x) / 2
                center_y_norm = (tl_y + br_y) / 2
                abs_center_x = int(center_x_norm * width)
                abs_center_y = int(center_y_norm * height)

                logging.info(f"Mapping action '{action}' using BBox to coordinates: ({abs_center_x}, {abs_center_y})")
                # *** STORE COORDINATES ***
                self._last_action_target_coords = (abs_center_x, abs_center_y)
                # Return a new action type 'tap_coords' with the target being the coordinate tuple
                return ("tap_coords", (abs_center_x, abs_center_y), None)

            except (KeyError, IndexError, TypeError, ValueError) as e:
                logging.warning(f"Error processing bounding box {bbox}: {e}. Falling back to description matching for '{action}'.")
                # Fall through to description matching

        # --- Fallback/Default: Use Description Matching (especially for INPUT) ---
        element: Optional[WebElement] = None # Ensure type hint
        if action in ["click", "input"]:
            # (If we reached here for 'click', it means bbox failed or wasn't provided/valid)
            if not target_desc:
                 # If click had no bbox AND no description, then error
                if action == 'click':
                     logging.error(f"AI suggestion for '{action}' missing 'target_description' and BBox failed/absent. Cannot map.")
                     return None
                # If input has no description, error
                elif action == 'input':
                     logging.error(f"AI suggestion for '{action}' missing 'target_description'. Cannot map.")
                     return None


            candidate_elements = self.driver.get_all_elements()
            if not candidate_elements:
                 logging.error("Could not retrieve any elements from the screen for description mapping.")
                 return None

            element = self._find_element_by_description(target_desc, candidate_elements)

            if not element:
                # No element found matching the description
                return None # Mapping failed

            # *** STORE ELEMENT CENTER COORDINATES ***
            # Store coords even if bbox mapping failed for click, use element center instead
            self._last_action_target_coords = self._get_element_center(element)

        # --- Return Mapped Action Tuples ---
        if action == "click":
            # If bbox failed, we mapped via description to an element
            return ("click", element, None)
        elif action == "input":
            # Input always needs the element, found via description
            final_input_text = input_text if input_text is not None else "default_text"
            # Storing coords already happened above when element was found
            return ("input", element, final_input_text)
        elif action == "scroll_down":
             # For scroll, indicate the center of the screen where scroll starts
             window_size = self.driver.get_window_size()
             if window_size:
                 self._last_action_target_coords = (window_size['width'] // 2, window_size['height'] // 2)
             return ("scroll", "down", None)
        elif action == "scroll_up":
             window_size = self.driver.get_window_size()
             if window_size:
                 self._last_action_target_coords = (window_size['width'] // 2, window_size['height'] // 2)
             return ("scroll", "up", None)
        elif action == "back":
             # No specific coords for back button press
             self._last_action_target_coords = None
             return ("back", None, None)
        else:
            logging.error(f"Unknown action type from AI: {action}")
            return None


    def _save_annotated_screenshot(self, original_screenshot_bytes: bytes, step: int, screen_id: int):
        """Takes the original screenshot, draws indicator, and saves it."""
        if not original_screenshot_bytes or self._last_action_target_coords is None:
            logging.debug("Skipping annotated screenshot: No original image or target coordinates.")
            return

        annotated_bytes = utils.draw_indicator_on_image(
            original_screenshot_bytes,
            self._last_action_target_coords
        )

        if annotated_bytes:
            try:
                annotated_dir = config.ANNOTATED_SCREENSHOTS_DIR
                os.makedirs(annotated_dir, exist_ok=True)
                # Use step and screen ID for clearer naming
                filename = f"annotated_step_{step}_screen_{screen_id}.png"
                filepath = os.path.join(annotated_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(annotated_bytes)
                logging.info(f"Saved annotated screenshot: {filepath} (Target: {self._last_action_target_coords})")
            except Exception as e:
                logging.error(f"Failed to save annotated screenshot {filepath}: {e}")
        else:
            logging.warning("Failed to generate annotated screenshot bytes.")



    def _execute_action(self, mapped_action: Tuple[str, Optional[object], Optional[str]]) -> bool:
        """Executes the mapped Appium action."""
        action_type, target, text = mapped_action
        success = False

        logging.info(f"Executing: {action_type.upper()} {'on '+str(target) if target else ''} {'with text \"'+text+'\"' if text else ''}")

        if action_type == "tap_coords" and isinstance(target, tuple) and len(target) == 2:
             # Target is the (x, y) tuple
             success = self.driver.tap_coordinates(target[0], target[1])
        elif action_type == "click" and isinstance(target, WebElement):
            success = self.driver.click_element(target)
        elif action_type == "input" and isinstance(target, WebElement):
            success = self.driver.input_text_into_element(target, text or "", click_first=True)
        elif action_type == "scroll":
            success = self.driver.scroll(direction=target) # Target holds direction string
        elif action_type == "back":
            success = self.driver.press_back_button()
        else:
            logging.error(f"Cannot execute unknown/invalid mapped action type: {action_type} with target type: {type(target)}")

        if success:
             self.consecutive_exec_failures = 0
        else:
             self.consecutive_exec_failures += 1
             logging.warning(f"Action execution failed ({self.consecutive_exec_failures} consecutive).")
        return success


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

                # 8. SAVE ANNOTATED SCREENSHOT (Before Execution)
                # Pass the original screenshot bytes captured at the start of the step
                self._save_annotated_screenshot(
                    original_screenshot_bytes=screenshot_bytes,
                    step=step + 1,
                    screen_id=current_screen_repr.id
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
