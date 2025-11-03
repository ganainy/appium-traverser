# Key for output data dir config
OUTPUT_DATA_DIR_KEY = "OUTPUT_DATA_DIR"
import os
import logging
from typing import Any, Callable, Dict, Optional
from datetime import datetime
from infrastructure.user_config_store import UserConfigStore

# --- Refactored Centralized Configuration Class ---
class Config:
    """
    Central configuration class with four-layer precedence:
    cache > user storage (SQLite) > environment > Pydantic defaults
    """
    def __init__(self, user_config_json_path: Optional[str] = None):
        self._defaults = type('Defaults', (), {})()  # Empty defaults object as placeholder
        self._user_store = UserConfigStore()
        self._cache: Dict[str, Any] = {}
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

    def _init_paths(self):
        # For backward compatibility, set up path-related attributes from defaults
        self.BASE_DIR = os.path.abspath(os.path.dirname(__file__))
        self.SHUTDOWN_FLAG_PATH = os.path.abspath(os.path.join(self.BASE_DIR, "..", "shutdown.flag"))
        # Cache for resolved session context
        self._session_context: Dict[str, Any] = {}

    def _project_root(self) -> str:
        """Return absolute project root (one level up from config module)."""
        return os.path.abspath(os.path.join(self.BASE_DIR, ".."))

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
        return key.upper() in self._secrets or key.lower().endswith("_key")

    def get(self, key: str, default: Any = None) -> Any:
        # 1. Check runtime cache
        if key in self._cache:
            return self._cache[key]
        # 2. Check user storage (SQLite)
        val = self._user_store.get(key)
        if val is not None and val != "":  # Skip empty strings to allow fallback to defaults
            self._cache[key] = val
            return val
        # 3. Check environment variables
        if key in self._env:
            val = self._env[key]
            self._cache[key] = val
            return val
        # 4. Fallback to hardcoded defaults (module-level constants)
        module = globals()
        if key in module:
            val = module[key]
            self._cache[key] = val
            return val
        return default

    def set(self, key: str, value: Any, persist: bool = True) -> None:
        self._cache[key] = value
        if persist and not self._is_secret(key):
            self._user_store.set(key, value)

    def save_user_config(self):
        # No-op: user config is now persisted in SQLite
        pass

    def load_user_config(self, path: Optional[str] = None):
        # No-op: config is loaded dynamically from SQLite and env
        pass

    # For backward compatibility, expose some common config attributes as properties
    @property
    def OUTPUT_DATA_DIR(self):
        # Ensure OUTPUT_DATA_DIR resolves to an absolute on-disk path
        raw = self.get(OUTPUT_DATA_DIR_KEY)
        return self._resolve_output_dir_value(raw)

    @property
    def SESSION_DIR(self):
        """Resolve and cache the concrete session directory path.

        Expands:
        - {OUTPUT_DATA_DIR} -> resolved OUTPUT_DATA_DIR path
        - {device_id}, {app_package}, {timestamp}
        If a session was already resolved this run, reuse it for stability.
        """
        # Reuse cached session path if present
        if "SESSION_DIR" in self._session_context:
            return self._session_context["SESSION_DIR"]

        template = self.get("SESSION_DIR")
        template = self._resolve_output_dir_placeholder(template)

        # Build session variables
        device_id = self.get("TARGET_DEVICE_UDID") or "unknown_device"
        app_package = (self.get("APP_PACKAGE") or "unknown.app").replace(".", "_")
        # Stable timestamp per process
        ts = self._session_context.get("SESSION_TIMESTAMP")
        if not ts:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._session_context["SESSION_TIMESTAMP"] = ts

        # Fallback if template missing
        if not template:
            base = self.OUTPUT_DATA_DIR or self._project_root()
            session_dir = os.path.join(base, f"{device_id}_{app_package}_{ts}")
        else:
            # Replace variables in template string
            session_dir = template
            session_dir = session_dir.replace("{device_id}", device_id)
            session_dir = session_dir.replace("{app_package}", app_package)
            session_dir = session_dir.replace("{timestamp}", ts)

        # Normalize and cache
        session_dir = os.path.abspath(session_dir)
        self._session_context["SESSION_DIR"] = session_dir
        return session_dir

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
        # Resolve template with session variables
        template = self.get("LOG_DIR")
        template = self._resolve_output_dir_placeholder(template)
        if template and "{session_dir}" in template:
            session_dir = self.SESSION_DIR
            if session_dir:
                return template.replace("{session_dir}", session_dir)
        return template

    @property
    def LOG_FILE_NAME(self):
        return self.get("LOG_FILE_NAME")

    @property
    def CONTINUE_EXISTING_RUN(self):
        return self.get("CONTINUE_EXISTING_RUN")

    @property
    def DB_NAME(self):
        # Resolve template with session variables
        template = self.get("DB_NAME")
        template = self._resolve_output_dir_placeholder(template)
        if template and "{session_dir}" in template:
            session_dir = self.SESSION_DIR
            if session_dir:
                template = template.replace("{session_dir}", session_dir)
        if template and "{package}" in template:
            package = self.get("APP_PACKAGE", "").replace(".", "_")
            template = template.replace("{package}", package)
        return template

    @property
    def SCREENSHOTS_DIR(self):
        # Resolve template with session variables
        template = self.get("SCREENSHOTS_DIR")
        template = self._resolve_output_dir_placeholder(template)
        if template and "{session_dir}" in template:
            session_dir = self.SESSION_DIR
            if session_dir:
                return template.replace("{session_dir}", session_dir)
        return template

    @property
    def ANNOTATED_SCREENSHOTS_DIR(self):
        # Resolve template with session variables
        template = self.get("ANNOTATED_SCREENSHOTS_DIR")
        template = self._resolve_output_dir_placeholder(template)
        if template and "{session_dir}" in template:
            session_dir = self.SESSION_DIR
            if session_dir:
                return template.replace("{session_dir}", session_dir)
        return template

    @property
    def TRAFFIC_CAPTURE_OUTPUT_DIR(self):
        # Resolve template with session variables
        template = self.get("TRAFFIC_CAPTURE_OUTPUT_DIR")
        template = self._resolve_output_dir_placeholder(template)
        if template and "{session_dir}" in template:
            session_dir = self.SESSION_DIR
            if session_dir:
                return template.replace("{session_dir}", session_dir)
        return template

    @property
    def CRAWLER_PID_PATH(self):
        """Resolve OUTPUT_DATA_DIR in the crawler PID path template."""
        template = self.get("CRAWLER_PID_PATH")
        resolved = self._resolve_output_dir_placeholder(template)
        return os.path.abspath(resolved) if resolved else resolved

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
            return [fa["area"] for fa in focus_areas if fa["enabled"]]
        return self.get("focus_areas")

    @property
    def MAX_APPS_TO_SEND_TO_AI(self):
        return self.get("MAX_APPS_TO_SEND_TO_AI")

    @property
    def THIRD_PARTY_APPS_ONLY(self):
        return self.get("THIRD_PARTY_APPS_ONLY")

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

    def update_setting_and_save(self, key: str, value: Any, callback: Optional[Callable] = None) -> None:
        """
        Backwards-compatible helper used throughout the codebase.
        Persists the value to the runtime cache and user store (unless secret),
        then invokes an optional callback (used to sync UI/API files).
        """
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
MAX_APPS_TO_SEND_TO_AI = 200
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
    "qwen2.5vl": {
        "name": "qwen2.5vl",
        "description": "Qwen 2.5 VL model for vision-language tasks.",
        "generation_config": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 1024,
        },
        "online": False,
        "vision_supported": True,
    },
    "granite3.2-vision": {
        "name": "granite3.2-vision",
        "description": "Granite 3.2 Vision model with multimodal capabilities.",
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
THIRD_PARTY_APPS_ONLY = True

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