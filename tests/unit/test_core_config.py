"""
Unit tests for core Configuration class.
"""
import pytest
from core.config import Configuration


class TestConfiguration:
    """Test Configuration class functionality."""

    def test_init_default(self):
        """Test Configuration initialization with defaults."""
        config = Configuration(name="test", settings={"max_depth": 5, "timeout": 60, "platform": "android"})

        assert config.name == "test"
        assert config.settings["max_depth"] == 5
        assert config.is_default is False
        assert config.config_id is not None

    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        config = Configuration(
            name="valid",
            settings={"max_depth": 3, "timeout": 120, "platform": "android"}
        )

        # Should not raise
        config.validate()

    def test_validate_invalid_name(self):
        """Test validation rejects invalid names."""
        config = Configuration(name="", settings={"max_depth": 1, "timeout": 30, "platform": "android"})

        with pytest.raises(ValueError, match="name must be a non-empty string"):
            config.validate()

    def test_validate_missing_required_setting(self):
        """Test validation rejects missing required settings."""
        config = Configuration(name="test", settings={"max_depth": 1})  # missing timeout and platform

        with pytest.raises(ValueError, match="Required setting 'timeout' is missing"):
            config.validate()

    def test_validate_invalid_max_depth(self):
        """Test validation rejects invalid max_depth."""
        config = Configuration(
            name="test",
            settings={"max_depth": 0, "timeout": 30, "platform": "android"}
        )

        with pytest.raises(ValueError, match="max_depth must be a positive integer"):
            config.validate()

    def test_validate_invalid_platform(self):
        """Test validation rejects invalid platform."""
        config = Configuration(
            name="test",
            settings={"max_depth": 1, "timeout": 30, "platform": "invalid"}
        )

        with pytest.raises(ValueError, match="platform must be one of"):
            config.validate()

    def test_from_dict(self):
        """Test creating Configuration from dictionary."""
        data = {
            "name": "from_dict",
            "settings": {"max_depth": 2, "timeout": 90, "platform": "ios"},
            "is_default": True
        }

        config = Configuration.from_dict(data)

        assert config.name == "from_dict"
        assert config.settings["platform"] == "ios"
        assert config.is_default is True

    def test_to_dict(self):
        """Test converting Configuration to dictionary."""
        config = Configuration(
            name="to_dict_test",
            settings={"max_depth": 4, "timeout": 180, "platform": "android"}
        )

        data = config.to_dict()

        assert data["name"] == "to_dict_test"
        assert data["settings"]["max_depth"] == 4
        assert "config_id" in data
        assert "created_at" in data