"""
Numeric constants for the application.

This module centralizes all magic numbers and numeric literals used throughout
the codebase, making them easier to understand, maintain, and modify.
"""

# ========== XML Processing Constants ==========

# XML length thresholds for logging and mode detection
XML_ORIGINAL_LEN_LOG_THRESHOLD = 200  # Log when XML exceeds this length
XML_TIGHT_MODE_THRESHOLD = 50000  # Switch to tight mode below this length
XML_VERY_TIGHT_MODE_THRESHOLD = 20000  # Switch to very tight mode below this length

# Text field length limits based on mode
XML_TEXT_FIELD_LEN_VERY_TIGHT = 50
XML_TEXT_FIELD_LEN_TIGHT = 80
XML_TEXT_FIELD_LEN_NORMAL = 120

# Default XML processing limits
XML_SNIPPET_MAX_LEN_DEFAULT = 15000
XML_SUMMARY_MAX_LINES_DEFAULT = 120

# Hash distance threshold for similarity detection
HASH_DISTANCE_ERROR_THRESHOLD = 1000

# ========== Time Constants ==========

# Time conversion factors
MS_PER_SECOND = 1000
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400

# Default wait times (in seconds)
WAIT_AFTER_ACTION_DEFAULT = 2.0
STABILITY_WAIT_DEFAULT = 1.0
APP_LAUNCH_WAIT_TIME_DEFAULT = 5
ACTIVITY_LAUNCH_WAIT_TIME_DEFAULT = 5.0

# Long press duration (in milliseconds)
LONG_PRESS_MIN_DURATION_MS = 600

# ========== Service Check Timeouts ==========

# Service health check timeouts (in seconds)
APPIUM_STATUS_TIMEOUT = 3
MCP_STATUS_TIMEOUT = 3
MOBSF_STATUS_TIMEOUT = 3
OLLAMA_API_TIMEOUT = 1.5
OLLAMA_CLI_TIMEOUT = 2

# ========== UI Range Constants ==========

# Image crop percentage limits
CROP_PERCENT_MIN = 0
CROP_PERCENT_MAX = 50

# Crawler step limits
MAX_CRAWL_STEPS_MIN = 1
MAX_CRAWL_STEPS_MAX = 10000

# Crawler duration limits (in seconds)
MAX_CRAWL_DURATION_MIN_SECONDS = 60  # 1 minute
MAX_CRAWL_DURATION_MAX_SECONDS = 86400  # 1 day

# App launch wait time limits (in seconds)
APP_LAUNCH_WAIT_TIME_MIN = 0
APP_LAUNCH_WAIT_TIME_MAX = 300  # 5 minutes

# XML snippet max length range
XML_SNIPPET_MAX_LEN_MIN = 5000
XML_SNIPPET_MAX_LEN_MAX = 500000

# Image dimensions
IMAGE_MAX_WIDTH_MIN = 240
IMAGE_MAX_WIDTH_MAX = 4000

# Image quality range
IMAGE_QUALITY_MIN = 10
IMAGE_QUALITY_MAX = 100

# Visual similarity threshold range
VISUAL_SIMILARITY_THRESHOLD_MIN = 0
VISUAL_SIMILARITY_THRESHOLD_MAX = 100

# Error handling limits
MAX_CONSECUTIVE_FAILURES_MIN = 1
MAX_CONSECUTIVE_FAILURES_MAX = 100

# ========== Audio Constants ==========

# Beep frequencies (Hz)
BEEP_FREQUENCY_ERROR = 900
BEEP_FREQUENCY_SUCCESS = 800

# Beep durations (milliseconds)
BEEP_DURATION_ERROR = 150
BEEP_DURATION_SUCCESS = 200

# Beep delay (milliseconds)
BEEP_DELAY_MS = 220

# ========== Database Constants ==========

# Database timeouts
DB_CONNECT_TIMEOUT = 10  # seconds
DB_BUSY_TIMEOUT = 5000  # milliseconds

# ========== Cache Constants ==========

# Maximum number of screens to cache
CACHE_MAX_SCREENS = 100

# ========== Truncation Constants ==========

# Result truncation length for logging
RESULT_TRUNCATION_LENGTH = 200

# ========== HTTP Status Codes ==========

# Common HTTP status codes (use http.HTTPStatus for full set)
HTTP_OK = 200
HTTP_SERVICE_UNAVAILABLE = 503

# ========== Image Processing Constants ==========

# Image quality defaults
IMAGE_DEFAULT_QUALITY = 70
IMAGE_DEFAULT_FORMAT = 'JPEG'

# Image crop percentages (as decimals)
IMAGE_CROP_TOP_PCT_DEFAULT = 0.06
IMAGE_CROP_BOTTOM_PCT_DEFAULT = 0.06

# Image dimensions
IMAGE_MAX_WIDTH_DEFAULT = 640

# Image background color (RGB tuple for transparent image conversion)
IMAGE_BG_COLOR = (255, 255, 255)  # White background

# Image sharpening parameters
IMAGE_SHARPEN_RADIUS = 0.5
IMAGE_SHARPEN_PERCENT = 150
IMAGE_SHARPEN_THRESHOLD = 3

# ========== Model Configuration Constants ==========

# Default model parameters
DEFAULT_MODEL_TEMP = 0.7
DEFAULT_MAX_TOKENS = 4096

# ========== Loop Detection Constants ==========

LOOP_VISIT_THRESHOLD = 3
LOOP_HISTORY_LENGTH = 6

# ========== Logging Constants ==========

# AI interaction log filename
AI_LOG_FILENAME = 'readable.log'

# ========== Provider Defaults ==========

# Default AI provider name
DEFAULT_AI_PROVIDER = 'gemini'

