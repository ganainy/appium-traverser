import logging
import time
from typing import Optional, Tuple, Any, List, Dict
from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, InvalidSelectorException

# Assuming AppiumDriver is in appium_driver.py and has a find_element and find_elements method
# from .appium_driver import AppiumDriver # This will be used if ActionMapper takes an AppiumDriver instance

class ActionMapper:
    def __init__(self, driver, element_finding_strategies, config_dict: dict): # driver is an instance of AppiumDriver
        self.driver = driver
        self.element_finding_strategies = element_finding_strategies
        
        # Validate required configuration values
        if 'USE_COORDINATE_FALLBACK' not in config_dict:
            raise ValueError("USE_COORDINATE_FALLBACK is required in configuration")
        if 'MAX_CONSECUTIVE_MAP_FAILURES' not in config_dict:
            raise ValueError("MAX_CONSECUTIVE_MAP_FAILURES not configured")
            
        self.use_coordinate_fallback = config_dict['USE_COORDINATE_FALLBACK']
        self.consecutive_map_failures = 0  # Initialize to 0 but fail based on config
        self.config_dict = config_dict
        
        logging.info(f"ActionMapper initialized. Coordinate fallback is {'ENABLED' if self.use_coordinate_fallback else 'DISABLED'}.")

    def _find_element_by_ai_identifier(self, identifier: str) -> Optional[WebElement]:
        """
        Attempts to find a WebElement using the identifier provided by the AI,
        trying different strategies in a dynamically prioritized order.
        Promotes successful strategies and returns immediately upon finding a suitable element.
        """
        if not identifier or not self.driver or not self.driver.driver: # self.driver.driver refers to the actual appium webdriver
            logging.warning("Cannot find element: Invalid identifier or driver not available.")
            return None

        logging.info(f"Attempting to find element using identifier: '{identifier}'")
        total_start_time = time.perf_counter()

        for index, (strategy_key, appium_by, log_name) in enumerate(self.element_finding_strategies):
            element: Optional[WebElement] = None
            start_time = time.perf_counter()
            xpath_generated = ""

            try:
                if strategy_key in ['id', 'acc_id']:
                    logging.debug(f"Trying {log_name}: '{identifier}'")
                    element = self.driver.find_element(appium_by, identifier)
                elif strategy_key == 'xpath_exact':
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
                    logging.debug(f"Trying {log_name} (Quote Safe): {xpath_generated}")
                    element = self.driver.find_element(AppiumBy.XPATH, xpath_generated)
                elif strategy_key == 'xpath_contains':
                    if "'" in identifier: xpath_safe_identifier = f'"{identifier}"'
                    else: xpath_safe_identifier = f"'{identifier}'"
                    xpath_generated = (f"//*[contains(@text, {xpath_safe_identifier}) or "
                                       f"contains(@content-desc, {xpath_safe_identifier}) or "
                                       f"contains(@resource-id, {xpath_safe_identifier})]")
                    logging.debug(f"Trying {log_name} (Basic Quote Handling): {xpath_generated}")
                    possible_elements = self.driver.driver.find_elements(AppiumBy.XPATH, xpath_generated) # Access raw driver for find_elements
                    found_count = len(possible_elements)
                    logging.debug(f"Found {found_count} potential elements via '{log_name}' XPath.")
                    for el in possible_elements:
                        try:
                            if el.is_displayed() and el.is_enabled():
                                element = el
                                break
                        except Exception: continue
                    if not element:
                         logging.debug(f"No suitable element found by '{log_name}' XPath after filtering.")

                duration = time.perf_counter() - start_time

                if element and element.is_displayed() and element.is_enabled():
                    logging.info(f"Found element by {log_name}: '{identifier}' (took {duration:.4f}s)")
                    if index > 0:
                        promoted_strategy = self.element_finding_strategies.pop(index)
                        self.element_finding_strategies.insert(0, promoted_strategy)
                        logging.info(f"Promoted strategy '{log_name}' to the front. New order: {[s[2] for s in self.element_finding_strategies]}")
                    return element
                elif element:
                    logging.debug(f"Element found by {log_name} but not displayed/enabled (took {duration:.4f}s).")
            except NoSuchElementException:
                duration = time.perf_counter() - start_time
                logging.debug(f"Not found by {log_name} (took {duration:.4f}s).")
            except InvalidSelectorException as e:
                duration = time.perf_counter() - start_time
                logging.warning(f"Invalid Selector Exception finding by {log_name} '{identifier}' (XPath: {xpath_generated}). Error: {e} (took {duration:.4f}s)")
            except Exception as e:
                duration = time.perf_counter() - start_time
                logging.warning(f"Error finding by {log_name} '{identifier}' (took {duration:.4f}s): {e}")

        total_duration = time.perf_counter() - total_start_time
        logging.warning(f"Could not find suitable element using identifier '{identifier}' with any strategy (total search time {total_duration:.4f}s). Current strategy order: {[s[2] for s in self.element_finding_strategies]}")
        return None    
    
    def _track_map_failure(self, reason: str) -> None:
        """Helper method to track and log mapping failures."""
        self.consecutive_map_failures += 1
        max_failures = self.config_dict['MAX_CONSECUTIVE_MAP_FAILURES']
        logging.warning(f"Action mapping failed ({self.consecutive_map_failures}/{max_failures} consecutive): {reason}")
        return None

    def map_ai_to_action(self, ai_suggestion: dict) -> Optional[Tuple[str, Any, Optional[str], Optional[str]]]:
        """
        Maps the AI's JSON suggestion (using 'target_identifier' or 'target_bounding_box')
        to an executable action tuple.
        Returns: (action_type, target_object_or_info, input_text_or_none, action_mode_or_none)
                where:
                - action_type: The type of action to perform (click, input, scroll, back)
                - target_object_or_info: WebElement for click/input, string for scroll,
                                    or dict with coordinates for coordinate-based actions
                - input_text_or_none: Text to input for input actions, None otherwise
                - action_mode_or_none: "coordinate_action" for coordinate-based actions, None otherwise
        """
        action = ai_suggestion.get("action")
        target_identifier = ai_suggestion.get("target_identifier")
        input_text = ai_suggestion.get("input_text")
        target_bounding_box = ai_suggestion.get("target_bounding_box")

        logging.info(f"Attempting to map AI suggestion: Action='{action}', Identifier='{target_identifier}', Input='{input_text}', BBox='{target_bounding_box}'")

        if action not in ["click", "input", "scroll_down", "scroll_up", "back"]:
            logging.error(f"Unknown action type from AI: {action}")
            self._track_map_failure("unknown action type")
            return None

        if action == "scroll_down":
            self.consecutive_map_failures = 0  # Success
            return ("scroll", "down", None, None)
        
        if action == "scroll_up":
            self.consecutive_map_failures = 0  # Success 
            return ("scroll", "up", None, None)
        
        if action == "back":
            self.consecutive_map_failures = 0  # Success
            return ("back", None, None, None)

        if action in ["click", "input"]:
            # Try to find element by identifier first
            target_element = None
            if target_identifier:
                target_element = self._find_element_by_ai_identifier(target_identifier)
            else:
                logging.info(f"No 'target_identifier' provided for action '{action}'. Will check for bounding box.")

            if target_element:
                logging.info(f"Successfully mapped AI identifier '{target_identifier}' to initial WebElement.")
                
                if action == "input":
                    original_element = target_element
                    is_editable = False
                    element_class = None
                    final_target_element = original_element
                    
                    try:
                        element_class: str | Dict[str, Any] | None = original_element.get_attribute('class')
                        logging.debug(f"Initial element found for INPUT: ID='{original_element.id}', Class='{element_class}', Identifier='{target_identifier}'")
                        editable_classes = ['edittext', 'textfield', 'input', 'autocomplete', 'searchview']
                        max_levels_to_check = 3

                        if isinstance(element_class, str) and any(editable_tag in element_class.lower() for editable_tag in editable_classes):
                            is_editable = True
                            logging.info(f"Initial element (Class: {element_class}) is directly editable. Using it for INPUT.")
                        else:
                            logging.info(f"Initial element (Class: {element_class}) is NOT directly editable. Searching upwards for an editable ancestor...")
                            current_ancestor = original_element
                            for level in range(1, max_levels_to_check + 1):
                                try:
                                    parent_element = current_ancestor.find_element(AppiumBy.XPATH, "..")
                                    if parent_element:
                                        parent_class = parent_element.get_attribute('class')
                                        logging.debug(f"Checking ancestor level {level}: ID='{parent_element.id}', Class='{parent_class}'")
                                        if parent_class and any(editable_tag in parent_class.lower() for editable_tag in editable_classes):
                                            logging.info(f"Found editable ancestor at level {level} (Class: {parent_class}). Switching target for INPUT action.")
                                            final_target_element = parent_element
                                            is_editable = True
                                            break
                                        else:
                                            current_ancestor = parent_element
                                    else:
                                        logging.debug(f"Could not retrieve class attribute from ancestor at level {level}. Stopping upward search.")
                                        break
                                except NoSuchElementException:
                                    logging.debug(f"No more parent elements found at level {level}. Stopping upward search.")
                                    break
                                except Exception as parent_err:
                                    logging.error(f"Error finding or checking ancestor element at level {level}: {parent_err}", exc_info=True)
                                    break
                        
                        if not is_editable:
                            logging.error(f"AI suggested INPUT for identifier '{target_identifier}', but neither the initially found element (Class: {element_class}) nor its ancestors (up to {max_levels_to_check} levels) were suitable/editable. Mapping failed.")
                            self._track_map_failure("no editable element found")
                            return None
                            
                    except Exception as e:
                        logging.error(f"Error during element class validation/ancestor check for INPUT action (Identifier: '{target_identifier}'): {e}", exc_info=True)
                        self._track_map_failure(str(e))
                        return None

                    self.consecutive_map_failures = 0  # Success
                    logging.info(f"Mapping successful for INPUT. Using element ID: {final_target_element.id}")
                    return (action, final_target_element, input_text, None)
                
                # For click action
                self.consecutive_map_failures = 0  # Success
                logging.info(f"Mapping successful for CLICK. Using element ID: {target_element.id}")
                return (action, target_element, None, None)

            # Element not found by identifier, try bounding box fallback
            if self.use_coordinate_fallback and target_bounding_box and isinstance(target_bounding_box, dict):
                if ('top_left' in target_bounding_box and 'bottom_right' in target_bounding_box and 
                    isinstance(target_bounding_box['top_left'], list) and len(target_bounding_box['top_left']) == 2 and 
                    isinstance(target_bounding_box['bottom_right'], list) and len(target_bounding_box['bottom_right']) == 2):
                    
                    try:
                        tl_x, tl_y = target_bounding_box['top_left']
                        br_x, br_y = target_bounding_box['bottom_right']
                        
                        if not all(isinstance(coord, (int, float)) for coord in [tl_x, tl_y, br_x, br_y]):
                            logging.warning(f"Invalid coordinate types in bounding box: {target_bounding_box}. Cannot use for coordinate action.")
                            self._track_map_failure("invalid coordinate types")
                            return None
                        
                        center_x = int((tl_x + br_x) / 2)
                        center_y = int((tl_y + br_y) / 2)
                        
                        self.consecutive_map_failures = 0  # Success
                        logging.info(f"Element not found by identifier '{target_identifier}'. Using bounding box fallback (config ENABLED) for action '{action}' at coordinates ({center_x}, {center_y}).")
                        return (action, {"coordinates": (center_x, center_y), "original_bbox": target_bounding_box}, input_text, "coordinate_action")

                    except Exception as e:
                        logging.error(f"Error processing bounding box {target_bounding_box} for coordinate action: {e}", exc_info=True)
                        self._track_map_failure(str(e))
                        return None

            if not self.use_coordinate_fallback:
                logging.info(f"Element not found by identifier '{target_identifier}'. Bounding box fallback is DISABLED by configuration. Skipping.")

            # If no element and no (valid) bounding box fallback (or fallback disabled)
            log_msg = f"Failed to find element using AI identifier: '{target_identifier}'"
            if target_identifier and not target_bounding_box:
                log_msg += " and no bounding box provided."
            elif not target_identifier and not target_bounding_box:
                log_msg = "No target_identifier or bounding_box provided."
            elif target_bounding_box:  # Implies bounding box was invalid or processed with error
                log_msg += " and bounding box fallback also failed or was invalid."
            else:
                log_msg += " (unknown reason)."
            logging.warning(log_msg)
            self._track_map_failure("no element found and no valid fallback")

        return None

