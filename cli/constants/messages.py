# === Switch provider command (user-facing strings) ===
SWITCH_PROVIDER_NAME = "switch-provider"
SWITCH_PROVIDER_DESC = "Switch the AI provider ({providers}) and reload config live."
SWITCH_PROVIDER_ARG_HELP = "AI provider to use ({providers})"
SWITCH_PROVIDER_MODEL_ARG_HELP = "Model name/alias to use"
SWITCH_PROVIDER_SUCCESS = "Switched AI provider to {provider}"
SWITCH_PROVIDER_FAIL = "Failed to switch AI provider to {provider}"
# === Service check command group (user-facing strings) ===
PRECHECK_NAME = "precheck-services"
PRECHECK_DESC = "Run pre-crawl validation checks for services and configuration"
PRECHECK_SUCCESS = "All pre-crawl checks passed!"
PRECHECK_WARNING = "Pre-crawl validation completed with warnings"
PRECHECK_ERROR = "Pre-crawl validation failed"
PRECHECK_RESULT_SUCCESS = "All checks passed"
PRECHECK_RESULT_WARNING = "Checks passed with warnings"
PRECHECK_RESULT_ERROR = "Some checks failed"
PRECHECK_STATUS_TABLE_HEADER = "Service Status"
PRECHECK_STATUS_RUNNING = "running"
PRECHECK_STATUS_WARNING = "warning"
PRECHECK_STATUS_ERROR = "error"
PRECHECK_STATUS_MESSAGE_OK = "All required API keys configured"
PRECHECK_STATUS_MESSAGE_NO_APP = "No app selected"
PRECHECK_STATUS_MESSAGE_SELECTED = "Selected: {app_package}"
PRECHECK_STATUS_MESSAGE_REACHABLE = "Reachable at {url}"
PRECHECK_STATUS_MESSAGE_NOT_READY = "Not ready at {url}"
PRECHECK_STATUS_MESSAGE_HTTP = "HTTP {code} at {url}"
PRECHECK_STATUS_MESSAGE_CONN_FAIL = "Connection failed: {error}"
PRECHECK_STATUS_MESSAGE_READY = "Ready at {url} (tools: {tools}, active: {active}, uptime: {uptime}ms)"
PRECHECK_STATUS_MESSAGE_NOT_READY_UNAVAILABLE = "Not ready at {url} (service unavailable)"
PRECHECK_STATUS_MESSAGE_HEALTH_ALIVE = "Alive but not ready at {url} (uptime: {uptime}ms)"
PRECHECK_STATUS_MESSAGE_HEALTH_FAIL = "Health check failed: {error}"
PRECHECK_STATUS_MESSAGE_MCP_FAIL = "MCP server check failed: {error}"
PRECHECK_STATUS_MESSAGE_CLI_ACCESSIBLE = "CLI accessible"
PRECHECK_STATUS_MESSAGE_CLI_NOT_ACCESSIBLE = "CLI not accessible"
PRECHECK_STATUS_MESSAGE_NOT_ACCESSIBLE = "Not accessible at {url}"
PRECHECK_STATUS_MESSAGE_API_REACHABLE = "API reachable at {url}"
PRECHECK_STATUS_MESSAGE_ISSUE = "{msg}"
PRECHECK_STATUS_MESSAGE_WARN = "{msg}"
PRECHECK_STATUS_MESSAGE_MISSING_KEY = "{key} not set (check {env} in .env)"
PRECHECK_STATUS_MESSAGE_OLLAMA_DEFAULT = "Ollama base URL not set (using default localhost:11434)"
# === Packages command group (user-facing strings) ===
LIST_PACKAGES_NAME = "list-packages"
LIST_PACKAGES_DESC = "List all allowed external packages"
LIST_PACKAGES_JSON_HELP = "Output as JSON"
LIST_PACKAGES_NO_PKGS = "No allowed external packages configured."
LIST_PACKAGES_HEADER = "Allowed external packages ({count}):"
LIST_PACKAGES_ITEM = "  {index}. {package}"
LIST_PACKAGES_RESULT = "Listed {count} allowed packages"

ADD_PACKAGE_NAME = "add-package"
ADD_PACKAGE_DESC = "Add a package to allowed external packages"
ADD_PACKAGE_ARG_HELP = "Package name to add (e.g., com.example.app)"
ADD_PACKAGE_SUCCESS = "Added package: {package_name}"
ADD_PACKAGE_FAIL = "Failed to add package: {package_name}"
ADD_PACKAGE_RESULT = "Package added: {package_name}"
ADD_PACKAGE_RESULT_FAIL = "Failed to add package: {package_name}"

