"""
Capability builder utilities for W3C-compliant Appium capabilities.

Builds and validates Appium capabilities for Android platform.
"""

import logging
from typing import Any, Dict, Optional, Literal

from infrastructure.device_detection import DeviceInfo, Platform

logger = logging.getLogger(__name__)

# Type alias for capabilities dictionary
AppiumCapabilities = Dict[str, Any]


def build_w3c_capabilities(
    platform: Platform,
    device: DeviceInfo,
    additional_caps: Optional[Dict[str, Any]] = None
) -> AppiumCapabilities:
    """
    Build W3C compliant capabilities from input parameters.
    
    Args:
        platform: Platform ('android')
        device: Device information
        additional_caps: Additional capabilities to merge
        
    Returns:
        W3C-compliant capabilities dictionary
    """
    additional_caps = additional_caps or {}
    
    base_caps: AppiumCapabilities = {
        'platformName': 'Android',
        'appium:automationName': 'UiAutomator2',
        'appium:deviceName': device.name,
        'appium:udid': device.id,
        'appium:newCommandTimeout': 600,
        'appium:noReset': True,
    }
    
    # Add platform version if available
    if device.version and device.version != 'Unknown':
        base_caps['appium:platformVersion'] = device.version
    
    # Merge additional capabilities
    merged_caps = {**base_caps, **additional_caps}
    
    # Validate required capabilities
    validate_capabilities(merged_caps)
    
    logger.debug(
        f'Built W3C capabilities for {platform} device {device.name}: '
        f'{list(merged_caps.keys())}'
    )
    
    return merged_caps


def format_capabilities_for_w3c(capabilities: AppiumCapabilities) -> Dict[str, Any]:
    """
    Format capabilities for W3C WebDriver protocol.
    
    Args:
        capabilities: Appium capabilities dictionary
        
    Returns:
        W3C-formatted capabilities
    """
    w3c_caps: Dict[str, Any] = {
        'alwaysMatch': {}
    }
    
    # Standard W3C capabilities
    if 'platformName' in capabilities:
        w3c_caps['alwaysMatch']['platformName'] = capabilities['platformName']
    
    # Appium-specific capabilities with appium: prefix
    for key, value in capabilities.items():
        if key.startswith('appium:') and value is not None:
            w3c_caps['alwaysMatch'][key] = value
    
    # Handle firstMatch for compatibility
    w3c_caps['firstMatch'] = [{}]
    
    logger.debug(
        f'Formatted capabilities for W3C protocol: '
        f'{list(w3c_caps["alwaysMatch"].keys())}'
    )
    
    return w3c_caps


def build_android_capabilities(
    device: DeviceInfo,
    app_package: Optional[str] = None,
    app_activity: Optional[str] = None,
    app: Optional[str] = None,
    additional_caps: Optional[Dict[str, Any]] = None
) -> AppiumCapabilities:
    """
    Build Android-specific capabilities.
    
    Args:
        device: Android device information
        app_package: Android app package (optional)
        app_activity: Android app activity (optional)
        app: Path to app file (optional)
        additional_caps: Additional capabilities to merge
        
    Returns:
        Android capabilities dictionary
    """
    additional_caps = additional_caps or {}
    
    android_caps: Dict[str, Any] = {
        'appium:chromeDriverPort': 9515,
        'appium:systemPort': 8200,
        'appium:mjpegServerPort': 7894,
        'appium:skipServerInstallation': True,
        'appium:autoGrantPermissions': True,
        'appium:ignoreHiddenApiPolicyError': True,
        'appium:allowTestPackages': True,
        'appium:allowInsecure': ['adb_shell'],
        **additional_caps
    }
    
    if app_package:
        android_caps['appium:appPackage'] = app_package
    if app_activity:
        android_caps['appium:appActivity'] = app_activity
    if app:
        android_caps['appium:app'] = app
    
    # Remove None values
    android_caps = {k: v for k, v in android_caps.items() if v is not None}
    
    return build_w3c_capabilities('android', device, android_caps)


def build_browser_capabilities(
    platform: Platform,
    browser_name: str = 'chrome',
    additional_caps: Optional[Dict[str, Any]] = None
) -> AppiumCapabilities:
    """
    Build capabilities for browser automation.
    
    Args:
        platform: Platform ('android')
        browser_name: Browser name (default: 'chrome')
        additional_caps: Additional capabilities to merge
        
    Returns:
        Browser capabilities dictionary
    """
    additional_caps = additional_caps or {}
    
    browser_caps: Dict[str, Any] = {
        'appium:browserName': browser_name,
        'appium:nativeWebScreenshot': True,
        # Note: chromedriver paths are handled automatically by Appium
        # If custom paths are needed, provide them via additional_caps
        **additional_caps
    }
    
    # Create a virtual device info for browser
    browser_device = DeviceInfo(
        platform=platform,
        id='browser',
        name=f'{browser_name} on {platform}',
        version='Unknown',
        type='device'
    )
    
    return build_w3c_capabilities(platform, browser_device, browser_caps)


