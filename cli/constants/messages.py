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
