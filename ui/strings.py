"""
Centralized UI strings for the application.

This module contains all user-facing strings (labels, tooltips, error messages, etc.)
to enable future internationalization and maintain consistency.
"""

from typing import Dict

# ========== Common UI Labels ==========
NO_MODEL_SELECTED = "No model selected"
SELECT_MODEL_TO_CONFIGURE = "Select a model to configure image inputs."
MODEL_SUPPORTS_IMAGE_INPUTS = "This model supports image inputs."
MODEL_DOES_NOT_SUPPORT_IMAGE_INPUTS = "This model does not support image inputs."
WARNING_MODEL_NO_IMAGE_SUPPORT = "⚠️ This model does not support image inputs."

# ========== Image Context Tooltips ==========
IMAGE_CONTEXT_DISABLED_PAYLOAD_LIMIT = "Image context disabled due to provider payload limits (max {max_kb} KB)."
IMAGE_CONTEXT_ENABLED_TOOLTIP = "Enable sending screenshots to AI for visual analysis. Disable for text-only analysis."

# ========== Model Selection Messages ==========
NO_OLLAMA_MODELS_AVAILABLE = "No Ollama models available - run 'ollama pull <model>'"
OLLAMA_NOT_RUNNING = "Ollama not running - start Ollama service"

# ========== UI Mode Labels ==========
UI_MODE_BASIC = "Basic"
UI_MODE_EXPERT = "Expert"
UI_MODE_TOOLTIP = "Switch between Basic and Expert UI modes. Expert mode shows advanced configuration options."

# ========== Reset Button ==========
RESET_TO_DEFAULTS_TOOLTIP = "Restore all configuration values to their defaults."

# ========== Action History ==========
ACTION_HISTORY_PLACEHOLDER = "Action history will appear here during crawling..."

# ========== Appium Settings ==========
APPIUM_URL_TOOLTIP = "Appium server URL (e.g., {url})"

# ========== Device Settings ==========
DEVICE_UDID_TOOLTIP = "Unique Device Identifier (UDID) of the target Android device or emulator. Optional."

# ========== App Selection ==========
HEALTH_APP_SELECTOR_TOOLTIP = "Select a health-related app discovered on the device"
USE_AI_FILTER_TOOLTIP = "Enable AI-powered filtering to discover health-related apps on the device"
REFRESH_APPS_TOOLTIP = "Scans the connected device for installed applications and filters for health-related ones using AI"
SCAN_REFRESH_HEALTH_APPS = "Scan/Refresh Health Apps List"

# ========== AI Provider Settings ==========
AI_PROVIDER_TOOLTIP = "Select the AI provider to use for decision-making during crawling"
REFRESH_OPENROUTER_MODELS_TOOLTIP = "Refresh the list of available OpenRouter models from the API"
OPENROUTER_SHOW_FREE_ONLY_TOOLTIP = "Show only free models in the model list"

# ========== Image Preprocessing Labels ==========
IMAGE_PREPROCESSING_GROUP = "Image Preprocessing"
MAX_SCREENSHOT_WIDTH_LABEL = "Max Screenshot Width (px): "
MAX_SCREENSHOT_WIDTH_TOOLTIP = "Max width to resize screenshots before sending to AI. Smaller reduces payload; larger preserves detail."
IMAGE_FORMAT_LABEL = "Image Format: "
IMAGE_FORMAT_TOOLTIP = "Choose output format for screenshots sent to AI."
IMAGE_QUALITY_LABEL = "Image Quality (%): "
IMAGE_QUALITY_TOOLTIP = "Compression quality for lossy formats (JPEG/WEBP). Lower = smaller payload, higher = more detail."
CROP_BARS_LABEL = "Crop Top/Bottom Bars: "
CROP_BARS_TOOLTIP = "Remove top/bottom bars to reduce payload while keeping UI content."
CROP_TOP_PERCENT_LABEL = "Crop Top Percent (%): "
CROP_TOP_PERCENT_TOOLTIP = "Percentage of image height to crop from the top when cropping bars is enabled."
CROP_BOTTOM_PERCENT_LABEL = "Crop Bottom Percent (%): "
CROP_BOTTOM_PERCENT_TOOLTIP = "Percentage of image height to crop from the bottom when cropping bars is enabled."

