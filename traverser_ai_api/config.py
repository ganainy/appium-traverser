import os
import logging
import sys
import os
import json
from typing import Optional, Dict, Any, List, Union, get_type_hints
from dotenv import load_dotenv

# --- Centralized Configuration Class ---
class Config:
    def __init__(self, defaults_module_path: str, user_config_json_path: str):
        self.DEFAULTS_MODULE_PATH = os.path.abspath(defaults_module_path)
        self.USER_CONFIG_FILE_PATH = os.path.abspath(user_config_json_path)
        self.BASE_DIR = os.path.dirname(self.DEFAULTS_MODULE_PATH) # Dir where config.py resides
        self.SHUTDOWN_FLAG_PATH: Optional[str] = None  # Path to the shutdown flag file

        # --- Initialize all attributes to None or default literals ---
        self.APP_PACKAGE: Optional[str] = None
        self.APP_ACTIVITY: Optional[str] = None
        self.ALLOWED_EXTERNAL_PACKAGES: List[str] = []
        self.OUTPUT_DATA_DIR: Optional[str] = None # This will be the resolved absolute path
        self.APP_INFO_OUTPUT_DIR: Optional[str] = None
        self.SCREENSHOTS_DIR: Optional[str] = None
        self.ANNOTATED_SCREENSHOTS_DIR: Optional[str] = None
        self.TRAFFIC_CAPTURE_OUTPUT_DIR: Optional[str] = None
        self.LOG_LEVEL: str = 'INFO'
        self.LOG_FILE_NAME: str = "app.log"
        self.DB_NAME: Optional[str] = None
        self.DB_CONNECT_TIMEOUT: int = 10
        self.DB_BUSY_TIMEOUT: int = 5000
        self.WAIT_AFTER_ACTION: float = 2.0
        self.STABILITY_WAIT: float = 1.0
        self.APP_LAUNCH_WAIT_TIME: int = 7
        self.NEW_COMMAND_TIMEOUT: int = 300
        self.APPIUM_IMPLICIT_WAIT: int = 1
        self.APPIUM_SERVER_URL: str = "http://127.0.0.1:4723"
        self.TARGET_DEVICE_UDID: Optional[str] = None
        self.USE_COORDINATE_FALLBACK: bool = True
        self.GEMINI_API_KEY: Optional[str] = None
        self.DEFAULT_MODEL_TYPE: str = 'flash-latest-fast'
        self.USE_CHAT_MEMORY: bool = False
        self.MAX_CHAT_HISTORY: int = 10
        self.ENABLE_XML_CONTEXT: bool = True
        self.XML_SNIPPET_MAX_LEN: int = 500000
        self.MAX_APPS_TO_SEND_TO_AI: int = 200
        self.LOOP_DETECTION_VISIT_THRESHOLD: int = 1
        self.USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY: bool = False
        self.AI_SAFETY_SETTINGS: Dict[str, Any] = {}
        self.GEMINI_MODELS: Dict[str, Any] = {}
        self.CRAWL_MODE: str = 'steps'
        self.MAX_CRAWL_STEPS: int = 10
        self.MAX_CRAWL_DURATION_SECONDS: int = 600
        self.CONTINUE_EXISTING_RUN: bool = False
        self.VISUAL_SIMILARITY_THRESHOLD: int = 5
        self.THIRD_PARTY_APPS_ONLY: bool = True
        self.AVAILABLE_ACTIONS: List[str] = []
        self.ACTION_DESC_CLICK: Optional[str] = None
        self.ACTION_DESC_INPUT: Optional[str] = None
        self.ACTION_DESC_SCROLL_DOWN: Optional[str] = None
        self.ACTION_DESC_SCROLL_UP: Optional[str] = None
        self.ACTION_DESC_BACK: Optional[str] = None
        self.MAX_CONSECUTIVE_AI_FAILURES: int = 3
        self.MAX_CONSECUTIVE_MAP_FAILURES: int = 3
        self.MAX_CONSECUTIVE_EXEC_FAILURES: int = 3
        self.MAX_CONSECUTIVE_CONTEXT_FAILURES: int = 3
        self.ENABLE_TRAFFIC_CAPTURE: bool = True
        self.PCAPDROID_PACKAGE: str = "com.emanuelef.remote_capture"
        self.PCAPDROID_ACTIVITY: Optional[str] = None # Will be derived
        self.PCAPDROID_API_KEY: Optional[str] = None
        self.DEVICE_PCAP_DIR: str = "/sdcard/Download/PCAPdroid"
        self.CLEANUP_DEVICE_PCAP_FILE: bool = True
        self.CURRENT_HEALTH_APP_LIST_FILE: Optional[str] = None # From user_config typically
        self.LAST_SELECTED_APP: Optional[Dict[str,str]] = None # From user_config typically

        # Store templates from defaults for dynamic resolution
        self._OUTPUT_DATA_DIR_TEMPLATE: str = "output_data"
        self._APP_INFO_OUTPUT_DIR_TEMPLATE: str = "{output_data_dir}/app_info"
        self._SCREENSHOTS_DIR_TEMPLATE: str = "{output_data_dir}/screenshots/crawl_screenshots_{package}"
        self._ANNOTATED_SCREENSHOTS_DIR_TEMPLATE: str = "{output_data_dir}/screenshots/annotated_crawl_screenshots_{package}"
        self._TRAFFIC_CAPTURE_OUTPUT_DIR_TEMPLATE: str = "{output_data_dir}/traffic_captures"
        self._DB_NAME_TEMPLATE: str = "{output_data_dir}/database_output/{package}_crawl_data.db"

        self._load_from_defaults_module()
        self._load_environment_variables()
        self.load_user_config() # Loads from self.USER_CONFIG_FILE_PATH and resolves paths

    def _load_from_defaults_module(self):
        defaults_vars = {'os': os} # Provide 'os' module for config.py if it uses it
        try:
            with open(self.DEFAULTS_MODULE_PATH, 'r', encoding='utf-8') as f:
                exec(f.read(), defaults_vars)

            # Process path templates first
            path_templates = {
                "OUTPUT_DATA_DIR": "_OUTPUT_DATA_DIR_TEMPLATE",
                "APP_INFO_OUTPUT_DIR": "_APP_INFO_OUTPUT_DIR_TEMPLATE",
                "SCREENSHOTS_DIR": "_SCREENSHOTS_DIR_TEMPLATE",
                "ANNOTATED_SCREENSHOTS_DIR": "_ANNOTATED_SCREENSHOTS_DIR_TEMPLATE",
                "TRAFFIC_CAPTURE_OUTPUT_DIR": "_TRAFFIC_CAPTURE_OUTPUT_DIR_TEMPLATE",
                "DB_NAME": "_DB_NAME_TEMPLATE"
            }
            
            for key in path_templates:
                value = defaults_vars.get(key)
                if value is not None:
                    if isinstance(value, str):
                        setattr(self, path_templates[key], str(value))
                    else:
                        logging.warning(f"Config key '{key}' in {self.DEFAULTS_MODULE_PATH} is not a string, using default template.")

            # Process other configuration values
            for key, value in defaults_vars.items():
                if key.startswith('__') or callable(value) or isinstance(value, type(sys)) or key in path_templates:
                    continue

                if hasattr(self, key):
                    expected_attr = getattr(self, key)
                    if expected_attr is not None and not isinstance(value, type(expected_attr)) and not isinstance(value, (int, float, str, list, dict, bool)):
                        logging.warning(f"Config key '{key}' in {self.DEFAULTS_MODULE_PATH} has an unexpected type ({type(value)}). Skipping assignment from defaults.")
                        continue
                    setattr(self, key, value)

            logging.info(f"Loaded base defaults from: {self.DEFAULTS_MODULE_PATH}")
        except Exception as e:
            logging.critical(f"Failed to load base defaults from '{self.DEFAULTS_MODULE_PATH}': {e}", exc_info=True)
            raise

    def _load_environment_variables(self):
        load_dotenv(override=True) # Load .env file, potentially overriding existing env vars
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", self.GEMINI_API_KEY)
        self.PCAPDROID_API_KEY = os.getenv("PCAPDROID_API_KEY", self.PCAPDROID_API_KEY)
        # Add other environment variables you wish to load
        # Example: self.TARGET_DEVICE_UDID = os.getenv("TARGET_DEVICE_UDID", self.TARGET_DEVICE_UDID)
        logging.info("Applied configuration from environment variables.")

    def _update_attribute(self, key: str, new_value: Any, source: str, perform_type_conversion: bool = True):
        if not hasattr(self, key):
            # logging.debug(f"Key '{key}' from {source} not a recognized config attribute. Skipping.")
            return False # Do not add new attributes not defined in __init__

        old_value = getattr(self, key)
        converted_value = new_value

        if perform_type_conversion:
            type_hints = get_type_hints(Config) # Use self.__class__ if in external helper
            target_type_hinted = type_hints.get(key)

            if target_type_hinted is not None:
                origin_type = getattr(target_type_hinted, '__origin__', None)
                args_type = getattr(target_type_hinted, '__args__', tuple())

                actual_target_type = None
                if origin_type is Union: # Handles Optional[T] which is Union[T, NoneType]
                    non_none_args = [t for t in args_type if t is not type(None)]
                    if len(non_none_args) == 1:
                        actual_target_type = non_none_args[0]
                elif origin_type is list and len(args_type) == 1: # Handles List[T]
                     actual_target_type = list # Keep as list, element type conversion is harder here
                elif origin_type is dict and len(args_type) == 2: # Handles Dict[K,V]
                    actual_target_type = dict
                elif origin_type is None: # Not a generic type like Optional, List, Dict
                    actual_target_type = target_type_hinted


                if actual_target_type and not isinstance(new_value, actual_target_type):
                    try:
                        if actual_target_type == bool:
                            converted_value = str(new_value).lower() in ['true', '1', 'yes', 'on']
                        elif actual_target_type == int:
                            converted_value = int(new_value)
                        elif actual_target_type == float:
                            converted_value = float(new_value)
                        elif actual_target_type == list and isinstance(new_value, str):
                             # Special case for lists coming as newline-separated strings from UI
                            converted_value = [item.strip() for item in new_value.split('\n') if item.strip()]
                        # Add more specific conversions if necessary
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Type conversion error for '{key}' from {source} (value: '{new_value}', type: {type(new_value)}). Expected {actual_target_type}. Using original value. Error: {e}")
                        converted_value = old_value # Revert to old if conversion fails

        if old_value != converted_value:
            setattr(self, key, converted_value)
            logging.info(f"Config changed by {source}: {key} = {converted_value} (was: {old_value})")
        return True

    def load_user_config(self, path: Optional[str] = None):
        file_path = path or self.USER_CONFIG_FILE_PATH
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                logging.info(f"Loading user configuration from: {file_path}")
                for key, value in user_data.items():
                    self._update_attribute(key, value, source=f"user_config '{os.path.basename(file_path)}'")
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing user config {file_path}: Invalid JSON. {e}", exc_info=True)
            except Exception as e:
                logging.warning(f"Failed to load or apply user config from {file_path}: {e}", exc_info=True)
        else:
            logging.info(f"User configuration file ({file_path}) not found. Using defaults and environment variables.")
        self._resolve_all_paths() # Resolve paths after all overrides

    def _get_user_savable_config(self) -> Dict[str, Any]:
        # Define keys that are safe and intended to be saved in user_config.json
        # Exclude API keys if managed by env, or complex internal state.
        savable_keys = [
            "APP_PACKAGE", "APP_ACTIVITY", "ALLOWED_EXTERNAL_PACKAGES",
            "LOG_LEVEL", # User might want to change this
            "DB_CONNECT_TIMEOUT", "DB_BUSY_TIMEOUT",
            "WAIT_AFTER_ACTION", "STABILITY_WAIT", "APP_LAUNCH_WAIT_TIME",
            "NEW_COMMAND_TIMEOUT", "APPIUM_IMPLICIT_WAIT", "APPIUM_SERVER_URL",
            "TARGET_DEVICE_UDID", "USE_COORDINATE_FALLBACK",
            "DEFAULT_MODEL_TYPE", "USE_CHAT_MEMORY", "MAX_CHAT_HISTORY",
            "ENABLE_XML_CONTEXT", "XML_SNIPPET_MAX_LEN", "MAX_APPS_TO_SEND_TO_AI",
            "USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY", "AI_SAFETY_SETTINGS", #"GEMINI_MODELS" (can be large),
            "CRAWL_MODE", "MAX_CRAWL_STEPS", "MAX_CRAWL_DURATION_SECONDS",
            "CONTINUE_EXISTING_RUN", "VISUAL_SIMILARITY_THRESHOLD", "THIRD_PARTY_APPS_ONLY",
            "MAX_CONSECUTIVE_AI_FAILURES", "MAX_CONSECUTIVE_MAP_FAILURES", "MAX_CONSECUTIVE_EXEC_FAILURES",
            "ENABLE_TRAFFIC_CAPTURE", "PCAPDROID_PACKAGE", # PCAPDROID_ACTIVITY is derived
            "DEVICE_PCAP_DIR", "CLEANUP_DEVICE_PCAP_FILE",
            "CURRENT_HEALTH_APP_LIST_FILE", "LAST_SELECTED_APP",
            "_OUTPUT_DATA_DIR_TEMPLATE", # Save the template so user can change base output loc
        ]
        config_to_save = {}
        for key in savable_keys:
            if hasattr(self, key):
                value = getattr(self, key)
                # Ensure complex objects like GEMINI_MODELS are serializable or handled
                if key == "GEMINI_MODELS" and not isinstance(value, dict): # Basic check
                    pass # Or convert to a simpler representation if needed
                else:
                    config_to_save[key] = value
        # Rename _OUTPUT_DATA_DIR_TEMPLATE to OUTPUT_DATA_DIR for saving
        if "_OUTPUT_DATA_DIR_TEMPLATE" in config_to_save:
            config_to_save["OUTPUT_DATA_DIR"] = config_to_save.pop("_OUTPUT_DATA_DIR_TEMPLATE")

        return config_to_save

    def save_user_config(self, path: Optional[str] = None) -> None:
        file_path = path or self.USER_CONFIG_FILE_PATH
        data_to_save = self._get_user_savable_config()
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            logging.info(f"User configuration saved to: {file_path}")
        except Exception as e:
            logging.error(f"Failed to save user configuration to {file_path}: {e}", exc_info=True)

    def _resolve_path_template(self, template: Optional[str], base_output_dir: str, app_package: Optional[str]) -> str:
        if template is None: return ""
        
        resolved_path = template
        if "{output_data_dir}" in resolved_path:
            resolved_path = resolved_path.replace("{output_data_dir}", base_output_dir)
        if app_package and "{package}" in resolved_path:
            resolved_path = resolved_path.replace("{package}", app_package)
        
        if not os.path.isabs(resolved_path):
            # Paths from templates are relative to self.BASE_DIR (where config.py is)
            # OR relative to current working directory if not specified.
            # For consistency, let's make them relative to where config.py (defaults module) is.
            return os.path.abspath(os.path.join(self.BASE_DIR, resolved_path))
        return os.path.abspath(resolved_path) # Ensure even "absolute" paths are normalized

    def _resolve_all_paths(self):
        # 1. Resolve the main OUTPUT_DATA_DIR first
        # It's based on _OUTPUT_DATA_DIR_TEMPLATE which could be relative or absolute.
        # If relative, it's relative to self.BASE_DIR.
        if not os.path.isabs(self._OUTPUT_DATA_DIR_TEMPLATE):
            self.OUTPUT_DATA_DIR = os.path.abspath(os.path.join(self.BASE_DIR, self._OUTPUT_DATA_DIR_TEMPLATE))
        else:
            self.OUTPUT_DATA_DIR = os.path.abspath(self._OUTPUT_DATA_DIR_TEMPLATE)
        os.makedirs(self.OUTPUT_DATA_DIR, exist_ok=True) # Ensure base output dir exists

        # 2. Resolve other paths based on the now absolute self.OUTPUT_DATA_DIR and self.APP_PACKAGE
        current_app_package = getattr(self, 'APP_PACKAGE', "unknown_package")

        self.DB_NAME = self._resolve_path_template(self._DB_NAME_TEMPLATE, self.OUTPUT_DATA_DIR, current_app_package)
        self.SCREENSHOTS_DIR = self._resolve_path_template(self._SCREENSHOTS_DIR_TEMPLATE, self.OUTPUT_DATA_DIR, current_app_package)
        self.ANNOTATED_SCREENSHOTS_DIR = self._resolve_path_template(self._ANNOTATED_SCREENSHOTS_DIR_TEMPLATE, self.OUTPUT_DATA_DIR, current_app_package)
        self.APP_INFO_OUTPUT_DIR = self._resolve_path_template(self._APP_INFO_OUTPUT_DIR_TEMPLATE, self.OUTPUT_DATA_DIR, current_app_package)
        self.TRAFFIC_CAPTURE_OUTPUT_DIR = self._resolve_path_template(self._TRAFFIC_CAPTURE_OUTPUT_DIR_TEMPLATE, self.OUTPUT_DATA_DIR, current_app_package)

        # Derive PCAPDROID_ACTIVITY if PCAPDROID_PACKAGE is set
        if self.PCAPDROID_PACKAGE:
            self.PCAPDROID_ACTIVITY = f"{self.PCAPDROID_PACKAGE}/.activities.CaptureCtrl"

        logging.info("Resolved dynamic configuration paths.")
        logging.debug(f"  OUTPUT_DATA_DIR: {self.OUTPUT_DATA_DIR}")
        logging.debug(f"  DB_NAME: {self.DB_NAME}")
        logging.debug(f"  SCREENSHOTS_DIR: {self.SCREENSHOTS_DIR}")


    def update_setting_and_save(self, key: str, value: Any):
        """Public method to update a setting and persist to user_config.json"""
        if self._update_attribute(key, value, source="gui/dynamic_update"):
            # Check if paths need re-resolving
            if key in ["APP_PACKAGE", "_OUTPUT_DATA_DIR_TEMPLATE", "OUTPUT_DATA_DIR"]:
                if key == "OUTPUT_DATA_DIR": # if user directly sets OUTPUT_DATA_DIR
                    self._OUTPUT_DATA_DIR_TEMPLATE = value # update the template
                self._resolve_all_paths()
            
            self.save_user_config()

            # If logging settings change, the main script might need to re-init the logger
            if key in ["LOG_LEVEL", "LOG_FILE_NAME"]:
                logging.warning(f"Logging setting '{key}' changed. Logger re-initialization might be needed by the application.")



