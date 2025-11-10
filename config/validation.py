"""
Configuration validation module.

This module provides validation functions for configuration values to ensure
they are within acceptable ranges and formats.
"""

import os
import re
from typing import List, Tuple, Optional, Dict, Any
from urllib.parse import urlparse

from config.numeric_constants import (
    XML_SNIPPET_MAX_LEN_MIN,
    XML_SNIPPET_MAX_LEN_MAX,
    IMAGE_MAX_WIDTH_MIN,
    IMAGE_MAX_WIDTH_MAX,
    IMAGE_QUALITY_MIN,
    IMAGE_QUALITY_MAX,
    CROP_PERCENT_MIN,
    CROP_PERCENT_MAX,
    MAX_CRAWL_STEPS_MIN,
    MAX_CRAWL_STEPS_MAX,
    MAX_CRAWL_DURATION_MIN_SECONDS,
    MAX_CRAWL_DURATION_MAX_SECONDS,
    APP_LAUNCH_WAIT_TIME_MIN,
    APP_LAUNCH_WAIT_TIME_MAX,
    VISUAL_SIMILARITY_THRESHOLD_MIN,
    VISUAL_SIMILARITY_THRESHOLD_MAX,
    MAX_CONSECUTIVE_FAILURES_MIN,
    MAX_CONSECUTIVE_FAILURES_MAX,
    WAIT_AFTER_ACTION_DEFAULT,
    STABILITY_WAIT_DEFAULT,
)
from config.urls import ServiceURLs
from domain.providers.enums import AIProvider


class ValidationError(Exception):
    """Raised when a configuration value fails validation."""
    pass