# ========== Crawler Settings Labels ==========
CRAWL_MODE_LABEL = "Crawl Mode: "
MAX_CRAWL_STEPS_LABEL = "Max Crawl Steps: "
MAX_CRAWL_DURATION_LABEL = "Max Crawl Duration (seconds): "
WAIT_AFTER_ACTION_LABEL = "Wait After Action (seconds): "
STABILITY_WAIT_LABEL = "Stability Wait (seconds): "
APP_LAUNCH_WAIT_LABEL = "App Launch Wait Time (seconds): "
VISUAL_SIMILARITY_LABEL = "Visual Similarity Threshold: "
ALLOWED_EXTERNAL_PACKAGES_LABEL = "Allowed External Packages: "

# ========== Error Handling Labels ==========
ERROR_HANDLING_GROUP = "Error Handling Settings"
MAX_CONSECUTIVE_AI_FAILURES_LABEL = "Max Consecutive AI Failures: "
MAX_CONSECUTIVE_MAP_FAILURES_LABEL = "Max Consecutive Map Failures: "
MAX_CONSECUTIVE_EXEC_FAILURES_LABEL = "Max Consecutive Exec Failures: "

# ========== MobSF Settings ==========
MOBSF_API_URL_PLACEHOLDER = "Your MobSF API URL"
MOBSF_API_KEY_PLACEHOLDER = "Your MobSF API Key"

# ========== Buttons ==========
PRE_CHECK_TOOLTIP = "Run pre-crawl validation checks for services and configuration"
GENERATE_REPORT_TOOLTIP = "Generate a report from the crawl data"

# ========== CLI Messages ==========
CLI_ERROR_PREFIX = "[ERROR]"
CLI_SELECT_PROVIDER_PROMPT = "Select AI provider ({providers}): "
CLI_INVALID_PROVIDER = "Invalid provider: {provider}"

# ========== Run UI Messages ==========
RUN_UI_ERROR_PYSIDE6 = "ERROR: PySide6 is not installed. Please install it with: pip install PySide6"

# ========== Group Box Titles ==========
APPIUM_SETTINGS_GROUP = "Appium Settings"
DEVICE_SETTINGS_GROUP = "Device Settings"
TARGET_APP_SETTINGS_GROUP = "Target App Settings"
AI_SETTINGS_GROUP = "AI Settings"
CRAWLER_SETTINGS_GROUP = "Crawler Settings"
FOCUS_AREAS_GROUP = "Focus Areas"
TRAFFIC_CAPTURE_GROUP = "Traffic Capture"
MOBSF_SETTINGS_GROUP = "MobSF Settings"
VIDEO_RECORDING_GROUP = "Video Recording"

# ========== Configuration Tooltips ==========
# These tooltips are used by domain/ui_controller.py and passed to UI components

