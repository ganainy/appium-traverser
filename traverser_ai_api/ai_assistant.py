import google.generativeai as genai
from google.generativeai.client import configure as genai_configure
from google.generativeai.generative_models import GenerativeModel
from google.generativeai.types import GenerationConfig
from google.ai import generativelanguage as glm
from google.ai.generativelanguage import Schema, Type as GLMType, Content, Part


import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import json
from PIL import Image
import io
import re
import os

class AIAssistant:
    """
    Handles interactions with the Generative AI model, enforcing structured JSON output
    for actions and all UI elements using an OpenAPI-like schema.
    It now receives its configuration via a passed-in Config object instance.
    """

    @staticmethod
    def _get_ui_element_schema() -> Schema:
        """Defines the schema for a single UI element."""
        return Schema(
            type=GLMType.OBJECT,
            description="Represents a single identifiable UI element on the screen.",
            properties={
                'type': Schema(
                    type=GLMType.STRING,
                    description="The type of the UI element (e.g., button, editText, textView, imageView, radioButton, checkBox, switch, icon, label, FAB, etc.)."
                ),
                'description': Schema(
                    type=GLMType.STRING,
                    nullable=True,
                    description="Visible text content or accessibility label of the element."
                ),
                'resource_id': Schema(
                    type=GLMType.STRING,
                    nullable=True,
                    description="The resource-id of the element, if available and discernible from XML."
                ),
                'bounding_box': Schema(
                    type=GLMType.OBJECT,
                    nullable=True,
                    properties={
                        'top_left': Schema(type=GLMType.ARRAY, items=Schema(type=GLMType.NUMBER), description="[y1, x1] normalized coordinates (0.0-1.0) for the top-left corner."),
                        'bottom_right': Schema(type=GLMType.ARRAY, items=Schema(type=GLMType.NUMBER), description="[y2, x2] normalized coordinates (0.0-1.0) for the bottom-right corner.")
                    },
                    required=['top_left', 'bottom_right'],
                    description="Normalized bounding box of the element. Null if not determinable."
                )
            },
            required=['type', 'bounding_box'] # Description can be null, resource_id can be null
        )

    @staticmethod
    def _get_action_to_perform_schema() -> Schema:
        """Defines the schema for the AI's action_to_perform response part."""
        action_to_perform_schema = Schema(
            type=GLMType.OBJECT,
            description="Describes the single next UI action to perform.",
            properties={
                'action': Schema(
                    type=GLMType.STRING,
                    # MODIFIED: Add swipe actions here
                    enum=["click", "input", "scroll_up", "scroll_down", "swipe_left", "swipe_right", "back"],
                    description="The type of action to perform."
                ),
                'target_identifier': Schema(
                    type=GLMType.STRING,
                    nullable=True,
                    description="Identifier of the target element for 'click' or 'input' (e.g., resource-id, content-desc, or visible text). Null if not applicable."
                ),
                'target_bounding_box': Schema(
                    type=GLMType.OBJECT,
                    nullable=True,
                    properties={
                        'top_left': Schema(type=GLMType.ARRAY, items=Schema(type=GLMType.NUMBER)),
                        'bottom_right': Schema(type=GLMType.ARRAY, items=Schema(type=GLMType.NUMBER))
                    },
                    required=['top_left', 'bottom_right']
                ),
                'input_text': Schema(
                    type=GLMType.STRING,
                    nullable=True,
                    description="Text to input. Required for 'input' action, null otherwise."
                ),
                'reasoning': Schema(
                    type=GLMType.STRING,
                    description="Brief explanation for choosing this action."
                )
            },
            required=['action', 'reasoning']
        )
        return action_to_perform_schema

    @staticmethod
    def _get_main_response_schema() -> Schema:
        """Defines the schema for the AI's main response, focused only on action."""
        return Schema(
            type=GLMType.OBJECT,
            description="The overall response from the AI, including the action to perform.",
            properties={
                'action_to_perform': AIAssistant._get_action_to_perform_schema()
            },
            required=['action_to_perform']
        )


    def __init__(self,
                 app_config, # Type hint with your actual Config class
                 model_alias_override: Optional[str] = None,
                 safety_settings_override: Optional[Dict] = None):
        self.cfg = app_config
        self.response_cache: Dict[str, Tuple[Dict[str, Any], float, int]] = {}
        logging.info("AI response cache initialized.")

        if not self.cfg.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in the provided application configuration.")
        self.api_key = self.cfg.GEMINI_API_KEY

        model_alias = model_alias_override or self.cfg.DEFAULT_MODEL_TYPE
        if not model_alias:
            raise ValueError("Model alias must be provided.")

        if not self.cfg.GEMINI_MODELS or not isinstance(self.cfg.GEMINI_MODELS, dict):
            raise ValueError("GEMINI_MODELS must be defined in app_config and be a non-empty dictionary.")

        available_model_aliases = list(self.cfg.GEMINI_MODELS.keys())
        if not available_model_aliases:
            raise ValueError("GEMINI_MODELS in app_config is empty.")
        if model_alias not in available_model_aliases:
            raise ValueError(f"Invalid model alias '{model_alias}'. Available: {', '.join(available_model_aliases)}")

        model_config_from_file = self.cfg.GEMINI_MODELS.get(model_alias)
        if not model_config_from_file or not isinstance(model_config_from_file, dict):
            raise ValueError(f"Model configuration for alias '{model_alias}' not found or invalid.")

        actual_model_name = model_config_from_file.get('name')
        if not actual_model_name:
            raise ValueError(f"'name' field missing in app_config for alias '{model_alias}'.")

        self.model_alias = model_alias
        self.actual_model_name = actual_model_name

        raw_safety_settings_source = safety_settings_override if safety_settings_override is not None else self.cfg.AI_SAFETY_SETTINGS
        if raw_safety_settings_source is None: raw_safety_settings_source = {}
        if not isinstance(raw_safety_settings_source, dict):
            raise ValueError("Safety settings must be a dictionary.")

        self.processed_safety_settings: List[Dict[str, Any]] = []
        for key, value in raw_safety_settings_source.items():
            try:
                self.processed_safety_settings.append({'category': key, 'threshold': value})
            except Exception as e:
                raise ValueError(f"Error processing safety setting key '{key}' or value '{value}': {e}.")

        if not self.processed_safety_settings and raw_safety_settings_source:
            logging.warning("Safety settings provided but could not be processed.")
        elif not raw_safety_settings_source:
            logging.info("No safety settings provided; using API defaults.")

        try:
            genai_configure(api_key=self.api_key)
            self.response_schema = self._get_main_response_schema()

            generation_config_dict = model_config_from_file.get('generation_config')
            if not generation_config_dict or not isinstance(generation_config_dict, dict):
                raise ValueError(f"Generation config not found or invalid for alias '{self.model_alias}'.")

            required_fields = ['temperature', 'top_p', 'top_k', 'max_output_tokens']
            missing_fields = [f for f in required_fields if f not in generation_config_dict]
            if missing_fields:
                raise ValueError(f"Missing gen config fields for '{self.model_alias}': {', '.join(missing_fields)}")

            sdk_generation_config = GenerationConfig(
                temperature=generation_config_dict['temperature'],
                top_p=generation_config_dict['top_p'],
                top_k=generation_config_dict['top_k'],
                max_output_tokens=generation_config_dict['max_output_tokens'],
                candidate_count=generation_config_dict.get('candidate_count', 1),
                stop_sequences=generation_config_dict.get('stop_sequences', []) or [],
                response_mime_type="application/json",
                response_schema=self.response_schema
            )

            self.model = GenerativeModel(
                model_name=self.actual_model_name,
                generation_config=sdk_generation_config,
                safety_settings=self.processed_safety_settings
            )

            logging.info(f"AI Assistant initialized with model alias: {self.model_alias} (actual: {self.actual_model_name})")
            logging.info(f"Model description: {model_config_from_file.get('description', 'N/A')}")
            logging.info("Structured JSON output schema (for action and all_ui_elements) is ENABLED.")
            if self.processed_safety_settings:
                logging.info(f"Applied safety settings: {self.processed_safety_settings}")

            self.use_chat = self.cfg.USE_CHAT_MEMORY
            if self.use_chat is None:
                logging.warning("USE_CHAT_MEMORY not in app_config, defaulting to False.")
                self.use_chat = False
            if self.use_chat:
                try:
                    self.chat = self.model.start_chat(history=[]) # type: ignore
                    self.max_history = self.cfg.MAX_CHAT_HISTORY
                    if self.max_history is None:
                        logging.warning("MAX_CHAT_HISTORY not in app_config, defaulting to 10.")
                        self.max_history = 10
                    logging.info(f"Chat memory enabled (max history: {self.max_history} exchanges)")
                except Exception as e:
                    logging.warning(f"Failed to initialize chat: {e}. Disabling chat memory.")
                    self.chat = None # type: ignore
                    self.use_chat = False
            else:
                self.chat = None # type: ignore
                logging.info("Chat memory is disabled.")
        except Exception as e:
            logging.error(f"Failed to initialize GenerativeModel or AIAssistant: {e}", exc_info=True)
            raise

    def _log_empty_response_details(self, response) -> None:
        # ... (This method remains the same as in your provided code)
        logging.info("Detailed AI Response Analysis:")
        try:
            if not response:
                logging.warning("  Response object itself is None.")
                return

            if hasattr(response, "usage_metadata"):
                metadata = response.usage_metadata
                if metadata:
                    logging.info("  Usage Metadata:")
                    for m_attr in ["prompt_token_count", "candidates_token_count", "total_token_count"]:
                        if hasattr(metadata, m_attr):
                            logging.info(f"    {m_attr}: {getattr(metadata, m_attr)}")
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                logging.info("  First Candidate Details:")
                if hasattr(candidate, "finish_reason"):
                    logging.info(f"    finish_reason: {candidate.finish_reason}")
                if hasattr(candidate, "safety_ratings"):
                    logging.info(f"    safety_ratings: {candidate.safety_ratings}")
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    for i, part in enumerate(candidate.content.parts):
                        logging.info(f"    Content Part {i}: {type(part).__name__}")
                        if hasattr(part, "text"):
                            logging.info(f"      Text: {part.text[:200]}...") # Log snippet
        except Exception as e:
            logging.error(f"Error analyzing response details: {e}", exc_info=True)


    def _prepare_image_part(self, screenshot_bytes: bytes) -> Optional[Content]:
        try:
            img = Image.open(io.BytesIO(screenshot_bytes))

            # --- Image Optimization Logic ---
            max_width = 720
            if img.width > max_width:
                scale = max_width / img.width
                new_height = int(img.height * scale)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                logging.debug(f"Resized screenshot to {img.size} for AI analysis.")

            # --- FIX: Convert RGBA to RGB before saving as JPEG ---
            if img.mode == 'RGBA':
                img = img.convert('RGB')
                logging.debug("Converted image from RGBA to RGB for JPEG compatibility.")

            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=85)
            img_bytes_for_api = img_byte_arr.getvalue()
            
            logging.debug(f"Prepared image for AI. Original size: {len(screenshot_bytes)} bytes, Optimized size: {len(img_bytes_for_api)} bytes.")

            return Content(parts=[Part(inline_data=glm.Blob(mime_type="image/jpeg", data=img_bytes_for_api))])
        except Exception as e:
            logging.error(f"Failed to prepare image part for AI: {e}", exc_info=True)
            return None


    def _build_prompt(self, xml_context: str, previous_actions: List[str], available_actions: List[str], current_screen_visit_count: int, current_composite_hash: str, last_action_feedback: Optional[str] = None) -> str:
    
        action_descriptions = {
            "click": getattr(self.cfg, 'ACTION_DESC_CLICK', "Visually identify and select an interactive element."),
            "input": getattr(self.cfg, 'ACTION_DESC_INPUT', "Visually identify a text input field and provide text."),
            "scroll_down": getattr(self.cfg, 'ACTION_DESC_SCROLL_DOWN', "Scroll the view downwards."),
            "scroll_up": getattr(self.cfg, 'ACTION_DESC_SCROLL_UP', "Scroll the view upwards."),
            "swipe_left": getattr(self.cfg, 'ACTION_DESC_SWIPE_LEFT', "Swipe content from right to left (for carousels)."),
            "swipe_right": getattr(self.cfg, 'ACTION_DESC_SWIPE_RIGHT', "Swipe content from left to right."),
            "back": getattr(self.cfg, 'ACTION_DESC_BACK', "Navigate back using the system back button.")
        }

        feedback_section = ""
        if last_action_feedback:
            feedback_section = f"""**CRITICAL FEEDBACK ON YOUR PREVIOUS ACTION:**
{last_action_feedback}
Based on this feedback, you MUST choose a different action to avoid getting stuck.
"""

        actual_available_actions = getattr(self.cfg, 'AVAILABLE_ACTIONS', available_actions)
        if not actual_available_actions:
            actual_available_actions = ["click", "input", "scroll_down", "scroll_up", "swipe_left", "swipe_right", "back"]

        ui_element_types_guidance = """
        **Identifiable UI Element Types for `all_ui_elements` list:**
        When listing all UI elements, try to classify them into one of the following types:
        "button", "editText" (or "textInput", "searchBox"), "textView" (or "label", "text"), "imageView" (or "image", "icon"), "imageButton",
        "radioButton", "checkBox", "switch", "seekBar", "slider", "progressBar",
        "webView", "mapView", "videoPlayer", "datePicker", "timePicker", "numberPicker",
        "listViewItem", "recyclerViewItem", "gridItem", "carouselItem",
        "tab", "menuItem", "dialog", "advertisement", "banner", "card", "chip", "tooltip",
        "navigationBarIcon", "toolbarIcon", "FAB" (Floating Action Button),
        "header", "footer", "link", "other" (for elements not fitting other categories).
        Provide the most specific type possible.
        """

        bounding_box_guidance_general = """
        **Bounding Box Format for ALL Elements (`target_bounding_box` for action AND `bounding_box` in `all_ui_elements`):**
        -   Coordinates MUST be NORMALIZED (values between 0.0 and 1.0, where (0,0) is top-left, (1,1) is bottom-right).
        -   Provide `top_left` as `[y1, x1]` and `bottom_right` as `[y2, x2]`.
        -   If extracting from XML 'bounds' (e.g., `[x1,y1][x2,y2]`), carefully convert to normalized `[y,x]` format relative to screen dimensions.
            If screen dimensions are unknown, make your best visual estimate for normalization from the screenshot.
        -   If a precise bounding box cannot be determined for an element in `all_ui_elements`, you MAY set its `bounding_box` to `null`.
            However, for the `action_to_perform.target_bounding_box`, strive to provide it if the action is 'click' or 'input'.
        """
        
        # Simplified guidance for action_to_perform.target_bounding_box
        action_target_bbox_guidance = """
        **For `action_to_perform.target_bounding_box` (if action is 'click' or 'input'):**
        1.  **Extract from XML (Primary):** Use the 'bounds' attribute from the XML for the `target_identifier`. Convert to normalized `{"top_left": [y1, x1], "bottom_right": [y2, x2]}`.
        2.  **Visually Estimate (Fallback):** If XML bounds are unavailable/unreliable for the target, visually estimate normalized coordinates from the screenshot.
        3.  **Use `null` (Last Resort):** Only if coordinates cannot be determined for the action target. For 'scroll' or 'back', this should be `null`.
        """


        json_format_instruction_new = f"""\
        **RESPONSE FORMAT (Strict JSON Schema Enforced by API):**
        Your response MUST be a JSON object with one top-level key: `action_to_perform`.

        1.  `action_to_perform`: (object) MANDATORY. Describes the single best action to take. This object itself must always be present.
            -   `action`: (string, enum) The action (e.g., "click", "input"). REQUIRED.
            -   `target_identifier`: (string | null) Identifier for "click"/"input". Crucial if applicable, otherwise null.
            -   `target_bounding_box`: (object | null) Normalized bounding box for the action's target. `{{"top_left": [y1,x1], "bottom_right": [y2,x2]}}`. Strongly preferred for 'click'/'input'.
            -   `input_text`: (string | null) Text for "input" action. Required if action is "input", otherwise null.
            -   `reasoning`: (string) Your brief explanation. REQUIRED.

        Example of a valid JSON response:
        ```json
        {{
          "action_to_perform": {{
            "action": "click",
            "target_identifier": "com.example.app:id/submit_button",
            "target_bounding_box": {{ "top_left": [0.8, 0.1], "bottom_right": [0.85, 0.9] }},
            "input_text": null,
            "reasoning": "Clicked the submit button to proceed. Bounds estimated from screenshot as XML was minimal."
          }}
        }}
        ```
        """
        # ... (rest of loop_threshold, visit_context, visit_instruction, input_value_guidance, etc. remain similar to your provided code) ...

        loop_threshold = getattr(self.cfg, 'LOOP_DETECTION_VISIT_THRESHOLD', 3)
        if loop_threshold is None: loop_threshold = 3

        action_list_str = "\n".join([f"- {a}: {action_descriptions.get(a, '')}" for a in actual_available_actions])
        history_str = "\n".join([f"- {pa}" for pa in previous_actions]) if previous_actions else "None"
        visit_context = f"CURRENT SCREEN CONTEXT:\n- Hash: {current_composite_hash}\n- Visit Count (this session): {current_screen_visit_count}"
        visit_instruction = ""
        action_analysis = self._analyze_action_history(previous_actions)
        if current_screen_visit_count > loop_threshold or action_analysis["is_looping"]:
            repeated_text = ', '.join(action_analysis['repeated_actions']) if action_analysis['repeated_actions'] else 'None'
            tried_text = ', '.join(action_analysis['last_unique_actions']) if action_analysis['last_unique_actions'] else 'None'
            visit_instruction = f"""
            **CRITICAL - LOOP DETECTED / HIGH VISIT COUNT:**
            - Screen visited {current_screen_visit_count} times.
            - Recent action patterns detected as potentially looping: {repeated_text}.
            - Recent unique action types attempted on this screen: {tried_text}.
            REQUIRED ACTION CHANGES TO BREAK THE LOOP (for `action_to_perform`):
            1. DO NOT repeat recently failed or looped action sequences.
            2. Prioritize actions or elements that have NOT been tried recently on this screen.
            3. If all else fails and the app seems stuck, consider using 'back'.
            """
        test_email_val = os.environ.get("TEST_EMAIL", "test.user@example.com")
        test_password_val = os.environ.get("TEST_PASSWORD", "Str0ngP@ssw0rd!")
        test_name_val = os.environ.get("TEST_NAME", "Test User")
        if not all(os.environ.get(k) for k in ["TEST_EMAIL", "TEST_PASSWORD", "TEST_NAME"]):
             logging.warning("One or more test credentials not set in env. Using defaults for prompt.")

        input_value_guidance = f"""
        **Input Value Guidance (for `action_to_perform.input_text`):**
        - Email/Username: Use "{test_email_val}"
        - Password: Use "{test_password_val}"
        - Name: Use "{test_name_val}"
        - Other fields: Use realistic, context-appropriate test data.
        - AVOID generic placeholders like "test", "input", "asdf".
        """
        external_package_avoidance_guidance = """
        **CRUCIAL: External Package Avoidance (for `action_to_perform`):**
        - AVOID actions that navigate away from the current application package.
        """
        defer_authentication_guidance = """
        **STRATEGY: Defer Authentication Flows (Login/Registration) (for `action_to_perform`):**
        - Primary goal: explore features accessible *without* immediate login/registration.
        - If other navigation options exist (e.g., "Explore as Guest", "Skip"), prioritize those.
        """
        general_action_priorities_guidance = """
        General Action Priorities (for `action_to_perform`):
        1.  Fulfill Prerequisites for Non-Authentication Actions.
        2.  Explore Public/Guest Features & Navigation.
        3.  Input for Non-Authentication Tasks.
        4.  Scroll for More Options.
        5.  Engage with Login/Registration (Lower Priority).
        6.  System Back (Judiciously).
        """

        prompt = f"""
        You are an expert Android app tester. Your goal is to:
        1.  Determine the BEST SINGLE `action_to_perform` based on the visual screenshot and XML context, prioritizing PROGRESSION and IN-APP feature discovery.

        {feedback_section}

        **IMPORTANT: For `action_to_perform.target_identifier`:**
        Provide its actual value from the XML (e.g., "com.app:id/button", "Login") or visible text if no ID.
        CORRECT: "Login", INCORRECT: 'text="Login"'.


        {visit_context}

        CONTEXT:
        1. Screenshot: Provided as an image. This is your primary view.
        2. XML Layout: Provided below (may be a snippet/absent). Use for attributes.
        3. Previous Actions Taken *From This Exact Screen State* (if any) for `action_to_perform`:
        {history_str}

        TASK:
        Analyze the screenshot and XML.
        1.  For `action_to_perform`: Identify the BEST SINGLE action. Follow all CRUCIAL instructions and strategic guidance.

        {defer_authentication_guidance}
        {visit_instruction}
        {external_package_avoidance_guidance}
        {bounding_box_guidance_general}
        {action_target_bbox_guidance}
        {input_value_guidance}
        {general_action_priorities_guidance}

        Choose ONE action for `action_to_perform` from the available list below.
        Available actions for `action_to_perform.action`:
        {action_list_str}

        {json_format_instruction_new}

        XML CONTEXT:
        ```xml
        {xml_context if xml_context else "No XML context provided for this screen, or it was empty. Rely primarily on the screenshot."}
        ```
        """
        return prompt.strip()


    def _analyze_action_history(self, actions: List[str]) -> dict:
        # ... (This method remains the same as in your provided code)
        if not actions:
            return {"repeated_actions": [], "last_unique_actions": [], "is_looping": False}
        action_sequence: List[Tuple[str, str]] = []
        for action_str in actions: 
            action_detail = action_str.lower()
            if "input" in action_detail: action_sequence.append(("input", action_str))
            elif "click" in action_detail: action_sequence.append(("click", action_str))

        last_actions = action_sequence[-6:]
        is_looping = False
        repeated_actions_summary = []
        
        if len(last_actions) >= 4:
            action_types = [a[0] for a in last_actions]
            if action_types.count(action_types[-1]) >= 3 :
                is_looping = True
                repeated_actions_summary.append(f"repeated '{action_types[-1]}'")
            if len(action_types) >= 4 and action_types[-4:-2] == action_types[-2:]:
                is_looping = True
                repeated_actions_summary.append(f"pattern '{'-'.join(action_types[-2:])}'")
                
        return {
            "repeated_actions": list(set(repeated_actions_summary)),
            "last_unique_actions": list(set(a[0] for a in last_actions)),
            "is_looping": is_looping
        }

    def get_next_action(self,
                        screenshot_bytes: bytes,
                        xml_context: str,
                        previous_actions: List[str],
                        current_screen_visit_count: int,
                        current_composite_hash: str,
                        last_action_feedback: Optional[str] = None
                        ) -> Optional[Tuple[Dict[str, Any], float, int]]:
        
        # Create a unique key for the current state and context
        cache_key = f"{current_composite_hash}_{str(sorted(previous_actions))}_{last_action_feedback}"

        # Check cache before making the API call
        if cache_key in self.response_cache:
            logging.info(f"CACHE HIT: Found cached AI response for key: {cache_key[:70]}...")
            # Return a copy of the cached response with a simulated time of 0
            cached_response, _, cached_tokens = self.response_cache[cache_key]
            return dict(cached_response), 0.0, cached_tokens

        current_available_actions = getattr(self.cfg, 'AVAILABLE_ACTIONS', None)
        if not current_available_actions or \
           not isinstance(current_available_actions, list) or \
           not all(isinstance(a, str) for a in current_available_actions):
            logging.warning("cfg.AVAILABLE_ACTIONS invalid. Using default actions.")
            current_available_actions = ["click", "input", "scroll_up", "scroll_down", "swipe_left", "swipe_right", "back"]

        logging.info(f"get_next_action: xml_len={len(xml_context)}, prev_actions={len(previous_actions)}, avail_actions={current_available_actions}, visits={current_screen_visit_count}, hash={current_composite_hash}")

        image_content_part = self._prepare_image_part(screenshot_bytes)
        if not image_content_part:
            logging.error("Failed to prepare image content for AI; cannot proceed. screenshot_bytes length: %d", len(screenshot_bytes) if screenshot_bytes else 0)
            return None

        start_time = time.time()
        try:
            prompt_text = self._build_prompt(
                xml_context, previous_actions, current_available_actions,
                current_screen_visit_count, current_composite_hash,
                last_action_feedback
            )
            
            content_message = Content(
                parts=[Part(text=prompt_text)],
                role="user"
            )
            image_content = image_content_part or Content()
            content_for_api = [content_message, image_content]

            logging.debug("Requesting AI generation with structured JSON...")

            try:
                if self.use_chat and self.chat:
                    response = self.chat.send_message(content_for_api)
                    if len(self.chat.history) > self.max_history * 2 and self.max_history > 0:
                        num_pairs_to_trim = (len(self.chat.history) // 2) - self.max_history
                        if num_pairs_to_trim > 0:
                            self.chat.history = self.chat.history[2 * num_pairs_to_trim:]
                            logging.info(f"Trimmed chat history to ~{len(self.chat.history)//2} exchanges.")
                else:
                    response = self.model.generate_content(content_for_api)

                elapsed_time = time.time() - start_time
                total_tokens = 0
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    total_tokens = getattr(response.usage_metadata, 'total_token_count', 0)
                    logging.info(f"Token Usage: Prompt={getattr(response.usage_metadata, 'prompt_token_count', 'N/A')}, Candidates={getattr(response.usage_metadata, 'candidates_token_count', 'N/A')}, Total={total_tokens}")

                logging.info(f"AI API call completed. Processing Time: {elapsed_time:.2f} seconds")

                if not hasattr(response, 'candidates') or not response.candidates:
                    logging.error("AI response contains no candidates.")
                    self._log_empty_response_details(response)
                    return None

                candidate = response.candidates[0]
                proceed_to_parse = False
                raw_finish_reason_str = "UNKNOWN"

                if hasattr(candidate, 'finish_reason'):
                    finish_reason_enum = candidate.finish_reason
                    reason_name = getattr(finish_reason_enum, 'name', str(finish_reason_enum)).upper()

                    if reason_name == "STOP" or reason_name == "MAX_TOKENS":
                        if reason_name == "MAX_TOKENS": logging.warning(f"AI generation hit MAX_TOKENS. Will attempt to parse.")
                        proceed_to_parse = True
                    else:
                        logging.error(f"AI generation stopped for reason: {reason_name}. Raw: {str(finish_reason_enum)}")
                        self._log_empty_response_details(response)
                        return None
                else:
                    logging.error("Candidate missing 'finish_reason'.")
                    self._log_empty_response_details(response)
                    return None

                if not proceed_to_parse: return None

                if not hasattr(candidate, 'content') or not candidate.content or not candidate.content.parts or not hasattr(candidate.content.parts[0], 'text'):
                    logging.error("AI response candidate lacks valid content/parts.")
                    self._log_empty_response_details(response)
                    return None

                raw_json_text = candidate.content.parts[0].text
                json_str_to_parse = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_json_text.strip(), flags=re.I | re.M)

                if not json_str_to_parse:
                    logging.error("AI response: Empty JSON string after cleaning. Raw: %s", raw_json_text[:200])
                    return None

                try:
                    parsed_main_response = json.loads(json_str_to_parse)
                    logging.info("Successfully parsed AI main JSON response.")                    

                    if not isinstance(parsed_main_response.get("action_to_perform"), dict):
                        logging.error(f"Parsed JSON lacks 'action_to_perform' dictionary. Data: {parsed_main_response}")
                        return None
                    
                    # Store the successful response in the cache before returning
                    self.response_cache[cache_key] = (dict(parsed_main_response), elapsed_time, total_tokens)
                    logging.debug(f"Stored AI response in cache with key: {cache_key[:70]}...")
                    
                    return parsed_main_response, elapsed_time, total_tokens

                except json.JSONDecodeError as json_err:
                    logging.error(f"JSON parse error: {json_err}. Snippet: '{json_str_to_parse[:500]}'")
                    self._log_empty_response_details(response)
                    return None

            except Exception as api_err:
                logging.error(f"AI API call error: {api_err}", exc_info=True)
                return None

        except Exception as e:
            logging.error(f"General error in get_next_action before API call: {e}", exc_info=True)
            return None