from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

# ------ Provider-Agnostic Entities ------

@dataclass
class Session:
    """Represents a provider-agnostic AI session."""
    session_id: str
    provider: str
    model: str
    created_at: float
    last_active: float
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

"""
==========================================================================
AI Model Adapters
==========================================================================

This module provides abstract interfaces and concrete implementations
for different AI model providers, allowing the app crawler to use
multiple model providers such as Google Gemini, OpenRouter and Ollama.

Each adapter implements a common interface for:
1. Model initialization and configuration
2. Image processing and prompting
3. Response parsing and formatting
4. Error handling and rate limiting

This module focuses on runtime model interaction (inference). For model
discovery and metadata management, see:
- domain/ollama_models.py: Ollama model discovery, caching, and vision detection
- domain/openrouter_models.py: OpenRouter model discovery, caching, and metadata
"""

import io
import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image

# ------ Abstract Model Adapter Interface ------

class ModelAdapter(ABC):
    """Abstract base class for AI model adapters."""
    
    @abstractmethod
    def initialize(self, model_config: Dict[str, Any], safety_settings: Optional[Dict] = None) -> None:
        """Initialize the model with the provided configuration."""
        pass
    
    @abstractmethod
    def generate_response(self, 
                        prompt: str, 
                        image: Optional[Image.Image] = None,
                         **kwargs) -> Tuple[str, Dict[str, Any]]:
        """Generate a response from the model based on the prompt and optional image."""
        pass
    
    @property
    @abstractmethod
    def model_info(self) -> Dict[str, Any]:
        """Return information about the model."""
        pass


# ------ Google Gemini Adapter ------