TOOLTIP_APPIUM_SERVER_URL = "URL of the Appium server (e.g., http://127.0.0.1:4723). This is the server that handles mobile automation."
TOOLTIP_TARGET_DEVICE_UDID = "Unique Device Identifier (UDID) of the target Android device or emulator. Optional."
TOOLTIP_DEFAULT_MODEL_TYPE = "The default AI model to use for AI operations."
TOOLTIP_XML_SNIPPET_MAX_LEN = "Maximum characters of the XML page source to send to the AI for context. Minimum 5000 characters to ensure AI has sufficient UI structure information. The system automatically adjusts this limit based on the selected AI provider's payload size constraints to prevent API errors."
TOOLTIP_CRAWL_MODE = "'steps': Crawl for a fixed number of actions. 'time': Crawl for a fixed duration."
TOOLTIP_MAX_CRAWL_STEPS = "Maximum number of actions to perform if CRAWL_MODE is 'steps'."
TOOLTIP_MAX_CRAWL_DURATION_SECONDS = "Maximum duration in seconds for the crawl if CRAWL_MODE is 'time'."
TOOLTIP_WAIT_AFTER_ACTION = "Seconds to wait for the UI to stabilize after performing an action."
TOOLTIP_STABILITY_WAIT = "Seconds to wait before capturing the UI state (screenshot/XML) after an action, ensuring UI is stable."
TOOLTIP_APP_LAUNCH_WAIT_TIME = "Seconds to wait after launching the app for it to stabilize before starting the crawl."
TOOLTIP_VISUAL_SIMILARITY_THRESHOLD = "Perceptual hash distance threshold for comparing screenshots. Lower values mean screenshots must be more similar to be considered the same state."
TOOLTIP_ALLOWED_EXTERNAL_PACKAGES = "List of package names (one per line) that the crawler can interact with outside the main target app (e.g., for logins, webviews)."
TOOLTIP_MAX_CONSECUTIVE_AI_FAILURES = "Maximum number of consecutive times the AI can fail to provide a valid action before stopping."
TOOLTIP_MAX_CONSECUTIVE_MAP_FAILURES = "Maximum number of consecutive times the AI action cannot be mapped to a UI element before stopping."
TOOLTIP_MAX_CONSECUTIVE_EXEC_FAILURES = "Maximum number of consecutive times an action execution can fail before stopping."
TOOLTIP_ENABLE_IMAGE_CONTEXT = "Enable to send screenshots to the AI for visual analysis. Disable for text-only analysis using XML only."
TOOLTIP_ENABLE_TRAFFIC_CAPTURE = "Enable to capture network traffic (PCAP) during the crawl using PCAPdroid (requires PCAPdroid to be installed and configured on the device)."
TOOLTIP_CLEANUP_DEVICE_PCAP_FILE = "If traffic capture is enabled, delete the PCAP file from the device after successfully pulling it to the computer."
TOOLTIP_CONTINUE_EXISTING_RUN = "Enable to resume a previous crawl session, using its existing database and screenshots. Disable to start a fresh run."
TOOLTIP_ENABLE_MOBSF_ANALYSIS = "Enable to perform static analysis of the app using MobSF."
TOOLTIP_MOBSF_API_URL = "URL of the MobSF API (e.g., http://localhost:8000/api/v1)"
TOOLTIP_MOBSF_API_KEY = "API Key for authenticating with MobSF. This can be found in the MobSF web interface or in the config file."
TOOLTIP_ENABLE_VIDEO_RECORDING = "Enable to record the entire crawl session as an MP4 video."

# Image preprocessing tooltips
TOOLTIP_IMAGE_MAX_WIDTH = "Max screenshot width before sending to AI. Smaller widths (e.g., 720–1080px) reduce payload and are sufficient for most UI understanding; use larger widths for dense UIs or OCR."
TOOLTIP_IMAGE_FORMAT = "Screenshot format sent to AI. JPEG offers broad compatibility; WEBP typically yields smaller files with similar quality (great for OpenRouter); PNG is lossless and best for crisp text/OCR but larger."
TOOLTIP_IMAGE_QUALITY = "Compression quality for JPEG/WEBP. 70–85 is a good balance; increase to 90–95 if the model struggles to read fine text; decrease to ~60 to minimize payload."
TOOLTIP_IMAGE_CROP_BARS = "Remove top/bottom system bars to reduce payload while keeping the core app UI. Enable when bars are not needed for analysis."
TOOLTIP_IMAGE_CROP_TOP_PERCENT = "Percent of image height to crop from the top. 5–8% is typical for Android status bars; adjust if needed."
TOOLTIP_IMAGE_CROP_BOTTOM_PERCENT = "Percent of image height to crop from the bottom. 8–12% is typical for Android navigation bars; adjust if needed."


