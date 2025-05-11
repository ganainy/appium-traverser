import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .appium_driver import AppiumDriver # To avoid circular import

class AppContextManager:
    """Manages the application context, including launching and ensuring the app is in focus."""

    def __init__(self, driver: 'AppiumDriver', config_dict: dict):
        self.driver = driver
        self.config_dict = config_dict
        self.logger = logging.getLogger(__name__)

    def launch_and_verify_app(self) -> bool:
        """Launches the target application and verifies it is active."""
        target_pkg = self.config_dict.get('APP_PACKAGE')
        target_activity = self.config_dict.get('APP_ACTIVITY')

        if not target_pkg:
            self.logger.critical("Target app package name (APP_PACKAGE) not found in configuration.")
            return False

        self.logger.info(f"Attempting to launch app: {target_pkg}/{target_activity}")
        
        # Check if already running
        current_pkg = self.driver.get_current_package()
        if current_pkg == target_pkg:
            self.logger.info(f"Target app {target_pkg} is already active.")
            return True

        # If not running, launch it
        self.driver.launch_app(target_pkg, target_activity)
        
        # Wait for app to launch and stabilize
        app_launch_wait_time = self.config_dict.get('APP_LAUNCH_WAIT_TIME', 5)
        self.logger.debug(f"Waiting {app_launch_wait_time}s for app to stabilize after launch.")
        time.sleep(app_launch_wait_time)
        
        # Verify again
        current_pkg_after_launch = self.driver.get_current_package()
        current_activity_after_launch = self.driver.get_current_activity()

        if current_pkg_after_launch == target_pkg:
            self.logger.info(f"Successfully launched target app: {target_pkg}/{current_activity_after_launch}")
            return True
        else:
            self.logger.error(f"Failed to launch target app {target_pkg}. Current app is {current_pkg_after_launch}.")
            return False

    def ensure_in_app(self) -> bool:
        """Checks if the driver is focused on the target app or allowed external apps, and attempts recovery."""
        if not self.driver.driver:
            self.logger.error("Driver not connected, cannot ensure app context.")
            return False

        context = self.driver.get_current_app_context()
        if not context:
            self.logger.error("Could not get current app context. Attempting relaunch as fallback.")
            self.driver.relaunch_app() 
            time.sleep(self.config_dict.get('WAIT_AFTER_ACTION', 2))
            context = self.driver.get_current_app_context()
            if not context:
                self.logger.critical("Failed to get app context even after relaunch attempt.")
                return False

        current_package, current_activity = context
        target_package = self.config_dict.get('APP_PACKAGE')
        
        allowed_external_packages = self.config_dict.get('ALLOWED_EXTERNAL_PACKAGES', [])
        allowed_packages = [target_package] + (allowed_external_packages if isinstance(allowed_external_packages, list) else [])

        self.logger.debug(f"Current app context: {current_package} / {current_activity}. Allowed: {allowed_packages}")

        if current_package in allowed_packages:
            self.logger.debug(f"App context OK (In {current_package}).")
            return True
        else:
            self.logger.warning(f"App context incorrect: In '{current_package}', expected one of {allowed_packages}. Attempting recovery.")
            
            # Try pressing back first
            self.driver.press_back_button()
            time.sleep(self.config_dict.get('WAIT_AFTER_ACTION', 2) / 2)

            context_after_back = self.driver.get_current_app_context()
            if context_after_back and context_after_back[0] in allowed_packages:
                self.logger.info("Recovery successful: Returned to target/allowed package after back press.")
                return True
            else:
                self.logger.warning("Recovery failed after back press. Relaunching target application.")
                self.driver.relaunch_app() 
                time.sleep(self.config_dict.get('WAIT_AFTER_ACTION', 5))

                context_after_relaunch = self.driver.get_current_app_context()
                if context_after_relaunch and context_after_relaunch[0] in allowed_packages:
                    self.logger.info("Recovery successful: Relaunched target application.")
                    return True
                else:
                    current_pkg_after_relaunch_fail = context_after_relaunch[0] if context_after_relaunch else "Unknown"
                    self.logger.error(f"Recovery failed: Could not return to target/allowed application. Still in '{current_pkg_after_relaunch_fail}'.")
                    return False
