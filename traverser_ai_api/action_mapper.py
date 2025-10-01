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
try:
    from traverser_ai_api.config import Config # Assuming Config class is in config.py in the same package
except ImportError:
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

    def _escape_xpath_literal(self, s: str) -> str:
        """Safely escape a string for use as an XPath literal.
        Handles cases where the string contains both single and double quotes
        by using concat().
        """
        if s is None:
            return "''"
        if "'" in s and '"' in s:
            parts = []
            for i, part in enumerate(s.split("'")):
                if '"' in part:
                    parts.append(f"'{part}'")
                elif part:
                    parts.append(f'"{part}"')
                if i < len(s.split("'")) - 1:
                    parts.append("\"'\"")
            return f"concat({','.join(filter(None, parts))})"
        elif "'" in s:
            return f'"{s}"'
        else:
            return f"'{s}'"

    def _is_full_resource_id(self, identifier: str) -> bool:
        """Return True if identifier looks like a full Android resource-id, e.g., 'com.pkg:id/view_id'."""
        try:
            return isinstance(identifier, str) and ":id/" in identifier and len(identifier.split(":id/")) == 2
        except Exception:
            return False

    def _build_full_resource_id(self, simple_id: str) -> Optional[str]:
        """Build full resource-id using configured app package if available."""
        package = getattr(self.cfg, 'APP_PACKAGE', None)
        if package and isinstance(simple_id, str) and simple_id:
            return f"{package}:id/{simple_id}"
        return None

    def _find_element_by_ai_identifier(self, identifier: str) -> Optional[Any]: # Return type Any for WebElement
        """
        Attempts to find a WebElement using the identifier provided by the AI,
        trying different strategies and retrying on stale elements.
        """
        if not identifier or not self.driver or not self.driver.driver:
            logging.warning("Cannot find element: Invalid identifier or driver not available.")
            return None

        max_retries = 2
        for retry in range(max_retries + 1):
            try:
                logging.debug(f"Attempting to find element '{identifier}' (Attempt {retry + 1}/{max_retries + 1})")
                total_start_time = time.perf_counter()

                for index, (strategy_key, appium_by_strategy_str, log_name) in enumerate(self.element_finding_strategies):
                    element: Optional[Any] = None
                    start_time = time.perf_counter()
                    duration = 0.0
                    xpath_generated = ""

                    try:
                        actual_appium_by: Optional[str] = None
                        if appium_by_strategy_str:
                            actual_appium_by = appium_by_strategy_str

                        if strategy_key in ['id', 'acc_id'] and actual_appium_by:
                            # Normalize resource-id handling for 'id'
                            if strategy_key == 'id':
                                # Try full resource-id directly
                                if self._is_full_resource_id(identifier):
                                    element = self.driver.find_element(by=actual_appium_by, value=identifier)
                                else:
                                    # Try building full id with package
                                    full_id = self._build_full_resource_id(identifier)
                                    if full_id:
                                        try:
                                            element = self.driver.find_element(by=actual_appium_by, value=full_id)
                                        except (NoSuchElementException, InvalidSelectorException):
                                            element = None
                                    # If still not found and identifier lacks package prefix, try XPath contains on resource-id
                                    if not element:
                                        safe = self._escape_xpath_literal(identifier)
                                        xpath_generated = f"//*[@resource-id and contains(@resource-id,{safe})]"
                                        element = self.driver.find_element(by=AppiumBy.XPATH, value=xpath_generated)
                            else:
                                # Accessibility ID straightforward
                                element = self.driver.find_element(by=actual_appium_by, value=identifier)
                        elif strategy_key == 'xpath_exact':
                            if "'" in identifier and '"' in identifier:
                                parts = []
                                split_by_single = identifier.split("'")
                                for i, part in enumerate(split_by_single):
                                    if '"' in part: parts.append(f"'{part}'")
                                    elif part: parts.append(f'"{part}"')
                                    if i < len(split_by_single) - 1: parts.append("\"'\"")
                                xpath_text_expression = f"concat({','.join(filter(None, parts))})"
                            elif "'" in identifier: xpath_text_expression = f'"{identifier}"'
                            elif '"' in identifier: xpath_text_expression = f"'{identifier}'"
                            else: xpath_text_expression = f"'{identifier}'"
                            xpath_generated = f"//*[@text={xpath_text_expression} or @content-desc={xpath_text_expression} or @resource-id='{identifier}']"
                            element = self.driver.find_element(by=AppiumBy.XPATH, value=xpath_generated)
                        elif strategy_key == 'xpath_contains':
                            safe = self._escape_xpath_literal(identifier)
                            xpath_generated = f"//*[contains(@resource-id,{safe}) or contains(@text,{safe}) or contains(@content-desc,{safe})]"
                            element = self.driver.find_element(by=AppiumBy.XPATH, value=xpath_generated)
                        elif strategy_key == 'id_partial':
                            safe = self._escape_xpath_literal(identifier)
                            xpath_generated = f"//*[@resource-id and contains(@resource-id,{safe})]"
                            element = self.driver.find_element(by=AppiumBy.XPATH, value=xpath_generated)
                        elif strategy_key == 'text_case_insensitive':
                            # Case-insensitive text contains using translate()
                            safe_lowerable = self._escape_xpath_literal(identifier)
                            xpath_generated = (
                                "//*[contains("
                                "translate(@text,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), "
                                f"translate({safe_lowerable},'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))]"
                            )
                            element = self.driver.find_element(by=AppiumBy.XPATH, value=xpath_generated)
                        elif strategy_key == 'class_contains':
                            safe = self._escape_xpath_literal(identifier)
                            xpath_generated = f"//*[contains(@class,{safe})]"
                            element = self.driver.find_element(by=AppiumBy.XPATH, value=xpath_generated)
                        elif strategy_key == 'xpath_flexible':
                            safe = self._escape_xpath_literal(identifier)
                            xpath_generated = (
                                f"//*[(starts-with(@resource-id,{safe}) or contains(@resource-id,{safe})) "
                                f"or (starts-with(@text,{safe}) or contains(@text,{safe})) "
                                f"or (starts-with(@content-desc,{safe}) or contains(@content-desc,{safe}))]"
                            )
                            element = self.driver.find_element(by=AppiumBy.XPATH, value=xpath_generated)
                        # ... (other strategies can be added here)

                        if element:
                            is_displayed = element.is_displayed()
                            is_enabled = element.is_enabled()
                            if is_displayed and is_enabled:
                                duration = time.perf_counter() - start_time
                                logging.info(f"Found suitable element by {log_name}: '{identifier}' (took {duration:.4f}s)")
                                if index > 0:
                                    promoted_strategy = self.element_finding_strategies.pop(index)
                                    self.element_finding_strategies.insert(0, promoted_strategy)
                                    logging.info(f"Promoted strategy '{log_name}'.")
                                return element
                            else:
                                element = None

                    except (NoSuchElementException, InvalidSelectorException, StaleElementReferenceException) as e:
                        duration = time.perf_counter() - start_time
                        if isinstance(e, StaleElementReferenceException):
                            logging.debug(f"Stale element detected with {log_name}. Re-raising to trigger retry.")
                            raise
                        elif isinstance(e, NoSuchElementException):
                            logging.debug(f"Not found by {log_name} (took {duration:.4f}s).")
                        else:
                            logging.warning(f"Error with {log_name} (XPath: {xpath_generated}): {e} (took {duration:.4f}s)")

                total_duration = time.perf_counter() - total_start_time
                logging.warning(f"Could not find suitable element for identifier '{identifier}' in this attempt. Total time: {total_duration:.4f}s.")
                return None

            except StaleElementReferenceException:
                if retry < max_retries:
                    logging.debug(f"StaleElementReferenceException caught, retrying... ({retry + 1}/{max_retries})")
                    time.sleep(0.5)
                    continue
                else:
                    logging.warning(f"Element finding failed for '{identifier}' after {max_retries + 1} attempts due to stale elements.")
                    return None
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
        try:
            top_left = target_bounding_box.get('top_left')
            bottom_right = target_bounding_box.get('bottom_right')

            if not (isinstance(top_left, list) and len(top_left) == 2 and
                    isinstance(bottom_right, list) and len(bottom_right) == 2):
                logging.warning(f"Invalid format for bounding box: {target_bounding_box}")
                return None

            window_size = self.driver.get_window_size()
            if not window_size:
                logging.error("Failed to get window size for coordinate calculation.")
                return None
            
            screen_width, screen_height = window_size['width'], window_size['height']
            y1_norm, x1_norm = top_left
            y2_norm, x2_norm = bottom_right

            if not all(isinstance(coord, (int, float)) for coord in [y1_norm, x1_norm, y2_norm, x2_norm]):
                logging.warning(f"Non-numeric coordinates: {target_bounding_box}")
                return None
            
            # FIX: Check if coordinates are already absolute vs normalized
            if all(coord <= 1.0 for coord in [y1_norm, x1_norm, y2_norm, x2_norm]):
                # Normalized coordinates (0-1 range)
                x1 = int(float(x1_norm) * screen_width)
                y1 = int(float(y1_norm) * screen_height)
                x2 = int(float(x2_norm) * screen_width)
                y2 = int(float(y2_norm) * screen_height)
            else:
                # Already absolute coordinates
                x1, y1, x2, y2 = int(x1_norm), int(y1_norm), int(x2_norm), int(y2_norm)

            # Ensure coordinates are within screen bounds
            x1 = max(0, min(x1, screen_width - 1))
            y1 = max(0, min(y1, screen_height - 1))
            x2 = max(0, min(x2, screen_width - 1))
            y2 = max(0, min(y2, screen_height - 1))

            if x1 > x2: x1, x2 = x2, x1
            if y1 > y2: y1, y2 = y2, y1

            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)
            
            logging.debug(f"Calculated tap coordinates ({center_x}, {center_y}) from bbox {target_bounding_box}")
            return center_x, center_y
            
        except Exception as e:
            logging.error(f"Error processing bounding box: {e}", exc_info=True)
            return None


    def map_ai_action_to_appium(self, ai_response: Dict[str, Any], current_xml_string: Optional[str] = None) -> Optional[Dict[str, Any]]:
        action_type = ai_response.get("action")
        target_identifier = ai_response.get("target_identifier")
        input_text = ai_response.get("input_text")
        target_bounding_box = ai_response.get("target_bounding_box")

        logging.info(
            f"Mapping AI suggestion: Action='{action_type}', Identifier='{target_identifier}', "
            f"Input='{input_text}', BBox='{target_bounding_box is not None}'"
        )

        if not action_type or action_type not in self.cfg.AVAILABLE_ACTIONS:
            self._track_map_failure(f"Unknown or unavailable action type from AI: {action_type}")
            return None

        action_details: Dict[str, Any] = {"type": action_type}

        if action_type in ["scroll_down", "scroll_up", "swipe_left", "swipe_right"]:
            self.consecutive_map_failures = 0
            action_details["direction"] = action_type.split('_')[1]
            return action_details
        
        if action_type == "back":
            self.consecutive_map_failures = 0
            return action_details

        target_element: Optional[Any] = None
        element_info: Dict[str, Any] = {}

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
                     target_element = None
                except Exception as e_attr:
                    logging.warning(f"Error fetching attributes for element found by '{target_identifier}': {e_attr}")


        if target_element:
            action_details["element"] = target_element
            action_details["element_info"] = element_info
            # Carry through any provided bbox for potential execution-time fallback
            if isinstance(target_bounding_box, dict):
                action_details["original_bbox"] = target_bounding_box
            if action_type == "input":
                if input_text is None:
                    logging.warning(f"AI suggested 'input' for '{target_identifier}' but 'input_text' is null. Will attempt to clear or input empty.")
                    action_details["text"] = "" 
                else:
                    action_details["text"] = str(input_text)
            self.consecutive_map_failures = 0
            logging.info(f"Successfully mapped action '{action_type}' to element (ID: {element_info.get('id', 'N/A')}) found by identifier.")
            return action_details
        
        logging.info(f"Element not found by identifier '{target_identifier}'. Checking coordinate fallback (Enabled: {self.use_coordinate_fallback}).")
        if self.use_coordinate_fallback and target_bounding_box and isinstance(target_bounding_box, dict):
            coordinates = self._extract_coordinates_from_bbox(target_bounding_box)
            if coordinates:
                center_x, center_y = coordinates
                action_details["type"] = "tap_coords"
                action_details["coordinates"] = (center_x, center_y)
                action_details["original_bbox"] = target_bounding_box
                if action_type == "input" and input_text is not None:
                    action_details["intended_input_text"] = str(input_text)
                    logging.info(f"Coordinate fallback for INPUT action: will tap at ({center_x},{center_y}), then try to input text.")
                else:
                     logging.info(f"Coordinate fallback for {action_type}: will tap at ({center_x},{center_y}).")
                
                self.consecutive_map_failures = 0
                return action_details
            else:
                logging.warning(f"Bounding box provided but could not extract valid coordinates: {target_bounding_box}")
        
        log_msg = f"Failed to map AI action. Element for identifier '{target_identifier}' not found."
        if self.use_coordinate_fallback:
            log_msg += " Coordinate fallback also failed or BBox not suitable."
        else:
            log_msg += " Coordinate fallback disabled."
        if not target_identifier and not target_bounding_box:
            log_msg = "Failed to map AI action: No target_identifier or target_bounding_box provided."
            
        self._track_map_failure(log_msg)
        return None