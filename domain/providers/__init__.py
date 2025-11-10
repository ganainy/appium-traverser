"""
Provider abstraction module for AI providers.

This module provides a unified interface for working with different AI providers
(gemini, openrouter, ollama) using the Strategy pattern and Registry pattern.
"""

from domain.providers.enums import AIProvider
from domain.providers.registry import ProviderRegistry
from domain.providers.base import ProviderStrategy
from domain.providers.gemini_provider import GeminiProvider
from domain.providers.openrouter_provider import OpenRouterProvider
from domain.providers.ollama_provider import OllamaProvider

__all__ = [
    'AIProvider',
    'ProviderRegistry',
    'ProviderStrategy',
    'GeminiProvider',
    'OpenRouterProvider',
    'OllamaProvider',
]

