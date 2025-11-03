# === Analysis/Reporting/Database keys and paths ===
CONFIG_OUTPUT_DATA_DIR = "OUTPUT_DATA_DIR"
PROJECT_ROOT = "PROJECT_ROOT"
DATABASE_DIR = "database"
CRAWL_DB_GLOB = "*_crawl_data.db"
KEY_INDEX = "index"
KEY_APP_PACKAGE = "app_package"
KEY_DB_PATH = "db_path"
KEY_DB_FILENAME = "db_filename"
KEY_SESSION_DIR = "session_dir"
KEY_APP_PACKAGE_SAFE = "app_package_safe"
KEY_ERROR = "error"
KEY_TARGET_INFO = "target_info"
KEY_RUNS = "runs"
KEY_MESSAGE = "message"
KEY_PDF_PATH = "pdf_path"
KEY_RUN_INFO = "run_info"
KEY_METRICS = "metrics"
KEY_SUCCESS = "success"

# === Telemetry Service Keys ===
KEY_TIMESTAMP = "timestamp"
KEY_TYPE = "type"
KEY_DATA = "data"
KEY_ARGS = "args"
KEY_DURATION_SECONDS = "duration_seconds"
KEY_ERROR_TYPE = "error_type"
KEY_ERROR_MESSAGE = "error_message"
KEY_CONTEXT = "context"
KEY_START_TIME = "start_time"
KEY_END_TIME = "end_time"
KEY_TOTAL_EVENTS = "total_events"
KEY_COMMANDS_EXECUTED = "commands_executed"
KEY_ERRORS_ENCOUNTERED = "errors_encountered"
KEY_SUCCESS_RATE = "success_rate"

# Directory and file names
DIR_REPORTS = "reports"
DIR_SCREENSHOTS = "screenshots"
DIR_ANNOTATED_SCREENSHOTS = "annotated_screenshots"
DIR_TOOLS = "tools"
FILE_ANALYSIS_PDF = "analysis.pdf"

# Command line arguments
ARG_DB_PATH = "--db-path"
ARG_SCREENS_DIR = "--screens-dir"
ARG_OUT_DIR = "--out-dir"
# === AI provider keys and valid providers ===
AI_PROVIDER_GEMINI = "gemini"
AI_PROVIDER_OPENROUTER = "openrouter"
AI_PROVIDER_OLLAMA = "ollama"
VALID_AI_PROVIDERS = (AI_PROVIDER_GEMINI, AI_PROVIDER_OPENROUTER, AI_PROVIDER_OLLAMA)
# === Service check command group (internal keys/magic strings) ===
SERVICE_TELEMETRY = "telemetry"
SERVICE_APPIUM = "Appium Server"
SERVICE_MCP = "MCP Server"
SERVICE_MOBSF = "MobSF Server"
SERVICE_OLLAMA = "Ollama Service"
SERVICE_API_KEYS = "API Keys"
SERVICE_TARGET_APP = "Target App"

CONFIG_AI_PROVIDER = "AI_PROVIDER"
CONFIG_GEMINI_API_KEY = "GEMINI_API_KEY"
CONFIG_OPENROUTER_API_KEY = "OPENROUTER_API_KEY"
CONFIG_OLLAMA_BASE_URL = "OLLAMA_BASE_URL"
CONFIG_ENABLE_TRAFFIC_CAPTURE = "ENABLE_TRAFFIC_CAPTURE"
CONFIG_PCAPDROID_API_KEY = "PCAPDROID_API_KEY"
CONFIG_ENABLE_MOBSF_ANALYSIS = "ENABLE_MOBSF_ANALYSIS"
CONFIG_MOBSF_API_KEY = "MOBSF_API_KEY"
CONFIG_APPIUM_SERVER_URL = "APPIUM_SERVER_URL"
CONFIG_MCP_SERVER_URL = "MCP_SERVER_URL"
CONFIG_MOBSF_API_URL = "MOBSF_API_URL"
CONFIG_APP_PACKAGE = "APP_PACKAGE"

