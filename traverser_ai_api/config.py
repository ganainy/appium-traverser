import os
import logging
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, get_type_hints, Callable
from dotenv import load_dotenv


# --- Centralized Configuration Class ---
class Config:
    def __init__(self, defaults_module_path: str, user_config_json_path: str):
        self.DEFAULTS_MODULE_PATH = os.path.abspath(defaults_module_path)
        self.USER_CONFIG_FILE_PATH = os.path.abspath(user_config_json_path)
        self.BASE_DIR = os.path.dirname(
            self.DEFAULTS_MODULE_PATH
        )  # Dir where config.py resides
        self.SHUTDOWN_FLAG_PATH = os.path.join(
            self.BASE_DIR, "crawler_shutdown.flag"
        )  # Set default path for shutdown flag
        self.PAUSE_FLAG_PATH = os.path.join(
            self.BASE_DIR, "crawler_pause.flag"
        )  # For pause/resume

        # --- Initialize all attributes to None or default literals ---
        self.APP_PACKAGE: Optional[str] = None
        self.APP_ACTIVITY: Optional[str] = None
        self.ALLOWED_EXTERNAL_PACKAGES: List[str] = []
        self.OUTPUT_DATA_DIR: Optional[str] = (
            None  # This will be the resolved absolute path
        )
        self.SESSION_DIR: Optional[str] = None  # Unique session directory for each run
        self.APP_INFO_OUTPUT_DIR: Optional[str] = None
        self.SCREENSHOTS_DIR: Optional[str] = None
        self.ANNOTATED_SCREENSHOTS_DIR: Optional[str] = None
        self.TRAFFIC_CAPTURE_OUTPUT_DIR: Optional[str] = None
        self.LOG_DIR: Optional[str] = None  # For app-specific logs
        self.LOG_LEVEL: str = "INFO"
        self.LOG_FILE_NAME: str = "main_traverser_final.log"
        self.DB_NAME: Optional[str] = None
        self.MOBSF_SCAN_DIR: Optional[str] = None
        self.EXTRACTED_APK_DIR: Optional[str] = None
        self.PDF_REPORT_DIR: Optional[str] = None
        self.VIDEO_RECORDING_DIR: Optional[str] = None
        self.ENABLE_VIDEO_RECORDING: bool = False
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
        self.OPENROUTER_API_KEY: Optional[str] = None
        self.OPENROUTER_REFRESH_BTN: bool = False
        self.OPENROUTER_SHOW_FREE_ONLY: bool = False
        self.OPENROUTER_NON_FREE_WARNING: bool = False
        self.OLLAMA_BASE_URL: Optional[str] = None
        self.AI_PROVIDER: str = "gemini"  # 'gemini', or 'ollama'
        self.DEFAULT_MODEL_TYPE: str = "flash-latest-fast"
        self.USE_CHAT_MEMORY: bool = False
        self.MAX_CHAT_HISTORY: int = 10
        self.ENABLE_IMAGE_CONTEXT: bool = False
        self.XML_SNIPPET_MAX_LEN: int = 15000
        self.MAX_APPS_TO_SEND_TO_AI: int = 200
        self.LOOP_DETECTION_VISIT_THRESHOLD: int = 1
        self.USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY: bool = True
        self.AI_SAFETY_SETTINGS: Dict[str, Any] = {}
        self.GEMINI_MODELS: Dict[str, Any] = {}
        self.OLLAMA_MODELS: Dict[str, Any] = {}
        self.OPENROUTER_MODELS: Dict[str, Any] = {}
        self.CRAWL_MODE: str = "steps"
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
        # ---- Start of Corrected Area ----
        self.ACTION_DESC_SWIPE_LEFT: Optional[str] = None
        self.ACTION_DESC_SWIPE_RIGHT: Optional[str] = None
        self.ACTION_DESC_LONG_PRESS: Optional[str] = None
        # ---- End of Corrected Area ----
        # Long press minimum duration (ms) for tap-and-hold semantics
        self.LONG_PRESS_MIN_DURATION_MS: int = 600
        self.MAX_CONSECUTIVE_AI_FAILURES: int = 3
        self.MAX_CONSECUTIVE_MAP_FAILURES: int = 3
        self.MAX_CONSECUTIVE_EXEC_FAILURES: int = 3
        self.MAX_CONSECUTIVE_CONTEXT_FAILURES: int = 3
        # ---- Start of Corrected Area ----
        self.MAX_CONSECUTIVE_NO_OP_FAILURES: int = 3
        # Cap how many times the same action can be attempted on the same screen before forcing a fallback
        self.MAX_SAME_ACTION_REPEAT: int = 3
        self.FALLBACK_ACTIONS_SEQUENCE: List[Dict[str, Any]] = []
        self.USE_ADB_INPUT_FALLBACK: bool = True
        # Safety tap configuration (used by AppiumDriver.tap_at_coordinates)
        self.SAFE_TAP_MARGIN_RATIO: float = 0.03  # 3% safe margin from each edge
        self.SAFE_TAP_EDGE_HANDLING: str = "snap"  # 'reject' or 'snap'
        # Overlay/Toast handling (used by ActionExecutor pre-action wait)
        self.TOAST_DISMISS_WAIT_MS: int = 1200
        # ---- End of Corrected Area ----
        self.ENABLE_TRAFFIC_CAPTURE: bool = True
        self.PCAPDROID_PACKAGE: str = "com.emanuelef.remote_capture"
        self.PCAPDROID_ACTIVITY: Optional[str] = None  # Will be derived
        self.PCAPDROID_API_KEY: Optional[str] = None
        self.DEVICE_PCAP_DIR: str = "/sdcard/Download/PCAPdroid"
        self.CLEANUP_DEVICE_PCAP_FILE: bool = True
        self.CURRENT_HEALTH_APP_LIST_FILE: Optional[str] = None
        self.LAST_SELECTED_APP: Optional[Dict[str, str]] = None
        self.UI_MODE: str = "Basic"  # basic or expert

        self.MOBSF_API_URL: Optional[str] = None
        self.MOBSF_API_KEY: Optional[str] = None
        self.ENABLE_MOBSF_ANALYSIS: bool = False

        # Focus areas for AI agent behavior
        self.FOCUS_AREAS: List[Dict[str, Any]] = []
        # Limit how many enabled focus areas are considered ACTIVE in prompts/validation
        self.FOCUS_MAX_ACTIVE: int = 5
        # Optionally disable expensive XPath strategies for element search
        # Enable by default to improve matching robustness
        self.DISABLE_EXPENSIVE_XPATH: bool = False
        # Cap how many element-finding strategies are attempted per mapping
        # Set to 0 or negative to disable capping
        self.ELEMENT_STRATEGY_MAX_ATTEMPTS: int = 0
        # Auto-hide software keyboard before non-input actions to avoid overlay-induced no-ops
        self.AUTO_HIDE_KEYBOARD_BEFORE_NON_INPUT: bool = True

        # Image preprocessing controls (persisted and overridable via UI)
        # These correspond to global defaults defined at the bottom of this file
        # and will be loaded by _load_from_defaults_module, then saved to user_config.json
        self.IMAGE_MAX_WIDTH: int = 896  # Max width for downsampling; no upscaling
        self.IMAGE_FORMAT: str = "JPEG"  # Preferred encoding format (JPEG/WebP/PNG)
        self.IMAGE_QUALITY: int = 70  # Compression quality (0-100)
        self.IMAGE_CROP_BARS: bool = (
            True  # Crop status/navigation bars to reduce payload
        )
        self.IMAGE_CROP_TOP_PERCENT: float = 0.06  # Fraction of height to crop from top
        self.IMAGE_CROP_BOTTOM_PERCENT: float = (
            0.06  # Fraction of height to crop from bottom
        )

        # Store templates from defaults for dynamic resolution
        self._OUTPUT_DATA_DIR_TEMPLATE = "output_data"
        self._SESSION_DIR_TEMPLATE = (
            "{output_data_dir}/{{device_id}}_{{app_package}}_{{timestamp}}"
        )
        # Store app_info outside the per-run session so it can be reused across runs
        # New stable location: <OUTPUT_DATA_DIR>/app_info/<device_id>
        self._APP_INFO_OUTPUT_DIR_TEMPLATE = "{output_data_dir}/app_info/{device_id}"
        self._SCREENSHOTS_DIR_TEMPLATE = "{session_dir}/screenshots"
        self._ANNOTATED_SCREENSHOTS_DIR_TEMPLATE = "{session_dir}/annotated_screenshots"
        self._TRAFFIC_CAPTURE_OUTPUT_DIR_TEMPLATE = "{session_dir}/traffic_captures"
        self._DB_NAME_TEMPLATE = "{session_dir}/database/{package}_crawl_data.db"
        self._LOG_DIR_TEMPLATE = "{session_dir}/logs"
        self._MOBSF_SCAN_DIR_TEMPLATE = "{session_dir}/mobsf_scan_results"
        self._EXTRACTED_APK_DIR_TEMPLATE = "{session_dir}/extracted_apk"
        self._PDF_REPORT_DIR_TEMPLATE = "{session_dir}/reports"
        self._VIDEO_RECORDING_DIR_TEMPLATE = "{session_dir}/video"

        self._load_from_defaults_module()
        self._load_environment_variables()
        self.load_user_config()

    def _load_from_defaults_module(self):
        defaults_vars = {"os": os}
        try:
            with open(self.DEFAULTS_MODULE_PATH, "r", encoding="utf-8") as f:
                exec(f.read(), defaults_vars)

            path_templates = {
                "OUTPUT_DATA_DIR": "_OUTPUT_DATA_DIR_TEMPLATE",
                "SESSION_DIR": "_SESSION_DIR_TEMPLATE",
                "APP_INFO_OUTPUT_DIR": "_APP_INFO_OUTPUT_DIR_TEMPLATE",
                "SCREENSHOTS_DIR": "_SCREENSHOTS_DIR_TEMPLATE",
                "ANNOTATED_SCREENSHOTS_DIR": "_ANNOTATED_SCREENSHOTS_DIR_TEMPLATE",
                "TRAFFIC_CAPTURE_OUTPUT_DIR": "_TRAFFIC_CAPTURE_OUTPUT_DIR_TEMPLATE",
                "DB_NAME": "_DB_NAME_TEMPLATE",
                "LOG_DIR": "_LOG_DIR_TEMPLATE",
                "MOBSF_SCAN_DIR": "_MOBSF_SCAN_DIR_TEMPLATE",
                "EXTRACTED_APK_DIR": "_EXTRACTED_APK_DIR_TEMPLATE",
                "PDF_REPORT_DIR": "_PDF_REPORT_DIR_TEMPLATE",
                "VIDEO_RECORDING_DIR": "_VIDEO_RECORDING_DIR_TEMPLATE",
            }

            for key in path_templates:
                value = defaults_vars.get(key)
                if value is not None:
                    if isinstance(value, str):
                        setattr(self, path_templates[key], str(value))
                    else:
                        logging.warning(
                            f"Config key '{key}' in {self.DEFAULTS_MODULE_PATH} is not a string, using default template."
                        )

            for key, value in defaults_vars.items():
                if (
                    key.startswith("__")
                    or callable(value)
                    or isinstance(value, type(sys))
                    or key in path_templates
                ):
                    continue

                if hasattr(self, key):
                    expected_attr = getattr(self, key)
                    # Simplified type check for brevity, ensure it covers your needs
                    if (
                        expected_attr is not None
                        and not isinstance(value, type(expected_attr))
                        and type(expected_attr) not in [Union, List, Dict, Any]
                    ):
                        # Check if the target type is a Union (like Optional)
                        is_union = (
                            getattr(type(expected_attr), "__origin__", None) is Union
                        )
                        if (
                            not is_union
                        ):  # only warn if not a Union type that could accept None or other types
                            # Allow assignment if default is None, value is provided
                            if not (expected_attr is None and value is not None):
                                logging.warning(
                                    f"Config key '{key}' in {self.DEFAULTS_MODULE_PATH} has type {type(value)} but expected {type(expected_attr)}. Assigning anyway."
                                )
                    setattr(self, key, value)

            logging.debug(f"Loaded base defaults from: {self.DEFAULTS_MODULE_PATH}")
        except Exception as e:
            logging.critical(
                f"Failed to load base defaults from '{self.DEFAULTS_MODULE_PATH}': {e}",
                exc_info=True,
            )
            raise

    def _load_environment_variables(self):
        # Always use the .env file in the project root (parent directory of BASE_DIR)
        project_root_env_path = os.path.abspath(
            os.path.join(os.path.dirname(self.BASE_DIR), ".env")
        )
        try:
            if os.path.exists(project_root_env_path):
                # Try to manually read and parse the .env file to avoid encoding issues
                with open(
                    project_root_env_path, "r", encoding="utf-8", errors="ignore"
                ) as env_file:
                    for line in env_file:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip("\"'")
                            os.environ[key] = value
                            logging.debug(f"Loaded environment variable: {key}=****")
                logging.debug(
                    f"Manually loaded environment variables from: {project_root_env_path}"
                )
            else:
                logging.warning(
                    f"No .env file found at expected location: {project_root_env_path}"
                )
                # Fallback to default dotenv behavior
                load_dotenv(override=True)
        except Exception as e:
            logging.error(
                f"Error loading .env file: {e}. Trying standard dotenv loader."
            )
            try:
                load_dotenv(override=True)
            except Exception as e2:
                logging.error(f"Failed to load environment variables with dotenv: {e2}")

        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", self.GEMINI_API_KEY)
        self.OPENROUTER_API_KEY = os.getenv(
            "OPENROUTER_API_KEY", self.OPENROUTER_API_KEY
        )
        self.OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", self.OLLAMA_BASE_URL)
        self.PCAPDROID_API_KEY = os.getenv("PCAPDROID_API_KEY", self.PCAPDROID_API_KEY)
        self.MOBSF_API_KEY = os.getenv("MOBSF_API_KEY", self.MOBSF_API_KEY)
        logging.debug("Applied configuration from environment variables.")

    def _generate_session_dir_name(self) -> str:
        """Generate a unique session directory name with device_id, app_package, and timestamp.
        Attempts to get the real device ID using ADB if not set in config.
        """
        import re
        import subprocess

        device_id = self.TARGET_DEVICE_UDID
        # Sanitize placeholder values that may have been persisted accidentally
        if isinstance(device_id, str) and device_id.strip().lower() in (
            "no devices found",
            "",
        ):
            device_id = None
        if not device_id:
            try:
                result = subprocess.run(
                    ["adb", "get-serialno"], capture_output=True, text=True, timeout=5
                )
                if (
                    result.returncode == 0
                    and result.stdout.strip()
                    and result.stdout.strip() != "unknown"
                ):
                    device_id = result.stdout.strip()
                else:
                    # Fallback to 'adb devices' if get-serialno fails
                    devices_result = subprocess.run(
                        ["adb", "devices"], capture_output=True, text=True, timeout=5
                    )
                    if devices_result.returncode == 0:
                        lines = devices_result.stdout.strip().splitlines()
                        device_lines = [
                            line
                            for line in lines[1:]
                            if line.strip() and "\tdevice" in line
                        ]
                        if device_lines:
                            device_id = device_lines[0].split("\t")[0].strip()
            except Exception:
                device_id = None
        if not device_id:
            device_id = "unknown_device"
        # Clean device_id and app_package for filesystem compatibility
        device_id = re.sub(r"[^\w\-.]", "_", device_id)
        app_package = self.APP_PACKAGE or "unknown_package"
        app_package = app_package.replace(".", "_")
        # Generate timestamp in DD-MM-YY format
        timestamp = datetime.now().strftime("%d-%m-%y_%H-%M")
        return f"{device_id}_{app_package}_{timestamp}"

    def _update_attribute(
        self,
        key: str,
        new_value: Any,
        source: str,
        perform_type_conversion: bool = True,
    ):
        if not hasattr(self, key):
            return False

        old_value = getattr(self, key)
        converted_value = new_value

        if perform_type_conversion:
            type_hints = get_type_hints(Config)
            target_type_hinted = type_hints.get(key)

            if target_type_hinted is not None:
                origin_type = getattr(target_type_hinted, "__origin__", None)
                args_type = getattr(target_type_hinted, "__args__", tuple())
                actual_target_type = None

                if origin_type is Union:
                    non_none_args = [t for t in args_type if t is not type(None)]
                    if len(non_none_args) == 1:
                        actual_target_type = non_none_args[0]
                elif origin_type is list and len(args_type) == 1:
                    actual_target_type = list
                elif origin_type is dict and len(args_type) == 2:
                    actual_target_type = dict
                elif origin_type is None:
                    actual_target_type = target_type_hinted

                if actual_target_type and not isinstance(new_value, actual_target_type):
                    try:
                        if actual_target_type == bool:
                            converted_value = str(new_value).lower() in [
                                "true",
                                "1",
                                "yes",
                                "on",
                            ]
                        elif actual_target_type == int:
                            converted_value = int(new_value)
                        elif actual_target_type == float:
                            converted_value = float(new_value)
                        elif actual_target_type == list and isinstance(new_value, str):
                            converted_value = [
                                item.strip()
                                for item in new_value.split("\n")
                                if item.strip()
                            ]
                    except (ValueError, TypeError) as e:
                        logging.warning(
                            f"Type conversion error for '{key}' from {source} (value: '{new_value}', type: {type(new_value)}). Expected {actual_target_type}. Using original value. Error: {e}"
                        )
                        converted_value = old_value

        if old_value != converted_value:
            setattr(self, key, converted_value)
            logging.debug(
                f"Config changed by {source}: {key} = {converted_value} (was: {old_value})"
            )
        return True

    def load_user_config(self, path: Optional[str] = None):
        file_path = path or self.USER_CONFIG_FILE_PATH
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                logging.debug(f"Loading user configuration from: {file_path}")
                for key, value in user_data.items():
                    # Handle the OUTPUT_DATA_DIR specifically if it's in user_config
                    # to update the template before resolving all paths.
                    if key == "OUTPUT_DATA_DIR":
                        self._OUTPUT_DATA_DIR_TEMPLATE = value
                    else:
                        self._update_attribute(
                            key,
                            value,
                            source=f"user_config '{os.path.basename(file_path)}'",
                        )
            except json.JSONDecodeError as e:
                logging.error(
                    f"Error parsing user config {file_path}: Invalid JSON. {e}",
                    exc_info=True,
                )
            except Exception as e:
                logging.warning(
                    f"Failed to load or apply user config from {file_path}: {e}",
                    exc_info=True,
                )
        else:
            logging.debug(
                f"User configuration file ({file_path}) not found. Using defaults and environment variables."
            )
        self._resolve_all_paths(create_session_dirs=False)

        # Adjust XML limits based on AI provider
        self._adjust_xml_limits_for_provider()

        # Adjust image context based on AI provider capabilities
        self._adjust_image_context_for_provider()

    def _get_provider_capabilities(self, provider: str) -> Dict[str, Any]:
        """Get capabilities for a specific AI provider."""
        provider = provider.lower()
        # Access the module-level AI_PROVIDER_CAPABILITIES
        capabilities = AI_PROVIDER_CAPABILITIES.get(
            provider, AI_PROVIDER_CAPABILITIES.get("gemini", {})
        )
        return capabilities

    def _adjust_xml_limits_for_provider(self):
        """Automatically adjust XML_SNIPPET_MAX_LEN based on AI provider capabilities."""
        provider = getattr(self, "AI_PROVIDER", "gemini").lower()
        capabilities = self._get_provider_capabilities(provider)

        recommended_limit = capabilities.get("xml_max_len", 500000)
        current_limit = getattr(self, "XML_SNIPPET_MAX_LEN", 500000)

        # Only adjust if current limit is higher than recommended for this provider
        if current_limit > recommended_limit:
            logging.debug(
                f"Adjusting XML_SNIPPET_MAX_LEN from {current_limit} to {recommended_limit} for {provider} provider"
            )
            self.XML_SNIPPET_MAX_LEN = recommended_limit

            # Update user config if it exists
            if os.path.exists(self.USER_CONFIG_FILE_PATH):
                try:
                    with open(self.USER_CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                        user_data = json.load(f)

                    user_data["XML_SNIPPET_MAX_LEN"] = recommended_limit

                    with open(self.USER_CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                        json.dump(user_data, f, indent=4, ensure_ascii=False)

                    logging.debug(
                        f"Updated XML_SNIPPET_MAX_LEN in user config to {recommended_limit}"
                    )
                except Exception as e:
                    logging.warning(
                        f"Failed to update XML_SNIPPET_MAX_LEN in user config: {e}"
                    )
        elif current_limit < recommended_limit:
            logging.debug(
                f"XML_SNIPPET_MAX_LEN ({current_limit}) is below recommended limit for {provider} ({recommended_limit}). Consider increasing for better AI context."
            )

    def _adjust_image_context_for_provider(self):
        """Automatically adjust ENABLE_IMAGE_CONTEXT based on AI provider capabilities."""
        provider = getattr(self, "AI_PROVIDER", "gemini").lower()
        capabilities = self._get_provider_capabilities(provider)

        auto_disable = capabilities.get("auto_disable_image_context", False)

        if auto_disable:
            current_image_context = getattr(self, "ENABLE_IMAGE_CONTEXT", True)
            if current_image_context:
                logging.debug(
                    f"Disabling ENABLE_IMAGE_CONTEXT for {provider} provider due to payload size limits"
                )
                self.ENABLE_IMAGE_CONTEXT = False

                # Update user config if it exists
                if os.path.exists(self.USER_CONFIG_FILE_PATH):
                    try:
                        with open(
                            self.USER_CONFIG_FILE_PATH, "r", encoding="utf-8"
                        ) as f:
                            user_data = json.load(f)

                        user_data["ENABLE_IMAGE_CONTEXT"] = False

                        with open(
                            self.USER_CONFIG_FILE_PATH, "w", encoding="utf-8"
                        ) as f:
                            json.dump(user_data, f, indent=4, ensure_ascii=False)

                        logging.debug(
                            f"Updated ENABLE_IMAGE_CONTEXT to False in user config for {provider} compatibility"
                        )
                    except Exception as e:
                        logging.warning(
                            f"Failed to update ENABLE_IMAGE_CONTEXT in user config: {e}"
                        )
        else:
            # For providers that support images, auto-enable image context when a vision-capable model is selected.
            image_supported = bool(capabilities.get("image_supported", False))
            if image_supported:
                model_alias = str(getattr(self, "DEFAULT_MODEL_TYPE", "")).strip()
                vision_ok = False
                try:
                    if provider == "gemini":
                        # Gemini models are multimodal by default in this configuration
                        vision_ok = True
                    elif provider == "ollama":
                        model_info = self.OLLAMA_MODELS.get(model_alias)
                        if model_info and model_info.get("vision_supported"):
                            vision_ok = True
                        else:
                            # Heuristic based on common vision model naming
                            name = (
                                model_info.get("name", "")
                                if model_info
                                else model_alias
                            ).lower()
                            tokens = [
                                "vision",
                                "llava",
                                "bakllava",
                                "vl",
                                "minicpm",
                                "moondream",
                                "qwen2.5vl",
                                "granite3.2-vision",
                                "llama3.2",
                                "llama4",
                                "gemma3",
                            ]
                            if any(t in name for t in tokens):
                                vision_ok = True
                    elif provider == "openrouter":
                        model_info = self.OPENROUTER_MODELS.get(model_alias)
                        name = (
                            model_info.get("name", "") if model_info else model_alias
                        ).lower()
                        tokens = [
                            "vision",
                            "vl",
                            "llava",
                            "bakllava",
                            "multimodal",
                            "omni",
                            "gpt-4o",
                            "image",
                        ]
                        if any(t in name for t in tokens) or "openrouter/auto" in name:
                            vision_ok = True
                except Exception as e:
                    logging.debug(f"Vision capability check error: {e}")

                if vision_ok and not getattr(self, "ENABLE_IMAGE_CONTEXT", False):
                    self.ENABLE_IMAGE_CONTEXT = True
                    # Persist the change in user config for transparency
                    if os.path.exists(self.USER_CONFIG_FILE_PATH):
                        try:
                            with open(
                                self.USER_CONFIG_FILE_PATH, "r", encoding="utf-8"
                            ) as f:
                                user_data = json.load(f)
                            user_data["ENABLE_IMAGE_CONTEXT"] = True
                            with open(
                                self.USER_CONFIG_FILE_PATH, "w", encoding="utf-8"
                            ) as f:
                                json.dump(user_data, f, indent=4, ensure_ascii=False)
                            logging.debug(
                                f"Auto-enabled ENABLE_IMAGE_CONTEXT for provider '{provider}' and model '{model_alias}'."
                            )
                        except Exception as e:
                            logging.warning(
                                f"Failed to persist ENABLE_IMAGE_CONTEXT=True: {e}"
                            )
                elif not vision_ok:
                    logging.debug(
                        f"Selected provider/model ('{provider}', '{model_alias}') may not support images; leaving ENABLE_IMAGE_CONTEXT as-is."
                    )

    def _get_user_savable_config(self) -> Dict[str, Any]:
        savable_keys = [
            "APP_PACKAGE",
            "APP_ACTIVITY",
            "ALLOWED_EXTERNAL_PACKAGES",
            "LOG_LEVEL",
            "DB_CONNECT_TIMEOUT",
            "DB_BUSY_TIMEOUT",
            "WAIT_AFTER_ACTION",
            "STABILITY_WAIT",
            "APP_LAUNCH_WAIT_TIME",
            "NEW_COMMAND_TIMEOUT",
            "APPIUM_IMPLICIT_WAIT",
            "APPIUM_SERVER_URL",
            "TARGET_DEVICE_UDID",
            "USE_COORDINATE_FALLBACK",
            "AI_PROVIDER",
            "DEFAULT_MODEL_TYPE",
            "USE_CHAT_MEMORY",
            "MAX_CHAT_HISTORY",
            "OPENROUTER_REFRESH_BTN",
            "OPENROUTER_SHOW_FREE_ONLY",
            "OPENROUTER_NON_FREE_WARNING",
            "ENABLE_IMAGE_CONTEXT",
            "XML_SNIPPET_MAX_LEN",
            "MAX_APPS_TO_SEND_TO_AI",
            "USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY",
            "AI_SAFETY_SETTINGS",
            "CRAWL_MODE",
            "MAX_CRAWL_STEPS",
            "MAX_CRAWL_DURATION_SECONDS",
            "CONTINUE_EXISTING_RUN",
            "VISUAL_SIMILARITY_THRESHOLD",
            "THIRD_PARTY_APPS_ONLY",
            "MAX_CONSECUTIVE_AI_FAILURES",
            "MAX_CONSECUTIVE_MAP_FAILURES",
            "MAX_CONSECUTIVE_EXEC_FAILURES",
            "ENABLE_TRAFFIC_CAPTURE",
            "PCAPDROID_PACKAGE",
            "DEVICE_PCAP_DIR",
            "CLEANUP_DEVICE_PCAP_FILE",
            "ENABLE_VIDEO_RECORDING",
            "CURRENT_HEALTH_APP_LIST_FILE",
            "LAST_SELECTED_APP",
            "UI_MODE",
            "MOBSF_API_URL",
            "ENABLE_MOBSF_ANALYSIS",
            "FOCUS_AREAS",  # Add focus areas to savable config
            # Additional optimization flags
            "FOCUS_MAX_ACTIVE",
            "MAX_SAME_ACTION_REPEAT",
            "DISABLE_EXPENSIVE_XPATH",
            "ELEMENT_STRATEGY_MAX_ATTEMPTS",
            # Safety tap and overlay handling
            "SAFE_TAP_MARGIN_RATIO",
            "SAFE_TAP_EDGE_HANDLING",
            "TOAST_DISMISS_WAIT_MS",
            # Pre-action behavior
            "AUTO_HIDE_KEYBOARD_BEFORE_NON_INPUT",
            # Image preprocessing knobs
            "IMAGE_MAX_WIDTH",
            "IMAGE_FORMAT",
            "IMAGE_QUALITY",
            "IMAGE_CROP_BARS",
            "IMAGE_CROP_TOP_PERCENT",
            "IMAGE_CROP_BOTTOM_PERCENT",
            # Save the template for OUTPUT_DATA_DIR so user can change base output loc
            # The actual key in user_config.json will be "OUTPUT_DATA_DIR"
        ]
        config_to_save = {}
        for key in savable_keys:
            if hasattr(self, key):
                value = getattr(self, key)

                # Make paths relative when saving to config if they're within the app directory
                if (
                    key == "CURRENT_HEALTH_APP_LIST_FILE"
                    and value
                    and os.path.isabs(value)
                ):
                    try:
                        # Try to make it relative to the base directory
                        rel_path = os.path.relpath(value, self.BASE_DIR)
                        # Only make relative if it's within the app directory hierarchy
                        if not rel_path.startswith(".."):
                            value = rel_path
                    except ValueError:
                        # Different drives, can't make relative
                        pass

                config_to_save[key] = value

        # Explicitly add the _OUTPUT_DATA_DIR_TEMPLATE value under the key "OUTPUT_DATA_DIR"
        config_to_save["OUTPUT_DATA_DIR"] = self._OUTPUT_DATA_DIR_TEMPLATE
        return config_to_save

    def save_user_config(self, path: Optional[str] = None) -> None:
        file_path = path or self.USER_CONFIG_FILE_PATH
        data_to_save = self._get_user_savable_config()
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            logging.debug(f"User configuration saved to: {file_path}")
        except Exception as e:
            logging.error(
                f"Failed to save user configuration to {file_path}: {e}", exc_info=True
            )

    def _resolve_path_template(
        self,
        template: Optional[str],
        session_dir: str,
        app_package_for_path: Optional[str],
    ) -> str:
        if template is None:
            return ""

        # Use a placeholder if app_package is None to avoid errors in path formatting,
        # though ideally app_package should be set before paths are critically needed.
        package_segment = (
            app_package_for_path if app_package_for_path else "unknown_package"
        )

        resolved_path = template
        # Replace known placeholders
        if "{session_dir}" in resolved_path:
            resolved_path = resolved_path.replace("{session_dir}", session_dir)
        if "{output_data_dir}" in resolved_path:
            # Ensure OUTPUT_DATA_DIR is resolved before use
            output_dir = getattr(self, "OUTPUT_DATA_DIR", None)
            if not output_dir:
                # Resolve OUTPUT_DATA_DIR based on template if not already set
                if not os.path.isabs(self._OUTPUT_DATA_DIR_TEMPLATE):
                    output_dir = os.path.abspath(
                        os.path.join(self.BASE_DIR, self._OUTPUT_DATA_DIR_TEMPLATE)
                    )
                else:
                    output_dir = os.path.abspath(self._OUTPUT_DATA_DIR_TEMPLATE)
                self.OUTPUT_DATA_DIR = output_dir
            resolved_path = resolved_path.replace("{output_data_dir}", output_dir)
        if "{package}" in resolved_path:
            resolved_path = resolved_path.replace("{package}", package_segment)
        if "{device_id}" in resolved_path:
            device_id = getattr(self, "TARGET_DEVICE_UDID", None) or "unknown_device"
            resolved_path = resolved_path.replace("{device_id}", device_id)

        if not os.path.isabs(resolved_path):
            return os.path.abspath(os.path.join(self.BASE_DIR, resolved_path))
        return os.path.abspath(resolved_path)

    def _resolve_all_paths(self, create_session_dirs: bool = True):
        # 1. Resolve the main OUTPUT_DATA_DIR first
        if not os.path.isabs(self._OUTPUT_DATA_DIR_TEMPLATE):
            self.OUTPUT_DATA_DIR = os.path.abspath(
                os.path.join(self.BASE_DIR, self._OUTPUT_DATA_DIR_TEMPLATE)
            )
        else:
            self.OUTPUT_DATA_DIR = os.path.abspath(self._OUTPUT_DATA_DIR_TEMPLATE)
        if create_session_dirs:
            os.makedirs(self.OUTPUT_DATA_DIR, exist_ok=True)

        # 2. Generate unique session directory name
        session_dir_name = self._generate_session_dir_name()
        self.SESSION_DIR = os.path.join(self.OUTPUT_DATA_DIR, session_dir_name)
        if create_session_dirs:
            os.makedirs(self.SESSION_DIR, exist_ok=True)

        current_app_pkg = getattr(self, "APP_PACKAGE", None)  # Get current app_package

        # 3. Resolve all paths using the session directory
        self.APP_INFO_OUTPUT_DIR = self._resolve_path_template(
            self._APP_INFO_OUTPUT_DIR_TEMPLATE, self.SESSION_DIR, current_app_pkg
        )
        self.SCREENSHOTS_DIR = self._resolve_path_template(
            self._SCREENSHOTS_DIR_TEMPLATE, self.SESSION_DIR, current_app_pkg
        )
        self.ANNOTATED_SCREENSHOTS_DIR = self._resolve_path_template(
            self._ANNOTATED_SCREENSHOTS_DIR_TEMPLATE, self.SESSION_DIR, current_app_pkg
        )
        self.TRAFFIC_CAPTURE_OUTPUT_DIR = self._resolve_path_template(
            self._TRAFFIC_CAPTURE_OUTPUT_DIR_TEMPLATE, self.SESSION_DIR, current_app_pkg
        )
        self.DB_NAME = self._resolve_path_template(
            self._DB_NAME_TEMPLATE, self.SESSION_DIR, current_app_pkg
        )
        self.LOG_DIR = self._resolve_path_template(
            self._LOG_DIR_TEMPLATE, self.SESSION_DIR, current_app_pkg
        )
        self.MOBSF_SCAN_DIR = self._resolve_path_template(
            self._MOBSF_SCAN_DIR_TEMPLATE, self.SESSION_DIR, current_app_pkg
        )
        self.EXTRACTED_APK_DIR = self._resolve_path_template(
            self._EXTRACTED_APK_DIR_TEMPLATE, self.SESSION_DIR, current_app_pkg
        )
        self.PDF_REPORT_DIR = self._resolve_path_template(
            self._PDF_REPORT_DIR_TEMPLATE, self.SESSION_DIR, current_app_pkg
        )
        self.VIDEO_RECORDING_DIR = self._resolve_path_template(
            self._VIDEO_RECORDING_DIR_TEMPLATE, self.SESSION_DIR, current_app_pkg
        )

        # 4. Ensure all directories are created
        dirs_to_create = [
            self.APP_INFO_OUTPUT_DIR,
            self.SCREENSHOTS_DIR,
            self.ANNOTATED_SCREENSHOTS_DIR,
            self.TRAFFIC_CAPTURE_OUTPUT_DIR,
            self.LOG_DIR,
            self.MOBSF_SCAN_DIR,
            self.EXTRACTED_APK_DIR,
            self.PDF_REPORT_DIR,
            self.VIDEO_RECORDING_DIR,
        ]
        if self.DB_NAME:  # DB_NAME is a file path, so create its parent
            dirs_to_create.append(os.path.dirname(self.DB_NAME))

        if create_session_dirs:
            for dir_path in filter(None, dirs_to_create):
                if dir_path:  # Ensure dir_path is not empty
                    os.makedirs(dir_path, exist_ok=True)

        if self.PCAPDROID_PACKAGE:
            self.PCAPDROID_ACTIVITY = (
                f"{self.PCAPDROID_PACKAGE}/.activities.CaptureCtrl"
            )

        logging.debug("Resolved dynamic configuration paths.")
        logging.debug(f"  OUTPUT_DATA_DIR: {self.OUTPUT_DATA_DIR}")
        logging.debug(f"  SESSION_DIR: {self.SESSION_DIR}")
        logging.debug(f"  APP_INFO_OUTPUT_DIR: {self.APP_INFO_OUTPUT_DIR}")
        logging.debug(f"  SCREENSHOTS_DIR: {self.SCREENSHOTS_DIR}")
        logging.debug(f"  ANNOTATED_SCREENSHOTS_DIR: {self.ANNOTATED_SCREENSHOTS_DIR}")
        logging.debug(f"  DB_NAME: {self.DB_NAME}")
        logging.debug(
            f"  TRAFFIC_CAPTURE_OUTPUT_DIR: {self.TRAFFIC_CAPTURE_OUTPUT_DIR}"
        )
        logging.debug(f"  LOG_DIR: {self.LOG_DIR}")
        logging.debug(f"  MOBSF_SCAN_DIR: {self.MOBSF_SCAN_DIR}")
        logging.debug(f"  EXTRACTED_APK_DIR: {self.EXTRACTED_APK_DIR}")
        logging.debug(f"  PDF_REPORT_DIR: {self.PDF_REPORT_DIR}")

    def update_setting_and_save(
        self, key: str, value: Any, sync_callback: Optional[Callable[[], None]] = None
    ):
        """Public method to update a setting and persist to user_config.json"""
        # Special handling if OUTPUT_DATA_DIR is being set directly
        # to update the underlying template.
        is_output_dir_template_update = False
        if key == "OUTPUT_DATA_DIR":
            # We assume if user sets OUTPUT_DATA_DIR, they mean to change the template
            if self._OUTPUT_DATA_DIR_TEMPLATE != value:
                self._OUTPUT_DATA_DIR_TEMPLATE = value
                is_output_dir_template_update = True

        # Sanitize placeholder for device UDID so it is not persisted as a real value
        if key == "TARGET_DEVICE_UDID" and isinstance(value, str):
            if value.strip().lower() in ("no devices found", ""):
                value = None

        attribute_updated = self._update_attribute(
            key, value, source="gui/dynamic_update"
        )

        if attribute_updated or is_output_dir_template_update:
            # Re-resolve paths if APP_PACKAGE changed, or if OUTPUT_DATA_DIR template changed
            if key == "APP_PACKAGE" or is_output_dir_template_update:
                self._resolve_all_paths(create_session_dirs=False)

            self.save_user_config()

            # Call synchronization callback if provided
            if sync_callback:
                try:
                    sync_callback()
                except Exception as e:
                    logging.warning(f"Failed to execute synchronization callback: {e}")

            if key in ["LOG_LEVEL", "LOG_FILE_NAME"]:  # LOG_DIR might also be relevant
                logging.warning(
                    f"Logging setting '{key}' changed. Logger re-initialization might be needed by the application."
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
SESSION_DIR = "{output_data_dir}/{device_id}_{app_package}_{timestamp}"
APP_INFO_OUTPUT_DIR = "{output_data_dir}/app_info/{device_id}"
SCREENSHOTS_DIR = "{session_dir}/screenshots"
ANNOTATED_SCREENSHOTS_DIR = "{session_dir}/annotated_screenshots"
TRAFFIC_CAPTURE_OUTPUT_DIR = "{session_dir}/traffic_captures"
LOG_DIR = "{session_dir}/logs"

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
NEW_COMMAND_TIMEOUT = 300
APPIUM_IMPLICIT_WAIT = 1

APPIUM_SERVER_URL = "http://127.0.0.1:4723"
TARGET_DEVICE_UDID = None
USE_COORDINATE_FALLBACK = True

AI_PROVIDER = "gemini"  # 'gemini' or 'deepseek' - Gemini has generous free tier
DEFAULT_MODEL_TYPE = "flash-latest-fast"
USE_CHAT_MEMORY = False
MAX_CHAT_HISTORY = 10
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
        "name": "gemini-2.5-flash-preview-05-20",
        "description": "Latest Flash model (2.5) with settings optimized for faster responses.",
        "generation_config": {
            "temperature": 0.3,
            "top_p": 0.8,
            "top_k": 20,
            "max_output_tokens": 2048,
        },
        "online": True,
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
    # Future providers can be easily added here, e.g.:
    # 'claude': {
    #     'xml_max_len': 200000,
    #     'image_supported': True,
    #     'image_max_width': 600,
    #     'image_quality': 70,
    #     'image_format': 'JPEG',
    #     'payload_max_size_kb': 500,
    #     'auto_disable_image_context': False,
    #     'description': 'Anthropic Claude - Balanced capabilities',
    #     'online': True
    # },
    # 'ollama': {
    #     'xml_max_len': 100000,
    #     'image_supported': False,
    #     'image_max_width': None,
    #     'image_quality': None,
    #     'image_format': None,
    #     'payload_max_size_kb': None,
    #     'auto_disable_image_context': False,
    #     'description': 'Ollama - Local LLM provider',
    #     'online': False  # Local provider
    # }
}
OPENROUTER_MODELS = {}
OPENROUTER_REFRESH_BTN = False
OPENROUTER_SHOW_FREE_ONLY = False
