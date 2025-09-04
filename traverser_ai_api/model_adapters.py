"""
==========================================================================
AI Model Adapters
==========================================================================

This module provides abstract interfaces and concrete implementations
for different AI model providers, allowing the app crawler to use
multiple model providers such as Google Gemini and DeepSeek.

Each adapter implements a common interfa            # Check if model is available before attempting to use it
            try:
                available_models = ollama.list()
                model_names = []
                
                # Safely extract model names with better error handling
                if 'models' in available_models and isinstance(available_models['models'], list):
                    for model in available_models['models']:
                        if isinstance(model, dict):
                            # Try both 'name' and 'model' keys
                            model_name = model.get('name') or model.get('model', '')
                            if model_name:
                                model_names.append(model_name)
                                # Also add base name without tag
                                if ':' in model_name:
                                    base_name = model_name.split(':')[0]
                                    if base_name and base_name not in model_names:
                                        model_names.append(base_name)
                
                # Check if our model is in the list (with or without tag)
                base_model_name = self.model_name.split(':')[0] if ':' in self.model_name else self.model_name
                if self.model_name not in model_names and base_model_name not in model_names:
                    available_str = ", ".join(model_names) if model_names else "None"
                    error_msg = f"🔴 Model '{self.model_name}' not found. Available models: {available_str}. Please run: ollama pull {self.model_name}"
                    logging.error(error_msg)
                    raise ValueError(error_msg)
                else:
                    logging.debug(f"✅ Verified model '{self.model_name}' is available in Ollama")
            except Exception as list_error:
                logging.warning(f"⚠️ Could not verify model availability: {list_error}. Proceeding anyway.")
1. Model initialization and configuration
2. Image processing and prompting
3. Response parsing and formatting
4. Error handling and rate limiting
"""

import os
import logging
import time
import json
import re
import io
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
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
            from google.generativeai.types import GenerationConfig
            from google.generativeai.generative_models import GenerativeModel
            
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


# ------ DeepSeek Adapter ------

