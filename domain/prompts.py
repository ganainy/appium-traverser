from typing import Dict, Optional, Any

# Define the JSON output schema as a dictionary
JSON_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "target_identifier": {"type": "string"},
        "target_bounding_box": {
            "type": ["object", "null"],
            "properties": {
                "top_left": {"type": "array", "items": {"type": "number"}},
                "bottom_right": {"type": "array", "items": {"type": "number"}}
            }
        },
        "input_text": {"type": ["string", "null"]},
        "reasoning": {"type": "string"},
        "focus_influence": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["action", "target_identifier", "reasoning"]
}

# Fallback available actions (used only when config is not available)
# This should match CRAWLER_AVAILABLE_ACTIONS in config/app_config.py
_DEFAULT_AVAILABLE_ACTIONS = {
    "click": "Perform a click action on the target element.",
    "input": "Input text into the specified element.",
    "long_press": "Perform a long press action on the target element.",
    "scroll_down": "Scroll the view downward to reveal more content below.",
    "scroll_up": "Scroll the view upward to reveal more content above.",
    "swipe_left": "Swipe left to navigate or reveal content on the right.",
    "swipe_right": "Swipe right to navigate or reveal content on the left.",
    "back": "Press the back button to return to the previous screen.",
    "double_tap": "Perform a double tap gesture on the target element (useful for zooming, image galleries).",
    "clear_text": "Clear all text from the target input element.",
    "replace_text": "Replace existing text in the target input element with new text.",
    "flick": "Perform a fast flick gesture in the specified direction (faster than scroll for quick navigation).",
    "reset_app": "Reset the app to its initial state (clears app data and restarts)."
}

def get_available_actions(config: Optional[Any] = None) -> Dict[str, str]:
    """Get available actions from config, or return fallback defaults.
    
    Args:
        config: Optional Config instance. If provided, uses CRAWLER_AVAILABLE_ACTIONS.
                If None or config returns empty, returns fallback defaults.
    
    Returns:
        Dictionary mapping action names to descriptions
    """
    if config is not None:
        try:
            actions = config.CRAWLER_AVAILABLE_ACTIONS
            if actions and isinstance(actions, dict):
                return actions
        except Exception:
            pass
    
    return _DEFAULT_AVAILABLE_ACTIONS

# Backward compatibility: export as AVAILABLE_ACTIONS for existing imports
# This will be removed in a future version - use get_available_actions() instead
AVAILABLE_ACTIONS = _DEFAULT_AVAILABLE_ACTIONS

# Define prompt templates as string constants
# Editable part - users can customize this in the UI
ACTION_DECISION_SYSTEM_PROMPT = "You are an AI agent tasked with deciding the next action for mobile app testing."

# Fixed part - automatically appended by code, not editable by users
ACTION_DECISION_FIXED_PART = """
Use the following JSON schema to structure your output:
{json_schema}

Available actions:
{action_list}
"""

def build_action_decision_prompt(custom_part: Optional[str] = None) -> str:
    """Build the full action decision prompt by combining custom and fixed parts.
    
    Args:
        custom_part: Custom prompt text from user (editable part). If None, uses default.
    
    Returns:
        Complete prompt string with both custom and fixed parts
    """
    if custom_part is None:
        custom_part = ACTION_DECISION_SYSTEM_PROMPT
    
    # Combine custom part with fixed part
    return f"{custom_part}{ACTION_DECISION_FIXED_PART}"
