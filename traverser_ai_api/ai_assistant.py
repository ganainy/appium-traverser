import google.generativeai as genai
from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel
from google.generativeai.types import GenerationConfig
import logging
import time
from typing import Any, Dict, List, Optional
import json
from PIL import Image
import io
from . import config
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
                    description=_bounding_box_description + " This entire object can be null if bounds cannot be determined.",
                    nullable=True
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

            # Log response metadata
            if hasattr(response, "usage_metadata"):
                metadata = response.usage_metadata
                if metadata:
                    logging.info("  Usage Metadata:")
                    for m_attr in ["prompt_token_count", "candidates_token_count", "total_token_count"]:
                        if hasattr(metadata, m_attr):
                            logging.info(f"    {m_attr}: {getattr(metadata, m_attr)}")

            # Log candidate details if available
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                logging.info("  First Candidate Details:")
                
                # Log finish reason
                if hasattr(candidate, "finish_reason"):
                    logging.info(f"    finish_reason: {candidate.finish_reason}")
                
                # Log safety ratings
                if hasattr(candidate, "safety_ratings"):
                    logging.info(f"    safety_ratings: {candidate.safety_ratings}")
                
                # Log content parts
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    for i, part in enumerate(candidate.content.parts):
                        logging.info(f"    Content Part {i}: {type(part).__name__}")
                        if hasattr(part, "text"):
                            logging.info(f"      Text: {part.text}")

        except Exception as e:
            logging.error(f"Error analyzing response details: {e}", exc_info=True)

    def _prepare_image_part(self, screenshot_bytes: bytes) -> Optional[Image.Image]:
        try:
            return Image.open(io.BytesIO(screenshot_bytes))
        except Exception as e:
            logging.error(f"Failed to load image for AI: {e}")
            return None

    def _build_prompt(self, xml_context: str, previous_actions: List[str], available_actions: List[str], current_screen_visit_count: int, current_composite_hash: str) -> str:
        action_descriptions = {
            "click": "Visually identify and select an interactive element. Provide its best identifier (resource-id, content-desc, or text).",
            "input": "Visually identify a text input field (e.g., class='android.widget.EditText'). Provide its best identifier AND the text to input. **CRITICAL: ONLY suggest 'input' for elements designed for text entry.**",
            "scroll_down": "Scroll the view downwards.",
            "scroll_up": "Scroll the view upwards.",
            "back": "Navigate back using the system back button."
        }

        bounding_box_guidance = """
        **CRUCIAL: Bounding Box for 'click' and 'input' Actions (`target_bounding_box`):**
        Your goal is to provide `target_bounding_box` for 'click' and 'input' actions. Use the following prioritized methods:

        1.  **Extract from XML (Primary Method):**
            * First, examine the provided XML CONTEXT for the element matching your `target_identifier`.
            * If this XML element has a 'bounds' attribute (typically formatted like `bounds="[x1,y1][x2,y2]`), extract these coordinates.
            * Convert them to the required JSON format: `{"top_left": [y1, x1], "bottom_right": [y2, x2]}`.
                * **Important Coordinate Order:** Note that the XML might be `[x1,y1][x2,y2]`, but the JSON schema requires `top_left` as `[y1, x1]` and `bottom_right` as `[y2, x2]`. Ensure you map them correctly.
            * This is the preferred and generally most accurate method.

        2.  **Visually Estimate from Screenshot (Fallback Method):**
            * If the 'bounds' attribute is NOT found for your chosen `target_identifier` in the XML,
            * OR if the provided XML snippet is missing or doesn't seem to contain the specific element you're targeting,
            * OR if you strongly suspect the XML bounds are incorrect for the visible element,
            * THEN, you should attempt to visually estimate the bounding box of the target element directly from the provided screenshot.
            * Identify the top-left (y1, x1) and bottom-right (y2, x2) pixel coordinates of the element in the image.
            * The image origin (0,0) is the top-left corner. Y values increase downwards, and X values increase to the right.

        3.  **Use `null` (Last Resort):**
            * If, after attempting BOTH XML extraction AND visual estimation, you cannot confidently determine the bounding box for the chosen target element, set `target_bounding_box` to `null`.
            * For actions other than 'click' or 'input' (e.g., 'scroll', 'back'), `target_bounding_box` should ALWAYS be `null`.
        """

        json_format_instruction = f"""
        **RESPONSE FORMAT (Strict JSON Schema Enforced by API):**
        Your response MUST be a JSON object adhering to the predefined schema. The API will validate this.
        Key fields (refer to schema for full details):
        - `action`: (string, enum) The action to take (e.g., "click", "input"). REQUIRED.
        - `target_identifier`: (string | null) Identifier for "click"/"input" (e.g., resource-id, content-desc, text value). Crucial if applicable, otherwise null.
        - `target_bounding_box`: (object | null) For "click" and "input" actions, this is STRONGLY PREFERRED.
            1. Prioritize extracting from the 'bounds' attribute of the target element in the XML (ensure correct `[Y,X]` coordinate order: `{{"top_left": [y1,x1], "bottom_right": [y2,x2]}}`).
            2. If unavailable/unreliable in XML for the specific target, visually estimate from the screenshot.
            3. Use `null` only as a last resort if coordinates cannot be determined, or for non-click/input actions.
        - `input_text`: (string | null) Text for "input" action. Required if action is "input", otherwise null.
        - `reasoning`: (string) Your brief explanation for choosing this action, including how you determined the target and its bounding box if applicable. REQUIRED.

        Example of a valid JSON response (structure is enforced):
        ```json
        {{
            "action": "click",
            "target_identifier": "com.example.app:id/submit_button",
            "target_bounding_box": {{ "top_left": [450, 100], "bottom_right": [500, 980] }},
            "input_text": null,
            "reasoning": "Clicked the submit button. Bounds extracted from XML."
        }}
        ```
        Another example:
        ```json
        {{
            "action": "click",
            "target_identifier": "Next Button (visually identified text)",
            "target_bounding_box": {{ "top_left": [1234, 50], "bottom_right": [1284, 950] }},
            "input_text": null,
            "reasoning": "Clicked what appears to be a 'Next' button. Bounds attribute was missing in XML, so estimated visually from screenshot."
        }}
        ```
        A scroll example:
        ```json
        {{
            "action": "scroll_down",
            "target_identifier": null,
            "target_bounding_box": null,
            "input_text": null,
            "reasoning": "The current screen content has been reviewed, scrolling to find more interactive elements or information."
        }}
        ```
        """

        action_list_str = "\n".join([f"- {a}: {action_descriptions.get(a, '')}" for a in available_actions])
        history_str = "\n".join([f"- {pa}" for pa in previous_actions]) if previous_actions else "None"

        visit_context = f"CURRENT SCREEN CONTEXT:\n- Hash: {current_composite_hash}\n- Visit Count (this session): {current_screen_visit_count}"
        visit_instruction = ""
        # Ensure config.LOOP_DETECTION_VISIT_THRESHOLD is loaded correctly, e.g., from self or a config module
        loop_threshold = getattr(config, 'LOOP_DETECTION_VISIT_THRESHOLD', 3) 
        
        # Internal helper for action history analysis (could be moved to a utility if used elsewhere)
        def analyze_action_history(actions: List[str]) -> dict:
            if not actions:
                return {"repeated_actions": [], "last_unique_actions": [], "is_looping": False}
            action_sequence = []
            # Simplified extraction: assumes action strings contain "input" or "click" discernibly
            for action_str in actions: 
                action_detail = action_str.lower() # Process the string representation of the action
                if "input" in action_detail: # Check keywords in the action description
                    action_sequence.append(("input", action_str))
                elif "click" in action_detail:
                    action_sequence.append(("click", action_str))
                # Add other action types if needed for more complex loop detection logic

            last_actions = action_sequence[-6:] # Consider last 6 relevant (click/input) actions
            is_looping = False
            repeated_actions_summary = [] # Store summary of repeated patterns
            
            if len(last_actions) >= 4:
                # Check for simple repetition of the last action type
                action_types = [a[0] for a in last_actions]
                if action_types.count(action_types[-1]) > 2 : # e.g. click, click, click
                    is_looping = True
                    repeated_actions_summary.append(f"repeated '{action_types[-1]}'")
                
                # Check for alternating pattern like (input, click, input, click)
                # This checks if the last 4 actions are A, B, A, B
                if len(action_types) >= 4 and action_types[-4:-2] == action_types[-2:]:
                     is_looping = True
                     repeated_actions_summary.append(f"pattern '{'-'.join(action_types[-2:])}'")
                     
            return {
                "repeated_actions": list(set(repeated_actions_summary)), # Unique patterns
                "last_unique_actions": list(set(a[0] for a in last_actions)),
                "is_looping": is_looping
            }
        
        action_analysis = analyze_action_history(previous_actions)
        if current_screen_visit_count > loop_threshold or action_analysis["is_looping"]:
            repeated_text = ', '.join(action_analysis['repeated_actions']) if action_analysis['repeated_actions'] else 'None'
            tried_text = ', '.join(action_analysis['last_unique_actions']) if action_analysis['last_unique_actions'] else 'None'
            visit_instruction = f"""
        **CRITICAL - LOOP DETECTED / HIGH VISIT COUNT:**
        - Screen visited {current_screen_visit_count} times.
        - Recent action patterns detected as potentially looping: {repeated_text}.
        - Recent unique action types attempted on this screen: {tried_text}.
        REQUIRED ACTION CHANGES TO BREAK THE LOOP:
        1. DO NOT repeat recently failed or looped action sequences.
        2. If an input-then-click pattern failed, try significantly different input values, target different elements, or try a navigation action (scroll, back, explore menus).
        3. On error screens or validation messages, analyze the message and adjust your action. Try alternative data or paths. Look for "skip" or "do this later" options.
        4. Prioritize actions or elements that have NOT been tried recently on this screen. If scrolling hasn't been tried and content might be hidden, try scrolling.
        5. If all else fails and the app seems stuck, consider using 'back' if it leads to a different, productive state.
        """

        test_email_val = os.environ.get("TEST_EMAIL")
        test_password_val = os.environ.get("TEST_PASSWORD")
        test_name_val = os.environ.get("TEST_NAME")

        if not all([test_email_val, test_password_val, test_name_val]):
            logging.warning("One or more test credentials (TEST_EMAIL, TEST_PASSWORD, TEST_NAME) are not set in environment variables. Using default fallbacks for prompt generation.")
            test_email_val = test_email_val or "test.user@example.com"
            test_password_val = test_password_val or "Str0ngP@ssw0rd!"
            test_name_val = test_name_val or "Test User"

        input_value_guidance = f"""
        **CRUCIAL: Input Value Guidance:**
        - Email/Username: Use "{test_email_val}"
        - Password: Use "{test_password_val}"
        - Name: Use "{test_name_val}"
        - Other fields: Use realistic, context-appropriate test data based on field hints or labels (e.g., for a "City" field, input a city name like "Berlin").
        - CAPTCHA/Verification: If you see text for a CAPTCHA, input that visible text. If it fails or is unclear, note this in reasoning and consider alternative actions if possible (like refresh CAPTCHA if an option exists, or trying to proceed if allowed).
        - AVOID generic placeholders like "test", "input", "asdf" unless no context is available at all.
        """

        external_package_avoidance_guidance = """
        **CRUCIAL: External Package Avoidance:**
        - AVOID actions that navigate away from the current application package (e.g., opening an external mail app, browser for "Help" links, or external sharing dialogs that leave the app).
        - Prioritize actions that keep interaction within the current app. If an action seems to lead outside the app, choose an in-app alternative or a different exploratory path.
        """

        defer_authentication_guidance = """
        **STRATEGY: Defer Authentication Flows (Login/Registration):**
        - Your primary goal is to discover and interact with features of the app that are accessible *without* immediate login or registration.
        - Identify if the current screen is primarily a Login, Registration, or an initial onboarding screen that strongly funnels towards these authentication actions (look for keywords like "Login", "Register", "Sign In", "Sign Up", "Anmelden", "Registrieren", and typical email/password fields).
        - If other navigation options or content exploration paths exist on such screens (e.g., "Explore as Guest", "Skip for Now", "About Us", "Privacy Policy", "Help", settings, or general content Browse), prioritize those actions *before* attempting to log in or register.
        - You should only select an action related to "Login" or "Register" as a lower priority, as detailed in the 'General Action Priorities' section.
        """

        general_action_priorities_guidance = """
        General Action Priorities (Higher number means lower priority; aim for lowest number possible):
        1.  **Fulfill Prerequisites for Non-Authentication Actions:** If a desired progression button (e.g., "Next" for a tutorial, "Continue" for feature setup, NOT login/register) is disabled, perform the prerequisite action (e.g., fill a *non-authentication* related field, toggle a setting for feature exploration).
        2.  **Explore Public/Guest Features & Navigation:**
            * Click enabled progression buttons that lead to general app exploration (e.g., "Skip Tour", "Explore App", "Continue to Main Screen", "View Content").
            * Interact with elements clearly related to primary app functionalities accessible without login (e.g., viewing public articles, Browse product catalogs, accessing "Settings", "Help", "About Us", "Terms of Service", "Privacy Policy" if they don't force login).
            * Explore primary navigation elements (side drawers, bottom tabs, menus) for sections accessible without authentication.
        3.  **Input for Non-Authentication Tasks:** If text input is required for a non-authentication feature (e.g., a search bar for public content, a feedback form not tied to an account), perform the "input" action following Input Value Guidance.
        4.  **Scroll for More Options:** If more content or non-authentication interactive elements might be available off-screen, scroll (up or down). This is especially important if the screen seems stuck or no obvious actions are present.
        5.  **Engage with Login/Registration (Lower Priority):**
            * Only if few or no other higher-priority exploratory actions (as listed in priorities 1-4) are available on the current screen, OR if the app persistently blocks further exploration without authentication, THEN you may consider actions related to Login or Registration.
            * When choosing this, use the 'Login' or 'Register' related elements. Use the provided test credentials for login. For registration, use realistic test data as per Input Value Guidance.
        6.  **System Back (Judiciously):**
            * Use 'back' if you are in a dead-end that is not an authentication screen, or to return from a detail view to explore other items on a list.
            * Use 'back' if you believe you were prematurely funneled into an authentication flow and want to see if a previous screen had other options (respecting the loop detection guidance).
            * Avoid using 'back' if it simply reloads the exact same screen where you are already stuck or if it exits the app unnecessarily. Consider this carefully if loop detection is active.
        """

        prompt = f"""
        You are an expert Android app tester. Your goal is to explore systematically by performing ONE logical action based on the visual screenshot and XML context.
        Prioritize PROGRESSION, IN-APP feature discovery, and adhering to the strategic guidance provided.
        **IMPORTANT: For 'click'/'input', the `target_identifier` field in your JSON response is crucial. Provide its actual value from the XML (e.g., "com.app:id/submit_button", "LoginButton") or the visible text if no ID is available.**
        Do NOT wrap identifiers in quotes or descriptive text within the value itself: CORRECT `target_identifier`: "Login", INCORRECT: `target_identifier`: 'text="Login"'.

        {visit_context}

        CONTEXT:
        1. Screenshot: Provided as an image. This is your primary view of the current screen.
        2. XML Layout: Provided below (may be a snippet, or absent if it could not be retrieved). Use this to find `resource-id`, `content-desc`, `text`, `class`, and other attributes like `clickable`, `enabled`, `bounds`.
        3. Previous Actions Taken *From This Exact Screen State* (if any):
        {history_str}

        TASK:
        Analyze the screenshot and XML (if provided). Identify the BEST SINGLE action to perform next.
        Your primary objective is to explore new screens and features within the current application.
        Follow all CRUCIAL instructions and strategic guidance.

        {defer_authentication_guidance}

        {visit_instruction}

        {external_package_avoidance_guidance}

        **CRUCIAL: Progression Buttons (e.g., Next, Continue, Save, Submit, Done):**
        - Before clicking, always check if the button is enabled (e.g., in XML `enabled="true"` or visually not greyed out).
        - IF THE BUTTON IS DISABLED: Identify and perform the prerequisite action first (e.g., fill a required field, accept terms). Prioritize this prerequisite action. Do NOT suggest clicking a disabled button.

        {input_value_guidance}

        {bounding_box_guidance}

        **CRUCIAL: 'input' Action Guidance:**
        - Only suggest 'input' for elements that are clearly designed for text entry.
        - VERIFY ELEMENT TYPE: If XML is available, prefer elements with an editable `class` (e.g., `android.widget.EditText`, `android.widget.AutoCompleteTextView`, `android.widget.TextInputEditText`, `android.widget.SearchView`).
        - If XML is not available or unclear, visually confirm the element looks like an input field (e.g., has a cursor, underline, or typical input field styling).
        - DO NOT suggest 'input' for non-editable display elements like `android.widget.TextView` or `android.widget.Button` (unless the button is part of a Search View).
        - PARENT ELEMENT: If a non-editable text label is part of a larger clickable input field complex (e.g. a date picker trigger), identify the main clickable element of that complex for a 'click' action, or the actual input field if text entry is needed directly.

        {general_action_priorities_guidance}

        Choose ONE action from the available list below. Your response MUST be a JSON object strictly adhering to the schema provided in the 'RESPONSE FORMAT' section.
        Available actions:
        {action_list_str}

        {json_format_instruction}

        XML CONTEXT:
        ```xml
        {xml_context if xml_context else "No XML context provided for this screen, or it was empty. Rely primarily on the screenshot for element identification and state."}
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
        
        logging.info(f"get_next_action called with: xml_context_len={len(xml_context)}, previous_actions={previous_actions}, available_actions={available_actions}, current_screen_visit_count={current_screen_visit_count}, current_composite_hash={current_composite_hash}")
        
        image_part = self._prepare_image_part(screenshot_bytes)
        if not image_part:
            logging.error("Failed to prepare image for AI; cannot proceed. screenshot_bytes length: %d", len(screenshot_bytes) if screenshot_bytes else 0)
            return None

        start_time = time.time()
        try:
            prompt = self._build_prompt(
                xml_context, previous_actions, available_actions,
                current_screen_visit_count, current_composite_hash
            )
            content_parts = [prompt, image_part]

            logging.info("Requesting AI generation with structured JSON output...")
            try:
                if self.use_chat and self.chat:
                    response = self.chat.send_message(content_parts)
                    if len(self.chat.history) > self.max_history * 2:
                        num_exchanges_to_trim = (len(self.chat.history) // 2) - self.max_history
                        if len(self.chat.history) > 2 : # Ensure there's enough history to trim meaningfully
                             self.chat.history = self.chat.history[2 * num_exchanges_to_trim:]
                             logging.info(f"Trimmed chat history to approximately {len(self.chat.history)//2} exchanges")
                else:
                    response = self.model.generate_content(content_parts)

                elapsed_time = time.time() - start_time
                logging.info(f"Total AI Processing Time: {elapsed_time:.2f} seconds")
                
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    logging.info("Token Usage:")
                    logging.info(f"  Prompt: {getattr(response.usage_metadata, 'prompt_token_count', 'N/A')}")
                    logging.info(f"  Candidates: {getattr(response.usage_metadata, 'candidates_token_count', 'N/A')}")
                    logging.info(f"  Total: {getattr(response.usage_metadata, 'total_token_count', 'N/A')}")

                if not hasattr(response, 'candidates') or not response.candidates:
                    logging.error("AI response contains no candidates. Response object: %s", response)
                    self._log_empty_response_details(response)
                    return None

                candidate = response.candidates[0]
                
                # MODIFIED finish_reason check
                proceed_to_parse = False
                raw_finish_reason_str = "UNKNOWN"

                if hasattr(candidate, 'finish_reason'):
                    finish_reason_enum = candidate.finish_reason 
                    raw_finish_reason_str = str(finish_reason_enum) # e.g. "FinishReason.MAX_TOKENS"
                    
                    # Using .name for string representation if it's an actual enum from the library
                    # Or comparing integer values if you know them for sure.
                    # Your logs show "Reason: 1" for MAX_TOKENS.
                    # Let's assume google.generativeai.types.FinishReason enum is available
                    # and its .name attribute gives 'STOP', 'MAX_TOKENS' etc.
                    # If not, direct integer comparison from logs might be needed.
                    
                    # Example using .name (adjust if using .value or specific integers)
                    # Important: The actual enum values/names might vary slightly by library version.
                    # For example, if finish_reason_enum is an int:
                    if isinstance(finish_reason_enum, int):
                        if finish_reason_enum == 0: # Placeholder for STOP if it's 0
                            logging.info(f"AI generation finished normally (Reason value: {finish_reason_enum}).")
                            proceed_to_parse = True
                        elif finish_reason_enum == 1: # MAX_TOKENS from your logs
                            logging.warning(f"AI generation hit MAX_TOKENS (Reason value: {finish_reason_enum}). Will attempt to parse potentially truncated JSON.")
                            proceed_to_parse = True
                        # Add other integer conditions for SAFETY, RECITATION, OTHER if known
                        # For example, from Gemini API documentation or SDK:
                        # 2 might be SAFETY, 3 RECITATION, 4 OTHER
                        elif finish_reason_enum == 2: # Placeholder for SAFETY
                            logging.error(f"AI generation stopped due to SAFETY (Reason value: {finish_reason_enum}).")
                            self._log_empty_response_details(response)
                            return None
                        else:
                            logging.error(f"AI generation finished with an unhandled reason value: {finish_reason_enum}.")
                            self._log_empty_response_details(response)
                            return None
                    elif hasattr(finish_reason_enum, 'name'): # If it's an enum object with a .name attribute
                        reason_name = finish_reason_enum.name.upper()
                        if reason_name == "STOP":
                            logging.info(f"AI generation finished normally (Reason: {raw_finish_reason_str}).")
                            proceed_to_parse = True
                        elif reason_name == "MAX_TOKENS":
                            logging.warning(f"AI generation hit MAX_TOKENS (Reason: {raw_finish_reason_str}). Will attempt to parse potentially truncated JSON.")
                            proceed_to_parse = True
                        elif reason_name in ["SAFETY", "RECITATION", "OTHER"]:
                            logging.error(f"AI generation stopped due to {reason_name} (Reason: {raw_finish_reason_str}).")
                            self._log_empty_response_details(response)
                            return None
                        else:
                            logging.error(f"AI generation finished with an unknown named reason: {reason_name} (Raw: {raw_finish_reason_str}).")
                            self._log_empty_response_details(response)
                            return None
                    else: # Fallback if it's not an int and has no .name
                        logging.error(f"AI generation finished with an unhandled finish_reason type/value: {raw_finish_reason_str}.")
                        self._log_empty_response_details(response)
                        return None
                else:
                    logging.error("Candidate does not have finish_reason attribute.")
                    self._log_empty_response_details(response)
                    return None

                if not proceed_to_parse:
                    # This path implies a non-recoverable finish reason was encountered.
                    return None

                if not hasattr(candidate, 'content') or not candidate.content or \
                   not hasattr(candidate.content, 'parts') or not candidate.content.parts:
                    logging.error("AI response candidate lacks valid content/parts. Candidate: %s", candidate)
                    self._log_empty_response_details(response)
                    return None
                
                first_part = candidate.content.parts[0]
                if not hasattr(first_part, 'text') or not first_part.text:
                    logging.error("AI response first part lacks text content. First part: %s", first_part)
                    self._log_empty_response_details(response)
                    return None
                
                raw_json_text = first_part.text
                logging.info(f"Raw AI response text (first 500 chars): {raw_json_text[:500]}")
                
                json_str_to_parse = raw_json_text.strip()
                if json_str_to_parse.startswith("```"):
                    logging.info(f"Stripping markdown from response: '{json_str_to_parse[:100]}...'")
                    json_str_to_parse = re.sub(r"^```(?:json)?\s*", "", json_str_to_parse, flags=re.IGNORECASE)
                    json_str_to_parse = re.sub(r"\s*```$", "", json_str_to_parse)
                    json_str_to_parse = json_str_to_parse.strip()
                
                if not json_str_to_parse:
                    logging.error("AI response: Empty JSON string after cleaning. Original text: %s", raw_json_text)
                    self._log_empty_response_details(response)
                    return None

                try:
                    parsed_data = json.loads(json_str_to_parse)
                    logging.info(f"Successfully parsed AI JSON: {parsed_data}")
                    
                    if not isinstance(parsed_data, dict):
                        logging.error(f"AI response not a dictionary: {type(parsed_data)}. Parsed data: {parsed_data}")
                        return None
                    
                    action_data = parsed_data

                    if "action" not in action_data or "reasoning" not in action_data:
                        logging.error(f"Missing required fields 'action' or 'reasoning' in response. Data: {action_data}")
                        return None

                    action_type = action_data.get("action")
                    if action_type in ["click", "input"] and not action_data.get("target_identifier"):
                        logging.warning(f"Missing target_identifier for action '{action_type}'. Data: {action_data}")

                    if action_type == "input" and action_data.get("input_text") is None: # Allow empty string "" for input_text
                        logging.warning(f"input_text is null for input action. Data: {action_data}")

                    bbox = action_data.get("target_bounding_box")
                    # Schema change: target_bounding_box itself can be null.
                    # If it's not null, then it must be a valid bbox object.
                    if bbox is not None: 
                        if not (isinstance(bbox, dict) and \
                                "top_left" in bbox and isinstance(bbox["top_left"], list) and len(bbox["top_left"]) == 2 and \
                                "bottom_right" in bbox and isinstance(bbox["bottom_right"], list) and len(bbox["bottom_right"]) == 2 and \
                                all(isinstance(coord, (int, float)) 
                                    for coord_pair in [bbox["top_left"], bbox["bottom_right"]] 
                                    for coord in coord_pair)):
                            logging.warning(f"Invalid bounding box format received: {bbox}. Setting to null. Data: {action_data}")
                            action_data["target_bounding_box"] = None 
                    # If schema expects target_bounding_box to be non-nullable (as per your previous change),
                    # then this check needs to align. With nullable=True, this is fine.

                    logging.info(f"AI Action: {action_type}, Target: {action_data.get('target_identifier')}, Input: {action_data.get('input_text')}, Reasoning: {action_data.get('reasoning')}")
                    return action_data

                except json.JSONDecodeError as json_err:
                    logging.error(f"JSON parse error: {json_err}. Problematic JSON string: '{json_str_to_parse}'")
                    self._log_empty_response_details(response) # Log details of the response that failed to parse
                    return None
                except Exception as parse_err: # Other validation errors
                    logging.error(f"Post-parsing validation error: {parse_err}. Parsed data was: '{json_str_to_parse}'")
                    return None

            except Exception as api_err:
                logging.error(f"AI API error: {api_err}", exc_info=True)
                logging.error(f"Prompt (first 500 chars): {prompt[:500]}")
                if "api key" in str(api_err).lower():
                    logging.critical("API key error - check configuration")
                return None

        except Exception as e:
            logging.error(f"General error in get_next_action: {e}", exc_info=True)
            logging.error(f"Input params to get_next_action: xml_context_len={len(xml_context)}, previous_actions_count={len(previous_actions)}, available_actions={available_actions}, current_screen_visit_count={current_screen_visit_count}, current_composite_hash={current_composite_hash}")
            return None