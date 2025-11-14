#!/usr/bin/env python3
"""
Device service for ADB device management.
"""

import logging
from typing import List, Optional

from cli.shared.context import ApplicationContext
from utils.adb_utils import AdbAdapter


class DeviceService:
    """Service for managing ADB devices."""
    
    def __init__(self, context: ApplicationContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
        self.adb_adapter = AdbAdapter()
    
    def list_devices(self) -> List[str]:
        """List all connected ADB devices.
        
        Returns:
            List of device UDIDs
        """
        return self.adb_adapter.get_connected_devices()
    
    def is_device_connected(self, device_udid: str) -> bool:
        """Check if a device with the given UDID is connected.
        
        Args:
            device_udid: Device UDID to check
            
        Returns:
            True if device is connected, False otherwise
        """
        devices = self.list_devices()
        return device_udid in devices
    
    def auto_select_device(self) -> Optional[str]:
        """Get the UDID of the first available device.
        
        Returns:
            First device UDID if available, None otherwise
        """
        devices = self.list_devices()
        return devices[0] if devices else None
