"""
Error handling utilities for Appium operations.

Provides custom exceptions, retry logic, and error formatting for Appium operations.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class AppiumError(Exception):
    """Base exception for Appium-related errors."""
    
    def __init__(self, message: str, code: str = 'APPIUM_ERROR', details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.name = self.__class__.__name__


class ActionableError(Exception):
    """Error that can be fixed by user action."""
    
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        self.name = self.__class__.__name__


class SessionNotFoundError(AppiumError):
    """Raised when no active Appium session is found."""
    
    def __init__(self, message: str = 'No active Appium session found'):
        super().__init__(message, 'SESSION_NOT_FOUND')


class ElementNotFoundError(AppiumError):
    """Raised when an element cannot be found."""
    
    def __init__(self, message: str = 'Element not found'):
        super().__init__(message, 'ELEMENT_NOT_FOUND')


class DeviceNotFoundError(AppiumError):
    """Raised when a device cannot be found."""
    
    def __init__(self, message: str = 'Device not found'):
        super().__init__(message, 'DEVICE_NOT_FOUND')


class GestureFailedError(AppiumError):
    """Raised when a gesture execution fails."""
    
    def __init__(self, message: str = 'Gesture execution failed'):
        super().__init__(message, 'GESTURE_FAILED')


class OCRNotAvailableError(AppiumError):
    """Raised when OCR plugin is not available."""
    
    def __init__(self, message: str = 'OCR plugin not available'):
        super().__init__(message, 'OCR_NOT_AVAILABLE')


class ImageMatchingError(AppiumError):
    """Raised when image matching fails."""
    
    def __init__(self, message: str = 'Image matching failed'):
        super().__init__(message, 'IMAGE_MATCHING_FAILED')


def is_webdriver_error(error: Exception) -> bool:
    """Check if error is a WebDriver/Selenium error."""
    error_name = error.__class__.__name__
    webdriver_errors = {
        'TimeoutException',
        'NoSuchElementException',
        'StaleElementReferenceException',
        'ElementNotInteractableException',
        'InvalidSelectorException',
        'JavascriptException',
        'MoveTargetOutOfBoundsException',
        'InvalidSessionIdException',
        'SessionNotCreatedException',
        'UnknownCommandException',
        'WebDriverException',
    }
    return error_name in webdriver_errors


def is_session_terminated(error: Exception) -> bool:
    """Check if an error indicates a session termination."""
    error_name = error.__class__.__name__
    error_message = str(error).lower()
    
    return (
        error_name in ('InvalidSessionIdException', 'SessionNotCreatedException') or
        'session' in error_message or
        'disconnected' in error_message or
        'timeout' in error_message
    )


def validate_coordinates(
    x: float,
    y: float,
    screen_width: int,
    screen_height: int,
    margin_ratio: float = 0.03
) -> Dict[str, float]:
    """
    Validate coordinates are within screen bounds.
    
    Args:
        x: X coordinate
        y: Y coordinate
        screen_width: Screen width
        screen_height: Screen height
        margin_ratio: Margin ratio for safe area (default 3%)
        
    Returns:
        Dictionary with validated x and y coordinates
    """
    margin_x = screen_width * margin_ratio
    margin_y = screen_height * margin_ratio
    
    # Snap to safe area if too close to edges
    safe_x = max(margin_x, min(x, screen_width - margin_x))
    safe_y = max(margin_y, min(y, screen_height - margin_y))
    
    if safe_x != x or safe_y != y:
        logger.warning(
            f"[SafeArea] Coordinates snapped from ({x}, {y}) to ({safe_x}, {safe_y})"
        )
    
    return {'x': safe_x, 'y': safe_y}


async def with_retry(
    operation: Callable[[], Any],
    max_retries: int = 3,
    retry_delay: float = 1.0,
    context: Optional[str] = None
) -> Any:
    """
    Retry wrapper for operations that may fail temporarily.
    
    Args:
        operation: Async operation to retry
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries in seconds
        context: Optional context string for logging
        
    Returns:
        Result of the operation
        
    Raises:
        The last exception if all retries fail
    """
    last_error: Optional[Exception] = None
    
    for attempt in range(1, max_retries + 1):
        try:
            if callable(operation):
                result = operation()
                # Handle both sync and async operations
                if hasattr(result, '__await__'):
                    return await result
                return result
            return operation
        except ActionableError:
            # Don't retry actionable errors
            raise
        except Exception as error:
            last_error = error
            
            # Don't retry on certain errors
            if is_webdriver_error(error):
                error_name = error.__class__.__name__
                if error_name in ('InvalidSelectorException', 'InvalidSessionIdException'):
                    raise
            
            # If this is the last attempt, raise the error
            if attempt == max_retries:
                raise
            
            # Wait before retrying with exponential backoff
            delay = retry_delay * attempt
            context_str = f"{context}: " if context else ""
            logger.warning(
                f"[Retry] {context_str}Attempt {attempt} failed, retrying in {delay}s...",
                exc_info=error
            )
            await asyncio.sleep(delay)
    
    # This should never be reached, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Retry operation failed without error")


def with_retry_sync(
    operation: Callable[[], T],
    max_retries: int = 3,
    retry_delay: float = 1.0,
    context: Optional[str] = None
) -> T:
    """
    Synchronous retry wrapper for operations that may fail temporarily.
    
    Args:
        operation: Synchronous operation to retry
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries in seconds
        context: Optional context string for logging
        
    Returns:
        Result of the operation
        
    Raises:
        The last exception if all retries fail
    """
    last_error: Optional[Exception] = None
    
    for attempt in range(1, max_retries + 1):
        try:
            return operation()
        except ActionableError:
            # Don't retry actionable errors
            raise
        except Exception as error:
            last_error = error
            
            # Don't retry on certain errors
            if is_webdriver_error(error):
                error_name = error.__class__.__name__
                if error_name in ('InvalidSelectorException', 'InvalidSessionIdException'):
                    raise
            
            # If this is the last attempt, raise the error
            if attempt == max_retries:
                raise
            
            # Wait before retrying with exponential backoff
            delay = retry_delay * attempt
            context_str = f"{context}: " if context else ""
            logger.warning(
                f"[Retry] {context_str}Attempt {attempt} failed, retrying in {delay}s...",
                exc_info=error
            )
            time.sleep(delay)
    
    # This should never be reached, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Retry operation failed without error")


def format_error_message(error: Exception) -> str:
    """
    Format error messages for user-friendly display.
    
    Args:
        error: Exception to format
        
    Returns:
        Formatted error message
    """
    if isinstance(error, ElementNotFoundError):
        return f"Element not found: {error.message}"
    
    if isinstance(error, SessionNotFoundError):
        return f"Session error: {error.message}. Please initialize a session first."
    
    if isinstance(error, DeviceNotFoundError):
        return f"Device error: {error.message}. Please check device connection."
    
    if isinstance(error, ActionableError):
        return error.message
    
    if isinstance(error, Exception):
        return f"Error: {str(error)}"
    
    return 'An unknown error occurred'

