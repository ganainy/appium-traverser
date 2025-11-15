import os
import io
import uuid
import time
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from PIL import Image
from pydantic import BaseModel, ValidationError, validator

# MCP client exceptions removed

# LangChain imports for orchestration
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import PromptTemplate
from langgraph.checkpoint.memory import MemorySaver

# Always use absolute import for model_adapters
from domain.model_adapters import create_model_adapter, Session
from domain.provider_utils import get_provider_api_key, get_provider_config_key, validate_provider_config
from config.numeric_constants import (
    DEFAULT_AI_PROVIDER,
    DEFAULT_MODEL_TEMP,
    DEFAULT_MAX_TOKENS,
    IMAGE_MAX_WIDTH_DEFAULT,
    IMAGE_DEFAULT_QUALITY,
    IMAGE_DEFAULT_FORMAT,
    IMAGE_CROP_TOP_PCT_DEFAULT,
    IMAGE_CROP_BOTTOM_PCT_DEFAULT,
    IMAGE_BG_COLOR,
    IMAGE_SHARPEN_RADIUS,
    IMAGE_SHARPEN_PERCENT,
    IMAGE_SHARPEN_THRESHOLD,
    LONG_PRESS_MIN_DURATION_MS,
    AI_LOG_FILENAME,
)
from config.urls import ServiceURLs
from domain.prompts import JSON_OUTPUT_SCHEMA, get_available_actions, ACTION_DECISION_SYSTEM_PROMPT, CONTEXT_ANALYSIS_PROMPT, SYSTEM_PROMPT_TEMPLATE

# Update AgentAssistant to initialize AppiumDriver with a valid Config instance
from config.app_config import Config

# Import XML simplification utility
from utils.utils import simplify_xml_for_ai

# Explicitly define the Tools class
class Tools:
    def __init__(self, driver):
        self.driver = driver