REMOVE_PACKAGE_NAME = "remove-package"
REMOVE_PACKAGE_DESC = "Remove a package from allowed external packages"
REMOVE_PACKAGE_ARG_HELP = "Package name to remove"
REMOVE_PACKAGE_SUCCESS = "Removed package: {package_name}"
REMOVE_PACKAGE_FAIL = "Failed to remove package: {package_name}"
REMOVE_PACKAGE_RESULT = "Package removed: {package_name}"
REMOVE_PACKAGE_RESULT_FAIL = "Failed to remove package: {package_name}"

CLEAR_PACKAGES_NAME = "clear-packages"
CLEAR_PACKAGES_DESC = "Clear all allowed external packages"
CLEAR_PACKAGES_YES_HELP = "Skip confirmation prompt"
CLEAR_PACKAGES_WARNING = "This will clear all allowed external packages."
CLEAR_PACKAGES_CONFIRM = "This will clear all allowed external packages."
CLEAR_PACKAGES_PROMPT = "Are you sure? (yes/no): "
CLEAR_PACKAGES_CANCELLED = "Cancelled."
CLEAR_PACKAGES_SUCCESS = "Cleared all allowed packages"
CLEAR_PACKAGES_FAIL = "Failed to clear packages"
CLEAR_PACKAGES_RESULT = "All packages cleared"
CLEAR_PACKAGES_RESULT_FAIL = "Failed to clear packages"
CLEAR_PACKAGES_RESULT_CANCEL = "Operation cancelled"

UPDATE_PACKAGE_NAME = "update-package"
UPDATE_PACKAGE_DESC = "Update (rename) an allowed external package"
UPDATE_PACKAGE_OLD_ARG = "Current package name"
UPDATE_PACKAGE_NEW_ARG = "New package name"
UPDATE_PACKAGE_SUCCESS = "Updated package: {old_name} -> {new_name}"
UPDATE_PACKAGE_FAIL = "Failed to update package: {old_name}"
UPDATE_PACKAGE_RESULT = "Package updated: {old_name} -> {new_name}"
UPDATE_PACKAGE_RESULT_FAIL = "Failed to update package: {old_name}"
# === Focus command group ===
FOCUS_COMMAND_GROUP_DESC = "Focus area management commands"

LIST_FOCUS_CMD_NAME = "list"
LIST_FOCUS_CMD_DESC = "List all configured focus areas"
FOCUS_SERVICE_NOT_AVAILABLE = "Focus area service not available"
TELEMETRY_SERVICE_NOT_AVAILABLE = "Telemetry service not available"
FOUND_FOCUS_AREAS = "Found {count} focus areas"

ADD_FOCUS_CMD_NAME = "add"
ADD_FOCUS_CMD_DESC = "Add a new focus area"
ADD_FOCUS_ARG_TITLE = "title"
ADD_FOCUS_ARG_TITLE_METAVAR = "TITLE"
ADD_FOCUS_ARG_TITLE_HELP = "Title of the focus area"
ADD_FOCUS_ARG_DESC = "description"
ADD_FOCUS_ARG_DESC_METAVAR = "TEXT"
ADD_FOCUS_ARG_DESC_HELP = "Description of the focus area"
ADD_FOCUS_ARG_PRIORITY = "priority"
ADD_FOCUS_ARG_PRIORITY_METAVAR = "NUMBER"
ADD_FOCUS_ARG_PRIORITY_HELP = "Priority of the focus area (default: {default})"
ADD_FOCUS_ARG_ENABLED = "enabled"
ADD_FOCUS_ARG_ENABLED_HELP = "Enable the focus area (default: enabled)"
ADD_FOCUS_SUCCESS = "Successfully added focus area: {title}"
ADD_FOCUS_FAIL = "Failed to add focus area: {title}"

EDIT_FOCUS_CMD_NAME = "edit"
EDIT_FOCUS_CMD_DESC = "Edit an existing focus area"
EDIT_FOCUS_ARG_ID_OR_NAME = "id_or_name"
EDIT_FOCUS_ARG_ID_OR_NAME_METAVAR = "ID_OR_NAME"
EDIT_FOCUS_ARG_ID_OR_NAME_HELP = "ID or name of the focus area to edit"
EDIT_FOCUS_ARG_TITLE = "title"
EDIT_FOCUS_ARG_TITLE_METAVAR = "TITLE"
EDIT_FOCUS_ARG_TITLE_HELP = "New title for the focus area"
EDIT_FOCUS_ARG_DESC = "description"
EDIT_FOCUS_ARG_DESC_METAVAR = "TEXT"
EDIT_FOCUS_ARG_DESC_HELP = "New description for the focus area"
EDIT_FOCUS_ARG_PRIORITY = "priority"
EDIT_FOCUS_ARG_PRIORITY_METAVAR = "NUMBER"
EDIT_FOCUS_ARG_PRIORITY_HELP = "New priority for the focus area"
EDIT_FOCUS_ARG_ENABLED = "enabled"
EDIT_FOCUS_ARG_ENABLED_HELP = "Enable the focus area"
EDIT_FOCUS_ARG_DISABLED = "disabled"
EDIT_FOCUS_ARG_DISABLED_HELP = "Disable the focus area"
EDIT_FOCUS_NO_CHANGES = "No changes specified. Use --title, --description, --priority, or --enabled/--disabled."
EDIT_FOCUS_SUCCESS = "Successfully updated focus area: {id_or_name}"
EDIT_FOCUS_FAIL = "Failed to update focus area: {id_or_name}"

