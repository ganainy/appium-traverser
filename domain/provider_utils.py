"""
Provider-agnostic utilities for AI provider configuration.

This module provides utilities for working with different AI providers (Gemini, OpenRouter, Ollama)
in a provider-agnostic way.
"""

from typing import Optional, Tuple, Any

from domain.providers.enums import AIProvider
from domain.providers.registry import ProviderRegistry


def get_provider_config_key(provider: str) -> Optional[str]:
    """
    Get the configuration key name for a given provider.
    
    Args:
        provider: The provider name (e.g., 'gemini', 'openrouter', 'ollama')
        
    Returns:
        The configuration key name, or None if provider is not supported
        
    Example:
        >>> get_provider_config_key('gemini')
        'GEMINI_API_KEY'
        >>> get_provider_config_key('ollama')
        'OLLAMA_BASE_URL'
    """
    strategy = ProviderRegistry.get_by_name(provider)
    if strategy:
        return strategy.get_api_key_name()
    return None


def get_provider_api_key(config: Any, provider: str, default_ollama_url: Optional[str] = None) -> Optional[str]:
    """
    Get the API key or base URL for a given provider from the configuration.
    
    This function is provider-agnostic and handles the special case of Ollama
    (which uses a base URL instead of an API key).
    
    Args:
        config: The configuration object (must have a .get() method or support getattr())
        provider: The provider name (e.g., 'gemini', 'openrouter', 'ollama')
        default_ollama_url: Optional default URL for Ollama if not configured
                          (defaults to None)
        
    Returns:
        The API key or base URL, or None if not found
        
    Example:
        >>> config = Config()
        >>> get_provider_api_key(config, 'gemini')
        'AIza...'
        >>> from config.urls import ServiceURLs
        >>> get_provider_api_key(config, 'ollama', default_ollama_url=ServiceURLs.OLLAMA)
        'http://localhost:11434'
    """
    strategy = ProviderRegistry.get_by_name(provider)
    if not strategy:
        return None
    
    return strategy.get_api_key(config, default_ollama_url)


def validate_provider_config(config: Any, provider: str, default_ollama_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate that the required configuration is present for a provider.
    
    Args:
        config: The configuration object
        provider: The provider name (e.g., 'gemini', 'openrouter', 'ollama')
        default_ollama_url: Optional default URL for Ollama if not configured
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if configuration is valid, False otherwise
        - error_message: Error message if invalid, None if valid
        
    Example:
        >>> config = Config()
        >>> validate_provider_config(config, 'gemini')
        (False, 'GEMINI_API_KEY is not set in configuration')
        >>> from config.urls import ServiceURLs
        >>> validate_provider_config(config, 'ollama', default_ollama_url=ServiceURLs.OLLAMA)
        (True, None)
    """
    strategy = ProviderRegistry.get_by_name(provider)
    if not strategy:
        return False, f"Unsupported AI provider: {provider}"
    
    return strategy.validate_config(config)


def get_missing_key_name(provider: str) -> str:
    """
    Get the human-readable name of the missing configuration key for a provider.
    
    Useful for error messages.
    
    Args:
        provider: The provider name
        
    Returns:
        The configuration key name, or a generic "API_KEY" if provider is unknown
    """
    strategy = ProviderRegistry.get_by_name(provider)
    if strategy:
        return strategy.get_api_key_name()
    return "API_KEY"

