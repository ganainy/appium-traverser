"""
Application-wide configuration management.

This module provides the Config class for managing application-wide settings
throughout the entire application. It handles:
- AI provider settings (Gemini, OpenRouter, Ollama)
- Path configurations (output directories, session paths, etc.)
- Feature flags and application behavior settings
- User preferences and environment variable overrides

The Config class uses a three-layer precedence system:
1. User storage (SQLite database) - persistent user settings
2. Environment variables
3. Module defaults (fallback only)

This is an infrastructure layer component that provides application-wide
configuration. It has no strict schema and uses a flexible key-value store.

Usage:
    from config.app_config import Config
    
    config = Config()
    api_key = config.GEMINI_API_KEY
    output_dir = config.OUTPUT_DATA_DIR

Note: This is different from core.crawler_config.Configuration, which manages
crawler session-specific settings (max_depth, timeout, platform).
"""

import os
import copy
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from cli.commands.base import CommandResult
from datetime import datetime
from infrastructure.user_config_store import UserConfigStore
from utils.paths import SessionPathManager
from cli.constants.keys import CONFIG_OUTPUT_DATA_DIR

# --- Refactored Centralized Configuration Class ---
class Config:
    """
    Central configuration class with simplified two-layer system:
    - Secrets: Environment variables only (API keys, sensitive data)
    - Everything else: SQLite only (int, str, bool, float values)
    
    On first launch, SQLite is populated with simple defaults from module constants.
    Module defaults are only used for initial population, not as runtime fallback.
    """
    def __init__(self, user_store: Optional[UserConfigStore] = None):
        self._defaults = type('Defaults', (), {})()  # Empty defaults object as placeholder
        self._user_store = user_store or UserConfigStore()
        self._env = os.environ
        # Load .env file if it exists
        try:
            from dotenv import load_dotenv
            dotenv_path = os.path.join(os.getcwd(), '.env')
            load_dotenv(dotenv_path)
            self._env = os.environ  # Refresh after loading
        except ImportError:
            logging.warning("python-dotenv not available, skipping .env loading")
        except Exception as e:
            logging.warning(f"Error loading .env: {e}")
        self._secrets = {"OPENROUTER_API_KEY", "GEMINI_API_KEY", "OLLAMA_BASE_URL", "MOBSF_API_KEY"}
        self._init_paths()
        self._path_manager = SessionPathManager(self)
        # Collect default settings snapshot for to_dict() and reset_settings()
        self._default_snapshot = self._collect_default_settings()
        # Initialize SQLite with simple defaults on first launch
        self._user_store.initialize_simple_defaults(self._default_snapshot)
        # Initialize default crawler actions on first launch
        module_globals = globals()
        if 'CRAWLER_AVAILABLE_ACTIONS' in module_globals:
            default_actions = module_globals['CRAWLER_AVAILABLE_ACTIONS']
            if isinstance(default_actions, dict):
                self._user_store.initialize_default_actions(default_actions)
        # Initialize ALLOWED_EXTERNAL_PACKAGES separately (it's a list, not a simple type)
        # Check if it's already in the database, and if not, initialize it
        # This handles both first launch and existing databases that don't have this key
        existing_value = self._user_store.get('ALLOWED_EXTERNAL_PACKAGES')
        if existing_value is None:
            module_globals = globals()
            if 'ALLOWED_EXTERNAL_PACKAGES' in module_globals:
                allowed_packages = module_globals['ALLOWED_EXTERNAL_PACKAGES']
                if isinstance(allowed_packages, list):
                    self._user_store.set('ALLOWED_EXTERNAL_PACKAGES', allowed_packages)

    def _init_paths(self):
        # Initialize path-related attributes used across the project
        self.BASE_DIR = os.path.abspath(os.path.dirname(__file__))
        # Placeholder for session-specific metadata (non-persistent)
        self._session_context: Dict[str, Any] = {}
    
    @property
    def SHUTDOWN_FLAG_PATH(self) -> str:
        """Return absolute path to shutdown flag file in project root."""
        return os.path.abspath(os.path.join(self._project_root(), "shutdown.flag"))

    def _project_root(self) -> str:
        """Return absolute project root using marker file detection."""
        from utils.paths import find_project_root
        return str(find_project_root(Path(self.BASE_DIR)))

    @property
    def PROJECT_ROOT(self):
        """Return absolute project root path."""
        return self._project_root()

    def _resolve_output_dir_value(self, value: Optional[str]) -> Optional[str]:
        """Resolve OUTPUT_DATA_DIR to an absolute path under project root when relative."""
        if not value:
            return value
        if os.path.isabs(value):
            return value
        return os.path.abspath(os.path.join(self._project_root(), value))

    def _resolve_output_dir_placeholder(self, template: Optional[str]) -> Optional[str]:
        """Replace the {OUTPUT_DATA_DIR} placeholder with the resolved OUTPUT_DATA_DIR path."""
        if not template or not isinstance(template, str):
            return template
        placeholder = f"{{{CONFIG_OUTPUT_DATA_DIR}}}"
        if placeholder in template:
            output_dir = self.OUTPUT_DATA_DIR
            if not output_dir:
                # If OUTPUT_DATA_DIR is not set, return None instead of using fallback
                return None
            return template.replace(placeholder, output_dir)
        return template

    def _is_secret(self, key: str) -> bool:
        upper_key = key.upper()
        if upper_key in self._secrets:
            return True
        return key == upper_key and upper_key.endswith("_KEY")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with simplified two-layer system.
        
        - If secret: check environment variables only
        - If not secret: check SQLite only
        
        Args:
            key: Configuration key
            default: Default value to return if not found
            
        Returns:
            Configuration value or default
        """
        # Check if this is a secret (API keys, etc.)
        if self._is_secret(key):
            # Secrets: environment variables only
            normalized_key = key.upper()
            env_value = self._env.get(key)
            if env_value is None and normalized_key != key:
                env_value = self._env.get(normalized_key)
            if env_value is not None:
                return env_value
            return default
        
        # Non-secrets: SQLite only
        user_value = self._user_store.get(key)
        if user_value is not None and user_value != "":
            # Handle case where boolean values might be stored as strings
            # (e.g., from old configs or if parsing failed)
            if isinstance(user_value, str):
                value_lower = user_value.strip().lower()
                # Check if it looks like a boolean string
                if value_lower in ('true', 'false', '1', '0', 'yes', 'no', 'on', 'off'):
                    if value_lower in ('true', '1', 'yes', 'on'):
                        return True
                    elif value_lower in ('false', '0', 'no', 'off'):
                        return False
            return user_value
        normalized_key = key.upper()
        if normalized_key != key:
            alt_user_value = self._user_store.get(normalized_key)
            if alt_user_value is not None and alt_user_value != "":
                # Handle string boolean conversion for alternate key too
                if isinstance(alt_user_value, str):
                    value_lower = alt_user_value.strip().lower()
                    if value_lower in ('true', 'false', '1', '0', 'yes', 'no', 'on', 'off'):
                        if value_lower in ('true', '1', 'yes', 'on'):
                            return True
                        elif value_lower in ('false', '0', 'no', 'off'):
                            return False
                return alt_user_value
        
        return default

    def to_dict(self) -> Dict[str, Any]:
        """Return a snapshot of current configuration values suitable for display."""
        snapshot: Dict[str, Any] = {}
        for key in self._default_snapshot:
            if self._is_secret(key):
                continue
            snapshot[key] = self.get(key)
        return snapshot

    def set(self, key: str, value: Any) -> None:
        if self._is_secret(key):
            if value is None:
                self._env.pop(key.upper(), None)
            else:
                self._env[key.upper()] = str(value)
            return

        self._user_store.set(key, value)

    # Path-related properties delegated to SessionPathManager
    @property
    def OUTPUT_DATA_DIR(self):
        # Currently using direct access to config since it's a bootstrap dependency
        raw = self.get(CONFIG_OUTPUT_DATA_DIR)
        if not raw:
            return raw
        if os.path.isabs(raw):
            return raw
        return os.path.abspath(os.path.join(self._project_root(), raw))

    @property
    def SESSION_DIR(self):
        """Returns the absolute path to the session directory."""
        session_path = self._path_manager.get_session_path()
        if session_path is None:
            raise RuntimeError("Cannot get SESSION_DIR: device info not available. Set device info first using set_device_info().")
        return str(session_path)

    @property
    def ENABLE_IMAGE_CONTEXT(self):
        return self.get("enable_image_context")

    @property
    def XML_SNIPPET_MAX_LEN(self):
        return self.get("xml_snippet_max_len")

    # No property for DEFAULT_MODEL_TYPE - it conflicts with the module constant

    @property
    def LOG_LEVEL(self):
        return self.get("log_level")

    @property
    def LOG_DIR(self):
        """Returns the absolute path to the log directory."""
        return str(self._path_manager.get_log_dir())

    @property
    def LOG_FILE_NAME(self):
        return self.get("LOG_FILE_NAME")

    @property
    def DB_NAME(self):
        """Returns the absolute path to the database file."""
        return str(self._path_manager.get_db_path())

    @property
    def SCREENSHOTS_DIR(self):
        """Returns the absolute path to the screenshots directory."""
        return str(self._path_manager.get_screenshots_dir())

    @property
    def ANNOTATED_SCREENSHOTS_DIR(self):
        """Returns the absolute path to the annotated screenshots directory."""
        return str(self._path_manager.get_annotated_screenshots_dir())

    @property
    def TRAFFIC_CAPTURE_OUTPUT_DIR(self):
        """Returns the absolute path to the traffic capture output directory."""
        return str(self._path_manager.get_traffic_capture_dir())

    @property
    def CRAWLER_PID_PATH(self):
        """Returns the absolute path to the crawler PID file."""
        # This is a special case that we handle directly since it's not session-based
        template = self.get("CRAWLER_PID_PATH")
        if template and f"{{{CONFIG_OUTPUT_DATA_DIR}}}" in template:
            output_dir = self.OUTPUT_DATA_DIR
            if not output_dir:
                # If OUTPUT_DATA_DIR is not set, return None instead of using fallback
                return None
            template = template.replace(f"{{{CONFIG_OUTPUT_DATA_DIR}}}", output_dir)
        return str(Path(template).resolve()) if template else None

    @property
    def AI_PROVIDER(self):
        return self.get("AI_PROVIDER")

    @property
    def USER_CONFIG_FILE_PATH(self):
        """Path to the user config file (SQLite-backed config)."""
        return self._user_store.db_path

    @property
    def FOCUS_AREAS(self):
        # Return focus areas from user store if present, else from defaults
        focus_areas = self._user_store.get_focus_areas_full()
        if focus_areas:
            return [fa["name"] for fa in focus_areas if fa.get("enabled", True)]

        stored_list = self.get("FOCUS_AREAS")
        if isinstance(stored_list, list):
            return stored_list

        return []
    
    @property
    def CRAWLER_AVAILABLE_ACTIONS(self):
        """Return crawler actions as a dict from user store, or defaults."""
        # Try to get from user store first
        actions = self._user_store.get_crawler_actions_full()
        if actions:
            return {action["name"]: action["description"] for action in actions if action.get("enabled", True)}
        
        # Fall back to module default
        return globals().get("CRAWLER_AVAILABLE_ACTIONS", {})
    
    @property
    def CRAWLER_ACTION_DECISION_PROMPT(self):
        """Return action decision prompt from SQLite (single source of truth), or None.
        
        SQLite is the only source of truth. Defaults are initialized on first launch.
        No fallback to prompts.py after initialization.
        """
        prompt = self._user_store.get_crawler_prompt_by_name("ACTION_DECISION_PROMPT")
        return prompt["template"] if prompt else None

    @property
    def USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY(self):
        return self.get("USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY")

    @property
    def GEMINI_API_KEY(self):
        return self.get("GEMINI_API_KEY")

    @property
    def OPENROUTER_API_KEY(self):
        return self.get("OPENROUTER_API_KEY")

    @property
    def OLLAMA_BASE_URL(self):
        return self.get("OLLAMA_BASE_URL")

    @property
    def DEFAULT_MODEL_TYPE(self):
        return self.get("DEFAULT_MODEL_TYPE")

    @property
    def CONFIG_APPIUM_SERVER_URL(self):
        from config.urls import ServiceURLs
        return self.get("CONFIG_APPIUM_SERVER_URL", ServiceURLs.APPIUM)

    @property
    def CONFIG_MOBSF_API_URL(self):
        from config.urls import ServiceURLs
        return self.get("CONFIG_MOBSF_API_URL", ServiceURLs.MOBSF)

    @property
    def CONFIG_OLLAMA_BASE_URL(self):
        from config.urls import ServiceURLs
        return self.get("CONFIG_OLLAMA_BASE_URL", ServiceURLs.OLLAMA)

    def update_setting_and_save(self, key: str, value: Any, callback: Optional[Callable] = None) -> None:
        """Persist the provided value and optionally invoke a callback."""
        try:
            # Use existing set() which handles persistence and secrets
            self.set(key, value)
            if callback:
                try:
                    callback()
                except Exception:
                    logging.exception("Callback in update_setting_and_save failed.")
        except Exception:
            logging.exception("Failed to update setting and save.")

    def reset_settings(self) -> None:
        """Reset persisted configuration to module defaults."""
        logging.info("Resetting configuration to defaults")
        try:
            self._user_store.reset_preferences(self._default_snapshot)
            # Also reset ALLOWED_EXTERNAL_PACKAGES (it's a list, not in _default_snapshot)
            module_globals = globals()
            if 'ALLOWED_EXTERNAL_PACKAGES' in module_globals:
                allowed_packages = module_globals['ALLOWED_EXTERNAL_PACKAGES']
                if isinstance(allowed_packages, list):
                    self._user_store.set('ALLOWED_EXTERNAL_PACKAGES', allowed_packages)
        except Exception:
            logging.exception("Failed to reset user preferences to defaults.")
            raise

    def _get_user_savable_config(self) -> Dict[str, Any]:
        """
        Return a dictionary of configuration values intended for user-facing display.
        
        Includes all types (int, str, bool, float, dict, list) that are stored in SQLite.
        App-specific keys (APP_PACKAGE, APP_ACTIVITY) are included but will be None/empty
        on first launch since they're not initialized from module defaults.
        
        Excludes:
        - Path templates with placeholders (e.g., "{session_dir}")
        - Documentation constants (ACTION_DESC_*)
        - Key constants (CONFIG_OUTPUT_DATA_DIR, etc.)
        """
        module = globals()
        result: Dict[str, Any] = {}
        
        # Keys to exclude (documentation or key constants)
        excluded_keys = {
            'CONFIG_OUTPUT_DATA_DIR',  # Key constant, not a config value
        }
        
        # App-specific keys that should be empty on first launch (not initialized from module defaults)
        app_specific_keys = {
            'APP_PACKAGE',  # App-specific, should be set per project
            'APP_ACTIVITY',  # App-specific, should be set per project
        }
        
        for k, v in module.items():
            if not k.isupper():
                continue
            
            # Skip excluded keys
            if k in excluded_keys:
                continue
            
            # Skip ACTION_DESC_* constants (documentation strings)
            if k.startswith('ACTION_DESC_'):
                continue
            
            # Exclude path templates with placeholders (they're resolved dynamically)
            # But allow complex types (dict, list) even if they contain strings with placeholders
            if isinstance(v, str) and '{' in v:
                continue
            
            # Include all types: int, str, bool, float, dict, list
            # Get from SQLite if available, otherwise use module default
            # UserConfigStore handles JSON deserialization for complex types automatically
            try:
                stored = self._user_store.get(k)
                if stored is not None and stored != "":
                    result[k] = stored
                else:
                    # For app-specific keys, use None/empty on first launch instead of module default
                    if k in app_specific_keys:
                        result[k] = None
                    else:
                        result[k] = v
            except Exception:
                # For app-specific keys, use None/empty on first launch instead of module default
                if k in app_specific_keys:
                    result[k] = None
                else:
                    result[k] = v
        
        return result

    def _collect_default_settings(self) -> Dict[str, Any]:
        """Collect default settings from module constants.
        
        Only includes simple types (int, str, bool, float) for SQLite storage.
        Complex types (dict, list) and None are excluded.
        
        Returns:
            Dictionary of simple type defaults for initial SQLite population
        """
        module = globals()
        defaults: Dict[str, Any] = {}
        for key, value in module.items():
            if not key.isupper():
                continue
            # Only include simple types for SQLite storage
            # Exclude dict, list, and None
            if isinstance(value, (int, str, bool, float)):
                defaults[key] = copy.deepcopy(value)
        return defaults
    
    def set_and_save_from_pairs(self, kv_pairs: List[str], telemetry_service=None) -> bool:
        """
        Set and save configuration values from a list of KEY=VALUE pairs.
        
        Args:
            kv_pairs: List of key=value pairs
            telemetry_service: Optional telemetry service for user feedback
            
        Returns:
            True if all pairs were processed successfully, False otherwise
        """
        success_count = 0
        total_count = len(kv_pairs)
        
        for kv_pair in kv_pairs:
            if "=" not in kv_pair:
                if telemetry_service:
                    telemetry_service.print_error(f"Invalid format: {kv_pair}. Use KEY=VALUE format.")
                continue
            
            key, value = kv_pair.split("=", 1)
            if self._set_config_value(key.strip(), value.strip()):
                success_count += 1
                if telemetry_service:
                    telemetry_service.print_success(f"Set {key} = {value}")
            else:
                if telemetry_service:
                    telemetry_service.print_error(f"Failed to set {key}")
        
        # Save all changes
        if telemetry_service and success_count > 0:
            telemetry_service.print_success("Configuration updated successfully")
        
        return success_count == total_count
    
    def _set_config_value(self, key: str, value_str: str) -> bool:
        """
        Set a configuration value from a string.
        
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

            self.update_setting_and_save(key, parsed_value)
            return True

        except Exception as e:
            logging.error(f"Failed to set config for {key}: {e}", exc_info=True)
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
        import json
        from typing import get_type_hints
        
        # First, check if value looks like a boolean string (even without type hints)
        # This handles cases where boolean configs are set via CLI
        value_lower = value_str.strip().lower()
        if value_lower in ('true', 'false', '1', '0', 'yes', 'no', 'on', 'off'):
            # Try to parse as boolean first
            if value_lower in ('true', '1', 'yes', 'on'):
                return True
            elif value_lower in ('false', '0', 'no', 'off'):
                return False
        
        # Default to string
        parsed_value = value_str
        
        try:
            # Get type hints for the config
            type_hints = get_type_hints(type(self))
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
    
    def get_deserialized_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value and deserialize it from JSON if it's a string.
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Deserialized configuration value or default
        """
        import json
        
        value = self.get(key, default)
        
        # Handle case where value might be stored as JSON string
        if value and isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        
        return value
    
# ============================================================================
# DEFAULT CONFIGURATION VALUES
# ============================================================================
# These defaults are used ONLY for initial SQLite population on first launch.
# 
# Simplified two-layer configuration system:
#   - Secrets (API keys): Environment variables only (never stored in SQLite)
#   - Everything else: SQLite only (int, str, bool, float values)
#
# On first launch, simple type defaults (int, str, bool, float) are automatically
# populated into SQLite. Complex types (dict, list) and None are excluded.
#
# IMPORTANT: These values in this file are NOT the active configuration!
# To see actual active values at runtime, use: config.get("KEY_NAME")
# 
# Module defaults are NOT used as runtime fallback - only for initial population.
# ============================================================================

APP_PACKAGE = None  # App-specific, must be set by user (not initialized on first launch)
APP_ACTIVITY = None  # App-specific, must be set by user (not initialized on first launch)
# Package constants are now in config.package_constants
from config.package_constants import PackageConstants
ALLOWED_EXTERNAL_PACKAGES = PackageConstants.get_allowed_external_packages([
    "org.mozilla.firefox",
    "com.sec.android.app.sbrowser",
    "com.microsoft.emmx",
    "com.brave.browser",
    "com.duckduckgo.mobile.android",
])

OUTPUT_DATA_DIR = "output_data"  # This is a template name, Config class makes it a path
SESSION_DIR = f"{{{CONFIG_OUTPUT_DATA_DIR}}}/sessions/{{device_id}}_{{app_package}}_{{timestamp}}"
APP_INFO_OUTPUT_DIR = f"{{{CONFIG_OUTPUT_DATA_DIR}}}/app_info"
SCREENSHOTS_DIR = "{session_dir}/screenshots"
ANNOTATED_SCREENSHOTS_DIR = "{session_dir}/annotated_screenshots"
TRAFFIC_CAPTURE_OUTPUT_DIR = "{session_dir}/traffic_captures"
LOG_DIR = "{session_dir}/logs"
CRAWLER_PID_PATH = f"{{{CONFIG_OUTPUT_DATA_DIR}}}/core/crawler.pid"

LOG_LEVEL = "INFO"
# Path constants are now in config.path_constants
from config.path_constants import PathConstants
LOG_FILE_NAME = PathConstants.LOG_FILE_NAME  # Actual file name, dir is separate

DB_NAME = f"{{session_dir}}/{PathConstants.DATABASE_DIR}/{{package}}{PathConstants.DB_FILE_SUFFIX}"
MOBSF_SCAN_DIR = f"{{session_dir}}/{PathConstants.MOBSF_SCAN_DIR}"
EXTRACTED_APK_DIR = f"{{session_dir}}/{PathConstants.EXTRACTED_APK_DIR}"
PDF_REPORT_DIR = f"{{session_dir}}/{PathConstants.REPORTS_DIR}"
# Database and time constants are now in config.numeric_constants
from config.numeric_constants import (
    DB_CONNECT_TIMEOUT,
    DB_BUSY_TIMEOUT,
    WAIT_AFTER_ACTION_DEFAULT as WAIT_AFTER_ACTION,
    STABILITY_WAIT_DEFAULT as STABILITY_WAIT,
    APP_LAUNCH_WAIT_TIME_DEFAULT as APP_LAUNCH_WAIT_TIME,
    ACTIVITY_LAUNCH_WAIT_TIME_DEFAULT as ACTIVITY_LAUNCH_WAIT_TIME,
)
# APPIUM_SERVER_URL is now in config.urls.ServiceURLs.APPIUM

TARGET_DEVICE_UDID = None
TARGET_DEVICE_NAME = None
USE_COORDINATE_FALLBACK = True

AI_PROVIDER = "gemini"  # Available providers: 'gemini', 'openrouter', 'ollama'
DEFAULT_MODEL_TYPE = None  # No default model - user must select a model before crawling
ENABLE_IMAGE_CONTEXT = False
# XML and cache constants are now in config.numeric_constants
from config.numeric_constants import (
    XML_SNIPPET_MAX_LEN_DEFAULT as XML_SNIPPET_MAX_LEN,
    XML_SUMMARY_MAX_LINES_DEFAULT as XML_SUMMARY_MAX_LINES,
    CACHE_MAX_SCREENS,
)
USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY = True
# AI Safety Settings for Gemini - Less restrictive configuration
# Set to BLOCK_NONE for all categories to allow all content through
# Categories: HARM_CATEGORY_HARASSMENT, HARM_CATEGORY_HATE_SPEECH, 
# HARM_CATEGORY_SEXUALLY_EXPLICIT, HARM_CATEGORY_DANGEROUS_CONTENT
# Threshold values: BLOCK_NONE=1, BLOCK_ONLY_HIGH=2, BLOCK_MEDIUM_AND_ABOVE=3, BLOCK_LOW_AND_ABOVE=4
AI_SAFETY_SETTINGS = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    }
]
# Prompt and XML compacting/caching for latency reduction
PROMPT_COMPACT_MODE = True
XML_INTERACTIVE_ONLY = True

# Crawler available actions (dict format: {"action_name": "description", ...})
CRAWLER_AVAILABLE_ACTIONS = {
    "click": "Perform a click action on the target element.",
    "input": "Input text into the target element.",
    "long_press": "Perform a long press action on the target element.",
    "scroll_down": "Scroll the view downward to reveal more content below.",
    "scroll_up": "Scroll the view upward to reveal more content above.",
    "swipe_left": "Swipe left to navigate or reveal content on the right.",
    "swipe_right": "Swipe right to navigate or reveal content on the left.",
    "back": "Press the back button to return to the previous screen.",
    "double_tap": "Perform a double tap gesture on the target element (useful for zooming, image galleries).",
    "clear_text": "Clear all text from the target input element.",
    "replace_text": "Replace existing text in the target input element with new text.",
    "flick": "Perform a fast flick gesture in the specified direction (faster than scroll for quick navigation).",
    "reset_app": "Reset the app to its initial state (clears app data and restarts)."
}

CRAWL_MODE = "steps"
MAX_CRAWL_STEPS = 10
MAX_CRAWL_DURATION_SECONDS = 600
VISUAL_SIMILARITY_THRESHOLD = 5

LONG_PRESS_MIN_DURATION_MS = 600

MAX_CONSECUTIVE_AI_FAILURES = 3
MAX_CONSECUTIVE_MAP_FAILURES = 3
MAX_CONSECUTIVE_EXEC_FAILURES = 3
MAX_CONSECUTIVE_CONTEXT_FAILURES = 3
LOOP_DETECTION_VISIT_THRESHOLD = 1

ENABLE_TRAFFIC_CAPTURE = True
# PCAPDROID_PACKAGE is now in config.package_constants.PackageConstants.PCAPDROID_PACKAGE
from config.package_constants import PackageConstants
PCAPDROID_PACKAGE = PackageConstants.PCAPDROID_PACKAGE
# PCAPDROID_ACTIVITY is derived by Config class
DEVICE_PCAP_DIR = "/sdcard/Download/PCAPdroid"
CLEANUP_DEVICE_PCAP_FILE = True

MAX_CONSECUTIVE_NO_OP_FAILURES = 2
# Enforce choosing different actions sooner to avoid loops
MAX_SAME_ACTION_REPEAT = 2
USE_ADB_INPUT_FALLBACK = True

# Safety tap configuration and toast handling defaults
SAFE_TAP_MARGIN_RATIO = 0.03  # 3% from each screen edge considered unsafe
SAFE_TAP_EDGE_HANDLING = "snap"  # Options: 'reject' or 'snap' to safe area
TOAST_DISMISS_WAIT_MS = 1200  # Wait time for transient toast overlays to dismiss

# Element selection heuristics and behavior
DISABLE_EXPENSIVE_XPATH = False  # Keep robust XPath strategies enabled by default
ELEMENT_STRATEGY_MAX_ATTEMPTS = (
    6  # Try multiple strategies before giving up on a target
)
AUTO_HIDE_KEYBOARD_BEFORE_NON_INPUT = (
    True  # Auto-hide keyboard to prevent overlay-related no-ops
)

# Appium performance settings
APPIUM_IMPLICIT_WAIT = 5000  # Implicit wait timeout in milliseconds (reduced from 10000 for faster element finding)
APPIUM_MAX_RETRIES = 3  # Maximum retry attempts for Appium operations
APPIUM_RETRY_DELAY = 1.0  # Delay between retries in seconds
APPIUM_WAIT_FOR_IDLE_TIMEOUT = 0  # Disable idle waiting for faster element finding
APPIUM_SNAPSHOT_MAX_DEPTH = 25  # Limit XML tree depth to reduce scanning overhead
APPIUM_IGNORE_UNIMPORTANT_VIEWS = True  # Filter out non-interactive elements
APPIUM_DISABLE_WINDOW_ANIMATION = True  # Skip animation waits

# MobSF Integration settings 
MOBSF_API_KEY = None  # Will be loaded from environment variable
ENABLE_MOBSF_ANALYSIS = False 

# Video Recording Settings
ENABLE_VIDEO_RECORDING = False
VIDEO_RECORDING_DIR = f"{{session_dir}}/{PathConstants.VIDEO_RECORDING_DIR}"

# --- Image Preprocessing (Global overrides) ---
# These knobs control how screenshots are preprocessed before being sent to the AI.
# They override provider defaults where applicable.
IMAGE_MAX_WIDTH = 896  # Max width for downsampling; no upscaling
IMAGE_FORMAT = "JPEG"  # Preferred encoding format (JPEG/WebP/PNG)
IMAGE_QUALITY = 70  # Compression quality (0-100, typical 60-80)
IMAGE_CROP_BARS = True  # If true, crop status bar and nav bar regions
IMAGE_CROP_TOP_PERCENT = 0.06  # Fraction of image height to crop from top
IMAGE_CROP_BOTTOM_PERCENT = 0.06  # Fraction of image height to crop from bottom

# --- AI Provider Capabilities Configuration ---
# This configuration makes it easy to add new AI providers with different capabilities
AI_PROVIDER_CAPABILITIES = {
    "gemini": {
        "xml_max_len": 500000,  # Retain large XML size for high capacity
        "image_supported": True,
        "image_max_width": 640,  # Optimal width for quality/compression balance
        "image_quality": 75,  # Good JPEG quality for clarity and size tradeoff
        "image_format": "JPEG",
        "payload_max_size_kb": 1000,  # Max payload around 1MB for cloud provider
        "auto_disable_image_context": False,  # Keep enabled for vision tasks
        "description": "Google Gemini - High capacity, supports large payloads and images",
        "online": True,
    },
    "ollama": {
        "xml_max_len": 200000,  # Slightly lowered to reasonable local model limit
        "image_supported": True,
        "image_max_width": 640,
        "image_quality": 75,
        "image_format": "JPEG",
        "payload_max_size_kb": None,  # No strict limits for local provider
        "auto_disable_image_context": False,
        "description": "Ollama - Local LLM provider with vision support for compatible models",
        "online": False,
    },
    "openrouter": {
        "xml_max_len": 200000,  # Balanced default accepted industry standard
        "image_supported": True,
        "image_max_width": 640,
        "image_quality": 75,
        "image_format": "JPEG",
        "payload_max_size_kb": 500,  # Conservative to improve performance under network constraints
        "auto_disable_image_context": False,
        "description": "OpenRouter - Unified gateway to multiple model providers",
        "online": True,
    },
}

OPENROUTER_MODELS = {}
OPENROUTER_REFRESH_BTN = False
OPENROUTER_SHOW_FREE_ONLY = False

