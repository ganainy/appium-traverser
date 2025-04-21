import google.generativeai as genai
import logging
import json
from PIL import Image
import io
from typing import Optional, Dict, List

class AIAssistant:
    """Handles interactions with the Generative AI model."""

    def __init__(self, api_key: str, model_name: str, safety_settings: Dict):
        if not api_key:
            raise ValueError("Gemini API key is required.")
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
            self.safety_settings = safety_settings
            logging.info(f"AI Assistant initialized with model: {model_name}")
        except Exception as e:
            logging.error(f"Failed to initialize GenerativeModel: {e}")
            raise

    def _prepare_image_part(self, screenshot_bytes: bytes) -> Optional[Image.Image]:
        """Converts screenshot bytes to PIL Image."""
        try:
            return Image.open(io.BytesIO(screenshot_bytes))
        except Exception as e:
            logging.error(f"Failed to load image for AI: {e}")
            return None

    # Function to build the prompt for the AI model
    def _build_prompt(self, xml_context: str, previous_actions: List[str], available_actions: List[str]) -> str:
            """Builds the detailed prompt for the AI model, REQUIRING bounding boxes for interactions."""
            action_descriptions = {
                "click": "Visually identify and click an interactive element (button, link, item). YOU MUST PROVIDE ITS BOUNDING BOX.",
                "input": "Visually identify a text input field, specify text, and PROVIDE ITS BOUNDING BOX.",
                "scroll_down": "Scroll the view downwards.",
                "scroll_up": "Scroll the view upwards.",
                "back": "Navigate back using the system back button."
            }
            action_list_str = "\n".join([f"- {a}: {action_descriptions.get(a, '')}" for a in available_actions])
            history_str = "\n".join([f"- {pa}" for pa in previous_actions]) if previous_actions else "None"

            # ***  Prompt REQUIRING Bounding Box ***
            prompt = f"""
            You are an expert Android application tester exploring an app using screen analysis.
            Your goal is to discover new screens and interactions systematically.
            You will be given the current screen's screenshot and its XML layout structure.
            **IMPORTANT: All 'click' and 'input' actions rely *solely* on precise bounding box coordinates.**

            CONTEXT:
            1. Screenshot: Provided as image input. Visually analyze this for interactive elements.
            2. XML Layout: Provided below. Use this primarily to understand structure, text, content-descriptions, and element types (e.g., EditText, Button) to aid visual identification.
            3. Previous Actions on this Screen State: The following actions (identified by their description) have already been attempted:
            {history_str}

            TASK:
            Analyze the screenshot and XML. Identify the BEST SINGLE action to perform next to explore the app further. Prioritize actions that lead to new screens or reveal new information, and interact with elements NOT previously attempted.

            Choose ONE action from the available types:
            {action_list_str}

            RESPONSE FORMAT:
            Respond ONLY with a valid JSON object containing these keys:
            - "action": (string) The chosen action type (e.g., "click", "input", "scroll_down", "back"). Required.
            - "target_description": (string) Brief text description of the visually identified target (e.g., "button with text 'Login'", "username input field"). Required for 'click' and 'input' for clarity, null otherwise.
            - "target_bounding_box": (object) **REQUIRED and MUST NOT be null if action is 'click' or 'input'.** Provide the precise **normalized** bounding box of the visually identified target element. Use the format {{"top_left": [x, y], "bottom_right": [x, y]}}, where x and y are floats between 0.0 and 1.0. If you choose 'click' or 'input', you MUST identify the element visually and provide its box. Set to null ONLY for 'scroll_down', 'scroll_up', or 'back'.
            - "input_text": (string | null) Text to input. Required ONLY if action is "input". Null otherwise.
            - "reasoning": (string) Briefly explain your choice and how you identified the target visually.

            EXAMPLE (Click Login Button - BBox REQUIRED):
            ```json
            {{
            "action": "click",
            "target_description": "The 'Login' button near the bottom",
            "target_bounding_box": {{"top_left": [0.4, 0.8], "bottom_right": [0.6, 0.88]}},
            "input_text": null,
            "reasoning": "Visually identified the primary login button. Proceeding requires clicking it."
            }}
            ```
            EXAMPLE (Input Email - BBox REQUIRED):
            ```json
            {{
            "action": "input",
            "target_description": "Rectangular email address input field",
            "target_bounding_box": {{"top_left": [0.1, 0.3], "bottom_right": [0.9, 0.38]}},
            "input_text": "test@example.com",
            "reasoning": "Visually identified the input field for the email address. Need to input email before logging in."
            }}
            ```
            EXAMPLE (Scroll):
            ```json
            {{
            "action": "scroll_down",
            "target_description": null,
            "target_bounding_box": null,
            "input_text": null,
            "reasoning": "The current view seems scrollable and more content might be below."
            }}
            ```

            XML CONTEXT FOR CURRENT SCREEN (Use for context, but interaction relies on visual BBox):
            ```xml
            {xml_context}
            ```
            """
            return prompt.strip()

    def get_next_action(self, screenshot_bytes: bytes, xml_context: str, previous_actions: List[str], available_actions: List[str]) -> Optional[Dict]:
        """Gets the next action suggestion from the AI."""
        image_part = self._prepare_image_part(screenshot_bytes)
        if not image_part:
            return None

        prompt = self._build_prompt(xml_context, previous_actions, available_actions)
        content_parts = [prompt, image_part]

        # *** ADD LOGGING FOR PROMPT ***
        logging.info("--- Sending Prompt to AI ---")
        # Log sensitive parts carefully if needed, maybe truncate XML here for logging
        log_prompt = prompt.replace(xml_context, f"[XML Context - Length: {len(xml_context)}]") if len(xml_context) > 500 else prompt
        logging.debug(f"Full AI Prompt:\n{log_prompt}") # Debug level for potentially long prompt
        logging.info("-----------------------------")


        try:
            logging.debug("Requesting AI generation...")
            response = self.model.generate_content(content_parts, safety_settings=self.safety_settings)

            # *** ADD LOGGING FOR RAW RESPONSE ***
            logging.info("--- Received Raw Response from AI ---")
            try:
                 raw_response_text = response.text
                 logging.debug(f"Raw AI Response Text:\n{raw_response_text}")
            except Exception as log_err:
                 logging.warning(f"Could not log raw AI response text: {log_err}")

            logging.debug(f"Prompt Feedback: {response.prompt_feedback}")

            finish_reason_val = None
            finish_reason_name = 'UNKNOWN'
            if response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                finish_reason_val = response.candidates[0].finish_reason
                # Try to get the name from the enum if possible, otherwise use the value
                try:
                    # The enum might be directly accessible like this:
                    finish_reason_name = genai.protos.Candidate.FinishReason(finish_reason_val).name
                except AttributeError:
                    # Fallback if the above path is wrong - just use the value
                    logging.debug("Could not resolve FinishReason enum name, using integer value.")
                    finish_reason_name = f"Value({finish_reason_val})"
                except Exception as enum_err:
                     logging.warning(f"Error getting FinishReason name: {enum_err}")
                     finish_reason_name = f"Value({finish_reason_val})"

            logging.debug(f"Finish Reason: {finish_reason_name}") # Log the name or value

            if response.candidates and hasattr(response.candidates[0], 'safety_ratings'):
                 logging.debug(f"Safety Ratings: {response.candidates[0].safety_ratings}")
            logging.info("------------------------------------")


            # Check for safety blocks or other issues (Use the value directly)
            # Common values: 0=Unknown, 1=Stop, 2=MaxTokens, 3=Safety, 4=Recitation, 5=Other
            if not response.candidates or finish_reason_val != 1: # Check if finish_reason is NOT 'STOP' (value 1)
                 logging.warning(f"AI generation finished abnormally or was blocked. Reason: {finish_reason_name}")
                 return None

            ai_response_text = response.text.strip()

            # Extract JSON part (handling potential markdown)
            # ... (keep existing JSON extraction logic) ...
            json_str = ai_response_text
            if json_str.startswith("```json"):
                json_str = json_str[7:-3].strip()
            elif json_str.startswith("```"): # Handle case where only closing backticks are missing
                json_str = json_str[3:].strip()
            if json_str.endswith("```"):
                 json_str = json_str[:-3].strip()


            try:
                action_data = json.loads(json_str)
                # *** Basic validation including bbox structure if present ***
                if not isinstance(action_data, dict) or "action" not in action_data:
                    logging.error(f"AI response parsed as JSON but lacks 'action' key: {action_data}")
                    return None
                # Validate bounding box structure if provided
                bbox = action_data.get("target_bounding_box")
                if bbox:
                    if not isinstance(bbox, dict) or \
                       "top_left" not in bbox or not isinstance(bbox["top_left"], list) or len(bbox["top_left"]) != 2 or \
                       "bottom_right" not in bbox or not isinstance(bbox["bottom_right"], list) or len(bbox["bottom_right"]) != 2:
                        logging.warning(f"AI provided 'target_bounding_box' but format is invalid: {bbox}. Ignoring bbox.")
                        action_data["target_bounding_box"] = None # Nullify invalid bbox

                logging.info(f"AI Suggested Action: {action_data.get('action')} - Target: {action_data.get('target_description')}")
                logging.debug(f"AI Full Parsed Suggestion: {action_data}")
                return action_data
            except json.JSONDecodeError as json_e:
                logging.error(f"Failed to parse AI response as JSON: {json_e}")
                logging.error(f"Problematic JSON string: '{json_str}'")
                return None

        except Exception as e:
            logging.error(f"Error during AI interaction: {e}", exc_info=True)
            return None