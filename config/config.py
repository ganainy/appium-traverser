# Key for output data dir config
OUTPUT_DATA_DIR_KEY = "OUTPUT_DATA_DIR"
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

# --- Refactored Centralized Configuration Class ---
class Config:
    """
    Central configuration class with three-layer precedence:
    user storage (SQLite) > environment > module defaults
    """
    def __init__(self, user_store: Optional[UserConfigStore] = None):
        self._defaults = type('Defaults', (), {})()  # Empty defaults object as placeholder
        self._user_store = user_store or UserConfigStore()
        self._volatile_overrides: Dict[str, Any] = {}
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
        self._default_snapshot = self._collect_default_settings()
        try:
            self._user_store.initialize_defaults(self._default_snapshot)
        except Exception:
            logging.exception("Failed to initialize default configuration values in user store.")

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
        placeholder = f"{{{OUTPUT_DATA_DIR_KEY}}}"
        if placeholder in template:
            return template.replace(placeholder, self.OUTPUT_DATA_DIR or "output_data")
        return template

    def _is_secret(self, key: str) -> bool:
        upper_key = key.upper()
        if upper_key in self._secrets:
            return True
        return key == upper_key and upper_key.endswith("_KEY")

    def get(self, key: str, default: Any = None) -> Any:
        # Layer 1a: runtime-only overrides set with persist=False
        if key in self._volatile_overrides:
            return self._volatile_overrides[key]

        # Layer 1b: user storage (SQLite)
        user_value = self._user_store.get(key)
        if user_value is not None and user_value != "":
            return user_value
        normalized_key = key.upper()
        if normalized_key != key:
            if normalized_key in self._volatile_overrides:
                return self._volatile_overrides[normalized_key]
            alt_user_value = self._user_store.get(normalized_key)
            if alt_user_value is not None and alt_user_value != "":
                return alt_user_value

        # Layer 2: environment variables
        env_value = self._env.get(key)
        if env_value is None and normalized_key != key:
            env_value = self._env.get(normalized_key)
        if env_value is not None:
            return env_value

        # Layer 3: module defaults
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

    def set(self, key: str, value: Any, persist: bool = True) -> None:
        if not persist:
            if value is None:
                self._volatile_overrides.pop(key, None)
                self._volatile_overrides.pop(key.upper(), None)
            else:
                self._volatile_overrides[key] = value
            return

        if self._is_secret(key):
            if value is None:
                self._env.pop(key.upper(), None)
            else:
                self._env[key.upper()] = str(value)
            self._volatile_overrides.pop(key, None)
            self._volatile_overrides.pop(key.upper(), None)
            return

        self._volatile_overrides.pop(key, None)
        self._volatile_overrides.pop(key.upper(), None)
        self._user_store.set(key, value)

    # Path-related properties delegated to SessionPathManager
    @property
    def OUTPUT_DATA_DIR(self):
        # Currently using direct access to config since it's a bootstrap dependency
        raw = self.get(OUTPUT_DATA_DIR_KEY)
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
        if template and f"{{{OUTPUT_DATA_DIR_KEY}}}" in template:
            template = template.replace(f"{{{OUTPUT_DATA_DIR_KEY}}}", self.OUTPUT_DATA_DIR or "output_data")
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
        focus_areas = self._user_store.get_focus_areas()
        if focus_areas:
            return [fa["area"] for fa in focus_areas if fa.get("enabled", True)]

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
    def GEMINI_MODELS(self):
        return self.get("GEMINI_MODELS")

    @property
    def OLLAMA_MODELS(self):
        return self.get("OLLAMA_MODELS")

    @property
    def CONFIG_APPIUM_SERVER_URL(self):
        return self.get("CONFIG_APPIUM_SERVER_URL", "http://127.0.0.1:4723")

    @property
    def CONFIG_MCP_SERVER_URL(self):
        return self.get("CONFIG_MCP_SERVER_URL", "http://localhost:3000/mcp")

    @property
    def CONFIG_MOBSF_API_URL(self):
        return self.get("CONFIG_MOBSF_API_URL", "http://localhost:8000/api/v1")

    @property
    def CONFIG_OLLAMA_BASE_URL(self):
        return self.get("CONFIG_OLLAMA_BASE_URL", "http://localhost:11434")

    def update_setting_and_save(self, key: str, value: Any, callback: Optional[Callable] = None) -> None:
        """Persist the provided value and optionally invoke a callback."""
        try:
            # Use existing set() which handles persistence and secrets
            self.set(key, value, persist=True)
            if callback:
                try:
                    callback()
                except Exception:
                    logging.exception("Callback in update_setting_and_save failed.")
        except Exception:
            logging.exception("Failed to update setting and save.")

    def reset_settings(self) -> None:
        """Reset persisted configuration to module defaults and clear overrides."""
        logging.info("Resetting configuration to defaults")
        self._volatile_overrides.clear()
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
    
    def switch_ai_provider(self, provider: str, model: Optional[str] = None) -> 'CommandResult':
        """
        Switch the AI provider and optionally set the model.
        
        Args:
            provider: AI provider to use (gemini, openrouter, ollama)
            model: Optional model name/alias to use
            
        Returns:
            CommandResult indicating success or failure
        """
        import logging
        from cli.constants.keys import VALID_AI_PROVIDERS
        from cli.commands.base import CommandResult

        # Validate provider
        if provider not in VALID_AI_PROVIDERS:
            return CommandResult(
                success=False,
                message=f"[ERROR] Invalid provider: {provider}",
                exit_code=1
            )

        try:
            # Update provider
            self.set("AI_PROVIDER", provider)

            # Update model if provided
            if model:
                self.set("DEFAULT_MODEL_TYPE", model)

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

