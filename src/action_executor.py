import logging
import re
import time
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

from selenium.common.exceptions import StaleElementReferenceException  # Added for explicit handling
from selenium.webdriver.remote.webelement import WebElement

if TYPE_CHECKING:
    from appium_driver import AppiumDriver
try:
    from traverser_ai_api.config import Config
except ImportError:
    from config import Config

class ActionExecutor:
    def __init__(self, driver: 'AppiumDriver', app_config: Config):
        self.driver = driver
        self.cfg = app_config

        if not hasattr(self.cfg, 'MAX_CONSECUTIVE_EXEC_FAILURES') or self.cfg.MAX_CONSECUTIVE_EXEC_FAILURES is None:
            logging.warning("MAX_CONSECUTIVE_EXEC_FAILURES not in config, defaulting to 3.")
            self.max_exec_failures = 3
        else:
            self.max_exec_failures = int(self.cfg.MAX_CONSECUTIVE_EXEC_FAILURES)

        use_adb_input_fallback = getattr(self.cfg, 'USE_ADB_INPUT_FALLBACK', None)
        if use_adb_input_fallback is None:
            logging.warning("USE_ADB_INPUT_FALLBACK not in config, defaulting to True.")
            self.use_adb_input_fallback = True
        else:
            self.use_adb_input_fallback = bool(use_adb_input_fallback)

        self.consecutive_exec_failures = 0
        self.last_error_message: Optional[str] = None # Added attribute
        logging.debug(f"ActionExecutor initialized. Max exec failures: {self.max_exec_failures}. ADB input fallback: {self.use_adb_input_fallback}")

    def reset_consecutive_failures(self): # Added method
        """Resets the consecutive execution failure counter."""
        if self.consecutive_exec_failures > 0: # Only log if there were failures
            logging.debug(f"Resetting consecutive execution failures from {self.consecutive_exec_failures} to 0.")
        self.consecutive_exec_failures = 0
        self.last_error_message = None

    def execute_action(self, action_details: Dict[str, Any]) -> bool:
        # Avoid interacting under transient overlays (e.g., Toast). Wait briefly if detected.
        try:
            if self.driver:
                self.driver.wait_for_toast_to_dismiss(getattr(self.cfg, 'TOAST_DISMISS_WAIT_MS', 1200))
        except Exception:
            # Non-fatal; proceed even if toast detection fails
            pass

        # Hide software keyboard before non-input actions to reduce overlay-related no-ops
        try:
            if bool(getattr(self.cfg, 'AUTO_HIDE_KEYBOARD_BEFORE_NON_INPUT', True)):
                action_type_preview = action_details.get('type') if isinstance(action_details, dict) else None
                # Only hide keyboard if we're not about to input text
                if action_type_preview not in ["input"] and self.driver and self.driver.is_keyboard_shown():
                    logging.debug("Software keyboard is shown before non-input action. Hiding keyboard.")
                    self.driver.hide_keyboard()
                    time.sleep(0.2)
        except Exception:
            # Non-fatal; proceed even if keyboard detection/hide fails
            pass
        # Add validation at the start
        if action_details.get('type') == 'tap_coords':
            coordinates = action_details.get('coordinates')
            if not coordinates or not isinstance(coordinates, tuple) or len(coordinates) != 2:
                logging.error(f"Invalid coordinates for tap_coords: {coordinates}")
                self._track_failure("Invalid coordinates format")
                return False
                
            x, y = coordinates
            if not all(isinstance(coord, int) for coord in [x, y]):
                logging.error(f"Non-integer coordinates: {coordinates}")
                self._track_failure("Non-integer coordinates")
                return False
                
            # Additional bounds checking
            if x < 0 or y < 0 or x > 5000 or y > 5000:  # Reasonable upper bounds
                logging.error(f"Coordinates out of reasonable bounds: {coordinates}")
                self._track_failure("Coordinates out of bounds")
                return False

        if not isinstance(action_details, dict) or 'type' not in action_details:
            error_msg = f"Invalid action_details: expected dict with 'type' key, got {action_details}"
            logging.error(error_msg)
            self._track_failure(error_msg)
            return False

        action_type = action_details.get("type")
        element: Optional[WebElement] = action_details.get("element")
        input_text: Optional[str] = action_details.get("text")
        intended_input_text_for_coord_tap: Optional[str] = action_details.get("intended_input_text")

        # Normalize scroll/swipe actions to a generic "scroll_or_swipe" action type
        direction_from_type: Optional[str] = None
        # NEW: Added swipe_left and swipe_right to the list of recognized actions
        if action_type in ["scroll_down", "scroll_up", "swipe_left", "swipe_right"]:
            direction_from_type = action_type.split("_")[-1] # e.g., "down" from "scroll_down", "left" from "swipe_left"
            internal_action = "scroll_or_swipe"
        else:
            internal_action = action_type

        success = False
        action_log_info = f"Action Type: {action_details.get('type')}" # Log original action type
        current_error_msg = None # For this specific execution attempt

        try:
            if internal_action == "tap_coords":
                coordinates = action_details.get("coordinates")
                if isinstance(coordinates, tuple) and len(coordinates) == 2:
                    action_log_info += f", Coords: {coordinates}"
                    logging.debug(f"Executing coordinate-based tap at {coordinates}")
                    # Support optional duration for long-press semantics
                    duration_ms = None
                    try:
                        if isinstance(action_details.get("duration_ms"), (int, float)):
                            duration_ms = int(action_details.get("duration_ms"))
                    except Exception:
                        duration_ms = None
                    success = self.driver.tap_at_coordinates(coordinates[0], coordinates[1], duration=duration_ms)
                    if success and intended_input_text_for_coord_tap is not None:
                        logging.debug(f"Coordinate tap successful. Now attempting to input text: '{intended_input_text_for_coord_tap}'")
                        time.sleep(0.5)
                        active_el = self.driver.get_active_element()
                        input_via_active_el = False
                        if active_el:
                            logging.debug(f"Found active element (ID: {active_el.id}) after coord tap, attempting input.")
                            input_via_active_el = self.driver.input_text_into_element(active_el, intended_input_text_for_coord_tap, click_first=False, clear_first=True)

                        if not input_via_active_el:
                            if self.use_adb_input_fallback:
                                logging.warning("Input to active element failed or no active element. Trying ADB input fallback.")
                                success = self.driver.type_text_by_adb(intended_input_text_for_coord_tap)
                                if not success: current_error_msg = "ADB input fallback failed after coordinate tap."
                            else:
                                current_error_msg = "Input to active element failed and ADB fallback disabled after coordinate tap."
                                logging.warning(current_error_msg)
                                success = False
                        else: # input via active_el succeeded
                            success = True
                else:
                    current_error_msg = f"Invalid 'coordinates' for tap_coords: {coordinates}"
                    logging.error(current_error_msg)
                    success = False

            elif internal_action == "click":
                if isinstance(element, WebElement):
                    action_log_info += f", Element ID: {getattr(element, 'id', 'N/A')}"
                    success = self.driver.click_element(element)
                    if not success:
                        logging.warning(f"Standard click failed for element ID {getattr(element, 'id', 'N/A')}. Attempting tap fallback.")
                        success = self.driver.tap_element_center(element)
                        if not success:
                            # Bounds-based coordinate fallback when element became stale
                            element_info: Dict[str, Any] = action_details.get("element_info", {}) if isinstance(action_details.get("element_info"), dict) else {}
                            bounds_str: Optional[str] = element_info.get("bounds")
                            center_from_bounds: Optional[Tuple[int, int]] = None
                            if isinstance(bounds_str, str):
                                try:
                                    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
                                    if m:
                                        x1, y1, x2, y2 = map(int, m.groups())
                                        center_from_bounds = (int((x1 + x2) / 2), int((y1 + y2) / 2))
                                except Exception:
                                    center_from_bounds = None
                            if center_from_bounds:
                                logging.info(f"Using bounds-based fallback tap at {center_from_bounds} for element ID {getattr(element, 'id', 'N/A')}")
                                success = self.driver.tap_at_coordinates(center_from_bounds[0], center_from_bounds[1])
                            # If bounds not available or failed, try original_bbox from mapping
                            if not success:
                                original_bbox = action_details.get("original_bbox")
                                if isinstance(original_bbox, dict):
                                    center_from_bbox = self._compute_center_from_bbox(original_bbox)
                                    if center_from_bbox:
                                        logging.info(f"Using bbox-based fallback tap at {center_from_bbox} for element ID {getattr(element, 'id', 'N/A')}")
                                        success = self.driver.tap_at_coordinates(center_from_bbox[0], center_from_bbox[1])
                            if not success:
                                current_error_msg = f"Click and all fallbacks failed for element (ID: {getattr(element, 'id', 'N/A')})."
                else:
                    current_error_msg = f"Invalid element for click action: {element}"
                    logging.error(current_error_msg)
                    success = False

            elif internal_action == "input":
                if isinstance(element, WebElement) and input_text is not None:
                    action_log_info += f", Element ID: {getattr(element, 'id', 'N/A')}, Text: '{input_text}'"
                    # Initial attempt with standard Appium command
                    success = self.driver.input_text_into_element(element, input_text)

                    # NEW: ADB input fallback logic
                    if not success and self.use_adb_input_fallback:
                        logging.warning(f"Standard input failed for element (ID: {getattr(element, 'id', 'N/A')}). Attempting ADB fallback.")
                        # Re-click to ensure focus before global ADB typing
                        self.driver.click_element(element)
                        time.sleep(0.5) # Allow time for keyboard/focus
                        adb_success = self.driver.type_text_by_adb(input_text)
                        if adb_success:
                            logging.debug("ADB input fallback succeeded.")
                            success = True
                        else:
                            current_error_msg = f"Standard and ADB input fallbacks failed for element (ID: {getattr(element, 'id', 'N/A')})."
                    elif not success:
                        current_error_msg = f"Input text into element (ID: {getattr(element, 'id', 'N/A')}) failed and ADB fallback is disabled."

                elif not isinstance(element, WebElement):
                    current_error_msg = f"Invalid element for input action: {element}"
                    logging.error(current_error_msg)
                    success = False
                else: # input_text is None
                    action_log_info += f", Element ID: {getattr(element, 'id', 'N/A')}, Action: Clear (input_text was None)"
                    logging.warning(f"Input action called but input_text is None for Element ID: {getattr(element, 'id', 'N/A')}. Attempting to clear.")
                    if isinstance(element, WebElement):
                        try:
                            element.clear()
                            success = True
                            logging.debug(f"Cleared element (ID: {getattr(element, 'id', 'N/A')}) as input_text was None.")
                        except Exception as e_clear:
                            current_error_msg = f"Failed to clear element (ID: {getattr(element, 'id', 'N/A')}): {e_clear}"
                            logging.warning(current_error_msg)
                            success = False
                    else:
                        current_error_msg = "No valid element to clear when input_text was None."
                        success = False

            # NEW: This block now handles all scroll and swipe directions
            elif internal_action == "scroll_or_swipe":
                if isinstance(direction_from_type, str):
                    action_log_info += f", Direction: {direction_from_type}"
                    # Prefer targeted element if provided
                    target_el = action_details.get("element")
                    if target_el:
                        action_log_info += f", Targeted Element ID: {getattr(target_el, 'id', 'N/A')}"
                        success = self.driver.scroll(direction=direction_from_type, element=target_el)
                    else:
                        # If bbox provided, compute region-based swipe within bbox
                        bbox = action_details.get("original_bbox")
                        if isinstance(bbox, (dict, str)):
                            coords = self._compute_bbox_swipe_coords(bbox, direction_from_type)
                            if coords:
                                sx, sy, ex, ey = coords
                                success = self.driver.swipe_points(sx, sy, ex, ey, duration_ms=400)
                            else:
                                # Fallback to full-screen gesture if bbox invalid
                                success = self.driver.scroll(direction=direction_from_type)
                        else:
                            success = self.driver.scroll(direction=direction_from_type)
                    if not success:
                        current_error_msg = f"Scroll/Swipe action in direction '{direction_from_type}' failed."
                else:
                    current_error_msg = f"Invalid direction for scroll/swipe action: {direction_from_type}"
                    logging.error(current_error_msg)
                    success = False

            elif internal_action == "back":
                success = self.driver.press_back_button()
                if not success: current_error_msg = "Press back button action failed."

            else:
                current_error_msg = f"Unknown action type for execution: {action_type}"
                logging.error(current_error_msg)
                success = False

        except StaleElementReferenceException as e_stale:
            current_error_msg = f"StaleElementReferenceException during action execution ({action_log_info}): {e_stale}"
            logging.error(current_error_msg, exc_info=True)
            success = False
        except Exception as e:
            current_error_msg = f"Exception during action execution ({action_log_info}): {e}"
            logging.error(current_error_msg, exc_info=True)
            success = False

        if success:
            self.reset_consecutive_failures()
            logging.debug(f"Action execution successful: {action_log_info}")
        else:
            self._track_failure(current_error_msg or f"Unknown failure: {action_log_info}")

        return success

    def _compute_bbox_swipe_coords(self, bbox: Any, direction: str) -> Optional[Tuple[int, int, int, int]]:
        """Compute start/end coordinates for a directional swipe within a given bbox.

        bbox may be a dict with top_left/bottom_right (normalized or absolute) or an Android bounds string.
        """
        try:
            window_size = self.driver.get_window_size()
            if not window_size:
                return None
            screen_width, screen_height = window_size['width'], window_size['height']

            # Parse bbox into absolute x1,y1,x2,y2
            x1 = y1 = x2 = y2 = None
            if isinstance(bbox, str):
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bbox.strip())
                if not m:
                    return None
                x1, y1, x2, y2 = map(int, m.groups())
            elif isinstance(bbox, dict):
                tl = bbox.get('top_left')
                br = bbox.get('bottom_right')
                if not (isinstance(tl, list) and isinstance(br, list) and len(tl) == 2 and len(br) == 2):
                    return None
                y1_norm, x1_norm = tl
                y2_norm, x2_norm = br
                if all(isinstance(v, (int, float)) for v in [y1_norm, x1_norm, y2_norm, x2_norm]):
                    if all(float(v) <= 1.0 for v in [y1_norm, x1_norm, y2_norm, x2_norm]):
                        x1 = int(float(x1_norm) * screen_width)
                        y1 = int(float(y1_norm) * screen_height)
                        x2 = int(float(x2_norm) * screen_width)
                        y2 = int(float(y2_norm) * screen_height)
                    else:
                        x1, y1, x2, y2 = int(x1_norm), int(y1_norm), int(x2_norm), int(y2_norm)
            else:
                return None

            # Sanity and clamp
            if x1 is None or y1 is None or x2 is None or y2 is None:
                return None
            x1 = max(0, min(x1, screen_width - 1)); x2 = max(0, min(x2, screen_width - 1))
            y1 = max(0, min(y1, screen_height - 1)); y2 = max(0, min(y2, screen_height - 1))
            if x1 > x2: x1, x2 = x2, x1
            if y1 > y2: y1, y2 = y2, y1

            center_y = int((y1 + y2) / 2)
            center_x = int((x1 + x2) / 2)
            # Use 20% inset from edges to reduce accidental edge gestures
            inset_x = int((x2 - x1) * 0.2)
            inset_y = int((y2 - y1) * 0.2)
            left_x = x1 + inset_x
            right_x = x2 - inset_x
            top_y = y1 + inset_y
            bottom_y = y2 - inset_y

            if direction == "left":
                return right_x, center_y, left_x, center_y
            elif direction == "right":
                return left_x, center_y, right_x, center_y
            elif direction == "up":
                return center_x, top_y, center_x, bottom_y
            elif direction == "down":
                return center_x, bottom_y, center_x, top_y
            else:
                return None
        except Exception:
            return None

    def _compute_center_from_bbox(self, bbox: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        """Compute center coordinates from a bbox dict that may contain normalized or absolute coordinates."""
        try:
            top_left = bbox.get('top_left')
            bottom_right = bbox.get('bottom_right')
            if not (isinstance(top_left, list) and isinstance(bottom_right, list) and len(top_left) == 2 and len(bottom_right) == 2):
                return None
            y1_norm, x1_norm = top_left
            y2_norm, x2_norm = bottom_right
            if not all(isinstance(v, (int, float)) for v in [y1_norm, x1_norm, y2_norm, x2_norm]):
                return None
            window_size = self.driver.get_window_size()
            if not window_size:
                return None
            screen_width, screen_height = window_size['width'], window_size['height']
            # Determine if normalized
            if all(float(v) <= 1.0 for v in [y1_norm, x1_norm, y2_norm, x2_norm]):
                x1 = int(float(x1_norm) * screen_width)
                y1 = int(float(y1_norm) * screen_height)
                x2 = int(float(x2_norm) * screen_width)
                y2 = int(float(y2_norm) * screen_height)
            else:
                x1, y1, x2, y2 = int(x1_norm), int(y1_norm), int(x2_norm), int(y2_norm)
            if x1 > x2: x1, x2 = x2, x1
            if y1 > y2: y1, y2 = y2, y1
            return int((x1 + x2) / 2), int((y1 + y2) / 2)
        except Exception:
            return None

    def _track_failure(self, reason: str):
        self.consecutive_exec_failures += 1
        self.last_error_message = reason
        logging.warning(
            f"Action execution failed: {reason}. Consecutive execution failures: "
            f"{self.consecutive_exec_failures}/{self.max_exec_failures}"
        )