# --- App Settings ---
APP_PACKAGE = "de.deltacity.android.blutspende"
APP_ACTIVITY = "de.deltacity.android.blutspende.activities.SplashScreenActivity"
ALLOWED_EXTERNAL_PACKAGES = [
    "com.google.android.gms",               # Google Play Services
    "com.android.chrome",                   # Google Chrome
    "com.google.android.permissioncontroller",  # System Permission Controller
    "org.mozilla.firefox",                  # Mozilla Firefox
    "com.sec.android.app.sbrowser",         # Samsung Internet Browser
    "com.microsoft.emmx",                   # Microsoft Edge
    "com.brave.browser",                    # Brave Browser
    "com.duckduckgo.mobile.android",        # DuckDuckGo Privacy Browser
]

# --- Base Output Directory Configuration (Templates) ---
# OUTPUT_DATA_DIR is the base for other output paths.
# It can be a simple name (relative to config.py's location) or an absolute path.
OUTPUT_DATA_DIR = "output_data"
APP_INFO_OUTPUT_DIR = "{output_data_dir}/app_info"
SCREENSHOTS_DIR = "{output_data_dir}/screenshots/crawl_screenshots_{package}"
ANNOTATED_SCREENSHOTS_DIR = "{output_data_dir}/screenshots/annotated_crawl_screenshots_{package}"
TRAFFIC_CAPTURE_OUTPUT_DIR = "{output_data_dir}/traffic_captures"

