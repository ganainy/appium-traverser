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
"""Magic string constants for CLI commands.

Centralizes service names, config keys, JSON keys, and other string literals.
"""

# Service names
SERVICE_APP_SCAN = "app_scan"
SERVICE_CONFIG = "config"

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

# === Packages command group (internal keys/magic strings) ===
JSON_KEY_PACKAGES = "packages"
JSON_KEY_COUNT = "count"
INPUT_YES = "yes"
INPUT_Y = "y"