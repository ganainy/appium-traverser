import logging
from typing import Tuple, Optional, Any, TYPE_CHECKING

from selenium.webdriver.remote.webelement import WebElement
# Import AppiumDriver if type hinting for self.driver is needed and it's not too complex
# from .appium_driver import AppiumDriver # Example

if TYPE_CHECKING:
    from .appium_driver import AppiumDriver

class ActionExecutor:
    """Handles the execution of mapped Appium actions."""

    def __init__(self, driver: 'AppiumDriver', config_dict: dict):
        self.driver = driver
        self.config_dict = config_dict # May be used for action-specific configs in future
        self.consecutive_exec_failures = 0

    def execute_action(self, mapped_action: Tuple[str, Optional[Any], Optional[str]]) -> bool:
        """Executes the mapped Appium action."""
        action_type, target, input_text = mapped_action
        success = False

        target_log_info = ""
        if isinstance(target, WebElement):
            try:
                target_log_info = f"Element (ID: {target.id})"
            except: # Handles potential StaleElementReferenceException if ID is accessed too late
                target_log_info = "Element (Stale?)"
        elif isinstance(target, str):  # For scroll direction
            target_log_info = f"Direction: {target}"
        
        logging.info(f"Executing: {action_type.upper()} {target_log_info}")

        try:
            if action_type == "click" and isinstance(target, WebElement):
                success = self.driver.click_element(target)
            elif action_type == "input" and isinstance(target, WebElement) and isinstance(input_text, str):
                success = self.driver.input_text_into_element(target, input_text)
            elif action_type == "scroll" and isinstance(target, str):
                success = self.driver.scroll(direction=target)
            elif action_type == "back" and target is None:
                success = self.driver.press_back_button()
            else:
                logging.error(f"Cannot execute unknown/invalid mapped action type or target combination: {action_type} with target: {target_log_info} (Type: {type(target)})Input: {input_text}")
                success = False # Explicitly false for unknown actions

        except Exception as e:
            logging.error(f"Exception during action execution ({action_type} on {target_log_info}): {e}", exc_info=True)
            success = False

        if success:
            self.consecutive_exec_failures = 0
            logging.info(f"Action {action_type.upper()} successful.")
        else:
            self.consecutive_exec_failures += 1
            logging.warning(f"Action {action_type.upper()} execution failed ({self.consecutive_exec_failures} consecutive). Target: {target_log_info}")
        return success
