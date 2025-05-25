import logging
from typing import Tuple, Optional, Any, Union, TYPE_CHECKING

from selenium.webdriver.remote.webelement import WebElement
# Import AppiumDriver if type hinting for self.driver is needed and it's not too complex
# from .appium_driver import AppiumDriver # Example

if TYPE_CHECKING:
    from .appium_driver import AppiumDriver

class ActionExecutor:
    """Handles the execution of mapped Appium actions."""

    def __init__(self, driver: 'AppiumDriver', config_dict: dict):
        self.driver = driver
        self.config_dict = config_dict

        # Verify required configuration values
        if 'MAX_CONSECUTIVE_EXEC_FAILURES' not in config_dict:
            raise ValueError("MAX_CONSECUTIVE_EXEC_FAILURES not configured")

        self.consecutive_exec_failures = 0  # Initialize to 0 but fail based on MAX_CONSECUTIVE_EXEC_FAILURES from config
        
    def execute_action(self, mapped_action: Tuple[str, Union[WebElement, dict[str, Any], str, None], Optional[str], Optional[str]]) -> bool:
        """Executes the mapped Appium action.
        Args:
            mapped_action: A 4-tuple containing (action_type, target_info, input_text, action_mode)
                where:
                - action_type: The type of action to perform (e.g., click, input, scroll)
                - target_info: WebElement for element actions, dict for coordinates, str for scroll direction, or None
                - input_text: Text to input for input actions, or None
                - action_mode: Special handling mode (e.g., "coordinate_action") or None
        Returns:
            bool: True if action was successful, False otherwise
        """
        if not isinstance(mapped_action, tuple) or len(mapped_action) != 4:
            logging.error(f"Invalid mapped_action: expected 4-tuple, got {type(mapped_action)}")
            return False
        
        action_type, target_info, input_text, action_mode = mapped_action

        success = False
        target_log_info = ""

        if action_mode == "coordinate_action" and isinstance(target_info, dict) and "coordinates" in target_info:
            coords = target_info["coordinates"]
            target_log_info = f"Coordinates: {coords}"
            logging.info(f"Executing coordinate-based: {action_type.upper()} at {target_log_info}")
            if action_type == "click":
                try:
                    center_x, center_y = coords
                    success = self.driver.tap_at_coordinates(center_x, center_y)
                except Exception as e:
                    logging.error(f"Exception during coordinate-based click at {coords}: {e}", exc_info=True)
                    success = False
            elif action_type == "input" and isinstance(input_text, str):
                try:
                    center_x, center_y = coords
                    logging.info(f"Attempting coordinate-based INPUT. Tapping at ({center_x}, {center_y}) to focus.")
                    tap_success = self.driver.tap_at_coordinates(center_x, center_y)
                    if tap_success:
                        logging.info(f"Tap successful for coordinate input. Attempting to send keys: '{input_text}'")
                        active_element = self.driver.get_active_element()
                        if active_element:
                            success = self.driver.input_text_into_element(active_element, input_text, click_first=False) # click_first=False as we already tapped
                            if not success:
                                logging.warning(f"Failed to send keys to active element after coordinate tap. Trying ADB fallback if configured.")
                                # Placeholder for potential ADB fallback in future
                        else:
                            logging.warning("No active element found after coordinate tap. Input via coordinates failed.")
                            success = False
                    else:
                        logging.warning(f"Tap failed for coordinate-based INPUT at ({center_x}, {center_y}). Cannot proceed with input.")
                        success = False
                except Exception as e:
                    logging.error(f"Exception during coordinate-based input at {coords} for text '{input_text}': {e}", exc_info=True)
                    success = False
            else:
                logging.error(f"Unknown coordinate-based action type: {action_type}")
                success = False

        elif isinstance(target_info, WebElement):
            try:
                target_log_info = f"Element (ID: {target_info.id})"
            except:
                target_log_info = "Element (Stale?)"
            logging.info(f"Executing element-based: {action_type.upper()} on {target_log_info}")
            try:
                if action_type == "click":
                    success = self.driver.click_element(target_info)
                elif action_type == "input" and isinstance(input_text, str):
                    success = self.driver.input_text_into_element(target_info, input_text)
                elif action_type == "scroll":
                    success = self.driver.scroll(direction=str(input_text), element=target_info)
                else:
                    logging.error(f"Cannot execute unknown element-based action type: {action_type} on {target_log_info}")
                    success = False
            except Exception as e:
                logging.error(f"Exception during element-based action ({action_type} on {target_log_info}): {e}", exc_info=True)
                success = False

        elif action_type == "scroll" and isinstance(target_info, str): # For scroll direction
            target_log_info = f"Direction: {target_info}"
            logging.info(f"Executing: {action_type.upper()} {target_log_info}")
            try:
                success = self.driver.scroll(direction=target_info)
            except Exception as e:
                logging.error(f"Exception during scroll action ({target_log_info}): {e}", exc_info=True)
                success = False
        elif action_type == "back" and target_info is None:
            logging.info(f"Executing: {action_type.upper()}")
            try:
                success = self.driver.press_back_button()
            except Exception as e:
                logging.error(f"Exception during back action: {e}", exc_info=True)
                success = False
        else:
            logging.error(f"Cannot execute unknown/invalid mapped action. Type: {action_type}, Target Info: {target_info} (Type: {type(target_info)}), Mode: {action_mode}")
            success = False

        if success:
            self.consecutive_exec_failures = 0
            logging.info(f"Action {action_type.upper()} successful.")
        else:
            self.consecutive_exec_failures += 1
            max_failures = self.config_dict['MAX_CONSECUTIVE_EXEC_FAILURES']
            logging.warning(f"Action {action_type.upper()} execution failed ({self.consecutive_exec_failures}/{max_failures} consecutive). Target: {target_log_info}")
        return success
