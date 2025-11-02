# -*- coding: utf-8 -*-
"""
Shared utilities for Android app discovery via ADB.

This module provides common functionality used by both the standalone CLI script
(find_app_info.py) and the UI wrapper (health_app_scanner.py) for discovering
and filtering Android applications.
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
    
    Attempts multiple strategies:
    1. Try `adb get-serialno` (fastest path)
    2. Fallback to `adb devices` parsing
    3. On timeout, retry with longer timeout (10s)
    4. Sanitize device ID for use in filenames (replace invalid chars with underscore)
    
    Returns:
        str: Sanitized device ID, or "unknown_device" if unable to detect
        
    Examples:
        >>> device_id = get_device_id()
        >>> print(device_id)  # "emulator-5554" or "FA8AX1A00D" etc.
    """
    try:
        # Try get-serialno (fast path)
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

        # Fallback to `adb devices`
        devices_result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=6
        )
        if devices_result.returncode == 0:
            lines = devices_result.stdout.strip().splitlines()
            device_lines = [
                line for line in lines[1:] if line.strip() and "\tdevice" in line
            ]
            if device_lines:
                device_id = device_lines[0].split("\t")[0].strip()
                return re.sub(r"[^\w\-.]", "_", device_id)
        return "unknown_device"
        
    except subprocess.TimeoutExpired:
        # Retry with longer timeout on timeout
        try:
            devices_result = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=10
            )
            if devices_result.returncode == 0:
                lines = devices_result.stdout.strip().splitlines()
                device_lines = [
                    line for line in lines[1:] if line.strip() and "\tdevice" in line
                ]
                if device_lines:
                    device_id = device_lines[0].split("\t")[0].strip()
                    return re.sub(r"[^\w\-.]", "_", device_id)
        except Exception:
            pass
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
        # Default: parent of config.BASE_DIR (typically project root)
        base_dir = os.path.abspath(os.path.join(config.BASE_DIR, ".."))
    
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


def heuristic_health_filter(
    apps: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Fallback keyword-based filter for health-related apps.
    
    Filters applications whose `app_name` or `package_name` contains
    health/fitness/wellness keywords. Used as a fallback when AI filtering
    is unavailable or disabled.
    
    Args:
        apps: List of app info dictionaries with 'app_name' and 'package_name' keys
    
    Returns:
        List of filtered app dictionaries matching health/fitness criteria.
        Returns empty list if input is None or empty.
        
    Examples:
        >>> apps = [
        ...     {"app_name": "Google Fit", "package_name": "com.google.android.apps.fitness"},
        ...     {"app_name": "Chrome", "package_name": "com.android.chrome"},
        ... ]
        >>> health_apps = heuristic_health_filter(apps)
        >>> len(health_apps)
        1
    """
    if not apps:
        return []
    
    # Keywords for health/fitness/wellness apps
    health_keywords = [
        "health",
        "fitness",
        "fit",
        "wellness",
        "med",
        "medical",
        "care",
        "doctor",
        "patient",
        "pill",
        "medication",
        "pharma",
        "drug",
        "clinic",
        "hosp",
        "hospital",
        "therapy",
        "mental",
        "mind",
        "sleep",
        "diet",
        "calorie",
        "nutrition",
        "run",
        "workout",
        "yoga",
        "step",
        "heart",
        "bp",
        "blood",
        "sugar",
        "diabetes",
    ]
    
    filtered = []
    for app in apps:
        # Get app name and package name, handling None/missing values
        app_name = app.get("app_name") or ""
        package_name = app.get("package_name") or ""
        
        # Combine for searching (case-insensitive)
        search_text = (app_name + " " + package_name).lower()
        
        # Check if any keyword matches
        if any(keyword in search_text for keyword in health_keywords):
            filtered.append(app)
    
    return filtered