REMOVE_FOCUS_CMD_NAME = "remove"
REMOVE_FOCUS_CMD_DESC = "Remove a focus area"
REMOVE_FOCUS_ARG_ID_OR_NAME = "id_or_name"
REMOVE_FOCUS_ARG_ID_OR_NAME_METAVAR = "ID_OR_NAME"
REMOVE_FOCUS_ARG_ID_OR_NAME_HELP = "ID or name of the focus area to remove"
REMOVE_FOCUS_SUCCESS = "Successfully removed focus area: {id_or_name}"
REMOVE_FOCUS_FAIL = "Failed to remove focus area: {id_or_name}"

IMPORT_FOCUS_CMD_NAME = "import"
IMPORT_FOCUS_CMD_DESC = "Import focus areas from a JSON file"
IMPORT_FOCUS_ARG_FILE_PATH = "file_path"
IMPORT_FOCUS_ARG_FILE_PATH_METAVAR = "FILE_PATH"
IMPORT_FOCUS_ARG_FILE_PATH_HELP = "Path to the JSON file to import"
IMPORT_FOCUS_SUCCESS = "Successfully imported focus areas from: {file_path}"
IMPORT_FOCUS_FAIL = "Failed to import focus areas from: {file_path}"

EXPORT_FOCUS_CMD_NAME = "export"
EXPORT_FOCUS_CMD_DESC = "Export focus areas to a JSON file"
EXPORT_FOCUS_ARG_FILE_PATH = "file_path"
EXPORT_FOCUS_ARG_FILE_PATH_METAVAR = "FILE_PATH"
EXPORT_FOCUS_ARG_FILE_PATH_HELP = "Path to the JSON file to export to"
EXPORT_FOCUS_SUCCESS = "Successfully exported focus areas to: {file_path}"
EXPORT_FOCUS_FAIL = "Failed to export focus areas to: {file_path}"
# === Device command group ===
DEVICE_COMMAND_GROUP_DESC = "Device management commands"

LIST_DEVICES_CMD_NAME = "list"
LIST_DEVICES_CMD_DESC = "List all connected ADB devices"
DEVICE_SERVICE_NOT_AVAILABLE = "Device service not available"
NO_CONNECTED_DEVICES_FOUND = "No connected devices found."
NO_DEVICES_FOUND = "No devices found"
CONNECTED_DEVICES_HEADER = "\n=== Connected Devices ==="
CONNECTED_DEVICE_ITEM = "{index}. {device}"
CONNECTED_DEVICES_FOOTER = "=========================="
FOUND_CONNECTED_DEVICES = "Found {count} connected devices"

SELECT_DEVICE_CMD_NAME = "select"
SELECT_DEVICE_CMD_DESC = "Select a device by UDID"
SELECT_DEVICE_ARG_NAME = "device_udid"
SELECT_DEVICE_ARG_METAVAR = "UDID"
SELECT_DEVICE_ARG_HELP = "Device UDID to select"
SELECT_DEVICE_SUCCESS = "Successfully selected device: {udid}"
SELECT_DEVICE_FAIL = "Failed to select device: {udid}"

AUTO_SELECT_DEVICE_CMD_NAME = "auto-select"
AUTO_SELECT_DEVICE_CMD_DESC = "Automatically select the first available device"
AUTO_SELECT_DEVICE_SUCCESS = "Successfully auto-selected device"
AUTO_SELECT_DEVICE_FAIL = "Failed to auto-select device"
# === Crawler command group ===
START_CMD_NAME = "start"
START_CMD_DESC = "Start the crawler process"
START_CMD_ANNOTATE_ARG = "--annotate-offline-after-run"
START_CMD_ANNOTATE_HELP = "Run offline UI annotator after crawler exits"
START_SUCCESS = "Crawler started successfully"
START_FAIL = "Failed to start crawler"
START_ANNOTATE_WILL_RUN = ". Offline annotation will run after completion."

STOP_CMD_NAME = "stop"
STOP_CMD_DESC = "Stop the crawler process"
STOP_SUCCESS = "Stop signal sent to crawler"
STOP_FAIL = "Failed to stop crawler"

PAUSE_CMD_NAME = "pause"
PAUSE_CMD_DESC = "Pause the crawler process"
PAUSE_SUCCESS = "Pause signal sent to crawler"
PAUSE_FAIL = "Failed to pause crawler"

