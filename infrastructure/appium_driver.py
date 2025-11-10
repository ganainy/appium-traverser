"""
Appium driver wrapper for direct Appium-Python-Client integration.

Provides a high-level interface for Appium operations using AppiumHelper.
"""

import base64
import logging
import time
from typing import Any, Dict, Optional, Tuple

from config.app_config import Config
from infrastructure.appium_helper import AppiumHelper
from infrastructure.device_detection import (
    detect_all_devices,
    select_best_device,
    validate_device,
    DeviceInfo,
    Platform,
)
from infrastructure.capability_builder import (
    build_android_capabilities,
    AppiumCapabilities,
)
from infrastructure.appium_error_handler import AppiumError, validate_coordinates

logger = logging.getLogger(__name__)


class AppiumDriver:
    """High-level Appium driver wrapper."""
    
    def __init__(self, app_config: Config):
        """
        Initialize AppiumDriver.
        
        Args:
            app_config: Application configuration
        """
        self.cfg = app_config
        self.helper: Optional[AppiumHelper] = None
        self._session_initialized = False
        self._session_info: Optional[Dict[str, Any]] = None
        logger.debug("AppiumDriver initialized.")
    
    def disconnect(self):
        """Disconnect Appium helper and close session."""
        if self.helper:
            try:
                if self._session_initialized:
                    try:
                        self.helper.close_driver()
                    except Exception as e:
                        logger.warning(f"Error closing Appium session: {e}")
                    finally:
                        self._session_initialized = False
                        self._session_info = None
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.helper = None
        logger.debug("AppiumDriver disconnected.")
    
    def _ensure_helper(self) -> bool:
        """Ensure AppiumHelper is initialized."""
        if not self.helper:
            # Create helper with config values
            max_retries = self.cfg.get('APPIUM_MAX_RETRIES', 3)
            retry_delay = self.cfg.get('APPIUM_RETRY_DELAY', 1.0)
            implicit_wait = self.cfg.get('APPIUM_IMPLICIT_WAIT', 10000)
            
            self.helper = AppiumHelper(
                max_retries=max_retries,
                retry_delay=retry_delay,
                implicit_wait=implicit_wait
            )
        return True
    
    def initialize_session(
        self,
        app_package: Optional[str] = None,
        app_activity: Optional[str] = None,
        device_udid: Optional[str] = None,
        platform_name: str = "Android"
    ) -> bool:
        """
        Initialize Appium session with device auto-detection.
        
        Args:
            app_package: Android app package name
            app_activity: Android app activity name
            device_udid: Device UDID (optional, will auto-detect if not provided)
            platform_name: Platform name ("Android")
            
        Returns:
            True if session initialized successfully, False otherwise
        """
        if not self._ensure_helper():
            return False
        
        try:
            # Detect available devices
            all_devices = detect_all_devices()
            if not all_devices:
                logger.error(
                    "No devices found. Please ensure:\n"
                    "- Android: Android SDK is installed and devices/emulators are connected"
                )
                return False
            
            # Select best device
            platform: Platform = 'android'
            selected_device = select_best_device(
                all_devices,
                platform,
                None  # device_name
            )
            
            if not selected_device:
                logger.error(
                    f"No suitable {platform_name} device found. Available devices:\n" +
                    "\n".join(f"- {d.name} ({d.platform}, {d.type})" for d in all_devices)
                )
                return False
            
            # Override with explicit UDID if provided
            if device_udid:
                for device in all_devices:
                    if device.id == device_udid:
                        selected_device = device
                        break
                else:
                    logger.warning(f"Device with UDID {device_udid} not found, using auto-selected device")
            
            # Validate device is ready
            if not validate_device(selected_device):
                logger.error(
                    f"Device {selected_device.name} is not ready for automation.\n"
                    "Please ensure the device is responsive and try again."
                )
                return False
            
            # Set device UDID and name in path manager for session path generation (before session path is accessed)
            # This ensures the output directory uses the correct device ID instead of "unknown_device"
            # Prefer device name over UDID for folder names (more readable)
            if hasattr(self.cfg, '_path_manager'):
                # Set device info in path manager (this will invalidate cached session path)
                self.cfg._path_manager.set_device_info(udid=selected_device.id, name=selected_device.name)
                logger.debug(f"Set device info in path manager: UDID={selected_device.id}, Name={selected_device.name}")
                
                # Get the session path (it will be generated with the correct device info)
                session_path = self.cfg._path_manager.get_session_path(force_regenerate=False)
                if session_path:
                    logger.debug(f"Session path: {session_path}")
                else:
                    # Path not created yet, this is OK - it will be created when needed
                    logger.debug("Session path not created yet (device info may not be set)")
            
            # Build capabilities for Android
            capabilities = build_android_capabilities(
                selected_device,
                app_package=app_package,
                app_activity=app_activity,
                app=None,  # Could be added as parameter
                additional_caps={
                    'appium:noReset': True,
                }
            )
            
            # Get allowed external packages from config
            allowed_external_packages = self.cfg.get('ALLOWED_EXTERNAL_PACKAGES')
            if allowed_external_packages:
                if isinstance(allowed_external_packages, str):
                    allowed_external_packages = [
                        pkg.strip() for pkg in allowed_external_packages.split('\n')
                        if pkg.strip()
                    ]
                elif isinstance(allowed_external_packages, (list, tuple)):
                    allowed_external_packages = [
                        str(pkg).strip() for pkg in allowed_external_packages
                        if pkg and str(pkg).strip()
                    ]
                else:
                    allowed_external_packages = []
            
            # Get Appium server URL
            from config.urls import ServiceURLs
            appium_url = self.cfg.get('APPIUM_SERVER_URL', ServiceURLs.APPIUM)
            
            # Initialize session with app context configuration
            context_config = {
                'targetPackage': app_package,
                'targetActivity': app_activity,
                'allowedExternalPackages': allowed_external_packages or []
            }
            
            self.helper.initialize_driver(
                capabilities,
                appium_url,
                context_config
            )
            
            self._session_initialized = True
            session_state = self.helper.get_session_state()
            self._session_info = {
                'sessionId': session_state.session_id,
                'platform': selected_device.platform,
                'device': selected_device.name,
                'udid': selected_device.id,
            }
            
            logger.debug(f"[OK] Appium session initialized: {session_state.session_id}")
            logger.debug(f"Session data: {self._session_info}")
            return True
            
        except AppiumError as e:
            logger.error(f"Appium error initializing session: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error initializing session: {e}", exc_info=True)
            return False
    
    def validate_session(self) -> bool:
        """Validate that the current session is still active."""
        if not self._ensure_helper():
            return False
        
        try:
            is_valid = self.helper.validate_session()
            if not is_valid:
                self._session_initialized = False
                self._session_info = None
            return is_valid
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            self._session_initialized = False
            return False
    
    def get_page_source(self) -> Optional[str]:
        """Get page source."""
        if not self._ensure_helper():
            return None
        
        try:
            return self.helper.get_page_source()
        except Exception as e:
            logger.error(f"Error getting page source: {e}")
            return None
    
    def get_screenshot_as_base64(self) -> Optional[str]:
        """Get screenshot as base64 string."""
        if not self._ensure_helper():
            return None
        
        try:
            screenshot = self.helper.take_screenshot()
            # Screenshot is already base64 from Appium-Python-Client
            if screenshot.startswith("data:image"):
                screenshot = screenshot.split(",", 1)[1]
            return screenshot
        except Exception as e:
            logger.error(f"Error getting screenshot: {e}")
            return None
    
    def tap(
        self,
        target_identifier: Optional[str],
        bbox: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Tap element or coordinates.
        
        Args:
            target_identifier: Element identifier (optional if bbox provided)
            bbox: Bounding box with 'top_left' and 'bottom_right' (optional if target_identifier provided)
            
        Returns:
            True if tap successful
        """
        if not self._ensure_helper():
            return False
        
        try:
            # Prefer coordinates (bbox) if available
            if bbox and isinstance(bbox, dict):
                top_left = bbox.get("top_left", [])
                bottom_right = bbox.get("bottom_right", [])
                if len(top_left) == 2 and len(bottom_right) == 2:
                    # Calculate center coordinates
                    x = (top_left[1] + bottom_right[1]) / 2
                    y = (top_left[0] + bottom_right[0]) / 2
                    
                    # Get window size for coordinate validation
                    window_size = self.helper.get_window_size()
                    coords = validate_coordinates(
                        x, y,
                        window_size['width'],
                        window_size['height']
                    )
                    
                    # Perform tap at coordinates using W3C Actions
                    self.helper.perform_w3c_tap(coords['x'], coords['y'])
                    logger.debug(f"Tapped at coordinates ({coords['x']}, {coords['y']}) from bbox")
                    return True
            
            # Fall back to element lookup if no coordinates or coordinates failed
            if target_identifier:
                return self.helper.tap_element(target_identifier, strategy='id')
            
            logger.error("tap() called without target_identifier or bbox")
            return False
            
        except Exception as e:
            logger.error(f"Error during tap: {e}")
            return False
    
    def input_text(self, target_identifier: str, text: str) -> bool:
        """Input text into element."""
        if not self._ensure_helper():
            return False
        
        try:
            return self.helper.send_keys(target_identifier, text, strategy='id')
        except Exception as e:
            logger.error(f"Error during input_text: {e}")
            return False
    
    def scroll(self, direction: str) -> bool:
        """
        Scroll in specified direction.
        
        Args:
            direction: Scroll direction ('up', 'down', 'left', 'right')
            
        Returns:
            True if scroll successful
        """
        if not self._ensure_helper():
            return False
        
        try:
            # Get window size
            window_size = self.helper.get_window_size()
            width = window_size['width']
            height = window_size['height']
            
            # Calculate scroll coordinates based on direction
            direction_lower = direction.lower()
            if direction_lower == 'up':
                start_x, start_y = width / 2, height * 0.8
                end_x, end_y = width / 2, height * 0.2
            elif direction_lower == 'down':
                start_x, start_y = width / 2, height * 0.2
                end_x, end_y = width / 2, height * 0.8
            elif direction_lower == 'left':
                start_x, start_y = width * 0.8, height / 2
                end_x, end_y = width * 0.2, height / 2
            elif direction_lower == 'right':
                start_x, start_y = width * 0.2, height / 2
                end_x, end_y = width * 0.8, height / 2
            else:
                logger.error(f"Invalid scroll direction: {direction}")
                return False
            
            # Perform swipe for scrolling
            driver = self.helper.get_driver()
            if driver:
                from selenium.webdriver.common.action_chains import ActionChains
                from selenium.webdriver.common.actions import interaction
                from selenium.webdriver.common.actions.action_builder import ActionBuilder
                from selenium.webdriver.common.actions.pointer_input import PointerInput
                
                actions = ActionChains(driver)
                actions.w3c_actions = ActionBuilder(
                    driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch")
                )
                actions.w3c_actions.pointer_action.move_to_location(start_x, start_y)
                actions.w3c_actions.pointer_action.pointer_down()
                actions.w3c_actions.pointer_action.move_to_location(end_x, end_y)
                actions.w3c_actions.pointer_action.pause(0.8)
                actions.w3c_actions.pointer_action.pointer_up()
                actions.perform()
                
                logger.debug(f"Scrolled {direction} from ({start_x}, {start_y}) to ({end_x}, {end_y})")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error during scroll: {e}")
            return False
    
    def long_press(self, target_identifier: str, duration: int) -> bool:
        """
        Long press element.
        
        Args:
            target_identifier: Element identifier
            duration: Press duration in milliseconds
            
        Returns:
            True if successful
        """
        if not self._ensure_helper():
            return False
        
        try:
            # Find element and get its center
            element = self.helper.find_element(target_identifier, strategy='id')
            x, y = self.helper._get_element_center(element)
            
            # Perform long press using W3C Actions with longer duration
            driver = self.helper.get_driver()
            if driver:
                from selenium.webdriver.common.action_chains import ActionChains
                from selenium.webdriver.common.actions import interaction
                from selenium.webdriver.common.actions.action_builder import ActionBuilder
                from selenium.webdriver.common.actions.pointer_input import PointerInput
                
                actions = ActionChains(driver)
                actions.w3c_actions = ActionBuilder(
                    driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch")
                )
                actions.w3c_actions.pointer_action.move_to_location(x, y)
                actions.w3c_actions.pointer_action.pointer_down()
                actions.w3c_actions.pointer_action.pause(duration / 1000.0)
                actions.w3c_actions.pointer_action.pointer_up()
                actions.perform()
                
                logger.debug(f"Long pressed element {target_identifier} for {duration}ms")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error during long_press: {e}")
            return False
    
    def press_back(self) -> bool:
        """Press back button."""
        if not self._ensure_helper():
            logger.error("Cannot press back: AppiumHelper not available")
            return False
        
        try:
            driver = self.helper.get_driver()
            if driver:
                driver.back()
                logger.debug("[OK] Back press succeeded")
                return True
            return False
        except Exception as e:
            logger.error(f"[ERROR] Error during press_back: {e}", exc_info=True)
            return False
    
    def press_home(self) -> bool:
        """Press home button."""
        if not self._ensure_helper():
            return False
        
        try:
            driver = self.helper.get_driver()
            if driver:
                # Use Appium's press_keycode for Android HOME key (3)
                driver.press_keycode(3)
                logger.debug("Home button pressed")
                return True
            return False
        except Exception as e:
            logger.error(f"Error during press_home: {e}")
            return False
    
    def wait_for_toast_to_dismiss(self, timeout_ms: int = 1200):
        """Wait for toast to dismiss."""
        time.sleep(timeout_ms / 1000.0)
    
    def get_window_size(self) -> Dict[str, int]:
        """Get window size."""
        if not self._ensure_helper():
            return {"width": 1080, "height": 1920}  # Default fallback
        
        try:
            return self.helper.get_window_size()
        except Exception as e:
            logger.error(f"Error getting window size: {e}")
            return {"width": 1080, "height": 1920}
    
    def start_video_recording(self, **kwargs) -> bool:
        """
        Starts recording the screen using Appium's built-in method.
        
        Args:
            **kwargs: Optional recording options to pass to start_recording_screen()
            
        Returns:
            True if recording started successfully, False otherwise
        """
        if not self._ensure_helper():
            logger.error("Cannot start video recording: AppiumHelper not available")
            return False
        
        try:
            driver = self.helper.get_driver()
            if not driver:
                logger.error("Cannot start video recording: Driver not available")
                return False
            
            driver.start_recording_screen(**kwargs)
            logger.info("Started video recording.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start video recording: {e}", exc_info=True)
            return False
    
    def stop_video_recording(self) -> Optional[str]:
        """
        Stops recording the screen and returns the video data as base64 string.
        
        Returns:
            Video data as base64-encoded string, or None on error
        """
        if not self._ensure_helper():
            logger.error("Cannot stop video recording: AppiumHelper not available")
            return None
        
        try:
            driver = self.helper.get_driver()
            if not driver:
                logger.error("Cannot stop video recording: Driver not available")
                return None
            
            video_data = driver.stop_recording_screen()
            logger.info("Stopped video recording.")
            return video_data
            
        except Exception as e:
            logger.error(f"Failed to stop video recording: {e}", exc_info=True)
            return None
    
    def save_video_recording(self, video_data: str, file_path: str) -> bool:
        """Saves the video data to a file.
        
        Args:
            video_data: Video data as base64-encoded string
            file_path: Path to save the video file
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not video_data:
            logger.error("Video data is empty, cannot save video.")
            return False
        
        try:
            import os
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(video_data))
            
            logger.info(f"Video saved to: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save video to {file_path}: {e}", exc_info=True)
            return False
    
    def get_current_package(self) -> Optional[str]:
        """Get current package name (Android only)."""
        if not self._ensure_helper():
            return None
        
        try:
            return self.helper.get_current_package()
        except Exception as e:
            logger.warning(f"Error getting current package: {e}")
            return None
    
    def get_current_activity(self) -> Optional[str]:
        """Get current activity name (Android only)."""
        if not self._ensure_helper():
            return None
        
        try:
            return self.helper.get_current_activity()
        except Exception as e:
            logger.error(f"Error getting current activity: {e}")
            return None
    
    def get_current_app_context(self) -> Optional[Tuple[Optional[str], Optional[str]]]:
        """Get current app context (package, activity)."""
        package = self.get_current_package()
        activity = self.get_current_activity()
        return package, activity
    
    def terminate_app(self, package_name: str) -> bool:
        """Terminate app."""
        if not self._ensure_helper():
            return False
        
        try:
            driver = self.helper.get_driver()
            if driver:
                driver.terminate_app(package_name)
                logger.debug(f"Terminated app: {package_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error terminating app: {e}")
            return False
    
    def launch_app(self) -> bool:
        """Launch app."""
        if not self._ensure_helper():
            return False
        
        try:
            driver = self.helper.get_driver()
            if driver:
                driver.launch_app()
                logger.debug("App launched")
                return True
            return False
        except Exception as e:
            logger.error(f"Error launching app: {e}")
            return False
    
    def start_activity(
        self,
        app_package: str,
        app_activity: str,
        wait_after_launch: float = 5.0
    ) -> bool:
        """
        Start an Android app activity.
        
        Args:
            app_package: Android app package name
            app_activity: Android app activity name
            wait_after_launch: Time to wait after launching activity (seconds)
            
        Returns:
            True if activity was started successfully, False otherwise
        """
        if not self._ensure_helper():
            return False
        
        try:
            wait_ms = int(wait_after_launch * 1000)
            success = self.helper.start_activity(app_package, app_activity, wait_ms)
            if success:
                logger.debug(f"Successfully started activity: {app_package}/{app_activity}")
            return success
        except Exception as e:
            logger.error(f"Error starting activity: {e}")
            return False
    
    def press_back_button(self) -> bool:
        """Press back button (alias for press_back)."""
        return self.press_back()
