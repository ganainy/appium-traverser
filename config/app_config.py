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
    Central configuration class with three-layer precedence:
    user storage (SQLite) > environment > module defaults
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
            return template.replace(placeholder, self.OUTPUT_DATA_DIR or "output_data")
        return template

    def _is_secret(self, key: str) -> bool:
        upper_key = key.upper()
        if upper_key in self._secrets:
            return True
        return key == upper_key and upper_key.endswith("_KEY")

    def get(self, key: str, default: Any = None) -> Any:
        # Layer 1: user storage (SQLite)
        user_value = self._user_store.get(key)
        if user_value is not None and user_value != "":
            return user_value
        normalized_key = key.upper()
        if normalized_key != key:
            alt_user_value = self._user_store.get(normalized_key)
            if alt_user_value is not None and alt_user_value != "":
                return alt_user_value

        # Layer 2: environment variables
        env_value = self._env.get(key)
        if env_value is None and normalized_key != key:
            env_value = self._env.get(normalized_key)
        if env_value is not None:
            return env_value

        # Layer 3: module defaults (fallback)
        module = globals()
        if key in module:
            return module[key]
        if normalized_key in module:
            return module[normalized_key]
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
        return str(self._path_manager.get_session_path())

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
    def CONTINUE_EXISTING_RUN(self):
        return self.get("CONTINUE_EXISTING_RUN")

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
            template = template.replace(f"{{{CONFIG_OUTPUT_DATA_DIR}}}", self.OUTPUT_DATA_DIR or "output_data")
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
        except Exception:
            logging.exception("Failed to reset user preferences to defaults.")
            raise

    def _get_user_savable_config(self) -> Dict[str, Any]:
        """
        Return a dictionary of configuration values intended for user-facing display
        and persistence. This gathers module-level uppercase defaults and overlays
        any persisted values from the user store.
        """
        module = globals()
        result: Dict[str, Any] = {}
        for k, v in module.items():
            if k.isupper():
                try:
                    stored = self._user_store.get(k)
                    if stored is not None:
                        result[k] = stored
                    else:
                        result[k] = v
                except Exception:
                    result[k] = v
        return result

    def _collect_default_settings(self) -> Dict[str, Any]:
        module = globals()
        defaults: Dict[str, Any] = {}
        for key, value in module.items():
            if not key.isupper():
                continue
            if isinstance(value, (str, int, float, bool, dict, list)) or value is None:
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
# These are FALLBACK defaults used when no user configuration exists.
# 
# Configuration precedence (highest to lowest):
#   1. User Store (SQLite database) - persistent user settings
#   2. Environment variables
#   3. These module defaults (fallback only)
#
# IMPORTANT: These values in this file are NOT the active configuration!
# To see actual active values at runtime, use: config.get("KEY_NAME")
# 
# User-facing settings are prefixed with DEFAULT_ for clarity.
# ============================================================================

APP_PACKAGE = "de.deltacity.android.blutspende"
APP_ACTIVITY = "de.deltacity.android.blutspende.activities.SplashScreenActivity"
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
DEFAULT_MODEL_TYPE = "google/gemini-flash-2.5:free"  # Free model from OpenRouter
ENABLE_IMAGE_CONTEXT = False
# XML and cache constants are now in config.numeric_constants
from config.numeric_constants import (
    XML_SNIPPET_MAX_LEN_DEFAULT as XML_SNIPPET_MAX_LEN,
    XML_SUMMARY_MAX_LINES_DEFAULT as XML_SUMMARY_MAX_LINES,
    CACHE_MAX_SCREENS,
)
USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY = True
AI_SAFETY_SETTINGS = {}
# Prompt and XML compacting/caching for latency reduction
PROMPT_COMPACT_MODE = True
XML_INTERACTIVE_ONLY = True

CRAWL_MODE = "steps"
MAX_CRAWL_STEPS = 10
MAX_CRAWL_DURATION_SECONDS = 600
CONTINUE_EXISTING_RUN = False
VISUAL_SIMILARITY_THRESHOLD = 5

AVAILABLE_ACTIONS = [
    "click",
    "input",
    "scroll_down",
    "scroll_up",
    "swipe_left",
    "swipe_right",
    "back",
    "long_press",
]
ACTION_DESC_CLICK = "Click the specified element."
ACTION_DESC_INPUT = "Input the provided text into the specified element."
ACTION_DESC_SCROLL_DOWN = "Scroll the screen down to reveal more content."
ACTION_DESC_SCROLL_UP = "Scroll the screen up to reveal previous content."
ACTION_DESC_BACK = "Press the device's back button."
ACTION_DESC_SWIPE_LEFT = "Swipe content from right to left (e.g., for carousels)."
ACTION_DESC_SWIPE_RIGHT = "Swipe content from left to right (e.g., for carousels)."
ACTION_DESC_LONG_PRESS = (
    "Press and hold on the specified element to open contextual options or menus."
)

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
FALLBACK_ACTIONS_SEQUENCE = [
    {"action": "scroll_down", "target_identifier": None, "input_text": None},
    {"action": "scroll_up", "target_identifier": None, "input_text": None},
    # Try content discovery via lateral gestures before backing out
    {"action": "swipe_left", "target_identifier": None, "input_text": None},
    {"action": "swipe_right", "target_identifier": None, "input_text": None},
    # Attempt a generic long_press which can reveal contextual menus
    {"action": "long_press", "target_identifier": None, "input_text": None},
    # Finally, back out of the current screen if gestures did not help
    {"action": "back", "target_identifier": None, "input_text": None},
]
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

# MobSF Integration settings - URL and default for ENABLE flag only
# API key should be set via environment variable MOBSF_API_KEY
# MOBSF_API_URL is now in config.urls.ServiceURLs.MOBSF
MOBSF_API_KEY = None  # Will be loaded from environment variable
ENABLE_MOBSF_ANALYSIS = True

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

