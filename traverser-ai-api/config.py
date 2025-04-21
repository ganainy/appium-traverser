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

# --- AI Settings ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Get API key from environment variable
AI_MODEL_NAME = "gemini-2.5-flash-preview-04-17" # Or "gemini-pro-vision", "gemini-1.5-pro", check availability
# Safety settings for Gemini - adjust as needed
# Reference: https://ai.google.dev/docs/safety_setting_gemini
AI_SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_MEDIUM_AND_ABOVE",
}

# --- Crawler Settings ---
# ...
ALLOWED_EXTERNAL_PACKAGES = [
    "com.google.android.gms",  # Google Sign-In
     "com.android.chrome", # for webviews during login
    "com.google.android.permissioncontroller",  # Remove if you dont want the crawler to give permissions to apps
]


# --- Crawler Settings ---
MAX_CRAWL_STEPS = 50 # Limit the number of interactions
SCREENSHOTS_DIR = f"traverser-ai-api/screenshots/crawl_screenshots_{APP_PACKAGE}"
ANNOTATED_SCREENSHOTS_DIR = f"traverser-ai-api/screenshots/annotated_crawl_screenshots_{APP_PACKAGE}"
# Database settings
DB_NAME = f"traverser-ai-api/database_output/{APP_PACKAGE}_crawl_data.db"
WAIT_AFTER_ACTION = 2.5 # Seconds to wait for UI to potentially change after an action
STABILITY_WAIT = 1.0 # Seconds to wait before getting state (screenshot/XML)
VISUAL_SIMILARITY_THRESHOLD = 5 # Perceptual hash distance threshold (lower means more similar)
ENABLE_XML_CONTEXT = True # Send XML snippet to AI?
XML_SNIPPET_MAX_LEN = 20000 #Max characters of XML to send

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
MAX_CONSECUTIVE_EXEC_FAILURES = 5