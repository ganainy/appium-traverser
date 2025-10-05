import os
import logging
import time
import json
from typing import Any, Dict, List, Optional, Tuple
import re
from PIL import Image
import io
from datetime import datetime

# Try both relative and absolute imports to support different execution contexts
try:
    # When running as a module within the traverser_ai_api package
    from traverser_ai_api.model_adapters import create_model_adapter
except ImportError:
    # When running directly from the traverser_ai_api directory
    from model_adapters import create_model_adapter

class AgentAssistant:
    """
    Handles interactions with AI models (Google Gemini, OpenRouter, Ollama) using adapters.
    Implements structured prompting for mobile app UI testing.
    
    The AgentAssistant can also directly perform actions using the AgentTools, allowing it to 
    implement more complex behaviors like planning, self-correction, and memory.
    """
    
    def __init__(self,
                app_config, # Type hint with your actual Config class
                model_alias_override: Optional[str] = None,
                safety_settings_override: Optional[Dict] = None,
                agent_tools=None,
                ui_callback=None):
        self.cfg = app_config
        self.response_cache: Dict[str, Tuple[Dict[str, Any], float, int]] = {}
        self.tools = agent_tools  # May be None initially and set later
        self.ui_callback = ui_callback  # Callback for UI updates
        logging.debug("AI response cache initialized.")

        # Determine which AI provider to use
        self.ai_provider = getattr(self.cfg, 'AI_PROVIDER', 'gemini').lower()
        logging.debug(f"Using AI provider: {self.ai_provider}")

        # Adapter provider override (for routing purposes without changing UI label)
        self._adapter_provider_override: Optional[str] = None

        # Get the appropriate API key based on the provider
        if self.ai_provider == 'gemini':
            if not self.cfg.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not set in the provided application configuration.")
            self.api_key = self.cfg.GEMINI_API_KEY
        elif self.ai_provider == 'openrouter':
            if not getattr(self.cfg, 'OPENROUTER_API_KEY', None):
                raise ValueError("OPENROUTER_API_KEY is not set in the provided application configuration.")
            self.api_key = self.cfg.OPENROUTER_API_KEY
        elif self.ai_provider == 'ollama':
            # For Ollama, we use the base URL instead of API key
            self.api_key = getattr(self.cfg, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

        model_alias = model_alias_override or self.cfg.DEFAULT_MODEL_TYPE
        # For OpenRouter, allow raw alias when dropdown-selected model isn't in predefined aliases
        openrouter_raw_alias = False
        # Respect explicit no-selection from UI
        if not model_alias or str(model_alias).strip() in ["", "No model selected"]:
            raise ValueError("No model selected. Please choose a model in AI Settings (Default Model Type).")

        # Get the models configuration based on the provider
        if self.ai_provider == 'gemini':
            models_config = self.cfg.GEMINI_MODELS
            if not models_config or not isinstance(models_config, dict):
                raise ValueError("GEMINI_MODELS must be defined in app_config and be a non-empty dictionary.")
        elif self.ai_provider == 'ollama':
            models_config = self.cfg.OLLAMA_MODELS
            if not models_config or not isinstance(models_config, dict):
                raise ValueError("OLLAMA_MODELS must be defined in app_config and be a non-empty dictionary.")
        elif self.ai_provider == 'openrouter':
            models_config = getattr(self.cfg, 'OPENROUTER_MODELS', None)
            if not models_config or not isinstance(models_config, dict) or len(models_config) == 0:
                # Allow direct ID if user selected a raw OpenRouter model string
                if isinstance(model_alias, str) and '/' in model_alias:
                    openrouter_raw_alias = True
                    models_config = {}
                    logging.info("OpenRouter: using direct model id without configured aliases.")
                else:
                    raise ValueError("OPENROUTER_MODELS is not configured and no direct model id provided. Please select a model in AI Settings.")
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

        available_model_aliases = list(models_config.keys())
        if not available_model_aliases and not (self.ai_provider == 'openrouter' and 'openrouter_raw_alias' in locals() and openrouter_raw_alias):
            raise ValueError(f"{self.ai_provider.upper()}_MODELS in app_config is empty. Please configure models or select a direct model id.")
        
        # Handle model alias that doesn't match the provider
        requested_alias = model_alias
        if model_alias not in available_model_aliases:
            # If OpenRouter and alias is a direct id, treat as raw alias
            if self.ai_provider == 'openrouter' and '/' in str(model_alias):
                openrouter_raw_alias = True
                logging.info(f"OpenRouter: using direct model id '{model_alias}'.")
            # For Ollama, try to extract the base model name by removing tags
            elif self.ai_provider == 'ollama':
                base_model_alias = self._extract_base_model_name(model_alias)
                
                # First try exact match with base name
                if base_model_alias in available_model_aliases:
                    model_alias = base_model_alias
                    logging.debug(f"Matched base model alias '{base_model_alias}' from model name '{model_alias}'")
                else:
                    # Try fuzzy matching by finding aliases that start with the base name
                    matching_aliases = [alias for alias in available_model_aliases if alias.startswith(base_model_alias)]
                    if matching_aliases:
                        model_alias = matching_aliases[0]
                        logging.debug(f"Fuzzy-matched model alias '{model_alias}' from base name '{base_model_alias}'")
                    else:
                        logging.warning(f"Model alias '{model_alias}' (base: '{base_model_alias}') not found in {self.ai_provider.upper()}_MODELS. " +
                                    f"Using default model for {self.ai_provider} provider.")
                        # Use the first available model for this provider
                        model_alias = available_model_aliases[0]
                        # Also update the config to match
                        if hasattr(self.cfg, 'update_setting_and_save'):
                            self.cfg.update_setting_and_save("DEFAULT_MODEL_TYPE", model_alias)
                            logging.debug(f"Updated DEFAULT_MODEL_TYPE setting to '{model_alias}' to match {self.ai_provider} provider")
            elif self.ai_provider in ['openrouter'] and not openrouter_raw_alias:
                # Do not auto-fallback; require explicit selection
                raise ValueError(f"OpenRouter: alias '{requested_alias}' not found in configured OPENROUTER_MODELS and no direct model id was provided.")
            else:
                logging.warning(f"Model alias '{model_alias}' not found in {self.ai_provider.upper()}_MODELS. " +
                               f"Using default model for {self.ai_provider} provider.")
                # Do not auto-select; require explicit selection
                raise ValueError(f"Model alias '{model_alias}' not found in {self.ai_provider.upper()}_MODELS. Please select a model explicitly.")

        model_config_from_file = models_config.get(model_alias)
        if (not model_config_from_file or not isinstance(model_config_from_file, dict)):
            if self.ai_provider == 'openrouter' and openrouter_raw_alias:
                # Build a fallback config using the raw alias as the actual model name
                model_config_from_file = {
                    'name': model_alias,
                    'description': f"Direct OpenRouter model '{model_alias}'",
                    'generation_config': {'temperature': 0.7, 'top_p': 0.95, 'max_output_tokens': 4096},
                    'online': True
                }
                logging.info(f"OpenRouter: using direct model '{model_alias}' with default generation settings.")
            else:
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

        self.ai_interaction_readable_logger = None

    def _initialize_model(self, model_config, safety_settings_override):
        """Initialize the AI model with appropriate settings using the adapter."""
        try:
            # Check if the required dependencies are installed for the chosen provider
            from model_adapters import check_dependencies
            adapter_provider = self._adapter_provider_override or self.ai_provider
            deps_installed, error_msg = check_dependencies(adapter_provider)
            
            if not deps_installed:
                logging.error(f"Missing dependencies for {adapter_provider}: {error_msg}")
                raise ImportError(error_msg)
            
            # Ensure we have a valid model name
            if not self.actual_model_name:
                raise ValueError("Model name must be provided.")
                    
            # Create model adapter
            self.model_adapter = create_model_adapter(
                provider=adapter_provider,
                api_key=self.api_key,
                model_name=self.actual_model_name
            )
            
            # Set up safety settings
            safety_settings = safety_settings_override or getattr(self.cfg, 'AI_SAFETY_SETTINGS', None)
            
            # Initialize the model adapter
            self.model_adapter.initialize(model_config, safety_settings)
            
            logging.debug(f"AI Assistant initialized with model alias: {self.model_alias} (actual: {self.actual_model_name})")
            logging.debug(f"Model description: {model_config.get('description', 'N/A')}")
            logging.debug(f"Model provider label: {self.ai_provider} | adapter: {adapter_provider}")

        except Exception as e:
            logging.error(f"Failed to initialize AI model: {e}", exc_info=True)
            raise

    def _setup_ai_interaction_logger(self):
        """Initializes only the human-readable logger (JSONL removed)."""
        if self.ai_interaction_readable_logger and self.ai_interaction_readable_logger.handlers:
            return  # Already configured

        target_log_dir = getattr(self.cfg, 'LOG_DIR', None)
        try:
            if target_log_dir:
                os.makedirs(target_log_dir, exist_ok=True)
        except OSError as e:
            logging.error(f"Could not create logs directory for AI interactions: {e}")

        # Human-readable logger
        self.ai_interaction_readable_logger = logging.getLogger('AIInteractionReadableLogger')
        self.ai_interaction_readable_logger.setLevel(logging.INFO)
        self.ai_interaction_readable_logger.propagate = False
        if self.ai_interaction_readable_logger.hasHandlers():
            self.ai_interaction_readable_logger.handlers.clear()

        if target_log_dir:
            try:
                readable_path = os.path.join(target_log_dir, 'ai_interactions_readable.log')
                fh_readable = logging.FileHandler(readable_path, encoding='utf-8')
                fh_readable.setLevel(logging.INFO)
                fh_readable.setFormatter(logging.Formatter('%(message)s'))
                self.ai_interaction_readable_logger.addHandler(fh_readable)
                logging.info(f"AI interaction readable logger initialized at: {readable_path}")
            except OSError as e:
                logging.error(f"Could not create AI interactions readable log file: {e}")
                self.ai_interaction_readable_logger.addHandler(logging.NullHandler())
        else:
            logging.error("Log directory not available, AI interaction readable log will not be saved.")
            self.ai_interaction_readable_logger.addHandler(logging.NullHandler())


    def _prepare_image_part(self, screenshot_bytes: Optional[bytes]) -> Optional[Image.Image]:
        """Prepare an image for the agent with config-driven preprocessing before model encoding.

        Steps:
        - Decode screenshot bytes to PIL Image
        - Optional: Crop status/nav bars using configured percentages
        - Resize down to configured max width (no upscaling), preserve aspect ratio
        - Convert to RGB for consistent compression downstream
        - Apply mild sharpening to preserve text clarity
        - Return processed PIL Image (model adapters will handle provider-specific encoding)
        """
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
            
            # Resolve preprocessing settings (global overrides take precedence)
            max_width = getattr(self.cfg, 'IMAGE_MAX_WIDTH', None) or capabilities.get('image_max_width', 640)
            quality = getattr(self.cfg, 'IMAGE_QUALITY', None) or capabilities.get('image_quality', 75)
            image_format = getattr(self.cfg, 'IMAGE_FORMAT', None) or capabilities.get('image_format', 'JPEG')
            crop_bars = getattr(self.cfg, 'IMAGE_CROP_BARS', True)
            crop_top_pct = float(getattr(self.cfg, 'IMAGE_CROP_TOP_PERCENT', 0.06) or 0.0)
            crop_bottom_pct = float(getattr(self.cfg, 'IMAGE_CROP_BOTTOM_PERCENT', 0.06) or 0.0)
            
            logging.debug(
                f"Image preprocessing settings -> provider: {ai_provider}, max_width: {max_width}, "
                f"quality: {quality}, format: {image_format}, crop_bars: {crop_bars}, "
                f"top_pct: {crop_top_pct}, bottom_pct: {crop_bottom_pct}"
            )

            # Optional: crop status bar and bottom nav/keyboard areas before resizing
            if crop_bars and (crop_top_pct > 0 or crop_bottom_pct > 0):
                try:
                    h = img.height
                    crop_top_px = int(max(0, min(1.0, crop_top_pct)) * h)
                    crop_bottom_px = int(max(0, min(1.0, crop_bottom_pct)) * h)
                    # Ensure we don't invert or over-crop
                    upper = crop_top_px
                    lower = max(upper + 1, h - crop_bottom_px)
                    if lower > upper:
                        img = img.crop((0, upper, img.width, lower))
                        logging.debug(f"Cropped bars: top {crop_top_px}px, bottom {crop_bottom_px}px -> new size {img.size}")
                except Exception as crop_err:
                    logging.warning(f"Failed to crop bars: {crop_err}")
            
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
            
            # Note: We return the processed PIL Image. Encoding (format/quality) is handled by model adapters.
            # Still, estimate potential savings for logging by encoding briefly to measure size.
            try:
                compressed_buffer = io.BytesIO()
                if image_format.upper() == 'JPEG':
                    img.save(
                        compressed_buffer,
                        format='JPEG',
                        quality=quality,
                        optimize=True,
                        progressive=True,
                        subsampling='4:2:0'
                    )
                else:
                    img.save(compressed_buffer, format=image_format, optimize=True)
                compressed_size = compressed_buffer.tell()
                compression_ratio = original_size / compressed_size if compressed_size > 0 else 1
                logging.debug(
                    f"Preprocessed image size estimate: {original_size} -> {compressed_size} bytes "
                    f"({compression_ratio:.1f}x). Final encoding will be done by adapter."
                )
            except Exception as est_err:
                logging.debug(f"Could not estimate compressed size: {est_err}")
            
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
            visit_instruction = (
                f"LOOP ALERT: visits={current_screen_visit_count}. "
                f"Looping actions: {repeated_text}. Tried: {tried_text}. "
                "Choose a different action/element; use 'back' if stuck."
            )
            
        test_email_val = os.environ.get("TEST_EMAIL", "test.user@example.com")
        test_password_val = os.environ.get("TEST_PASSWORD", "Str0ngP@ssw0rd!")
        test_name_val = os.environ.get("TEST_NAME", "Test User")
        
        input_value_guidance = f"Input hints: email {test_email_val}, password {test_password_val}, name {test_name_val}. Use realistic values; avoid placeholders."

        defer_authentication_guidance = "Strategy: Prefer non-auth flows (Guest/Skip) to explore features first."

        # Check if image context is enabled
        enable_image_context = getattr(self.cfg, 'ENABLE_IMAGE_CONTEXT', True)
        
        if enable_image_context:
            context_description = "1. Screenshot: Provided as an image. This is your primary view.\n        2. XML Layout: Provided below (may be a snippet/absent). Use for attributes."
        else:
            context_description = "1. Screenshot: Not provided (image context disabled). Rely on XML layout for analysis.\n        2. XML Layout: Provided below. This is your primary source of UI information."
        
        # Build focus areas section
        focus_areas_section = self._build_focus_areas_section()
        
        # NEW: Enhanced JSON output guidance section with stricter contract
        json_output_guidance = (
        "Return a JSON object in a ```json code block with keys: action, target_identifier, "
        "target_bounding_box, input_text, reasoning, focus_influence. Rules: "
        "target_identifier MUST be a single raw value for ONE attribute only (choose one of: resource-id like com.pkg:id/name, content-desc, or visible text). "
        "Do NOT include prefixes like 'id=' or 'content-desc=' and do NOT combine multiple attributes with '|'. "
        "target_bounding_box MUST be an object {top_left:[y,x], bottom_right:[y,x]} (absolute pixels or normalized 0..1). "
        "Do NOT use string formats like '[x,y][x2,y2]'. Use null for scroll/back if bbox/identifier are not applicable. "
        "No text outside the JSON."
        )
        
        prompt = f"""
        You are an expert Android app tester. Your goal is to:
        1. Determine the BEST SINGLE action to perform based on the visual screenshot and XML context, 
           prioritizing PROGRESSION and IN-APP feature discovery.

        {feedback_section}
        {focus_areas_section}

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

        {json_output_guidance}

        XML CONTEXT:
        ```xml
        {xml_context if xml_context else "No XML context provided for this screen, or it was empty. Rely primarily on the screenshot."}
        ```
        """
        return prompt.strip()

    def _build_focus_areas_section(self) -> str:
        """Build the focus areas section of the prompt."""
        focus_areas = getattr(self.cfg, 'FOCUS_AREAS', [])
        
        if not focus_areas:
            return ""
        
        # Sort by priority and filter enabled
        enabled_areas = [area for area in focus_areas if area.get('enabled', True)]
        enabled_areas.sort(key=lambda x: x.get('priority', 0))
        
        # Limit to top-K active areas to control prompt size
        max_active = getattr(self.cfg, 'FOCUS_MAX_ACTIVE', 5)
        if isinstance(max_active, int) and max_active > 0:
            enabled_areas = enabled_areas[:max_active]
        
        if not enabled_areas:
            return ""
        
        # Create focus area reference list
        focus_reference = "\n".join([
            f"- {area['id']}: {area['name']}" 
            for area in enabled_areas
        ])
        
        focus_text = "\n".join([area['prompt_modifier'] for area in enabled_areas])
        
        return f"""
        **ACTIVE FOCUS AREAS:**
        {focus_text}
        
        **FOCUS AREA IDs (use these in focus_influence):**
        {focus_reference}
        """

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
                # Pass config-driven image encoding preferences to the adapter so UI controls take effect
                img_fmt_override = getattr(self.cfg, 'IMAGE_FORMAT', None)
                img_quality_override = getattr(self.cfg, 'IMAGE_QUALITY', None)
                response_text, metadata = self.model_adapter.generate_response(
                    prompt=prompt,
                    image=processed_image,
                    image_format=img_fmt_override,
                    image_quality=img_quality_override
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

            # --- Log AI interaction ---
            try:
                self._setup_ai_interaction_logger()
                if self.ai_interaction_readable_logger:
                    readable_entry = (
                        f"=== AI Interaction @ {datetime.utcnow().isoformat()}Z ===\n"
                        f"Model: {self.model_alias}\n"
                        f"Tokens: {token_count}\n\n"
                        f"Prompt:\n{prompt}\n\n"
                        f"Response:\n{json.dumps(action_data, ensure_ascii=False, indent=2)}\n"
                        f"----------------------------------------\n"
                    )
                    self.ai_interaction_readable_logger.info(readable_entry)
            except Exception as log_err:
                logging.error(f"Failed to log AI interaction: {log_err}")
            # --- End log AI interaction ---

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
            success = False
            
            if action_type == "click":
                target_id = action_data.get("target_identifier")
                if not target_id:
                    # Try to use coordinates if available
                    bbox = action_data.get("target_bounding_box")
                    if bbox and isinstance(bbox, dict):
                        top_left = bbox.get("top_left", [])
                        bottom_right = bbox.get("bottom_right", [])
                        if len(top_left) == 2 and len(bottom_right) == 2:
                            # FIX: Bounding box format is {"top_left": [y1, x1], "bottom_right": [y2, x2]}
                            y1, x1 = top_left
                            y2, x2 = bottom_right
                            center_x = (x1 + x2) / 2  # CORRECT
                            center_y = (y1 + y2) / 2  # CORRECT
                            
                            # Add coordinate validation
                            window_size = self.tools.driver.get_window_size()
                            if window_size:
                                screen_width = window_size['width']
                                screen_height = window_size['height']
                                
                                # Clamp coordinates to screen bounds
                                center_x = max(0, min(center_x, screen_width - 1))
                                center_y = max(0, min(center_y, screen_height - 1))
                                
                                logging.debug(f"Calculated tap coordinates: ({center_x}, {center_y}) from bbox {bbox}")
                                result = self.tools.tap_coordinates(center_x, center_y, normalized=False)
                                success = result.get("success", False)
                            else:
                                logging.error("Cannot get screen size for coordinate validation")
                                return False
                    else:
                        logging.error("Cannot execute click: No target identifier or valid bounding box provided")
                        return False
                else:
                    result = self.tools.click_element(target_id)
                    success = result.get("success", False)
                    
            elif action_type == "input":
                target_id = action_data.get("target_identifier")
                input_text = action_data.get("input_text")
                if not target_id:
                    logging.error("Cannot execute input: No target identifier provided")
                    return False
                if input_text is None:
                    input_text = ""  # Empty string for clear operations
                result = self.tools.input_text(target_id, input_text)
                success = result.get("success", False)
                
            elif action_type == "scroll_down":
                result = self.tools.scroll("down")
                success = result.get("success", False)
                
            elif action_type == "scroll_up":
                result = self.tools.scroll("up")
                success = result.get("success", False)
                
            elif action_type == "swipe_left":
                result = self.tools.scroll("left")
                success = result.get("success", False)
                
            elif action_type == "swipe_right":
                result = self.tools.scroll("right")
                success = result.get("success", False)
                
            elif action_type == "back":
                result = self.tools.press_back()
                success = result.get("success", False)
            
            elif action_type == "long_press":
                target_id = action_data.get("target_identifier")
                bbox = action_data.get("target_bounding_box")
                # Default duration from config
                try:
                    default_duration_ms = int(getattr(self.cfg, 'LONG_PRESS_MIN_DURATION_MS', 600))
                except Exception:
                    default_duration_ms = 600
                duration_ms = action_data.get("duration_ms", default_duration_ms)
                if not target_id and bbox and isinstance(bbox, dict):
                    top_left = bbox.get("top_left", [])
                    bottom_right = bbox.get("bottom_right", [])
                    if len(top_left) == 2 and len(bottom_right) == 2:
                        # Compute center to long press
                        y1, x1 = top_left
                        y2, x2 = bottom_right
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        window_size = self.tools.driver.get_window_size()
                        if window_size:
                            screen_width = window_size['width']
                            screen_height = window_size['height']
                            center_x = max(0, min(center_x, screen_width - 1))
                            center_y = max(0, min(center_y, screen_height - 1))
                            # Use coordinate tap with duration for long press
                            result = self.tools.tap_coordinates(center_x, center_y, normalized=False, duration_ms=duration_ms)
                            success = result.get("success", False)
                        else:
                            logging.error("Cannot get screen size for coordinate validation")
                            return False
                    else:
                        logging.error("Invalid bounding box format for long_press")
                        return False
                else:
                    # Prefer element-based long press via tools
                    result = self.tools.long_press(target_id, bbox, duration_ms)
                    success = result.get("success", False)

            else:
                logging.error(f"Unknown action type: {action_type}")
                return False
                
            # If execution was successful and we have a UI callback, notify the UI
            if success and self.ui_callback:
                try:
                    self.ui_callback(action_data)
                except Exception as e:
                    logging.error(f"Error calling UI callback: {e}")
                    
            # Output focus attribution to stdout for UI monitoring
            if success and action_data.get('focus_influence'):
                focus_ids = action_data.get('focus_influence', [])
                if focus_ids:
                    # Get focus area names for better readability
                    focus_names = []
                    focus_areas = getattr(self.cfg, 'FOCUS_AREAS', [])
                    for focus_id in focus_ids:
                        for area in focus_areas:
                            if isinstance(area, dict) and area.get('id') == focus_id:
                                focus_names.append(area.get('name', focus_id))
                                break
                    
                    focus_info = {
                        'action': action_data.get('action', 'unknown'),
                        'focus_ids': focus_ids,
                        'focus_names': focus_names,
                        'reasoning': action_data.get('reasoning', '')
                    }
                    
                    # Output to stdout with UI_FOCUS prefix for UI to capture (JSON for robust parsing)
                    try:
                        print(f"UI_FOCUS:{json.dumps(focus_info, ensure_ascii=False)}")
                    except Exception:
                        # Fallback to string representation if JSON serialization fails
                        print(f"UI_FOCUS:{focus_info}")
                    
            return success
            
        except Exception as e:
            logging.error(f"Error executing action: {e}", exc_info=True)
            return False
            
    def plan_and_execute(self, 
                        screenshot_bytes: Optional[bytes],
                        xml_context: str,
                        previous_actions: List[str],
                        current_screen_visit_count: int,
                        current_composite_hash: str,
                        last_action_feedback: Optional[str] = None) -> Optional[Tuple[Dict[str, Any], float, int, bool]]:
        """
        Plans and executes the next action using a ReAct-style approach where the agent:
        1. Reasons about the current state
        2. Decides on an action
        3. Executes the action
        4. Observes the result
        5. Repeats as needed
        
        Returns:
            Tuple of (action_data, processing_time, total_tokens, success)
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
            
        response, elapsed_time, total_tokens = result
        
        action_data = response.get("action_to_perform")
        if not action_data:
            return None
            
        # Execute the action using agent tools
        success = self.execute_action(action_data)
        
        # Return the action data, time taken, token count, and success status
        return action_data, elapsed_time, total_tokens, success
            
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
        """Parse the action data from the model's response text using a two-tier approach.
        
        First Approach: Try to parse JSON directly from the response
        Second Approach: If the first approach fails, make a second call to the model
        to process the narrative response and extract structured action information.
        """
        try:
            # Log the raw response for debugging
            logging.debug(f"Raw AI response (first 500 chars): {response_text[:500]}")
            
            # First Approach: Check for JSON patterns in the response
            
            # Look for JSON in code blocks (support both ```json and bare ```)
            json_pattern = r'```(?:json|JSON)?\s*([\s\S]*?)\s*```'
            json_match = re.search(json_pattern, response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                logging.debug(f"Found JSON in code block: {json_str[:200]}...")
                action_data = self._clean_and_parse_json(json_str)
                if action_data:
                    logging.debug("✅ Successfully parsed JSON from code block")
                    # Validate and clean focus_influence
                    return self._validate_and_clean_action_data(action_data)
                else:
                    logging.warning("⚠️ Failed to parse JSON from code block, trying other methods")
            
            # Try to find any JSON-like structure in the response
            # 1) Quick regex-based attempt
            potential_json = re.search(r'({[\s\S]*?})', response_text)
            if potential_json:
                json_str = potential_json.group(1)
                logging.debug(f"Found potential JSON structure: {json_str[:200]}...")
                action_data = self._clean_and_parse_json(json_str)
                if action_data:
                    logging.debug("✅ Successfully parsed JSON from regex match")
                    # Validate and clean focus_influence
                    return self._validate_and_clean_action_data(action_data)
                else:
                    logging.warning("⚠️ Failed to parse JSON from regex match")

            # 2) Balanced-brace scan to extract the most likely JSON object
            candidate = self._extract_balanced_json(response_text)
            if candidate:
                logging.debug(f"Attempting balanced-brace JSON parse, candidate starts: {candidate[:200]}...")
                action_data = self._clean_and_parse_json(candidate)
                if action_data:
                    logging.debug("✅ Successfully parsed JSON via balanced-brace extraction")
                    return self._validate_and_clean_action_data(action_data)
            
            # Second Approach: It's likely a narrative response, make a second call to the model
            
            # Check if we have a narrative/essay-like response
            lines = response_text.strip().split('\n')
            
            # More robust narrative detection: Check for multiple conditions
            is_narrative = False
            
            # 1. Multiple lines without JSON structure
            if len(lines) > 5 and not any(line.strip().startswith('{') for line in lines[:5]) and '```json' not in response_text[:200]:
                is_narrative = True
            
            # 2. Short responses without JSON format but with action keywords
            action_keywords = ['click', 'input', 'type', 'enter', 'scroll', 'swipe', 'back', 'long_press', 'long press']
            if not is_narrative and len(response_text) < 500 and not '{' in response_text and any(keyword in response_text.lower() for keyword in action_keywords):
                is_narrative = True
            
            # 3. Responses with clear action sentences but no JSON
            action_patterns = [
                r'(?:should|would|recommend|can)\s+(?:click|input|type|enter|scroll|swipe|back|long\s?press)',
                r'(?:most appropriate|next|best)\s+action',
                r'(?:the user should|user needs to|we should)'
            ]
            if not is_narrative and any(re.search(pattern, response_text.lower()) for pattern in action_patterns):
                is_narrative = True
                
            # If heuristics say narrative OR if we still failed to parse JSON, attempt second-call extraction
            if is_narrative or True:
                logging.info("📝 Attempting structured extraction via second model call.")
                action_data = self._make_second_call_for_action_extraction(response_text)
                if action_data:
                    logging.info("✅ Successfully extracted action through second call to model")
                    return self._validate_and_clean_action_data(action_data)
                else:
                    logging.error("🔴 Failed to extract action through second call")
                    return None
            
            # If we're here, we couldn't find JSON and it wasn't a narrative response
            logging.error("🔴 Failed to parse action data from AI response")
            logging.debug(f"Full AI response: {response_text}")
            return None
            
        except Exception as e:
            logging.error(f"🔴 Error parsing action from response: {e}", exc_info=True)
            logging.debug(f"Response text that caused error: {response_text[:1000]}...")
            return None

    def _extract_balanced_json(self, text: str) -> Optional[str]:
        """Attempt to extract a top-level JSON object using balanced braces.
        Scans the text for the first '{' and returns the shortest substring that
        forms a balanced JSON object, ignoring braces inside string literals.
        """
        try:
            start = text.find('{')
            if start == -1:
                return None
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == '"':
                        in_string = False
                else:
                    if ch == '"':
                        in_string = True
                    elif ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            return text[start:i+1]
            return None
        except Exception as e:
            logging.debug(f"Balanced JSON extraction failed: {e}")
            return None
    
    def _make_second_call_for_action_extraction(self, narrative_response: str) -> Optional[Dict[str, Any]]:
        """Make a second call to the model to extract structured action data from a narrative response.
        
        Args:
            narrative_response: The narrative response from the first model call
            
        Returns:
            A dictionary with structured action data, or None if extraction failed
        """
        try:
            # Create a prompt that asks the model to extract action information
            prompt = f"""
            You are a helpful assistant that extracts structured action information from analysis text.
            
            I'll provide you with an analysis text that describes an action to take in a mobile app.
            Extract the following information in JSON format:
            
            1. action: The type of action (click, input, scroll_down, scroll_up, swipe_left, swipe_right, back, long_press)
            2. target_identifier: The target element (if applicable, otherwise null)
            3. target_bounding_box: The bounding box coordinates (if applicable, otherwise null)
            4. input_text: The text to input (if applicable, otherwise null)
            5. reasoning: A brief explanation of why this action was chosen
            6. focus_influence: An array of focus area IDs that influenced the decision (can be empty)
            
            RULES:
            - target_identifier MUST be a single raw value for ONE attribute only (choose one of: resource-id like com.pkg:id/name, content-desc, or visible text). Do NOT include prefixes like 'id=' or 'content-desc=' and do NOT combine multiple attributes with '|'.
            - target_bounding_box MUST be an object {top_left:[y,x], bottom_right:[y,x]} using absolute pixels or normalized 0..1. Do NOT use string formats like '[x,y][x2,y2]'.
            - Use null for scroll/back if bbox/identifier are not applicable.
            
            Respond ONLY with a valid JSON object containing these fields, nothing else.
            Here's the analysis text:
            
            ---
            {narrative_response}
            ---
            """
            
            # Generate a response from the model
            try:
                # We don't need an image for this call, just text
                response_text, _ = self.model_adapter.generate_response(prompt=prompt)
                
                # Try to parse the response as JSON
                try:
                    # First try direct JSON parsing
                    action_data = json.loads(response_text)
                    return action_data
                except json.JSONDecodeError:
                    # Try to clean and parse the JSON
                    cleaned_json = self._clean_and_parse_json(response_text)
                    if cleaned_json:
                        return cleaned_json
                    
                    # If that fails, look for JSON in code blocks
                    json_pattern = r'```(?:json)?\s*(.*?)\s*```'
                    json_match = re.search(json_pattern, response_text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        return self._clean_and_parse_json(json_str)
                    
                    # As a last resort, look for any JSON-like structure
                    potential_json = re.search(r'({[\s\S]*?})', response_text)
                    if potential_json:
                        json_str = potential_json.group(1)
                        return self._clean_and_parse_json(json_str)
                    
                    # If we still couldn't find JSON, log error and return None
                    logging.error("🔴 Failed to extract action data from second model call")
                    logging.debug(f"Second call response: {response_text}")
                    return None
                
            except Exception as e:
                logging.error(f"🔴 Error making second model call: {e}", exc_info=True)
                return None
                
        except Exception as e:
            logging.error(f"🔴 Error in second call extraction: {e}", exc_info=True)
            return None

    def _validate_and_clean_action_data(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean action data, including focus_influence."""
        if not action_data:
            return action_data

        # --- Normalize target_identifier to a single raw value (no prefixes/pipes) ---
        try:
            def _strip_quotes(val: str) -> str:
                v = val.strip()
                if (v.startswith("\"") and v.endswith("\"")) or (v.startswith("'") and v.endswith("'")):
                    return v[1:-1]
                return v

            def _normalize_target_identifier(raw: Any) -> Tuple[Optional[str], Optional[str]]:
                # Returns (normalized_value, type_hint)
                if raw is None:
                    return None, None
                # If dict-like identifier, pick the strongest key
                if isinstance(raw, dict):
                    for key in ["id", "resource_id", "resource-id", "content_desc", "content-desc", "text", "xpath"]:
                        if key in raw and isinstance(raw[key], str) and raw[key].strip():
                            return _strip_quotes(raw[key]), key
                    return None, None
                if not isinstance(raw, str):
                    try:
                        raw = str(raw)
                    except Exception:
                        return None, None
                s = raw.strip()
                # Split composite strings on pipes
                parts = re.split(r"\s*\|\s*", s) if "|" in s else [s]
                kv: Dict[str, str] = {}
                for p in parts:
                    m = re.match(r"\s*([a-zA-Z_\-]+)\s*=\s*(.+)\s*", p)
                    if m:
                        k = m.group(1).lower()
                        v = _strip_quotes(m.group(2))
                        kv[k] = v
                # Prefer resource-id, then content-desc, then text, then xpath
                for k in ["id", "resource_id", "resource-id"]:
                    if k in kv and kv[k]:
                        return kv[k], "resource-id"
                for k in ["content_desc", "content-desc"]:
                    if k in kv and kv[k]:
                        return kv[k], "content-desc"
                if "text" in kv and kv.get("text"):
                    return kv["text"], "text"
                if "xpath" in kv and kv.get("xpath"):
                    return kv["xpath"], "xpath"
                # If no kv pairs, try to infer from the raw string
                # If it's an XPath
                if s.startswith("//") or s.startswith(".//"):
                    return s, "xpath"
                # If it looks like an Android resource-id
                if ":id/" in s or re.match(r"^[A-Za-z0-9_.]+:id/[A-Za-z0-9_.]+$", s):
                    return s, "resource-id"
                # Otherwise treat as plain text or simple id
                return _strip_quotes(s), "plain"

            norm_id, id_type = _normalize_target_identifier(action_data.get("target_identifier"))
            if norm_id:
                if norm_id != action_data.get("target_identifier"):
                    logging.debug(f"Normalized target_identifier from '{action_data.get('target_identifier')}' to '{norm_id}' (type={id_type})")
                action_data["target_identifier"] = norm_id
            else:
                # Ensure explicit null when not applicable
                action_data["target_identifier"] = None
        except Exception as e:
            logging.debug(f"Failed to normalize target_identifier: {e}")

        # --- Normalize target_bounding_box to dict {top_left:[y,x], bottom_right:[y,x]} ---
        try:
            def _parse_bounds_string(bounds: str) -> Optional[Tuple[int, int, int, int]]:
                try:
                    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds.strip())
                    if not m:
                        return None
                    x1 = int(m.group(1)); y1 = int(m.group(2)); x2 = int(m.group(3)); y2 = int(m.group(4))
                    return x1, y1, x2, y2
                except Exception:
                    return None

            def _normalize_bbox(raw: Any) -> Optional[Dict[str, List[float]]]:
                if raw is None:
                    return None
                # Accept legacy Android bounds string "[x1,y1][x2,y2]"
                if isinstance(raw, str):
                    parsed = _parse_bounds_string(raw)
                    if not parsed:
                        logging.warning(f"Invalid bounds string format: {raw}")
                        return None
                    x1, y1, x2, y2 = parsed
                    return {"top_left": [float(y1), float(x1)], "bottom_right": [float(y2), float(x2)]}
                # Dict formats
                if isinstance(raw, dict):
                    tl = raw.get("top_left")
                    br = raw.get("bottom_right")
                    # Support object forms {top_left: {y:.., x:..}}
                    if isinstance(tl, dict):
                        tl = [tl.get("y"), tl.get("x")]
                    if isinstance(br, dict):
                        br = [br.get("y"), br.get("x")]
                    if isinstance(tl, (list, tuple)) and isinstance(br, (list, tuple)) and len(tl) == 2 and len(br) == 2:
                        try:
                            y1, x1 = float(tl[0]), float(tl[1])
                            y2, x2 = float(br[0]), float(br[1])
                            return {"top_left": [y1, x1], "bottom_right": [y2, x2]}
                        except Exception:
                            logging.warning(f"Non-numeric bbox coordinates: {raw}")
                            return None
                    logging.warning(f"Invalid bbox dict format: {raw}")
                    return None
                # Unsupported type
                logging.warning(f"Unsupported bbox type: {type(raw)}")
                return None

            norm_bbox = _normalize_bbox(action_data.get("target_bounding_box"))
            if norm_bbox:
                if norm_bbox != action_data.get("target_bounding_box"):
                    logging.debug(f"Normalized target_bounding_box from '{action_data.get('target_bounding_box')}' to '{norm_bbox}'")
                action_data["target_bounding_box"] = norm_bbox
            else:
                action_data["target_bounding_box"] = None
        except Exception as e:
            logging.debug(f"Failed to normalize target_bounding_box: {e}")

        # Validate focus_influence field
        if 'focus_influence' not in action_data:
            logging.debug("AI response missing focus_influence field, setting to empty list")
            action_data['focus_influence'] = []
        elif not isinstance(action_data['focus_influence'], list):
            logging.warning("focus_influence should be a list, converting")
            action_data['focus_influence'] = [action_data['focus_influence']]
        
        # Validate focus area IDs exist
        valid_ids = self._get_valid_focus_area_ids()
        original_influence = action_data['focus_influence']
        action_data['focus_influence'] = [
            fid for fid in action_data['focus_influence'] 
            if isinstance(fid, str) and fid in valid_ids
        ]
        
        if len(original_influence) != len(action_data['focus_influence']):
            logging.warning(f"Filtered invalid focus area IDs from {original_influence} to {action_data['focus_influence']}")
        
        return action_data

    def _get_valid_focus_area_ids(self) -> List[str]:
        """Get list of valid focus area IDs from configuration, limited to top-K by priority."""
        focus_areas = getattr(self.cfg, 'FOCUS_AREAS', [])
        enabled_areas = [area for area in focus_areas if area.get('enabled', True)]
        enabled_areas.sort(key=lambda x: x.get('priority', 0))
        max_active = getattr(self.cfg, 'FOCUS_MAX_ACTIVE', 5)
        if isinstance(max_active, int) and max_active > 0:
            enabled_areas = enabled_areas[:max_active]
        return [area.get('id', '') for area in enabled_areas]

    def _extract_base_model_name(self, model_name: str) -> str:
        """Extract the base model name without tag version and match it to available models.
        
        Handles different model name formats:
        - Models with version tags (e.g., "llama3.2-vision:latest")
        - Models with full names (e.g., "llama3.2-vision")
        
        Returns the closest matching key from OLLAMA_MODELS.
        """
        # Remove version tag if present (e.g., ":latest", ":7b")
        if ":" in model_name:
            base_name = model_name.split(":")[0]
        else:
            base_name = model_name
            
        return base_name
