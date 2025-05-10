import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- Appium Settings ---
APPIUM_SERVER_URL = "http://127.0.0.1:4723"
TARGET_DEVICE_UDID = None # Optional: Specify UDID, e.g., "emulator-5554" or real device ID
APP_PACKAGE = "eu.smartpatient.mytherapy" # CHANGE TO YOUR TARGET APP
APP_ACTIVITY = "eu.smartpatient.mytherapy.feature.account.presentation.onboarding.WelcomeActivity" # CHANGE TO YOUR TARGET APP's LAUNCH ACTIVITY
# Find these using `adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'` while app is open
NEW_COMMAND_TIMEOUT = 300 # Seconds Appium waits for a new command before quitting session
APPIUM_IMPLICIT_WAIT = 1 # Seconds Appium driver waits when trying to find elements before failing a strategy

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


# --- App Information Discovery ---
# Directory for caching discovered app information (package name, activity, category)
# Used by app_info_manager.py when integrated into main.py
APP_INFO_OUTPUT_DIR = "output_data/app_info"
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
SCREENSHOTS_DIR = f"output_data/screenshots/crawl_screenshots_{APP_PACKAGE}"
ANNOTATED_SCREENSHOTS_DIR = f"output_data/screenshots/annotated_crawl_screenshots_{APP_PACKAGE}"
# Database settings
DB_NAME = f"output_data/database_output/{APP_PACKAGE}_crawl_data.db"
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
MAX_CONSECUTIVE_AI_FAILURES = 5
MAX_CONSECUTIVE_MAP_FAILURES = 5
MAX_CONSECUTIVE_EXEC_FAILURES = 3

# --- App Launch Configuration ---
APP_LAUNCH_WAIT_TIME = 7 # Seconds to wait after launching an app for it to stabilize

# AI Settings
USE_CHAT_MEMORY = True  # Enable/disable chat history for more context-aware responses
MAX_CHAT_HISTORY = 10   # Maximum number of previous interactions to keep in memory


# Gemini Model Configurations
GEMINI_MODELS = {
    'flash-latest': {  # Default: Fast, cost-effective, multimodal
        'name': 'gemini-2.5-flash-preview-04-17',
        'description': 'Latest Flash model: Optimized for speed, cost, and multimodal tasks.'
    },
    'flash-latest-fast': { # Optimized for speed using generation config
        'name': 'gemini-2.5-flash-preview-04-17',
        'description': 'Latest Flash model with settings optimized for faster responses.',
        'generation_config': {
            'temperature': 0.3,
            'top_p': 0.8,
            'top_k': 20,
            'max_output_tokens': 1024, # Adjust if needed for Flash
        }
    },
    'pro-latest-accurate': { # Optimized for accuracy using Pro model and generation config
        'name': 'gemini-2.5-pro-exp-03-25',
        'description': 'Latest Pro model with settings optimized for higher accuracy and complex reasoning.',
        'generation_config': {
            'temperature': 0.7,
            'top_p': 0.95,
            'top_k': 40,
            'max_output_tokens': 2048, # Adjust if needed for Pro
        }
    }
}

# Default model configuration
DEFAULT_MODEL_TYPE = 'flash-latest-fast' # Changed default to the latest flash model

# --- Traffic Capture Settings (PCAPdroid) ---
ENABLE_TRAFFIC_CAPTURE = True # Set to True to enable traffic capture during crawl
PCAPDROID_PACKAGE = "com.emanuelef.remote_capture"
PCAPDROID_ACTIVITY = f"{PCAPDROID_PACKAGE}/.activities.CaptureCtrl"
DEVICE_PCAP_DIR = "/sdcard/Download/PCAPdroid" # Default PCAPdroid save directory
# Output directory for PCAP files, relative to the main project or traverser-ai-api
TRAFFIC_CAPTURE_OUTPUT_DIR = "output_data/traffic_captures"
CLEANUP_DEVICE_PCAP_FILE = True # Delete PCAP file from device after successful pull