# --- Default values (loaded if not in user_config.json or .env) ---
# --- These are loaded by _load_from_defaults_module by exec-ing this file ---

APP_PACKAGE = "de.deltacity.android.blutspende"
APP_ACTIVITY = "de.deltacity.android.blutspende.activities.SplashScreenActivity"
ALLOWED_EXTERNAL_PACKAGES = [
    "com.google.android.gms",
    "com.android.chrome",
    "com.google.android.permissioncontroller",
    "org.mozilla.firefox",
    "com.sec.android.app.sbrowser",
    "com.microsoft.emmx",
    "com.brave.browser",
    "com.duckduckgo.mobile.android",
]

OUTPUT_DATA_DIR = "output_data"  # This is a template name, Config class makes it a path
SESSION_DIR = f"{{{OUTPUT_DATA_DIR_KEY}}}/{{device_id}}_{{app_package}}_{{timestamp}}"
APP_INFO_OUTPUT_DIR = f"{{{OUTPUT_DATA_DIR_KEY}}}/app_info"
SCREENSHOTS_DIR = "{session_dir}/screenshots"
ANNOTATED_SCREENSHOTS_DIR = "{session_dir}/annotated_screenshots"
TRAFFIC_CAPTURE_OUTPUT_DIR = "{session_dir}/traffic_captures"
LOG_DIR = "{session_dir}/logs"
CRAWLER_PID_PATH = f"{{{OUTPUT_DATA_DIR_KEY}}}/core/crawler.pid"

LOG_LEVEL = "INFO"
LOG_FILE_NAME = "main_traverser_final.log"  # Actual file name, dir is separate

DB_NAME = "{session_dir}/database/{package}_crawl_data.db"
MOBSF_SCAN_DIR = "{session_dir}/mobsf_scan_results"
EXTRACTED_APK_DIR = "{session_dir}/extracted_apk"
PDF_REPORT_DIR = "{session_dir}/reports"
DB_CONNECT_TIMEOUT = 10
DB_BUSY_TIMEOUT = 5000

WAIT_AFTER_ACTION = 2.0
STABILITY_WAIT = 1.0
APP_LAUNCH_WAIT_TIME = 5
APPIUM_SERVER_URL = "http://127.0.0.1:4723"

MCP_SERVER_URL = "http://localhost:3000/mcp"
MCP_CONNECTION_TIMEOUT = 5.0
MCP_REQUEST_TIMEOUT = 30.0
MCP_MAX_RETRIES = 3
TARGET_DEVICE_UDID = None
USE_COORDINATE_FALLBACK = True

AI_PROVIDER = "gemini"  # Available providers: 'gemini', 'openrouter', 'ollama'
DEFAULT_MODEL_TYPE = "gemini-2.5-flash-image"
ENABLE_IMAGE_CONTEXT = False
XML_SNIPPET_MAX_LEN = 15000
USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY = True
AI_SAFETY_SETTINGS = {}
# Prompt and XML compacting/caching for latency reduction
PROMPT_COMPACT_MODE = True
XML_SUMMARY_MAX_LINES = 120
XML_INTERACTIVE_ONLY = True
CACHE_MAX_SCREENS = 100
GEMINI_MODELS = {
    "flash-latest": {
        "name": "gemini-2.5-flash-preview-05-20",
        "description": "Latest Flash model (2.5): Optimized for speed, cost, and multimodal tasks.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        },
        "online": True,
    },
    "flash-latest-fast": {
        "name": "gemini-2.5-flash-image",
        "description": "Latest Flash model (2.5) with settings optimized for faster responses.",
        "generation_config": {
            "temperature": 0.3,
            "top_p": 0.8,
            "top_k": 20,
            "max_output_tokens": 2048,
        },
        "online": True,
        "vision_supported": True,
    },
}