# Update ActionDecisionChain with real implementation
class ActionDecisionChain:
    def __init__(self, chain):
        self.chain = chain

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run the decision chain with the given context."""
        try:
            # The chain expects a dict with prompt variables
            # Format the context for the prompt template
            result = self.chain.invoke(context)
            # If result is a string, try to parse as JSON
            if isinstance(result, str):
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    # Try to extract JSON from text if wrapped
                    json_match = re.search(r'\{[^{}]*\}', result, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                    from config.numeric_constants import RESULT_TRUNCATION_LENGTH
                    logging.warning(f"Could not parse JSON from chain result: {result[:RESULT_TRUNCATION_LENGTH]}")
                    return {}
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logging.error(f"Error running ActionDecisionChain: {e}", exc_info=True)
            return {}

# Define the Pydantic model for ActionData
class ActionData(BaseModel):
    action: str
    target_identifier: str
    target_bounding_box: Optional[Dict[str, Any]] = None
    input_text: Optional[str] = None
    reasoning: str
    focus_influence: List[str]

    @validator("target_identifier")
    def clean_target_identifier(cls, value):
        # Add normalization logic for target_identifier if needed
        return value.strip()

    @validator("target_bounding_box", pre=True)
    def validate_bounding_box(cls, value):
        # Ensure bounding box is in the correct format
        if value is None:
            return None
        if not isinstance(value, dict) or "top_left" not in value or "bottom_right" not in value:
            raise ValueError("Invalid bounding box format")
        return value

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
                ui_callback=None,
                tools=None):  # Added tools parameter
        if tools is None:
            app_config = Config()
            from infrastructure.appium_driver import AppiumDriver
            tools = Tools(driver=AppiumDriver(app_config))
        
        self.tools = tools
        self.cfg = app_config
        self.response_cache: Dict[str, Tuple[Dict[str, Any], float, int]] = {}
        self.agent_tools = agent_tools  # May be None initially and set later
        self.ui_callback = ui_callback  # Callback for UI updates
        logging.debug("AI response cache initialized.")

        # Determine which AI provider to use
        self.ai_provider = self.cfg.get('AI_PROVIDER', DEFAULT_AI_PROVIDER).lower()
        logging.debug(f"Using AI provider: {self.ai_provider}")

        # Adapter provider override (for routing purposes without changing UI label)
        self._adapter_provider_override: Optional[str] = None

        # Get the appropriate API key based on the provider using provider-agnostic utility
        is_valid, error_msg = validate_provider_config(self.cfg, self.ai_provider, ServiceURLs.OLLAMA)
        if not is_valid:
            raise ValueError(error_msg or f"Unsupported AI provider: {self.ai_provider}")
        
        self.api_key = get_provider_api_key(self.cfg, self.ai_provider, ServiceURLs.OLLAMA)
        if not self.api_key:
            # This should not happen if validation passed, but add safety check
            config_key = get_provider_config_key(self.ai_provider) or "API_KEY"
            raise ValueError(f"{config_key} is not set in the provided application configuration.")

        # Use DEFAULT_MODEL_TYPE directly as a provider-specific model identifier
        model_id = model_alias_override or self.cfg.DEFAULT_MODEL_TYPE
        if not model_id or str(model_id).strip() in ["", "No model selected"]:
            raise ValueError("No model selected. Please choose a model in AI Settings (Default Model Type).")

        # Treat the selected value as the actual model name across providers
        self.model_alias = str(model_id)
        self.actual_model_name = str(model_id)

        # Construct a minimal provider-agnostic model config. Adapters apply defaults.
        model_config_from_file = {
            'name': self.actual_model_name,
            'description': f"Direct model id '{self.actual_model_name}' for provider '{self.ai_provider}'",
            'generation_config': {
                # Keep conservative defaults; adapters may override or apply safer fallbacks
                'temperature': DEFAULT_MODEL_TEMP,
                'top_p': 0.95,
                'max_output_tokens': DEFAULT_MAX_TOKENS
            },
            'online': self.ai_provider in [DEFAULT_AI_PROVIDER, 'openrouter']
        }

        # Initialize model using the adapter
        self._initialize_model(model_config_from_file, safety_settings_override)

        # Initialize provider-agnostic session
        self._init_session(user_id=None)
        
        # Initialize AI interaction logger (must be before LangChain components)
        self.ai_interaction_readable_logger = None
        self._setup_ai_interaction_logger()
        
        # Track if we've logged the static prompt parts (schema and actions)
        self._static_prompt_logged = False
        
        # Initialize LangChain components for orchestration
        self._init_langchain_components()
        
        # Initialize action dispatch map
        self._init_action_dispatch_map()

    def _init_session(self, user_id: Optional[str] = None):
        """Initialize a new provider-agnostic session."""
        now = time.time()
        # actual_model_name is always set in __init__ before this is called
        # This fallback chain is defensive programming but should never execute
        model = self.actual_model_name if hasattr(self, 'actual_model_name') else (self.model_alias if hasattr(self, 'model_alias') else self.cfg.get('DEFAULT_MODEL_TYPE', None))
        if not model:
            # This should never happen due to validation in __init__, but fail fast if it does
            raise ValueError("No model available for session initialization")
        self.session = Session(
            session_id=str(uuid.uuid4()),
            provider=self.ai_provider,
            model=str(model),
            created_at=now,
            last_active=now,
            metadata={
                'user_id': user_id,
                'initialized_at': now
            }
        )
        logging.debug(f"Session initialized: {self.session}")

    def _create_langchain_llm_wrapper(self):
        """Create a LangChain-compatible LLM wrapper around the existing model adapter."""
        def _llm_call(prompt_input) -> str:
            """Call the model adapter and return response text."""
            # Handle different input types from LangChain
            if hasattr(prompt_input, 'messages'):
                # ChatPromptValue - extract text from messages
                prompt_text = ""
                for message in prompt_input.messages:
                    if hasattr(message, 'content'):
                        prompt_text += str(message.content) + "\n"
            elif hasattr(prompt_input, 'content'):
                # Single message
                prompt_text = str(prompt_input.content)
            else:
                # Plain string
                prompt_text = str(prompt_input)

            # Log the AI input (prompt) - only log dynamic parts to avoid repetition
            if self.ai_interaction_readable_logger:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(f"AI INPUT - {timestamp}")
                self.ai_interaction_readable_logger.info("=" * 80)
                # Extract and log only the dynamic parts (everything after the static prompt)
                # The static prompt starts with "You are an AI agent..." and ends before "Current screen XML:"
                # We'll log everything from "Current screen XML:" onwards
                if "Current screen XML:" in prompt_text:
                    # Find where the dynamic part starts
                    dynamic_start = prompt_text.find("Current screen XML:")
                    dynamic_part = prompt_text[dynamic_start:]
                    self.ai_interaction_readable_logger.info(dynamic_part)
                else:
                    # Fallback: log the full prompt if we can't find the marker
                    self.ai_interaction_readable_logger.info(prompt_text)
                self.ai_interaction_readable_logger.info("")

            # Determine if we should include image context
            prepared_image = None
            enable_image_context = self.cfg.get('ENABLE_IMAGE_CONTEXT', False)
            
            if enable_image_context and hasattr(self, '_current_prepared_image'):
                # Check if provider/model supports image context
                try:
                    from domain.providers.registry import ProviderRegistry
                    provider_strategy = ProviderRegistry.get_by_name(self.ai_provider)
                    if provider_strategy:
                        model_name = self.actual_model_name if hasattr(self, 'actual_model_name') else self.model_alias
                        if provider_strategy.supports_image_context(self.cfg, model_name):
                            prepared_image = getattr(self, '_current_prepared_image', None)
                            if prepared_image:
                                logging.info(f"🖼️  SENDING IMAGE TO AI: Yes (size: {prepared_image.size[0]}x{prepared_image.size[1]})")
                            else:
                                logging.warning(f"🖼️  SENDING IMAGE TO AI: No (prepared image is None)")
                        else:
                            logging.info(f"🖼️  SENDING IMAGE TO AI: No (model '{model_name}' does not support image context)")
                    else:
                        logging.warning(f"🖼️  SENDING IMAGE TO AI: No (could not get provider strategy)")
                except Exception as e:
                    logging.warning(f"🖼️  SENDING IMAGE TO AI: No (error checking support: {e})", exc_info=True)
            elif enable_image_context:
                logging.info(f"🖼️  SENDING IMAGE TO AI: No (ENABLE_IMAGE_CONTEXT=True but no prepared image available)")
            else:
                logging.debug(f"🖼️  SENDING IMAGE TO AI: No (ENABLE_IMAGE_CONTEXT=False)")

            try:
                response_text, metadata = self.model_adapter.generate_response(
                    prompt=prompt_text,
                    image=prepared_image,
                    image_format=self.cfg.get('IMAGE_FORMAT', None),
                    image_quality=self.cfg.get('IMAGE_QUALITY', None)
                )
                
                # Log the AI response
                if self.ai_interaction_readable_logger:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.ai_interaction_readable_logger.info("=" * 80)
                    self.ai_interaction_readable_logger.info(f"AI RESPONSE - {timestamp}")
                    self.ai_interaction_readable_logger.info("=" * 80)
                    self.ai_interaction_readable_logger.info(response_text)
                    self.ai_interaction_readable_logger.info("")
                    self.ai_interaction_readable_logger.info("")
                
                return response_text
            except Exception as e:
                logging.error(f"Error in LangChain LLM wrapper: {e}")
                # Log error if logger is available
                if self.ai_interaction_readable_logger:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.ai_interaction_readable_logger.info("=" * 80)
                    self.ai_interaction_readable_logger.info(f"AI ERROR - {timestamp}")
                    self.ai_interaction_readable_logger.info("=" * 80)
                    self.ai_interaction_readable_logger.info(f"Error: {str(e)}")
                    self.ai_interaction_readable_logger.info("")
                    self.ai_interaction_readable_logger.info("")
                return ""

        return RunnableLambda(_llm_call)

    def _create_prompt_chain(self, prompt_template: str, llm_wrapper):
        """Create a LangChain Runnable chain from a prompt template.
        
        Args:
            prompt_template: The prompt template string with placeholders
            llm_wrapper: The LLM Runnable wrapper
            
        Returns:
            A Runnable chain: PromptTemplate | LLM | OutputParser
        """
        # Format the template with static values
        # Get available actions from config property (reads from database or defaults)
        available_actions = get_available_actions(self.cfg)
        action_list_str = "\n".join([f"- {action}: {desc}" for action, desc in available_actions.items()])
        json_output_guidance = json.dumps(JSON_OUTPUT_SCHEMA, indent=2)
        
        # Create formatted prompt string
        formatted_prompt = prompt_template.format(
            json_schema=json_output_guidance,
            action_list=action_list_str
        )
        
        # Log static prompt parts once
        if self.ai_interaction_readable_logger and not self._static_prompt_logged:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.ai_interaction_readable_logger.info("=" * 80)
            self.ai_interaction_readable_logger.info(f"AI PROMPT CONFIGURATION - {timestamp}")
            self.ai_interaction_readable_logger.info("=" * 80)
            self.ai_interaction_readable_logger.info(formatted_prompt)
            self.ai_interaction_readable_logger.info("")
            self.ai_interaction_readable_logger.info("(Note: The above JSON schema and available actions are static and will not be repeated in subsequent logs)")
            self.ai_interaction_readable_logger.info("")
            self._static_prompt_logged = True
        
        # Create a PromptTemplate that accepts dynamic context variables
        # We'll inject the formatted prompt as a system message
        # For simplicity, create a chain that formats the prompt with context
        def format_prompt_with_context(context: Dict[str, Any]) -> str:
            """Format the prompt with context variables."""
            # Build the full prompt with context
            prompt_parts = [formatted_prompt]
            
            # Build dynamic parts separately for logging
            dynamic_parts = []
            
            # Add context information
            if context.get("xml_context"):
                # XML is already simplified in _get_next_action_langchain, so use it directly
                xml_string = context['xml_context']
                
                # Ensure it's a string (should already be simplified at this point)
                if not isinstance(xml_string, str):
                    xml_string = str(xml_string)
                
                # Use the simplified XML directly (no need to simplify again)
                xml_part = f"\n\nCurrent screen XML:\n{xml_string}"
                prompt_parts.append(xml_part)
                dynamic_parts.append(xml_part)
            
            # Add stuck detection warning if applicable
            if context.get("is_stuck"):
                stuck_reason = context.get("stuck_reason", "Multiple actions on same screen")
                current_screen_id = context.get('current_screen_id')
                current_screen_actions = context.get('current_screen_actions', [])
                
                # Extract forbidden actions (actions that stayed on same screen)
                forbidden_actions = []
                for action in current_screen_actions:
                    action_desc = action.get('action_description', '')
                    success = action.get('execution_success', False)
                    to_screen_id = action.get('to_screen_id')
                    
                    # Include actions that either:
                    # 1. Stayed on the same screen (to_screen_id == current_screen_id)
                    # 2. Had no navigation (to_screen_id is None) and succeeded
                    if success and (to_screen_id == current_screen_id or to_screen_id is None):
                        # Extract the target identifier from action description
                        # Format: "click on btn_scan_erx" -> "btn_scan_erx"
                        # Format: "scroll_down on cl_home_no_receipts" -> "scroll_down on cl_home_no_receipts"
                        forbidden_actions.append(action_desc)
                
                # Build forbidden actions list
                forbidden_text = ""
                if forbidden_actions:
                    forbidden_lines = ["\n🚫 FORBIDDEN ACTIONS - DO NOT REPEAT THESE:"]
                    for action in forbidden_actions:
                        forbidden_lines.append(f"  - {action}")
                    forbidden_text = "\n".join(forbidden_lines)
                
                # Common navigation resource IDs (can be extended)
                # These are examples based on common patterns - the AI should look for similar patterns
                navigation_hints = """
