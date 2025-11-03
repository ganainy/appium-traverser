"""
Configuration service for CLI operations.
"""

import json
import logging
from typing import Any, Dict, List, Optional, get_type_hints

from cli.shared.context import CLIContext
from cli.commands.base import CommandResult
from cli.constants.keys import VALID_AI_PROVIDERS


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
    
    def set_and_save_from_pairs(self, kv_pairs: List[str]) -> bool:
        """
        Set and save configuration values from a list of KEY=VALUE pairs.
        
        Args:
            kv_pairs: List of key=value pairs
            
        Returns:
            True if all pairs were processed successfully, False otherwise
        """
        telemetry = self.context.services.get("telemetry")
        success_count = 0
        total_count = len(kv_pairs)
        
        for kv_pair in kv_pairs:
            if "=" not in kv_pair:
                telemetry.print_error(f"Invalid format: {kv_pair}. Use KEY=VALUE format.")
                continue
            
            key, value = kv_pair.split("=", 1)
            if self.set_config_value(key.strip(), value.strip()):
                success_count += 1
                telemetry.print_success(f"Set {key} = {value}")
            else:
                telemetry.print_error(f"Failed to set {key}")
        
        # Save all changes
        if success_count > 0:
            if self.save_all_changes():
                telemetry.print_success("Configuration saved successfully")
            else:
                telemetry.print_warning("Configuration updated but failed to save")
        
        return success_count == total_count
    
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
    
    def get_deserialized_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value and deserialize it from JSON if it's a string.
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Deserialized configuration value or default
        """
        value = getattr(self.config, key, default)
        
        # Handle case where value might be stored as JSON string
        if value and isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        
        return value
    
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
            'MCP_SERVER_URL',
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
    
    def switch_ai_provider(self, provider: str, model: Optional[str] = None) -> CommandResult:
        """
        Switch the AI provider and optionally set the model.
        
        Args:
            provider: AI provider to use (gemini, openrouter, ollama)
            model: Optional model name/alias to use
            
        Returns:
            CommandResult indicating success or failure
        """
        # Validate provider
        if provider not in VALID_AI_PROVIDERS:
            return CommandResult(
                success=False,
                message=f"[ERROR] Invalid provider: {provider}",
                exit_code=1
            )
        
        try:
            # Update provider
            self.config.set("AI_PROVIDER", provider)
            
            # Update model if provided
            if model:
                self.config.set("DEFAULT_MODEL_TYPE", model)
            
            # Save configuration (no-op for SQLite-backed config, but kept for compatibility)
            self.config.save_user_config()
            
            return CommandResult(
                success=True,
                message=f"Provider switched to '{provider}'. Please restart session/command if required.",
                exit_code=0
            )
            
        except Exception as e:
            logging.error(f"Failed to switch AI provider: {e}", exc_info=True)
            return CommandResult(
                success=False,
                message=f"[ERROR] Failed to switch provider: {str(e)}",
                exit_code=1
            )