# --- Logging Configuration ---
LOG_LEVEL = 'INFO'  # Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE_NAME = "main_traverser_final.log" # Filename, full path resolved later

# --- Database Settings (Template) ---
DB_NAME = "{output_data_dir}/database_output/{package}_crawl_data.db"
DB_CONNECT_TIMEOUT = 10  # Seconds for sqlite3.connect() timeout
DB_BUSY_TIMEOUT = 5000  # Milliseconds for PRAGMA busy_timeout

# --- Timing Settings ---
WAIT_AFTER_ACTION = 2.0  # Seconds to wait for UI to potentially change after an action
STABILITY_WAIT = 1.0  # Seconds to wait before getting state (screenshot/XML)
APP_LAUNCH_WAIT_TIME = 7  # Seconds to wait after launching an app for it to stabilize
NEW_COMMAND_TIMEOUT = 300  # Seconds Appium waits for a new command before quitting session
APPIUM_IMPLICIT_WAIT = 1  # Seconds Appium driver waits when trying to find elements

# --- Appium Settings ---
APPIUM_SERVER_URL = "http://127.0.0.1:4723"
TARGET_DEVICE_UDID = None  # Optional: Specify UDID, e.g., "emulator-5554"
USE_COORDINATE_FALLBACK = True  # Use bounding box coordinates if element identification fails