OLLAMA_MODELS = {
    # Text-only models
    "llama3.2": {
        "name": "llama3.2",
        "description": "Llama 3.2 model running locally via Ollama (text-only).",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": False,
    },
    "llama3.2-fast": {
        "name": "llama3.2",
        "description": "Llama 3.2 model with optimized settings for faster responses (text-only).",
        "generation_config": {
            "temperature": 0.3,
            "top_p": 0.8,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": False,
    },
    "mistral": {
        "name": "mistral",
        "description": "Mistral 7B model running locally via Ollama (text-only).",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": False,
    },
    "mistral-small": {
        "name": "mistral-small",
        "description": "Mistral Small model running locally via Ollama (text-only).",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": False,
    },
    "qwen2.5": {
        "name": "qwen2.5",
        "description": "Qwen 2.5 model running locally via Ollama (text-only).",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": False,
    },
    "granite3.2": {
        "name": "granite3.2",
        "description": "Granite 3.2 model running locally via Ollama (text-only).",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": False,
    },
    # Vision-capable models
    "llama3.2-vision": {
        "name": "llama3.2-vision",
        "description": "Llama 3.2 Vision model with multimodal capabilities.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "llama3.2-vision-fast": {
        "name": "llama3.2-vision",
        "description": "Llama 3.2 Vision model with optimized settings for faster responses.",
        "generation_config": {
            "temperature": 0.3,
            "top_p": 0.8,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "llava": {
        "name": "llava",
        "description": "LLaVA model for vision-language tasks.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "llava-llama3": {
        "name": "llava-llama3",
        "description": "LLaVA model with Llama 3 backbone for vision-language tasks.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "llava-phi3": {
        "name": "llava-phi3",
        "description": "LLaVA model with Phi-3 backbone for vision-language tasks.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "bakllava": {
        "name": "bakllava",
        "description": "BakLLaVA model for vision-language tasks.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "minicpm-v": {
        "name": "minicpm-v",
        "description": "MiniCPM-V model for vision-language tasks.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "moondream": {
        "name": "moondream",
        "description": "Moondream model for vision-language tasks.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "gemma3": {
        "name": "gemma3",
        "description": "Gemma 3 model with multimodal capabilities.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "llama4": {
        "name": "llama4",
        "description": "Llama 4 model with multimodal capabilities.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "mistral-small3.1": {
        "name": "mistral-small3.1",
        "description": "Mistral Small 3.1 model with multimodal capabilities.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "mistral-small3.2": {
        "name": "mistral-small3.2",
        "description": "Mistral Small 3.2 model with multimodal capabilities.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
}

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
PCAPDROID_PACKAGE = "com.emanuelef.remote_capture"
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
MOBSF_API_URL = "http://localhost:8000/api/v1"
MOBSF_API_KEY = None  # Will be loaded from environment variable
ENABLE_MOBSF_ANALYSIS = True

# Video Recording Settings
ENABLE_VIDEO_RECORDING = False
VIDEO_RECORDING_DIR = "{session_dir}/video"

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
        "xml_max_len": 500000,  # Maximum XML characters
        "image_supported": True,  # Whether images are supported
        "image_max_width": 640,  # Reduced from 720 for better compression
        "image_quality": 75,  # Reduced from 85 for smaller size while maintaining clarity
        "image_format": "JPEG",  # Image format for compression
        "payload_max_size_kb": 1000,  # Maximum payload size in KB
        "auto_disable_image_context": False,  # Whether to auto-disable image context
        "description": "Google Gemini - High capacity, supports large payloads and images",
        "online": True,  # Indicates this is an online/cloud provider
    },
    "ollama": {
        "xml_max_len": 100000,  # Higher limit for local models
        "image_supported": True,  # Ollama supports images with vision-capable models
        "image_max_width": 640,  # Standard image size for vision models
        "image_quality": 75,  # Good quality for vision processing
        "image_format": "JPEG",  # JPEG format for efficient transmission
        "payload_max_size_kb": None,  # No payload limits for local models
        "auto_disable_image_context": False,  # Don't auto-disable since vision models exist
        "description": "Ollama - Local LLM provider with vision support for compatible models",
        "online": False,  # Local provider
    },
    "openrouter": {
        "xml_max_len": 200000,  # Balanced default; depends on routed model
        "image_supported": True,  # Many OpenRouter models support images
        "image_max_width": 640,
        "image_quality": 75,
        "image_format": "JPEG",
        "payload_max_size_kb": 500,  # Conservative; varies by downstream model
        "auto_disable_image_context": False,
        "description": "OpenRouter - Unified gateway to multiple model providers",
        "online": True,
    },
}
OPENROUTER_MODELS = {}
OPENROUTER_REFRESH_BTN = False
OPENROUTER_SHOW_FREE_ONLY = False