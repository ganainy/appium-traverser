# app_context_manager.py
import logging
import time
from typing import TYPE_CHECKING, List, Optional

# Import your main Config class and AppiumDriver
# Adjust paths based on your project structure
if TYPE_CHECKING:
    from appium_driver import AppiumDriver  # For type hinting
try:
    from traverser_ai_api.config import Config  # Assuming Config class is in config.py in the same package
except ImportError:
    from traverser_ai_api.config import Config  # Assuming Config class is in config.py in the same package

class AppContextManager:
    """Manages the application context, including launching and ensuring the app is in focus,
    using a centralized Config object."""

    def __init__(self, driver: 'AppiumDriver', app_config: Config): # Changed signature
        """
        Initialize the AppContextManager.

        Args:
            driver (AppiumDriver): An instance of the refactored AppiumDriver.
            app_config (Config): The main application Config object instance.
        """
        self.driver = driver
        self.cfg = app_config # Store the Config object instance
        self.logger = logging.getLogger(__name__)

        # Validate required configuration values from self.cfg
        required_attrs = [
            'APP_PACKAGE', 'APP_ACTIVITY', 'APP_LAUNCH_WAIT_TIME', 
            'WAIT_AFTER_ACTION', 'ALLOWED_EXTERNAL_PACKAGES',
            'MAX_CONSECUTIVE_CONTEXT_FAILURES' # For AppCrawler
        ]
        missing_attrs = []
        for attr_name in required_attrs:
            value = getattr(self.cfg, attr_name, None)
            
            if attr_name == 'ALLOWED_EXTERNAL_PACKAGES':
                if not isinstance(value, list):
                    missing_attrs.append(attr_name)  # Missing or wrong type
            elif value is None:
                missing_attrs.append(attr_name)
        
        if missing_attrs:
            raise ValueError(f"AppContextManager: Missing required configurations in Config object: {', '.join(missing_attrs)}")

        if not self.cfg.APP_PACKAGE or not self.cfg.APP_ACTIVITY: # Specific check
             raise ValueError("AppContextManager: APP_PACKAGE and APP_ACTIVITY cannot be empty in Config.")

        self.consecutive_context_failures: int = 0
        logging.debug(f"AppContextManager initialized for target: {self.cfg.APP_PACKAGE}")

    def reset_context_failures(self):
        """Resets the consecutive context failure counter."""
        if self.consecutive_context_failures > 0: # Only log if there were failures
            self.logger.debug(f"Resetting consecutive context failures from {self.consecutive_context_failures} to 0.")
        self.consecutive_context_failures = 0
        
    def launch_and_verify_app(self) -> bool:
        """Launches the target application (defined in self.cfg) and verifies it is active."""
        target_pkg = str(self.cfg.APP_PACKAGE) 
        # target_activity is used by driver.launch_app() internally from its own cfg

        self.logger.info(f"Attempting to launch and verify app: {target_pkg}")
        
        # Check if already running and in foreground
        current_pkg = self.driver.get_current_package()
        if current_pkg == target_pkg:
            self.logger.info(f"Target app {target_pkg} is already the active foreground package.")
            self.consecutive_context_failures = 0 # Reset on success
            return True
        
        # Try up to 3 times with increasing wait times
        max_attempts = 3
        last_pkg = None
        
        for attempt in range(max_attempts):
            wait_time = (attempt + 1) * float(self.cfg.APP_LAUNCH_WAIT_TIME)
            self.logger.info(f"Launch attempt {attempt + 1}/{max_attempts} with wait time {wait_time}s...")
            
            # If not first attempt, try to close app first
            if attempt > 0:
                try:
                    self.driver.terminate_app(target_pkg)
                    time.sleep(1)  # Short wait after termination
                except Exception as e:
                    self.logger.warning(f"Failed to terminate app before retry: {e}")

            # Attempt to launch
            if not self.driver.launch_app(): 
                self.logger.error(f"Launch attempt {attempt + 1} failed for {target_pkg}")
                continue
            
            # Wait progressively longer
            time.sleep(wait_time)
            
            # Verify launch
            last_pkg = self.driver.get_current_package()
            current_activity = self.driver.get_current_activity()

            if last_pkg == target_pkg:
                self.logger.info(f"Successfully launched target app on attempt {attempt + 1}: {target_pkg}/{current_activity}")
                self.consecutive_context_failures = 0
                return True
            else:
                self.logger.warning(f"Attempt {attempt + 1}: App not in foreground. Current: {last_pkg}")
                
        self.logger.error(f"Failed to launch {target_pkg} after {max_attempts} attempts. Last foreground app: {last_pkg or 'Unknown'}")
        return False

    def ensure_in_app(self) -> bool:
        """
        Checks if the driver is focused on the target app or an allowed external package.
        Attempts recovery by pressing back or relaunching the target app if out of context.
        Returns True if in expected context, False otherwise after recovery attempts.
        """
        if not self.driver.driver: # Check if raw driver is active
            self.logger.error("Driver not connected, cannot ensure app context.")
            self.consecutive_context_failures += 1
            return False

        # Add retry mechanism for context detection
        max_context_retries = 2
        context = None
        
        for retry in range(max_context_retries + 1):
            try:
                context = self.driver.get_current_app_context()
                if context and context[0] is not None:
                    break
            except Exception as e:
                logging.warning(f"Error getting app context (retry {retry}): {e}")
                if retry < max_context_retries:
                    time.sleep(1)
                    continue
        
        if not context or context[0] is None: # Package name is crucial
            self.logger.warning("Could not get app context after retries. Attempting recovery.")
            # Directly try relaunching as the state is unknown
            if self.driver.launch_app(): # Relaunches target app from cfg
                time.sleep(float(self.cfg.WAIT_AFTER_ACTION)) # type: ignore
                context_after_relaunch = self.driver.get_current_app_context()
                if context_after_relaunch and context_after_relaunch[0] == self.cfg.APP_PACKAGE:
                    self.logger.info("Recovery successful: Relaunched target application after unknown context.")
                    self.consecutive_context_failures = 0
                    return True
            self.logger.error("Failed to recover context even after relaunch from unknown state.")
            self.consecutive_context_failures += 1
            return False

        current_package, current_activity = context
        target_package = str(self.cfg.APP_PACKAGE)
        # Ensure ALLOWED_EXTERNAL_PACKAGES is a list and handle if it's None from cfg
        allowed_external_packages: List[str] = self.cfg.ALLOWED_EXTERNAL_PACKAGES or []
        
        allowed_packages_set = set([target_package] + allowed_external_packages)

        self.logger.debug(f"Current app context: {current_package}/{current_activity}. Allowed: {allowed_packages_set}")

        if current_package in allowed_packages_set:
            self.logger.debug(f"App context OK (In '{current_package}').")
            self.consecutive_context_failures = 0 # Reset on success
            return True
        else:
            self.logger.warning(f"App context incorrect: In '{current_package}', expected one of {allowed_packages_set}.")
            self.consecutive_context_failures += 1
            
            if self.consecutive_context_failures >= self.cfg.MAX_CONSECUTIVE_CONTEXT_FAILURES: # type: ignore
                self.logger.error("Maximum consecutive context failures reached. No further recovery attempts this step.")
                return False # Let AppCrawler decide termination

            self.logger.info("Attempting recovery: Pressing back button...")
            self.driver.press_back_button()
            time.sleep(float(self.cfg.WAIT_AFTER_ACTION) / 2) # Shorter wait after back press

            context_after_back = self.driver.get_current_app_context()
            if context_after_back and context_after_back[0] in allowed_packages_set:
                self.logger.info("Recovery successful: Returned to target/allowed package after back press.")
                self.consecutive_context_failures = 0
                return True
            else:
                self.logger.warning(f"Recovery still not successful after back press (current: {context_after_back[0] if context_after_back else 'Unknown'}). Relaunching target application.")
                if self.driver.launch_app(): # Relaunches target app from cfg
                    time.sleep(float(self.cfg.WAIT_AFTER_ACTION)) # type: ignore
                    context_after_relaunch = self.driver.get_current_app_context()
                    if context_after_relaunch and context_after_relaunch[0] in allowed_packages_set:
                        self.logger.info("Recovery successful: Relaunched target application.")
                        self.consecutive_context_failures = 0
                        return True
                
                current_pkg_after_all_attempts = self.driver.get_current_package() or "Unknown"
                self.logger.error(f"All recovery attempts failed. Could not return to target/allowed application. Currently in '{current_pkg_after_all_attempts}'.")
                # consecutive_context_failures already incremented
                return False
