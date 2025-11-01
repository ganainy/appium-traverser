#!/usr/bin/env python3
"""
Service names constants for CLI context services.

This module centralizes all service name strings used throughout the CLI
to ensure consistency and make it easy to reference services across features.
"""

# Database service - used for all database operations including focus areas, etc.
DATABASE_SERVICE = "database"

# Configuration service - used for managing user configuration
CONFIG_SERVICE = "config"

# Logging service (if implemented)
LOGGING_SERVICE = "logging"

# App discovery/scanning service
APP_SCANNER_SERVICE = "app_scanner"

# Device service (if implemented)
DEVICE_SERVICE = "device"

# Additional services can be added here as features are implemented