RESUME_CMD_NAME = "resume"
RESUME_CMD_DESC = "Resume the crawler process"
RESUME_SUCCESS = "Resume signal sent to crawler"
RESUME_FAIL = "Failed to resume crawler"

STATUS_CMD_NAME = "status"
STATUS_CMD_DESC = "Show crawler status"
STATUS_SUCCESS = "Status retrieved"

SERVICE_NOT_AVAILABLE = "{service} service not available"

# Print format strings for status
STATUS_HEADER = "\n=== Crawler Status ==="
STATUS_PROCESS = "  Process: {process}"
STATUS_STATE = "  State: {state}"
STATUS_TARGET_APP = "  Target App: {target_app}"
STATUS_OUTPUT_DIR = "  Output Data Dir: {output_dir}"
STATUS_FOOTER = "======================="
"""User-facing message constants for CLI commands.

Centralizes strings for descriptions, help text, errors, and print formatting.
"""

# Command group
ANALYSIS_GROUP_DESC = "Analysis and reporting commands"

# ListAnalysisTargetsCommand
CMD_LIST_ANALYSIS_TARGETS_DESC = "List available analysis targets"
ERR_ANALYSIS_TARGET_DISCOVERY_FAILED = "Error: Could not discover analysis targets."
INFO_NO_ANALYSIS_TARGETS_FOUND = "No analysis targets found."
HEADER_AVAILABLE_ANALYSIS_TARGETS = "=== Available Analysis Targets ==="
FOOTER_SECTION_SEPARATOR = "================================"
LABEL_APP_PACKAGE = "App Package:"
LABEL_DB_FILE = "DB File:"
LABEL_SESSION_DIR = "Session Dir:"
MSG_FOUND_ANALYSIS_TARGETS = "Found {count} analysis targets"

# Shared argument help text
ARG_HELP_TARGET_INDEX = "Target index from list-analysis-targets"
ARG_HELP_TARGET_APP_PACKAGE = "Target app package name"
ARG_HELP_PDF_OUTPUT_NAME = "Custom PDF filename (optional)"
ARG_HELP_VERBOSE = "Enable verbose output for this command"

# General help
HELP_AVAILABLE_COMMANDS = "Available commands"

# ListRunsForTargetCommand
CMD_LIST_RUNS_FOR_TARGET_DESC = "List runs for a specific analysis target"
MSG_RUNS_LISTED_SUCCESS = "Runs listed successfully"
ERR_FAILED_LIST_RUNS_FOR_TARGET = "Failed to list runs for target"

# GenerateAnalysisPDFCommand
CMD_GENERATE_ANALYSIS_PDF_DESC = "Generate PDF report for analysis target"
MSG_PDF_GENERATION_SUCCESS = "PDF generation completed successfully"
ERR_PDF_GENERATION_FAILED = "PDF generation failed"

# PrintAnalysisSummaryCommand
CMD_PRINT_ANALYSIS_SUMMARY_DESC = "Print summary metrics for analysis target"
MSG_ANALYSIS_SUMMARY_SUCCESS = "Analysis summary printed successfully"
ERR_ANALYSIS_SUMMARY_FAILED = "Failed to print analysis summary"

# Apps command group
APPS_GROUP_DESC = "App management commands"

# ScanAllAppsCommand
CMD_SCAN_ALL_DESC = "Scan device and cache ALL installed apps with AI health filtering (merged file)"
ARG_HELP_FORCE_RESCAN = "Force rescan even if cache exists"
MSG_SCAN_ALL_SUCCESS = "Successfully scanned and cached apps with AI filtering. Cache at: {cache_path}"
ERR_SCAN_APPS_FAILED = "Failed to scan apps"

# ScanHealthAppsCommand
CMD_SCAN_HEALTH_DESC = "Scan device and cache apps with AI health filtering (same as scan-all)"
MSG_SCAN_HEALTH_SUCCESS = "Successfully scanned apps with AI health filtering. Cache at: {cache_path}"

# ListAllAppsCommand
CMD_LIST_ALL_DESC = "List ALL apps from the latest merged cache"

# ListHealthAppsCommand
CMD_LIST_HEALTH_DESC = "List health apps from the latest cache"

# SelectAppCommand
CMD_SELECT_DESC = "Select an app by index or name"
ARG_HELP_APP_IDENTIFIER = "App index (1-based) or name/package"
MSG_SELECT_APP_SUCCESS = "Selected app: {name} ({package})"
ERR_SELECT_APP_FAILED = "Failed to select app: {app_identifier}"

# ShowSelectedAppCommand
CMD_SHOW_SELECTED_DESC = "Show the currently selected app"
HEADER_SELECTED_APP = "=== Selected App ==="
LABEL_NAME = "Name:"
LABEL_PACKAGE = "Package:"
LABEL_ACTIVITY = "Activity:"
FOOTER_SELECTED_APP = "===================="
MSG_NO_APP_SELECTED = "No app selected. Use 'apps select' to select an app."
ERR_APP_SCAN_SERVICE_NOT_AVAILABLE = "App scan service not available"
ERR_CONFIG_SERVICE_NOT_AVAILABLE = "Config service not available"

