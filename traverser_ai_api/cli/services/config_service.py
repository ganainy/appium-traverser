"""
Configuration service for CLI operations.
"""

import json
import logging
from typing import Any, Dict, Optional, get_type_hints

from ..shared.context import CLIContext


class ConfigService:
    """Service for managing configuration operations."""
    
    def __init__(self, context: CLIContext):
        """
        Initialize config service.
        
        Args:
            context: CLI context
        """
        self.context = context
        self.config = context.config
    
    def show_config(self, filter_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current configuration.
        
        Args:
            filter_key: Optional key to filter by
            
        Returns:
            Configuration dictionary
        """
        config_to_display = self.config._get_user_savable_config()
        
        if filter_key:
            filtered_config = {
                k: v for k, v in config_to_display.items() 
                if filter_key.lower() in k.lower()
            }
            return filtered_config
        
        return config_to_display
    
    def set_config_value(self, key: str, value_str: str) -> bool:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value_str: Value as string
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logging.debug(f"Setting config: {key} = '{value_str}'")
            
            # Try smarter parsing for complex types
            parsed_value = self._parse_value(key, value_str)
            
            self.config.update_setting_and_save(key, parsed_value)
            return True
            
        except Exception as e:
            logging.error(f"Failed to set config for {key}: {e}", exc_info=True)
            return False
    
    def save_all_changes(self) -> bool:
        """
        Save all configuration changes.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logging.debug("Saving all configuration changes...")
            self.config.save_user_config()
            return True
        except Exception as e:
            logging.error(f"Failed to save configuration: {e}", exc_info=True)
            return False
    
    def _parse_value(self, key: str, value_str: str) -> Any:
        """
        Parse a value string to the appropriate type.
        
        Args:
            key: Configuration key
            value_str: Value as string
            
        Returns:
            Parsed value
        """
        # Default to string
        parsed_value = value_str
        
        try:
            # Get type hints for the config
            type_hints = get_type_hints(type(self.config))
            target_hint = type_hints.get(key)
            
            if target_hint:
                origin_type = getattr(target_hint, "__origin__", None)
                
                # If value looks like JSON or target expects list/dict, attempt JSON parse
                looks_like_json = value_str.strip().startswith(("[", "{", '"'))
                if looks_like_json or origin_type in (list, dict):
                    try:
                        parsed_value = json.loads(value_str)
                        logging.debug(f"Parsed JSON for {key}: type={type(parsed_value)}")
                    except Exception:
                        # Fall back to raw string if JSON parsing fails
                        logging.debug(f"JSON parsing failed for {key}, using string value")
                        parsed_value = value_str
                else:
                    # Try to parse as basic types
                    parsed_value = self._parse_basic_type(value_str, target_hint)
            
        except Exception as e:
            logging.debug(f"Error parsing value for {key}: {e}, using string")
            parsed_value = value_str
        
        return parsed_value
    
    def _parse_basic_type(self, value_str: str, target_type: type) -> Any:
        """
        Parse a string to a basic type.
        
        Args:
            value_str: Value as string
            target_type: Target type
            
        Returns:
            Parsed value
        """
        # Handle boolean values
        if target_type == bool:
            lower_val = value_str.lower()
            if lower_val in ('true', '1', 'yes', 'on'):
                return True
            elif lower_val in ('false', '0', 'no', 'off'):
                return False
            else:
                return bool(value_str)
        
        # Handle integer values
        if target_type == int:
            try:
                return int(value_str)
            except ValueError:
                return value_str
        
        # Handle float values
        if target_type == float:
            try:
                return float(value_str)
            except ValueError:
                return value_str
        
        # Default to string
        return value_str
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        return getattr(self.config, key, default)
    
    def validate_config(self) -> Dict[str, Any]:
        """
        Validate current configuration.
        
        Returns:
            Validation result with any issues found
        """
        issues = []
        warnings = []
        
        # Check required configuration
        required_keys = [
            'APP_PACKAGE',
            'APP_ACTIVITY',
            'OUTPUT_DATA_DIR',
            'BASE_DIR'
        ]
        
        for key in required_keys:
            if not getattr(self.config, key, None):
                issues.append(f"Missing required configuration: {key}")
        
        # Check optional but recommended configuration
        recommended_keys = [
            'APPIUM_SERVER_URL',
            'AI_PROVIDER',
            'DEFAULT_MODEL_TYPE'
        ]
        
        for key in recommended_keys:
            if not getattr(self.config, key, None):
                warnings.append(f"Missing recommended configuration: {key}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }