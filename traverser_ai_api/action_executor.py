import logging
import time
from typing import Tuple, Optional, Any, Union, TYPE_CHECKING, Dict

from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import StaleElementReferenceException # Added for explicit handling

if TYPE_CHECKING:
    from appium_driver import AppiumDriver
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
        
        self.use_adb_input_fallback = getattr(self.cfg, 'USE_ADB_INPUT_FALLBACK', False)

        self.consecutive_exec_failures = 0
        self.last_error_message: Optional[str] = None # Added attribute
        logging.info(f"ActionExecutor initialized. Max exec failures: {self.max_exec_failures}. ADB input fallback: {self.use_adb_input_fallback}")

    def reset_consecutive_failures(self): # Added method
        """Resets the consecutive execution failure counter."""
        if self.consecutive_exec_failures > 0: # Only log if there were failures
            logging.debug(f"Resetting consecutive execution failures from {self.consecutive_exec_failures} to 0.")
        self.consecutive_exec_failures = 0
        self.last_error_message = None

    def execute_action(self, action_details: Dict[str, Any]) -> bool:
        if not isinstance(action_details, dict) or 'type' not in action_details:
            error_msg = f"Invalid action_details: expected dict with 'type' key, got {action_details}"
            logging.error(error_msg)
            self._track_failure(error_msg)
            return False
        
        action_type = action_details.get("type")
        element: Optional[WebElement] = action_details.get("element")
        input_text: Optional[str] = action_details.get("text")
        scroll_direction: Optional[str] = action_details.get("direction")
        intended_input_text_for_coord_tap: Optional[str] = action_details.get("intended_input_text")
        
        success = False
        action_log_info = f"Action Type: {action_type}"
        current_error_msg = None # For this specific execution attempt

        try:
            if action_type == "tap_coords":
                coordinates = action_details.get("coordinates")
                if isinstance(coordinates, tuple) and len(coordinates) == 2:
                    action_log_info += f", Coords: {coordinates}"
                    logging.info(f"Executing coordinate-based tap at {coordinates}")
                    success = self.driver.tap_at_coordinates(coordinates[0], coordinates[1])
                    if success and intended_input_text_for_coord_tap is not None:
                        logging.info(f"Coordinate tap successful. Now attempting to input text: '{intended_input_text_for_coord_tap}'")
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

            elif action_type == "click":
                if isinstance(element, WebElement):
                    action_log_info += f", Element ID: {getattr(element, 'id', 'N/A')}"
                    success = self.driver.click_element(element)
                    if not success: current_error_msg = f"Click on element (ID: {getattr(element, 'id', 'N/A')}) failed."
                else:
                    current_error_msg = f"Invalid element for click action: {element}"
                    logging.error(current_error_msg)
                    success = False
            
            elif action_type == "input":
                if isinstance(element, WebElement) and input_text is not None:
                    action_log_info += f", Element ID: {getattr(element, 'id', 'N/A')}, Text: '{input_text}'"
                    success = self.driver.input_text_into_element(element, input_text)
                    if not success: current_error_msg = f"Input text into element (ID: {getattr(element, 'id', 'N/A')}) failed."
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
                            logging.info(f"Cleared element (ID: {getattr(element, 'id', 'N/A')}) as input_text was None.")
                        except Exception as e_clear:
                            current_error_msg = f"Failed to clear element (ID: {getattr(element, 'id', 'N/A')}): {e_clear}"
                            logging.warning(current_error_msg)
                            success = False
                    else: # Should not happen due to outer check, but defensive
                        current_error_msg = "No valid element to clear when input_text was None."
                        success = False 
            
            elif action_type == "scroll":
                if isinstance(scroll_direction, str):
                    action_log_info += f", Direction: {scroll_direction}"
                    success = self.driver.scroll(direction=scroll_direction)
                    if not success: current_error_msg = f"Scroll action in direction '{scroll_direction}' failed."
                else:
                    current_error_msg = f"Invalid direction for scroll action: {scroll_direction}"
                    logging.error(current_error_msg)
                    success = False
            
            elif action_type == "back":
                success = self.driver.press_back_button()
                if not success: current_error_msg = "Press back button action failed."
            
            else:
                current_error_msg = f"Unknown action type for execution: {action_type}"
                logging.error(current_error_msg)
                success = False

        except StaleElementReferenceException as e_stale:
            current_error_msg = f"StaleElementReferenceException during action execution ({action_log_info}): {e_stale}"
            logging.error(current_error_msg, exc_info=True) # Keep exc_info for stale elements as it's common
            success = False
        except Exception as e:
            current_error_msg = f"Exception during action execution ({action_log_info}): {e}"
            logging.error(current_error_msg, exc_info=True)
            success = False

        if success:
            self.reset_consecutive_failures() # Use the new method
            logging.info(f"Action execution successful: {action_log_info}")
        else:
            self._track_failure(current_error_msg or f"Unknown failure: {action_log_info}")
        
        return success

    def _track_failure(self, reason: str):
        self.consecutive_exec_failures += 1
        self.last_error_message = reason # Store the reason for this failure
        logging.warning(
            f"Action execution failed: {reason}. Consecutive execution failures: "
            f"{self.consecutive_exec_failures}/{self.max_exec_failures}"
        )