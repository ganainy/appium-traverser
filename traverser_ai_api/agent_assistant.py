import os
import logging
import time
import json
from typing import Any, Dict, List, Optional, Tuple
import re
from PIL import Image
import io

# Try both relative and absolute imports to support different execution contexts
try:
    # When running as a module within the traverser_ai_api package
    from traverser_ai_api.model_adapters import create_model_adapter
except ImportError:
    # When running directly from the traverser_ai_api directory
    from model_adapters import create_model_adapter

class AgentAssistant:
    """
    Handles interactions with AI models (Google Gemini, DeepSeek) using adapters.
    Implements structured prompting for mobile app UI testing.
    
    The AgentAssistant can also directly perform actions using the AgentTools, allowing it to 
    implement more complex behaviors like planning, self-correction, and memory.
    """
    
    def __init__(self,
                 app_config, # Type hint with your actual Config class
                 model_alias_override: Optional[str] = None,
                 safety_settings_override: Optional[Dict] = None,
                 agent_tools=None):
        self.cfg = app_config
        self.response_cache: Dict[str, Tuple[Dict[str, Any], float, int]] = {}
        self.tools = agent_tools  # May be None initially and set later
        logging.debug("AI response cache initialized.")

        # Determine which AI provider to use
        self.ai_provider = getattr(self.cfg, 'AI_PROVIDER', 'gemini').lower()
        logging.debug(f"Using AI provider: {self.ai_provider}")

        # Get the appropriate API key based on the provider
        if self.ai_provider == 'gemini':
            if not self.cfg.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not set in the provided application configuration.")
            self.api_key = self.cfg.GEMINI_API_KEY
        elif self.ai_provider == 'deepseek':
            if not self.cfg.DEEPSEEK_API_KEY:
                raise ValueError("DEEPSEEK_API_KEY is not set in the provided application configuration.")
            self.api_key = self.cfg.DEEPSEEK_API_KEY
        elif self.ai_provider == 'ollama':
            # For Ollama, we use the base URL instead of API key
            self.api_key = getattr(self.cfg, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

        model_alias = model_alias_override or self.cfg.DEFAULT_MODEL_TYPE
        if not model_alias:
            raise ValueError("Model alias must be provided.")

        # Get the models configuration based on the provider
        if self.ai_provider == 'gemini':
            models_config = self.cfg.GEMINI_MODELS
            if not models_config or not isinstance(models_config, dict):
                raise ValueError("GEMINI_MODELS must be defined in app_config and be a non-empty dictionary.")
        elif self.ai_provider == 'deepseek':
            models_config = self.cfg.DEEPSEEK_MODELS
            if not models_config or not isinstance(models_config, dict):
                raise ValueError("DEEPSEEK_MODELS must be defined in app_config and be a non-empty dictionary.")
        elif self.ai_provider == 'ollama':
            models_config = self.cfg.OLLAMA_MODELS
            if not models_config or not isinstance(models_config, dict):
                raise ValueError("OLLAMA_MODELS must be defined in app_config and be a non-empty dictionary.")
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

        available_model_aliases = list(models_config.keys())
        if not available_model_aliases:
            raise ValueError(f"{self.ai_provider.upper()}_MODELS in app_config is empty.")
        
        # Handle model alias that doesn't match the provider
        if model_alias not in available_model_aliases:
            logging.warning(f"Model alias '{model_alias}' not found in {self.ai_provider.upper()}_MODELS. " +
                           f"Using default model for {self.ai_provider} provider.")
            # Use the first available model for this provider
            model_alias = available_model_aliases[0]
            # Also update the config to match
            if hasattr(self.cfg, 'update_setting_and_save'):
                self.cfg.update_setting_and_save("DEFAULT_MODEL_TYPE", model_alias)
                logging.debug(f"Updated DEFAULT_MODEL_TYPE setting to '{model_alias}' to match {self.ai_provider} provider")

        model_config_from_file = models_config.get(model_alias)
        if not model_config_from_file or not isinstance(model_config_from_file, dict):
            raise ValueError(f"Model configuration for alias '{model_alias}' not found or invalid.")

        actual_model_name = model_config_from_file.get('name')
        if not actual_model_name:
            raise ValueError(f"'name' field missing in app_config for alias '{model_alias}'.")

        self.model_alias = model_alias
        self.actual_model_name = actual_model_name

        # Initialize model using the adapter
        self._initialize_model(model_config_from_file, safety_settings_override)
        
        # Cache and history settings
        self.use_chat = self.cfg.USE_CHAT_MEMORY
        if self.use_chat is None:
            logging.warning("USE_CHAT_MEMORY not in app_config, defaulting to False.")
            self.use_chat = False
        
        if self.use_chat:
            self.max_history = self.cfg.MAX_CHAT_HISTORY
            if self.max_history is None:
                logging.warning("MAX_CHAT_HISTORY not in app_config, defaulting to 10.")
                self.max_history = 10
            logging.debug(f"Chat memory enabled (max history: {self.max_history} exchanges)")
            # Initialize chat history
            self.chat_history = {}
        else:
            logging.debug("Chat memory is disabled.")

    def _initialize_model(self, model_config, safety_settings_override):
        """Initialize the AI model with appropriate settings using the adapter."""
        try:
            # Check if the required dependencies are installed for the chosen provider
            from model_adapters import check_dependencies
            deps_installed, error_msg = check_dependencies(self.ai_provider)
            
            if not deps_installed:
                logging.error(f"Missing dependencies for {self.ai_provider}: {error_msg}")
                raise ImportError(error_msg)
            
            # Ensure we have a valid model name
            if not self.actual_model_name:
                raise ValueError("Model name must be provided.")
                    
            # Create model adapter
            self.model_adapter = create_model_adapter(
                provider=self.ai_provider,
                api_key=self.api_key,
                model_name=self.actual_model_name
            )
            
            # Set up safety settings
            safety_settings = safety_settings_override or getattr(self.cfg, 'AI_SAFETY_SETTINGS', None)
            
            # Initialize the model adapter
            self.model_adapter.initialize(model_config, safety_settings)
            
            logging.debug(f"AI Assistant initialized with model alias: {self.model_alias} (actual: {self.actual_model_name})")
            logging.debug(f"Model description: {model_config.get('description', 'N/A')}")
            logging.debug(f"Model provider: {self.ai_provider}")

        except Exception as e:
            logging.error(f"Failed to initialize AI model: {e}", exc_info=True)
            raise

    def _prepare_image_part(self, screenshot_bytes: Optional[bytes]) -> Optional[Image.Image]:
        """Prepare an image for the agent with optimized compression for LLM understanding."""
        if screenshot_bytes is None:
            return None
            
        try:
            img = Image.open(io.BytesIO(screenshot_bytes))
            original_size = len(screenshot_bytes)
            
            # Get AI provider for provider-specific optimizations
            ai_provider = getattr(self.cfg, 'AI_PROVIDER', 'gemini').lower()
            
            # Get provider capabilities from config
            try:
                from .config import AI_PROVIDER_CAPABILITIES
            except ImportError:
                from config import AI_PROVIDER_CAPABILITIES
            
            capabilities = AI_PROVIDER_CAPABILITIES.get(ai_provider, AI_PROVIDER_CAPABILITIES.get('gemini', {}))
            
            # Use provider-specific image settings
            max_width = capabilities.get('image_max_width', 640)
            quality = capabilities.get('image_quality', 75)
            image_format = capabilities.get('image_format', 'JPEG')
            
            logging.debug(f"Applying {ai_provider}-specific image optimization: {max_width}px width, {quality}% quality, {image_format} format")
            
            # Resize if necessary (maintain aspect ratio)
            if img.width > max_width:
                scale = max_width / img.width
                new_height = int(img.height * scale)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                logging.debug(f"Resized screenshot from {img.size} to fit max width {max_width}px")
            
            # Convert to RGB if necessary (for JPEG compatibility and better compression)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                    img = background
                else:
                    img = img.convert('RGB')
                logging.debug("Converted image to RGB format for optimal compression")
            
            # Apply sharpening to maintain text clarity after compression
            from PIL import ImageFilter, ImageEnhance
            # Mild sharpening to preserve text readability
            img = img.filter(ImageFilter.UnsharpMask(radius=0.5, percent=150, threshold=3))
            
            # Compress with optimized settings
            compressed_buffer = io.BytesIO()
            
            if image_format.upper() == 'JPEG':
                # Use progressive JPEG with chroma subsampling for maximum compression
                img.save(
                    compressed_buffer, 
                    format='JPEG', 
                    quality=quality, 
                    optimize=True,
                    progressive=True,  # Progressive JPEG for better compression
                    subsampling='4:2:0'  # Chroma subsampling reduces file size significantly
                )
            else:
                # Fallback to PNG if specified (though JPEG is better for photos/screenshots)
                img.save(compressed_buffer, format=image_format, optimize=True)
            
            compressed_buffer.seek(0)
            compressed_size = compressed_buffer.tell()
            
            # Reload the compressed image
            img = Image.open(compressed_buffer)
            
            # Calculate compression ratio
            compression_ratio = original_size / compressed_size if compressed_size > 0 else 1
            logging.debug(f"Compressed image: {original_size} -> {compressed_size} bytes ({compression_ratio:.1f}x compression)")
            logging.debug(f"Optimized image for {ai_provider}: {img.size}, {quality}% quality, {image_format} format")
            
            return img
            
        except Exception as e:
            logging.error(f"Failed to prepare image part for AI: {e}", exc_info=True)
            return None

    def _build_system_prompt(self, xml_context: str, previous_actions: List[str], available_actions: List[str], 
                            current_screen_visit_count: int, current_composite_hash: str, 
                            last_action_feedback: Optional[str] = None) -> str:
        """Build the system prompt for the agent."""
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
            feedback_section = f"""
            **CRITICAL FEEDBACK ON YOUR PREVIOUS ACTION:**
            {last_action_feedback}
            Based on this feedback, you MUST choose a different action to avoid getting stuck.
            """

        actual_available_actions = getattr(self.cfg, 'AVAILABLE_ACTIONS', available_actions)
        if not actual_available_actions:
            actual_available_actions = ["click", "input", "scroll_down", "scroll_up", "swipe_left", "swipe_right", "back"]

        action_list_str = "\n".join([f"- {a}: {action_descriptions.get(a, '')}" for a in actual_available_actions])
        history_str = "\n".join([f"- {pa}" for pa in previous_actions]) if previous_actions else "None"
        visit_context = f"CURRENT SCREEN CONTEXT:\n- Hash: {current_composite_hash}\n- Visit Count (this session): {current_screen_visit_count}"
        
        loop_threshold = getattr(self.cfg, 'LOOP_DETECTION_VISIT_THRESHOLD', 3)
        if loop_threshold is None: loop_threshold = 3

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
            REQUIRED ACTION CHANGES TO BREAK THE LOOP:
            1. DO NOT repeat recently failed or looped action sequences.
            2. Prioritize actions or elements that have NOT been tried recently on this screen.
            3. If all else fails and the app seems stuck, consider using 'back'.
            """
            
        test_email_val = os.environ.get("TEST_EMAIL", "test.user@example.com")
        test_password_val = os.environ.get("TEST_PASSWORD", "Str0ngP@ssw0rd!")
        test_name_val = os.environ.get("TEST_NAME", "Test User")
        
        input_value_guidance = f"""
        **Input Value Guidance (for input text):**
        - Email/Username: Use "{test_email_val}"
        - Password: Use "{test_password_val}"
        - Name: Use "{test_name_val}"
        - Other fields: Use realistic, context-appropriate test data.
        - AVOID generic placeholders like "test", "input", "asdf".
        """

        defer_authentication_guidance = """
        **STRATEGY: Defer Authentication Flows (Login/Registration):**
        - Primary goal: explore features accessible *without* immediate login/registration.
        - If other navigation options exist (e.g., "Explore as Guest", "Skip"), prioritize those.
        """

        # Check if image context is enabled
        enable_image_context = getattr(self.cfg, 'ENABLE_IMAGE_CONTEXT', True)
        
        if enable_image_context:
            context_description = "1. Screenshot: Provided as an image. This is your primary view.\n        2. XML Layout: Provided below (may be a snippet/absent). Use for attributes."
        else:
            context_description = "1. Screenshot: Not provided (image context disabled). Rely on XML layout for analysis.\n        2. XML Layout: Provided below. This is your primary source of UI information."
        
        prompt = f"""
        You are an expert Android app tester. Your goal is to:
        1. Determine the BEST SINGLE action to perform based on the visual screenshot and XML context, 
           prioritizing PROGRESSION and IN-APP feature discovery.

        {feedback_section}

        {visit_context}

        CONTEXT:
        {context_description}
        3. Previous Actions Taken *From This Exact Screen State* (if any):
        {history_str}

        TASK:
        Analyze the screenshot and XML.
        1. Identify the BEST SINGLE action to take next.
        2. Use the perform_ui_action tool to execute your chosen action.

        {defer_authentication_guidance}
        {visit_instruction}
        {input_value_guidance}

        Choose ONE action from the available list below:
        {action_list_str}

        When using the perform_ui_action tool, you MUST provide a JSON object with the following structure:
        {{
            "action": "click|input|scroll_down|scroll_up|swipe_left|swipe_right|back",
            "target_identifier": "optional identifier for the target element",
            "target_bounding_box": {{"top_left": [y1, x1], "bottom_right": [y2, x2]}},
            "input_text": "text to input if action is input",
            "reasoning": "brief explanation for choosing this action"
        }}

        XML CONTEXT:
        ```xml
        {xml_context if xml_context else "No XML context provided for this screen, or it was empty. Rely primarily on the screenshot."}
        ```
        """
        return prompt.strip()

    def _analyze_action_history(self, actions: List[str]) -> dict:
        """Analyze the action history to detect loops."""
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
                        screenshot_bytes: Optional[bytes],
                        xml_context: str,
                        previous_actions: List[str],
                        current_screen_visit_count: int,
                        current_composite_hash: str,
                        last_action_feedback: Optional[str] = None
                        ) -> Optional[Tuple[Dict[str, Any], float, int]]:
        """
        Uses the agent-based approach with the configured AI model to determine the next action to take.
        Returns the action data, processing time, and token count.
        """
        try:
            start_time = time.time()
            
            # Check if image context is enabled
            enable_image_context = getattr(self.cfg, 'ENABLE_IMAGE_CONTEXT', True)
            
            processed_image = None
            if enable_image_context:
                # Prepare image
                processed_image = self._prepare_image_part(screenshot_bytes)
                if not processed_image:
                    logging.error("Failed to process screenshot for AI analysis")
                    return None
            else:
                logging.debug("Image context disabled, using text-only analysis")
                
            # Build the system prompt
            available_actions = getattr(self.cfg, 'AVAILABLE_ACTIONS', [])
            prompt = self._build_system_prompt(
                xml_context,
                previous_actions,
                available_actions,
                current_screen_visit_count,
                current_composite_hash,
                last_action_feedback
            )
            
            # Generate response from the model
            try:
                response_text, metadata = self.model_adapter.generate_response(
                    prompt=prompt,
                    image=processed_image
                )
                elapsed_time = metadata.get("processing_time", time.time() - start_time)
                token_count = metadata.get("token_count", {}).get("total", len(prompt) // 4)
            except Exception as e:
                logging.error(f"Error generating AI response: {e}", exc_info=True)
                return None
                
            # Parse the action from the response
            action_data = self._parse_action_from_response(response_text)
            if not action_data:
                logging.error("Failed to parse action data from AI response")
                return None
                
            return {"action_to_perform": action_data}, elapsed_time, token_count
            
        except Exception as e:
            logging.error(f"Error in get_next_action: {e}", exc_info=True)
            return None
            
    def execute_action(self, action_data: Dict[str, Any]) -> bool:
        """
        Executes an action using the provided agent tools.
        
        Args:
            action_data: The action data to execute
            
        Returns:
            True if the action was successfully executed, False otherwise
        """
        if not self.tools:
            logging.error("Cannot execute action: AgentTools not available")
            return False
            
        action_type = action_data.get("action")
        if not action_type:
            logging.error("Cannot execute action: No action type provided")
            return False
            
        try:
            if action_type == "click":
                target_id = action_data.get("target_identifier")
                if not target_id:
                    # Try to use coordinates if available
                    bbox = action_data.get("target_bounding_box")
                    if bbox and isinstance(bbox, dict):
                        top_left = bbox.get("top_left", [])
                        bottom_right = bbox.get("bottom_right", [])
                        if len(top_left) == 2 and len(bottom_right) == 2:
                            center_y = (top_left[0] + bottom_right[0]) / 2
                            center_x = (top_left[1] + bottom_right[1]) / 2
                            result = self.tools.tap_coordinates(center_x, center_y)
                            return result.get("success", False)
                    logging.error("Cannot execute click: No target identifier or valid bounding box provided")
                    return False
                result = self.tools.click_element(target_id)
                return result.get("success", False)
                
            elif action_type == "input":
                target_id = action_data.get("target_identifier")
                input_text = action_data.get("input_text")
                if not target_id:
                    logging.error("Cannot execute input: No target identifier provided")
                    return False
                if input_text is None:
                    input_text = ""  # Empty string for clear operations
                result = self.tools.input_text(target_id, input_text)
                return result.get("success", False)
                
            elif action_type == "scroll_down":
                result = self.tools.scroll("down")
                return result.get("success", False)
                
            elif action_type == "scroll_up":
                result = self.tools.scroll("up")
                return result.get("success", False)
                
            elif action_type == "swipe_left":
                result = self.tools.scroll("left")
                return result.get("success", False)
                
            elif action_type == "swipe_right":
                result = self.tools.scroll("right")
                return result.get("success", False)
                
            elif action_type == "back":
                result = self.tools.press_back()
                return result.get("success", False)
                
            else:
                logging.error(f"Unknown action type: {action_type}")
                return False
                
        except Exception as e:
            logging.error(f"Error executing action: {e}", exc_info=True)
            return False
            
    def plan_and_execute(self, 
                        screenshot_bytes: Optional[bytes],
                        xml_context: str,
                        previous_actions: List[str],
                        current_screen_visit_count: int,
                        current_composite_hash: str,
                        last_action_feedback: Optional[str] = None) -> Optional[Tuple[Dict[str, Any], float, bool]]:
        """
        Plans and executes the next action using a ReAct-style approach where the agent:
        1. Reasons about the current state
        2. Decides on an action
        3. Executes the action
        4. Observes the result
        5. Repeats as needed
        
        Returns:
            Tuple of (action_data, processing_time, success)
        """
        if not self.tools:
            logging.error("Cannot plan and execute: AgentTools not available")
            return None
            
        # Check if image context is enabled and screenshot is available
        enable_image_context = getattr(self.cfg, 'ENABLE_IMAGE_CONTEXT', True)
        if enable_image_context and screenshot_bytes is None:
            logging.error("Cannot plan and execute: Screenshot bytes is None but image context is enabled")
            return None
        elif not enable_image_context and screenshot_bytes is None:
            logging.debug("Image context disabled and no screenshot provided - using text-only analysis")
            
        # Get the next action suggestion from the model
        result = self.get_next_action(
            screenshot_bytes,
            xml_context,
            previous_actions,
            current_screen_visit_count,
            current_composite_hash,
            last_action_feedback
        )
        
        if not result:
            return None
            
        response, elapsed_time, _ = result
        
        action_data = response.get("action_to_perform")
        if not action_data:
            return None
            
        # Execute the action using agent tools
        success = self.execute_action(action_data)
        
        # Return the action data, time taken, and success status
        return action_data, elapsed_time, success
            
    def _clean_and_parse_json(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Clean and parse potentially malformed JSON from AI responses."""
        cleaned = json_str.strip()  # Initialize cleaned variable
        try:
            # First, try direct parsing
            return json.loads(json_str)
        except json.JSONDecodeError:
            # If direct parsing fails, try to fix common issues
            try:
                # More robust single quote to double quote conversion
                # Use a more careful approach to avoid breaking apostrophes in text

                # First, handle object keys: 'key': -> "key":
                cleaned = re.sub(r"'([^']+)'\s*:", r'"\1":', cleaned)

                # Then handle string values: : 'value' -> : "value"
                # But be careful not to replace apostrophes within the string
                cleaned = re.sub(r":\s*'([^']*)'", r': "\1"', cleaned)
                cleaned = re.sub(r":\s*'([^']*)'\s*,", r': "\1",', cleaned)
                cleaned = re.sub(r":\s*'([^']*)'\s*}", r': "\1"}', cleaned)
                cleaned = re.sub(r":\s*'([^']*)'\s*]", r': "\1"]', cleaned)

                # Handle arrays: ['item1', 'item2'] -> ["item1", "item2"]
                cleaned = re.sub(r"\[\s*'([^']*)'\s*\]", r'["\1"]', cleaned)
                cleaned = re.sub(r"'([^']*)'\s*,", r'"\1",', cleaned)
                cleaned = re.sub(r"'([^']*)'\s*]", r'"\1"]', cleaned)

                # Remove trailing commas before closing braces/brackets
                cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)

                # Fix any remaining single quotes that might be in the middle of strings
                # This is a last resort and might break some cases
                cleaned = re.sub(r"'([^']*)'", r'"\1"', cleaned)

                # Try parsing the cleaned JSON
                return json.loads(cleaned)
            except (json.JSONDecodeError, Exception) as e:
                logging.debug(f"Failed to clean and parse JSON: {e}. Original: {json_str[:200]}...")
                logging.debug(f"Cleaned version: {cleaned[:200]}...")
                return None

    def _parse_action_from_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse the action data from the model's response text."""
        try:
            # Log the raw response for debugging
            logging.debug(f"Raw AI response (first 500 chars): {response_text[:500]}")
            
            # Look for JSON pattern in the response
            json_pattern = r'```json\s*(.*?)\s*```'
            json_match = re.search(json_pattern, response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                logging.debug(f"Found JSON in code block: {json_str[:200]}...")
                action_data = self._clean_and_parse_json(json_str)
                if action_data:
                    logging.debug("Successfully parsed JSON from code block")
                else:
                    logging.warning("Failed to parse JSON from code block, trying fallback methods")
            else:
                # Try to find any JSON-like structure
                potential_json = re.search(r'({[\s\S]*?})', response_text)
                if potential_json:
                    json_str = potential_json.group(1)
                    logging.debug(f"Found potential JSON structure: {json_str[:200]}...")
                    action_data = self._clean_and_parse_json(json_str)
                    if action_data:
                        logging.debug("Successfully parsed JSON from regex match")
                    else:
                        logging.warning("Failed to parse JSON from regex match, trying manual parsing")
                else:
                    action_data = None
                    logging.debug("No JSON structure found in response, will try manual parsing")
            
            # If JSON parsing failed, try manual parsing as fallback
            if not action_data:
                logging.debug("Attempting manual parsing of AI response")
                action_data = self._manual_parse_action_response(response_text)
            
            # Validate the action data
            if action_data:
                required_fields = ["action", "reasoning"]
                if not all(field in action_data for field in required_fields):
                    logging.warning(f"Missing required fields in action data: {action_data}")
                    # Add default reasoning if missing
                    if "reasoning" not in action_data:
                        action_data["reasoning"] = "No explicit reasoning provided"
                
                return action_data
            else:
                logging.error("Failed to parse action data from AI response")
                logging.error(f"Full AI response: {response_text}")
                return None
            
            return action_data
            
        except Exception as e:
            logging.error(f"Error parsing action from response: {e}", exc_info=True)
            logging.error(f"Response text that caused error: {response_text[:1000]}...")
            return None
    
    def _manual_parse_action_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Manually parse action data from AI response when JSON parsing fails."""
        try:
            # Determine action type with more comprehensive patterns
            action_type = None
            response_lower = response_text.lower()
            
            # More comprehensive action detection
            action_patterns = [
                (r'\bclick\b', "click"),
                (r'\binput\b|\btype\b|\benter\b', "input"),
                (r'\bscroll_down\b|\bscroll down\b|\bscroll\b.*down', "scroll_down"),
                (r'\bscroll_up\b|\bscroll up\b', "scroll_up"),
                (r'\bswipe_left\b|\bswipe left\b|\bswipe\b.*left', "swipe_left"),
                (r'\bswipe_right\b|\bswipe right\b|\bswipe\b.*right', "swipe_right"),
                (r'\bback\b|\bgo back\b|\bnavigate back\b', "back")
            ]
            
            for pattern, action in action_patterns:
                if re.search(pattern, response_lower):
                    action_type = action
                    break
            
            if not action_type:
                logging.warning("Could not determine action type from response")
                logging.debug(f"Response text: {response_text[:300]}...")
                return None
            
            # Extract reasoning with multiple patterns
            reasoning = "AI determined action"
            reasoning_patterns = [
                r'reasoning["\s:]+([^"]+)',
                r'reason["\s:]+([^"]+)',
                r'reasoning:\s*([^\n]+)',
                r'reason:\s*([^\n]+)',
                r'because\s+([^.\n]+)',
                r'to\s+([^.\n]+)',
                r'I\s+([^.\n]+)',
                r'action:\s*([^\n]+)'
            ]
            
            for pattern in reasoning_patterns:
                match = re.search(pattern, response_text, re.IGNORECASE)
                if match:
                    reasoning = match.group(1).strip()
                    # Clean up the reasoning
                    reasoning = re.sub(r'^["\']|["\']$', '', reasoning)  # Remove quotes
                    reasoning = re.sub(r'[.]$', '', reasoning)  # Remove trailing period
                    break
            
            # Create basic action data
            action_data: Dict[str, Any] = {
                "action": action_type,
                "reasoning": reasoning
            }
            
            # Try to extract target identifier with multiple patterns
            target_patterns = [
                r'target_identifier["\s:]+([^",\s]+)',
                r'target["\s:]+([^",\s]+)',
                r'target_id["\s:]+([^",\s]+)',
                r'id["\s:]+([^",\s]+)',
                r'element["\s:]+([^",\s]+)',
                r'on\s+["\']([^"\']+)["\']',
                r'["\']([^"\']+)["\']\s+element',
                r'button\s+["\']([^"\']+)["\']',
                r'field\s+["\']([^"\']+)["\']'
            ]
            
            for pattern in target_patterns:
                match = re.search(pattern, response_text, re.IGNORECASE)
                if match:
                    action_data["target_identifier"] = match.group(1).strip()
                    break
            
            # Try to extract bounding box with more patterns
            bbox_patterns = [
                r'target_bounding_box["\s:]+({[^}]+})',
                r'bounding_box["\s:]+({[^}]+})',
                r'bbox["\s:]+({[^}]+})',
                r'coordinates["\s:]+({[^}]+})',
                r'box["\s:]+({[^}]+})',
                r'position["\s:]+({[^}]+})'
            ]
            
            for pattern in bbox_patterns:
                match = re.search(pattern, response_text, re.IGNORECASE)
                if match:
                    try:
                        bbox_str = match.group(1).strip()
                        parsed_bbox = self._clean_and_parse_json(bbox_str)
                        if parsed_bbox:
                            action_data["target_bounding_box"] = parsed_bbox
                            break
                    except:
                        continue
            
            # Try to extract input text for input actions with more patterns
            if action_type == "input":
                input_patterns = [
                    r'input_text["\s:]+([^"]+)',
                    r'text["\s:]+([^"]+)',
                    r'input["\s:]+([^"]+)',
                    r'value["\s:]+([^"]+)',
                    r'type\s+["\']([^"\']+)["\']',
                    r'enter\s+["\']([^"\']+)["\']',
                    r'["\']([^"\']+)["\']\s+into',
                    r'with\s+["\']([^"\']+)["\']'
                ]
                
                for pattern in input_patterns:
                    match = re.search(pattern, response_text, re.IGNORECASE)
                    if match:
                        action_data["input_text"] = match.group(1).strip()
                        break
                
                # If no input text found, try to extract from general text
                if "input_text" not in action_data:
                    text_match = re.search(r'(?:type|enter|input)\s+["\']([^"\']+)["\']', response_text, re.IGNORECASE)
                    if text_match:
                        action_data["input_text"] = text_match.group(1).strip()
            
            logging.debug(f"Manually parsed action: {action_type}, reasoning: {reasoning}")
            if "target_identifier" in action_data:
                logging.debug(f"Target identifier: {action_data['target_identifier']}")
            if "input_text" in action_data:
                logging.debug(f"Input text: {action_data['input_text']}")
            return action_data
            
        except Exception as e:
            logging.error(f"Error in manual parsing: {e}", exc_info=True)
            return None