class ConfigValidator:
    """Validates configuration values."""
    
    @staticmethod
    def validate_url(url: str, name: str = "URL") -> Tuple[bool, Optional[str]]:
        """
        Validate a URL format.
        
        Args:
            url: The URL to validate
            name: Name of the URL field for error messages
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url or not isinstance(url, str):
            return False, f"{name} must be a non-empty string"
        
        try:
            result = urlparse(url)
            if not result.scheme or not result.netloc:
                return False, f"{name} must include scheme (http/https) and host"
            if result.scheme not in ('http', 'https'):
                return False, f"{name} must use http or https scheme"
        except Exception as e:
            return False, f"{name} is invalid: {str(e)}"
        
        return True, None
    
    @staticmethod
    def validate_numeric_range(
        value: Any,
        min_val: float,
        max_val: float,
        name: str = "Value",
        allow_none: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a numeric value is within a range.
        
        Args:
            value: The value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            name: Name of the field for error messages
            allow_none: Whether None is an acceptable value
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None:
            if allow_none:
                return True, None
            return False, f"{name} cannot be None"
        
        try:
            num_value = float(value)
            if num_value < min_val or num_value > max_val:
                return False, f"{name} must be between {min_val} and {max_val} (got {num_value})"
        except (ValueError, TypeError):
            return False, f"{name} must be a number (got {type(value).__name__})"
        
        return True, None
    
    @staticmethod
    def validate_integer_range(
        value: Any,
        min_val: int,
        max_val: int,
        name: str = "Value",
        allow_none: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate an integer value is within a range.
        
        Args:
            value: The value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            name: Name of the field for error messages
            allow_none: Whether None is an acceptable value
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None:
            if allow_none:
                return True, None
            return False, f"{name} cannot be None"
        
        try:
            int_value = int(value)
            if int_value < min_val or int_value > max_val:
                return False, f"{name} must be between {min_val} and {max_val} (got {int_value})"
        except (ValueError, TypeError):
            return False, f"{name} must be an integer (got {type(value).__name__})"
        
        return True, None
    
    @staticmethod
    def validate_ai_provider(provider: str) -> Tuple[bool, Optional[str]]:
        """
        Validate an AI provider name.
        
        Args:
            provider: The provider name to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not provider or not isinstance(provider, str):
            return False, "AI provider must be a non-empty string"
        
        try:
            AIProvider.from_string(provider)
            return True, None
        except ValueError as e:
            valid_providers = [p.value for p in AIProvider]
            return False, f"Invalid AI provider '{provider}'. Valid providers: {', '.join(valid_providers)}"
    
    @staticmethod
    def validate_package_name(package: str) -> Tuple[bool, Optional[str]]:
        """
        Validate an Android package name format.
        
        Args:
            package: The package name to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not package or not isinstance(package, str):
            return False, "Package name must be a non-empty string"
        
        # Android package name pattern: com.example.app (lowercase, dots, underscores)
        pattern = r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'
        if not re.match(pattern, package):
            return False, f"Invalid package name format: '{package}'. Must match pattern: com.example.app"
        
        return True, None
    
    @staticmethod
    def validate_crawl_mode(mode: str) -> Tuple[bool, Optional[str]]:
        """
        Validate crawl mode value.
        
        Args:
            mode: The crawl mode to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        valid_modes = ['steps', 'time']
        if not mode or not isinstance(mode, str):
            return False, "Crawl mode must be a non-empty string"
        
        if mode.lower() not in valid_modes:
            return False, f"Invalid crawl mode '{mode}'. Valid modes: {', '.join(valid_modes)}"
        
        return True, None
    
    @staticmethod
    def validate_image_format(format_str: str) -> Tuple[bool, Optional[str]]:
        """
        Validate image format value.
        
        Args:
            format_str: The image format to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        valid_formats = ['JPEG', 'WEBP', 'PNG']
        if not format_str or not isinstance(format_str, str):
            return False, "Image format must be a non-empty string"
        
        if format_str.upper() not in valid_formats:
            return False, f"Invalid image format '{format_str}'. Valid formats: {', '.join(valid_formats)}"
        
        return True, None
    
    @staticmethod
    def validate_config_dict(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a complete configuration dictionary.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate URLs
        if 'APPIUM_SERVER_URL' in config:
            is_valid, error = ConfigValidator.validate_url(config['APPIUM_SERVER_URL'], "APPIUM_SERVER_URL")
            if not is_valid:
                errors.append(error)
        
        if 'MOBSF_API_URL' in config:
            is_valid, error = ConfigValidator.validate_url(config['MOBSF_API_URL'], "MOBSF_API_URL")
            if not is_valid:
                errors.append(error)
        
        if 'OLLAMA_BASE_URL' in config:
            is_valid, error = ConfigValidator.validate_url(config['OLLAMA_BASE_URL'], "OLLAMA_BASE_URL")
            if not is_valid:
                errors.append(error)
        
        # Validate AI provider
        if 'AI_PROVIDER' in config:
            is_valid, error = ConfigValidator.validate_ai_provider(config['AI_PROVIDER'])
            if not is_valid:
                errors.append(error)
        
        # Validate numeric ranges
        if 'XML_SNIPPET_MAX_LEN' in config:
            is_valid, error = ConfigValidator.validate_integer_range(
                config['XML_SNIPPET_MAX_LEN'],
                XML_SNIPPET_MAX_LEN_MIN,
                XML_SNIPPET_MAX_LEN_MAX,
                "XML_SNIPPET_MAX_LEN"
            )
            if not is_valid:
                errors.append(error)
        
        if 'IMAGE_MAX_WIDTH' in config:
            is_valid, error = ConfigValidator.validate_integer_range(
                config['IMAGE_MAX_WIDTH'],
                IMAGE_MAX_WIDTH_MIN,
                IMAGE_MAX_WIDTH_MAX,
                "IMAGE_MAX_WIDTH"
            )
            if not is_valid:
                errors.append(error)
        
        if 'IMAGE_QUALITY' in config:
            is_valid, error = ConfigValidator.validate_integer_range(
                config['IMAGE_QUALITY'],
                IMAGE_QUALITY_MIN,
                IMAGE_QUALITY_MAX,
                "IMAGE_QUALITY"
            )
            if not is_valid:
                errors.append(error)
        
        if 'IMAGE_CROP_TOP_PERCENT' in config:
            is_valid, error = ConfigValidator.validate_numeric_range(
                config['IMAGE_CROP_TOP_PERCENT'],
                CROP_PERCENT_MIN,
                CROP_PERCENT_MAX,
                "IMAGE_CROP_TOP_PERCENT"
            )
            if not is_valid:
                errors.append(error)
        
        if 'IMAGE_CROP_BOTTOM_PERCENT' in config:
            is_valid, error = ConfigValidator.validate_numeric_range(
                config['IMAGE_CROP_BOTTOM_PERCENT'],
                CROP_PERCENT_MIN,
                CROP_PERCENT_MAX,
                "IMAGE_CROP_BOTTOM_PERCENT"
            )
            if not is_valid:
                errors.append(error)
        
        if 'MAX_CRAWL_STEPS' in config:
            is_valid, error = ConfigValidator.validate_integer_range(
                config['MAX_CRAWL_STEPS'],
                MAX_CRAWL_STEPS_MIN,
                MAX_CRAWL_STEPS_MAX,
                "MAX_CRAWL_STEPS"
            )
            if not is_valid:
                errors.append(error)
        
        if 'MAX_CRAWL_DURATION_SECONDS' in config:
            is_valid, error = ConfigValidator.validate_integer_range(
                config['MAX_CRAWL_DURATION_SECONDS'],
                MAX_CRAWL_DURATION_MIN_SECONDS,
                MAX_CRAWL_DURATION_MAX_SECONDS,
                "MAX_CRAWL_DURATION_SECONDS"
            )
            if not is_valid:
                errors.append(error)
        
        if 'APP_LAUNCH_WAIT_TIME' in config:
            is_valid, error = ConfigValidator.validate_numeric_range(
                config['APP_LAUNCH_WAIT_TIME'],
                APP_LAUNCH_WAIT_TIME_MIN,
                APP_LAUNCH_WAIT_TIME_MAX,
                "APP_LAUNCH_WAIT_TIME"
            )
            if not is_valid:
                errors.append(error)
        
        if 'VISUAL_SIMILARITY_THRESHOLD' in config:
            is_valid, error = ConfigValidator.validate_numeric_range(
                config['VISUAL_SIMILARITY_THRESHOLD'],
                VISUAL_SIMILARITY_THRESHOLD_MIN,
                VISUAL_SIMILARITY_THRESHOLD_MAX,
                "VISUAL_SIMILARITY_THRESHOLD"
            )
            if not is_valid:
                errors.append(error)
        
        if 'MAX_CONSECUTIVE_AI_FAILURES' in config:
            is_valid, error = ConfigValidator.validate_integer_range(
                config['MAX_CONSECUTIVE_AI_FAILURES'],
                MAX_CONSECUTIVE_FAILURES_MIN,
                MAX_CONSECUTIVE_FAILURES_MAX,
                "MAX_CONSECUTIVE_AI_FAILURES"
            )
            if not is_valid:
                errors.append(error)
        
        if 'MAX_CONSECUTIVE_MAP_FAILURES' in config:
            is_valid, error = ConfigValidator.validate_integer_range(
                config['MAX_CONSECUTIVE_MAP_FAILURES'],
                MAX_CONSECUTIVE_FAILURES_MIN,
                MAX_CONSECUTIVE_FAILURES_MAX,
                "MAX_CONSECUTIVE_MAP_FAILURES"
            )
            if not is_valid:
                errors.append(error)
        
        if 'MAX_CONSECUTIVE_EXEC_FAILURES' in config:
            is_valid, error = ConfigValidator.validate_integer_range(
                config['MAX_CONSECUTIVE_EXEC_FAILURES'],
                MAX_CONSECUTIVE_FAILURES_MIN,
                MAX_CONSECUTIVE_FAILURES_MAX,
                "MAX_CONSECUTIVE_EXEC_FAILURES"
            )
            if not is_valid:
                errors.append(error)
        
        # Validate crawl mode
        if 'CRAWL_MODE' in config:
            is_valid, error = ConfigValidator.validate_crawl_mode(config['CRAWL_MODE'])
            if not is_valid:
                errors.append(error)
        
        # Validate image format
        if 'IMAGE_FORMAT' in config:
            is_valid, error = ConfigValidator.validate_image_format(config['IMAGE_FORMAT'])
            if not is_valid:
                errors.append(error)
        
        # Validate package names in allowed external packages
        if 'ALLOWED_EXTERNAL_PACKAGES' in config:
            packages = config['ALLOWED_EXTERNAL_PACKAGES']
            if isinstance(packages, list):
                for i, package in enumerate(packages):
                    is_valid, error = ConfigValidator.validate_package_name(package)
                    if not is_valid:
                        errors.append(f"ALLOWED_EXTERNAL_PACKAGES[{i}]: {error}")
        
        return len(errors) == 0, errors

