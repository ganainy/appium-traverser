"""
Constants for the AgentAssistant class.
This file contains all hardcoded "magic" values that were previously
embedded directly in the AgentAssistant implementation.
"""

# Provider/Model Defaults
DEFAULT_AI_PROVIDER = 'gemini'
DEFAULT_OLLAMA_URL = 'http://localhost:11434'
DEFAULT_MODEL_NAME = 'gemini/gemini-pro'

# Model Config Defaults
DEFAULT_MODEL_TEMP = 0.7
DEFAULT_MAX_TOKENS = 4096

# Logging Defaults
AI_LOG_FILENAME = 'ai_interactions_readable.log'

# Image Processing Defaults
IMAGE_MAX_WIDTH = 640
IMAGE_DEFAULT_QUALITY = 75
IMAGE_DEFAULT_FORMAT = 'JPEG'
IMAGE_CROP_TOP_PCT = 0.06
IMAGE_CROP_BOTTOM_PCT = 0.06
IMAGE_BG_COLOR = (255, 255, 255)
IMAGE_SHARPEN_RADIUS = 0.5
IMAGE_SHARPEN_PERCENT = 150
IMAGE_SHARPEN_THRESHOLD = 3

# Logic Defaults
LOOP_VISIT_THRESHOLD = 3
LOOP_HISTORY_LENGTH = 6
DEFAULT_LONG_PRESS_MS = 600

