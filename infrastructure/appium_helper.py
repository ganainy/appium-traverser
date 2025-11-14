"""
Core Appium helper class.

Provides W3C WebDriver client with session management and error recovery using Appium-Python-Client.
"""

import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal
from urllib.parse import urlparse

from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from appium.options.android import UiAutomator2Options
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementNotInteractableException,
    InvalidSelectorException,
    WebDriverException,
)

from infrastructure.appium_error_handler import (
    AppiumError,
    SessionNotFoundError,
    ElementNotFoundError,
    GestureFailedError,
    is_session_terminated,
    validate_coordinates,
    with_retry_sync,
)
from infrastructure.capability_builder import AppiumCapabilities
from infrastructure.device_detection import Platform, DeviceInfo

logger = logging.getLogger(__name__)

LocatorStrategy = Literal[
    'id', 'xpath', 'accessibility id', 'class name', 'css selector',
    'tag name', 'link text', 'partial link text', 'name',
    'android uiautomator'
]


@dataclass
class ActionHistory:
    """Action history entry."""
    action: str
    target: str
    success: bool
    timestamp: float
    duration: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class SessionState:
    """Current session state."""
    driver: Optional[Any] = None
    current_platform: Optional[Platform] = None
    current_device: Optional[DeviceInfo] = None
    session_id: Optional[str] = None
    last_capabilities: Optional[AppiumCapabilities] = None
    last_appium_url: Optional[str] = None
    action_history: List[ActionHistory] = field(default_factory=list)


