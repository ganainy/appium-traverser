# action_mapper.py
import logging
import time
from typing import Optional, Tuple, Any, List, Dict, TYPE_CHECKING

from appium.webdriver.common.appiumby import AppiumBy
# WebElement is imported via TYPE_CHECKING for AppiumDriver, but if used directly here, ensure it's available.
# from selenium.webdriver.remote.webelement import WebElement 
from selenium.common.exceptions import NoSuchElementException, InvalidSelectorException, StaleElementReferenceException

# Import your main Config class and AppiumDriver
# Adjust paths based on your project structure
if TYPE_CHECKING: # For type hinting to avoid circular imports if AppiumDriver imports ActionMapper
    from appium_driver import AppiumDriver 
from config import Config # Assuming Config class is in config.py in the same package


class ActionMapper:
    def __init__(self, driver: 'AppiumDriver', element_finding_strategies: List[Tuple[str, Optional[str], str]], app_config: Config):
        """
        Initialize the ActionMapper.

        Args:
            driver (AppiumDriver): An instance of the refactored AppiumDriver.
            element_finding_strategies (List[Tuple[str, Optional[str], str]]): 
                List of strategies to find elements. Example: [('id', AppiumBy.ID, "ID"), ...].
                The AppiumBy string itself is passed, not the direct AppiumBy member for flexibility if strategies evolve.
            app_config (Config): The main application Config object instance.
        """
        self.driver = driver
        self.element_finding_strategies = element_finding_strategies # Store as is
        self.cfg = app_config # Store the Config object instance

        # Validate required configuration values from self.cfg
        if not hasattr(self.cfg, 'USE_COORDINATE_FALLBACK') or self.cfg.USE_COORDINATE_FALLBACK is None:
            # Defaulting if not explicitly set, but better to ensure it's in Config class
            logging.warning("USE_COORDINATE_FALLBACK not explicitly in config, defaulting to True for ActionMapper.")
            self.use_coordinate_fallback = True 
        else:
            self.use_coordinate_fallback = bool(self.cfg.USE_COORDINATE_FALLBACK)

        if not hasattr(self.cfg, 'MAX_CONSECUTIVE_MAP_FAILURES') or self.cfg.MAX_CONSECUTIVE_MAP_FAILURES is None:
            logging.warning("MAX_CONSECUTIVE_MAP_FAILURES not explicitly in config, defaulting to 3 for ActionMapper.")
            self.max_map_failures = 3
        else:
            self.max_map_failures = int(self.cfg.MAX_CONSECUTIVE_MAP_FAILURES)
            
        self.consecutive_map_failures = 0
        
        logging.info(
            f"ActionMapper initialized. Coordinate fallback: {'ENABLED' if self.use_coordinate_fallback else 'DISABLED'}. "
            f"Max map failures: {self.max_map_failures}"
        )

    def _find_element_by_ai_identifier(self, identifier: str) -> Optional[Any]: # Return type Any for WebElement
        """
        Attempts to find a WebElement using the identifier provided by the AI,
        trying different strategies. Promotes successful strategies.
        """
        if not identifier or not self.driver:
            logging.warning("Cannot find element: Invalid identifier or driver not available.")
            return None
        # self.driver.driver would refer to the raw Appium WebDriver instance if your AppiumDriver wrapper has such an attribute.
        # Assuming self.driver (AppiumDriver instance) has a method like find_element and find_elements.
        if not self.driver.driver: # Check if the raw driver is connected
             logging.warning("Raw Appium WebDriver not available in AppiumDriver instance.")
             return None


        logging.info(f"Attempting to find element using identifier: '{identifier}'")
        total_start_time = time.perf_counter()

        for index, (strategy_key, appium_by_strategy_str, log_name) in enumerate(self.element_finding_strategies):
            element: Optional[Any] = None # WebElement
            start_time = time.perf_counter()
            xpath_generated = ""

            try:
                actual_appium_by: Optional[str] = None
                if appium_by_strategy_str: # If an AppiumBy strategy string is provided
                    actual_appium_by = appium_by_strategy_str # e.g., "id", "accessibility id"

                if strategy_key in ['id', 'acc_id'] and actual_appium_by:
                    logging.debug(f"Trying {log_name}: '{identifier}' using AppiumBy strategy '{actual_appium_by}'")
                    element = self.driver.find_element(by=actual_appium_by, value=identifier) # Assumes AppiumDriver.find_element handles string 'by'
                elif strategy_key == 'xpath_exact':
                    # Robust quote handling for XPath
                    if "'" in identifier and '"' in identifier: # Contains both single and double
                        parts = []
                        split_by_single = identifier.split("'")
                        for i, part in enumerate(split_by_single):
                            if '"' in part: parts.append(f"'{part}'") # Part has double, enclose in single
                            elif part: parts.append(f'"{part}"')      # Part safe for double, enclose in double
                            if i < len(split_by_single) - 1: parts.append("\"'\"") # Add escaped single quote
                        xpath_text_expression = f"concat({','.join(filter(None, parts))})"
                    elif "'" in identifier: xpath_text_expression = f'"{identifier}"' # Contains single, use double
                    elif '"' in identifier: xpath_text_expression = f"'{identifier}'" # Contains double, use single
                    else: xpath_text_expression = f"'{identifier}'" # No quotes, use single
                    
                    xpath_generated = f"//*[@text={xpath_text_expression} or @content-desc={xpath_text_expression} or @resource-id='{identifier}']"
                    logging.debug(f"Trying {log_name} (Quote Safe): {xpath_generated}")
                    element = self.driver.find_element(by=AppiumBy.XPATH, value=xpath_generated)
                elif strategy_key == 'xpath_contains':
                    # Simpler quote handling for contains, as exact match is less critical
                    if "'" in identifier: xpath_safe_identifier = f'"{identifier}"'
                    else: xpath_safe_identifier = f"'{identifier}'"
                    
                    xpath_generated = (
                        f"//*[contains(@text, {xpath_safe_identifier}) or "
                        f"contains(@content-desc, {xpath_safe_identifier}) or "
                        f"contains(@resource-id, {xpath_safe_identifier})]"
                    )
                    logging.debug(f"Trying {log_name} (Quote Safe Contains): {xpath_generated}")
                    # Use driver.find_elements to get a list and then filter
                    possible_elements = self.driver.driver.find_elements(AppiumBy.XPATH, xpath_generated)
                    found_count = len(possible_elements)
                    logging.debug(f"Found {found_count} potential elements via '{log_name}' XPath.")
                    for el in possible_elements:
                        try:
                            if el.is_displayed() and el.is_enabled():
                                element = el
                                break 
                        except StaleElementReferenceException: # Element might go stale during iteration
                            logging.debug("Stale element encountered while filtering XPath contains results.")
                            continue
                        except Exception: continue # Ignore other errors for non-critical filtering
                    if not element and found_count > 0:
                        logging.debug(f"No suitable (displayed/enabled) element found by '{log_name}' XPath after filtering {found_count} candidates.")
                    elif found_count == 0:
                        logging.debug(f"No elements found by '{log_name}' XPath.")


                duration = time.perf_counter() - start_time

                if element:
                    is_displayed = False
                    is_enabled = False
                    try:
                        is_displayed = element.is_displayed()
                        is_enabled = element.is_enabled()
                    except StaleElementReferenceException:
                        logging.warning(f"Element found by {log_name} became stale before display/enable check.")
                        element = None # Treat as not found if stale immediately

                    if element and is_displayed and is_enabled:
                        logging.info(f"Found suitable element by {log_name}: '{identifier}' (took {duration:.4f}s)")
                        if index > 0: # Promote successful strategy
                            promoted_strategy = self.element_finding_strategies.pop(index)
                            self.element_finding_strategies.insert(0, promoted_strategy)
                            logging.info(f"Promoted strategy '{log_name}'. New order: {[s[2] for s in self.element_finding_strategies]}")
                        return element
                    elif element:
                        logging.debug(f"Element found by {log_name} but not suitable (Displayed: {is_displayed}, Enabled: {is_enabled}). Took {duration:.4f}s.")
                        element = None # Not suitable, continue to next strategy

            except NoSuchElementException:
                duration = time.perf_counter() - start_time
                logging.debug(f"Not found by {log_name} (took {duration:.4f}s).")
            except InvalidSelectorException as e:
                duration = time.perf_counter() - start_time
                logging.warning(f"Invalid Selector for {log_name} (XPath: {xpath_generated}). Error: {e} (took {duration:.4f}s)")
            except Exception as e: # Catch other potential errors from driver.find_element
                duration = time.perf_counter() - start_time
                logging.warning(f"Unexpected error finding by {log_name} with identifier '{identifier}' (XPath: {xpath_generated}). Error: {e} (took {duration:.4f}s)", exc_info=False) # exc_info=False to reduce noise

        total_duration = time.perf_counter() - total_start_time
        logging.warning(
            f"Could not find suitable element for identifier '{identifier}' using any strategy. "
            f"Total search time: {total_duration:.4f}s. Current strategy order: {[s[2] for s in self.element_finding_strategies]}"
        )
        return None    
    
    def _track_map_failure(self, reason: str):
        """Helper method to track and log mapping failures."""
        self.consecutive_map_failures += 1
        logging.warning(
            f"Action mapping failed: {reason}. Consecutive failures: "
            f"{self.consecutive_map_failures}/{self.max_map_failures}"
        )
        # Termination due to max failures is handled by AppCrawler's _should_terminate()

    def _extract_coordinates_from_bbox(self, target_bounding_box: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        """Extracts and calculates center coordinates from a bounding box dictionary."""
        try:
            top_left = target_bounding_box.get('top_left')
            bottom_right = target_bounding_box.get('bottom_right')

            if not (isinstance(top_left, list) and len(top_left) == 2 and
                    isinstance(bottom_right, list) and len(bottom_right) == 2):
                logging.warning(f"Invalid format for 'top_left' or 'bottom_right' in bounding box: {target_bounding_box}")
                return None

            # AI schema uses [y1, x1], [y2, x2]
            y1, x1 = top_left
            y2, x2 = bottom_right

            if not all(isinstance(coord, (int, float)) for coord in [y1, x1, y2, x2]):
                logging.warning(f"Non-numeric coordinate types in bounding box: {target_bounding_box}")
                return None
            
            # Ensure coordinates are valid (e.g., x1 < x2, y1 < y2)
            if x1 > x2 or y1 > y2:
                logging.warning(f"Invalid bounding box coordinates (x1>x2 or y1>y2): tl=({x1},{y1}), br=({x2},{y2}). Swapping.")
                # Attempt to correct by swapping if order is simply reversed
                if x1 > x2: x1, x2 = x2, x1
                if y1 > y2: y1, y2 = y2, y1

            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)
            return center_x, center_y
        except Exception as e:
            logging.error(f"Error processing bounding box {target_bounding_box} for coordinate action: {e}", exc_info=True)
            return None


    def map_ai_action_to_appium(self, ai_response: Dict[str, Any], current_xml_string: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Maps the AI's JSON suggestion to an executable action dictionary for ActionExecutor.

        Args:
            ai_response (Dict[str, Any]): The structured JSON response from the AI.
            current_xml_string (Optional[str]): Full XML of the current screen for detailed mapping if needed.
        
        Returns:
            Optional[Dict[str, Any]]: Action details for ActionExecutor, or None if mapping fails.
            Example: {'type': 'click', 'element': WebElement, 'element_info': {...}}
                     {'type': 'input', 'element': WebElement, 'text': '...', 'element_info': {...}}
                     {'type': 'tap_coords', 'coordinates': (x,y), 'original_bbox': {...}}
                     {'type': 'scroll', 'direction': 'down'}
                     {'type': 'back'}
        """
        action_type = ai_response.get("action")
        target_identifier = ai_response.get("target_identifier") # String from AI (text, ID, content-desc)
        input_text = ai_response.get("input_text")
        target_bounding_box = ai_response.get("target_bounding_box") # Dict or None

        logging.info(
            f"Mapping AI suggestion: Action='{action_type}', Identifier='{target_identifier}', "
            f"Input='{input_text}', BBox='{target_bounding_box is not None}'"
        )

        if not action_type or action_type not in self.cfg.AVAILABLE_ACTIONS: # Use cfg for available actions
            self._track_map_failure(f"Unknown or unavailable action type from AI: {action_type}")
            return None

        action_details: Dict[str, Any] = {"type": action_type}

        if action_type in ["scroll_down", "scroll_up"]:
            self.consecutive_map_failures = 0
            action_details["direction"] = action_type.split('_')[1] # "down" or "up"
            return action_details
        
        if action_type == "back":
            self.consecutive_map_failures = 0
            return action_details # Type 'back' is sufficient

        # For click and input, we need a target
        target_element: Optional[Any] = None # WebElement
        element_info: Dict[str, Any] = {} # To store how element was found

        if target_identifier:
            target_element = self._find_element_by_ai_identifier(str(target_identifier))
            if target_element:
                element_info["method"] = "identifier"
                element_info["identifier_used"] = str(target_identifier)
                try:
                    element_info["id"] = target_element.id
                    element_info["class"] = target_element.get_attribute('class')
                    element_info["text"] = target_element.text
                    element_info["content-desc"] = target_element.get_attribute('content-desc')
                    element_info["bounds"] = target_element.get_attribute('bounds')
                except StaleElementReferenceException:
                     logging.warning(f"Element found by '{target_identifier}' became stale when fetching attributes.")
                     target_element = None # Treat as not found
                except Exception as e_attr:
                    logging.warning(f"Error fetching attributes for element found by '{target_identifier}': {e_attr}")


        if target_element:
            action_details["element"] = target_element
            action_details["element_info"] = element_info
            if action_type == "input":
                if input_text is None: # Allow empty string for input
                    logging.warning(f"AI suggested 'input' for '{target_identifier}' but 'input_text' is null. Will attempt to clear or input empty.")
                    action_details["text"] = "" 
                else:
                    action_details["text"] = str(input_text) # Ensure string
            self.consecutive_map_failures = 0
            logging.info(f"Successfully mapped action '{action_type}' to element (ID: {element_info.get('id', 'N/A')}) found by identifier.")
            return action_details
        
        # If element not found by identifier, or no identifier, try coordinate fallback
        logging.info(f"Element not found by identifier '{target_identifier}'. Checking coordinate fallback (Enabled: {self.use_coordinate_fallback}).")
        if self.use_coordinate_fallback and target_bounding_box and isinstance(target_bounding_box, dict):
            coordinates = self._extract_coordinates_from_bbox(target_bounding_box)
            if coordinates:
                center_x, center_y = coordinates
                action_details["type"] = "tap_coords" # Change action type for coordinate tap
                action_details["coordinates"] = (center_x, center_y)
                action_details["original_bbox"] = target_bounding_box # For annotation/logging
                # If original action was "input", we need to decide how to handle it.
                # For now, tap_coords won't carry input_text unless ActionExecutor handles it.
                if action_type == "input" and input_text is not None:
                    # ActionExecutor will need to know it should try ADB input after tap if this mode is used.
                    action_details["intended_input_text"] = str(input_text)
                    logging.info(f"Coordinate fallback for INPUT action: will tap at ({center_x},{center_y}), then try to input '{input_text}' (likely via ADB).")
                else:
                     logging.info(f"Coordinate fallback for {action_type}: will tap at ({center_x},{center_y}).")
                
                self.consecutive_map_failures = 0
                return action_details
            else:
                logging.warning(f"Bounding box provided but could not extract valid coordinates: {target_bounding_box}")
        
        # If all methods fail
        log_msg = f"Failed to map AI action. Element for identifier '{target_identifier}' not found."
        if self.use_coordinate_fallback:
            log_msg += " Coordinate fallback also failed or BBox not suitable."
        else:
            log_msg += " Coordinate fallback disabled."
        if not target_identifier and not target_bounding_box:
            log_msg = "Failed to map AI action: No target_identifier or target_bounding_box provided."
            
        self._track_map_failure(log_msg)
        return None