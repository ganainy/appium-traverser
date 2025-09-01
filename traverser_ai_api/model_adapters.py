"""
==========================================================================
AI Model Adapters
==========================================================================

This module provides abstract interfaces and concrete implementations
for different AI model providers, allowing the app crawler to use
multiple model providers such as Google Gemini and DeepSeek.

Each adapter implements a common interface to handle:
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
            
            logging.info(f"Gemini model initialized: {self.model_name}")
            
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
            
            logging.info(f"DeepSeek model initialized: {self.model_name}")
            
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
            
            # Add image if provided
            if image:
                # Convert PIL Image to bytes
                image_byte_arr = io.BytesIO()
                image.save(image_byte_arr, format='PNG')
                import base64
                image_b64 = base64.b64encode(image_byte_arr.getvalue()).decode('utf-8')
                
                # Add image to content
                user_message["content"].append({
                    "type": "image",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                })
            
            # Add text prompt
            user_message["content"].append({
                "type": "text",
                "text": prompt
            })
            
            # Add the user message to messages
            messages.append(user_message)
            
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
    return True, ""  # Default case

def create_model_adapter(provider: str, api_key: str, model_name: str) -> ModelAdapter:
    """Factory function to create the appropriate model adapter."""
    if provider.lower() == "gemini":
        return GeminiAdapter(api_key, model_name)
    elif provider.lower() == "deepseek":
        return DeepSeekAdapter(api_key, model_name)
    else:
        raise ValueError(f"Unsupported model provider: {provider}")
