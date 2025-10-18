#!/usr/bin/env python3
"""
Device service for ADB device management.
"""

import logging
import subprocess
from typing import List, Optional

from ..shared.context import CLIContext


class DeviceService:
    """Service for managing ADB devices."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def list_devices(self) -> List[str]:
        """List all connected ADB devices.
        
        Returns:
            List of device UDIDs
        """
        try:
            result = subprocess.run(
                ["adb", "devices"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            devices = []
            for line in result.stdout.strip().split("\n")[1:]:
                if "\tdevice" in line:
                    devices.append(line.split("\t")[0])
            return devices
        except FileNotFoundError:
            self.logger.error("ADB command not found. Is Android SDK platform-tools in your PATH?")
            return []
        except Exception as e:
            self.logger.error(f"Error listing devices: {e}")
            return []
    
    def select_device(self, device_udid: str) -> bool:
        """Select a device by UDID and save to configuration.
        
        Args:
            device_udid: Device UDID to select
            
        Returns:
            True if successful, False otherwise
        """
        # Verify device exists
        devices = self.list_devices()
        if device_udid not in devices:
            self.logger.error(f"Device '{device_udid}' not found in connected devices.")
            return False
        
        # Save to configuration
        try:
            config_service = self.context.services.get("config")
            if config_service:
                config_service.set_value("DEVICE_UDID", device_udid)
                config_service.save()
                self.logger.info(f"Successfully selected device: {device_udid}")
                return True
            else:
                self.logger.error("Config service not available")
                return False
        except Exception as e:
            self.logger.error(f"Error saving device selection: {e}")
            return False
    
    def auto_select_device(self) -> bool:
        """Automatically select the first available device.
        
        Returns:
            True if successful, False otherwise
        """
        devices = self.list_devices()
        if not devices:
            self.logger.error("No connected devices found.")
            return False
        
        return self.select_device(devices[0])