import logging
import shlex # For escaping text in ADB commands
import subprocess
import re
from typing import Optional, List, Dict, Any, Tuple

from appium.webdriver.webdriver import WebDriver as AppiumRemote
from appium.options.android.uiautomator2.base import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import (
    StaleElementReferenceException,
    WebDriverException,
    NoSuchElementException,
    InvalidElementStateException
)
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By # For finding all elements

import time

# Import your main Config class
# Adjust the import path based on your project structure
# from your_project.config import Config # Example if Config is in your_project/config.py
# Assuming it's in a config.py file at the same level or accessible in PYTHONPATH
# For the AppCrawler example, we used 'from .config import Config' implying it's in the same package.
try:
    from traverser_ai_api.config import Config # This assumes AppiumDriver is in the same package as config.py
except ImportError:
    from config import Config # This assumes AppiumDriver is in the same package as config.py

class AppiumDriver:
    """Wrapper for Appium WebDriver interactions, using a centralized Config object."""

    def __init__(self, app_config: Config): # Changed signature
        """
        Initialize the AppiumDriver.

        Args:
            app_config (Config): The main application Config object instance.
        """
        self.cfg = app_config  # Store the Config object instance
        self.driver: Optional[AppiumRemote] = None

        # Validate required configuration values from self.cfg
        required_attrs = [
            'APPIUM_SERVER_URL', 'APP_PACKAGE', 'APP_ACTIVITY',
            'NEW_COMMAND_TIMEOUT', 'APPIUM_IMPLICIT_WAIT',
            'APP_LAUNCH_WAIT_TIME', 'WAIT_AFTER_ACTION',
            'ALLOWED_EXTERNAL_PACKAGES' # Ensure this is a list, even if empty
        ]
        missing_attrs = []
        for attr_name in required_attrs:
            value = getattr(self.cfg, attr_name, None)
            if value is None:
                # For lists like ALLOWED_EXTERNAL_PACKAGES, an empty list is acceptable,
                # but None might indicate it wasn't set. Config class should init to [].
                if attr_name == 'ALLOWED_EXTERNAL_PACKAGES' and isinstance(value, list):
                    continue # Empty list is fine
                missing_attrs.append(attr_name)

        if missing_attrs:
            raise ValueError(f"AppiumDriver: Missing required configurations in Config object: {', '.join(missing_attrs)}")

        if not self.cfg.APPIUM_SERVER_URL: # Specific check for non-empty server URL
            raise ValueError("AppiumDriver: APPIUM_SERVER_URL cannot be empty.")

        logging.debug(f"AppiumDriver initialized for server: {self.cfg.APPIUM_SERVER_URL}")

    def connect(self) -> bool:
        """Establishes connection to the Appium server."""
        if self.driver:
            logging.warning("Appium session already exists. Disconnecting before attempting a new one.")
            self.disconnect()

        udid = self.cfg.TARGET_DEVICE_UDID
        if not udid:
            logging.info("TARGET_DEVICE_UDID not set. Attempting to auto-detect a single connected device.")
            try:
                result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, check=True)
                devices = []
                for line in result.stdout.strip().split('\n')[1:]:
                    if '\tdevice' in line:
                        devices.append(line.split('\t')[0])
                
                if len(devices) == 1:
                    udid = devices[0]
                    logging.info(f"Auto-detected single device: {udid}. Using it for the session.")
                elif len(devices) == 0:
                    logging.error("No ADB devices found. Please connect a device or start an emulator.")
                    return False
                else:
                    logging.error(f"Multiple ADB devices found: {devices}. Please specify one using TARGET_DEVICE_UDID in your config.")
                    return False
            except FileNotFoundError:
                logging.error("'adb' command not found. Please ensure the Android SDK platform-tools are in your system's PATH.")
                return False
            except Exception as e:
                logging.error(f"An error occurred while trying to detect ADB devices: {e}")
                return False

        options = UiAutomator2Options()
        caps = {
            "platformName": "Android",
            "appium:automationName": "UiAutomator2",
            "appium:appPackage": str(self.cfg.APP_PACKAGE),
            "appium:appActivity": str(self.cfg.APP_ACTIVITY),
            "appium:noReset": getattr(self.cfg, 'APPIUM_NO_RESET', True),
            "appium:autoGrantPermissions": getattr(self.cfg, 'APPIUM_AUTO_GRANT_PERMISSIONS', True),
            "appium:newCommandTimeout": int(self.cfg.NEW_COMMAND_TIMEOUT),
            "appium:ensureWebviewsHavePages": True,
            "appium:nativeWebScreenshot": True,
            "appium:connectHardwareKeyboard": True,
        }
        if udid:
            caps["appium:udid"] = udid

        options.load_capabilities(caps)

        try:
            logging.debug(f"Connecting to Appium server at {self.cfg.APPIUM_SERVER_URL} with capabilities: {caps}")
            self.driver = AppiumRemote(command_executor=str(self.cfg.APPIUM_SERVER_URL), options=options)

            implicit_wait_time = int(self.cfg.APPIUM_IMPLICIT_WAIT)
            self.driver.implicitly_wait(implicit_wait_time)
            logging.debug(f"Set Appium implicit wait to {implicit_wait_time} seconds.")
            logging.debug("Appium session established successfully.")
            return True

        except WebDriverException as e:
            logging.error(f"🔴 Failed to connect to Appium server or start session: {e}")
            self.driver = None
            return False
        except Exception as e:
            logging.error(f"🔴 An unexpected error occurred during Appium connection: {e}", exc_info=True)
            self.driver = None
            return False

    def disconnect(self):
        """Quits the Appium driver session."""
        if self.driver:
            try:
                logging.debug("Attempting to quit Appium session...")
                self.driver.quit()
            except WebDriverException as e: # Catch more specific driver errors
                logging.error(f"🔴 WebDriverException during Appium session quit: {e}")
            except Exception as e:
                logging.error(f"🔴 Unexpected error closing Appium session: {e}", exc_info=True)
            finally:
                self.driver = None
                logging.debug("Appium session resources released (driver set to None).")
        else:
            logging.debug("No active Appium session to disconnect.")


    def get_page_source(self) -> Optional[str]:
        """Retrieves the XML page source."""
        if not self.driver:
            logging.warning("⚠️ Driver not available, cannot get page source.")
            return None
        try:
            return self.driver.page_source
        except WebDriverException as e:
            logging.error(f"🔴 Error getting page source: {e}")
            return None
        except Exception as e: # Catch any other unexpected errors
            logging.error(f"🔴 Unexpected error getting page source: {e}", exc_info=True)
            return None


    def get_screenshot_bytes(self) -> Optional[bytes]:
        """Retrieves the current screen screenshot as PNG bytes."""
        if not self.driver:
            logging.warning("Driver not available, cannot get screenshot.")
            return None
        try:
            return self.driver.get_screenshot_as_png()
        except WebDriverException as e:
            logging.error(f"Error taking screenshot: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error taking screenshot: {e}", exc_info=True)
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
        except Exception as e:
            logging.error(f"Unexpected error getting current package: {e}", exc_info=True)
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
        except Exception as e:
            logging.error(f"Unexpected error getting current activity: {e}", exc_info=True)
            return None

    def get_current_app_context(self) -> Optional[Tuple[Optional[str], Optional[str]]]:
        """Retrieves the current application package and activity."""
        current_pkg = self.get_current_package()
        current_act = self.get_current_activity()
        if current_pkg is None and current_act is None:
            logging.warning("Could not retrieve current app context (both package and activity are None).")
            return None
        return current_pkg, current_act

    def launch_app(self) -> bool:
        """
        Launches the application specified in self.cfg.APP_PACKAGE and self.cfg.APP_ACTIVITY,
        with cleanup and verification steps.
        """
        if not self.driver:
            logging.error("Driver not available, cannot launch app.")
            return False

        app_package = str(self.cfg.APP_PACKAGE)
        app_activity = str(self.cfg.APP_ACTIVITY)

        if not app_package or not app_activity:
            logging.error("App package or activity not configured, cannot launch app.")
            return False

        try:
            # Step 1: Terminate app if running
            logging.debug(f"Attempting to terminate {app_package} if running...")
            try:
                self.driver.terminate_app(app_package)
                time.sleep(2)  # Brief wait after termination
            except:
                logging.warning("App termination failed (may not be running)")

            # Step 2: Clear app data via ADB
            logging.debug(f"Clearing app data for {app_package}...")
            try:
                self.driver.execute_script(
                    "mobile: shell",
                    {
                        "command": "pm",
                        "args": ["clear", app_package],
                    },
                )
                time.sleep(2)  # Wait for clear to take effect
            except:
                logging.warning("Failed to clear app data")

            # Step 3: Use Appium's activate_app
            logging.debug(f"Activating app: {app_package}")
            self.driver.activate_app(app_package)

            # Step 4: Wait and verify
            launch_wait = float(self.cfg.APP_LAUNCH_WAIT_TIME)
            logging.debug(f"Waiting {launch_wait}s for app to stabilize...")
            time.sleep(launch_wait)

            # Final verification
            current_pkg_after_launch = self.get_current_package()
            current_act_after_launch = self.get_current_activity()

            if current_pkg_after_launch == app_package:
                logging.debug(f"App {app_package} is now in foreground (Activity: {current_act_after_launch})")
                return True
            elif self.cfg.ALLOWED_EXTERNAL_PACKAGES and current_pkg_after_launch in self.cfg.ALLOWED_EXTERNAL_PACKAGES:
                logging.debug(f"Allowed external package '{current_pkg_after_launch}' present after launch attempt")
                return True
            else:
                logging.warning(f"App launch failed - Current foreground app is '{current_pkg_after_launch}' "
                              f"(activity: '{current_act_after_launch}')")
                return False

        except WebDriverException as e:
            logging.error(f"WebDriverException launching app {app_package}/{app_activity}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error launching app {app_package}/{app_activity}: {e}", exc_info=True)
            return False

    def find_element(self, by: str, value: str, timeout: Optional[float] = None) -> Optional[WebElement]:
        """Finds a single element with an optional explicit timeout."""
        if not self.driver or not value:
            logging.debug(f"Driver not available or value is empty for find_element({by}, {value})")
            return None

        try:
            # For now, direct find (relies on implicit wait set on driver)
            element = self.driver.find_element(by=by, value=value)
            logging.debug(f"Element found using {by}='{value}'")
            return element
        except NoSuchElementException:
            logging.debug(f"Element not found using {by}='{value}'")
            return None
        except WebDriverException as e:
            logging.warning(f"WebDriverException finding element {by}='{value}': {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error finding element {by}='{value}': {e}", exc_info=True)
            return None


    def click_element(self, element: WebElement) -> bool:
        """Clicks a WebElement."""
        if not self.driver or not element:
            logging.warning("Driver not available or element is None, cannot click.")
            return False
        element_id_str = "UnknownElement"
        try:
            element_id_str = element.id # For logging, get before potential stale error
            logging.debug(f"Attempting to click element (ID: {element_id_str})")
            element.click()
            logging.debug(f"Successfully clicked element (ID: {element_id_str})")
            return True
        except StaleElementReferenceException:
            logging.warning(f"Attempted to click a stale element reference (ID was: {element_id_str}).")
            return False
        except WebDriverException as e:
            logging.error(f"WebDriverException clicking element (ID: {element_id_str}): {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error clicking element (ID: {element_id_str}): {e}", exc_info=True)
            return False

    def tap_at_coordinates(self, x: int, y: int, duration: Optional[int] = None) -> bool:
        """Performs a tap action at the specified screen coordinates using W3C Actions API."""
        if not self.driver:
            logging.error("Driver not available, cannot tap at coordinates.")
            return False
        
        # ADD COORDINATE VALIDATION
        window_size = self.get_window_size()
        if window_size:
            max_x, max_y = window_size['width'], window_size['height']
            if x < 0 or y < 0 or x > max_x or y > max_y:
                logging.error(f"Invalid coordinates ({x}, {y}) for screen size {max_x}x{max_y}")
                return False
        
        try:
            from selenium.webdriver.common.actions import interaction
            from selenium.webdriver.common.actions.action_builder import ActionBuilder
            from selenium.webdriver.common.actions.pointer_input import PointerInput

            actual_duration = duration if duration is not None else 100
            logging.debug(f"Attempting tap at coordinates: ({x}, {y}), duration: {actual_duration}ms")

            # Create touch pointer action
            actions = ActionBuilder(self.driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
            
            # Move to the target coordinates
            actions.pointer_action.move_to_location(x, y)
            
            # Perform tap (press and release)
            actions.pointer_action.pointer_down()
            if actual_duration > 0:
                actions.pointer_action.pause(actual_duration / 1000)
            actions.pointer_action.release()
            
            # Execute the action sequence
            actions.perform()
            logging.debug(f"Successfully tapped at coordinates: ({x}, {y})")
            
            # Add a small pause after tap
            time.sleep(0.1)
            
            return True

        except WebDriverException as e:
            logging.error(f"WebDriverException during tap at ({x}, {y}): {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during tap at ({x}, {y}): {e}")
            return False

    def tap_element_center(self, element: WebElement) -> bool:
        """Calculates the center of an element and performs a tap."""
        if not self.driver or not element:
            logging.warning("Driver or element not available for tap_element_center.")
            return False
        try:
            location = element.location
            size = element.size
            center_x = location['x'] + size['width'] // 2
            center_y = location['y'] + size['height'] // 2
            logging.debug(f"Tapping center of element (ID: {element.id}) at coordinates ({center_x}, {center_y})")
            return self.tap_at_coordinates(center_x, center_y)
        except StaleElementReferenceException:
            logging.warning(f"Element became stale before center could be calculated for tap.")
            return False
        except Exception as e:
            logging.error(f"Unexpected error in tap_element_center: {e}", exc_info=True)
            return False
        
    def get_active_element(self) -> Optional[WebElement]:
        """Retrieves the currently active (focused) element on the screen."""
        if not self.driver:
            logging.warning("Driver not available, cannot get active element.")
            return None
        try:
            active_el = self.driver.switch_to.active_element
            if active_el and active_el.id: # Check if it's a valid WebElement
                logging.debug(f"Successfully retrieved active element. ID: {active_el.id}")
                return active_el
            else:
                logging.debug("No active element found or active element is not a valid WebElement.")
                return None
        except NoSuchElementException: # This can be raised if no element is focused
            logging.debug("No active element is currently focused (NoSuchElementException).")
            return None
        except WebDriverException as e:
            logging.warning(f"WebDriverException while trying to get active element: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error getting active element: {e}", exc_info=True)
            return None

    def input_text_into_element(self, element: WebElement, text: str, click_first: bool = True, clear_first: bool = True) -> bool:
        if not self.driver or not element:
            logging.warning("Driver not available or element is None, cannot input text.")
            return False

        element_id_str = "UnknownElementID"
        try:
            element_id_str = element.id
            logging.debug(f"Attempting to input '{text}' into element (ID: {element_id_str})")

            if click_first:
                logging.debug(f"Clicking element (ID: {element_id_str}) to ensure focus before input.")
                if not self.click_element(element):
                    logging.warning(f"Failed to click element (ID: {element_id_str}) before input, but will still attempt input.")
                time.sleep(1.0)

                # --- NEW: Focus Verification Logic ---
                logging.debug(f"Verifying focus on element (ID: {element_id_str}) after click.")
                active_element = self.get_active_element()
                if not active_element or active_element.id != element.id:
                    logging.warning(f"Focus check failed. Element (ID: {element_id_str}) is not the active element after click. Active element ID: {getattr(active_element, 'id', 'None')}.")
                    logging.debug(f"Attempting fallback tap on element (ID: {element_id_str}) to enforce focus.")

                    if self.tap_element_center(element):
                        time.sleep(0.5)  # Wait again after tap
                        active_element = self.get_active_element()  # Re-check focus
                        if not active_element or active_element.id != element.id:
                            logging.error(f"Focus check failed again after tap fallback. Cannot safely input text. Active element ID: {getattr(active_element, 'id', 'None')}.")
                            return False
                        else:
                            logging.debug("Focus successfully established after tap fallback.")
                    else:
                        logging.error("Tap fallback also failed. Cannot safely input text.")
                        return False
                else:
                    logging.debug(f"Focus confirmed on correct element (ID: {element_id_str}).")
                # --- End of New Logic ---

            if clear_first:
                try:
                    logging.debug(f"Clearing element (ID: {element_id_str}) before input.")
                    element.clear()
                    time.sleep(0.1)
                except (InvalidElementStateException, WebDriverException) as clear_err:
                    logging.warning(f"Could not clear element (ID: {element_id_str}) using native method: {clear_err}. Attempting fallback clear.")
                    try:
                        current_text_val = element.get_attribute('text')
                        if current_text_val:
                            for _ in range(len(current_text_val) + 5):
                                element.send_keys(AppiumBy.XPATH, "\uE003")
                            time.sleep(0.1)
                    except Exception as fb_clear_err:
                        logging.warning(f"Fallback clear method also failed for element (ID: {element_id_str}): {fb_clear_err}")
                    return False

            logging.debug(f"Sending keys '{text}' to element (ID: {element_id_str})")
            element.send_keys(text)
            logging.debug(f"Successfully sent keys '{text}' to element (ID: {element_id_str})")

            try:
                if self.is_keyboard_shown():
                    logging.debug("Hiding keyboard after input.")
                    self.hide_keyboard()
            except Exception as kb_err:
                logging.warning(f"Could not hide keyboard after input or check keyboard status: {kb_err}")
            return True
        except StaleElementReferenceException:
            logging.warning(f"Element (ID: {element_id_str}) became stale during input operation.")
            return False
        except InvalidElementStateException as e:
            logging.error(f"Element (ID: {element_id_str}) is not in a state to receive text (e.g., not visible, not enabled): {e}")
            return False
        except WebDriverException as e:
            logging.error(f"WebDriverException inputting text '{text}' into element (ID: {element_id_str}): {e}", exc_info=True)
            return False
        except Exception as e:
            logging.error(f"Unexpected error inputting text '{text}' into element (ID: {element_id_str}): {e}", exc_info=True)
            return False

    def press_back_button(self) -> bool:
        """Presses the Android back button."""
        if not self.driver:
            logging.error("Driver not available, cannot press back button.")
            return False
        try:
            logging.debug("Pressing Android back button (keycode 4).")
            self.driver.press_keycode(4)
            return True
        except WebDriverException as e:
            logging.error(f"Error pressing back button: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error pressing back button: {e}", exc_info=True)
            return False

    def scroll(self, direction: str, element: Optional[WebElement] = None, distance_ratio: float = 0.5) -> bool:
        """Performs a scroll gesture (swipe) on the screen or a specific element if provided."""
        if not self.driver:
            logging.error("Driver not available, cannot scroll.")
            return False
        try:
            start_x, start_y, end_x, end_y = 0, 0, 0, 0

            if element: # Scroll within a specific element
                ele_loc = element.location
                ele_size = element.size
                el_center_x = ele_loc['x'] + ele_size['width'] // 2
                el_center_y = ele_loc['y'] + ele_size['height'] // 2
                el_top_y = ele_loc['y'] + int(ele_size['height'] * 0.2)
                el_bottom_y = ele_loc['y'] + int(ele_size['height'] * 0.8)
                el_left_x = ele_loc['x'] + int(ele_size['width'] * 0.2)
                el_right_x = ele_loc['x'] + int(ele_size['width'] * 0.8)

                if direction == "down":
                    start_x, end_x = el_center_x, el_center_x
                    start_y, end_y = el_bottom_y, el_top_y
                elif direction == "up":
                    start_x, end_x = el_center_x, el_center_x
                    start_y, end_y = el_top_y, el_bottom_y
                elif direction == "left": # Swipe right-to-left within element
                    start_y, end_y = el_center_y, el_center_y
                    start_x, end_x = el_right_x, el_left_x
                elif direction == "right": # Swipe left-to-right within element
                    start_y, end_y = el_center_y, el_center_y
                    start_x, end_x = el_left_x, el_right_x
                else:
                    logging.error(f"Unsupported scroll direction for element scroll: {direction}")
                    return False
            else: # Full screen scroll
                window_size = self.get_window_size()
                if not window_size: return False
                width, height = window_size['width'], window_size['height']

                center_x = width // 2
                center_y = height // 2

                if direction == "down": # Swipe up to scroll content down
                    start_x, end_x = center_x, center_x
                    start_y = int(height * (0.5 + distance_ratio / 2))
                    end_y = int(height * (0.5 - distance_ratio / 2))
                elif direction == "up": # Swipe down to scroll content up
                    start_x, end_x = center_x, center_x
                    start_y = int(height * (0.5 - distance_ratio / 2))
                    end_y = int(height * (0.5 + distance_ratio / 2))
                elif direction == "left": # Swipe right-to-left on screen
                    start_y, end_y = center_y, center_y
                    start_x = int(width * (0.5 + distance_ratio / 2))
                    end_x = int(width * (0.5 - distance_ratio / 2))
                elif direction == "right": # Swipe left-to-right on screen
                    start_y, end_y = center_y, center_y
                    start_x = int(width * (0.5 - distance_ratio / 2))
                    end_x = int(width * (0.5 + distance_ratio / 2))
                else:
                    logging.error(f"Unsupported scroll direction for full screen: {direction}")
                    return False

            if start_y == end_y and start_x == end_x:
                logging.warning(f"Scroll calculation resulted in zero distance for direction '{direction}'. Skipping swipe.")
                return False

            logging.debug(f"Scrolling {direction} from ({start_x},{start_y}) to ({end_x},{end_y})")
            self.driver.swipe(start_x, start_y, end_x, end_y, duration=max(200, int(800 * distance_ratio)))
            return True
        except StaleElementReferenceException:
            logging.warning(f"Stale element encountered during scroll setup for element: {element}")
            return False
        except WebDriverException as e:
            logging.error(f"Error performing scroll {direction}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during scroll: {e}", exc_info=True)
            return False

    from typing import Sequence
    def get_all_elements(self) -> Sequence[WebElement]:
        """Gets all elements on the current screen using XPath '//*'."""
        if not self.driver:
            logging.warning("Driver not available, cannot get all elements.")
            return []
        try:
            return self.driver.find_elements(by=By.XPATH, value="//*")
        except WebDriverException as e:
            logging.error(f"Error getting all elements: {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error getting all elements: {e}", exc_info=True)
            return []


    def get_element_attributes(self, element: WebElement, attributes: List[str]) -> Dict[str, Optional[str]]:
        """Safely gets multiple attributes for a given element."""
        element_attrs: Dict[str, Optional[str]] = {}
        if not element:
            logging.debug("get_element_attributes called with None element.")
            return element_attrs

        for attr in attributes:
            val = None # Default to None if attribute cannot be fetched
            try:
                if attr == 'text': val = element.text
                elif attr == 'displayed': val = str(element.is_displayed()).lower()
                elif attr == 'enabled': val = str(element.is_enabled()).lower()
                elif attr == 'selected': val = str(element.is_selected()).lower()
                elif attr == 'resource-id': val = element.get_attribute('resourceId')
                elif attr == 'content-desc': val = element.get_attribute('contentDescription')
                else: val = element.get_attribute(attr)
            except StaleElementReferenceException:
                logging.warning(f"Stale element while getting attribute '{attr}'.")
                val = "STALE_ELEMENT" # Indicate staleness
                element_attrs[attr] = val # Store special value
                break # Stop trying to get other attributes for this stale element
            except Exception as e_attr:
                logging.debug(f"Could not get attribute '{attr}': {e_attr}")
                # val remains None
            element_attrs[attr] = val
        return element_attrs

    def get_window_size(self) -> Optional[Dict[str, int]]:
        """Gets the current device window size."""
        if not self.driver:
            logging.warning("Driver not available, cannot get window size.")
            return None
        try:
            size = self.driver.get_window_size()
            if size and 'width' in size and 'height' in size and \
               isinstance(size['width'], int) and isinstance(size['height'], int) and \
               size['width'] > 0 and size['height'] > 0:
                return {'width': size['width'], 'height': size['height']}
            else:
                logging.error(f"Received invalid window size data: {size}")
                return None
        except WebDriverException as e:
            logging.error(f"Error getting window size: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error getting window size: {e}", exc_info=True)
            return None

    def type_text_by_adb(self, text: str) -> bool:
        """Simulates typing text using ADB 'input text' command."""
        if not self.driver:
            logging.error("Driver not available, cannot type text via ADB.")
            return False
        if not isinstance(text, str):
            logging.error(f"Invalid text provided for ADB input (must be string): '{text}'")
            return False
        try:
            # Using 'args' parameter for mobile: shell is generally safer for special characters
            logging.debug(f"Executing ADB input text: '{text}'")
            self.driver.execute_script("mobile: shell", {
                'command': 'input',
                'args': ['text', text]
            })
            return True
        except WebDriverException as e:
            logging.error(f"WebDriverException executing ADB 'input text' for '{text}': {e}", exc_info=True)
            return False
        except Exception as e:
            logging.error(f"Unexpected error executing ADB 'input text' for '{text}': {e}", exc_info=True)
            return False

    def is_keyboard_shown(self) -> bool:
        """Checks if the software keyboard is currently shown."""
        if not self.driver:
            logging.warning("Driver not available, assuming keyboard not shown.")
            return False
        try:
            return self.driver.is_keyboard_shown()
        except WebDriverException as e:
            logging.warning(f"Could not determine keyboard state (may not be supported by driver/platform): {e}")
            return False # Assume not shown on error
        except Exception as e:
            logging.error(f"Unexpected error checking keyboard status: {e}", exc_info=True)
            return False


    def hide_keyboard(self):
        """Hides the software keyboard if it is shown."""
        if not self.driver:
            logging.warning("Driver not available, cannot hide keyboard.")
            return
        try:
            if self.is_keyboard_shown(): # Check first
                self.driver.hide_keyboard()
                logging.debug("hide_keyboard command sent.")
            else:
                logging.debug("Keyboard not shown, no need to hide.")
        except WebDriverException as e:
            logging.warning(f"Error hiding keyboard (might be expected if not shown or not supported): {e}")
        except Exception as e:
            logging.error(f"Unexpected error hiding keyboard: {e}", exc_info=True)

    def perform_action(self, action_type: str, target: Optional[Any], input_text: Optional[str] = None) -> bool:
        """
        Performs a given action based on type, target, and optional input text.
        'target' can be WebElement for click/input, direction string for scroll,
        or (x,y) tuple for tap.
        """
        if not self.driver:
            logging.error("Driver not available, cannot perform action.")
            return False

        success = False
        action_type_lower = action_type.lower()
        logging.debug(f"Attempting to perform action: Type='{action_type_lower}', Target='{str(target)[:50]}', Input='{input_text}'")

        try:
            if action_type_lower == "click":
                if isinstance(target, WebElement):
                    success = self.click_element(target)
                else:
                    logging.error(f"Invalid target type for click: {type(target)}. Expected WebElement.")
            elif action_type_lower == "input":
                if isinstance(target, WebElement) and input_text is not None: # Ensure input_text is provided
                    success = self.input_text_into_element(target, input_text)
                elif not isinstance(target, WebElement):
                    logging.error(f"Invalid target type for input: {type(target)}. Expected WebElement.")
                elif input_text is None:
                     logging.error(f"Input text is None for 'input' action. This might be for clearing, but needs explicit handling if so.")
            elif action_type_lower == "scroll": # Handles "scroll_down" and "scroll_up" if target is the direction string
                if isinstance(target, str) and target in ["down", "up", "left", "right"]:
                    success = self.scroll(direction=target) # Element for scroll is optional in self.scroll
                else:
                    logging.error(f"Invalid target for scroll: '{target}'. Expected direction string (down, up, etc.).")
            elif action_type_lower == "back":
                success = self.press_back_button()
            elif action_type_lower == "tap_coords": # Specific action for coordinate tap
                if isinstance(target, tuple) and len(target) == 2 and all(isinstance(coord, int) for coord in target):
                    success = self.tap_at_coordinates(target[0], target[1])
                else:
                    logging.error(f"Invalid target for tap_coords: {target}. Expected (x,y) tuple of integers.")
            else:
                logging.error(f"Unsupported action type in perform_action: '{action_type}'")

        except Exception as e:
            logging.error(f"An unexpected error occurred during perform_action ('{action_type}'): {e}", exc_info=True)
            success = False

        if success:
            logging.debug(f"Action '{action_type_lower}' performed successfully on target '{str(target)[:50]}'.")
        else:
            logging.warning(f"Action '{action_type_lower}' failed or was not supported with target '{str(target)[:50]}'.")

        return success

    def terminate_app(self, package_name: str) -> bool:
        """Terminates the given app if it's running.

        Args:
            package_name: The package name of the app to terminate.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            if not self.driver:
                logging.error("No active Appium session")
                return False

            if self.driver.terminate_app(package_name):
                logging.debug(f"Successfully terminated app: {package_name}")
                return True
            else:
                logging.warning(f"App termination returned False for: {package_name}")
                return False
        except Exception as e:
            logging.error(f"Error terminating app {package_name}: {e}")
            return False