Look for these navigation elements in the XML (HIGHEST PRIORITY):
- Bottom navigation tabs: tv_home, tv_assortment, tv_cart, tv_account, tv_erx, or any element with "tv_" prefix in bottom navigation area
- Navigation buttons: Any element with "nav", "menu", "tab", "bar" in resource-id
- Back buttons: Elements with "back", "arrow", "up" in resource-id or content-desc, or use the "back" action
- Menu items: Elements that clearly lead to different app sections
- Tab indicators: Elements that switch between different views/screens
"""
                
                stuck_warning = f"""
⚠️ CRITICAL: STUCK DETECTION - {stuck_reason}

You are stuck in a loop on the same screen. You MUST break out of this loop immediately.

{forbidden_text}

PRIORITY ORDER FOR YOUR NEXT ACTION (choose one):
1. 🎯 NAVIGATION ACTIONS (HIGHEST PRIORITY) - Use bottom navigation or menu items:
   - Click on navigation tabs (tv_home, tv_assortment, tv_cart, tv_account, etc.)
   - These will take you to DIFFERENT screens and break the loop
   {navigation_hints}

2. ⬅️ BACK BUTTON (HIGH PRIORITY):
   - Use the "back" action to exit this screen
   - This will return you to a previous screen

3. 📜 SCROLL ACTIONS (MEDIUM PRIORITY):
   - Only if scrolling reveals NEW navigation elements you haven't tried
   - Do NOT scroll if you've already scrolled on this screen

4. 🚫 DO NOT:
   - Repeat any of the forbidden actions listed above
   - Click buttons you've already clicked on this screen
   - Try variations of actions you've already attempted
   - Stay on this screen - you MUST navigate away