# BaseListAppsCommand
MSG_NO_APPS_FOUND = "No {cache_key_type} apps found in cache."
HEADER_APPS_LIST = "\n=== {header_title} ({count}) ==="
FORMAT_APP_LIST_ITEM = "{index:2d}. {name} ({package})"
FOOTER_APPS_LIST = "=" * (len("{header_title}") + 10)
MSG_LISTED_APPS_SUCCESS = "Listed {count} {cache_key_type} apps"

# Header titles
HEADER_ALL_APPS = "All Apps"
HEADER_HEALTH_APPS = "Health Apps"

# Config command group
CONFIG_GROUP_NAME = "config"
CONFIG_GROUP_DESC = "Configuration management commands"

# ShowConfigCommand
SHOW_CONFIG_CMD_NAME = "show"
SHOW_CONFIG_CMD_DESC = "Show current configuration"
SHOW_CONFIG_FILTER_HELP = "Optional filter to show specific config keys"
SHOW_CONFIG_DISPLAYED = "Configuration displayed"
SHOW_CONFIG_DISPLAYED_FILTERED = "Configuration displayed for filter: {filter}"

# SetConfigCommand
SET_CONFIG_CMD_NAME = "set"
SET_CONFIG_CMD_DESC = "Set configuration values"
SET_CONFIG_KEY_VALUE_HELP = "Key-value pairs to set (e.g., key1=value1 key2=value2)"

# Analysis service error messages
ERR_CONFIG_SERVICE_NOT_AVAILABLE = "Config service not available"
ERR_OUTPUT_DATA_DIR_NOT_CONFIGURED = "OUTPUT_DATA_DIR is not configured."
ERR_OUTPUT_DIRECTORY_NOT_FOUND = "Output directory not found: {db_output_root}"
ERR_ANALYSIS_TARGET_DISCOVERY_FAILED = "Could not discover analysis targets. Check OUTPUT_DATA_DIR and database_output structure."
ERR_TARGET_INDEX_NOT_FOUND = "Target index {index} not found."
ERR_TARGET_APP_PACKAGE_NOT_FOUND = "Target app package '{package}' not found."
ERR_INVALID_TARGET_INDEX = "Invalid target index: '{identifier}'. Must be a number."
ERR_RUN_ANALYZER_IMPORT_FAILED = "Failed to import RunAnalyzer: {error}"
ERR_TARGET_NOT_FOUND = "Target not found"
ERR_XHTML2PDF_NOT_AVAILABLE = "PDF library (xhtml2pdf) not available. Install with: pip install xhtml2pdf"
ERR_OUTPUT_DATA_DIR_NOT_SET = "OUTPUT_DATA_DIR is not configured."
ERR_FAILED_TO_DETERMINE_RUN_ID = "Failed to determine a run_id for {operation} for target {app_package}."
ERR_DATABASE_FILE_NOT_FOUND = "Database file not found for {operation}: {db_path}"
ERR_ERROR_DURING_OPERATION = "Error {operation} target {app_package}, run {run_id}: {error}"
ERR_PROJECT_ROOT_NOT_CONFIGURED = "PROJECT_ROOT is not configured."
ERR_OFFLINE_UI_ANNOTATOR_FAILED = "Offline UI annotation failed (code {returncode}). Output:\n{stdout}\n{stderr}"
ERR_FAILED_TO_RUN_OFFLINE_UI_ANNOTATOR = "Failed to run offline UI annotator: {error}"
ERR_ANNOTATION_SERVICE_NOT_AVAILABLE = "Annotation service not available"
ERR_DATABASE_ERROR_DETERMINING_RUN_ID = "Database error determining run ID: {error}"
ERR_COULD_NOT_DISCOVER_ANALYSIS_TARGETS = "Could not discover analysis targets."

# Analysis service success messages
MSG_OFFLINE_UI_ANNOTATION_COMPLETED = "Offline UI annotation completed successfully."
MSG_USING_RUN_ID_LATEST = "Using Run ID: {run_id} (latest/only)"
MSG_USING_RUN_ID_FIRST_AVAILABLE = "Could not determine latest run, using first available Run ID: {run_id}"
MSG_NO_RUNS_FOUND = "No runs found in the database."

