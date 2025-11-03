from typing import Dict

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

# Define the list of available actions and their descriptions
AVAILABLE_ACTIONS = {
    "click": "Perform a click action on the target element.",
    "input": "Input text into the target element.",
    "long_press": "Perform a long press action on the target element.",
    "swipe": "Swipe in a specified direction.",
    "scroll": "Scroll the view to reveal more content."
}

# Define prompt templates as string constants
ACTION_DECISION_SYSTEM_PROMPT = """
You are an AI agent tasked with deciding the next action for mobile app testing. Use the following JSON schema to structure your output:
{json_schema}

Available actions:
{action_list}
"""

CONTEXT_ANALYSIS_PROMPT = """
Analyze the given context and provide insights. Use the JSON schema below for your output:
{json_schema}

Available actions:
{action_list}
"""

SYSTEM_PROMPT_TEMPLATE = """
System prompt for building actions. JSON schema:
{json_schema}

Actions:
{action_list}
"""

SECOND_CALL_PROMPT = """
Make a second call for action extraction. Use the JSON schema:
{json_schema}

Actions:
{action_list}
"""