AI_PROVIDER_GEMINI = "gemini"
AI_PROVIDER_OPENROUTER = "openrouter"
AI_PROVIDER_OLLAMA = "ollama"
VALID_AI_PROVIDERS = ("gemini", "openrouter", "ollama")

APPIUM_STATUS_PATH = "/status"
MCP_READY_PATH = "/ready"
MCP_HEALTH_PATH = "/health"
MOBSF_STATUS_PATH = "/server_status"
OLLAMA_TAGS_PATH = "/api/tags"

STATUS_KEY_STATUS = "status"
STATUS_KEY_MESSAGE = "message"
STATUS_RUNNING = "running"
STATUS_WARNING = "warning"
STATUS_ERROR = "error"

JSON_KEY_READY = "ready"
JSON_KEY_VALUE = "value"
JSON_KEY_UPTIME_MS = "uptimeMs"
JSON_KEY_REGISTERED_TOOLS = "registeredTools"
JSON_KEY_ACTIVE_INVOCATIONS = "activeInvocations"

HTTP_CODE_OK = 200
HTTP_CODE_SERVICE_UNAVAILABLE = 503
# === OpenRouter service and keys ===
OPENROUTER_SERVICE = "openrouter"
HANDLER = "handler"

# Model dictionary keys
MODEL_ID = "id"
MODEL_NAME = "name"
MODEL_PRICING = "pricing"
# === Focus command group ===
FOCUS_SERVICE = "focus"
TELEMETRY_SERVICE = "telemetry"
# === Device command group ===
DEVICE_SERVICE = "device"
TELEMETRY_SERVICE = "telemetry"
# === Crawler command group ===
CRAWLER_SERVICE = "crawler"
ANALYSIS_SERVICE = "analysis"

# Status dictionary keys
PROCESS_KEY = "process"
STATE_KEY = "state"
TARGET_APP_KEY = "target_app"
OUTPUT_DIR_KEY = "output_dir"

# Crawler status dictionary keys
PROCESS_STATUS_KEY = "process_status"
PROCESS_ID_KEY = "process_id"
"""Magic string constants for CLI commands.

Centralizes service names, config keys, JSON keys, and other string literals.
"""

# Service names
SERVICE_APP_SCAN = "app_scan"
SERVICE_CONFIG = "config"
SERVICE_ANNOTATION = "annotation"

# Cache key types
CACHE_KEY_ALL = "all"
CACHE_KEY_HEALTH = "health"

# JSON keys in cache files
JSON_KEY_ALL_APPS = "all_apps"
JSON_KEY_HEALTH_APPS = "health_apps"

# App data keys
APP_NAME = "app_name"
PACKAGE_NAME = "package_name"
ACTIVITY_NAME = "activity_name"

# Config keys
CONFIG_LAST_SELECTED_APP = "LAST_SELECTED_APP"
CONFIG_APP_PACKAGE = "APP_PACKAGE"
CONFIG_APP_ACTIVITY = "APP_ACTIVITY"

# Command names
CMD_SCAN_ALL = "scan-all"
CMD_SCAN_HEALTH = "scan-health"
CMD_LIST_ALL = "list-all"
CMD_LIST_HEALTH = "list-health"
CMD_SELECT = "select"
CMD_SHOW_SELECTED = "show-selected"

# Argument names
ARG_FORCE_RESCAN = "--force-rescan"
ARG_APP_IDENTIFIER = "app_identifier"
ARG_METAVAR_ID_OR_NAME = "ID_OR_NAME"

# Default values
DEFAULT_UNKNOWN = "Unknown"

# === App Scan Service ===
# Service names
SERVICE_CONFIG = "config"

