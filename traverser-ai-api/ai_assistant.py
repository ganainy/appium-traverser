import google.generativeai as genai
import logging
import json
from PIL import Image
import io
from typing import Optional, Dict, List
import config
import time  # Add this import at the top

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
    def _build_prompt(self, xml_context: str, previous_actions: List[str], available_actions: List[str], current_screen_visit_count: int, current_composite_hash: str) -> str: # Added visit count and hash
        """Builds the detailed prompt for the AI model, including visit count awareness."""
        action_descriptions = {
            "click": "Visually identify and select an interactive element. Provide its best identifier (resource-id, content-desc, or text).",
            "input": "Visually identify a text input field. Provide its best identifier and the text to input.",
            "scroll_down": "Scroll the view downwards.",
            "scroll_up": "Scroll the view upwards.",
            "back": "Navigate back using the system back button."
        }
        action_list_str = "\n".join([f"- {a}: {action_descriptions.get(a, '')}" for a in available_actions])
        history_str = "\n".join([f"- {pa}" for pa in previous_actions]) if previous_actions else "None"

        # --- Added Visit Count Context ---
        visit_context = f"""
        CURRENT SCREEN CONTEXT:
        - Hash: {current_composite_hash}
        - Visit Count (this session): {current_screen_visit_count}
        """
        # --- Instruction based on Visit Count ---
        visit_instruction = ""
        # Use a configurable threshold, e.g., from config.LOOP_DETECTION_VISIT_THRESHOLD
        loop_threshold = getattr(config, 'LOOP_DETECTION_VISIT_THRESHOLD', 3) # Default to 3 if not in config
        if current_screen_visit_count > loop_threshold:
            visit_instruction = f"""
        **IMPORTANT LOOP PREVENTION:** This screen has been visited {current_screen_visit_count} times (more than the threshold of {loop_threshold}).
        Strongly prioritize actions that explore *new* functionality or are highly likely lead to a *different screen state* you haven't just come from.
        AVOID actions (like clicking standard confirmation buttons or simple navigation elements) if you suspect they will just return you to the immediately preceding screen state, unless absolutely necessary to fulfill a prerequisite for *further* progression. Consider scrolling or interacting with less obvious elements if possible.
        """
        # ---------------------------------

        prompt = f"""
        You are an expert Android application tester exploring an app using screen analysis.
        Your goal is to discover new screens and interactions systematically by performing ONE logical action at a time, with a focus on PROGRESSION.
        You will be given the current screen's screenshot and its XML layout structure.
        **IMPORTANT: 'click' and 'input' actions rely on you providing a good identifier (resource-id, content-desc, or text).
        Provide ONLY the value without the attribute name. For example:
        - CORRECT: "Back"
        - INCORRECT: 'content-desc="Back"' or 'text="Back"'**

        {visit_context}  # Insert visit count context here

        CONTEXT:
        1. Screenshot: Provided as image input.
        2. XML Layout: Provided below. Use this to find identifiers and check element states.
        3. Previous Actions Taken *From This Screen*:
        {history_str}

        TASK:
        Analyze the screenshot and XML. Identify the BEST SINGLE action to perform next to logically progress or explore the app. Prioritize reaching NEW screens or enabling PROGRESSION buttons.

        {visit_instruction} # Insert visit count instruction here

        **CRUCIAL RULE for Progression Buttons (Next, Continue, Save, etc.):**
        - CHECK PREREQUISITES: Check XML for identifier and `enabled="true"`. Check visually.
        - IF DISABLED: Perform the prerequisite action first (provide its identifier).
        - PRIORITIZE PREREQUISITES.

        General Priorities:
        1. Fulfill required prerequisites if progression buttons are disabled.
        2. Click enabled progression buttons ('Next', 'Save', 'Continue', etc.) to move forward.
        3. Look for and prioritize elements related to:
           - Privacy Policy, Terms of Service, Data Protection
           - Account settings, Personal Information, Profile
           - Registration, Login, or Data Collection forms
        4. Explore other interactive elements likely to lead to NEW areas (especially if visit count is high).
        5. Input text into fields if required or relevant for exploration.
        6. Scroll if more content seems available OR if other actions seem unproductive/looping.
        7. Use 'back' if exploration seems stuck or to return from a detail view (but avoid if it just completes a loop).

        Look for elements with keywords like:
        - "Privacy", "Policy", "Terms", "GDPR", "Data Protection"
        - "Account", "Profile", "Personal", "Settings"
        - "Register", "Sign up", "Login", "Create Account"
        - "Consent", "Permissions", "Allow"

        Choose ONE action from the available types:
        {action_list_str}

        RESPONSE FORMAT: (JSON with action, target_identifier, optional target_bounding_box, input_text, reasoning)
        # ... (Keep JSON format examples as before) ...

        XML CONTEXT FOR CURRENT SCREEN:
        ```xml
        {xml_context}
        ```
        """
        return prompt.strip()

    def get_next_action(self,
                        screenshot_bytes: bytes,
                        xml_context: str,
                        previous_actions: List[str],
                        available_actions: List[str],
                        current_screen_visit_count: int,
                        current_composite_hash: str
                       ) -> Optional[Dict]:
        """
        Gets the next action suggestion from the AI, providing visit count context.
        Includes logic to handle responses wrapped in a single-element list.

        Args:
            screenshot_bytes: PNG bytes of the current screen.
            xml_context: Simplified XML string of the current screen.
            previous_actions: List of action descriptions already attempted from this screen state.
            available_actions: List of action types the AI can choose from.
            current_screen_visit_count: How many times this screen state has been visited in the current run.
            current_composite_hash: The unique hash identifier for the current screen state.

        Returns:
            A dictionary representing the AI's suggested action in JSON format, or None if an error occurs
            or the AI fails to provide a valid suggestion.
        """
        image_part = self._prepare_image_part(screenshot_bytes)
        if not image_part:
            logging.error("Failed to prepare image for AI.")
            return None

        start_time = time.time()  # Start timing at the beginning

        try:
            prompt = self._build_prompt(
                xml_context,
                previous_actions,
                available_actions,
                current_screen_visit_count,
                current_composite_hash
            )
        except Exception as prompt_err:
             logging.error(f"Error building AI prompt: {prompt_err}", exc_info=True)
             return None

        content_parts = [prompt, image_part]

        logging.info("--- Sending Prompt to AI ---")
        # Truncate potentially long XML for logging clarity
        log_prompt = prompt.replace(xml_context, f"[XML Context Len:{len(xml_context)}]") if len(xml_context) > 1000 else prompt
        logging.debug(f"AI Prompt (XML potentially truncated):\n{log_prompt}")
        logging.info("-----------------------------")

        try:
            logging.debug("Requesting AI generation...")
            # Make the API call
            response = self.model.generate_content(content_parts, safety_settings=self.safety_settings)
            
            # Calculate and log total elapsed time
            elapsed_time = time.time() - start_time
            logging.info(f"Total AI Processing Time: {elapsed_time:.2f} seconds")

            # --- Logging for Raw Response ---
            logging.info("--- Received Raw Response from AI ---")
            raw_response_text = "[Response Error]" # Default in case of issues
            try:
                 # Accessing response.text might fail if response is blocked etc.
                 if response.parts:
                     raw_response_text = response.text # Get the actual text part
                 else:
                     # Log if the response structure is unexpected (e.g., blocked)
                     logging.warning("AI response has no parts (potentially blocked or empty).")
                     raw_response_text = "[No Text Part in Response]" # Placeholder text

                 # Log the raw text (might be long) at DEBUG level
                 logging.debug(f"Raw AI Response Text:\n{raw_response_text}")

            except AttributeError:
                 # Handle cases where response structure might be different than expected
                 logging.warning("Could not access response.text or response.parts directly.")
                 # Try accessing candidates if available as a fallback inspection
                 if hasattr(response, 'candidates') and response.candidates:
                     try: raw_response_text = response.candidates[0].content.parts[0].text
                     except Exception: raw_response_text = "[Error accessing candidate text]"
                 else: raw_response_text = "[No text found in response structure]"
                 logging.debug(f"Fallback Raw AI Response Text:\n{raw_response_text}")
            except Exception as log_err:
                 # Catch any other errors during logging attempt
                 logging.warning(f"Could not log or access raw AI response text: {log_err}")
                 raw_response_text = f"[Error Logging Response: {log_err}]"


            # --- Detailed Logging of Response Metadata ---
            if hasattr(response, 'prompt_feedback'):
                logging.debug(f"Prompt Feedback: {response.prompt_feedback}")
            else: logging.debug("Prompt Feedback attribute not found.")

            finish_reason_val = None; finish_reason_name = 'UNKNOWN'; safety_ratings_log = "N/A"
            if response.candidates:
                candidate = response.candidates[0] # Process first candidate
                if hasattr(candidate, 'finish_reason'):
                    finish_reason_val = candidate.finish_reason
                    try: finish_reason_name = genai.protos.Candidate.FinishReason(finish_reason_val).name
                    except Exception: finish_reason_name = f"Value({finish_reason_val})" # Fallback to value
                else: logging.debug("Finish Reason attribute not found in candidate.")

                if hasattr(candidate, 'safety_ratings'):
                     safety_ratings_log = str(candidate.safety_ratings)
                     logging.debug(f"Safety Ratings: {safety_ratings_log}")
                else: logging.debug("Safety Ratings attribute not found in candidate.")
            else: logging.warning("AI response has no candidates.")

            logging.info(f"Generation Finish Reason: {finish_reason_name}")
            logging.info("------------------------------------")

            # --- Check for abnormal finish or safety blocks ---
            # Define normal finish reason value (usually 1 for STOP)
            NORMAL_FINISH_REASON = 1
            if finish_reason_val != NORMAL_FINISH_REASON:
                 logging.warning(f"AI generation finished abnormally or was blocked. Reason: {finish_reason_name} ({finish_reason_val}).")
                 # Provide more context if blocked for safety
                 SAFETY_FINISH_REASON = 3 # Assuming 3 indicates safety block
                 if finish_reason_val == SAFETY_FINISH_REASON:
                     logging.warning(f"Safety Ratings causing block: {safety_ratings_log}")
                 logging.warning(f"Raw response content that was blocked/abnormal: {raw_response_text}")
                 return None # Do not proceed

            # --- Process Normal Response ---
            ai_response_text = raw_response_text.strip()
            if not ai_response_text:
                 logging.error("AI returned an empty response string after successful finish.")
                 return None

            # Attempt to clean and extract JSON from the final text
            json_str = ai_response_text
            # Handle common markdown code blocks
            if json_str.startswith("```json"): json_str = json_str[7:]
            elif json_str.startswith("```"): json_str = json_str[3:]
            if json_str.endswith("```"): json_str = json_str[:-3]
            json_str = json_str.strip() # Clean trailing/leading whitespace

            if not json_str:
                logging.error("Extracted JSON string is empty after cleaning markdown.")
                logging.error(f"Original problematic AI response was: '{ai_response_text}'")
                return None

            # Attempt to parse the potentially list-or-dict JSON string
            try:
                parsed_data: Any = json.loads(json_str)
                action_data: Optional[Dict] = None # Variable to hold the final action dictionary

                # --- Handle list wrapper: Check if response is list like [{...}] ---
                if isinstance(parsed_data, list):
                    # Check if it's a list containing exactly one dictionary
                    if len(parsed_data) == 1 and isinstance(parsed_data[0], dict):
                        logging.warning("AI returned response wrapped in a list '[{...}]', extracting the inner dictionary.")
                        action_data = parsed_data[0] # Use the dictionary inside the list
                    else:
                        logging.error(f"AI returned a list, but not the expected format [dict] (length={len(parsed_data)}): {parsed_data}")
                        return None # Fail if list format is wrong
                elif isinstance(parsed_data, dict):
                    # If it's already a dictionary, use it directly
                    action_data = parsed_data
                else:
                    # The parsed data is neither a list nor a dict
                    logging.error(f"AI response parsed, but is neither a list nor a dict. Type: {type(parsed_data)}, Data: {parsed_data}")
                    return None
                # ---------------------------------------------------------------------

                # --- Validation (Operates on the extracted action_data dictionary) ---
                if action_data is None:
                    # This check is defensive, should not be reached if logic above is correct
                    logging.error("Internal logic error: action_data is None after parsing/extraction checks.")
                    return None

                # Check for required 'action' key
                if "action" not in action_data:
                    logging.error(f"Extracted JSON object lacks required 'action' key: {action_data}")
                    return None

                # Validate identifier presence for relevant actions
                action_type = action_data.get("action")
                if action_type in ["click", "input"] and not action_data.get("target_identifier"):
                     logging.error(f"AI response for action '{action_type}' missing required 'target_identifier'. Data: {action_data}")
                     return None

                # Validate input_text presence for input action (allow empty string, but not null/None)
                if action_type == "input" and action_data.get("input_text") is None:
                    logging.error(f"AI response for action 'input' missing required 'input_text' (was None). Data: {action_data}")
                    return None

                # Optional bbox validation (if present)
                bbox = action_data.get("target_bounding_box")
                if bbox:
                    if not isinstance(bbox, dict) or \
                       "top_left" not in bbox or not isinstance(bbox["top_left"], list) or len(bbox["top_left"]) != 2 or \
                       "bottom_right" not in bbox or not isinstance(bbox["bottom_right"], list) or len(bbox["bottom_right"]) != 2:
                        logging.warning(f"AI provided 'target_bounding_box' but format is invalid: {bbox}. Nullifying bbox for this action.")
                        action_data["target_bounding_box"] = None # Correct the data for subsequent use

                # --- Log Success and Return Validated Data ---
                logging.info(f"AI Suggested Action: {action_data.get('action')} - Target Identifier: {action_data.get('target_identifier')}")
                logging.debug(f"AI Full Parsed & Validated Suggestion: {action_data}")
                return action_data

            except json.JSONDecodeError as json_e:
                logging.error(f"Failed to parse AI response as JSON: {json_e}")
                logging.error(f"Problematic JSON string received from AI: '{json_str}'")
                return None
            except Exception as parse_err:
                # Catch other potential errors during validation (e.g., unexpected types)
                logging.error(f"Error during JSON processing or validation: {parse_err}", exc_info=True)
                return None

        except Exception as e:
            # Catch broader errors during the API call or initial response handling
            logging.error(f"Unhandled error during AI interaction or response processing: {e}", exc_info=True)
            return None