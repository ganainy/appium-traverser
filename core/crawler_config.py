"""
Crawler session configuration management.

This module provides the Configuration class for managing crawler-specific settings
that are tied to individual crawler sessions. These settings include:
- max_depth: Maximum depth for crawling
- timeout: Timeout for crawler operations
- platform: Target platform (e.g., "android")

This is a domain model in the core layer, representing a specific crawler session's
configuration. It has strict validation, schema enforcement, and is persisted
alongside crawler sessions in the database.

Usage:
    from core.crawler_config import Configuration, ConfigurationError
    
    config = Configuration(
        name="My Crawler Config",
        settings={"max_depth": 10, "timeout": 300, "platform": "android"}
    )
    crawler = Crawler(config)

Note: This is different from config.app_config.Config, which manages
application-wide settings (AI providers, paths, features, etc.).
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigurationError(ValueError):
    """Base exception for configuration-related errors."""
    pass


class Configuration:
    """Represents shared settings for crawling behavior."""
    # --- Schema Definition ---
    REQUIRED_SETTINGS = ["max_depth", "timeout", "platform"]
    VALID_PLATFORMS = ["android"]
    # --- Validation Rules ---
    MIN_DEPTH = 1
    MAX_DEPTH = 1000  # Reasonable upper limit to prevent resource exhaustion
    MIN_TIMEOUT_SEC = 30
    MAX_TIMEOUT_SEC = 86400  # 24 hours - reasonable upper limit

    def __init__(
        self,
        name: str,
        settings: Dict[str, Any],
        *,
        is_default: bool = False,
        validate_on_init: bool = True
    ):
        """
        Initialize Configuration instance.
        
        Args:
            name: Configuration name (must be non-empty string)
            settings: Dictionary of configuration settings
            is_default: Whether this is a default configuration
            validate_on_init: If True, validate immediately after initialization
            
        Raises:
            ConfigurationError: If validation fails and validate_on_init is True
        """
        self.config_id = str(uuid.uuid4())
        self.name = name
        # Create a copy to prevent external mutation without validation
        self.settings = dict(settings) if isinstance(settings, dict) else settings
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.is_default = bool(is_default)
        
        if validate_on_init:
            self.validate()

    def validate(self) -> None:
        """
        Validate configuration settings.
        
        Raises:
            ConfigurationError: If validation fails with specific error message
        """
        # Validate name
        if not self.name or not isinstance(self.name, str):
            raise ConfigurationError("Configuration name must be a non-empty string")

        # Validate settings is a dictionary
        if not isinstance(self.settings, dict):
            raise ConfigurationError("Settings must be a dictionary")

        # Check required settings
        for key in self.REQUIRED_SETTINGS:
            if key not in self.settings:
                raise ConfigurationError(f"Required setting '{key}' is missing")

        # Validate max_depth
        max_depth = self.settings.get("max_depth")
        if not isinstance(max_depth, int):
            raise ConfigurationError("max_depth must be an integer")
        if max_depth < self.MIN_DEPTH:
            raise ConfigurationError(
                f"max_depth must be at least {self.MIN_DEPTH}, got {max_depth}"
            )
        if max_depth > self.MAX_DEPTH:
            raise ConfigurationError(
                f"max_depth must be at most {self.MAX_DEPTH}, got {max_depth}"
            )

        # Validate timeout
        timeout = self.settings.get("timeout")
        if not isinstance(timeout, int):
            raise ConfigurationError("timeout must be an integer")
        if timeout < self.MIN_TIMEOUT_SEC:
            raise ConfigurationError(
                f"timeout must be at least {self.MIN_TIMEOUT_SEC} seconds, got {timeout}"
            )
        if timeout > self.MAX_TIMEOUT_SEC:
            raise ConfigurationError(
                f"timeout must be at most {self.MAX_TIMEOUT_SEC} seconds, got {timeout}"
            )

        # Validate platform
        platform = self.settings.get("platform")
        if platform not in self.VALID_PLATFORMS:
            raise ConfigurationError(
                f"platform must be one of {self.VALID_PLATFORMS}, got '{platform}'"
            )

        logger.debug(f"Configuration '{self.name}' validated successfully")

    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """
        Update configuration settings with validation.
        
        This method validates the new settings before applying them and updates
        the updated_at timestamp.
        
        Args:
            new_settings: Dictionary of settings to update (merged with existing)
            
        Raises:
            ConfigurationError: If validation fails after update
        """
        # Create a copy of current settings and merge with new ones
        updated_settings = dict(self.settings)
        updated_settings.update(new_settings)
        
        # Temporarily update settings for validation
        original_settings = self.settings
        self.settings = updated_settings
        
        try:
            self.validate()
            # Validation passed, update timestamp
            self.updated_at = datetime.now()
        except ConfigurationError:
            # Restore original settings on validation failure
            self.settings = original_settings
            raise

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        validate_on_init: bool = True
    ) -> 'Configuration':
        """
        Create Configuration from dictionary.
        
        Args:
            data: Dictionary containing configuration data
            validate_on_init: If True, validate after deserialization
            
        Returns:
            Configuration instance
            
        Raises:
            ConfigurationError: If data is invalid or validation fails
        """
        if not isinstance(data, dict):
            raise ConfigurationError("Configuration data must be a dictionary")
        
        if "name" not in data or "settings" not in data:
            raise ConfigurationError("Configuration data must include 'name' and 'settings'")
        
        if not isinstance(data["settings"], dict):
            raise ConfigurationError("Configuration 'settings' must be a dictionary")

        config = cls(
            name=data["name"],
            settings=data["settings"],
            is_default=bool(data.get("is_default", False)),
            validate_on_init=validate_on_init
        )

        # Restore config_id if provided
        config_id = data.get("config_id")
        if config_id:
            if not isinstance(config_id, str):
                raise ConfigurationError("config_id must be a string")
            # Validate UUID format - must be a valid UUID
            try:
                uuid.UUID(config_id)
            except (ValueError, TypeError) as e:
                raise ConfigurationError(f"config_id '{config_id}' is not a valid UUID format: {e}")
            config.config_id = config_id

        # Restore timestamps with error handling
        created_at = data.get("created_at")
        if created_at:
            config.created_at = cls._parse_datetime(created_at, "created_at")
        else:
            # If not provided, use current time
            config.created_at = datetime.now()

        updated_at = data.get("updated_at")
        if updated_at:
            config.updated_at = cls._parse_datetime(updated_at, "updated_at")
        else:
            # If not provided, use current time
            config.updated_at = datetime.now()

        return config

    @staticmethod
    def _parse_datetime(value: Any, field_name: str) -> datetime:
        """
        Parse datetime from various formats with fallback handling.
        
        Args:
            value: Datetime value (string, datetime object, or None)
            field_name: Name of the field for error messages
            
        Returns:
            Parsed datetime object
            
        Raises:
            ConfigurationError: If datetime cannot be parsed
        """
        if isinstance(value, datetime):
            return value
        
        if not isinstance(value, str):
            raise ConfigurationError(
                f"{field_name} must be a string or datetime object, got {type(value).__name__}"
            )
        
        # Try ISO format first (most common)
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            pass
        
        # Try common alternative formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except (ValueError, TypeError):
                continue
        
        # If all parsing attempts fail, raise error
        raise ConfigurationError(
            f"Unable to parse {field_name} datetime from '{value}'. "
            f"Expected ISO format (YYYY-MM-DDTHH:MM:SS) or datetime object."
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Configuration to dictionary.
        
        Returns:
            Dictionary representation of the configuration
        """
        return {
            "config_id": self.config_id,
            "name": self.name,
            "settings": dict(self.settings),  # Return a copy
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_default": self.is_default
        }

