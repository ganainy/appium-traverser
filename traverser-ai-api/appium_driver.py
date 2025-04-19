import logging
import time
from typing import Optional, Tuple, List, Dict

from appium import webdriver
from appium.options.common.base import AppiumOptions
from selenium.common import WebDriverException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

class AppiumDriver:
    """Wrapper for Appium WebDriver interactions."""

    def __init__(self, server_url: str, config: dict):
        self.server_url = server_url
        self.config = config
        self.driver: Optional[webdriver.Remote] = None

    def connect(self) -> bool:
        """Establishes connection to the Appium server."""
        options = AppiumOptions()
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
            self.driver.implicitly_wait(5) # Small implicit wait
            logging.info("Appium session established successfully.")
            time.sleep(2) # Allow app to fully load
            return True
        except WebDriverException as e:
            logging.error(f"Failed to connect to Appium server: {e}", exc_info=True)
            self.driver = None
            return False
        except Exception as e:
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
        """Clicks a given WebElement."""
        if not element: return False
        try:
            element.click()
            return True
        except WebDriverException as e:
            logging.error(f"Error clicking element: {e}")
            return False

    def input_text_into_element(self, element: WebElement, text: str, click_first: bool = False) -> bool:
        """Clears and inputs text into a given WebElement. Optionally clicks first."""
        if not element: return False
        try:
            if click_first:
                logging.debug("Clicking input element first...")
                element.click()
                time.sleep(0.5) # Short pause after click

            # Clear might be necessary sometimes, try it carefully
            try:
                element.clear()
                time.sleep(0.2)
            except Exception as clear_e:
                logging.warning(f"Could not clear element before input: {clear_e}")
                # Continue anyway, send_keys might overwrite

            element.send_keys(text)
            # Optional: Hide keyboard if it obstructs things (can be device/app specific)
            # try:
            #     self.driver.hide_keyboard()
            # except WebDriverException:
            #     pass # Ignore if hide_keyboard isn't supported or fails
            return True
        except WebDriverException as e:
            logging.error(f"Error inputting text '{text}' into element: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during input_text: {e}", exc_info=True)
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

    def get_current_activity(self) -> Optional[str]:
         if not self.driver: return None
         try:
             return self.driver.current_activity
         except WebDriverException as e:
             logging.warning(f"Could not get current activity: {e}")
             return None

    def get_current_app_context(self) -> Optional[Tuple[str, str]]:
         """Gets the current package and activity."""
         if not self.driver: return None
         try:
             package = self.driver.current_package
             activity = self.driver.current_activity
             return package, activity
         except WebDriverException as e:
             logging.warning(f"Could not get current app context: {e}")
             return None

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