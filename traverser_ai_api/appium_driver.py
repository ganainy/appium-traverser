import logging
import shlex # Added shlex
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException, NoSuchElementException, InvalidElementStateException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from typing import Optional, List, Dict, Any, Tuple # Added Tuple

from . import config # Changed to relative import
import time

class AppiumDriver:
    """Wrapper for Appium WebDriver interactions."""

    def __init__(self, server_url: str, config: dict):
        self.server_url = server_url
        self.config = config
        self.driver: Optional[webdriver.Remote] = None

    def connect(self) -> bool:
        """Establishes connection to the Appium server."""
        options = UiAutomator2Options()
        caps = {
            "platformName": "Android",
            "appium:automationName": "UiAutomator2",
            "appium:appPackage": self.config['APP_PACKAGE'],
            "appium:appActivity": self.config['APP_ACTIVITY'],
            "appium:noReset": True, # Keep app data between sessions
            "appium:autoGrantPermissions": True,
            "appium:newCommandTimeout": self.config['NEW_COMMAND_TIMEOUT'],
            "appium:ensureWebviewsHavePages": True,
            "appium:nativeWebScreenshot": True,
            "appium:connectHardwareKeyboard": True,
        }
        if self.config.get('TARGET_DEVICE_UDID'):
            caps["appium:udid"] = self.config['TARGET_DEVICE_UDID']

        options.load_capabilities(caps)

        try:
            logging.info(f"Connecting to Appium server at {self.server_url}...")
            self.driver = webdriver.Remote(self.server_url, options=options)

            # --- Set Implicit Wait ---
            implicit_wait_time = getattr(config, 'APPIUM_IMPLICIT_WAIT', 5) # Default to 5 if not in config
            logging.info(f"Setting Appium implicit wait to {implicit_wait_time} seconds.")
            self.driver.implicitly_wait(implicit_wait_time)

            logging.info("Appium session established successfully.")

            return True
        except WebDriverException as e:
            logging.error(f"Failed to connect to Appium server or start session: {e}")
            self.driver = None
            return False
        except Exception as e: # Catch other potential errors like config issues
            logging.error(f"An unexpected error occurred during Appium connection: {e}", exc_info=True)
            self.driver = None
            return False

    def disconnect(self):
        """Quits the Appium driver session."""
        if self.driver:
            try:
                logging.info("Closing Appium session...")
                self.driver.quit()
            except Exception as e:
                logging.error(f"Error closing Appium session: {e}")
            finally:
                self.driver = None
                logging.info("Appium session closed.")

    def get_page_source(self) -> Optional[str]:
        """Retrieves the XML page source."""
        if not self.driver: return None
        try:
            return self.driver.page_source
        except WebDriverException as e:
            logging.error(f"Error getting page source: {e}")
            return None

    def get_screenshot_bytes(self) -> Optional[bytes]:
        """Retrieves the current screen screenshot as PNG bytes."""
        if not self.driver: return None
        try:
            return self.driver.get_screenshot_as_png()
        except WebDriverException as e:
            logging.error(f"Error taking screenshot: {e}")
            return None

    def get_current_package(self) -> Optional[str]:
        """Retrieves the current application package name."""
        if not self.driver:
            logging.warning("Driver not available, cannot get current package.")
            return None
        try:
            return self.driver.current_package
        except WebDriverException as e:
            logging.error(f"Error getting current package: {e}")
            return None

    def get_current_activity(self) -> Optional[str]:
        """Retrieves the current application activity name."""
        if not self.driver:
            logging.warning("Driver not available, cannot get current activity.")
            return None
        try:
            return self.driver.current_activity
        except WebDriverException as e:
            logging.error(f"Error getting current activity: {e}")
            return None

    def launch_app(self, app_package: str, app_activity: str) -> bool:
        """
        Launches the specified application or brings it to the foreground if already running.
        Note: This uses ADB via Appium's mobile: shell.
        """
        if not self.driver:
            logging.error("Driver not available, cannot launch app.")
            return False
        if not app_package or not app_activity:
            logging.error("App package or activity not provided, cannot launch app.")
            return False
        try:
            logging.info(f"Attempting to launch app: {app_package}/{app_activity}")
            # Using 'am start' is generally reliable for starting an activity.
            # The -n flag specifies the component name (package/activity).
            # It will bring an existing task to the foreground or start a new one.
            self.driver.execute_script(
                "mobile: shell",
                {
                    "command": "am",
                    "args": ["start", "-n", f"{app_package}/{app_activity}"],
                },
            )
            # Add a short delay to allow the app to launch and stabilize
            time.sleep(getattr(self.config, 'APP_LAUNCH_WAIT_TIME', 3)) # Use configured or default
            
            # Verification step (optional but recommended)
            current_pkg = self.get_current_package()
            current_act = self.get_current_activity()
            if current_pkg == app_package: # Check if the top activity is part of the package
                logging.info(f"App {app_package} is now in the foreground (current activity: {current_act}).")
                return True
            else:
                logging.warning(f"App launch command sent, but current foreground app is {current_pkg} (expected {app_package}). The target app might not have launched correctly or another app took focus.")
                return False
        except WebDriverException as e:
            logging.error(f"WebDriverException launching app {app_package}/{app_activity}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error launching app {app_package}/{app_activity}: {e}", exc_info=True)
            return False

    def find_element(self, by: str, value: str) -> Optional[WebElement]:
        """Finds a single element with a short timeout."""
        if not self.driver or not value: return None
        try:
            # Use a short explicit wait for finding elements
            # element = WebDriverWait(self.driver, 3).until(
            #     EC.presence_of_element_located((by, value))
            # )
            # Simpler find without explicit wait for now
            element = self.driver.find_element(by=by, value=value)
            return element
        except NoSuchElementException:
            logging.debug(f"Element not found using {by}='{value}'")
            return None
        except WebDriverException as e:
            logging.warning(f"WebDriverException finding element {by}='{value}': {e}")
            return None

    def click_element(self, element: WebElement) -> bool:
        """Clicks a WebElement."""
        if not self.driver or not element:
            logging.warning("Driver not available or element is None, cannot click.")
            return False
        try:
            element_id = element.id # For logging
            logging.debug(f"Attempting to click element {element_id}")
            element.click()
            logging.debug(f"Successfully clicked element {element_id}")
            return True
        except StaleElementReferenceException:
             logging.warning(f"Attempted to click a stale element reference (ID was: {element.id if hasattr(element,'id') else 'N/A'}).")
             return False
        except WebDriverException as e:
            element_id_str = element.id if hasattr(element,'id') else 'Unknown ID'
            logging.error(f"Error clicking element {element_id_str}: {e}")
            return False
        except Exception as e:
            element_id_str = element.id if hasattr(element,'id') else 'Unknown ID'
            logging.error(f"Unexpected error clicking element {element_id_str}: {e}", exc_info=True)
            return False

    def input_text_into_element(self, element: WebElement, text: str, click_first: bool = True) -> bool:
        """Inputs text into a WebElement, optionally clicking it first."""
        if not self.driver or not element:
            logging.warning("Driver not available or element is None, cannot input text.")
            return False

        element_id_str = "Unknown ID" # Default if ID retrieval fails early
        try:
            # Try to get ID early for better logging, handle potential immediate staleness
            try:
                 element_id_str = element.id
            except StaleElementReferenceException:
                 logging.warning("Element was already stale before attempting input.")
                 return False

            logging.debug(f"Attempting to input '{text}' into element {element_id_str}")

            # *** STEP 1: Click the element to ensure focus ***
            if click_first:
                try:
                    logging.debug(f"Clicking element {element_id_str} before input.")
                    # Use the robust click method
                    if not self.click_element(element):
                        logging.warning(f"Failed to click element {element_id_str} before input, but will still attempt input.")
                        # Decide if you want to proceed or return False here. Proceeding might still work sometimes.
                        # return False # Uncomment this line to be stricter: fail if click fails

                    # Optional: Add a very small delay if clicking immediately followed by send_keys fails
                    # time.sleep(0.2) # Start without this, add only if needed

                except StaleElementReferenceException:
                     # This case should theoretically be caught by self.click_element, but double-check
                     logging.warning(f"Element {element_id_str} became stale during the pre-input click phase.")
                     return False # Can't proceed if element is stale
                except Exception as click_err:
                    # Log warning but proceed, maybe click wasn't needed or possible,
                    # but the element might still accept keys if already focused.
                    logging.warning(f"Unexpected error clicking element {element_id_str} before input, attempting input anyway: {click_err}")

            # *** STEP 2: Attempt to send keys ***
            logging.debug(f"Sending keys '{text}' to element {element_id_str}")
            # Consider using element.set_value(text) as an alternative if send_keys consistently fails
            element.send_keys(text)
            # element.set_value(text) # Alternative approach

            logging.info(f"Successfully sent keys '{text}' to element {element_id_str}") # Changed to INFO for successful action

            # Optional: Hide keyboard if it causes issues later (uncomment if necessary)
            try:
                if self.driver.is_keyboard_shown():
                    logging.debug("Hiding keyboard after input.")
                    self.driver.hide_keyboard()
            except Exception as kb_err:
                logging.warning(f"Could not hide keyboard after input: {kb_err}")

            return True

        except InvalidElementStateException as e:
             # Specific logging for the error you encountered
             logging.error(f"Error inputting text '{text}' into element {element_id_str}: {e}", exc_info=False) # Keep stack trace minimal for this specific error
             # Log the element's state if possible to help diagnose
             try:
                 # Check important attributes at the time of failure
                 is_enabled = element.is_enabled()
                 is_displayed = element.is_displayed()
                 # Use your existing get_element_attributes method if you have one, otherwise access directly
                 attrs = {}
                 try:
                     attrs['class'] = element.get_attribute('class')
                     attrs['text'] = element.get_attribute('text')
                     attrs['content-desc'] = element.get_attribute('content-desc')
                     attrs['resource-id'] = element.get_attribute('resource-id')
                     attrs['bounds'] = element.get_attribute('bounds')
                 except Exception as attr_err:
                      logging.warning(f"Could not get all attributes for element {element_id_str} during error diagnosis: {attr_err}")

                 logging.error(f"Element state at time of InvalidElementStateException: Enabled={is_enabled}, Displayed={is_displayed}, Attrs={attrs}")
             except StaleElementReferenceException:
                  logging.error(f"Element {element_id_str} became stale when trying to get state after input error.")
             except Exception as state_err:
                 logging.error(f"Could not retrieve element state for {element_id_str} after input error: {state_err}")
             return False
        except StaleElementReferenceException:
             logging.warning(f"Element {element_id_str} became stale before or during sending keys.")
             return False # Can't proceed if element is stale
        except WebDriverException as e:
            # General error logging for other WebDriver issues
            logging.error(f"Generic WebDriverException inputting text '{text}' into element {element_id_str}: {e}", exc_info=True)
            return False
        except Exception as e:
            # Catch any other unexpected errors
            logging.error(f"Unexpected error inputting text '{text}' into element {element_id_str}: {e}", exc_info=True)
            return False

    def press_back_button(self) -> bool:
        """Presses the Android back button."""
        if not self.driver: return False
        try:
            self.driver.press_keycode(4) # Android keycode for BACK
            return True
        except WebDriverException as e:
            logging.error(f"Error pressing back button: {e}")
            return False

    def scroll(self, direction: str, element: Optional[WebElement] = None, distance_ratio: float = 0.5) -> bool:
        """Performs a scroll gesture (swipe)."""
        if not self.driver: return False
        try:
            # Get window size for calculating swipe coordinates
            window_size = self.driver.get_window_size()
            width = window_size.get('width', 0)
            height = window_size.get('height', 0)
            if width == 0 or height == 0:
                logging.error("Could not get valid window size for scroll.")
                return False

            # Define start and end points based on direction
            center_x = width // 2
            start_y, end_y = 0, 0
            start_x, end_x = center_x, center_x # Default vertical scroll

            if direction == "down":
                start_y = int(height * 0.8)
                end_y = int(height * (0.8 - distance_ratio))
            elif direction == "up":
                start_y = int(height * 0.2)
                end_y = int(height * (0.2 + distance_ratio))
            # Add 'left'/'right' if needed, adjusting start_x/end_x
            else:
                logging.error(f"Unsupported scroll direction: {direction}")
                return False

            logging.debug(f"Scrolling {direction} from ({start_x},{start_y}) to ({end_x},{end_y})")
            # Perform the swipe
            self.driver.swipe(start_x, start_y, end_x, end_y, duration=800) # Duration in ms
            return True

        except WebDriverException as e:
            logging.error(f"Error performing scroll {direction}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during scroll: {e}", exc_info=True)
            return False

    def relaunch_app(self):
         """Attempts to relaunch the target application activity."""
         if not self.driver: return
         try:
             # Construct the intent string for the main activity
             intent = f"{self.config['APP_PACKAGE']}/{self.config['APP_ACTIVITY']}"
             logging.info(f"Attempting to relaunch app via intent: {intent}")
             # Use the execute_script method to start the activity
             # This is often more reliable than driver.launch_app() if already running
             self.driver.execute_script("mobile: startActivity", {"intent": intent})
             time.sleep(3) # Allow time for app to restart/come to foreground
             logging.info("Relaunch command sent.")
         except WebDriverException as e:
             logging.error(f"Error relaunching app: {e}", exc_info=True)

    def get_all_elements(self) -> List[WebElement]:
        """Gets all elements on the current screen."""
        if not self.driver: return []
        try:
            # Using XPath '//*' gets everything
            return self.driver.find_elements(by=By.XPATH, value="//*")
        except WebDriverException as e:
            logging.error(f"Error getting all elements: {e}")
            return []

    def get_element_attributes(self, element: WebElement, attributes: List[str]) -> Dict[str, Optional[str]]:
        """Safely gets multiple attributes for a given element."""
        element_attrs = {}
        if not element: return element_attrs
        for attr in attributes:
            try:
                # Handle common attributes/properties
                if attr == 'text':
                    val = element.text
                elif attr == 'displayed':
                    val = str(element.is_displayed()).lower()
                elif attr == 'enabled':
                    val = str(element.is_enabled()).lower()
                elif attr == 'selected':
                    val = str(element.is_selected()).lower()
                elif attr == 'resource-id': # Common Appium attribute name
                    val = element.get_attribute('resourceId') # Note capitalization
                else:
                    val = element.get_attribute(attr)
                element_attrs[attr] = val
            except Exception:
                element_attrs[attr] = None # Attribute not found or error getting it
        return element_attrs

    def get_window_size(self) -> Optional[Dict[str, int]]:
        """Gets the current device window size."""
        if not self.driver: return None
        try:
            size = self.driver.get_window_size()
            # Add basic validation
            if size and 'width' in size and 'height' in size and size['width'] > 0 and size['height'] > 0:
                return size
            else:
                logging.error(f"Received invalid window size: {size}")
                return None
        except WebDriverException as e:
            logging.error(f"Error getting window size: {e}")
            return None


    def tap_coordinates(self, x: int, y: int) -> bool:
        """Performs a tap action at the specified absolute pixel coordinates."""
        if not self.driver: return False
        try:
            logging.info(f"Tapping coordinates: ({x}, {y})")
            # Appium's tap takes a list of coordinate tuples
            self.driver.tap([(x, y)], duration=100) # Short duration tap
            return True
        except WebDriverException as e:
            logging.error(f"Error tapping coordinates ({x},{y}): {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during coordinate tap: {e}", exc_info=True)
            return False


    def type_text_by_adb(self, text: str) -> bool:
        """
        Simulates typing text using ADB 'input text' command.
        Assumes the target text field is already focused and keyboard *may* be open.
        """
        if not self.driver:
            logging.error("Driver not available, cannot type text via ADB.")
            return False
        if not isinstance(text, str):
             logging.error(f"Invalid text provided for ADB input (must be string): {text}")
             return False

        try:
            # Use shlex.quote to safely escape the text for the shell command
            escaped_text = shlex.quote(text)
            command = f"input text {escaped_text}"
            logging.info(f"Executing ADB shell command: '{command}'")

            # Execute the adb shell command via Appium
            self.driver.execute_script("mobile: shell", {
                'command': 'input',
                'args': ['text', text] # Preferred way if 'args' is supported
                # 'command': command # Fallback if 'args' not supported
            })
            # Note: execute_script might not return a useful success/failure value for shell commands.
            # We assume success if no exception is raised.
            logging.info(f"Successfully executed ADB input text command for: '{text}'")
            return True
        except WebDriverException as e:
            # Specific check for common issues
            if "process didn't end within the specified timeout" in str(e):
                 logging.error(f"ADB command 'input text' timed out. Text: '{text}'. Error: {e}")
            else:
                 logging.error(f"WebDriverException executing ADB 'input text' for '{text}': {e}", exc_info=True)
            return False
        except Exception as e:
            logging.error(f"Unexpected error executing ADB 'input text' for '{text}': {e}", exc_info=True)
            return False

    def is_keyboard_shown(self) -> bool:
        if not self.driver: return False
        try:
            return self.driver.is_keyboard_shown()
        except WebDriverException as e:
            logging.warning(f"Could not determine keyboard state: {e}")
            return False # Assume not shown on error

    def hide_keyboard(self):
        if not self.driver: return
        try:
            self.driver.hide_keyboard()
        except WebDriverException as e:
            # Often throws if keyboard wasn't shown, log as warning
            logging.warning(f"Error hiding keyboard (might be expected if not shown): {e}")

    def perform_action(self, action_type: str, target: Optional[WebElement | str], input_text: Optional[str] = None) -> bool:
        """Performs a given action based on type, target, and optional input text."""
        if not self.driver:
            logging.error("Driver not available, cannot perform action.")
            return False

        success = False
        action_type_lower = action_type.lower()

        try:
            if action_type_lower == "click":
                if isinstance(target, WebElement):
                    success = self.click_element(target)
                else:
                    logging.error(f"Invalid target type for click: {type(target)}. Expected WebElement.")
            elif action_type_lower == "input":
                if isinstance(target, WebElement) and isinstance(input_text, str):
                    success = self.input_text_into_element(target, input_text)
                elif not isinstance(target, WebElement):
                    logging.error(f"Invalid target type for input: {type(target)}. Expected WebElement.")
                elif not isinstance(input_text, str):
                    logging.error(f"Invalid input_text type for input: {type(input_text)}. Expected str.")
            elif action_type_lower == "scroll":
                if isinstance(target, str): # Target here is the direction, e.g., "down", "up"
                    success = self.scroll(direction=target)
                else:
                    logging.error(f"Invalid target type for scroll: {type(target)}. Expected direction string.")
            elif action_type_lower == "back":
                success = self.press_back_button()
            # Add other actions like tap_coordinates, type_text_by_adb if they are to be exposed via perform_action
            # elif action_type_lower == "tap":
            #     if isinstance(target, tuple) and len(target) == 2 and all(isinstance(coord, int) for coord in target):
            #         success = self.tap_coordinates(target[0], target[1])
            #     else:
            #         logging.error(f"Invalid target for tap: {target}. Expected (x,y) tuple of integers.")
            else:
                logging.error(f"Unsupported action type: {action_type}")

        except Exception as e:
            logging.error(f"An unexpected error occurred during perform_action ({action_type}): {e}", exc_info=True)
            success = False

        if success:
            logging.info(f"Action '{action_type_lower}' performed successfully.")
        else:
            logging.warning(f"Action '{action_type_lower}' failed or was not supported with given parameters.")
        
        return success