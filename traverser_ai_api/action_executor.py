# action_executor.py
import logging
import time
from typing import Tuple, Optional, Any, Union, TYPE_CHECKING, Dict # Added Dict

from selenium.webdriver.remote.webelement import WebElement

# Import your main Config class and AppiumDriver
# Adjust paths based on your project structure
if TYPE_CHECKING:
    from appium_driver import AppiumDriver # For type hinting
from config import Config # Assuming Config class is in config.py in the same package

class ActionExecutor:
    """Handles the execution of mapped Appium actions using a centralized Config object."""

    def __init__(self, driver: 'AppiumDriver', app_config: Config): # Changed signature
        """
        Initialize the ActionExecutor.

        Args:
            driver (AppiumDriver): An instance of the refactored AppiumDriver.
            app_config (Config): The main application Config object instance.
        """
        self.driver = driver
        self.cfg = app_config # Store the Config object instance

        # Verify required configuration values from self.cfg
        if not hasattr(self.cfg, 'MAX_CONSECUTIVE_EXEC_FAILURES') or self.cfg.MAX_CONSECUTIVE_EXEC_FAILURES is None:
            logging.warning("MAX_CONSECUTIVE_EXEC_FAILURES not in config, defaulting to 3.")
            self.max_exec_failures = 3
        else:
            self.max_exec_failures = int(self.cfg.MAX_CONSECUTIVE_EXEC_FAILURES)
        
        # For ADB input fallback
        self.use_adb_input_fallback = getattr(self.cfg, 'USE_ADB_INPUT_FALLBACK', False)

        self.consecutive_exec_failures = 0
        logging.info(f"ActionExecutor initialized. Max exec failures: {self.max_exec_failures}. ADB input fallback: {self.use_adb_input_fallback}")

    def execute_action(self, action_details: Dict[str, Any]) -> bool:
        """
        Executes the mapped Appium action.
        ActionMapper now returns a Dict.

        Args:
            action_details (Dict[str, Any]): A dictionary from ActionMapper, e.g.,
                {'type': 'click', 'element': WebElement, 'element_info': {...}}
                {'type': 'input', 'element': WebElement, 'text': '...', 'element_info': {...}}
                {'type': 'tap_coords', 'coordinates': (x,y), 'original_bbox': {...}, 'intended_input_text': '...'}
                {'type': 'scroll', 'direction': 'down'}
                {'type': 'back'}
        Returns:
            bool: True if action was successful, False otherwise.
        """
        if not isinstance(action_details, dict) or 'type' not in action_details:
            logging.error(f"Invalid action_details: expected dict with 'type' key, got {action_details}")
            self._track_failure("Invalid action details structure")
            return False
        
        action_type = action_details.get("type")
        element: Optional[WebElement] = action_details.get("element") # type: ignore
        target_info_dict: Optional[Dict[str, Any]] = action_details # For coordinate actions
        input_text: Optional[str] = action_details.get("text")
        scroll_direction: Optional[str] = action_details.get("direction")
        
        # For coordinate-based input, ActionMapper might add this
        intended_input_text_for_coord_tap: Optional[str] = action_details.get("intended_input_text")


        success = False
        action_log_info = f"Action Type: {action_type}"

        try:
            if action_type == "tap_coords":
                coordinates = action_details.get("coordinates")
                if isinstance(coordinates, tuple) and len(coordinates) == 2:
                    action_log_info += f", Coords: {coordinates}"
                    logging.info(f"Executing coordinate-based tap at {coordinates}")
                    success = self.driver.tap_at_coordinates(coordinates[0], coordinates[1])
                    if success and intended_input_text_for_coord_tap is not None:
                        logging.info(f"Coordinate tap successful. Now attempting to input text: '{intended_input_text_for_coord_tap}'")
                        time.sleep(0.5) # Brief pause for focus after tap
                        # Try sending to active element first, if any
                        active_el = self.driver.get_active_element()
                        input_via_active_el = False
                        if active_el:
                            logging.debug(f"Found active element (ID: {active_el.id}) after coord tap, attempting input.")
                            input_via_active_el = self.driver.input_text_into_element(active_el, intended_input_text_for_coord_tap, click_first=False, clear_first=True)
                        
                        if not input_via_active_el:
                            if self.use_adb_input_fallback:
                                logging.warning("Input to active element failed or no active element. Trying ADB input fallback.")
                                success = self.driver.type_text_by_adb(intended_input_text_for_coord_tap)
                            else:
                                logging.warning("Input to active element failed and ADB fallback disabled. Input part of coordinate action failed.")
                                success = False # Overall input action failed if text part fails
                        else:
                            success = True # Input to active element succeeded
                else:
                    logging.error(f"Invalid 'coordinates' for tap_coords: {coordinates}")
                    success = False

            elif action_type == "click":
                if isinstance(element, WebElement):
                    action_log_info += f", Element ID: {getattr(element, 'id', 'N/A')}"
                    success = self.driver.click_element(element)
                else:
                    logging.error(f"Invalid element for click action: {element}")
                    success = False
            
            elif action_type == "input":
                if isinstance(element, WebElement) and input_text is not None:
                    action_log_info += f", Element ID: {getattr(element, 'id', 'N/A')}, Text: '{input_text}'"
                    success = self.driver.input_text_into_element(element, input_text)
                elif not isinstance(element, WebElement):
                    logging.error(f"Invalid element for input action: {element}")
                    success = False
                else: # input_text is None
                    logging.warning(f"Input action called but input_text is None for Element ID: {getattr(element, 'id', 'N/A')}. Assuming clear or no-op.")
                    # Attempting to clear the element if input_text is None
                    if isinstance(element, WebElement):
                        try:
                            element.clear()
                            success = True
                            logging.info(f"Cleared element (ID: {getattr(element, 'id', 'N/A')}) as input_text was None.")
                        except Exception as e_clear:
                            logging.warning(f"Failed to clear element (ID: {getattr(element, 'id', 'N/A')}): {e_clear}")
                            success = False # Clearing failed
                    else:
                        success = False # No element to clear
            
            elif action_type == "scroll":
                if isinstance(scroll_direction, str):
                    action_log_info += f", Direction: {scroll_direction}"
                    success = self.driver.scroll(direction=scroll_direction) # element is optional in AppiumDriver.scroll
                else:
                    logging.error(f"Invalid direction for scroll action: {scroll_direction}")
                    success = False
            
            elif action_type == "back":
                success = self.driver.press_back_button()
            
            else:
                logging.error(f"Unknown action type for execution: {action_type}")
                success = False

        except Exception as e:
            logging.error(f"Exception during action execution ({action_log_info}): {e}", exc_info=True)
            success = False

        if success:
            self.consecutive_exec_failures = 0
            logging.info(f"Action execution successful: {action_log_info}")
        else:
            self._track_failure(f"Failed: {action_log_info}")
        
        return success

    def _track_failure(self, reason: str):
        """Tracks execution failures."""
        self.consecutive_exec_failures += 1
        logging.warning(
            f"Action execution failed: {reason}. Consecutive execution failures: "
            f"{self.consecutive_exec_failures}/{self.max_exec_failures}"
        )
        # Termination logic is handled by AppCrawler using this counter.