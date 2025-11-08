# -*- coding: utf-8 -*-
"""
Shared utilities for Android app discovery via ADB.

This module provides common functionality used by both the app discovery script
(domain/find_app_info.py) and the UI wrapper (ui/app_scanner_ui.py) for discovering
and managing Android applications.
"""

import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

from config.config import Config


def get_device_id() -> str:
    """
    Get the ID of the currently connected Android device via ADB.

    Uses `adb get-serialno` to get device ID.

    Returns:
        str: Sanitized device ID, or "unknown_device" if unable to detect

    Examples:
        >>> device_id = get_device_id()
        >>> print(device_id)  # "emulator-5554" or "FA8AX1A00D" etc.
    """
    try:
        # Try get-serialno
        result = subprocess.run(
            ["adb", "get-serialno"], capture_output=True, text=True, timeout=5
        )
        if (
            result.returncode == 0
            and result.stdout.strip()
            and result.stdout.strip() != "unknown"
        ):
            device_id = result.stdout.strip()
            return re.sub(r"[^\w\-.]", "_", device_id)
        return "unknown_device"

    except Exception:
        return "unknown_device"


def get_app_cache_path(
    device_id: str, config: Config, base_dir: Optional[str] = None
) -> str:
    """
    Get the device-specific cache file path for app info.
    
    Constructs the full path to the app cache JSON file and ensures the
    directory structure exists.
    
    Args:
        device_id: Device identifier (should be sanitized for filenames)
        config: Config instance for OUTPUT_DATA_DIR setting
        base_dir: Optional base directory override (defaults to config.BASE_DIR parent)
    
    Returns:
        str: Full path to device cache file following the pattern:
             {base_dir}/output_data/app_info/{device_id}/device_{device_id}_app_info.json
    
    Raises:
        OSError: If directory creation fails
        
    Examples:
        >>> from config.config import Config
        >>> cfg = Config()
        >>> path = get_app_cache_path("emulator-5554", cfg)
        >>> print(path)  # e.g., "/path/to/output_data/app_info/emulator-5554/..."
    """
    # Handle None device_id
    if not device_id:
        device_id = "unknown_device"
    
    # Determine base directory
    if base_dir is None:
        # Default: project root found using marker files
        from pathlib import Path
        from utils.paths import find_project_root
        base_dir = str(find_project_root(Path(config.BASE_DIR)))
    
    # Get output data directory from config
    output_data_dir = getattr(config, "OUTPUT_DATA_DIR", "output_data")
    
    # Construct the app info directory
    app_info_dir = os.path.join(base_dir, output_data_dir, "app_info", device_id)
    
    # Ensure directory exists
    os.makedirs(app_info_dir, exist_ok=True)
    
    # Build the full cache file path
    cache_filename = f"device_{device_id}_app_info.json"
    cache_path = os.path.join(app_info_dir, cache_filename)
    
    return cache_path