# Config keys
CONFIG_APP_INFO_OUTPUT_DIR = "APP_INFO_OUTPUT_DIR"
CONFIG_CURRENT_HEALTH_APP_LIST_FILE = "CURRENT_HEALTH_APP_LIST_FILE"

# Cache key types
CACHE_KEY_ALL = "all"
CACHE_KEY_HEALTH = "health"
CACHE_KEY_HEALTH_FILTERED = "health_filtered"

# JSON keys in cache files
JSON_KEY_ALL_APPS = "all_apps"
JSON_KEY_HEALTH_APPS = "health_apps"

# App data keys
APP_NAME = "app_name"
PACKAGE_NAME = "package_name"
ACTIVITY_NAME = "activity_name"

# File patterns
FILE_PATTERN_DEVICE_APP_INFO = "device_*_app_info.json"

# === Packages command group (internal keys/magic strings) ===
JSON_KEY_PACKAGES = "packages"
JSON_KEY_COUNT = "count"
INPUT_YES = "yes"
INPUT_Y = "y"

# === ADB Device Management ===
ADB_COMMAND = "adb"
ADB_DEVICES_COMMAND = "devices"
ADB_DEVICE_STATUS_SEPARATOR = "\tdevice"
CONFIG_DEVICE_UDID = "DEVICE_UDID"

# === Focus Area Dictionary Keys ===
FOCUS_AREA_ID = "id"
FOCUS_AREA_NAME = "name"
FOCUS_AREA_TITLE = "title"
FOCUS_AREA_DESCRIPTION = "description"
FOCUS_AREA_PRIORITY = "priority"
FOCUS_AREA_ENABLED = "enabled"

# === OpenRouter Service Constants ===
# Config keys
CONFIG_OPENROUTER_SHOW_FREE_ONLY = "OPENROUTER_SHOW_FREE_ONLY"
CONFIG_OPENROUTER_NON_FREE_WARNING = "OPENROUTER_NON_FREE_WARNING"
CONFIG_DEFAULT_MODEL_TYPE = "DEFAULT_MODEL_TYPE"
CONFIG_ENABLE_IMAGE_CONTEXT = "ENABLE_IMAGE_CONTEXT"
CONFIG_NO_MODEL_SELECTED = "No model selected"

# Model data keys
MODEL_ID = "id"
MODEL_NAME = "name"
MODEL_DESCRIPTION = "description"
MODEL_CONTEXT_LENGTH = "context_length"
MODEL_PRICING = "pricing"
MODEL_PROMPT_PRICE = "prompt"
MODEL_COMPLETION_PRICE = "completion"
MODEL_IMAGE_PRICE = "image"
MODEL_ARCHITECTURE = "architecture"
MODEL_INPUT_MODALITIES = "input_modalities"
MODEL_OUTPUT_MODALITIES = "output_modalities"
MODEL_SUPPORTED_PARAMETERS = "supported_parameters"
MODEL_SUPPORTS_IMAGE = "supports_image"
MODEL_TOP_PROVIDER = "top_provider"
MODEL_PROVIDER_NAME = "provider_name"
MODEL_MODEL_FORMAT = "model_format"

# Dictionary keys for data structures
KEY_SUCCESS = "success"
KEY_ERROR = "error"
KEY_MODEL = "model"
KEY_IS_FREE = "is_free"
KEY_SHOW_WARNING = "show_warning"
KEY_MODEL_IDENTIFIER = "model_identifier"
KEY_SUPPORTS_IMAGE = "supports_image"
KEY_CURRENT_SETTING = "current_setting"
KEY_ENABLED = "enabled"
KEY_ACTION = "action"
KEY_HEURISTIC_SUPPORTS_IMAGE = "heuristic_supports_image"
KEY_CURRENT_IMAGE_CONTEXT = "current_image_context"

# String literals
PROVIDER_OPENROUTER = "openrouter"

# Subprocess creation flags
SUBPROCESS_CREATION_FLAG = "creationflags"