YOUR TASK: Choose an action that will take you to a DIFFERENT screen.
In your reasoning, explicitly state: "I am navigating away from this screen to break the loop by..."
"""
                prompt_parts.append(stuck_warning)
                dynamic_parts.append(stuck_warning)
            
            # Format action history with success/failure indicators
            if context.get("action_history"):
                action_history = context['action_history']
                if action_history:
                    history_lines = ["\n\nRecent Actions:"]
                    for step in action_history[-10:]:  # Show last 10 actions
                        step_num = step.get('step_number', '?')
                        action_desc = step.get('action_description', 'unknown action')
                        success = step.get('execution_success', False)
                        error_msg = step.get('error_message')
                        from_screen_id = step.get('from_screen_id')
                        to_screen_id = step.get('to_screen_id')
                        
                        status = "SUCCESS" if success else "FAILED"
                        details = []
                        if to_screen_id:
                            if from_screen_id == to_screen_id:
                                details.append("stayed on same screen")
                            else:
                                details.append(f"navigated to screen #{to_screen_id}")
                        elif success:
                            details.append("no navigation occurred")
                        if error_msg:
                            details.append(f"error: {error_msg}")
                        
                        detail_str = f" ({', '.join(details)})" if details else ""
                        history_lines.append(f"- Step {step_num}: {action_desc} → {status}{detail_str}")
                    
                    actions_part = "\n".join(history_lines)
                    prompt_parts.append(actions_part)
                    dynamic_parts.append(actions_part)
            
            # Format visited screens information
            if context.get("visited_screens"):
                visited_screens = context['visited_screens']
                if visited_screens:
                    screens_lines = ["\n\nVisited Screens (this run):"]
                    for screen in visited_screens[:15]:  # Show top 15 most visited screens
                        screen_id = screen.get('screen_id', '?')
                        activity = screen.get('activity_name', 'UnknownActivity')
                        visit_count = screen.get('visit_count', 0)
                        screens_lines.append(f"- Screen #{screen_id} ({activity}): visited {visit_count} time{'s' if visit_count != 1 else ''}")
                    
                    screens_part = "\n".join(screens_lines)
                    prompt_parts.append(screens_part)
                    dynamic_parts.append(screens_part)
            
            # Format current screen actions (if revisiting)
            if context.get("current_screen_actions") and len(context['current_screen_actions']) > 0:
                current_screen_actions = context['current_screen_actions']
                current_screen_id = context.get('current_screen_id')
                actions_lines = [f"\n\nActions already tried on this screen (Screen #{current_screen_id}):"]
                for action in current_screen_actions:
                    action_desc = action.get('action_description', 'unknown action')
                    success = action.get('execution_success', False)
                    error_msg = action.get('error_message')
                    to_screen_id = action.get('to_screen_id')
                    
                    status = "SUCCESS" if success else "FAILED"
                    details = []
                    if to_screen_id:
                        if to_screen_id == current_screen_id:
                            details.append("stayed on same screen")
                        else:
                            details.append(f"navigated to screen #{to_screen_id}")
                    elif success:
                        details.append("no navigation occurred")
                    if error_msg:
                        details.append(f"error: {error_msg}")
                    
                    detail_str = f" ({', '.join(details)})" if details else ""
                    actions_lines.append(f"- {action_desc} → {status}{detail_str}")
                
                current_actions_part = "\n".join(actions_lines)
                prompt_parts.append(current_actions_part)
                dynamic_parts.append(current_actions_part)
            
            if context.get("last_action_feedback"):
                feedback_part = f"\n\nLast action feedback: {context['last_action_feedback']}"
                prompt_parts.append(feedback_part)
                dynamic_parts.append(feedback_part)
            
            if context.get("current_screen_visit_count"):
                visit_count_part = f"\n\nScreen visit count: {context['current_screen_visit_count']}"
                prompt_parts.append(visit_count_part)
                dynamic_parts.append(visit_count_part)
            
            closing_part = "\n\nPlease respond with a JSON object matching the schema above."
            prompt_parts.append(closing_part)
            dynamic_parts.append(closing_part)
            
            # Store dynamic parts in context for logging
            context['_dynamic_prompt_parts'] = "\n".join(dynamic_parts)
            
            # Store the full prompt in context for database storage
            full_prompt = "\n".join(prompt_parts)
            context['_full_ai_input_prompt'] = full_prompt
            
            return full_prompt
        
        # Create chain: format prompt -> LLM -> parse JSON
        def parse_json_output(llm_output: str) -> Dict[str, Any]:
            """Parse JSON from LLM output."""
            try:
                # Try direct JSON parse
                return json.loads(llm_output)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks or text
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_output, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                # Try to find JSON object in text
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', llm_output, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                logging.warning(f"Could not parse JSON from LLM output: {llm_output[:200]}")
                return {}
        
        # Chain: format prompt -> LLM -> parse JSON
        chain = RunnableLambda(format_prompt_with_context) | llm_wrapper | RunnableLambda(parse_json_output)
        return chain

    def _init_langchain_components(self):
        """Initialize LangChain components for orchestration."""
        try:
            logging.debug("Initializing LangChain components for AI orchestration")

            # Create the LLM wrapper
            self.langchain_llm = self._create_langchain_llm_wrapper()

            # Create the action decision chain with proper Runnable chain
            # Use config property (reads from database or None)
            action_decision_prompt = self.cfg.CRAWLER_ACTION_DECISION_PROMPT
            if not action_decision_prompt:
                action_decision_prompt = ACTION_DECISION_SYSTEM_PROMPT
            action_chain = self._create_prompt_chain(action_decision_prompt, self.langchain_llm)
            self.action_decision_chain = ActionDecisionChain(chain=action_chain)

            # Create the context analysis chain with proper Runnable chain
            context_chain = self._create_prompt_chain(CONTEXT_ANALYSIS_PROMPT, self.langchain_llm)
            self.context_analysis_chain = ActionDecisionChain(chain=context_chain)

            # Initialize memory checkpointer for cross-request context
            self.langchain_memory = MemorySaver()

            logging.debug("LangChain components initialized successfully")

        except Exception as e:
            logging.error(f"Failed to initialize LangChain components: {e}", exc_info=True)
            raise

    def _execute_click_action(self, action_data: Dict[str, Any]) -> bool:
        """Execute click action with proper argument handling."""
        target_id = action_data.get("target_identifier")
        bbox = action_data.get("target_bounding_box")
        
        # Pass both target_identifier and bbox to driver.tap()
        # The driver will call MCP server, which will:
        # 1. Prefer coordinates (bbox) if available
        # 2. Fall back to element lookup with multiple strategies if coordinates not available
        # 3. Use element lookup as fallback if coordinates fail
        return self.tools.driver.tap(target_id, bbox)
    
    def _execute_input_action(self, action_data: Dict[str, Any]) -> bool:
        """Execute input action with proper argument handling."""
        target_id = action_data.get("target_identifier")
        input_text = action_data.get("input_text")
        if not target_id:
            logging.error("Cannot execute input: No target identifier provided")
            return False
        if input_text is None:
            input_text = ""  # Empty string for clear operations
        return self.tools.driver.input_text(target_id, input_text)
    
    def _execute_long_press_action(self, action_data: Dict[str, Any]) -> bool:
        """Execute long press action with proper argument handling."""
        target_id = action_data.get("target_identifier")
        bbox = action_data.get("target_bounding_box")
        # Default duration from config
        try:
            default_duration_ms = int(self.cfg.get('LONG_PRESS_MIN_DURATION_MS', LONG_PRESS_MIN_DURATION_MS))
        except Exception:
            default_duration_ms = LONG_PRESS_MIN_DURATION_MS
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
                    # Use coordinate tap with duration for long press - create bbox
                    tap_bbox = {"top_left": [center_y, center_x], "bottom_right": [center_y, center_x]}
                    return self.tools.driver.tap(None, tap_bbox)
                else:
                    logging.error("Cannot get screen size for coordinate validation")
                    return False
            else:
                logging.error("Invalid bounding box format for long_press")
                return False
        else:
            # Prefer element-based long press via driver
            return self.tools.driver.long_press(target_id or "", duration_ms)
    
    def _execute_double_tap_action(self, action_data: Dict[str, Any]) -> bool:
        """Execute double tap action with proper argument handling."""
        target_id = action_data.get("target_identifier")
        bbox = action_data.get("target_bounding_box")
        
        # Pass both target_identifier and bbox to driver.double_tap()
        return self.tools.driver.double_tap(target_id, bbox)
    
    def _execute_clear_text_action(self, action_data: Dict[str, Any]) -> bool:
        """Execute clear text action with proper argument handling."""
        target_id = action_data.get("target_identifier")
        if not target_id:
            logging.error("Cannot execute clear_text: No target identifier provided")
            return False
        return self.tools.driver.clear_text(target_id)
    
    def _execute_replace_text_action(self, action_data: Dict[str, Any]) -> bool:
        """Execute replace text action with proper argument handling."""
        target_id = action_data.get("target_identifier")
        input_text = action_data.get("input_text")
        if not target_id:
            logging.error("Cannot execute replace_text: No target identifier provided")
            return False
        if input_text is None:
            logging.error("Cannot execute replace_text: No input_text provided")
            return False
        return self.tools.driver.replace_text(target_id, input_text)
    
    def _execute_flick_action(self, action_data: Dict[str, Any]) -> bool:
        """Execute flick action with proper argument handling."""
        # Try to get direction from action_data or infer from reasoning/target
        direction = action_data.get("direction")
        if not direction:
            # Try to infer from reasoning or target_identifier
            reasoning = action_data.get("reasoning", "").lower()
            target_id = action_data.get("target_identifier", "").lower()
            
            if "up" in reasoning or "up" in target_id:
                direction = "up"
            elif "down" in reasoning or "down" in target_id:
                direction = "down"
            elif "left" in reasoning or "left" in target_id:
                direction = "left"
            elif "right" in reasoning or "right" in target_id:
                direction = "right"
            else:
                # Default to down
                direction = "down"
                logging.debug("No direction specified for flick, defaulting to 'down'")
        
        return self.tools.driver.flick(direction.lower())
    
    def _execute_reset_app_action(self, action_data: Dict[str, Any]) -> bool:
        """Execute reset app action."""
        # reset_app doesn't need any parameters
        return self.tools.driver.reset_app()

    def _init_action_dispatch_map(self):
        """Initialize the action dispatch map for efficient action execution."""
        self.action_dispatch_map = {
            "click": self._execute_click_action,
            "input": self._execute_input_action,
            "scroll_down": lambda action_data: self.tools.driver.scroll("down"),
            "scroll_up": lambda action_data: self.tools.driver.scroll("up"),
            "swipe_left": lambda action_data: self.tools.driver.scroll("left"),
            "swipe_right": lambda action_data: self.tools.driver.scroll("right"),
            "back": self.tools.driver.press_back,
            "long_press": self._execute_long_press_action,
            "double_tap": self._execute_double_tap_action,
            "clear_text": self._execute_clear_text_action,
            "replace_text": self._execute_replace_text_action,
            "flick": self._execute_flick_action,
            "reset_app": self._execute_reset_app_action
        }
    
    def _normalize_action_type(self, action_type: str, action_data: Dict[str, Any]) -> str:
        """Normalize generic action types to specific ones.
        
        Args:
            action_type: The action type string (may be generic like "scroll" or "swipe")
            action_data: The full action data dictionary for context
            
        Returns:
            Normalized action type string matching one of the supported actions
        """
        # If action is already specific, return as-is
        if action_type in self.action_dispatch_map:
            return action_type
        
        # Map generic actions to specific ones
        target_identifier = action_data.get("target_identifier", "").lower()
        reasoning = action_data.get("reasoning", "").lower()
        
        if action_type == "scroll":
            # Try to infer direction from context
            if "up" in target_identifier or "up" in reasoning:
                return "scroll_up"
            elif "down" in target_identifier or "down" in reasoning:
                return "scroll_down"
            else:
                # Default to scroll_down (most common)
                logging.debug(f"Generic 'scroll' action mapped to 'scroll_down' (default)")
                return "scroll_down"
        
        elif action_type == "swipe":
            # Try to infer direction from context
            if "left" in target_identifier or "left" in reasoning:
                return "swipe_left"
            elif "right" in target_identifier or "right" in reasoning:
                return "swipe_right"
            else:
                # Default to swipe_left (common for navigation)
                logging.debug(f"Generic 'swipe' action mapped to 'swipe_left' (default)")
                return "swipe_left"
        
        # Return original if no mapping found
        return action_type
    
    def execute_action(self, action_data: Dict[str, Any]) -> bool:
        """Execute an action based on the action_data dictionary.
        
        Args:
            action_data: Dictionary containing action information with at least an 'action' key.
                        Expected keys: action, target_identifier, target_bounding_box, input_text, etc.
        
        Returns:
            True if action executed successfully, False otherwise
        """
        try:
            # Ensure driver is connected before executing
            if not self._ensure_driver_connected():
                logging.error("Cannot execute action: Driver not connected")
                return False
            
            # Get the action type
            action_type = action_data.get("action", "").lower()
            
            if not action_type:
                logging.error("Cannot execute action: No action type specified")
                return False
            
            # Map generic actions to specific ones if needed
            action_type = self._normalize_action_type(action_type, action_data)
            
            # Look up the handler in the dispatch map
            handler = self.action_dispatch_map.get(action_type)
            
            if not handler:
                logging.error(f"Unknown action type: {action_type}. Available actions: {list(self.action_dispatch_map.keys())}")
                return False
            
            # Execute the handler
            try:
                logging.debug(f"Executing action: {action_type}")
                # Some handlers expect action_data, others don't (like press_back, reset_app)
                if action_type in ["back", "reset_app"]:
                    result = handler()
                else:
                    result = handler(action_data)
                
                if result:
                    logging.debug(f"[OK] Successfully executed action: {action_type}")
                else:
                    logging.warning(f"[FAIL] Action execution returned False: {action_type}")
                
                return bool(result)
            except Exception as e:
                logging.error(f"[ERROR] Error executing action {action_type}: {e}", exc_info=True)
                return False
                
        except Exception as e:
            logging.error(f"Unexpected error in execute_action: {e}", exc_info=True)
            return False

    def _initialize_model(self, model_config, safety_settings_override):
        """Initialize the AI model with appropriate settings using the adapter."""
        try:
            # Check if the required dependencies are installed for the chosen provider
            from domain.model_adapters import check_dependencies
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
            safety_settings = safety_settings_override or self.cfg.get('AI_SAFETY_SETTINGS', None)
            
            # Initialize the model adapter
            self.model_adapter.initialize(model_config, safety_settings)
            
            logging.debug(f"AI Assistant initialized with model alias: {self.model_alias} (actual: {self.actual_model_name})")
            logging.debug(f"Model description: {model_config.get('description', 'N/A')}")
            logging.debug(f"Model provider label: {self.ai_provider} | adapter: {adapter_provider}")

        except Exception as e:
            logging.error(f"Failed to initialize AI model: {e}", exc_info=True)
            raise

    def _setup_ai_interaction_logger(self, force_recreate: bool = False):
        """Initializes only the human-readable logger (JSONL removed).
        
        Args:
            force_recreate: If True, close existing handlers and recreate them.
        """
        # Get the logger instance (shared across all AgentAssistant instances)
        logger = logging.getLogger('AIInteractionReadableLogger')
        
        # Set self.ai_interaction_readable_logger to the logger instance
        self.ai_interaction_readable_logger = logger
        
        # Clean up any closed or invalid handlers before checking
        if logger.handlers:
            for handler in list(logger.handlers):
                try:
                    # Check if handler is closed or invalid
                    if isinstance(handler, logging.FileHandler):
                        # Try to access the stream to see if it's closed
                        if hasattr(handler, 'stream') and handler.stream:
                            try:
                                # Check if stream is closed
                                if handler.stream.closed:
                                    logger.removeHandler(handler)
                                    continue
                            except (AttributeError, ValueError):
                                # Stream might be invalid, remove handler
                                logger.removeHandler(handler)
                                continue
                except Exception:
                    # If we can't check the handler, remove it to be safe
                    try:
                        logger.removeHandler(handler)
                    except Exception:
                        pass
        
        if logger.handlers and not force_recreate:
            return  # Already configured

        # Close existing file handlers if recreating
        if force_recreate and logger.handlers:
            for handler in list(logger.handlers):
                if isinstance(handler, logging.FileHandler):
                    try:
                        handler.close()
                    except Exception:
                        pass
                logger.removeHandler(handler)

        # Use the LOG_DIR property which resolves the template properly
        try:
            target_log_dir = self.cfg.LOG_DIR if hasattr(self.cfg, 'LOG_DIR') else self.cfg.get('LOG_DIR', None)
        except Exception as e:
            logging.warning(f"Could not get LOG_DIR property: {e}, trying get() method")
            target_log_dir = self.cfg.get('LOG_DIR', None)
        
        # Don't create directory here - it will be created when the file handler is created
        # This allows path regeneration to work without directory locks
        
        # Configure logger settings
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if logger.hasHandlers() and not force_recreate:
            return  # Already has handlers and not forcing recreate

        if target_log_dir:
            # Check if we have a real device ID - don't create directory for unknown_device
            # Get device info from path_manager if available
            if hasattr(self.cfg, '_path_manager'):
                path_manager = self.cfg._path_manager
                device_name = path_manager.get_device_name()
                device_udid = path_manager.get_device_udid()
            else:
                device_name = None
                device_udid = None
            has_real_device = device_name or device_udid
            
            # Only create directory and file handler if we have a real device or if forcing recreate
            if has_real_device or force_recreate:
                try:
                    # Create directory only when actually creating the file handler
                    os.makedirs(target_log_dir, exist_ok=True)
                    readable_path = os.path.join(target_log_dir, AI_LOG_FILENAME)
                    fh_readable = logging.FileHandler(readable_path, encoding='utf-8')
                    fh_readable.setLevel(logging.INFO)
                    fh_readable.setFormatter(logging.Formatter('%(message)s'))
                    logger.addHandler(fh_readable)
                    logging.debug(f"AI interaction readable logger initialized at: {readable_path}")
                except OSError as e:
                    logging.error(f"Could not create AI interactions readable log file: {e}")
                    if not logger.handlers:
                        logger.addHandler(logging.NullHandler())
            else:
                # Delay file handler creation until device is initialized
                # Use NullHandler for now to avoid creating directories
                if not logger.handlers:
                    logger.addHandler(logging.NullHandler())
                logging.debug("AI interaction logger delayed - waiting for device initialization")
        else:
            logging.warning("Log directory not available, AI interaction readable log will not be saved.")
            if not logger.handlers:
                logger.addHandler(logging.NullHandler())


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
            ai_provider = self.cfg.get('AI_PROVIDER', DEFAULT_AI_PROVIDER).lower()
            
            # Get provider capabilities from config
            try:
                from config.app_config import AI_PROVIDER_CAPABILITIES
            except ImportError:
                from config.app_config import AI_PROVIDER_CAPABILITIES
            
            capabilities = AI_PROVIDER_CAPABILITIES.get(ai_provider, AI_PROVIDER_CAPABILITIES.get(DEFAULT_AI_PROVIDER, {}))
            
            # Resolve preprocessing settings (global overrides take precedence)
            max_width = self.cfg.get('IMAGE_MAX_WIDTH', None) or capabilities.get('image_max_width', IMAGE_MAX_WIDTH_DEFAULT)
            quality = self.cfg.get('IMAGE_QUALITY', None) or capabilities.get('image_quality', IMAGE_DEFAULT_QUALITY)
            image_format = self.cfg.get('IMAGE_FORMAT', None) or capabilities.get('image_format', IMAGE_DEFAULT_FORMAT)
            crop_bars = self.cfg.get('IMAGE_CROP_BARS', True)
            crop_top_pct = float(self.cfg.get('IMAGE_CROP_TOP_PERCENT', IMAGE_CROP_TOP_PCT_DEFAULT) or 0.0)
            crop_bottom_pct = float(self.cfg.get('IMAGE_CROP_BOTTOM_PERCENT', IMAGE_CROP_BOTTOM_PCT_DEFAULT) or 0.0)
            
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
                    background = Image.new('RGB', img.size, IMAGE_BG_COLOR)

                    background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                    img = background
                else:
                    img = img.convert('RGB')
                logging.debug("Converted image to RGB format for optimal compression")
            
            # Apply sharpening to maintain text clarity after compression
            from PIL import ImageFilter

            # Mild sharpening to preserve text readability
            img = img.filter(ImageFilter.UnsharpMask(radius=IMAGE_SHARPEN_RADIUS, percent=IMAGE_SHARPEN_PERCENT, threshold=IMAGE_SHARPEN_THRESHOLD))
            
            # Note: We return the processed PIL Image. Encoding (format/quality) is handled by model adapters.
            # Still, estimate potential savings for logging by encoding briefly to measure size.
            try:
                compressed_buffer = io.BytesIO()
                if image_format.upper() == IMAGE_DEFAULT_FORMAT:
                    img.save(
                        compressed_buffer,
                        format=IMAGE_DEFAULT_FORMAT,
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

    def _get_next_action_langchain(self, screenshot_bytes: Optional[bytes], xml_context: str, 
                                   action_history: Optional[List[Dict[str, Any]]] = None,
                                   visited_screens: Optional[List[Dict[str, Any]]] = None,
                                   current_screen_actions: Optional[List[Dict[str, Any]]] = None,
                                   current_screen_id: Optional[int] = None,
                                   current_screen_visit_count: int = 0, 
                                   current_composite_hash: str = "", 
                                   last_action_feedback: Optional[str] = None,
                                   is_stuck: bool = False,
                                   stuck_reason: Optional[str] = None) -> Optional[Tuple[Dict[str, Any], float, int, Optional[str]]]:
        """Get the next action using LangChain decision chain.
        
        Args:
            screenshot_bytes: Screenshot image bytes (optional, for future vision support)
            xml_context: XML representation of current screen
            action_history: List of structured action history entries with success/failure info
            visited_screens: List of visited screens with visit counts (filtered to exclude system dialogs)
            current_screen_actions: List of actions already tried on current screen
            current_screen_id: ID of current screen (if known)
            current_screen_visit_count: Number of times current screen has been visited
            current_composite_hash: Hash of current screen state
            last_action_feedback: Feedback from last action execution
            is_stuck: Whether the crawler is detected to be stuck on the same screen
            stuck_reason: Reason why the crawler is considered stuck
            
        Returns:
            Tuple of (action_data dict, confidence float, token_count int, ai_input_prompt str) or None on error
        """
        try:
            # Prepare context for the chain
            context = {
                "screenshot_bytes": screenshot_bytes,
                "xml_context": xml_context or "",
                "action_history": action_history or [],
                "visited_screens": visited_screens or [],
                "current_screen_actions": current_screen_actions or [],
                "current_screen_id": current_screen_id,
                "current_screen_visit_count": current_screen_visit_count or 0,
                "current_composite_hash": current_composite_hash or "",
                "last_action_feedback": last_action_feedback or "",
                "is_stuck": is_stuck,
                "stuck_reason": stuck_reason or ""
            }

            # Extract actual XML string and simplify it before sending to AI
            xml_string_raw = xml_context
            if isinstance(xml_context, dict):
                # Handle nested MCP response structure: data.data.source or data.source
                if 'data' in xml_context:
                    data = xml_context['data']
                    if isinstance(data, dict):
                        # Check for nested data structure (data.data.source)
                        if 'data' in data and isinstance(data['data'], dict):
                            xml_string_raw = data['data'].get('source') or data['data'].get('xml') or str(xml_context)
                        else:
                            # Direct data.source
                            xml_string_raw = data.get('source') or data.get('xml') or str(xml_context)
                    else:
                        xml_string_raw = str(xml_context)
                else:
                    xml_string_raw = str(xml_context)
            elif not isinstance(xml_string_raw, str):
                xml_string_raw = str(xml_string_raw)
            
            # Clean and simplify XML before sending to AI to remove unnecessary attributes
            # Original XML is unlimited, simplified XML is limited to 15000 chars
            xml_string_simplified = xml_string_raw
            if xml_string_raw:
                try:
                    from config.numeric_constants import XML_SNIPPET_MAX_LEN_DEFAULT
                    xml_string_simplified = simplify_xml_for_ai(
                        xml_string=xml_string_raw,
                        max_len=XML_SNIPPET_MAX_LEN_DEFAULT,  # Simplified XML limited to default max length
                        provider=self.ai_provider,
                        prune_noninteractive=True
                    )
                    logging.debug(f"XML simplified: {len(xml_string_raw)} -> {len(xml_string_simplified)} chars (provider: {self.ai_provider})")
                except Exception as e:
                    logging.warning(f"⚠️ XML simplification failed, using original: {e}")
                    xml_string_simplified = xml_string_raw
            
            # Update context with simplified XML (format_prompt_with_context will use this)
            context['xml_context'] = xml_string_simplified
            context['_full_xml_context'] = xml_string_raw  # Store original for reference
            
            # Prepare image if ENABLE_IMAGE_CONTEXT is enabled
            # Store it in self so the LLM wrapper can access it
            self._current_prepared_image = None
            enable_image_context = self.cfg.get('ENABLE_IMAGE_CONTEXT', False)
            
            # Log image context status
            if enable_image_context:
                logging.info(f"🖼️  IMAGE CONTEXT: Enabled (ENABLE_IMAGE_CONTEXT=True)")
            else:
                logging.info(f"🖼️  IMAGE CONTEXT: Disabled (ENABLE_IMAGE_CONTEXT=False)")
            
            if enable_image_context and screenshot_bytes:
                try:
                    # Check if provider/model supports image context before preparing
                    from domain.providers.registry import ProviderRegistry
                    provider_strategy = ProviderRegistry.get_by_name(self.ai_provider)
                    if provider_strategy:
                        model_name = self.actual_model_name if hasattr(self, 'actual_model_name') else self.model_alias
                        if provider_strategy.supports_image_context(self.cfg, model_name):
                            # Prepare the image using existing method
                            prepared_image = self._prepare_image_part(screenshot_bytes)
                            if prepared_image:
                                self._current_prepared_image = prepared_image
                                logging.debug(f"🖼️  IMAGE CONTEXT: Prepared screenshot (size: {prepared_image.size[0]}x{prepared_image.size[1]}) - will be sent to AI model")
                            else:
                                logging.debug(f"🖼️  IMAGE CONTEXT: Image preparation returned None - image will NOT be sent")
                        else:
                            logging.debug(f"🖼️  IMAGE CONTEXT: Model '{model_name}' does not support image context - image will NOT be sent")
                    else:
                        logging.debug(f"🖼️  IMAGE CONTEXT: Could not get provider strategy for {self.ai_provider} - image will NOT be sent")
                except Exception as e:
                    logging.debug(f"🖼️  IMAGE CONTEXT: Error preparing image: {e} - image will NOT be sent", exc_info=True)
            elif enable_image_context and not screenshot_bytes:
                logging.debug(f"🖼️  IMAGE CONTEXT: Enabled but no screenshot bytes available - image will NOT be sent")
            
            # Log the decision request context
            if self.ai_interaction_readable_logger:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(f"DECISION REQUEST - {timestamp}")
                self.ai_interaction_readable_logger.info("=" * 80)
                if is_stuck:
                    self.ai_interaction_readable_logger.info(f"⚠️ STUCK DETECTED: {stuck_reason}")
                    self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(f"Action history entries: {len(action_history) if action_history else 0}")
                self.ai_interaction_readable_logger.info(f"Visited screens: {len(visited_screens) if visited_screens else 0}")
                self.ai_interaction_readable_logger.info(f"Current screen actions: {len(current_screen_actions) if current_screen_actions else 0}")
                self.ai_interaction_readable_logger.info(f"Current screen ID: {current_screen_id}")
                self.ai_interaction_readable_logger.info(f"Screen visit count: {current_screen_visit_count}")
                self.ai_interaction_readable_logger.info(f"Last action feedback: {last_action_feedback}")
                self.ai_interaction_readable_logger.info(f"XML context length (original): {len(xml_string_raw) if xml_string_raw else 0} chars")
                self.ai_interaction_readable_logger.info(f"XML context length (simplified): {len(xml_string_simplified) if xml_string_simplified else 0} chars")
                self.ai_interaction_readable_logger.info("")
                
                # Log the simplified XML context that will be sent to AI
                self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(f"FULL XML CONTEXT SENT TO AI (SIMPLIFIED) - {timestamp}")
                self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(xml_string_simplified if xml_string_simplified else "(empty)")
                self.ai_interaction_readable_logger.info("")

            # Run the decision chain
            try:
                chain_result = self.action_decision_chain.run(context=context)
            finally:
                # Clear the prepared image after use to avoid memory leaks
                self._current_prepared_image = None
            
            # Extract the AI input prompt from context (stored by format_prompt_with_context)
            ai_input_prompt = context.get('_full_ai_input_prompt', None)
            
            # Log the parsed result
            if self.ai_interaction_readable_logger:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(f"PARSED RESULT - {timestamp}")
                self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(json.dumps(chain_result, indent=2) if chain_result else "None")
                self.ai_interaction_readable_logger.info("")
                self.ai_interaction_readable_logger.info("")
            
            # Validate and clean the result
            if not chain_result:
                logging.warning("Chain returned empty result")
                return None
            
            validated_data = self._validate_and_clean_action_data(chain_result)
            
            # Return with metadata (confidence and token count are placeholders for now)
            # Include the AI input prompt for database storage
            return validated_data, 0.0, 0, ai_input_prompt
            
        except ValidationError as e:
            # Clear prepared image on error
            self._current_prepared_image = None
            logging.error(f"Validation error in action data: {e}")
            if self.ai_interaction_readable_logger:
                self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(f"VALIDATION ERROR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(f"Error: {str(e)}")
                self.ai_interaction_readable_logger.info("")
                self.ai_interaction_readable_logger.info("")
            return None
        except Exception as e:
            # Clear prepared image on error
            self._current_prepared_image = None
            logging.error(f"Error getting next action from LangChain: {e}", exc_info=True)
            if self.ai_interaction_readable_logger:
                self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(f"ERROR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                self.ai_interaction_readable_logger.info("=" * 80)
                self.ai_interaction_readable_logger.info(f"Error: {str(e)}")
                self.ai_interaction_readable_logger.info("")
                self.ai_interaction_readable_logger.info("")
            return None


    def _validate_and_clean_action_data(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        return ActionData.model_validate(action_data).dict()

    def _ensure_driver_initialized(self):
        if not self.tools:
            raise RuntimeError("Tools are not initialized.")
        if not hasattr(self.tools, 'driver') or not self.tools.driver:
            raise RuntimeError("Driver is not initialized or unavailable.")
    
    def _ensure_driver_connected(self) -> bool:
        """Ensure the driver is connected to MCP and session is initialized.
        
        Returns:
            True if driver is connected and ready, False otherwise
        """
        try:
            try:
                self._ensure_driver_initialized()
            except RuntimeError:
                return False
            
            driver = self.tools.driver
            
            # Check if session is already initialized
            if hasattr(driver, '_session_initialized') and driver._session_initialized:
                # Validate session is still active
                if driver.validate_session():
                    return True
                else:
                    logging.warning("Session validation failed, reinitializing...")
                    driver._session_initialized = False
            
            # Initialize session if not initialized
            if not driver._session_initialized:
                app_package = self.cfg.get('APP_PACKAGE')
                app_activity = self.cfg.get('APP_ACTIVITY')
                # Get device UDID from path_manager if available
                if hasattr(self.cfg, '_path_manager'):
                    device_udid = self.cfg._path_manager.get_device_udid()
                else:
                    device_udid = None
                
                if not driver.initialize_session(
                    app_package=app_package,
                    app_activity=app_activity,
                    device_udid=device_udid
                ):
                    logging.error("Failed to initialize Appium session")
                    return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error ensuring driver connection: {e}", exc_info=True)
            return False

    def _initialize_action_decision_chain(self):
        if not self.action_decision_chain:
            # Properly initialize action_decision_chain here
            self.action_decision_chain = ActionDecisionChain(chain=self._create_prompt_chain(ACTION_DECISION_SYSTEM_PROMPT))  # Replace with actual initialization logic