# === App Scan Service Messages ===
# Error messages
ERR_ALL_APPS_SCAN_NO_CACHE = "All-apps scan did not produce a cache file."
ERR_HEALTH_APPS_SCAN_NO_CACHE = "Health-apps scan did not produce a cache file."
ERR_APP_INFO_OUTPUT_DIR_NOT_CONFIGURED = "APP_INFO_OUTPUT_DIR not configured in ConfigService"
ERR_NO_APP_CACHE_FOUND = "No app cache found. Run 'apps scan-all' or 'apps scan-health' first."
ERR_FAILED_TO_LOAD_APPS_FROM_CACHE = "Failed to load apps from cache"
ERR_FAILED_TO_LOAD_APPS_FROM_CACHE_WITH_ERROR = "Failed to load apps from cache: {error}"
ERR_NO_HEALTH_APPS_LOADED = "No health apps loaded. Run scan-health-apps first."
ERR_APP_NOT_FOUND = "App '{app_identifier}' not found."
ERR_SELECTED_APP_MISSING_PACKAGE_ACTIVITY = "Selected app '{name}' missing package/activity."

# Debug messages
DEBUG_STARTING_ALL_APPS_SCAN = "Starting ALL apps scan (no AI filter)..."
DEBUG_STARTING_HEALTH_APPS_SCAN = "Starting HEALTH apps scan (AI filter)..."
DEBUG_NO_CACHE_FILES_FOUND = "No cache files found for pattern: {pattern}"
DEBUG_RESOLVED_LATEST_CACHE_FILE = "Resolved latest cache file for '{app_type}': {latest}"

# === Crawler Status Messages ===
CRAWLER_STATUS_STOPPED = "stopped"
CRAWLER_STATUS_UNKNOWN = "unknown"
CRAWLER_STATUS_ERROR = "error"
CRAWLER_STATUS_RUNNING = "running"

# === ADB Device Management Messages ===
ERR_ADB_NOT_FOUND = "ADB command not found. Is Android SDK platform-tools in your PATH?"
ERR_ADB_LIST_DEVICES = "Error listing devices: {error}"

# === Focus Area Messages ===
FOCUS_AREA_FALLBACK_NAME = "Area {index}"
FOCUS_AREA_NOT_FOUND = "Focus area '{id_or_name}' not found."
FOCUS_AREA_ALREADY_EXISTS = "Error: Focus area with title '{title}' already exists."
FOCUS_AREA_SET_ENABLED = "Focus area '{name}' set enabled={enabled}"
FOCUS_AREA_MOVED = "Moved focus area to position {position}"
FOCUS_AREA_ADDED = "Successfully added focus area: {title}"
FOCUS_AREA_UPDATED = "Successfully updated focus area: {name}"
FOCUS_AREA_REMOVED = "Successfully removed focus area: {name}"
DATABASE_SERVICE_NOT_AVAILABLE = "Database service not available"
FAILED_TO_UPDATE_FOCUS_AREA = "Failed to update focus area: {error}"
FAILED_TO_REORDER_FOCUS_AREAS = "Failed to reorder focus areas: {error}"
ERROR_ADDING_FOCUS_AREA = "Error adding focus area: {error}"
ERROR_UPDATING_FOCUS_AREA = "Error updating focus area: {error}"
ERROR_REMOVING_FOCUS_AREA = "Error removing focus area: {error}"
INDEX_OUT_OF_RANGE = "Index out of range for focus areas list"
INDEXES_MUST_BE_INTEGERS = "--from-index and --to-index must be integers (1-based)"

# === OpenRouter Service Messages ===
# Error messages
ERR_OPENROUTER_IMPORT_FAILED = "Failed to import openrouter_models: {error}"
ERR_OPENROUTER_MODELS_CACHE_NOT_FOUND = "OpenRouter models cache not found. Run refresh first."
ERR_OPENROUTER_MODEL_NOT_FOUND = "Model '{model_identifier}' not found."
ERR_OPENROUTER_SELECT_MODEL_FAILED = "Failed to select OpenRouter model: {error}"
ERR_OPENROUTER_NOT_SELECTED_PROVIDER = "This command is only available when OpenRouter is selected as the AI provider."
ERR_OPENROUTER_NO_MODEL_SELECTED = "No OpenRouter model selected. Use '--select-openrouter-model <model>' first."
ERR_OPENROUTER_MODEL_NOT_IN_CACHE = "Model '{model_identifier}' not found in cache."
ERR_OPENROUTER_REFRESH_FAILED = "Failed to refresh OpenRouter models cache"

# Success messages
SUCCESS_OPENROUTER_MODELS_REFRESHED = "OpenRouter models cache refreshed successfully; saved to {cache_path}"
SUCCESS_OPENROUTER_MODEL_SELECTED = "Successfully selected OpenRouter model: {model_name} ({model_id})"

# Command names and descriptions
OPENROUTER_GROUP_NAME = "openrouter"
OPENROUTER_GROUP_DESC = "OpenRouter AI model management commands"

REFRESH_MODELS_CMD_NAME = "refresh-models"
REFRESH_MODELS_DESC = "Refresh OpenRouter models cache"

LIST_MODELS_CMD_NAME = "list-models"
LIST_MODELS_DESC = "List available OpenRouter models"
LIST_MODELS_FREE_ONLY = "Show only free models"
LIST_MODELS_ALL = "Show all models (ignore free-only filter)"

