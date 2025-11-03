#!/usr/bin/env python3
"""
ADB utility functions and adapter for device management.
"""

import logging
import subprocess
from typing import List

from cli.constants import keys as KEY
from cli.constants import messages as MSG


class AdbAdapter:
    """Adapter for ADB command operations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_connected_devices(self) -> List[str]:
        """Get all connected ADB devices.
        
        Returns:
            List of device UDIDs
        """
        try:
            result = subprocess.run(
                [KEY.ADB_COMMAND, KEY.ADB_DEVICES_COMMAND],
                capture_output=True,
                text=True,
                check=True
            )
            devices = []
            for line in result.stdout.strip().split("\n")[1:]:
                if KEY.ADB_DEVICE_STATUS_SEPARATOR in line:
                    devices.append(line.split("\t")[0])
            return devices
        except FileNotFoundError:
            self.logger.error(MSG.ERR_ADB_NOT_FOUND)
            return []
        except Exception as e:
            self.logger.error(MSG.ERR_ADB_LIST_DEVICES.format(error=e))
            return []