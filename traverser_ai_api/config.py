import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- App Settings ---
APP_PACKAGE = "de.deltacity.android.blutspende"
APP_ACTIVITY = "de.deltacity.android.blutspende.activities.SplashScreenActivity"
ALLOWED_EXTERNAL_PACKAGES = [
    "com.google.android.gms",                   # Google Play Services
    "com.android.chrome",                       # Google Chrome
    "com.google.android.permissioncontroller",  # System Permission Controller
    "org.mozilla.firefox",                      # Mozilla Firefox
    "com.sec.android.app.sbrowser",            # Samsung Internet Browser
    "com.microsoft.emmx",                       # Microsoft Edge
    "com.brave.browser",                        # Brave Browser
    "com.duckduckgo.mobile.android",           # DuckDuckGo Privacy Browser
]

# --- Base Output Directory Configuration ---
OUTPUT_DATA_DIR = "output_data"  # Base directory for all output data
APP_INFO_OUTPUT_DIR = f"{OUTPUT_DATA_DIR}/app_info"
SCREENSHOTS_DIR = f"{OUTPUT_DATA_DIR}/screenshots/crawl_screenshots_{APP_PACKAGE}"
ANNOTATED_SCREENSHOTS_DIR = f"{OUTPUT_DATA_DIR}/screenshots/annotated_crawl_screenshots_{APP_PACKAGE}"
TRAFFIC_CAPTURE_OUTPUT_DIR = f"{OUTPUT_DATA_DIR}/traffic_captures"

# --- Logging Configuration ---
LOG_LEVEL = 'INFO'  # Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE_NAME = "main_traverser_final.log"

# --- Database Settings ---
DB_NAME = f"{OUTPUT_DATA_DIR}/database_output/{APP_PACKAGE}_crawl_data.db"
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_MODEL_TYPE = 'flash-latest-fast'
USE_CHAT_MEMORY = False  # Enable/disable chat history
MAX_CHAT_HISTORY = 10
ENABLE_XML_CONTEXT = True
XML_SNIPPET_MAX_LEN = 1000000  # Max characters of XML to send
MAX_APPS_TO_SEND_TO_AI = 200
USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY = False

AI_SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_MEDIUM_AND_ABOVE",
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
MAX_CRAWL_STEPS = 100
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

# --- Traffic Capture Settings ---
ENABLE_TRAFFIC_CAPTURE = True
PCAPDROID_PACKAGE = "com.emanuelef.remote_capture"
PCAPDROID_ACTIVITY = f"{PCAPDROID_PACKAGE}/.activities.CaptureCtrl"
PCAPDROID_API_KEY = os.getenv("PCAPDROID_API_KEY")
DEVICE_PCAP_DIR = "/sdcard/Download/PCAPdroid"
CLEANUP_DEVICE_PCAP_FILE = True  # Delete PCAP file from device after successful pull

