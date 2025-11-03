# === Service check command group (magic numbers) ===
APPIUM_STATUS_TIMEOUT = 3
MCP_STATUS_TIMEOUT = 3
MOBSF_STATUS_TIMEOUT = 3
OLLAMA_API_TIMEOUT = 1.5
OLLAMA_CLI_TIMEOUT = 2
# Configuration constants for CLI commands

DEFAULT_FOCUS_PRIORITY = 999

# SQL queries for analysis service
SQL_SELECT_LATEST_RUN_ID = "SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1"
SQL_SELECT_ANY_RUN_ID = "SELECT run_id FROM runs LIMIT 1"