SELECT_MODEL_CMD_NAME = "select-model"
SELECT_MODEL_DESC = "Select an OpenRouter model"
SELECT_MODEL_ARG = "Model index (1-based) or name/ID fragment"
SELECT_MODEL_SUCCESS = "Selected model: {name} ({id})"
SELECT_MODEL_FAIL = "Failed to select model: {identifier}"

SHOW_SELECTION_CMD_NAME = "show-selection"
SHOW_SELECTION_DESC = "Show currently selected OpenRouter model"
SHOW_SELECTION_SUCCESS = "Selected model: {name} ({id})"
SHOW_SELECTION_FAIL = "No OpenRouter model selected"

SHOW_MODEL_DETAILS_CMD_NAME = "show-model-details"
SHOW_MODEL_DETAILS_DESC = "Show detailed information about selected model"
SHOW_MODEL_DETAILS_SUCCESS = "Model details displayed"
SHOW_MODEL_DETAILS_FAIL = "Failed to show model details"

CONFIGURE_IMAGE_CONTEXT_CMD_NAME = "configure-image-context"
CONFIGURE_IMAGE_CONTEXT_DESC = "Configure image context for vision models"
CONFIGURE_IMAGE_CONTEXT_MODEL_ARG = "Model ID (uses current if not specified)"
CONFIGURE_IMAGE_CONTEXT_ENABLE = "Enable image context"
CONFIGURE_IMAGE_CONTEXT_DISABLE = "Disable image context"
CONFIGURE_IMAGE_CONTEXT_CONFLICT = "Cannot specify both --enable and --disable"
CONFIGURE_IMAGE_CONTEXT_SUCCESS = "Image context {action} successfully"
CONFIGURE_IMAGE_CONTEXT_FAIL = "Failed to configure image context"

# Service availability messages
OPENROUTER_SERVICE_NOT_AVAILABLE = "OpenRouter service not available"
TELEMETRY_SERVICE_NOT_AVAILABLE = "Telemetry service not available"

# List models messages
LIST_MODELS_SUCCESS = "Listed {count} models"
LIST_MODELS_FAIL = "Failed to list models"
LIST_MODELS_NONE = "No models available"

# Added constants for process_utils.py
DEFAULT_FLAG_CONTENT = "flag"
SUBPROCESS_ENCODING = "utf-8"
SUBPROCESS_ERRORS = "replace"
PID_FILE_CREATED = "PID file created successfully."
FAILED_TO_CREATE_PID_FILE = "Failed to create PID file."
ERROR_READING_PID_FILE = "Error reading PID file."
PID_FILE_REMOVED = "PID file removed successfully."
FAILED_TO_REMOVE_PID_FILE = "Failed to remove PID file."
REMOVED_PID_FILE = "Removed PID file."
ERROR_DURING_PID_CLEANUP = "Error during PID file cleanup."
FLAG_FILE_CREATED = "Flag file created successfully."
FAILED_TO_CREATE_FLAG_FILE = "Failed to create flag file."
FLAG_FILE_REMOVED = "Flag file removed successfully."
FAILED_TO_REMOVE_FLAG_FILE = "Failed to remove flag file."
COMMAND_TIMED_OUT = "Command timed out after {timeout} seconds: {command}."
ERROR_RUNNING_COMMAND = "Error running command '{command}': {error}."
STARTED_DAEMON_PROCESS = "Started daemon process."
FAILED_TO_START_DAEMON_PROCESS = "Failed to start daemon process."
PROCESS_EXITED = "Process exited with code {code}."
ERROR_MONITORING_PROCESS = "Error monitoring process: {error}."
SIGNAL_RECEIVED = "Signal received: {signal}."
SIGHUP_NOT_SUPPORTED = "SIGHUP signal is not supported on this platform."

# === Telemetry Service Messages ===
# Event types
EVENT_COMMAND_START = "command_start"
EVENT_COMMAND_END = "command_end"
EVENT_ERROR = "error"
EVENT_SUCCESS = "success"
EVENT_WARNING = "warning"
EVENT_INFO = "info"
EVENT_JSON_OUTPUT = "json_output"
EVENT_SESSION_RESET = "session_reset"

# Service check event
EVENT_SERVICE_CHECK = "service_check"

# Status messages
STATUS_RUNNING = "running"
STATUS_WARNING = "warning"
STATUS_ERROR = "error"
STATUS_UNKNOWN = "unknown"

# Icons
ICON_SUCCESS = "✅"
ICON_WARNING = "⚠️"
ICON_ERROR = "❌"
ICON_INFO = "ℹ️"
ICON_QUESTION = "❓"
ICON_MONEY = "💰"
ICON_FREE = "🆓"
ICON_SEARCH = "🔍"