class GeminiAdapter(ModelAdapter):
    """Adapter for Google's Gemini models."""
    
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.model = None
        self._model_info = {
            "provider": "Google",
            "model_family": "Gemini",
            "model_name": model_name
        }
    
    def initialize(self, model_config: Dict[str, Any], safety_settings: Optional[Dict] = None) -> None:
        """Initialize the Gemini model."""
        try:
            import google.generativeai as genai
            from google.generativeai.generative_models import GenerativeModel
            from google.generativeai.types import GenerationConfig

            # Set API key
            os.environ["GOOGLE_API_KEY"] = self.api_key
            
            # Create generation config
            generation_config_dict = model_config.get('generation_config', {})
            generation_config = GenerationConfig(
                temperature=generation_config_dict.get('temperature', 0.7),
                top_p=generation_config_dict.get('top_p', 0.95),
                top_k=generation_config_dict.get('top_k', 40),
                max_output_tokens=generation_config_dict.get('max_output_tokens', 1024)
            )
            
            # Initialize the model
            self.model = GenerativeModel(
                model_name=self.model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            logging.debug(f"Gemini model initialized: {self.model_name}")
            
        except Exception as e:
            logging.error(f"Failed to initialize Gemini model: {e}", exc_info=True)
            raise
    
    def generate_response(self, 
                        prompt: str, 
                        image: Optional[Image.Image] = None,
                         **kwargs) -> Tuple[str, Dict[str, Any]]:
        """Generate a response from Gemini."""
        if not self.model:
            raise ValueError("Gemini model not initialized")
            
        try:
            start_time = time.time()
            
            # Prepare content parts
            content_parts = []
            
            # Add image if provided
            if image:
                # Gemini handles PIL images directly
                content_parts.append(image)
                
            # Add text prompt
            content_parts.append(prompt)
            
            # Generate response
            response = self.model.generate_content(content_parts)
            
            # Get response text
            response_text = response.text if hasattr(response, 'text') else str(response)
            
            # Prepare metadata
            elapsed_time = time.time() - start_time
            metadata = {
                "processing_time": elapsed_time,
                "model": self.model_name,
                "provider": "Google Gemini"
            }
            
            # Try to get token usage if available
            try:
                prompt_token_count = getattr(response, 'usage_metadata', {}).get('prompt_token_count', 0)
                response_token_count = getattr(response, 'usage_metadata', {}).get('candidates_token_count', 0)
                metadata["token_count"] = {
                    "prompt": prompt_token_count,
                    "response": response_token_count,
                    "total": prompt_token_count + response_token_count
                }
            except:
                # If token count not available, make an estimate
                metadata["token_count"] = {
                    "prompt": len(prompt) // 4,  # Rough estimate
                    "response": len(response_text) // 4,  # Rough estimate
                    "total": (len(prompt) + len(response_text)) // 4  # Rough estimate
                }
            
            return response_text, metadata
            
        except Exception as e:
            logging.error(f"Error generating response from Gemini: {e}", exc_info=True)
            raise
    
    @property
    def model_info(self) -> Dict[str, Any]:
        """Return information about the model."""
        return self._model_info





# ------ OpenRouter Adapter ------

class OpenRouterAdapter(ModelAdapter):
    """Adapter for OpenRouter's models (OpenAI-compatible API)."""
    
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self._model_info = {
            "provider": "OpenRouter",
            "model_family": "OpenRouter",
            "model_name": model_name
        }
    
    def initialize(self, model_config: Dict[str, Any], safety_settings: Optional[Dict] = None) -> None:
        """Initialize the OpenRouter model."""
        try:
            # Dynamically import OpenAI to avoid import errors if package is not installed
            OpenAI = __import__('openai').OpenAI
            
            # Initialize client (OpenRouter uses OpenAI-compatible API)
            self.client = OpenAI(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")
            
            # Store generation parameters
            self.generation_params = model_config.get('generation_config', {})
            
            logging.debug(f"OpenRouter model initialized: {self.model_name}")
            
        except ImportError:
            error_msg = "OpenAI Python SDK not installed. Run: pip install openai"
            logging.error(error_msg)
            raise ImportError(error_msg)
        except Exception as e:
            logging.error(f"Failed to initialize OpenRouter model: {e}", exc_info=True)
            raise
    
    def generate_response(self, 
                         prompt: str, 
                         image: Optional[Image.Image] = None,
                         **kwargs) -> Tuple[str, Dict[str, Any]]:
        """Generate a response from OpenRouter."""
        if not self.client:
            raise ValueError("OpenRouter client not initialized")
            
        try:
            start_time = time.time()
            
            # Prepare message content
            messages = []
            
            # Create user message
            user_message = {"role": "user", "content": []}
            
            # Add image if provided (use provider capability settings, with UI overrides)
            if image:
                # Get provider capabilities for image settings
                try:
                    from config import AI_PROVIDER_CAPABILITIES
                except ImportError:
                    from config import AI_PROVIDER_CAPABILITIES
                
                capabilities = AI_PROVIDER_CAPABILITIES.get('openrouter', {})
                # UI/kwargs overrides take precedence over provider defaults
                image_format = kwargs.get('image_format', None) or capabilities.get('image_format', 'JPEG')
                image_quality = kwargs.get('image_quality', None) or capabilities.get('image_quality', 65)
                
                # Convert PIL Image to bytes with optimized settings
                image_byte_arr = io.BytesIO()
                # Ensure compatible color mode for certain formats
                try:
                    if image_format.upper() in ('JPEG', 'WEBP') and image.mode not in ('RGB'):
                        image = image.convert('RGB')
                except Exception:
                    pass
                if image_format.upper() == 'JPEG':
                    image.save(image_byte_arr, format='JPEG', quality=image_quality, optimize=True, progressive=True, subsampling='4:2:0')
                else:
                    image.save(image_byte_arr, format=image_format, optimize=True)
                image_bytes = image_byte_arr.getvalue()
                
                payload_max_kb = capabilities.get('payload_max_size_kb', 150)
                payload_max_bytes = payload_max_kb * 1024
                
                # Estimate total payload size (prompt + base64 image)
                estimated_prompt_size = len(prompt.encode('utf-8'))
                estimated_image_size = len(image_bytes)
                estimated_base64_size = (estimated_image_size * 4) // 3
                total_estimated_size = estimated_prompt_size + estimated_base64_size
                
                # If total estimated size > limit, skip image to prevent payload errors
                if total_estimated_size > payload_max_bytes:
                    logging.warning(f"Estimated payload size ({total_estimated_size} bytes) too large for OpenRouter (limit: {payload_max_bytes}). Skipping image context.")
                    logging.debug(f"Prompt size: {estimated_prompt_size}, Image size: {estimated_image_size} -> {estimated_base64_size} (base64)")
                else:
                    import base64
                    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
                    
                    # Add image to content (OpenAI-style image_url for multimodal models)
                    user_message["content"].append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{image_format.lower()};base64,{image_b64}"}
                    })
                    logging.debug(f"Added compressed image to OpenRouter payload ({image_format}, {image_quality}% quality, base64 size: {len(image_b64)} chars)")
            
            # Add text prompt
            user_message["content"].append({
                "type": "text",
                "text": prompt
            })
            
            messages.append(user_message)
            
            # Log payload size estimate for debugging
            try:
                payload_str = json.dumps(messages, separators=(',', ':'))
                payload_size = len(payload_str.encode('utf-8'))
                
                try:
                    from config import AI_PROVIDER_CAPABILITIES
                except ImportError:
                    from config import AI_PROVIDER_CAPABILITIES
                
                capabilities = AI_PROVIDER_CAPABILITIES.get('openrouter', {})
                payload_max_kb = capabilities.get('payload_max_size_kb', 150)
                warning_threshold = int(payload_max_kb * 0.9) * 1024
                
                logging.debug(f"OpenRouter payload size: {payload_size} bytes")
                if payload_size > warning_threshold:
                    logging.warning(f"OpenRouter payload size ({payload_size} bytes) approaching limit ({payload_max_kb}KB). Consider reducing XML_SNIPPET_MAX_LEN.")
            except Exception as size_calc_error:
                logging.debug(f"Could not calculate payload size: {size_calc_error}")
            
            # Generate response via OpenAI-compatible API
            def _create_completion(model_name: str):
                return self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=self.generation_params.get("temperature", 0.7),
                    top_p=self.generation_params.get("top_p", 0.95),
                    max_tokens=self.generation_params.get("max_output_tokens", 1024)
                )

            response = None
            try:
                response = _create_completion(self.model_name)
            except Exception as e_req:
                # Handle common OpenRouter 404 when a model alias/id is unavailable
                err_str = str(e_req)
                if ("No endpoints found" in err_str) or ("404" in err_str and "/chat/completions" in err_str):
                    logging.error(
                        f"OpenRouter model '{self.model_name}' unavailable (404). No fallback will be attempted. Please select a different model.")
                    raise
                else:
                    # Unknown error, re-raise
                    raise
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Prepare metadata
            elapsed_time = time.time() - start_time
            metadata = {
                "processing_time": elapsed_time,
                "model": self.model_name,
                "provider": "OpenRouter"
            }
            
            # Get token usage if available
            try:
                metadata["token_count"] = {
                    "prompt": response.usage.prompt_tokens,
                    "response": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                }
            except:
                metadata["token_count"] = {
                    "prompt": len(prompt) // 4,
                    "response": len(response_text) // 4,
                    "total": (len(prompt) + len(response_text)) // 4
                }
            
            return response_text, metadata
            
        except Exception as e:
            logging.error(f"Error generating response from OpenRouter: {e}", exc_info=True)
            raise
    
    @property
    def model_info(self) -> Dict[str, Any]:
        """Return information about the model."""
        return self._model_info


