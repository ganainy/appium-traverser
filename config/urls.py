"""
Centralized URL configuration for all external services.

All service URLs can be overridden via environment variables with sensible defaults.
This provides flexibility for different deployment environments (dev, staging, prod).
"""

import os
from typing import Optional


class ServiceURLs:
    """Centralized service URL configuration with environment variable support."""
    
    # Appium Server
    APPIUM = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    
    # MobSF API
    MOBSF = os.getenv("MOBSF_API_URL", "http://localhost:8000/api/v1")
    
    # Ollama Service
    OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # OpenRouter API
    OPENROUTER_API = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODELS = f"{OPENROUTER_API}/models"
    
    # Google Gemini API
    GEMINI_API = os.getenv("GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta")
    GEMINI_MODELS = f"{GEMINI_API}/models"
    
    @classmethod
    def get_appium_url(cls, override: Optional[str] = None) -> str:
        """Get Appium server URL with optional override."""
        return override or cls.APPIUM
    
    @classmethod
    def get_mobsf_url(cls, override: Optional[str] = None) -> str:
        """Get MobSF API URL with optional override."""
        return override or cls.MOBSF
    
    @classmethod
    def get_ollama_url(cls, override: Optional[str] = None) -> str:
        """Get Ollama base URL with optional override."""
        return override or cls.OLLAMA
    
    @classmethod
    def get_openrouter_api_url(cls, override: Optional[str] = None) -> str:
        """Get OpenRouter API base URL with optional override."""
        return override or cls.OPENROUTER_API
    
    @classmethod
    def get_openrouter_models_url(cls, override: Optional[str] = None) -> str:
        """Get OpenRouter models endpoint URL with optional override."""
        if override:
            # If override is a full URL, use it; otherwise append /models
            if override.endswith("/models"):
                return override
            return f"{override}/models" if override.endswith("/v1") else f"{override}/api/v1/models"
        return cls.OPENROUTER_MODELS
    
    @classmethod
    def get_gemini_api_url(cls, override: Optional[str] = None) -> str:
        """Get Gemini API base URL with optional override."""
        return override or cls.GEMINI_API
    
    @classmethod
    def get_gemini_models_url(cls, override: Optional[str] = None) -> str:
        """Get Gemini models endpoint URL with optional override."""
        if override:
            # If override is a full URL, use it; otherwise append /models
            if override.endswith("/models"):
                return override
            return f"{override}/models"
        return cls.GEMINI_MODELS