def validate_capabilities(capabilities: AppiumCapabilities) -> None:
    """
    Validate required capabilities.
    
    Args:
        capabilities: Capabilities to validate
        
    Raises:
        ValueError: If required capabilities are missing or invalid
    """
    required = ['platformName', 'appium:automationName']
    missing = [cap for cap in required if cap not in capabilities or capabilities[cap] is None]
    
    if missing:
        raise ValueError(f'Missing required capabilities: {", ".join(missing)}')
    
    # Validate platform name
    if 'platformName' in capabilities:
        valid_platforms = ['Android']
        platform_name = capabilities['platformName']
        if platform_name not in valid_platforms:
            raise ValueError(
                f'Invalid platformName: {platform_name}. '
                f'Must be one of: {", ".join(valid_platforms)}'
            )
    
    # Validate automation name
    if 'appium:automationName' in capabilities:
        automation_name = capabilities['appium:automationName']
        platform = capabilities.get('platformName')
        
        if platform == 'Android' and automation_name != 'UiAutomator2':
            logger.warning(
                f"Recommended automationName for Android is 'UiAutomator2', got '{automation_name}'"
            )
    
    logger.debug('Capabilities validation passed')


def merge_capabilities(
    base_caps: AppiumCapabilities,
    additional_caps: Dict[str, Any]
) -> AppiumCapabilities:
    """
    Merge capabilities with conflict resolution.
    
    Args:
        base_caps: Base capabilities
        additional_caps: Additional capabilities to merge
        
    Returns:
        Merged capabilities
    """
    merged = {**base_caps}
    
    for key, value in additional_caps.items():
        if value is not None:
            merged[key] = value
    
    return merged


def get_default_capabilities(platform: Platform) -> Dict[str, Any]:
    """
    Get default capabilities for platform.
    
    Args:
        platform: Platform ('android')
        
    Returns:
        Default capabilities dictionary
    """
    defaults: Dict[Platform, Dict[str, Any]] = {
        'android': {
            'platformName': 'Android',
            'appium:automationName': 'UiAutomator2',
            'appium:newCommandTimeout': 600,
            'appium:uiautomator2ServerLaunchTimeout': 60000,
            'appium:uiautomator2ServerInstallTimeout': 120000,
        }
    }
    
    return defaults.get(platform, {})


def sanitize_capabilities(capabilities: AppiumCapabilities) -> AppiumCapabilities:
    """
    Sanitize capabilities (remove invalid or deprecated values).
    
    Args:
        capabilities: Capabilities to sanitize
        
    Returns:
        Sanitized capabilities
    """
    sanitized = {**capabilities}
    
    # Remove deprecated capabilities
    deprecated_caps = [
        'appium:device',
        'automationName',  # Should be appium:automationName
        'platform',  # Should be platformName
        'deviceName',  # Should be appium:deviceName
        'udid',  # Should be appium:udid
    ]
    
    for cap in deprecated_caps:
        if cap in sanitized:
            logger.warning(f'Removing deprecated capability: {cap}')
            del sanitized[cap]
    
    # Validate and fix numeric values
    for key, value in list(sanitized.items()):
        if 'Timeout' in key and isinstance(value, str):
            try:
                num_value = int(value)
                if num_value > 0:
                    sanitized[key] = num_value
                else:
                    logger.warning(f'Invalid timeout value for {key}: {value}, removing capability')
                    del sanitized[key]
            except ValueError:
                logger.warning(f'Invalid timeout value for {key}: {value}, removing capability')
                del sanitized[key]
    
    return sanitized


def log_capabilities(capabilities: AppiumCapabilities, title: str = 'Capabilities') -> None:
    """
    Log capabilities in a readable format.
    
    Args:
        capabilities: Capabilities to log
        title: Log title
    """
    readable: Dict[str, Any] = {}
    
    for key, value in capabilities.items():
        if key.startswith('appium:'):
            readable[key.replace('appium:', '')] = value
        else:
            readable[key] = value
    
    logger.info(f'{title}: {readable}')