class AppiumHelper:
    """Core Appium helper for session management and device interaction."""
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        implicit_wait: int = 5000
    ):
        """
        Initialize AppiumHelper.
        
        Args:
            max_retries: Maximum retry attempts for operations
            retry_delay: Delay between retries in seconds
            implicit_wait: Implicit wait timeout in milliseconds
        """
        self.driver: Optional[webdriver.Remote] = None
        self.last_capabilities: Optional[AppiumCapabilities] = None
        self.last_appium_url: Optional[str] = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.implicit_wait = implicit_wait
        self._current_implicit_wait: Optional[float] = None  # Track current implicit wait in seconds
        self.action_history: List[ActionHistory] = []
        
        # App context tracking
        self.target_package: Optional[str] = None
        self.target_activity: Optional[str] = None
        self.allowed_external_packages: List[str] = []
        self.consecutive_context_failures: int = 0
        self.max_consecutive_context_failures: int = 3
    
    def initialize_driver(
        self,
        capabilities: AppiumCapabilities,
        appium_url: str = 'http://localhost:4723',
        context_config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize WebDriver session with capabilities.
        
        Args:
            capabilities: Appium capabilities dictionary
            appium_url: Appium server URL
            context_config: App context configuration (targetPackage, targetActivity, allowedExternalPackages)
        """
        start_time = time.time()
        
        try:
            logger.debug(
                f'Initializing Appium session: platform={capabilities.get("platformName")}, '
                f'automationName={capabilities.get("appium:automationName")}, '
                f'deviceName={capabilities.get("appium:deviceName")}'
            )
            
            # Parse URL - ensure we use just the base URL without path
            parsed_url = urlparse(appium_url)
            # Remove any path from URL, use just scheme://host:port
            server_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Create Android/UiAutomator2 options
            options = UiAutomator2Options()
            
            # Log capabilities for debugging
            logger.debug(f'Loading capabilities: {list(capabilities.keys())}')
            
            # Load all capabilities into options object
            # load_capabilities accepts a dict and returns the options object
            # It handles both appium: prefixed and non-prefixed keys
            try:
                options.load_capabilities(capabilities)
            except Exception as load_error:
                logger.warning(f'load_capabilities failed, trying direct assignment: {load_error}')
                # Fallback: try setting capabilities directly
                # Convert appium: prefixed keys to option attributes
                for key, value in capabilities.items():
                    if value is not None:
                        try:
                            # Try with appium: prefix first
                            if hasattr(options, key):
                                setattr(options, key, value)
                            # Try without appium: prefix
                            elif key.startswith('appium:'):
                                option_key = key.replace('appium:', '')
                                if hasattr(options, option_key):
                                    setattr(options, option_key, value)
                        except Exception:
                            # If direct assignment fails, continue
                            pass
            
            logger.debug(f'Server URL: {server_url}')
            
            # Create driver with options
            self.driver = webdriver.Remote(
                command_executor=server_url,
                options=options
            )
            
            self.last_capabilities = capabilities
            self.last_appium_url = appium_url
            
            # Store app context information
            if context_config:
                self.target_package = context_config.get('targetPackage')
                self.target_activity = context_config.get('targetActivity')
                self.allowed_external_packages = context_config.get('allowedExternalPackages', [])
            else:
                # Extract from capabilities if not provided
                self.target_package = capabilities.get('appium:appPackage')
                self.target_activity = capabilities.get('appium:appActivity')
                self.allowed_external_packages = []
            
            self.consecutive_context_failures = 0
            
            # Set implicit wait
            implicit_wait_seconds = self.implicit_wait / 1000.0  # Convert ms to seconds
            self.driver.implicitly_wait(implicit_wait_seconds)
            self._current_implicit_wait = implicit_wait_seconds  # Track the current value
            
            # Apply performance-optimizing driver settings
            self._apply_performance_settings()
            
            duration = (time.time() - start_time) * 1000
            session_id = self.driver.session_id
            
            logger.debug(
                f'Appium session initialized successfully: sessionId={session_id}, '
                f'duration={duration:.0f}ms'
            )
            
        except Exception as error:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f'Failed to initialize Appium session: {error}, duration={duration:.0f}ms'
            )
            raise AppiumError(
                f'Failed to initialize Appium session: {error}',
                'SESSION_INIT_FAILED',
                {'error': str(error)}
            )
    
    def _apply_performance_settings(self) -> None:
        """
        Apply performance-optimizing driver settings after session initialization.
        
        These settings dramatically improve element finding speed by:
        - Disabling idle waiting (waitForIdleTimeout: 0)
        - Limiting XML tree depth (snapshotMaxDepth)
        - Filtering non-interactive elements (ignoreUnimportantViews)
        """
        if not self.driver:
            return
        
        try:
            # Get performance settings from config if available, otherwise use defaults
            # Note: These settings are applied via driver.update_settings() after session init
            # The capabilities we set earlier may not work for all settings, so we apply them here too
            performance_settings = {
                'waitForIdleTimeout': 0,  # Disable idle waiting for faster element finding
                'snapshotMaxDepth': 25,  # Limit XML tree depth to reduce scanning overhead
                'ignoreUnimportantViews': True,  # Filter out non-interactive elements
            }
            
            # Update driver settings
            self.driver.update_settings(performance_settings)
            logger.debug(f'Applied performance settings: {performance_settings}')
        except Exception as error:
            # Non-critical - log warning but don't fail
            logger.warning(f'Failed to apply performance settings: {error}')
    
    def validate_session(self) -> bool:
        """
        Validate if current session is still active.
        
        Returns:
            True if session is valid, False otherwise
        """
        if not self.driver:
            return False
        
        try:
            # Try to get page source to validate session
            self.driver.page_source
            return True
        except Exception as error:
            if is_session_terminated(error):
                logger.warning('Session terminated, attempting recovery...')
                return self._attempt_session_recovery()
            return False
    
    def _attempt_session_recovery(self) -> bool:
        """
        Attempt to recover from session termination.
        
        Returns:
            True if recovery successful, False otherwise
        """
        if not self.last_capabilities or not self.last_appium_url:
            logger.error('Cannot recover session: missing capabilities or URL')
            return False
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f'Session recovery attempt {attempt}/{self.max_retries}')
                
                # Clean up existing session
                if self.driver:
                    try:
                        self.driver.quit()
                    except Exception:
                        pass  # Ignore cleanup errors
                    self.driver = None
                
                # Reinitialize session (preserve context config)
                self.initialize_driver(
                    self.last_capabilities,
                    self.last_appium_url,
                    {
                        'targetPackage': self.target_package,
                        'targetActivity': self.target_activity,
                        'allowedExternalPackages': self.allowed_external_packages
                    }
                )
                
                logger.info('Session recovery successful')
                return True
                
            except Exception as error:
                logger.error(f'Session recovery attempt {attempt} failed: {error}')
                
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)
        
        logger.error('Session recovery failed after all attempts')
        return False
    
    def safe_execute(self, operation, error_message: str = 'Operation failed'):
        """
        Safe execution wrapper with session validation and retry.
        
        Args:
            operation: Operation to execute (callable)
            error_message: Error message for failures
            
        Returns:
            Result of the operation
        """
        if not self.driver:
            raise SessionNotFoundError('No active Appium session')
        
        # Validate session before operation
        if not self.validate_session():
            raise SessionNotFoundError('Session validation failed')
        
        return with_retry_sync(
            operation,
            self.max_retries,
            self.retry_delay,
            error_message
        )
    
    def _get_locator(self, selector: str, strategy: LocatorStrategy) -> tuple:
        """
        Get Selenium/Appium locator tuple from strategy and selector.
        
        Args:
            selector: Element selector
            strategy: Locator strategy
            
        Returns:
            Tuple of (By, selector) for use with find_element
        """
        strategy_map = {
            'id': (AppiumBy.ID, selector),
            'xpath': (AppiumBy.XPATH, selector),
            'accessibility id': (AppiumBy.ACCESSIBILITY_ID, selector),
            'class name': (AppiumBy.CLASS_NAME, selector),
            'css selector': (AppiumBy.CSS_SELECTOR, selector),
            'tag name': (AppiumBy.TAG_NAME, selector),
            'link text': (AppiumBy.LINK_TEXT, selector),
            'partial link text': (AppiumBy.PARTIAL_LINK_TEXT, selector),
            'name': (AppiumBy.NAME, selector),
            'android uiautomator': (AppiumBy.ANDROID_UIAUTOMATOR, selector),
        }
        
        return strategy_map.get(strategy, (AppiumBy.ID, selector))
    
    def find_element(
        self,
        selector: str,
        strategy: LocatorStrategy = 'id',
        timeout_ms: int = 10000
    ) -> WebElement:
        """
        Find element with specified strategy.
        
        Args:
            selector: Element selector
            strategy: Locator strategy
            timeout_ms: Timeout in milliseconds
            
        Returns:
            Found WebElement
            
        Raises:
            ElementNotFoundError: If element not found
        """
        def _find():
            start_time = time.time()
            last_error: Optional[Exception] = None
            
            try:
                # Temporarily reduce implicit wait to 2 seconds for faster attempts
                original_timeout = self._current_implicit_wait or (self.implicit_wait / 1000.0)
                reduced_implicit_wait = 2.0  # Lower implicit wait for faster attempts
                
                if abs(original_timeout - reduced_implicit_wait) > 0.1:
                    self.driver.implicitly_wait(reduced_implicit_wait)
                    self._current_implicit_wait = reduced_implicit_wait
                
                try:
                    # For Android with 'id' strategy, prioritize UIAutomator (proven to be ~100x faster)
                    if strategy == 'id' and self._get_current_platform() == 'android':
                        # Primary strategy: Android UIAutomator (fastest for Android resource IDs)
                        strategy_start = time.time()
                        logger.info(f'[Element Find] Attempting primary strategy: Android UIAutomator for "{selector}"')
                        try:
                            uiautomator_selector = f'new UiSelector().resourceId("{selector}")'
                            element = self.driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, uiautomator_selector)
                            if element.is_displayed():
                                strategy_duration = (time.time() - strategy_start) * 1000
                                total_duration = (time.time() - start_time) * 1000
                                logger.info(f'[Element Find] ✓ Primary strategy (UIAutomator) SUCCESS in {strategy_duration:.0f}ms (total: {total_duration:.0f}ms)')
                                return element
                        except (NoSuchElementException, TimeoutException) as e:
                            strategy_duration = (time.time() - strategy_start) * 1000
                            logger.info(f'[Element Find] ✗ Primary strategy (UIAutomator) FAILED in {strategy_duration:.0f}ms')
                            last_error = e
                        
                        # Fallback 1: Standard ID with explicit wait (slower but more compatible)
                        by, value = self._get_locator(selector, strategy)
                        explicit_timeout = min(timeout_ms / 1000.0, 3.0)  # Reduced to 3 seconds for fallback
                        fallback_start = time.time()
                        logger.info(f'[Element Find] Attempting fallback 1: ID (visibility) for "{selector}"')
                        try:
                            wait = WebDriverWait(self.driver, explicit_timeout)
                            element = wait.until(EC.visibility_of_element_located((by, value)))
                            fallback_duration = (time.time() - fallback_start) * 1000
                            total_duration = (time.time() - start_time) * 1000
                            logger.info(f'[Element Find] ✓ Fallback 1 (ID visibility) SUCCESS in {fallback_duration:.0f}ms (total: {total_duration:.0f}ms)')
                            return element
                        except (NoSuchElementException, TimeoutException) as e:
                            fallback_duration = (time.time() - fallback_start) * 1000
                            logger.info(f'[Element Find] ✗ Fallback 1 (ID visibility) FAILED in {fallback_duration:.0f}ms')
                        
                        # Fallback 2: Accessibility ID
                        fallback_start = time.time()
                        logger.info(f'[Element Find] Attempting fallback 2: Accessibility ID for "{selector}"')
                        try:
                            element = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, selector)
                            if element.is_displayed():
                                fallback_duration = (time.time() - fallback_start) * 1000
                                total_duration = (time.time() - start_time) * 1000
                                logger.info(f'[Element Find] ✓ Fallback 2 (Accessibility ID) SUCCESS in {fallback_duration:.0f}ms (total: {total_duration:.0f}ms)')
                                return element
                        except (NoSuchElementException, TimeoutException) as e:
                            fallback_duration = (time.time() - fallback_start) * 1000
                            logger.info(f'[Element Find] ✗ Fallback 2 (Accessibility ID) FAILED in {fallback_duration:.0f}ms')
                        
                        # Fallback 3: Package-prefixed ID (for traditional views)
                        if ':' not in selector and self.target_package:
                            package_prefixed = f'{self.target_package}:id/{selector}'
                            fallback_start = time.time()
                            logger.info(f'[Element Find] Attempting fallback 3: Package-prefixed ID for "{package_prefixed}"')
                            try:
                                element = self.driver.find_element(by, package_prefixed)
                                if element.is_displayed():
                                    fallback_duration = (time.time() - fallback_start) * 1000
                                    total_duration = (time.time() - start_time) * 1000
                                    logger.info(f'[Element Find] ✓ Fallback 3 (Package-prefixed ID) SUCCESS in {fallback_duration:.0f}ms (total: {total_duration:.0f}ms)')
                                    return element
                            except (NoSuchElementException, TimeoutException) as e:
                                fallback_duration = (time.time() - fallback_start) * 1000
                                logger.info(f'[Element Find] ✗ Fallback 3 (Package-prefixed ID) FAILED in {fallback_duration:.0f}ms')
                        
                        # Fallback 4: XPath by resource-id (slower, last resort)
                        fallback_start = time.time()
                        logger.info(f'[Element Find] Attempting fallback 4: XPath (resource-id) for "{selector}"')
                        try:
                            xpath_exact = f'//*[@resource-id="{selector}"]'
                            element = self.driver.find_element(AppiumBy.XPATH, xpath_exact)
                            if element.is_displayed():
                                fallback_duration = (time.time() - fallback_start) * 1000
                                total_duration = (time.time() - start_time) * 1000
                                logger.info(f'[Element Find] ✓ Fallback 4 (XPath resource-id) SUCCESS in {fallback_duration:.0f}ms (total: {total_duration:.0f}ms)')
                                return element
                        except (NoSuchElementException, TimeoutException) as e:
                            fallback_duration = (time.time() - fallback_start) * 1000
                            logger.info(f'[Element Find] ✗ Fallback 4 (XPath resource-id) FAILED in {fallback_duration:.0f}ms')
                        
                        # Fallback 5: XPath with package prefix (last resort)
                        if ':' not in selector and self.target_package:
                            package_prefixed = f'{self.target_package}:id/{selector}'
                            fallback_start = time.time()
                            logger.info(f'[Element Find] Attempting fallback 5: XPath (prefixed resource-id) for "{package_prefixed}"')
                            try:
                                xpath_prefixed = f'//*[@resource-id="{package_prefixed}"]'
                                element = self.driver.find_element(AppiumBy.XPATH, xpath_prefixed)
                                if element.is_displayed():
                                    fallback_duration = (time.time() - fallback_start) * 1000
                                    total_duration = (time.time() - start_time) * 1000
                                    logger.info(f'[Element Find] ✓ Fallback 5 (XPath prefixed) SUCCESS in {fallback_duration:.0f}ms (total: {total_duration:.0f}ms)')
                                    return element
                            except (NoSuchElementException, TimeoutException) as e:
                                fallback_duration = (time.time() - fallback_start) * 1000
                                logger.info(f'[Element Find] ✗ Fallback 5 (XPath prefixed) FAILED in {fallback_duration:.0f}ms')
                        
                        # If all strategies failed, raise the last error
                        if last_error:
                            raise last_error
                        raise ElementNotFoundError(f'Element not found with any strategy: {selector}')
                    else:
                        # For non-Android or non-ID strategies, use standard approach
                        by, value = self._get_locator(selector, strategy)
                        explicit_timeout = min(timeout_ms / 1000.0, 5.0)  # Cap at 5 seconds for explicit wait
                        
                        # Primary strategy timing
                        strategy_start = time.time()
                        logger.info(f'[Element Find] Attempting primary strategy: {strategy} for "{selector}"')
                        
                        # Use explicit WebDriverWait for more precise control
                        wait = WebDriverWait(self.driver, explicit_timeout)
                        # Wait for element to be present and visible
                        element = wait.until(EC.visibility_of_element_located((by, value)))
                        
                        strategy_duration = (time.time() - strategy_start) * 1000
                        total_duration = (time.time() - start_time) * 1000
                        logger.info(f'[Element Find] ✓ Primary strategy ({strategy}) SUCCESS in {strategy_duration:.0f}ms (total: {total_duration:.0f}ms)')
                        
                        return element
                except (NoSuchElementException, TimeoutException) as error:
                    # This catches exceptions from the non-Android/non-ID path
                    last_error = error
                    raise
                finally:
                    # Restore original timeout if we changed it
                    if abs(self._current_implicit_wait - original_timeout) > 0.1:
                        self.driver.implicitly_wait(original_timeout)
                        self._current_implicit_wait = original_timeout
                    
            except (NoSuchElementException, TimeoutException, ElementNotFoundError) as error:
                duration = (time.time() - start_time) * 1000
                error_msg = f'Element not found with {strategy}: {selector}'
                if last_error:
                    error_msg += f' (tried fallback strategies)'
                logger.error(f'{error_msg}, duration={duration:.0f}ms')
                raise ElementNotFoundError(error_msg) from error
        
        return self.safe_execute(_find, f'Find element with {strategy}: {selector}')
    
    def find_elements(
        self,
        selector: str,
        strategy: LocatorStrategy = 'id'
    ) -> List[WebElement]:
        """
        Find multiple elements with specified strategy.
        
        Args:
            selector: Element selector
            strategy: Locator strategy
            
        Returns:
            List of found WebElements
        """
        def _find():
            start_time = time.time()
            
            try:
                by, value = self._get_locator(selector, strategy)
                elements = self.driver.find_elements(by, value)
                
                duration = (time.time() - start_time) * 1000
                logger.debug(
                    f'Found {len(elements)} elements with {strategy}: {selector} in {duration:.0f}ms'
                )
                
                return elements
            except Exception as error:
                duration = (time.time() - start_time) * 1000
                logger.error(
                    f'Error finding elements with {strategy}: {selector}, duration={duration:.0f}ms'
                )
                return []
        
        return self.safe_execute(_find, f'Find elements with {strategy}: {selector}')
    
    def tap_element(
        self,
        selector: str,
        strategy: LocatorStrategy = 'id'
    ) -> bool:
        """
        Tap element with multiple fallback strategies.
        
        Args:
            selector: Element selector
            strategy: Locator strategy
            
        Returns:
            True if tap successful
        """
        start_time = time.time()
        
        def _tap():
            element = self.find_element(selector, strategy)
            last_error: Optional[Exception] = None
            
            # Method 1: Standard click
            try:
                element.click()
                self._record_action('tap', selector, True, time.time() - start_time)
                return True
            except Exception as click_error:
                last_error = click_error
                logger.debug('Standard click failed, trying W3C Actions')
            
            # Method 2: W3C Actions API
            try:
                x, y = self._get_element_center(element)
                self.perform_w3c_tap(x, y)
                self._record_action('tap', selector, True, time.time() - start_time)
                return True
            except Exception as w3c_error:
                last_error = w3c_error
                logger.debug('W3C Actions failed, trying mobile command')
            
            # Method 3: Mobile tap command
            try:
                x, y = self._get_element_center(element)
                self.driver.execute_script('mobile: tap', {'x': x, 'y': y})
                self._record_action('tap', selector, True, time.time() - start_time)
                return True
            except Exception as mobile_error:
                last_error = mobile_error
            
            # All methods failed
            error_msg = str(last_error) if last_error else 'Unknown error'
            self._record_action('tap', selector, False, time.time() - start_time, error_msg)
            raise GestureFailedError(
                f'Failed to tap element after all fallback methods: {error_msg}'
            )
        
        return self.safe_execute(_tap, f'Tap element: {selector}')
    
    def send_keys(
        self,
        selector: str,
        text: str,
        strategy: LocatorStrategy = 'id',
        clear_first: bool = True
    ) -> bool:
        """
        Send text to element with focus verification.
        
        Args:
            selector: Element selector
            text: Text to send
            strategy: Locator strategy
            clear_first: Whether to clear element before typing
            
        Returns:
            True if successful
        """
        start_time = time.time()
        
        def _send():
            # Re-find element right before each operation to avoid StaleElementReferenceException
            # This ensures we always have a fresh reference to the element
            
            # Find element and focus it
            element = self.find_element(selector, strategy)
            try:
                element.click()
            except Exception:
                logger.debug('Failed to click element before sending keys, continuing...')
            
            # Clear element if requested (re-find to avoid stale reference)
            if clear_first:
                try:
                    element = self.find_element(selector, strategy)
                    element.clear()
                except Exception:
                    logger.debug('Failed to clear element value, continuing...')
            
            # Re-find element right before send_keys to ensure fresh reference
            # This prevents StaleElementReferenceException
            element = self.find_element(selector, strategy)
            element.send_keys(text)
            
            # Hide keyboard on mobile
            try:
                self.driver.hide_keyboard()
            except Exception:
                pass  # Keyboard might not be present
            
            self._record_action('sendKeys', selector, True, time.time() - start_time)
            return True
        
        return self.safe_execute(_send, f'Send keys to element: {selector}')
    
    def perform_w3c_tap(self, x: float, y: float) -> None:
        """
        Perform W3C Actions API tap at coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.actions import interaction
        from selenium.webdriver.common.actions.action_builder import ActionBuilder
        from selenium.webdriver.common.actions.pointer_input import PointerInput
        
        actions = ActionChains(self.driver)
        actions.w3c_actions = ActionBuilder(self.driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
        actions.w3c_actions.pointer_action.move_to_location(x, y)
        actions.w3c_actions.pointer_action.pointer_down()
        actions.w3c_actions.pointer_action.pause(0.1)
        actions.w3c_actions.pointer_action.pointer_up()
        actions.perform()
    
    def _get_element_center(self, element: WebElement) -> tuple[float, float]:
        """
        Get element center coordinates.
        
        Args:
            element: WebElement
            
        Returns:
            Tuple of (x, y) coordinates
        """
        location = element.location
        size = element.size
        
        return (
            location['x'] + size['width'] / 2,
            location['y'] + size['height'] / 2
        )
    
    def _record_action(
        self,
        action: str,
        target: str,
        success: bool,
        duration: float,
        error_message: Optional[str] = None
    ) -> None:
        """
        Record action in history.
        
        Args:
            action: Action name
            target: Target identifier
            success: Whether action succeeded
            duration: Duration in seconds
            error_message: Optional error message
        """
        history_entry = ActionHistory(
            action=action,
            target=target,
            success=success,
            timestamp=time.time(),
            duration=duration,
            error_message=error_message
        )
        
        self.action_history.append(history_entry)
        
        # Keep only last 100 actions
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]
        
        logger.debug(
            f'Action recorded: {action} on {target}, success={success}, '
            f'duration={duration*1000:.0f}ms'
        )
    
    def get_action_history(self) -> List[ActionHistory]:
        """
        Get action history.
        
        Returns:
            List of action history entries
        """
        return list(self.action_history)
    
    def get_session_state(self) -> SessionState:
        """
        Get current session state.
        
        Returns:
            SessionState object
        """
        return SessionState(
            driver=self.driver,
            current_platform=self._get_current_platform(),
            current_device=None,  # Would need device detection logic
            session_id=self.driver.session_id if self.driver else None,
            last_capabilities=self.last_capabilities,
            last_appium_url=self.last_appium_url,
            action_history=self.get_action_history()
        )
    
    def _get_current_platform(self) -> Optional[Platform]:
        """
        Get current platform from capabilities.
        
        Returns:
            Platform or None
        """
        if self.last_capabilities:
            platform_name = self.last_capabilities.get('platformName', '').lower()
            if 'android' in platform_name:
                return 'android'
        return None
    
    def close_driver(self) -> None:
        """Close driver and clean up session."""
        if self.driver:
            try:
                session_id = self.driver.session_id
                self.driver.quit()
                logger.info(f'Session closed: {session_id}')
            except Exception as error:
                logger.error(f'Error closing session: {error}')
            finally:
                self.driver = None
                self.last_capabilities = None
                self.last_appium_url = None
                self.target_package = None
                self.target_activity = None
                self.allowed_external_packages = []
                self.consecutive_context_failures = 0
    
    def get_page_source(self) -> str:
        """
        Get page source.
        
        Returns:
            Page source XML string
        """
        def _get():
            return self.driver.page_source
        
        return self.safe_execute(_get, 'Get page source')
    
    def take_screenshot(self) -> str:
        """
        Take screenshot.
        
        Returns:
            Base64-encoded screenshot string
        """
        def _take():
            return self.driver.get_screenshot_as_base64()
        
        return self.safe_execute(_take, 'Take screenshot')
    
    def get_window_size(self) -> Dict[str, int]:
        """
        Get window size.
        
        Returns:
            Dictionary with 'width' and 'height'
        """
        def _get():
            size = self.driver.get_window_size()
            return {'width': size['width'], 'height': size['height']}
        
        return self.safe_execute(_get, 'Get window size')
    
    def get_driver(self) -> Optional[webdriver.Remote]:
        """
        Get driver instance (for advanced operations).
        
        Returns:
            WebDriver instance or None
        """
        return self.driver
    
    def get_current_package(self) -> Optional[str]:
        """
        Get current package name (Android only).
        
        Returns:
            Package name or None
        """
        if not self.driver:
            return None
        
        try:
            platform = self._get_current_platform()
            if platform != 'android':
                return None
            
            # Try Appium's get_current_package method
            try:
                package_name = self.driver.current_package
                if package_name:
                    return package_name
            except Exception:
                pass
            
            # Fallback: use mobile: shell to get current package via dumpsys
            try:
                result = self.driver.execute_script(
                    'mobile: shell',
                    {
                        'command': 'dumpsys',
                        'args': ['window', 'windows']
                    }
                )
                
                # Parse package name from dumpsys output
                if isinstance(result, str):
                    focus_match = re.search(r'mCurrentFocus.*?(\w+\.\w+(?:\.\w+)*)', result)
                    if focus_match and focus_match.group(1):
                        return focus_match.group(1)
            except Exception:
                pass
            
            return None
        except Exception as error:
            logger.debug(f'Failed to get current package: {error}')
            return None
    
    def get_current_activity(self) -> Optional[str]:
        """
        Get current activity name (Android only).
        
        Returns:
            Activity name or None
        """
        if not self.driver:
            return None
        
        try:
            platform = self._get_current_platform()
            if platform != 'android':
                return None
            
            # Try Appium's get_current_activity method
            try:
                activity = self.driver.current_activity
                if activity:
                    return activity
            except Exception:
                pass
            
            # Fallback: use mobile: shell to get current activity via dumpsys
            try:
                result = self.driver.execute_script(
                    'mobile: shell',
                    {
                        'command': 'dumpsys',
                        'args': ['window', 'windows']
                    }
                )
                
                # Parse activity from dumpsys output
                if isinstance(result, str):
                    focus_match = re.search(r'mCurrentFocus.*?(\w+\.\w+(?:\/\w+\.\w+)*)', result)
                    if focus_match and focus_match.group(1):
                        return focus_match.group(1)
            except Exception:
                pass
            
            return None
        except Exception as error:
            logger.debug(f'Failed to get current activity: {error}')
            return None
    
    def start_activity(
        self,
        app_package: str,
        app_activity: str,
        wait_after_launch: int = 5000
    ) -> bool:
        """
        Start an Android app activity.
        
        Args:
            app_package: Android app package name
            app_activity: Android app activity name
            wait_after_launch: Wait time in milliseconds after launching
            
        Returns:
            True if successful
        """
        if not self.driver:
            logger.error('Driver not initialized, cannot start activity')
            return False
        
        try:
            platform = self._get_current_platform()
            if platform != 'android':
                logger.warning('startActivity is only supported on Android')
                return False
            
            # Normalize activity name
            # Handle different activity name formats
            if app_activity.startswith('.'):
                # Relative activity name (e.g., ".MainActivity")
                full_activity = f'{app_package}{app_activity}'
            elif '/' in app_activity:
                # Full activity path (e.g., "com.example/.MainActivity")
                full_activity = app_activity
            elif '.' in app_activity:
                # Full qualified activity (e.g., "com.example.MainActivity")
                full_activity = app_activity
            else:
                # Simple activity name (e.g., "MainActivity")
                full_activity = f'{app_package}.{app_activity}'
            
            # Construct activity component for ADB
            activity_component = f'{app_package}/{full_activity}'
            
            logger.info(f'Attempting to start activity: {activity_component}')
            
            # Method 1: Try Appium's start_activity method (recommended)
            try:
                self.driver.start_activity(app_package, app_activity)
                logger.info(f'Started activity using Appium method: {app_package}/{app_activity}')
            except Exception as appium_error:
                logger.warning(f'Appium start_activity failed: {appium_error}, trying ADB fallback...')
                
                # Method 2: Try ADB shell command via subprocess (more reliable)
                try:
                    # Get device UDID from driver capabilities
                    device_udid = None
                    try:
                        if self.last_capabilities:
                            device_udid = self.last_capabilities.get('appium:udid')
                    except Exception:
                        pass
                    
                    # Build ADB command
                    adb_cmd = ['adb']
                    if device_udid:
                        adb_cmd.extend(['-s', device_udid])
                    adb_cmd.extend(['shell', 'am', 'start', '-W', '-n', activity_component])
                    
                    logger.debug(f'Executing ADB command: {" ".join(adb_cmd)}')
                    result = subprocess.run(
                        adb_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        logger.info(f'Started activity using ADB: {activity_component}')
                    else:
                        logger.error(f'ADB command failed: {result.stderr}')
                        # Try one more fallback with mobile: shell
                        raise Exception(f'ADB failed: {result.stderr}')
                        
                except Exception as adb_error:
                    logger.warning(f'ADB fallback failed: {adb_error}, trying mobile: shell...')
                    
                    # Method 3: Fallback to mobile: shell (last resort)
                    try:
                        self.driver.execute_script(
                            'mobile: shell',
                            {
                                'command': 'am',
                                'args': ['start', '-W', '-n', activity_component]
                            }
                        )
                        logger.info(f'Started activity using mobile: shell: {activity_component}')
                    except Exception as shell_error:
                        logger.error(f'All methods failed to start activity: {shell_error}')
                        return False
            
            # Wait for app to load
            if wait_after_launch > 0:
                logger.debug(f'Waiting {wait_after_launch}ms for app to fully load...')
                time.sleep(wait_after_launch / 1000.0)
            
            # Verify the app actually launched
            try:
                current_package = self.get_current_package()
                if current_package == app_package:
                    logger.info(f'Verified app launched successfully: {app_package}')
                    return True
                else:
                    logger.warning(
                        f'App may not have launched correctly. '
                        f'Expected: {app_package}, Current: {current_package}'
                    )
                    # Still return True if we got here without errors
                    return True
            except Exception as verify_error:
                logger.warning(f'Could not verify app launch: {verify_error}')
                # Still return True if the launch command succeeded
                return True
            
        except Exception as error:
            logger.error(f'Failed to start activity: {error}', exc_info=True)
            return False
    
    def activate_app(self, app_package: str) -> bool:
        """
        Activate an app (bring to foreground).
        
        Args:
            app_package: App package name
            
        Returns:
            True if successful
        """
        if not self.driver:
            return False
        
        try:
            self.driver.activate_app(app_package)
            logger.info(f'Activated app: {app_package}')
            return True
        except Exception as error:
            logger.debug(f'activateApp failed: {error}')
            return False
    
    def get_target_package(self) -> Optional[str]:
        """Get target package name."""
        return self.target_package
    
    def get_target_activity(self) -> Optional[str]:
        """Get target activity name."""
        return self.target_activity
    
    def get_allowed_external_packages(self) -> List[str]:
        """Get allowed external packages."""
        return list(self.allowed_external_packages)
    
    def set_allowed_external_packages(self, packages: List[str]) -> None:
        """Set allowed external packages."""
        self.allowed_external_packages = list(packages)
    
    def ensure_in_app(self) -> bool:
        """
        Ensure we are in the correct app context before performing actions.
        
        Checks if current package matches target or allowed external packages.
        Attempts recovery if not in correct context.
        
        Returns:
            True if in correct app context
        """
        if not self.driver:
            logger.error('Driver not connected, cannot ensure app context')
            self.consecutive_context_failures += 1
            return False
        
        # Skip check if no target package is set (not configured)
        if not self.target_package:
            logger.debug('No target package set, skipping app context check')
            return True
        
        platform = self._get_current_platform()
        if platform != 'android':
            logger.debug('App context check skipped for non-Android platform')
            return True
        
        # Get current package with retry
        current_package: Optional[str] = None
        max_context_retries = 2
        for retry in range(max_context_retries + 1):
            try:
                current_package = self.get_current_package()
                if current_package:
                    break
            except Exception as error:
                logger.warning(f'Error getting app context (retry {retry}): {error}')
                if retry < max_context_retries:
                    time.sleep(1.0)
                    continue
        
        if not current_package:
            logger.warning('Could not get app context after retries. Attempting recovery.')
            # Try to relaunch target app
            if self.target_package and self.target_activity:
                if self.start_activity(self.target_package, self.target_activity):
                    time.sleep(2.0)
                    context_after_relaunch = self.get_current_package()
                    if context_after_relaunch == self.target_package:
                        logger.info(
                            'Recovery successful: Relaunched target application after unknown context'
                        )
                        self.consecutive_context_failures = 0
                        return True
            logger.error('Failed to recover context even after relaunch from unknown state')
            self.consecutive_context_failures += 1
            return False
        
        # Build allowed packages set
        allowed_packages_set = {self.target_package, *self.allowed_external_packages}
        
        logger.debug(
            f'Current app context: {current_package}. '
            f'Allowed: {", ".join(allowed_packages_set)}'
        )
        
        if current_package in allowed_packages_set:
            logger.debug(f'App context OK (In \'{current_package}\')')
            self.consecutive_context_failures = 0
            return True
        
        # Not in correct app context
        logger.warning(
            f'App context incorrect: In \'{current_package}\', '
            f'expected one of {", ".join(allowed_packages_set)}'
        )
        self.consecutive_context_failures += 1
        
        if self.consecutive_context_failures >= self.max_consecutive_context_failures:
            logger.error(
                'Maximum consecutive context failures reached. '
                'No further recovery attempts this step.'
            )
            return False
        
        # Attempt recovery: press back button first
        logger.info('Attempting recovery: Pressing back button...')
        try:
            self.driver.back()
            time.sleep(1.0)
        except Exception as error:
            logger.debug(f'Failed to press back button during recovery: {error}')
        
        # Check if back button worked
        context_after_back = self.get_current_package()
        if context_after_back and context_after_back in allowed_packages_set:
            logger.info(
                'Recovery successful: Returned to target/allowed package after back press'
            )
            self.consecutive_context_failures = 0
            return True
        
        # Back button didn't work, try relaunching target app
        logger.warning(
            f'Recovery still not successful after back press '
            f'(current: {context_after_back or "Unknown"}). '
            f'Relaunching target application.'
        )
        if self.target_package and self.target_activity:
            if self.start_activity(self.target_package, self.target_activity):
                time.sleep(2.0)
                context_after_relaunch = self.get_current_package()
                if context_after_relaunch and context_after_relaunch in allowed_packages_set:
                    logger.info('Recovery successful: Relaunched target application')
                    self.consecutive_context_failures = 0
                    return True
        elif self.target_package:
            # Try activateApp if we don't have activity
            if self.activate_app(self.target_package):
                time.sleep(2.0)
                context_after_activate = self.get_current_package()
                if context_after_activate and context_after_activate in allowed_packages_set:
                    logger.info('Recovery successful: Activated target application')
                    self.consecutive_context_failures = 0
                    return True
        
        current_pkg_after_all = self.get_current_package() or 'Unknown'
        logger.error(
            f'All recovery attempts failed. Could not return to target/allowed application. '
            f'Currently in \'{current_pkg_after_all}\'.'
        )
        return False

