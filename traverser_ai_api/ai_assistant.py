import google.generativeai as genai
import logging
import json
from PIL import Image
import io
from typing import Optional, Dict, List, Any  # Add Any here
from . import config
import time  # Add this import at the top

class AIAssistant:
    """Handles interactions with the Generative AI model."""

    def __init__(self, api_key: str, model_name: str = None, safety_settings: Dict = None):
        if not api_key:
            raise ValueError("Gemini API key is required.")
        try:
            genai.configure(api_key=api_key)
            
            # Get model configuration
            model_type = model_name or getattr(config, 'DEFAULT_MODEL_TYPE', 'pro-vision')
            model_config = getattr(config, 'GEMINI_MODELS', {}).get(model_type)
            
            if not model_config:
                logging.warning(f"Model type '{model_type}' not found in config, using default pro-vision")
                model_config = {'name': 'gemini-pro-vision'}
            
            # Initialize model with configuration
            self.model = genai.GenerativeModel(
                model_config['name'],
                generation_config=model_config.get('generation_config')
            )
            
            logging.info(f"AI Assistant initialized with model: {model_config['name']}")
            logging.info(f"Model description: {model_config.get('description', 'Standard configuration')}")
            
            self.safety_settings = safety_settings
            
            # Initialize chat if enabled
            self.use_chat = getattr(config, 'USE_CHAT_MEMORY', False)
            if self.use_chat:
                self.chat = self.model.start_chat(history=[])
                self.max_history = getattr(config, 'MAX_CHAT_HISTORY', 10)
                logging.info(f"Chat memory enabled (max history: {self.max_history})")
            else:
                self.chat = None
                
        except Exception as e:
            logging.error(f"Failed to initialize GenerativeModel: {e}")
            raise

    def _log_empty_response_details(self, response):
        """Helper to log details when an AI response is considered empty or problematic."""
        logging.info("Detailed AI Response Analysis:")
        try:
            if not response:
                logging.warning("  Response object itself is None.")
                return

            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                logging.info(f"  Prompt Feedback: {response.prompt_feedback}")
            else:
                logging.info("  No prompt feedback available or attribute missing.")

            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                finish_reason_value = getattr(candidate, 'finish_reason', 'N/A')
                finish_reason_name = genai.protos.Candidate.FinishReason(finish_reason_value).name if isinstance(finish_reason_value, int) else str(finish_reason_value)
                logging.info(f"  Candidate Finish Reason: {finish_reason_name} ({finish_reason_value})")
                
                if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                    logging.info("  Candidate Safety Ratings:")
                    for rating in candidate.safety_ratings:
                        category = getattr(rating, 'category', 'N/A')
                        probability = getattr(rating, 'probability', 'N/A')
                        category_name = genai.protos.HarmCategory(category).name if isinstance(category, int) else str(category)
                        probability_name = genai.protos.HarmProbability(probability).name if isinstance(probability, int) else str(probability)
                        logging.info(f"    Category: {category_name}, Probability: {probability_name}")
                else:
                    logging.info("  No safety ratings available for the candidate or attribute missing.")
                
                if hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts') and candidate.content.parts:
                    logging.info(f"  Candidate Content Parts ({len(candidate.content.parts)} part(s)):")
                    for i, part in enumerate(candidate.content.parts):
                        part_text_snippet = "N/A"
                        if hasattr(part, 'text') and part.text:
                            part_text_snippet = part.text[:100] + ('...' if len(part.text) > 100 else '')
                        elif hasattr(part, 'function_call'):
                            part_text_snippet = f"FunctionCall: {part.function_call}"
                        elif hasattr(part, 'inline_data'):
                            part_text_snippet = f"InlineData: mime_type={part.inline_data.mime_type}"
                        elif not hasattr(part, 'text') or not part.text:
                            part_text_snippet = "<Part has no text or text is empty>"

                        logging.info(f"    Part {i} ({type(part).__name__}): {part_text_snippet}")
                else:
                    logging.info("  No content parts found for the candidate or attributes missing.")
            else:
                logging.info("  No candidates found in AI response or attribute missing.")
            
            if hasattr(response, 'text'):
                logging.info(f"  Raw response.text (stripped): '{response.text.strip() if response.text is not None else '<None>'}'")

            # Ensure usage_metadata and its attributes exist before accessing them
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                logging.info(f"Usage Metadata: Prompt Tokens={getattr(response.usage_metadata, 'prompt_token_count', 'N/A')}, Candidates Tokens={getattr(response.usage_metadata, 'candidates_token_count', 'N/A')}, Total Tokens={getattr(response.usage_metadata, 'total_token_count', 'N/A')}")
            else:
                logging.warning("Usage metadata not available in AI response.")

        except Exception as e_details:
            logging.error(f"  Error during detailed AI response analysis: {e_details}", exc_info=True)

    def _prepare_image_part(self, screenshot_bytes: bytes) -> Optional[Image.Image]:
        """Converts screenshot bytes to PIL Image."""
        try:
            return Image.open(io.BytesIO(screenshot_bytes))
        except Exception as e:
            logging.error(f"Failed to load image for AI: {e}")
            return None

    def _build_prompt(self, xml_context: str, previous_actions: List[str], available_actions: List[str], current_screen_visit_count: int, current_composite_hash: str) -> str:
        """Builds the detailed prompt for the AI model, including visit count awareness."""
        action_descriptions = {
            "click": "Visually identify and select an interactive element. Provide its best identifier (resource-id, content-desc, or text).",
            "input": "Visually identify a text input field (e.g., class='android.widget.EditText'). Provide its best identifier AND the text to input. **CRITICAL: ONLY suggest 'input' for elements designed for text entry.**",
            "scroll_down": "Scroll the view downwards.",
            "scroll_up": "Scroll the view upwards.",
            "back": "Navigate back using the system back button."
        }
        action_list_str = "\n".join([f"- {a}: {action_descriptions.get(a, '')}" for a in available_actions])
        history_str = "\n".join([f"- {pa}" for pa in previous_actions]) if previous_actions else "None"

        visit_context = f"""
        CURRENT SCREEN CONTEXT:
        - Hash: {current_composite_hash}
        - Visit Count (this session): {current_screen_visit_count}
        """
        visit_instruction = ""
        loop_threshold = getattr(config, 'LOOP_DETECTION_VISIT_THRESHOLD', 3)
        if current_screen_visit_count > loop_threshold:
            visit_instruction = f"""
        **IMPORTANT LOOP PREVENTION:** This screen has been visited {current_screen_visit_count} times (more than the threshold of {loop_threshold}).
        Strongly prioritize actions that explore *new* functionality or are highly likely lead to a *different screen state* you haven't just come from.
        AVOID actions (like clicking standard confirmation buttons or simple navigation elements) if you suspect they will just return you to the immediately preceding screen state, unless absolutely necessary to fulfill a prerequisite for *further* progression. Consider scrolling or interacting with less obvious elements if possible.
        """

        json_format_example = """
        {
            "action": "click" | "input" | "scroll_up" | "scroll_down" | "back",
            "target_identifier": "element identifier (required for click/input)",
            "target_bounding_box": {
                "top_left": [0.1, 0.5],
                "bottom_right": [0.3, 0.6]
            },
            "input_text": "text to input (required for input action)",
            "reasoning": "Brief explanation of why this action was chosen"
        }
        """

        json_example_click = """
        {
            "action": "click",
            "target_identifier": "Continue",
            "target_bounding_box": {
                "top_left": [0.1, 0.5],
                "bottom_right": [0.3, 0.6]
            },
            "reasoning": "Clicking 'Continue' button to progress through setup"
        }
        """

        json_example_input = """
        {
            "action": "input",
            "target_identifier": "email_input",
            "target_bounding_box": {
                "top_left": [0.2, 0.3],
                "bottom_right": [0.8, 0.4]
            },
            "input_text": "test@example.com",
            "reasoning": "Filling email field to complete registration form"
        }
        """

        json_example_scroll = """
        {
            "action": "scroll_down",
            "reasoning": "Content appears to continue below viewport"
        }
        """

        prompt = f"""
        You are an expert Android application tester exploring an app using screen analysis.
        Your goal is to discover new screens and interactions systematically by performing ONE logical action at a time, with a focus on PROGRESSION.
        You will be given the current screen's screenshot and its XML layout structure.
        **IMPORTANT: 'click' and 'input' actions rely on you providing a good identifier (resource-id, content-desc, or text).
        Provide ONLY the value without the attribute name. For example:
        - CORRECT: "Back"
        - INCORRECT: 'content-desc="Back"' or 'text="Back"'**

        {visit_context}

        CONTEXT:
        1. Screenshot: Provided as image input.
        2. XML Layout: Provided below. Use this to find identifiers and check element states (like `class`, `enabled`, `clickable`).
        3. Previous Actions Taken *From This Screen*:
        {history_str}

        TASK:
        Analyze the screenshot and XML. Identify the BEST SINGLE action to perform next to logically progress or explore the app. Prioritize reaching NEW screens or enabling PROGRESSION buttons.

        {visit_instruction}

        **CRUCIAL RULE for Progression Buttons (Next, Continue, Save, etc.):**
        - CHECK PREREQUISITES: Check XML for identifier and `enabled="true"`. Check visually.
        - IF DISABLED: Perform the prerequisite action first (provide its identifier).
        - PRIORITIZE PREREQUISITES.

        **CRUCIAL RULE for 'input' Action:**
        - VERIFY ELEMENT TYPE: Before suggesting 'input', check the XML context for the target element. Ensure its `class` attribute indicates it is an editable field (e.g., `android.widget.EditText`, `android.widget.AutoCompleteTextView`, etc.).
        - DO NOT suggest 'input' for non-editable elements like `android.widget.TextView`, `android.widget.Button`, etc.
        - PARENT ELEMENT PRIORITY: If you see a non-editable text element (TextView) that appears to be part of an input field:
          1. Look for its parent container that has an editable class
          2. Use the parent's identifier instead of the child TextView
          3. Verify the parent is actually editable (class='android.widget.EditText' or similar)
          4. Only suggest 'input' if you find a proper editable parent
        - EDITABLE CLASS EXAMPLES:
          * android.widget.EditText
          * android.widget.AutoCompleteTextView
          * android.widget.TextInputEditText
          * android.widget.SearchView

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

        RESPONSE FORMAT: Return a JSON object with the following structure:
        {json_format_example}

        Example responses:
        {json_example_click}
        {json_example_input}
        {json_example_scroll}

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
        log_prompt = prompt.replace(xml_context, f"[XML Context Len:{len(xml_context)}]") if len(xml_context) > 1000 else prompt
        logging.debug(f"AI Prompt (XML potentially truncated):\n{log_prompt}")
        logging.info("-----------------------------")

        try:
            logging.debug("Requesting AI generation...")
            content_parts = [prompt, image_part]

            if self.use_chat and self.chat:
                response = self.chat.send_message(content_parts, safety_settings=self.safety_settings)
                
                if len(self.chat.history) > self.max_history:
                    excess = len(self.chat.history) - self.max_history
                    self.chat.history = self.chat.history[:1] + self.chat.history[1+excess:]
                    logging.debug(f"Trimmed chat history to {self.max_history} entries")
            else:
                response = self.model.generate_content(content_parts, safety_settings=self.safety_settings)

            elapsed_time = time.time() - start_time
            logging.info(f"Total AI Processing Time: {elapsed_time:.2f} seconds")

            # Ensure usage_metadata and its attributes exist before accessing them
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                logging.info(f"Tokens used: Prompt={getattr(response.usage_metadata, 'prompt_token_count', 'N/A')}, Candidates={getattr(response.usage_metadata, 'candidates_token_count', 'N/A')}, Total={getattr(response.usage_metadata, 'total_token_count', 'N/A')}")
            else:
                logging.warning("Usage metadata not available in AI response.")

            if not response.candidates:
                logging.error("AI response has no candidates.")
                self._log_empty_response_details(response)
                return None

            candidate = response.candidates[0]
            if candidate.finish_reason != genai.protos.Candidate.FinishReason.STOP:
                logging.warning(f"AI generation finished abnormally.")
                self._log_empty_response_details(response)
                return None

            if not candidate.content or not candidate.content.parts:
                logging.warning("AI response candidate has no content parts.")
                self._log_empty_response_details(response) 
                return None
            
            raw_response_text = response.text
            if raw_response_text is None or not raw_response_text.strip():
                logging.error("AI returned empty response (text is None or empty after strip, though parts may exist).")
                self._log_empty_response_details(response)
                return None
            
            raw_response_text = raw_response_text.strip()

            json_str = raw_response_text
            if json_str.startswith("```"): 
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"): json_str = json_str[4:]
            json_str = json_str.strip()

            try:
                parsed_data: Any = json.loads(json_str)
                action_data: Optional[Dict] = None

                if isinstance(parsed_data, list):
                    if len(parsed_data) == 1 and isinstance(parsed_data[0], dict):
                        logging.warning("AI returned response wrapped in a list '[{...}]', extracting the inner dictionary.")
                        action_data = parsed_data[0]
                    else:
                        logging.error(f"AI returned a list, but not the expected format [dict] (length={len(parsed_data)}): {parsed_data}")
                        return None
                elif isinstance(parsed_data, dict):
                    action_data = parsed_data
                else:
                    logging.error(f"AI response parsed, but is neither a list nor a dict. Type: {type(parsed_data)}, Data: {parsed_data}")
                    return None

                if action_data is None:
                    logging.error("Internal logic error: action_data is None after parsing/extraction checks.")
                    return None

                if "action" not in action_data:
                    logging.error(f"Extracted JSON object lacks required 'action' key: {action_data}")
                    return None

                action_type = action_data.get("action")
                if action_type in ["click", "input"] and not action_data.get("target_identifier"):
                     logging.error(f"AI response for action '{action_type}' missing required 'target_identifier'. Data: {action_data}")
                     return None

                if action_type == "input" and action_data.get("input_text") is None:
                    logging.error(f"AI response for action 'input' missing required 'input_text' (was None). Data: {action_data}")
                    return None

                bbox = action_data.get("target_bounding_box")
                if bbox:
                    if not isinstance(bbox, dict) or \
                       "top_left" not in bbox or not isinstance(bbox["top_left"], list) or len(bbox["top_left"]) != 2 or \
                       "bottom_right" not in bbox or not isinstance(bbox["bottom_right"], list) or len(bbox["bottom_right"]) != 2:
                        logging.warning(f"AI provided 'target_bounding_box' but format is invalid: {bbox}. Nullifying bbox for this action.")
                        action_data["target_bounding_box"] = None

                logging.info(f"AI Suggested Action: {action_data.get('action')} - Target Identifier: {action_data.get('target_identifier')}")
                logging.debug(f"AI Full Parsed & Validated Suggestion: {action_data}")
                return action_data

            except json.JSONDecodeError as json_e:
                logging.error(f"Failed to parse AI response as JSON: {json_e}")
                logging.error(f"Problematic JSON string received from AI: '{json_str}'")
                return None
            except Exception as parse_err:
                logging.error(f"Error during JSON processing or validation: {parse_err}", exc_info=True)
                return None

        except Exception as e:
            logging.error(f"Unhandled error during AI interaction or response processing: {e}", exc_info=True)
            return None