def get_tooltips_dict() -> Dict[str, str]:
    """
    Get a dictionary of all configuration tooltips.
    
    This function returns a dictionary mapping configuration keys to their tooltip strings.
    Used by domain/ui_controller.py to provide tooltips to UI components.
    
    Returns:
        Dictionary mapping config keys to tooltip strings
    """
    return {
        "APPIUM_SERVER_URL": TOOLTIP_APPIUM_SERVER_URL,
        "TARGET_DEVICE_UDID": TOOLTIP_TARGET_DEVICE_UDID,
        "DEFAULT_MODEL_TYPE": TOOLTIP_DEFAULT_MODEL_TYPE,
        "XML_SNIPPET_MAX_LEN": TOOLTIP_XML_SNIPPET_MAX_LEN,
        "CRAWL_MODE": TOOLTIP_CRAWL_MODE,
        "MAX_CRAWL_STEPS": TOOLTIP_MAX_CRAWL_STEPS,
        "MAX_CRAWL_DURATION_SECONDS": TOOLTIP_MAX_CRAWL_DURATION_SECONDS,
        "WAIT_AFTER_ACTION": TOOLTIP_WAIT_AFTER_ACTION,
        "STABILITY_WAIT": TOOLTIP_STABILITY_WAIT,
        "APP_LAUNCH_WAIT_TIME": TOOLTIP_APP_LAUNCH_WAIT_TIME,
        "VISUAL_SIMILARITY_THRESHOLD": TOOLTIP_VISUAL_SIMILARITY_THRESHOLD,
        "ALLOWED_EXTERNAL_PACKAGES": TOOLTIP_ALLOWED_EXTERNAL_PACKAGES,
        "MAX_CONSECUTIVE_AI_FAILURES": TOOLTIP_MAX_CONSECUTIVE_AI_FAILURES,
        "MAX_CONSECUTIVE_MAP_FAILURES": TOOLTIP_MAX_CONSECUTIVE_MAP_FAILURES,
        "MAX_CONSECUTIVE_EXEC_FAILURES": TOOLTIP_MAX_CONSECUTIVE_EXEC_FAILURES,
        "ENABLE_IMAGE_CONTEXT": TOOLTIP_ENABLE_IMAGE_CONTEXT,
        "ENABLE_TRAFFIC_CAPTURE": TOOLTIP_ENABLE_TRAFFIC_CAPTURE,
        "CLEANUP_DEVICE_PCAP_FILE": TOOLTIP_CLEANUP_DEVICE_PCAP_FILE,
        "CONTINUE_EXISTING_RUN": TOOLTIP_CONTINUE_EXISTING_RUN,
        "ENABLE_MOBSF_ANALYSIS": TOOLTIP_ENABLE_MOBSF_ANALYSIS,
        "MOBSF_API_URL": TOOLTIP_MOBSF_API_URL,
        "MOBSF_API_KEY": TOOLTIP_MOBSF_API_KEY,
        "ENABLE_VIDEO_RECORDING": TOOLTIP_ENABLE_VIDEO_RECORDING,
        "IMAGE_MAX_WIDTH": TOOLTIP_IMAGE_MAX_WIDTH,
        "IMAGE_FORMAT": TOOLTIP_IMAGE_FORMAT,
        "IMAGE_QUALITY": TOOLTIP_IMAGE_QUALITY,
        "IMAGE_CROP_BARS": TOOLTIP_IMAGE_CROP_BARS,
        "IMAGE_CROP_TOP_PERCENT": TOOLTIP_IMAGE_CROP_TOP_PERCENT,
        "IMAGE_CROP_BOTTOM_PERCENT": TOOLTIP_IMAGE_CROP_BOTTOM_PERCENT,
    }