class DeepSeekAdapter(ModelAdapter):
    """Adapter for DeepSeek's models."""
    
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self._model_info = {
            "provider": "DeepSeek",
            "model_family": "DeepSeek",
            "model_name": model_name
        }
    
    def initialize(self, model_config: Dict[str, Any], safety_settings: Optional[Dict] = None) -> None:
        """Initialize the DeepSeek model."""
        try:
            # Dynamically import OpenAI to avoid import errors if package is not installed
            OpenAI = __import__('openai').OpenAI
            
            # Initialize client (DeepSeek uses OpenAI-compatible API)
            self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
            
            # Store generation parameters
            self.generation_params = model_config.get('generation_config', {})
            
            logging.debug(f"DeepSeek model initialized: {self.model_name}")
            
        except ImportError:
            error_msg = "OpenAI Python SDK not installed. Run: pip install openai"
            logging.error(error_msg)
            raise ImportError(error_msg)
        except Exception as e:
            logging.error(f"Failed to initialize DeepSeek model: {e}", exc_info=True)
            raise
    
    def generate_response(self, 
                         prompt: str, 
                         image: Optional[Image.Image] = None,
                         **kwargs) -> Tuple[str, Dict[str, Any]]:
        """Generate a response from DeepSeek."""
        if not self.client:
            raise ValueError("DeepSeek client not initialized")
            
        try:
            start_time = time.time()
            
            # Prepare message content
            messages = []
            
            # Create user message
            user_message = {"role": "user", "content": []}
            
            # Add image if provided (with size validation for DeepSeek)
            if image:
                # Get provider capabilities for image settings
                try:
                    from .config import AI_PROVIDER_CAPABILITIES
                except ImportError:
                    from config import AI_PROVIDER_CAPABILITIES
                
                capabilities = AI_PROVIDER_CAPABILITIES.get('deepseek', {})
                image_format = capabilities.get('image_format', 'JPEG')
                image_quality = capabilities.get('image_quality', 65)
                
                # Convert PIL Image to bytes using optimized settings
                image_byte_arr = io.BytesIO()
                if image_format.upper() == 'JPEG':
                    image.save(image_byte_arr, format='JPEG', quality=image_quality, optimize=True, progressive=True, subsampling='4:2:0')
                else:
                    image.save(image_byte_arr, format=image_format, optimize=True)
                image_bytes = image_byte_arr.getvalue()
                
                payload_max_kb = capabilities.get('payload_max_size_kb', 150)
                payload_max_bytes = payload_max_kb * 1024
                
                # Check if image + prompt would exceed provider limits
                estimated_prompt_size = len(prompt.encode('utf-8'))
                estimated_image_size = len(image_bytes)
                estimated_base64_size = (estimated_image_size * 4) // 3  # Base64 encoding increases size by ~33%
                total_estimated_size = estimated_prompt_size + estimated_base64_size
                
                # If total estimated size > limit, skip image to prevent payload errors
                if total_estimated_size > payload_max_bytes:
                    logging.warning(f"Estimated payload size ({total_estimated_size} bytes) too large for DeepSeek (limit: {payload_max_bytes}). Skipping image context.")
                    logging.debug(f"Prompt size: {estimated_prompt_size}, Image size: {estimated_image_size} -> {estimated_base64_size} (base64)")
                else:
                    import base64
                    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
                    
                    # Add image to content
                    user_message["content"].append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{image_format.lower()};base64,{image_b64}"}
                    })
                    logging.debug(f"Added compressed image to DeepSeek payload ({image_format}, {image_quality}% quality, base64 size: {len(image_b64)} chars)")
            
            # Add text prompt
            user_message["content"].append({
                "type": "text",
                "text": prompt
            })
            
            # Add the user message to messages
            messages.append(user_message)
            
            # Log payload size estimate for debugging
            try:
                import json
                payload_str = json.dumps(messages, separators=(',', ':'))
                payload_size = len(payload_str.encode('utf-8'))
                
                # Get provider capabilities for warning threshold
                try:
                    from .config import AI_PROVIDER_CAPABILITIES
                except ImportError:
                    from config import AI_PROVIDER_CAPABILITIES
                
                capabilities = AI_PROVIDER_CAPABILITIES.get('deepseek', {})
                payload_max_kb = capabilities.get('payload_max_size_kb', 150)
                warning_threshold = int(payload_max_kb * 0.9) * 1024  # 90% of limit
                
                logging.debug(f"DeepSeek payload size: {payload_size} bytes")
                if payload_size > warning_threshold:  # Warn if over 90% of limit
                    logging.warning(f"DeepSeek payload size ({payload_size} bytes) approaching limit ({payload_max_kb}KB). Consider reducing XML_SNIPPET_MAX_LEN.")
            except Exception as size_calc_error:
                logging.debug(f"Could not calculate payload size: {size_calc_error}")
            
            # Generate response
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.generation_params.get("temperature", 0.7),
                top_p=self.generation_params.get("top_p", 0.95),
                max_tokens=self.generation_params.get("max_output_tokens", 1024)
            )
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Prepare metadata
            elapsed_time = time.time() - start_time
            metadata = {
                "processing_time": elapsed_time,
                "model": self.model_name,
                "provider": "DeepSeek"
            }
            
            # Get token usage if available
            try:
                metadata["token_count"] = {
                    "prompt": response.usage.prompt_tokens,
                    "response": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
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
            logging.error(f"Error generating response from DeepSeek: {e}", exc_info=True)
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
        
        This method uses a direct query to Ollama for model information when possible,
        and falls back to pattern matching when necessary.
        """
        try:
            import ollama
            
            # Extract base name for feature detection
            base_name = model_name.split(':')[0].lower()
            
            # First, try to get model tags or metadata from Ollama
            # This would be the preferred approach if Ollama API provides this info
            # Future improvement: Use Ollama API to get model capabilities directly
            
            # For now, we'll still use name-based detection as primary method
            # since Ollama doesn't have a direct "capabilities" API
            vision_patterns = [
                'vision', 'llava', 'bakllava', 'minicpm-v', 'moondream', 'gemma3', 
                'llama', 'qwen2.5vl', 'mistral3', 'vl'
            ]
            return any(pattern in base_name for pattern in vision_patterns)
            
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
            import ollama
            import base64
            import io
            start_time = time.time()
            
            # Check if model is available before attempting to use it
            try:
                available_models = ollama.list()
                model_names = []
                
                # Handle the new Ollama API response format (Python SDK v0.5.0+)
                if hasattr(available_models, 'models') and isinstance(available_models.models, list):
                    for model_obj in available_models.models:
                            # Extract model name from the model object
                            if hasattr(model_obj, 'model'):
                                model_name = model_obj.model
                                if model_name and isinstance(model_name, str):
                                    model_names.append(model_name)
                                    
                                    # Also add base name without tag
                                    if ':' in model_name:
                                        base_name = model_name.split(':')[0]
                                        if base_name and base_name not in model_names:
                                            model_names.append(base_name)                # Handle older dictionary format for backward compatibility
                elif isinstance(available_models, dict) and 'models' in available_models:
                    for model in available_models['models']:
                        if isinstance(model, dict):
                            model_name = model.get('name') or model.get('model', '')
                            if model_name and isinstance(model_name, str):
                                model_names.append(model_name)
                                # Also add base name without tag
                                if ':' in model_name:
                                    base_name = model_name.split(':')[0]
                                    if base_name and base_name not in model_names:
                                        model_names.append(base_name)
                
                # Check if our model is in the list (with or without tag)
                base_model_name = self.model_name.split(':')[0] if ':' in self.model_name else self.model_name
                if self.model_name not in model_names and base_model_name not in model_names:
                    available_str = ", ".join(model_names) if model_names else "None"
                    error_msg = f"🔴 Model '{self.model_name}' not found. Available models: {available_str}. Please run: ollama pull {self.model_name}"
                    logging.error(error_msg)
                    raise ValueError(error_msg)
                else:
                    logging.debug(f"✅ Verified model '{self.model_name}' is available in Ollama")
            except Exception as list_error:
                logging.warning(f"⚠️ Could not verify model availability: {list_error}. Proceeding anyway.")
            
            # Prepare messages and images
            messages = []
            images = []
            
            # Check if the model supports vision
            supports_vision = self.vision_supported
            
            # Handle image if provided and model supports vision
            if image and supports_vision:
                try:
                    # Save temporary file with a unique identifier
                    import uuid
                    temp_image_path = f"temp_ollama_image_{uuid.uuid4()}.jpg"
                    
                    # Convert image to RGB mode if it's not in a compatible format
                    if image.mode not in ('RGB'):
                        image = image.convert('RGB')
                        
                    # Save the image to a temporary file
                    image.save(temp_image_path, format="JPEG", quality=95)
                    
                    # For Ollama, we'll pass the file path directly in the images parameter
                    # This follows the documented approach: https://ollama.com/blog/vision-models
                    images.append(temp_image_path)
                    logging.debug(f"Added image to Ollama request (file: {temp_image_path})")
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
            temp_files_to_cleanup = []
            
            if supports_vision and images:
                logging.debug(f"Using Ollama vision API with {len(images)} images")
                # Track temporary files to clean up
                temp_files_to_cleanup.extend(images)
                
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
                    if hasattr(response, 'message') and hasattr(response.message, 'content'):
                        response_text = response.message.content
                    else:
                        response_text = response.get('message', {}).get('content', '')
                except Exception as chat_error:
                    logging.error(f"Error in Ollama chat API call: {chat_error}", exc_info=True)
                    raise ValueError(f"Ollama chat API call failed: {chat_error}")
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
                    if hasattr(response, 'message') and hasattr(response.message, 'content'):
                        response_text = response.message.content
                    else:
                        response_text = response.get('message', {}).get('content', '')
                    
                    # Ensure response_text is a string
                    if response_text is None:
                        response_text = ""
                    elif not isinstance(response_text, str):
                        response_text = str(response_text)
                except Exception as chat_error:
                    logging.error(f"Error in Ollama chat API call: {chat_error}")
                    raise ValueError(f"Ollama chat API call failed: {chat_error}")
            
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
            
            # Clean up any temporary image files
            for temp_file in temp_files_to_cleanup:
                try:
                    import os
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logging.debug(f"Cleaned up temporary file: {temp_file}")
                except Exception as cleanup_error:
                    logging.warning(f"Failed to clean up temporary file {temp_file}: {cleanup_error}")
            
            return response_text, metadata
            
        except Exception as e:
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
    elif provider.lower() == "deepseek":
        try:
            # Try to import OpenAI
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
    elif provider.lower() == "deepseek":
        return DeepSeekAdapter(api_key, model_name)
    elif provider.lower() == "ollama":
        return OllamaAdapter(api_key, model_name)
    else:
        raise ValueError(f"Unsupported model provider: {provider}")
