"""
Configuration management for crawler settings.
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


class Configuration:
    """Represents shared settings for crawling behavior."""
    # --- Schema Definition ---
    REQUIRED_SETTINGS = ["max_depth", "timeout", "platform"]
    VALID_PLATFORMS = ["android", "ios"]
    # --- Validation Rules ---
    MIN_DEPTH = 1
    MIN_TIMEOUT_SEC = 30

    def __init__(self, name: str, settings: Dict[str, Any], *, is_default: bool = False):
        self.config_id = str(uuid.uuid4())
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
                raise ValueError("max_depth must be a positive integer")

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
        if "name" not in data or "settings" not in data:
            raise ValueError("Configuration data must include 'name' and 'settings'")

        config = cls(
            name=data["name"],
            settings=data["settings"],
            is_default=bool(data.get("is_default", False))
        )

        config_id = data.get("config_id")
        if config_id:
            config.config_id = config_id

        created_at = data.get("created_at")
        if created_at:
            config.created_at = datetime.fromisoformat(created_at)

        updated_at = data.get("updated_at")
        if updated_at:
            config.updated_at = datetime.fromisoformat(updated_at)

        return config

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