# UI Messages
UI_SERVICE_STATUS_SUMMARY = "Service Status Summary"
UI_CURRENT_CONFIGURATION = "Current Configuration"
UI_NO_ITEMS_FOUND = "No items found."
UI_NOT_AVAILABLE = "N/A"
UI_UNKNOWN = "Unknown"
UI_YES = "Yes"
UI_NO = "No"
UI_ENABLED = "Enabled"
UI_DISABLED = "Disabled"

# Model-related messages
UI_NO_MODELS_AVAILABLE = "No models available."
UI_NO_FOCUS_AREAS_CONFIGURED = "No focus areas configured."
UI_NO_OPENROUTER_MODEL_SELECTED = "No OpenRouter model selected."
UI_FREE_MARKER = "[FREE]"

# Headers and footers
UI_CRAWLER_STATUS = "Crawler Status"
UI_FOCUS_AREAS = "Focus Areas"
UI_OPENROUTER_MODELS = "OpenRouter Models"
UI_SELECTED_OPENROUTER_MODEL = "Selected OpenRouter Model"
UI_OPENROUTER_MODEL_DETAILS = "OpenRouter Model Details"
UI_OPENROUTER_IMAGE_CONTEXT_CONFIGURATION = "OpenRouter Image Context Configuration"

# Model selection messages
UI_SUCCESSFULLY_SELECTED_OPENROUTER_MODEL = "Successfully selected OpenRouter model:"
UI_MODEL_ID = "Model ID"
UI_MODEL_NAME = "Model Name"
UI_PRICING = "Pricing"
UI_PROMPT = "Prompt"
UI_COMPLETION = "Completion"
UI_IMAGE = "Image"
UI_PAID_MODEL_WARNING = "WARNING: You've selected a PAID model!"
UI_PAID_MODEL_COST_WARNING = "This model will incur costs for each API call."
UI_PAID_MODEL_CONFIG_WARNING = "To disable this warning, set OPENROUTER_NON_FREE_WARNING=false in config."
UI_PAID_MODEL_FREE_ONLY_WARNING = "To see only free models, use '--list-openrouter-models --free-only'"
UI_PAID_MODEL_INFO = "This is a PAID model. Costs will be incurred for usage."
UI_FREE_MODEL_INFO = "This is a FREE model."
UI_SHOW_SELECTION_INFO = "Use '--show-openrouter-selection' to view this information again."

# Image context messages
UI_IMAGE_SUPPORT = "Image Support"
UI_MODEL = "Model"
UI_CURRENT_IMAGE_CONTEXT_SETTING = "Current image context setting"
UI_THIS_MODEL_SUPPORTS_IMAGE_INPUTS = "This model supports image inputs."
UI_IMAGE_CONTEXT_ENABLED_FOR_MODEL = "Image context enabled for model"
UI_IMAGE_CONTEXT_DISABLED_FOR_MODEL = "Image context disabled for model"
UI_IMAGE_CONTEXT_DISABLED_MODEL_NO_SUPPORT = "Image context disabled (model does not support images)"
UI_WARNING_MODEL_NO_IMAGE_SUPPORT = "Warning: This model does not support image inputs. Cannot enable image context."
UI_MODEL_CAPABILITY_UNKNOWN = "Model capability unknown"
UI_HEURISTIC_SUGGESTS_SUPPORTS_IMAGES = "heuristic suggests it supports images"
UI_HEURISTIC_SUGGESTS_NO_SUPPORT = "heuristic suggests it does not support images"
UI_HEURISTIC_BASED = "(heuristic-based)"

# Model details messages
UI_DESCRIPTION = "Description"
UI_CONTEXT_LENGTH = "Context Length"
UI_PRICING_NOT_AVAILABLE = "Not available"
UI_CAPABILITIES = "Capabilities"
UI_INPUT_MODALITIES = "Input Modalities"
UI_OUTPUT_MODALITIES = "Output Modalities"
UI_SUPPORTED_PARAMETERS = "Supported Parameters"
UI_PROVIDER_INFORMATION = "Provider Information"
UI_PROVIDER_NAME = "Provider Name"
UI_MODEL_FORMAT = "Model Format"
UI_CURRENT_CONFIGURATION = "Current Configuration"
UI_IMAGE_CONTEXT = "Image Context"
UI_FREE_MODEL = "Free Model"

# Log messages
LOG_STARTING_COMMAND = "Starting command: {command_name}"
LOG_COMMAND_COMPLETED_SUCCESSFULLY = "Command {command_name} completed successfully"
LOG_COMMAND_FAILED = "Command {command_name} failed"
LOG_ERROR_OCCURRED = "Error occurred: {error}"
LOG_SERVICE_IS_STATUS = "Service {service_name} is {status}"
LOG_OUTPUT_DATA_AS_JSON = "Output data as JSON"
LOG_TELEMETRY_EVENTS_CLEARED = "Telemetry events cleared"
