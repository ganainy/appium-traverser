# UI Constants Module
# Contains constants used across the UI components

# UI Mode Constants
UI_MODE_BASIC = "Basic"
UI_MODE_EXPERT = "Expert"
UI_MODE_DEFAULT = UI_MODE_BASIC
UI_MODE_CONFIG_KEY = "UI_MODE"

# Define which settings groups and fields are considered advanced
# These will be hidden in basic mode
ADVANCED_GROUPS = [
    "appium_settings_group",
    "image_preprocessing_group",  # Image preprocessing controls are advanced
]

ADVANCED_FIELDS = {
    "TARGET_DEVICE_UDID": True,  # True means hide in basic mode
    "DEFAULT_MODEL_TYPE": False,
    "XML_SNIPPET_MAX_LEN": True,
    "STABILITY_WAIT": True,
    "VISUAL_SIMILARITY_THRESHOLD": True,
    "ALLOWED_EXTERNAL_PACKAGES": True,
    "MAX_CONSECUTIVE_AI_FAILURES": True,
    "MAX_CONSECUTIVE_MAP_FAILURES": True,
    "ENABLE_IMAGE_CONTEXT": False,
    "ENABLE_TRAFFIC_CAPTURE": False,
    "MOBSF_API_URL": True,
    "MOBSF_API_KEY": True,
    "OPENROUTER_API_KEY": False,  # API keys should be visible in basic mode
    "GEMINI_API_KEY": False,  # API keys should be visible in basic mode
    "OPENROUTER_SHOW_FREE_ONLY": False,
    # Image preprocessing controls
    "IMAGE_MAX_WIDTH": True,
    "IMAGE_FORMAT": True,
    "IMAGE_QUALITY": True,
    "IMAGE_CROP_BARS": True,
    "IMAGE_CROP_TOP_PERCENT": True,
    "IMAGE_CROP_BOTTOM_PERCENT": True,
    # Crawler prompt templates
    "CRAWLER_ACTION_DECISION_PROMPT": True,
    "CRAWLER_AVAILABLE_ACTIONS": True,
}

