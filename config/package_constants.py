"""
Package name constants for Android system and third-party applications.

All package names can be overridden via environment variables with sensible defaults.
This provides flexibility for different Android versions and device manufacturers.
"""

import os
from typing import List


class PackageConstants:
    """Centralized package name configuration with environment variable support."""
    
    # PCAPdroid package for traffic capture
    PCAPDROID_PACKAGE = os.getenv("PCAPDROID_PACKAGE", "com.emanuelef.remote_capture")
    
    # System UI package (essential for navigation)
    SYSTEM_UI_PACKAGE = os.getenv("SYSTEM_UI_PACKAGE", "com.android.systemui")
    
    # Default allowed external packages (can be extended via config)
    DEFAULT_ALLOWED_EXTERNAL_PACKAGES = [
        "com.google.android.gms",
        "com.android.chrome",
        "com.google.android.permissioncontroller",
    ]
    
    # System package prefixes (used to identify system packages)
    SYSTEM_PACKAGE_PREFIXES = [
        "android.",
        "com.android.",
        "com.google.android.",
        "com.qualcomm.",
        "com.qti.",
        "com.miui.",
        "com.xiaomi.",
        "vendor.",
        "org.ifaa.",
        "de.qualcomm.",
        "com.sec.",
        "com.samsung.",
        "com.huawei.",
    ]
    
    @classmethod
    def get_allowed_external_packages(cls, additional: List[str] = None) -> List[str]:
        """Get allowed external packages with optional additional packages."""
        packages = cls.DEFAULT_ALLOWED_EXTERNAL_PACKAGES.copy()
        if additional:
            packages.extend(additional)
        return list(set(packages))  # Remove duplicates
    
    @classmethod
    def is_system_package(cls, package_name: str) -> bool:
        """Check if a package name matches system package prefixes."""
        return any(package_name.startswith(prefix) for prefix in cls.SYSTEM_PACKAGE_PREFIXES)

