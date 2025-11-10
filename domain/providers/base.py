"""
Base provider strategy interface.

This module defines the abstract base class that all provider implementations
must follow, ensuring a consistent interface across different AI providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from config.app_config import Config

from domain.providers.enums import AIProvider


class ProviderStrategy(ABC):
    """
    Abstract base class for AI provider strategies.
    
    Each provider (Gemini, OpenRouter, Ollama) implements this interface
    to provide provider-specific functionality while maintaining a consistent
    API across all providers.
    """
    
    def __init__(self, provider: AIProvider):
        """
        Initialize the provider strategy.
        
        Args:
            provider: The AIProvider enum value for this strategy
        """
        self.provider = provider
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name as a string."""
        pass
    
    @abstractmethod
    def get_models(self, config: 'Config') -> List[str]:
        """
        Get the list of available models for this provider.
        
        Args:
            config: Configuration object
            
        Returns:
            List of model names/IDs available for this provider
        """
        pass
    
    @abstractmethod
    def get_api_key_name(self) -> str:
        """
        Get the configuration key name for the API key/URL.
        
        Returns:
            Configuration key name (e.g., 'GEMINI_API_KEY', 'OLLAMA_BASE_URL')
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: 'Config') -> Tuple[bool, Optional[str]]:
        """
        Validate that the provider configuration is correct.
        
        Args:
            config: Configuration object to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if configuration is valid
            - error_message: Error message if invalid, None if valid
        """
        pass
    
    @abstractmethod
    def get_api_key(self, config: 'Config', default_url: Optional[str] = None) -> Optional[str]:
        """
        Get the API key or base URL for this provider.
        
        Args:
            config: Configuration object
            default_url: Optional default URL (used for Ollama)
            
        Returns:
            API key or base URL, or None if not configured
        """
        pass
    
    @abstractmethod
    def check_dependencies(self) -> Tuple[bool, str]:
        """
        Check if required dependencies are installed for this provider.
        
        Returns:
            Tuple of (is_installed, error_message)
            - is_installed: True if dependencies are installed
            - error_message: Installation instructions if not installed
        """
        pass
    
    @abstractmethod
    def supports_image_context(self, config: 'Config', model_name: Optional[str] = None) -> bool:
        """
        Check if the provider/model supports image context.
        
        Args:
            config: Configuration object
            model_name: Optional model name to check
            
        Returns:
            True if image context is supported
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get provider-specific capabilities and limits.
        
        Returns:
            Dictionary of capabilities (e.g., payload_max_size_kb, xml_max_len)
        """
        pass
    
    def __str__(self) -> str:
        """Return string representation."""
        return self.name
    
    def __repr__(self) -> str:
        """Return developer representation."""
        return f"{self.__class__.__name__}(provider={self.provider})"

