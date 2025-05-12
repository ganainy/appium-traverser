import google.generativeai as genai
import logging
import json
from PIL import Image
import io
from typing import Optional, Dict, List, Any
from . import config
import time
import re
import os # Added
from dotenv import load_dotenv # Added

load_dotenv() # Added: Load environment variables from .env file

class AIAssistant:
    """Handles interactions with the Generative AI model."""

    def __init__(self, api_key: str, model_name: str = None, safety_settings: Dict = None):
        if not api_key:
            raise ValueError("Gemini API key is required.")
        try:
            genai.configure(api_key=api_key)
            
            model_type = model_name or getattr(config, 'DEFAULT_MODEL_TYPE', 'pro-vision')
            model_config = getattr(config, 'GEMINI_MODELS', {}).get(model_type)
            
            if not model_config:
                logging.warning(f"Model type '{model_type}' not found in config, using default pro-vision")
                model_config = {'name': 'gemini-pro-vision'} # Fallback, though pro-vision might not be ideal for chat
            
            self.model = genai.GenerativeModel(
                model_config['name'],
                generation_config=model_config.get('generation_config')
            )
            
            logging.info(f"AI Assistant initialized with model: {model_config['name']}")
            logging.info(f"Model description: {model_config.get('description', 'Standard configuration')}")
            
            self.safety_settings = safety_settings
            
            self.use_chat = getattr(config, 'USE_CHAT_MEMORY', False)
            if self.use_chat:
                # Check if model supports chat (multi-turn conversations)
                # Basic check: Vision models often don't support .start_chat directly, non-vision 'pro' models do.
                # A more robust check might involve inspecting model capabilities if API provides it.
                if "vision" not in model_config['name']:
                    self.chat = self.model.start_chat(history=[])
                    self.max_history = getattr(config, 'MAX_CHAT_HISTORY', 10)
                    logging.info(f"Chat memory enabled (max history: {self.max_history})")
                else:
                    logging.warning(f"Model {model_config['name']} may not support chat history. Disabling chat memory.")
                    self.chat = None
                    self.use_chat = False # Force disable
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
                # Convert enum int to name if possible
                finish_reason_name = finish_reason_value
                if isinstance(finish_reason_value, int):
                    try: finish_reason_name = genai.protos.Candidate.FinishReason(finish_reason_value).name
                    except ValueError: pass # Keep as int if unknown enum

                logging.info(f"  Candidate Finish Reason: {finish_reason_name} ({finish_reason_value})")
                
                if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                    logging.info("  Candidate Safety Ratings:")
                    for rating in candidate.safety_ratings:
                        category_val = getattr(rating, 'category', 'N/A')
                        probability_val = getattr(rating, 'probability', 'N/A')
                        category_name = category_val
                        probability_name = probability_val
                        if isinstance(category_val, int):
                            try: category_name = genai.protos.HarmCategory(category_val).name
                            except ValueError: pass
                        if isinstance(probability_val, int):
                            try: probability_name = genai.protos.HarmProbability(probability_val).name
                            except ValueError: pass
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
            
            if hasattr(response, 'text'): # For non-chat responses or simple text access
                logging.info(f"  Raw response.text (stripped): '{response.text.strip() if response.text is not None else '<None>'}'")

            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                logging.info(f"Usage Metadata: Prompt Tokens={getattr(response.usage_metadata, 'prompt_token_count', 'N/A')}, Candidates Tokens={getattr(response.usage_metadata, 'candidates_token_count', 'N/A')}, Total Tokens={getattr(response.usage_metadata, 'total_token_count', 'N/A')}")
            else:
                logging.warning("Usage metadata not available in AI response.")

        except Exception as e_details:
            logging.error(f"  Error during detailed AI response analysis: {e_details}", exc_info=True)

    def _prepare_image_part(self, screenshot_bytes: bytes) -> Optional[Image.Image]:
        try:
            return Image.open(io.BytesIO(screenshot_bytes))
        except Exception as e:
            logging.error(f"Failed to load image for AI: {e}")
            return None

    def _build_prompt(self, xml_context: str, previous_actions: List[str], available_actions: List[str], current_screen_visit_count: int, current_composite_hash: str) -> str:
        action_descriptions = {
            "click": "Visually identify and select an interactive element. Provide its best identifier (resource-id, content-desc, or text).",
            "input": "Visually identify a text input field (e.g., class=\'android.widget.EditText\'). Provide its best identifier AND the text to input. **CRITICAL: ONLY suggest \'input\' for elements designed for text entry.**",
            "scroll_down": "Scroll the view downwards.",
            "scroll_up": "Scroll the view upwards.",
            "back": "Navigate back using the system back button."
        }
        action_list_str = "\\n".join([f"- {a}: {action_descriptions.get(a, '')}" for a in available_actions])
        history_str = "\\n".join([f"- {pa}" for pa in previous_actions]) if previous_actions else "None"

        visit_context = f"CURRENT SCREEN CONTEXT:\\n- Hash: {current_composite_hash}\\n- Visit Count (this session): {current_screen_visit_count}"
        visit_instruction = ""
        loop_threshold = getattr(config, 'LOOP_DETECTION_VISIT_THRESHOLD', 3)
        
        # Enhanced loop detection and avoidance logic
        def analyze_action_history(actions: List[str]) -> dict:
            if not actions:
                return {"repeated_actions": [], "last_unique_actions": [], "is_looping": False}
            
            action_sequence = []
            for action in actions:
                if "input" in action.lower():
                    action_sequence.append(("input", action))
                elif "click" in action.lower():
                    action_sequence.append(("click", action))
            
            # Look for repeating patterns in last 6 actions
            last_actions = action_sequence[-6:]
            is_looping = False
            repeated_actions = []
            
            if len(last_actions) >= 4:
                # Check if same action is being repeated
                action_types = [a[0] for a in last_actions]
                if action_types.count(action_types[-1]) > 2:
                    is_looping = True
                    repeated_actions.append(action_types[-1])
                
                # Check for input-click patterns
                if len(last_actions) >= 4:
                    if all(a == ("input", "click") for a in zip(action_types[::2], action_types[1::2])):
                        is_looping = True
                        repeated_actions.extend(["input-click pattern"])
            
            return {
                "repeated_actions": repeated_actions,
                "last_unique_actions": list(set(a[0] for a in last_actions)),
                "is_looping": is_looping
            }
        
        action_analysis = analyze_action_history(previous_actions)
        if current_screen_visit_count > loop_threshold or action_analysis["is_looping"]:
            visit_instruction = f"""
        **CRITICAL - LOOP DETECTED:**
        - Screen visited {current_screen_visit_count} times
        - Repeated actions detected: {', '.join(action_analysis['repeated_actions']) if action_analysis['repeated_actions'] else 'None'}
        - Previous unique actions tried: {', '.join(action_analysis['last_unique_actions'])}
        
        REQUIRED ACTION CHANGES:
        1. DO NOT repeat the same action sequence that failed before
        2. If input-click pattern is failing, try:
           - Different input values
           - Alternative interactive elements
           - Navigation options (back, menu)
           - Scroll to find new elements
        3. If on an error/validation screen:
           - Look for error messages and adjust accordingly
           - Consider alternative paths or return to previous screens
           - Check for "skip" or "later" options
        4. Prioritize actions that haven't been tried yet
        """

        test_email = os.environ.get("TEST_EMAIL")
        test_password = os.environ.get("TEST_PASSWORD")
        test_name = os.environ.get("TEST_NAME")

        input_value_guidance = f"""
        **CRUCIAL: Input Value Guidance:**
        - For specific fields, use these exact values:
            - Email/Username: "{test_email if test_email else ''}"
            - Password: "{test_password if test_password else ''}"
            - Name (First, Last, Full): "{test_name if test_name else ''}"
        - For other fields, use realistic-looking, contextually appropriate test data
        - For CAPTCHA/verification codes:
           - ONLY use exactly what is visible in the image
           - If multiple attempts fail, try alternative paths
           - Look for refresh/regenerate options
        - AVOID generic placeholders like "test", "input", "random string" unless no other context is available.
        """

        external_package_avoidance_guidance = """
        **CRUCIAL: External Package Avoidance:**
        - AVOID actions that navigate away from the current application to interact with other apps (e.g., opening a mail app to reset a password, opening a browser for help pages, or sharing content via external apps).
        - Prioritize actions that keep the interaction within the current application\'s main package. If an action seems to lead outside the app, choose an alternative that explores more features *within* the app.
        """

        json_format_example = """
        {
            "action": "click" | "input" | "scroll_up" | "scroll_down" | "back",
            "target_identifier": "element identifier (required for click/input, use resource-id, content-desc, or text value)",
            "target_bounding_box": {"top_left": [y1, x1], "bottom_right": [y2, x2]},
            "input_text": "text to input (required for input action)",
            "reasoning": "Brief explanation of why this action was chosen"
        }
        """
        prompt = f"""
        You are an expert Android app tester. Your goal is to explore systematically by performing ONE logical action.
        You get a screenshot and XML layout. Prioritize PROGRESSION and IN-APP exploration.
        **IMPORTANT: For \'click\'/\'input\', provide identifier (resource-id, content-desc, or text). ONLY the value.**
        CORRECT: "Continue", INCORRECT: \'text="Continue"\'.

        {visit_context}

        CONTEXT:
        1. Screenshot: Provided as image.
        2. XML Layout: Provided below. Use for identifiers and element states (class, enabled, clickable).
        3. Previous Actions Taken *From This Screen*:
        {history_str}

        TASK:
        Analyze screenshot/XML. Identify BEST SINGLE action to progress/explore **within the current application**. Prioritize NEW screens and features.

        {visit_instruction}

        {external_package_avoidance_guidance}

        **CRUCIAL: Progression Buttons (Next, Continue, Save):**
        - CHECK PREREQUISITES: Check XML for identifier and `enabled="true"`. Visually verify.
        - IF DISABLED: Perform prerequisite action first.
        - PRIORITIZE PREREQUISITES.

        {input_value_guidance}

        **CRUCIAL: \\\'input\\\' Action:**
        - VERIFY ELEMENT TYPE: Ensure XML class is editable (e.g., `android.widget.EditText`).
        - DO NOT suggest \\\'input\\\' for non-editable elements (TextView, Button).
        - PARENT ELEMENT: If a non-editable text element is part of an input field, use its editable parent\\\'s identifier.
        - EDITABLE CLASSES: `android.widget.EditText`, `android.widget.AutoCompleteTextView`, `android.widget.TextInputEditText`, `android.widget.SearchView`.

        General Priorities:
        1. Fulfill prerequisites for disabled progression buttons.
        2. Click enabled progression buttons.
        3. Explore elements related to: Privacy, Terms, Data Protection, Account, Profile, Register, Login, Consent.
        4. Explore other interactive elements likely leading to NEW areas (especially if visit count is high).
        5. Input text if required/relevant, following the Input Value Guidance.
        6. Scroll if more content seems available OR if stuck/looping.
        7. Use \\\'back\\\' if stuck or to return from detail view (avoid if it completes a loop).

        Choose ONE action from:
        {action_list_str}

        RESPONSE FORMAT (JSON only):
        {json_format_example}

        XML CONTEXT:
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
        image_part = self._prepare_image_part(screenshot_bytes)
        if not image_part:
            logging.error("Failed to prepare image for AI.")
            return None

        start_time = time.time()
        try:
            prompt = self._build_prompt(
                xml_context, previous_actions, available_actions,
                current_screen_visit_count, current_composite_hash
            )
        except Exception as prompt_err:
             logging.error(f"Error building AI prompt: {prompt_err}", exc_info=True)
             return None

        content_parts = [prompt, image_part]
        # logging.debug(f"AI Prompt (XML potentially truncated):\n{prompt[:2000]}...") # Log snippet

        try:
            logging.debug("Requesting AI generation...")
            if self.use_chat and self.chat: # Check self.chat is not None
                response = self.chat.send_message(content_parts, safety_settings=self.safety_settings)
                if len(self.chat.history) > self.max_history * 2: # Trim more aggressively if it grows too large
                    excess = len(self.chat.history) - self.max_history
                    self.chat.history = self.chat.history[:1] + self.chat.history[1+excess:] # Keep first (system?) and latest
                    logging.debug(f"Aggressively trimmed chat history to ~{self.max_history} entries")
            else:
                response = self.model.generate_content(content_parts, safety_settings=self.safety_settings)

            elapsed_time = time.time() - start_time
            logging.info(f"Total AI Processing Time: {elapsed_time:.2f} seconds")
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                logging.info(f"Tokens: P={getattr(response.usage_metadata, 'prompt_token_count', 'N')}, C={getattr(response.usage_metadata, 'candidates_token_count', 'N')}, T={getattr(response.usage_metadata, 'total_token_count', 'N')}")

            if not hasattr(response, 'candidates') or not response.candidates:
                logging.error("AI response has no candidates.")
                self._log_empty_response_details(response)
                return None

            candidate = response.candidates[0]
            if candidate.finish_reason != genai.protos.Candidate.FinishReason.STOP:
                logging.warning(f"AI generation finished abnormally (Reason: {candidate.finish_reason}).")
                self._log_empty_response_details(response)
                return None

            if not hasattr(candidate, 'content') or not candidate.content or \
               not hasattr(candidate.content, 'parts') or not candidate.content.parts or \
               not hasattr(candidate.content.parts[0], 'text') or not candidate.content.parts[0].text:
                logging.error("AI response candidate lacks valid text content in the first part.")
                self._log_empty_response_details(response)
                return None
            
            raw_response_text = candidate.content.parts[0].text.strip()
            if not raw_response_text:
                logging.error("AI response text is empty after stripping.")
                self._log_empty_response_details(response)
                return None
            
            json_str = raw_response_text
            if json_str.startswith("```"): 
                json_str = re.sub(r"```json\s*|```", "", json_str) # More robust removal
            json_str = json_str.strip()

            try:
                parsed_data: Any = json.loads(json_str)
                action_data: Optional[Dict] = None

                if isinstance(parsed_data, list) and len(parsed_data) == 1 and isinstance(parsed_data[0], dict):
                    action_data = parsed_data[0]
                elif isinstance(parsed_data, dict):
                    action_data = parsed_data
                else:
                    logging.error(f"AI response parsed, but not dict or [dict]. Type: {type(parsed_data)}, Data: {parsed_data}")
                    return None

                if not action_data or "action" not in action_data:
                    logging.error(f"Extracted JSON object lacks 'action' key or is empty: {action_data}")
                    return None

                action_type = action_data.get("action")
                if action_type in ["click", "input"] and not action_data.get("target_identifier"):
                     logging.error(f"AI response for '{action_type}' missing 'target_identifier'. Data: {action_data}")
                     return None
                if action_type == "input" and action_data.get("input_text") is None: # Check for explicit None
                    logging.error(f"AI response for 'input' missing 'input_text'. Data: {action_data}")
                    return None
                
                # Validate bounding box structure if present
                bbox = action_data.get("target_bounding_box")
                if bbox:
                    if not (isinstance(bbox, dict) and \
                            "top_left" in bbox and isinstance(bbox["top_left"], list) and len(bbox["top_left"]) == 2 and \
                            "bottom_right" in bbox and isinstance(bbox["bottom_right"], list) and len(bbox["bottom_right"]) == 2 and \
                            all(isinstance(coord, (int, float)) for coord_pair in [bbox["top_left"], bbox["bottom_right"]] for coord in coord_pair)):
                        logging.warning(f"AI 'target_bounding_box' format invalid: {bbox}. Nullifying.")
                        action_data["target_bounding_box"] = None
                
                logging.info(f"AI Suggested Action: {action_data.get('action')} - Target: {action_data.get('target_identifier')}")
                # logging.debug(f"AI Full Parsed Suggestion: {action_data}") # Can be verbose
                return action_data

            except json.JSONDecodeError as json_e:
                logging.error(f"Failed to parse AI response as JSON: {json_e}. String: '{json_str}'")
                return None
            except Exception as parse_err:
                logging.error(f"Error during JSON processing/validation: {parse_err}", exc_info=True)
                return None

        except Exception as e:
            logging.error(f"Unhandled error during AI interaction: {e}", exc_info=True)
            # Check for specific API errors if possible (e.g., quota, auth)
            # This might depend on the structure of exceptions from google.generativeai
            if "API key not valid" in str(e):
                logging.critical("Gemini API key is invalid. Please check configuration.")
            return None