# --- AI and Machine Learning Settings ---
# GEMINI_API_KEY will be loaded from environment variables by the Config class
DEFAULT_MODEL_TYPE = 'flash-latest-fast'
USE_CHAT_MEMORY = False  # Enable/disable chat history
MAX_CHAT_HISTORY = 10
ENABLE_XML_CONTEXT = True
XML_SNIPPET_MAX_LEN = 500000  # Max characters of XML to send
MAX_APPS_TO_SEND_TO_AI = 200
USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY = False

AI_SAFETY_SETTINGS = {
}

GEMINI_MODELS = {
    'flash-latest': {
        'name': 'gemini-2.5-flash-preview-05-20',
        'description': 'Latest Flash model (2.5): Optimized for speed, cost, and multimodal tasks.',
        'generation_config': {
            'temperature': 0.7,
            'top_p': 0.95,
            'top_k': 40,
            'max_output_tokens': 8192
        }
    },
    'flash-latest-fast': {
        'name': 'gemini-2.5-flash-preview-05-20',
        'description': 'Latest Flash model (2.5) with settings optimized for faster responses.',
        'generation_config': {
            'temperature': 0.3,
            'top_p': 0.8,
            'top_k': 20,
            'max_output_tokens': 8192
        }
    }
}

# --- Crawler Settings ---
CRAWL_MODE = 'steps'  # Options: 'steps' or 'time'
MAX_CRAWL_STEPS = 10
MAX_CRAWL_DURATION_SECONDS = 600  # 10 minutes
CONTINUE_EXISTING_RUN = False
VISUAL_SIMILARITY_THRESHOLD = 5  # Perceptual hash distance threshold
THIRD_PARTY_APPS_ONLY = True

