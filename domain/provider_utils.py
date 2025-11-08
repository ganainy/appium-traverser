"""
Provider-agnostic utilities for AI provider configuration.

This module provides utilities for working with different AI providers (Gemini, OpenRouter, Ollama)
in a provider-agnostic way, eliminating the need for provider-specific if/elif chains throughout
the codebase.
"""

from typing import Optional, Tuple, Any


# Provider-to-config-key mapping
# Maps provider names to their corresponding configuration key names
PROVIDER_API_KEY_MAP = {
    'gemini': 'GEMINI_API_KEY',
    'openrouter': 'OPENROUTER_API_KEY',
    'ollama': 'OLLAMA_BASE_URL'  # Note: For Ollama, this is a URL, not an API key
}


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
    return PROVIDER_API_KEY_MAP.get(provider.lower())


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
        >>> get_provider_api_key(config, 'ollama', default_ollama_url='http://localhost:11434')
        'http://localhost:11434'
    """
    provider = provider.lower()
    config_key = get_provider_config_key(provider)
    
    if not config_key:
        return None
    
    # Get the value from config (supports both .get() method and getattr())
    if hasattr(config, 'get'):
        value = config.get(config_key)
    else:
        value = getattr(config, config_key, None)
    
    # For Ollama, use default URL if not configured
    if provider == 'ollama' and not value and default_ollama_url:
        return default_ollama_url
    
    return value


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
        >>> validate_provider_config(config, 'ollama', default_ollama_url='http://localhost:11434')
        (True, None)
    """
    provider = provider.lower()
    
    # Check if provider is supported
    if provider not in PROVIDER_API_KEY_MAP:
        return False, f"Unsupported AI provider: {provider}"
    
    config_key = PROVIDER_API_KEY_MAP[provider]
    api_key_or_url = get_provider_api_key(config, provider, default_ollama_url)
    
    # For Ollama, it's okay if not set (will use default)
    if provider == 'ollama':
        return True, None
    
    # For other providers, API key is required
    if not api_key_or_url:
        return False, f"{config_key} is not set in configuration"
    
    return True, None


def get_missing_key_name(provider: str) -> str:
    """
    Get the human-readable name of the missing configuration key for a provider.
    
    Useful for error messages.
    
    Args:
        provider: The provider name
        
    Returns:
        The configuration key name, or a generic "API_KEY" if provider is unknown
    """
    return PROVIDER_API_KEY_MAP.get(provider.lower(), "API_KEY")

