import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- Required Environment Variables & Config Settings ---
# Logging configuration
LOG_LEVEL = 'INFO'  # Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE_NAME = os.environ.get('LOG_FILE_NAME', 'main_traverser_final.log')

# --- Database Settings ---
DB_CONNECT_TIMEOUT = int(os.environ.get('DB_CONNECT_TIMEOUT', '10'))  # Seconds for sqlite3.connect() timeout
DB_BUSY_TIMEOUT = int(os.environ.get('DB_BUSY_TIMEOUT', '5000'))  # Milliseconds for PRAGMA busy_timeout

# --- App Discovery Settings ---
# Override with environment variables if provided
MAX_APPS_TO_SEND_TO_AI = int(os.environ.get('MAX_APPS_TO_SEND_TO_AI', '200'))
THIRD_PARTY_APPS_ONLY = os.environ.get('THIRD_PARTY_APPS_ONLY', 'true').lower() == 'true'

# --- AI Memory Settings (moved from hardcoded) ---
USE_CHAT_MEMORY = os.environ.get('USE_CHAT_MEMORY', 'true').lower() == 'true'
MAX_CHAT_HISTORY = int(os.environ.get('MAX_CHAT_HISTORY', '10'))

# --- Appium Settings ---
APPIUM_SERVER_URL = "http://127.0.0.1:4723"
TARGET_DEVICE_UDID = None # Optional: Specify UDID, e.g., "emulator-5554" or real device ID
APP_PACKAGE = "de.deltacity.android.blutspende" # Updated to match Blutspende app
APP_ACTIVITY = "de.deltacity.android.blutspende.activities.SplashScreenActivity" # Updated to match Blutspende app launch activity
# Find these using `adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'` while app is open
NEW_COMMAND_TIMEOUT = 300 # Seconds Appium waits for a new command before quitting session
APPIUM_IMPLICIT_WAIT = 1 # Seconds Appium driver waits when trying to find elements before failing a strategy

# --- Coordinate Fallback Settings ---
USE_COORDINATE_FALLBACK = True # Whether to use bounding box coordinates if element identification fails

# --- AI Settings ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Get API key from environment variable
# Safety settings for Gemini - adjust as needed
# Reference: https://ai.google.dev/docs/safety_setting_gemini
AI_SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_MEDIUM_AND_ABOVE",
}

# --- Crawler Settings ---
# List of package names that the crawler is allowed to interact with outside the main target app
# Useful for handling logins via Google, webviews, or permission dialogs.
ALLOWED_EXTERNAL_PACKAGES = [
    "com.google.android.gms",                   # Google Play Services (for Sign-In, etc.)
    "com.android.chrome",                       # Google Chrome (already present)
    "com.google.android.permissioncontroller",  # System Permission Controller
    "org.mozilla.firefox",                      # Mozilla Firefox
    "com.sec.android.app.sbrowser",             # Samsung Internet Browser
    "com.microsoft.emmx",                       # Microsoft Edge
    "com.brave.browser",                        # Brave Browser
    "com.duckduckgo.mobile.android",            # DuckDuckGo Privacy Browser
    # Add any other specific package names needed for your app's flows (e.g., Facebook login)
]


# --- Base Output Directory ---
OUTPUT_DATA_DIR = "output_data"  # Base directory for all output data

# --- App Information Discovery ---
# Directory for caching discovered app information (package name, activity, category)
# Used by app_info_manager.py when integrated into main.py
APP_INFO_OUTPUT_DIR = f"{OUTPUT_DATA_DIR}/app_info" # Changed to use base output directory
# When discovering the TARGET_APP_PACKAGE_NAME, should we look for it
# only among AI-filtered (e.g., health) apps?
# False: Search for TARGET_APP_PACKAGE_NAME in all discovered apps.
# True: Search for TARGET_APP_PACKAGE_NAME only in AI-filtered apps (less common for a specific target).
USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY = False


# --- Crawler Settings ---
CONTINUE_EXISTING_RUN = False  # Set to True to use existing DB and screenshots, False to start fresh
# Crawling control
CRAWL_MODE = 'steps'  # Options: 'steps' or 'time'
MAX_CRAWL_STEPS = 100  # Max steps if CRAWL_MODE is 'steps'
MAX_CRAWL_DURATION_SECONDS = 600  # Max duration in seconds (e.g., 600 for 10 mins) if CRAWL_MODE is 'time'
# Screenshot directories
SCREENSHOTS_DIR = f"{OUTPUT_DATA_DIR}/screenshots/crawl_screenshots_{APP_PACKAGE}"
ANNOTATED_SCREENSHOTS_DIR = f"{OUTPUT_DATA_DIR}/screenshots/annotated_crawl_screenshots_{APP_PACKAGE}"
# Database settings
DB_NAME = f"{OUTPUT_DATA_DIR}/database_output/{APP_PACKAGE}_crawl_data.db"
WAIT_AFTER_ACTION = 2.0 # Seconds to wait for UI to potentially change after an action
STABILITY_WAIT = 1.0 # Seconds to wait before getting state (screenshot/XML)
VISUAL_SIMILARITY_THRESHOLD = 5 # Perceptual hash distance threshold (lower means more similar)
ENABLE_XML_CONTEXT = True # Send XML snippet to AI?
XML_SNIPPET_MAX_LEN = 30000 #Max characters of XML to send

# --- Action Definitions (for AI prompt and mapping) ---
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

# --- App Launch Configuration ---
APP_LAUNCH_WAIT_TIME = 7 # Seconds to wait after launching an app for it to stabilize

# AI Settings
USE_CHAT_MEMORY = True  # Enable/disable chat history for more context-aware responses
MAX_CHAT_HISTORY = 10   # Maximum number of previous interactions to keep in memory
DEFAULT_MODEL_TYPE = 'flash-latest-fast' # Specify the default model to use


# Gemini Model Configurations
GEMINI_MODELS = {
    'flash-latest': {  # Default: Fast, cost-effective, multimodal
        'name': 'gemini-2.5-flash-preview-05-20',
        'description': 'Latest Flash model (2.5): Optimized for speed, cost, and multimodal tasks with built-in thinking capabilities.',
        'generation_config': {
            'temperature': 0.7,
            'top_p': 0.95,
            'top_k': 40,
            'max_output_tokens': 4096
        }
    },
    'flash-latest-fast': { # Optimized for speed using generation config
        'name': 'gemini-2.5-flash-preview-05-20',
        'description': 'Latest Flash model (2.5) with settings optimized for faster responses.',
        'generation_config': {
            'temperature': 0.3,
            'top_p': 0.8,
            'top_k': 20,
            'max_output_tokens': 2048
        }
    }
}

# --- Traffic Capture Settings (PCAPdroid) ---
ENABLE_TRAFFIC_CAPTURE = True # Set to True to enable traffic capture during crawl
PCAPDROID_PACKAGE = "com.emanuelef.remote_capture"
PCAPDROID_ACTIVITY = f"{PCAPDROID_PACKAGE}/.activities.CaptureCtrl"
PCAPDROID_API_KEY = os.getenv("PCAPDROID_API_KEY")  # API key for automated control
DEVICE_PCAP_DIR = "/sdcard/Download/PCAPdroid" # Default PCAPdroid save directory
# Output directory for PCAP files, relative to the main project or traverser-ai-api
TRAFFIC_CAPTURE_OUTPUT_DIR = f"{OUTPUT_DATA_DIR}/traffic_captures"
CLEANUP_DEVICE_PCAP_FILE = True # Delete PCAP file from device after successful pull

