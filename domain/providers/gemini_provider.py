"""
Gemini provider strategy implementation.

This module contains all Gemini-specific logic including model fetching,
caching, and metadata management.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from config.app_config import Config

from domain.providers.base import ProviderStrategy
from domain.providers.enums import AIProvider
from config.app_config import AI_PROVIDER_CAPABILITIES

logger = logging.getLogger(__name__)


class GeminiProvider(ProviderStrategy):
    """Provider strategy for Google Gemini."""
    
    def __init__(self):
        super().__init__(AIProvider.GEMINI)
    
    @property
    def name(self) -> str:
        return "gemini"
    
    # ========== Cache Management ==========
    
    def _get_cache_path(self) -> str:
        """Determine the full path to the Gemini models cache file."""
        # Use the traverser_ai_api directory as the base
        traverser_ai_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_dir = os.path.join(traverser_ai_api_dir, "output_data", "cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file_path = os.path.join(cache_dir, "gemini_models.json")
        return cache_file_path
    
    def _load_models_cache(self) -> Optional[List[Dict[str, Any]]]:
        """Load and return the list of models from cache.
        
        Returns:
            List of model dicts if cache exists, None otherwise
        """
        try:
            cache_path = self._get_cache_path()
            if not os.path.exists(cache_path):
                return None
            
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # New schema: { schema_version, timestamp, models, index }
            if isinstance(data, dict) and data.get("schema_version") and isinstance(data.get("models"), list):
                models = data.get("models")
                return models if models else None
            
            return None
        except Exception as e:
            logger.debug(f"Failed to read Gemini cache: {e}")
            return None
    
    def _save_models_to_cache(self, models: List[Dict[str, Any]]) -> None:
        """Write normalized model list to cache with schema v1 and index mapping."""
        try:
            cache_path = self._get_cache_path()
            # Build index mapping for fast lookup
            index: Dict[str, int] = {}
            for i, m in enumerate(models):
                model_id = m.get("id") or m.get("name")
                if model_id:
                    index[str(model_id)] = i
            payload = {
                "schema_version": 1,
                "timestamp": int(time.time()),
                "models": models,
                "index": index,
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info(f"Gemini cache saved with schema v1; models: {len(models)}")
        except Exception as e:
            logger.error(f"Failed to save Gemini cache: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
    
    # ========== Model Normalization ==========
    
    def _normalize_model(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single Gemini model for cache storage.
        
        Args:
            model_data: Raw model data from Google API
            
        Returns:
            Normalized model dictionary
        """
        model_name = model_data.get("name", "")
        # Extract model ID from name (e.g., "models/gemini-1.5-pro" -> "gemini-1.5-pro")
        model_id = model_name.replace("models/", "") if model_name.startswith("models/") else model_name
        
        # Detect vision support
        # Check model name patterns first (most reliable)
        model_id_lower = model_id.lower()
        vision_supported = (
            "gemini-1.5" in model_id_lower or 
            "gemini-pro-vision" in model_id_lower or
            "vision" in model_id_lower
        )
        
        # Also check supported methods and description if name pattern didn't match
        if not vision_supported:
            supported_methods = model_data.get("supportedGenerationMethods", [])
            # If generateContent is supported, check description for vision indicators
            if "generateContent" in supported_methods:
                description = model_data.get("description", "").lower()
                if "vision" in description or "image" in description or "multimodal" in description:
                    vision_supported = True
        else:
            supported_methods = model_data.get("supportedGenerationMethods", [])
        
        # Get context window
        input_token_limit = model_data.get("inputTokenLimit", 0)
        output_token_limit = model_data.get("outputTokenLimit", 0)
        
        # Get display name
        display_name = model_data.get("displayName", model_id)
        description = model_data.get("description", f"Gemini model: {model_id}")
        
        normalized = {
            "id": model_id,
            "name": model_id,
            "display_name": display_name,
            "description": description,
            "vision_supported": vision_supported,
            "input_token_limit": input_token_limit,
            "output_token_limit": output_token_limit,
            "supported_methods": supported_methods,
            "provider": "gemini",
            "online": True,  # Gemini models are always online
        }
        
        return normalized
    
    # ========== Model Fetching ==========
    
    def _fetch_models(self, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch available models from Google Gemini API.
        
        Args:
            api_key: Optional API key (uses get_api_key() if not provided)
            
        Returns:
            List of normalized model dictionaries
            
        Raises:
            ImportError: If requests package is not installed
            RuntimeError: If API call fails or API key is missing
        """
        if api_key is None:
            # Try to get from config if available
            try:
                from config.app_config import Config
                config = Config()
                api_key = config.get("GEMINI_API_KEY")
            except Exception:
                pass
            
            # Try environment variable
            if not api_key:
                api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not found. Set it as an environment variable or in config."
            )
        
        try:
            from config.urls import ServiceURLs
            url = ServiceURLs.get_gemini_models_url()
            params = {"key": api_key}
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            models_list = data.get("models", [])
            
            if not models_list:
                logger.info("No Gemini models found in API response")
                return []
            
            # Normalize all models
            normalized_models = []
            for model_data in models_list:
                try:
                    normalized = self._normalize_model(model_data)
                    normalized_models.append(normalized)
                except Exception as e:
                    logger.warning(f"Failed to normalize model {model_data}: {e}")
                    continue
            
            logger.info(f"Fetched {len(normalized_models)} Gemini models")
            return normalized_models
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch Gemini models: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from None
        except Exception as e:
            error_msg = f"Unexpected error fetching Gemini models: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from None
    
    # ========== ProviderStrategy Interface ==========
    
    def get_models(self, config: 'Config') -> List[str]:
        """Get available Gemini models from cache or API."""
        models = []
        
        # Try to load from cache first
        try:
            cached_models = self._load_models_cache()
            if cached_models:
                for model in cached_models:
                    model_id = model.get("id") or model.get("name")
                    if model_id:
                        models.append(model_id)
        except Exception:
            pass
        
        # If no cache, try to fetch fresh (if API key is available)
        if not models:
            try:
                api_key = self.get_api_key(config) or os.environ.get("GEMINI_API_KEY")
                if api_key:
                    fetched_models = self._fetch_models(api_key)
                    if fetched_models:
                        self._save_models_to_cache(fetched_models)
                        for model in fetched_models:
                            model_id = model.get("id") or model.get("name")
                            if model_id:
                                models.append(model_id)
            except Exception:
                pass
        
        return models
    
    def get_api_key_name(self) -> str:
        return "GEMINI_API_KEY"
    
    def validate_config(self, config: 'Config') -> Tuple[bool, Optional[str]]:
        """Validate Gemini configuration."""
        api_key = self.get_api_key(config)
        if not api_key:
            return False, "GEMINI_API_KEY is not set in configuration"
        return True, None
    
    def get_api_key(self, config: 'Config', default_url: Optional[str] = None) -> Optional[str]:
        """Get Gemini API key from config or environment."""
        # Try config first
        api_key = config.get("GEMINI_API_KEY")
        if api_key:
            return api_key
        
        # Fallback to environment variable
        return os.environ.get("GEMINI_API_KEY")
    
    def check_dependencies(self) -> Tuple[bool, str]:
        """Check if Google Generative AI SDK is installed."""
        try:
            import google.generativeai
            return True, ""
        except ImportError:
            return False, "Google Generative AI Python SDK not installed. Run: pip install google-generativeai"
    
    def supports_image_context(self, config: 'Config', model_name: Optional[str] = None) -> bool:
        """Check if Gemini model supports image context."""
        if model_name:
            # Check model metadata for vision support
            model_meta = self.get_model_meta(model_name)
            if model_meta:
                return model_meta.get("vision_supported", True)  # Default to True for Gemini
        return True  # Gemini generally supports image context
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get Gemini provider capabilities."""
        return AI_PROVIDER_CAPABILITIES.get("gemini", {})
    
    # ========== Extended API for Services ==========
    
    def get_models_full(self, config: 'Config', refresh: bool = False) -> Tuple[bool, Optional[List[Dict[str, Any]]]]:
        """Get full model metadata (not just IDs).
        
        Args:
            config: Configuration object
            refresh: If True, refresh the cache before listing
            
        Returns:
            Tuple of (success, models_list) where models_list contains full model dicts
        """
        # If refresh requested, fetch fresh models
        if refresh:
            try:
                api_key = self.get_api_key(config) or os.environ.get("GEMINI_API_KEY")
                if api_key:
                    models = self._fetch_models(api_key)
                    if models:
                        self._save_models_to_cache(models)
                        return True, models if models else []
            except Exception as e:
                logger.error(f"Failed to refresh Gemini models: {e}")
                # Fall back to cache
                pass
        
        # Try to load from cache first
        models = self._load_models_cache()
        
        # If no cache, try to fetch fresh
        if not models:
            try:
                api_key = self.get_api_key(config) or os.environ.get("GEMINI_API_KEY")
                if api_key:
                    models = self._fetch_models(api_key)
                    if models:
                        self._save_models_to_cache(models)
            except Exception as e:
                logger.error(f"Failed to fetch Gemini models: {e}")
                return False, None
        
        if not models:
            return False, None
        
        return True, models
    
    def get_model_meta(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Lookup a model's metadata by id from the cache.
        
        Args:
            model_id: The model ID to look up
            
        Returns:
            Model metadata dict if found, None otherwise
        """
        try:
            cache_path = self._get_cache_path()
            if not os.path.exists(cache_path):
                return None
            
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if isinstance(data, dict) and data.get("schema_version") and isinstance(data.get("models"), list):
                index = data.get("index") or {}
                models = data.get("models") or []
                i = index.get(str(model_id))
                if isinstance(i, int) and 0 <= i < len(models):
                    return models[i]
                # Fallback linear search
                for m in models:
                    if str(m.get("id")) == str(model_id) or str(m.get("name")) == str(model_id):
                        return m
                return None
            
            return None
        except Exception as e:
            logger.debug(f"Failed to lookup model meta: {e}")
            return None
    
    def refresh_models(self, config: 'Config', wait_for_completion: bool = False) -> Tuple[bool, Optional[str]]:
        """Refresh Gemini models cache.
        
        Args:
            config: Configuration object
            wait_for_completion: If True, wait for the refresh to complete before returning
            
        Returns:
            Tuple of (success, cache_path) where cache_path is the path to the saved cache file
        """
        def refresh_logic():
            api_key = self.get_api_key(config) or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not found for refresh")
            
            models = self._fetch_models(api_key)
            
            if not models:
                logger.warning("No Gemini models found during refresh")
                return None
            
            cache_path = self._get_cache_path()
            self._save_models_to_cache(models)
            return cache_path

        if wait_for_completion:
            try:
                cache_path = refresh_logic()
                return True, cache_path
            except Exception as e:
                logger.error(f"Failed to refresh Gemini models synchronously: {e}", exc_info=True)
                raise
        else:
            def background_worker():
                try:
                    refresh_logic()
                except Exception as e:
                    logger.error(f"Background refresh for Gemini failed: {e}", exc_info=True)
            
            thread = threading.Thread(target=background_worker, daemon=True)
            thread.start()
            return True, None