# --- Action Definitions ---
AVAILABLE_ACTIONS = ["click", "input", "scroll_down", "scroll_up", "back"]
ACTION_DESC_CLICK = "Click the specified element."
ACTION_DESC_INPUT = "Input the provided text into the specified element."
ACTION_DESC_SCROLL_DOWN = "Scroll the screen down to reveal more content."
ACTION_DESC_SCROLL_UP = "Scroll the screen up to reveal previous content."
ACTION_DESC_BACK = "Press the device's back button."

# --- Error Handling ---
MAX_CONSECUTIVE_AI_FAILURES = 3
MAX_CONSECUTIVE_MAP_FAILURES = 3
MAX_CONSECUTIVE_EXEC_FAILURES = 3
MAX_CONSECUTIVE_CONTEXT_FAILURES = 3  # Maximum consecutive failures when getting screen context
LOOP_DETECTION_VISIT_THRESHOLD = 1  # Number of times a state can be visited before considering it a loop

# --- Traffic Capture Settings ---
ENABLE_TRAFFIC_CAPTURE = True
PCAPDROID_PACKAGE = "com.emanuelef.remote_capture"
PCAPDROID_ACTIVITY = f"{PCAPDROID_PACKAGE}/.activities.CaptureCtrl"
# PCAPDROID_API_KEY will be loaded from environment variables by the Config class
DEVICE_PCAP_DIR = "/sdcard/Download/PCAPdroid"
CLEANUP_DEVICE_PCAP_FILE = True  # Delete PCAP file from device after successful pull