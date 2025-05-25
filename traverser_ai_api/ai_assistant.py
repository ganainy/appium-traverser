import google.generativeai as genai
from google.generativeai.client import configure # Corrected import
from google.generativeai.generative_models import GenerativeModel # Corrected import
from google.generativeai.types import GenerationConfig
import logging
import time
from typing import Any, Dict, List, Optional 
import json
from PIL import Image
import io
from typing import Optional, Dict, List, Any
from . import config
import time
import re
import os
from dotenv import load_dotenv
from google.ai import generativelanguage as glm
from google.ai.generativelanguage import Schema, Type as GLMType

load_dotenv()

class AIAssistant:
    """
    Handles interactions with the Generative AI model, enforcing structured JSON output
    for actions using an OpenAPI-like schema.
    """

    @staticmethod
    def _get_action_response_schema() -> Schema:
        """
        Defines the schema for the AI's action response, similar to an OpenAPI schema.
        The model's output will be forced to adhere to this structure.
        """
        # Schema for the bounding box (optional part of the main action)
        # This defines the structure if a bounding box is provided.
        _bounding_box_properties = {
            'top_left': Schema(
                type=GLMType.ARRAY,
                items=Schema(type=GLMType.NUMBER), # Expects array of numbers [y, x]
                description="[y1, x1] coordinates for the top-left corner of the bounding box."
            ),
            'bottom_right': Schema(
                type=GLMType.ARRAY,
                items=Schema(type=GLMType.NUMBER), # Expects array of numbers [y, x]
                description="[y2, x2] coordinates for the bottom-right corner of the bounding box."
            )
        }
        _bounding_box_required = ['top_left', 'bottom_right']
        _bounding_box_description = "Bounding box coordinates of the target element."

        # Main action schema
        action_schema = Schema(
            type=GLMType.OBJECT,
            description="Describes the next UI action to perform based on screen analysis. Output MUST strictly adhere to this schema.",
            properties={
                'action': Schema(
                    type=GLMType.STRING,
                    enum=["click", "input", "scroll_up", "scroll_down", "back"],
                    description="The type of action to perform."
                ),
                'target_identifier': Schema(
                    type=GLMType.STRING,
                    description="Identifier of the target element (e.g., resource-id, content-desc, or visible text). "
                                "This is crucial for 'click' and 'input' actions. Should be null if not applicable (e.g., for 'scroll' or 'back').",
                    nullable=True # Allows the model to explicitly set this to null
                ),
                'target_bounding_box': Schema(
                    type=GLMType.OBJECT,
                    properties=_bounding_box_properties,
                    required=_bounding_box_required,
                    description=_bounding_box_description + " This entire object is optional and can be null.",
                    nullable=True # Makes the target_bounding_box field itself optional
                ),
                'input_text': Schema(
                    type=GLMType.STRING,
                    description="Text to input into a field. Required for 'input' action. Should be null if not applicable.",
                    nullable=True # Allows null if action is not 'input'
                ),
                'reasoning': Schema(
                    type=GLMType.STRING,
                    description="A brief explanation and thought process for choosing this specific action."
                )
            },
            required=['action', 'reasoning'] # These fields are always mandatory in the response
        )
        return action_schema

    def __init__(self, api_key: str, model_name: Optional[str] = None, safety_settings: Optional[Dict] = None):
        """Initialize the AI Assistant with strict configuration requirements.

        Args:
            api_key (str): The Gemini API key
            model_name (Optional[str]): The specific model to use (e.g., 'flash-latest-fast' from config.GEMINI_MODELS)
            safety_settings (Optional[Dict]): Safety settings for content generation (will be overridden by config.AI_SAFETY_SETTINGS if present)

        Raises:
            ValueError: If required configurations are missing or invalid
        """
        if not api_key:
            raise ValueError("API key is required")

        # Model alias (e.g., 'flash-latest-fast') is required and must come from config
        model_alias = model_name or getattr(config, 'DEFAULT_MODEL_TYPE')
        if not model_alias:
            raise ValueError("Model alias must be provided either directly or through config.DEFAULT_MODEL_TYPE")

        available_model_aliases = list(getattr(config, 'GEMINI_MODELS', {}).keys())
        if not available_model_aliases:
            raise ValueError("GEMINI_MODELS must be defined in config and contain model configurations.")

        if model_alias not in available_model_aliases:
            raise ValueError(f"Invalid model alias '{model_alias}'. Available aliases: {', '.join(available_model_aliases)}")

        model_config_from_file = getattr(config, 'GEMINI_MODELS', {}).get(model_alias)
        if not model_config_from_file or not isinstance(model_config_from_file, dict):
            raise ValueError(f"Model configuration for alias '{model_alias}' not found or is not a dictionary in GEMINI_MODELS config.")

        actual_model_name = model_config_from_file.get('name')
        if not actual_model_name:
            raise ValueError(f"The 'name' field (actual model identifier) is missing in the configuration for alias '{model_alias}'.")
        
        self.model_alias = model_alias 
        self.actual_model_name = actual_model_name 
        self.api_key = api_key
        
        # Prioritize AI_SAFETY_SETTINGS from config file if available
        config_safety_settings = getattr(config, 'AI_SAFETY_SETTINGS', None)
        raw_safety_settings_source = config_safety_settings if config_safety_settings is not None else safety_settings or {}
        
        if not isinstance(raw_safety_settings_source, dict):
            raise ValueError("Safety settings must be a dictionary.")
        
        self.processed_safety_settings = []
        for key, value in raw_safety_settings_source.items():
            try:
                self.processed_safety_settings.append({'category': key, 'threshold': value})
            except Exception as e: # More general exception for safety setting processing
                raise ValueError(f"Error processing safety setting key '{key}' or value '{value}': {e}. Ensure they match Google AI SDK's expected format.")
        
        if not self.processed_safety_settings and raw_safety_settings_source:
             logging.warning("Safety settings were provided but could not be processed into the required list-of-dicts format. Proceeding without them.")
        elif not raw_safety_settings_source:
            logging.info("No safety settings provided. Proceeding with API defaults.")

        try:
            configure(api_key=api_key)
            
            self.response_schema = self._get_action_response_schema()

            generation_config_dict = model_config_from_file.get('generation_config')
            if not generation_config_dict or not isinstance(generation_config_dict, dict):
                raise ValueError(f"Generation configuration not found or is not a dictionary for model alias {self.model_alias}")
            
            required_fields = ['temperature', 'top_p', 'top_k', 'max_output_tokens']
            missing_fields = [field for field in required_fields if field not in generation_config_dict]
            if missing_fields:
                raise ValueError(f"Missing required generation config fields for alias '{self.model_alias}': {', '.join(missing_fields)}")
            
            sdk_generation_config = GenerationConfig(
                temperature=generation_config_dict['temperature'],
                top_p=generation_config_dict['top_p'],
                top_k=generation_config_dict['top_k'],
                max_output_tokens=generation_config_dict['max_output_tokens'],
                candidate_count=generation_config_dict.get('candidate_count', 1),
                stop_sequences=generation_config_dict.get('stop_sequences', []),
                response_mime_type="application/json", 
                response_schema=self.response_schema 
            )
            
            self.model = GenerativeModel(
                model_name=self.actual_model_name, 
                generation_config=sdk_generation_config,
                safety_settings=self.processed_safety_settings 
            )
            
            logging.info(f"AI Assistant initialized with model alias: {self.model_alias} (actual: {self.actual_model_name})")
            logging.info(f"Model description: {model_config_from_file.get('description', 'No description available.')}")
            logging.info(f"Structured JSON output schema is ENABLED (response_mime_type='application/json').")
            if self.processed_safety_settings:
                logging.info(f"Applied safety settings: {self.processed_safety_settings}")
            else:
                logging.info("No custom safety settings applied; using API defaults.")

            self.use_chat = getattr(config, 'USE_CHAT_MEMORY', False) 
            if self.use_chat is None:
                raise ValueError("USE_CHAT_MEMORY must be defined in config (True or False)")
                
            if self.use_chat:
                try:
                    # For chat, safety settings are inherited from the model.
                    self.chat = self.model.start_chat(history=[])
                    self.max_history = getattr(config, 'MAX_CHAT_HISTORY', 10) 
                    if self.max_history is None:
                        raise ValueError("MAX_CHAT_HISTORY must be defined in config (integer)")
                    logging.info(f"Chat memory enabled (max history: {self.max_history} exchanges)")
                except Exception as e:
                    logging.warning(f"Failed to initialize chat for model {self.actual_model_name}: {e}. Disabling chat memory.")
                    self.chat = None
                    self.use_chat = False
            else:
                self.chat = None
                logging.info("Chat memory is disabled.")
                
        except Exception as e:
            logging.error(f"Failed to initialize GenerativeModel or AIAssistant: {e}", exc_info=True)
            raise

    def _log_empty_response_details(self, response) -> None:
        """Helper to log details when an AI response is considered empty or problematic."""
        logging.info("Detailed AI Response Analysis:")
        try:
            if not response:
                logging.warning("  Response object itself is None.")
                return

            # Log basic response attributes
            for attr in ["prompt_feedback", "candidates", "text", "usage_metadata"]:
                if hasattr(response, attr):
                    value = getattr(response, attr)
                    if value is not None:
                        if attr == "candidates" and value:
                            candidate = value[0]
                            logging.info(f"  First Candidate Details:")
                            # Log candidate details
                            for c_attr in ["finish_reason", "safety_ratings", "content"]:
                                if hasattr(candidate, c_attr):
                                    c_value = getattr(candidate, c_attr)
                                    if c_value is not None:
                                        if c_attr == "content" and hasattr(c_value, "parts"):
                                            for i, part in enumerate(c_value.parts):
                                                logging.info(f"    Content Part {i}: {type(part).__name__}")
                                                if hasattr(part, "text"):
                                                    text = part.text[:300] + ("..." if len(part.text) > 300 else "")
                                                    logging.info(f"      Text: {text}")
                                        else:
                                            logging.info(f"    {c_attr}: {c_value}")
                        elif attr == "usage_metadata":
                            logging.info("  Usage Metadata:")
                            for m_attr in ["prompt_token_count", "candidates_token_count", "total_token_count"]:
                                if hasattr(value, m_attr):
                                    logging.info(f"    {m_attr}: {getattr(value, m_attr)}")
                        else:
                            logging.info(f"  {attr}: {value}")
                    else:
                        logging.info(f"  {attr} is None")
                else:
                    logging.info(f"  {attr} attribute not found")
        except Exception as e:
            logging.error(f"Error analyzing response details: {e}", exc_info=True)


    def _prepare_image_part(self, screenshot_bytes: bytes) -> Optional[Image.Image]:
        try:
            return Image.open(io.BytesIO(screenshot_bytes))
        except Exception as e:
            logging.error(f"Failed to load image for AI: {e}")
            return None

    def _build_prompt(self, xml_context: str, previous_actions: List[str], available_actions: List[str], current_screen_visit_count: int, current_composite_hash: str) -> str:
        """Build the prompt for the AI model with all necessary context and instructions."""
        action_descriptions = {
            "click": "Visually identify and select an interactive element. Provide its best identifier (resource-id, content-desc, or text).",
            "input": "Visually identify a text input field (e.g., class='android.widget.EditText'). Provide its best identifier AND the text to input. **CRITICAL: ONLY suggest 'input' for elements designed for text entry.**",
            "scroll_down": "Scroll the view downwards.",
            "scroll_up": "Scroll the view upwards.",
            "back": "Navigate back using the system back button."
        }
        action_list_str = "\n".join([f"- {a}: {action_descriptions.get(a, '')}" for a in available_actions])
        history_str = "\n".join([f"- {pa}" for pa in previous_actions]) if previous_actions else "None"

        visit_context = f"CURRENT SCREEN CONTEXT:\n- Hash: {current_composite_hash}\n- Visit Count (this session): {current_screen_visit_count}"
        visit_instruction = ""
        loop_threshold = getattr(config, 'LOOP_DETECTION_VISIT_THRESHOLD', 3)
        
        def analyze_action_history(actions: List[str]) -> dict:
            if not actions:
                return {"repeated_actions": [], "last_unique_actions": [], "is_looping": False}
            action_sequence = []
            for action in actions:
                if "input" in action.lower():
                    action_sequence.append(("input", action))
                elif "click" in action.lower():
                    action_sequence.append(("click", action))
            last_actions = action_sequence[-6:]
            is_looping = False
            repeated_actions = []
            if len(last_actions) >= 4:
                action_types = [a[0] for a in last_actions]
                if action_types.count(action_types[-1]) > 2:
                    is_looping = True
                    repeated_actions.append(action_types[-1])
                if len(last_actions) >= 4 and all(a == ("input", "click") for a in zip(action_types[::2], action_types[1::2])):
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
        - Screen visited {current_screen_visit_count} times. Repeated: {', '.join(action_analysis['repeated_actions']) if action_analysis['repeated_actions'] else 'None'}. Tried: {', '.join(action_analysis['last_unique_actions'])}.
        REQUIRED ACTION CHANGES:
        1. DO NOT repeat failed action sequences.
        2. If input-click pattern fails, try: Different input values, alternative elements, navigation (back, menu), scroll.
        3. On error/validation screens: Adjust based on error, try alternative paths, look for skip/later options.
        4. Prioritize untried actions.
        """

        test_email = os.environ.get("TEST_EMAIL", "test.user@example.com")
        test_password = os.environ.get("TEST_PASSWORD", "Str0ngP@ssw0rd!")
        test_name = os.environ.get("TEST_NAME", "Test User")

        input_value_guidance = f"""
        **CRUCIAL: Input Value Guidance:**
        - Email/Username: "{test_email}"
        - Password: "{test_password}"
        - Name: "{test_name}"
        - Other fields: Use realistic, context-appropriate test data.
        - CAPTCHA/Verification: Use VISIBLE text. If fails, try alternatives/refresh.
        - AVOID generic placeholders (e.g., "test", "input") unless no context.
        """

        external_package_avoidance_guidance = """
        **CRUCIAL: External Package Avoidance:**
        - AVOID actions navigating away from the current app (e.g., opening mail, browser for help, external sharing).
        - Prioritize actions within the current app. If an action seems external, choose an in-app alternative.
        """

        json_format_instruction = """
        **RESPONSE FORMAT (Strict JSON Schema Enforced by API):**
        Your response MUST be a JSON object adhering to the predefined schema. The API will validate this.
        Key fields (refer to schema for full details):
        - `action`: (string, enum) The action to take (e.g., "click", "input"). REQUIRED.
        - `target_identifier`: (string | null) Identifier for "click"/"input" (e.g., resource-id, content-desc, text value). Crucial if applicable, otherwise null.
        - `target_bounding_box`: (object | null) Optional. Coordinates `{"top_left": [y,x], "bottom_right": [y,x]}`. Null if not applicable/determinable.
        - `input_text`: (string | null) Text for "input" action. Required if action is "input", otherwise null.
        - `reasoning`: (string) Your brief explanation for choosing this action. REQUIRED.

        Example of a valid JSON response (structure is enforced):
        ```json
        {
            "action": "input",
            "target_identifier": "com.example.app:id/email_field",
            "target_bounding_box": null,
            "input_text": "test.user@example.com",
            "reasoning": "Identified the email input field and entering the provided test email."
        }
        ```
        Another example:
        ```json
        {
            "action": "scroll_down",
            "target_identifier": null,
            "target_bounding_box": null,
            "input_text": null,
            "reasoning": "The current screen content has been reviewed, scrolling to find more interactive elements or information."
        }
        ```
        """

        prompt = f"""
        You are an expert Android app tester. Your goal is to explore systematically by performing ONE logical action.
        You receive a screenshot and XML layout. Prioritize PROGRESSION and IN-APP exploration.
        **IMPORTANT: For 'click'/'input', the `target_identifier` field in JSON is crucial. Provide its actual value (e.g., "ContinueButton", "com.app:id/submit").**
        Do NOT wrap identifiers in quotes or descriptive text within the value itself: CORRECT `target_identifier`: "Login", INCORRECT: 'text="Login"'.

        {visit_context}

        CONTEXT:
        1. Screenshot: Provided as image.
        2. XML Layout: Provided below. Use for identifiers and element states (class, enabled, clickable).
        3. Previous Actions Taken *From This Screen*:
        {history_str}

        TASK:
        Analyze the screenshot and XML. Identify the BEST SINGLE action to progress or explore **within the current application**. Prioritize discovering NEW screens and features.

        {visit_instruction}

        {external_package_avoidance_guidance}

        **CRUCIAL: Progression Buttons (Next, Continue, Save, etc.):**
        - CHECK PREREQUISITES: Verify in XML for identifier and `enabled="true"`. Visually confirm.
        - IF DISABLED: Perform the prerequisite action first (e.g., fill a required field).
        - PRIORITIZE PREREQUISITES over clicking a disabled button.

        {input_value_guidance}

        **CRUCIAL: 'input' Action:**
        - VERIFY ELEMENT TYPE: Ensure XML class is editable (e.g., `android.widget.EditText`).
        - DO NOT suggest 'input' for non-editable elements (TextView, Button).
        - PARENT ELEMENT: If a non-editable text element is part of a larger input field, use the editable parent's identifier if available.
        - COMMON EDITABLE CLASSES: `android.widget.EditText`, `android.widget.AutoCompleteTextView`, `android.widget.TextInputEditText`, `android.widget.SearchView`.

        General Action Priorities:
        1. Fulfill prerequisites for disabled progression buttons.
        2. Click enabled progression buttons.
        3. Explore elements related to core app functions: Privacy, Terms, Data Protection, Account, Profile, Register, Login, Consent, Settings.
        4. Explore other interactive elements likely leading to NEW areas (especially if visit count is high or stuck).
        5. Input text if required/relevant for progression, following the Input Value Guidance.
        6. Scroll if more content seems available OR if stuck/looping.
        7. Use 'back' judiciously if stuck or to return from a detail view (avoid if it completes a loop back to the same stuck state).

        Choose ONE action from the available list:
        {action_list_str}

        {json_format_instruction}

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
        # Prepare the image
        image_part = self._prepare_image_part(screenshot_bytes)
        if not image_part:
            logging.error("Failed to prepare image for AI; cannot proceed.")
            return None

        start_time = time.time()
        try:
            # Build the prompt with context and instructions
            prompt = self._build_prompt(
                xml_context, previous_actions, available_actions,
                current_screen_visit_count, current_composite_hash
            )
            content_parts = [prompt, image_part]

            # Request generation
            logging.debug("Requesting AI generation with structured JSON output...")
            try:
                if self.use_chat and self.chat:
                    response = self.chat.send_message(
                        content_parts,
                        # Safety settings are inherited from the model for chat messages
                    )
                    # Trim chat history if it exceeds max_history
                    if len(self.chat.history) > self.max_history * 2:
                        num_exchanges_to_trim = (len(self.chat.history) // 2) - self.max_history
                        if len(self.chat.history) > 2:
                            self.chat.history = self.chat.history[2 * num_exchanges_to_trim:]
                            logging.debug(f"Trimmed chat history to approximately {len(self.chat.history)//2} exchanges")
                else:
                    # Safety settings are part of the model's initialization.
                    response = self.model.generate_content(
                        content_parts,
                    )

                elapsed_time = time.time() - start_time
                logging.info(f"Total AI Processing Time: {elapsed_time:.2f} seconds")
                
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    logging.info("Token Usage:")
                    logging.info(f"  Prompt: {getattr(response.usage_metadata, 'prompt_token_count', 'N/A')}")
                    logging.info(f"  Candidates: {getattr(response.usage_metadata, 'candidates_token_count', 'N/A')}")
                    logging.info(f"  Total: {getattr(response.usage_metadata, 'total_token_count', 'N/A')}")

                # Validate response
                if not hasattr(response, 'candidates') or not response.candidates:
                    logging.error("AI response contains no candidates")
                    self._log_empty_response_details(response)
                    return None

                candidate = response.candidates[0]
                
                # Basic finish reason check
                if hasattr(candidate, 'finish_reason'):
                    reason = str(candidate.finish_reason)
                    if 'STOP' not in reason:
                        logging.warning(f"AI generation finished abnormally (Reason: {reason})")
                        self._log_empty_response_details(response)
                        return None

                if not hasattr(candidate, 'content') or not candidate.content or \
                   not hasattr(candidate.content, 'parts') or not candidate.content.parts:
                    logging.error("AI response candidate lacks valid content/parts")
                    self._log_empty_response_details(response)
                    return None
                
                # Get the JSON response
                first_part = candidate.content.parts[0]
                if not hasattr(first_part, 'text') or not first_part.text:
                    logging.error("AI response first part lacks text content")
                    self._log_empty_response_details(response)
                    return None
                
                raw_json_text = first_part.text
                
                # Clean the JSON text
                json_str_to_parse = raw_json_text.strip()
                if json_str_to_parse.startswith("```"):
                    logging.debug(f"Stripping markdown from response: '{json_str_to_parse[:100]}...'")
                    json_str_to_parse = re.sub(r"^```(?:json)?\s*", "", json_str_to_parse, flags=re.IGNORECASE)
                    json_str_to_parse = re.sub(r"\s*```$", "", json_str_to_parse)
                    json_str_to_parse = json_str_to_parse.strip()
                
                if not json_str_to_parse:
                    logging.error("AI response: Empty JSON string after cleaning")
                    self._log_empty_response_details(response)
                    return None

                try:
                    # Parse and validate the JSON
                    parsed_data = json.loads(json_str_to_parse)
                    
                    if not isinstance(parsed_data, dict):
                        logging.error(f"AI response not a dictionary: {type(parsed_data)}")
                        return None
                    
                    action_data = parsed_data

                    # Validate required fields
                    if "action" not in action_data or "reasoning" not in action_data:
                        logging.error("Missing required fields in response")
                        return None

                    # Validate action-specific fields
                    action_type = action_data.get("action")
                    if action_type in ["click", "input"] and not action_data.get("target_identifier"):
                         logging.warning(f"Missing target_identifier for {action_type}")

                    if action_type == "input" and action_data.get("input_text") is None:
                        logging.warning("Missing input_text for input action")

                    # Validate bounding box if present
                    bbox = action_data.get("target_bounding_box")
                    if bbox is not None:
                        if not (isinstance(bbox, dict) and \
                                "top_left" in bbox and isinstance(bbox["top_left"], list) and len(bbox["top_left"]) == 2 and \
                                "bottom_right" in bbox and isinstance(bbox["bottom_right"], list) and len(bbox["bottom_right"]) == 2 and \
                                all(isinstance(coord, (int, float)) 
                                    for coord_pair in [bbox["top_left"], bbox["bottom_right"]] 
                                    for coord in coord_pair)):
                            logging.warning(f"Invalid bounding box format: {bbox}")
                            action_data["target_bounding_box"] = None
                    
                    logging.info(f"AI Action: {action_type}, Target: {action_data.get('target_identifier')}, Input: {action_data.get('input_text')}")
                    return action_data

                except json.JSONDecodeError as json_err:
                    logging.error(f"JSON parse error: {json_err}")
                    self._log_empty_response_details(response)
                    return None
                except Exception as parse_err:
                    logging.error(f"Validation error: {parse_err}")
                    return None

            except Exception as api_err:
                logging.error(f"AI API error: {api_err}")
                if "api key" in str(api_err).lower():
                    logging.critical("API key error - check configuration")
                return None

        except Exception as e:
            logging.error(f"General error: {e}", exc_info=True)
            return None
