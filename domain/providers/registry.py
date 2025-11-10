"""
Provider registry for managing provider strategy instances.

This module implements the Registry pattern to centralize provider management
and eliminate the need for if/else chains throughout the codebase.
"""

from typing import Dict, Optional

from domain.providers.base import ProviderStrategy
from domain.providers.enums import AIProvider
from domain.providers.gemini_provider import GeminiProvider
from domain.providers.openrouter_provider import OpenRouterProvider
from domain.providers.ollama_provider import OllamaProvider


class ProviderRegistry:
    """
    Registry for managing AI provider strategies.
    
    This class provides a centralized way to register and retrieve provider
    strategies, eliminating the need for provider-specific if/else chains.
    """
    
    _providers: Dict[AIProvider, ProviderStrategy] = {}
    _initialized = False
    
    @classmethod
    def _initialize(cls):
        """Initialize the registry with default providers."""
        if cls._initialized:
            return
        
        # Register default providers
        cls.register(AIProvider.GEMINI, GeminiProvider())
        cls.register(AIProvider.OPENROUTER, OpenRouterProvider())
        cls.register(AIProvider.OLLAMA, OllamaProvider())
        
        cls._initialized = True
    
    @classmethod
    def register(cls, provider: AIProvider, strategy: ProviderStrategy):
        """
        Register a provider strategy.
        
        Args:
            provider: The AIProvider enum value
            strategy: The ProviderStrategy instance
        """
        cls._providers[provider] = strategy
    
    @classmethod
    def get(cls, provider: AIProvider) -> Optional[ProviderStrategy]:
        """
        Get a provider strategy by enum value.
        
        Args:
            provider: The AIProvider enum value
            
        Returns:
            ProviderStrategy instance, or None if not found
        """
        cls._initialize()
        return cls._providers.get(provider)
    
    @classmethod
    def get_by_name(cls, provider_name: str) -> Optional[ProviderStrategy]:
        """
        Get a provider strategy by name string.
        
        Args:
            provider_name: Provider name as string (e.g., "gemini", "openrouter")
            
        Returns:
            ProviderStrategy instance, or None if not found
        """
        try:
            provider = AIProvider.from_string(provider_name)
            return cls.get(provider)
        except ValueError:
            return None
    
    @classmethod
    def get_all(cls) -> Dict[AIProvider, ProviderStrategy]:
        """
        Get all registered providers.
        
        Returns:
            Dictionary mapping AIProvider to ProviderStrategy
        """
        cls._initialize()
        return cls._providers.copy()
    
    @classmethod
    def is_registered(cls, provider: AIProvider) -> bool:
        """
        Check if a provider is registered.
        
        Args:
            provider: The AIProvider enum value
            
        Returns:
            True if registered, False otherwise
        """
        cls._initialize()
        return provider in cls._providers
    
    @classmethod
    def get_all_names(cls) -> list[str]:
        """
        Get all registered provider names.
        
        Returns:
            List of provider name strings
        """
        cls._initialize()
        return [p.value for p in cls._providers.keys()]