# ------ Ollama Adapter ------

class OllamaAdapter(ModelAdapter):
    """Adapter for Ollama local models."""
    
    def __init__(self, api_key: str, model_name: str):
        # Extract the actual model name from display name (remove "(local)" and vision indicator)
        self.display_name = model_name
        self.model_name = self._extract_model_name(model_name)
        self.base_url = api_key  # For Ollama, api_key parameter contains the base URL
        self.vision_supported = False  # Will be set during initialization
        self._model_info = {
            "provider": "Ollama",
            "model_family": "Local LLM",
            "model_name": self.model_name
        }
    
    def _extract_model_name(self, model_name: str) -> str:
        """Extract the model name, preserving the tag for Ollama API but removing suffixes.
        
        Ollama API uses the full model name with tag (e.g., "llama3.2-vision:latest"),
        but we need to strip any UI-specific suffixes like "(local)" or vision indicators.
        """
        # Remove UI-specific suffixes
        name_to_process = model_name
        for suffix in [" (local)", " 👁️", " (Ollama)"]:
            name_to_process = name_to_process.replace(suffix, "")
            
        # Check if the name has any whitespace (shouldn't for Ollama models)
        if " " in name_to_process:
            logging.warning(f"⚠️ Suspicious whitespace in model name: '{name_to_process}'. This may cause issues with Ollama.")
            name_to_process = name_to_process.strip()
            
        # Log the extraction
        if name_to_process != model_name:
            logging.debug(f"Extracted model name '{name_to_process}' from display name '{model_name}'")
            
        return name_to_process
    
    def _check_vision_support(self, model_name: str) -> bool:
        """Check if the model supports vision capabilities.
        
        Delegates to the shared vision detection function in ollama_models.py
        to ensure consistent detection across the codebase. Uses hybrid detection
        (metadata → CLI → patterns) for accurate results.
        """
        try:
            from domain.ollama_models import is_ollama_model_vision
            # Pass base_url if available to enable metadata/CLI checks with custom Ollama instances
            return is_ollama_model_vision(model_name, base_url=self.base_url)
        except Exception as e:
            # Log the error but don't crash - fall back to conservative result
            logging.warning(f"Error checking vision support for {model_name}: {e}")
            return False
    
    def initialize(self, model_config: Dict[str, Any], safety_settings: Optional[Dict] = None) -> None:
        """Initialize the Ollama model."""
        try:
            # Try to import ollama
            import ollama

            # Set the base URL if provided
            if self.base_url:
                # Set the base URL using environment variable (Ollama SDK method)
                os.environ['OLLAMA_HOST'] = self.base_url
            
            # Store generation parameters
            self.generation_params = model_config.get('generation_config', {})
            
            # Check if this model supports vision based on the actual model name
            self.vision_supported = self._check_vision_support(self.model_name)
            
            # Test connection to Ollama
            try:
                ollama.list()
                logging.debug(f"Ollama connection successful. Using model: {self.model_name}")
                if self.vision_supported:
                    logging.debug(f"Model {self.model_name} supports vision capabilities")
                else:
                    logging.debug(f"Model {self.model_name} is text-only")
            except Exception as conn_error:
                logging.warning(f"Could not verify Ollama connection: {conn_error}. Make sure Ollama is running.")
            
            logging.debug(f"Ollama model initialized: {self.model_name}")
            
        except ImportError:
            error_msg = "Ollama Python SDK not installed. Run: pip install ollama"
            logging.error(error_msg)
            raise ImportError(error_msg)
        except Exception as e:
            logging.error(f"Failed to initialize Ollama model: {e}", exc_info=True)
            raise
    
    def generate_response(self, 
                         prompt: str, 
                         image: Optional[Image.Image] = None,
                         **kwargs) -> Tuple[str, Dict[str, Any]]:
        """Generate a response from Ollama."""
        try:
            import base64
            import io

            import ollama
            start_time = time.time()
            
            # Check if model is available before attempting to use it
            available_model_names = []
            try:
                available_models = ollama.list()
                
                # Handle the new Ollama API response format (Python SDK v0.5.0+)
                for model_obj in available_models.models:
                    # Extract model name from the model object
                    if hasattr(model_obj, 'model'):
                        model_name = model_obj.model
                        if model_name and isinstance(model_name, str):
                            available_model_names.append(model_name)
                
                # Check if our model is in the list
                if self.model_name not in available_model_names:
                    # Build clean error message with available models and commands
                    if available_model_names:
                        models_list = "\n  - " + "\n  - ".join(available_model_names)
                        error_msg = (
                            f"Model '{self.model_name}' not found.\n"
                            f"Available models:{models_list}\n\n"
                            f"To select a model, run:\n"
                            f"  python run_cli.py ollama select-model <index_or_name>\n\n"
                            f"To install a new model, run:\n"
                            f"  ollama pull {self.model_name}"
                        )
                    else:
                        error_msg = (
                            f"Model '{self.model_name}' not found. No models available.\n\n"
                            f"To install a model, run:\n"
                            f"  ollama pull {self.model_name}\n\n"
                            f"Then select it with:\n"
                            f"  python run_cli.py ollama select-model {self.model_name}"
                        )
                    raise ValueError(error_msg)
                else:
                    logging.debug(f"✅ Verified model '{self.model_name}' is available in Ollama")
            except ValueError:
                # Re-raise ValueError (model not found) without modification
                raise
            except Exception as list_error:
                # If we can't list models, store available_model_names as empty for later error handling
                logging.debug(f"Could not verify model availability: {list_error}")
                available_model_names = []
            
            # Prepare messages and images
            messages = []
            images = []
            
            # Check if the model supports vision
            supports_vision = self.vision_supported
            
            # Handle image if provided and model supports vision
            if image and supports_vision:
                try:
                    # For Ollama, we can work directly with the PIL Image object
                    # The Ollama SDK supports passing PIL images directly in some versions
                    # If not supported, we'll use the raw image data
                    images.append(image)
                    logging.debug(f"Added image to Ollama request (format: {image.format}, size: {image.size})")
                except Exception as img_error:
                    logging.error(f"Error processing image for Ollama: {img_error}", exc_info=True)
                    raise ValueError(f"Failed to process image for Ollama: {img_error}")
            elif image and not supports_vision:
                logging.warning(f"Model '{self.model_name}' does not support vision. Processing text-only.")
            
            # Add user message with simple string content (Ollama format)
            user_message = {
                "role": "user", 
                "content": prompt
            }
            
            messages.append(user_message)
            
            # Use different API based on whether model supports vision
            if supports_vision and images:
                logging.debug(f"Using Ollama vision API with {len(images)} images")
                
                try:
                    # Using chat method with images in the message as shown in Ollama docs
                    # https://ollama.com/blog/vision-models
                    response = ollama.chat(
                        model=self.model_name,
                        messages=[
                            {
                                'role': 'user',
                                'content': prompt,
                                'images': images
                            }
                        ],
                        options={
                            "temperature": self.generation_params.get("temperature", 0.7),
                            "top_p": self.generation_params.get("top_p", 0.95),
                            "num_predict": self.generation_params.get("max_output_tokens", 1024)
                        }
                    )
                    # Extract response text from chat response
                    response_text = response.message.content
                    # Ensure response_text is a string
                    if not isinstance(response_text, str):
                        response_text = str(response_text)
                except Exception as chat_error:
                    # Check if it's a model not found error (404)
                    error_str = str(chat_error).lower()
                    if "not found" in error_str or "404" in error_str:
                        # Get available models if we don't have them yet
                        if not available_model_names:
                            try:
                                available_models = ollama.list()
                                for model_obj in available_models.models:
                                    if hasattr(model_obj, 'model'):
                                        model_name = model_obj.model
                                        if model_name and isinstance(model_name, str):
                                            available_model_names.append(model_name)
                            except Exception:
                                pass
                        
                        # Build clean error message
                        if available_model_names:
                            models_list = "\n  - " + "\n  - ".join(available_model_names)
                            error_msg = (
                                f"Model '{self.model_name}' not found.\n"
                                f"Available models:{models_list}\n\n"
                                f"To select a model, run:\n"
                                f"  python run_cli.py ollama select-model <index_or_name>\n\n"
                                f"To install a new model, run:\n"
                                f"  ollama pull {self.model_name}"
                            )
                        else:
                            error_msg = (
                                f"Model '{self.model_name}' not found. No models available.\n\n"
                                f"To install a model, run:\n"
                                f"  ollama pull {self.model_name}\n\n"
                                f"Then select it with:\n"
                                f"  python run_cli.py ollama select-model {self.model_name}"
                            )
                        raise ValueError(error_msg)
                    else:
                        # Other errors - log with minimal traceback
                        logging.error(f"Ollama chat API call failed: {chat_error}")
                        raise ValueError(f"Ollama API error: {chat_error}")
            else:
                logging.debug("Using Ollama chat API (text-only)")
                try:
                    # Use chat API for text-only models
                    response = ollama.chat(
                        model=self.model_name,
                        messages=messages,
                        options={
                            "temperature": self.generation_params.get("temperature", 0.7),
                            "top_p": self.generation_params.get("top_p", 0.95),
                            "num_predict": self.generation_params.get("max_output_tokens", 1024)
                        }
                    )
                    # Extract response text from chat response
                    response_text = response.message.content
                    # Ensure response_text is a string
                    if not isinstance(response_text, str):
                        response_text = str(response_text)
                except Exception as chat_error:
                    # Check if it's a model not found error (404)
                    error_str = str(chat_error).lower()
                    if "not found" in error_str or "404" in error_str:
                        # Get available models if we don't have them yet
                        if not available_model_names:
                            try:
                                available_models = ollama.list()
                                for model_obj in available_models.models:
                                    if hasattr(model_obj, 'model'):
                                        model_name = model_obj.model
                                        if model_name and isinstance(model_name, str):
                                            available_model_names.append(model_name)
                            except Exception:
                                pass
                        
                        # Build clean error message
                        if available_model_names:
                            models_list = "\n  - " + "\n  - ".join(available_model_names)
                            error_msg = (
                                f"Model '{self.model_name}' not found.\n"
                                f"Available models:{models_list}\n\n"
                                f"To select a model, run:\n"
                                f"  python run_cli.py ollama select-model <index_or_name>\n\n"
                                f"To install a new model, run:\n"
                                f"  ollama pull {self.model_name}"
                            )
                        else:
                            error_msg = (
                                f"Model '{self.model_name}' not found. No models available.\n\n"
                                f"To install a model, run:\n"
                                f"  ollama pull {self.model_name}\n\n"
                                f"Then select it with:\n"
                                f"  python run_cli.py ollama select-model {self.model_name}"
                            )
                        raise ValueError(error_msg)
                    else:
                        # Other errors - log with minimal traceback
                        logging.error(f"Ollama chat API call failed: {chat_error}")
                        raise ValueError(f"Ollama API error: {chat_error}")
            
            # Ensure response_text is a valid string
            if response_text is None:
                response_text = ""
            elif not isinstance(response_text, str):
                response_text = str(response_text)
            
            # Prepare metadata
            elapsed_time = time.time() - start_time
            metadata = {
                "processing_time": elapsed_time,
                "model": self.model_name,
                "provider": "Ollama"
            }
            
            # Ollama doesn't provide token counts in the same way
            # Make an estimate
            metadata["token_count"] = {
                "prompt": len(prompt) // 4,  # Rough estimate
                "response": len(response_text) // 4,  # Rough estimate
                "total": (len(prompt) + len(response_text)) // 4  # Rough estimate
            }
            
            return response_text, metadata
            
        except ValueError:
            # Re-raise ValueError (clean error messages) without modification
            raise
        except Exception as e:
            # Only log full traceback for unexpected errors
            logging.error(f"Error generating response from Ollama: {e}", exc_info=True)
            raise
    
    @property
    def model_info(self) -> Dict[str, Any]:
        """Return information about the model."""
        return self._model_info


# ------ Factory Function ------

def check_dependencies(provider: str) -> tuple[bool, str]:
    """Check if the required dependencies are installed for the chosen provider."""
    if provider.lower() == "gemini":
        try:
            import google.generativeai
            return True, ""
        except ImportError:
            return False, "Google Generative AI Python SDK not installed. Run: pip install google-generativeai"
    elif provider.lower() == "openrouter":
        try:
            __import__('openai')
            return True, ""
        except ImportError:
            return False, "OpenAI Python SDK not installed. Run: pip install openai"
    elif provider.lower() == "ollama":
        try:
            import ollama
            return True, ""
        except ImportError:
            return False, "Ollama Python SDK not installed. Run: pip install ollama"
    return True, ""  # Default case

def create_model_adapter(provider: str, api_key: str, model_name: str) -> ModelAdapter:
    """Factory function to create the appropriate model adapter."""
    if provider.lower() == "gemini":
        return GeminiAdapter(api_key, model_name)
    elif provider.lower() == "openrouter":
        return OpenRouterAdapter(api_key, model_name)
    elif provider.lower() == "ollama":
        return OllamaAdapter(api_key, model_name)
    else:
        raise ValueError(f"Unsupported model provider: {provider}")
