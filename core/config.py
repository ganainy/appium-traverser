"""
Configuration management for crawler settings.
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Configuration:
    """
    Represents shared settings for crawling behavior.
    """
    
    # Default fallback name
    DEFAULT_CONFIG_NAME = "default"
    # --- Schema Definition ---
    REQUIRED_SETTINGS = ["max_depth", "timeout", "platform"]
    VALID_PLATFORMS = ["android", "ios"]
    # --- Validation Rules ---
    MIN_DEPTH = 1
    MIN_TIMEOUT_SEC = 30

    def __init__(self, name: str, settings: Dict[str, Any], config_id: Optional[str] = None, is_default: bool = False):
        self.config_id = config_id or str(uuid.uuid4())
        self.name = name
        self.settings = settings
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.is_default = is_default

    def validate(self) -> None:
        """
        Validate configuration settings.
        """
        try:
            if not self.name or not isinstance(self.name, str):
                raise ValueError("Configuration name must be a non-empty string")

            if not isinstance(self.settings, dict):
                raise ValueError("Settings must be a dictionary")

            for key in self.REQUIRED_SETTINGS:
                if key not in self.settings:
                    raise ValueError(f"Required setting '{key}' is missing")

            if not isinstance(self.settings.get("max_depth"), int) or self.settings["max_depth"] < self.MIN_DEPTH:
                raise ValueError(f"max_depth must be at least {self.MIN_DEPTH}")

            if not isinstance(self.settings.get("timeout"), int) or self.settings["timeout"] < self.MIN_TIMEOUT_SEC:
                raise ValueError(f"timeout must be at least {self.MIN_TIMEOUT_SEC} seconds")

            if self.settings.get("platform") not in self.VALID_PLATFORMS:
                raise ValueError(f"platform must be one of {self.VALID_PLATFORMS}")

            logger.debug(f"Configuration '{self.name}' validated successfully")
        except Exception as e:
            logger.error(f"Configuration validation failed for '{self.name}': {e}")
            raise

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Configuration':
        """
        Create Configuration from dictionary.
        """
        return cls(
            name=data.get("name", cls.DEFAULT_CONFIG_NAME),
            settings=data.get("settings", {}),
            config_id=data.get("config_id"),
            is_default=data.get("is_default", False)
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Configuration to dictionary.
        """
        return {
            "config_id": self.config_id,
            "name": self.name,
            "settings": self.settings,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_default": self.is_default
        }