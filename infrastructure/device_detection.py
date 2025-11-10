"""
Device detection utilities for Android devices.

Detects available devices/emulators and provides device selection utilities.
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Literal

logger = logging.getLogger(__name__)

Platform = Literal['android']
DeviceType = Literal['emulator', 'device']


@dataclass
class DeviceInfo:
    """Information about a detected device."""
    platform: Platform
    id: str
    name: str
    version: str
    api_level: Optional[int] = None
    type: DeviceType = 'device'


def _run_command(command: List[str], timeout: int = 10) -> tuple[str, str, int]:
    """
    Run a shell command and return stdout, stderr, and return code.
    
    Args:
        command: Command to run as list of strings
        timeout: Command timeout in seconds
        
    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {' '.join(command)}")
        return "", "Command timed out", -1
    except Exception as e:
        logger.error(f"Error running command {' '.join(command)}: {e}")
        return "", str(e), -1


def detect_android_devices() -> List[DeviceInfo]:
    """
    Detect Android devices (emulators and physical devices).
    
    Returns:
        List of detected Android devices
    """
    devices: List[DeviceInfo] = []
    
    try:
        logger.debug('Detecting Android devices...')
        stdout, stderr, return_code = _run_command(['adb', 'devices', '-l'])
        
        if stderr:
            logger.warning(f'Android device detection stderr: {stderr}')
        
        if return_code != 0:
            logger.debug('adb command failed, Android devices may not be available')
            return devices
        
        lines = stdout.strip().split('\n')
        
        # Skip first line (List of devices attached)
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            # Parse device line: "emulator-5554 device product:sdk_gphone_x86 model:sdk_gphone_x86 device:generic_x86 transport_id:1"
            parts = line.split()
            if len(parts) < 2:
                continue
            
            device_id = parts[0]
            device_state = parts[1]
            
            # Handle unauthorized devices
            if device_state == 'unauthorized':
                logger.warning(
                    f'Device {device_id} requires USB debugging authorization. '
                    'Please unlock the device and accept the authorization prompt.'
                )
                continue
            
            # Skip other offline/unavailable devices
            if device_state != 'device':
                logger.debug(f'Skipping device {device_id} with state: {device_state}')
                continue
            
            # Extract device properties
            properties: dict[str, str] = {}
            for part in parts[2:]:
                if ':' in part:
                    key, value = part.split(':', 1)
                    properties[key] = value
            
            # Get additional device info
            api_level = None
            version = 'Unknown'
            name = properties.get('model', device_id)
            
            try:
                # Get API level
                api_stdout, _, api_return = _run_command(['adb', '-s', device_id, 'shell', 'getprop', 'ro.build.version.sdk'])
                if api_return == 0 and api_stdout.strip():
                    api_level = int(api_stdout.strip())
            except (ValueError, Exception) as e:
                logger.debug(f'Failed to get API level for device {device_id}: {e}')
            
            try:
                # Get Android version
                version_stdout, _, version_return = _run_command(
                    ['adb', '-s', device_id, 'shell', 'getprop', 'ro.build.version.release']
                )
                if version_return == 0 and version_stdout.strip():
                    version = version_stdout.strip()
            except Exception as e:
                logger.debug(f'Failed to get Android version for device {device_id}: {e}')
            
            # Determine device type
            device_type: DeviceType = 'emulator' if device_id.startswith('emulator-') else 'device'
            
            devices.append(DeviceInfo(
                platform='android',
                id=device_id,
                name=name or 'Unknown Device',
                version=version,
                api_level=api_level,
                type=device_type
            ))
        
        return devices
        
    except Exception as e:
        logger.error(f'Android device detection failed: {e}')
        return []


def detect_all_devices() -> List[DeviceInfo]:
    """
    Detect all available Android devices.
    
    Returns:
        List of all detected devices
    """
    android_devices = detect_android_devices()
    
    # Sort by name
    android_devices.sort(key=lambda d: d.name)
    
    logger.debug(f'Total devices found: {len(android_devices)} Android')
    
    return android_devices


def find_device_by_name(devices: List[DeviceInfo], device_name: str) -> Optional[DeviceInfo]:
    """
    Find device by name (partial match).
    
    Args:
        devices: List of devices to search
        device_name: Name or ID to search for
        
    Returns:
        Found device or None
    """
    normalized_name = device_name.lower()
    
    for device in devices:
        if normalized_name in device.name.lower() or normalized_name in device.id.lower():
            return device
    
    return None


def find_devices_by_platform(devices: List[DeviceInfo], platform: Platform) -> List[DeviceInfo]:
    """
    Find devices by platform.
    
    Args:
        devices: List of devices to filter
        platform: Platform to filter by
        
    Returns:
        Filtered list of devices
    """
    return [d for d in devices if d.platform == platform]


def select_best_device(
    devices: List[DeviceInfo],
    platform: Optional[Platform] = None,
    device_name: Optional[str] = None
) -> Optional[DeviceInfo]:
    """
    Select best device based on preferences.
    
    Args:
        devices: List of available devices
        platform: Preferred platform (optional)
        device_name: Preferred device name (optional)
        
    Returns:
        Selected device or None
    """
    if not devices:
        return None
    
    # If specific device name requested
    if device_name:
        candidate_devices = devices
        if platform:
            candidate_devices = find_devices_by_platform(candidate_devices, platform)
        
        found_device = find_device_by_name(candidate_devices, device_name)
        if found_device:
            logger.debug(f'Selected device by name: {found_device.name} ({found_device.platform})')
            return found_device
        
        logger.warning(f"Device with name containing '{device_name}' not found")
    
    # If platform specified
    if platform:
        platform_devices = find_devices_by_platform(devices, platform)
        if platform_devices:
            selected_device = platform_devices[0]
            logger.debug(f'Selected {platform} device: {selected_device.name}')
            return selected_device
        
        logger.warning(f'No {platform} devices found')
    
    # Auto-select first available device
    selected_device = devices[0]
    if selected_device:
        logger.debug(f'Auto-selected device: {selected_device.name} ({selected_device.platform})')
        return selected_device
    
    return None


def check_adb_availability() -> bool:
    """
    Check if adb is available (Android SDK).
    
    Returns:
        True if adb is available
    """
    try:
        _, _, return_code = _run_command(['adb', 'version'])
        return return_code == 0
    except Exception:
        return False


def validate_device(device: DeviceInfo) -> bool:
    """
    Validate device is ready for automation.
    
    Args:
        device: Device to validate
        
    Returns:
        True if device is ready
    """
    try:
        # Check if Android device is responsive
        stdout, _, return_code = _run_command(['adb', '-s', device.id, 'shell', 'echo', 'test'])
        return return_code == 0 and stdout.strip() == 'test'
    except Exception as e:
        logger.error(f'Device validation failed for {device.name}: {e}')
        return False

