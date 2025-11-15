"""
OpenRouter provider strategy implementation.

This module contains all OpenRouter-specific logic including model fetching,
caching, vision detection, free model detection, and metadata management.
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


class OpenRouterProvider(ProviderStrategy):
    """Provider strategy for OpenRouter."""
    
    def __init__(self):
        super().__init__(AIProvider.OPENROUTER)
    
    @property
    def name(self) -> str:
        return "openrouter"
    
    # ========== Cache Management ==========
    
    def _get_cache_path(self) -> str:
        """Determine the full path to the OpenRouter models cache file."""
        # Use the traverser_ai_api directory as the base
        traverser_ai_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_dir = os.path.join(traverser_ai_api_dir, "output_data", "cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file_path = os.path.join(cache_dir, "openrouter_models.json")
        return cache_file_path
    
    def _load_models_cache(self) -> Optional[List[Dict[str, Any]]]:
        """Load and return the list of models from cache, respecting TTL and triggering background refresh if needed.
        
        Returns:
            List of model dicts if cache exists and valid, None otherwise
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
                # TTL check: if cache older than 24h, queue background refresh
                try:
                    ttl_seconds = 24 * 3600
                    ts = int(data.get("timestamp") or 0)
                    if ts and (int(time.time()) - ts) > ttl_seconds:
                        logger.info("OpenRouter model cache older than 24h; queuing background refresh.")
                        # Start background refresh but don't wait
                        self.refresh_models(None, wait_for_completion=False)
                except Exception as e:
                    logger.debug(f"TTL check failed: {e}")
                return models if models else None
            
            return None
        except Exception as e:
            logger.debug(f"Failed to read OpenRouter cache: {e}")
            return None
    
    def _save_models_to_cache(self, models: List[Dict[str, Any]]) -> None:
        """Write normalized model list to cache with schema v1 and index mapping."""
        try:
            cache_path = self._get_cache_path()
            # Build index mapping for fast lookup
            index: Dict[str, int] = {}
            for i, m in enumerate(models):
                mid = m.get("id") or m.get("name")
                if mid:
                    index[str(mid)] = i
            payload = {
                "schema_version": 1,
                "timestamp": int(time.time()),
                "models": models,
                "index": index,
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info(f"OpenRouter cache saved with schema v1; models: {len(models)}")
        except Exception as e:
            logger.error(f"Failed to save OpenRouter cache: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
    
    # ========== Model Normalization ==========
    
    def _normalize_model(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single OpenRouter model for cache storage."""
        normalized = {
            "id": model.get("id", ""),
            "name": model.get("name", ""),
            "description": model.get("description", ""),
            "context_length": model.get("context_length", 0),
            "pricing": model.get("pricing", {}),
            "top_provider": model.get("top_provider", {}),
            "per_request_limits": model.get("per_request_limits", {}),
            "architecture": model.get("architecture", {}),
            "capabilities": model.get("capabilities", [])
        }
        
        # Extract supports_image from capabilities
        capabilities = normalized.get("capabilities", [])
        if isinstance(capabilities, list):
            normalized["supports_image"] = "image" in capabilities
        else:
            # Fallback: check architecture
            arch = normalized.get("architecture", {})
            if isinstance(arch, dict):
                input_modalities = arch.get("input_modalities", [])
                normalized["supports_image"] = "image" in input_modalities if isinstance(input_modalities, list) else False
            else:
                normalized["supports_image"] = None
        
        return normalized
    
    # ========== Model Fetching ==========
    
    def _fetch_models(self, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch available models from OpenRouter API.
        
        Args:
            api_key: Optional API key (uses get_api_key() if not provided)
            
        Returns:
            List of normalized model dictionaries
            
        Raises:
            RuntimeError: If API call fails or API key is missing
        """
        if api_key is None:
            # Try to get from config if available
            try:
                from config.app_config import Config
                config = Config()
                api_key = config.get("OPENROUTER_API_KEY")
            except Exception:
                pass
            
            # Try environment variable
            if not api_key:
                api_key = os.environ.get("OPENROUTER_API_KEY")
        
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not found. Set it as an environment variable or in config."
            )
        
        try:
            from config.urls import ServiceURLs
            url = ServiceURLs.get_openrouter_models_url()
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            models = data.get("data", [])
            
            if not models:
                logger.info("No models received from OpenRouter API")
                return []
            
            # Normalize all models
            normalized_models = []
            for model in models:
                try:
                    normalized = self._normalize_model(model)
                    normalized_models.append(normalized)
                except Exception as e:
                    logger.warning(f"Failed to normalize model {model}: {e}")
                    continue
            
            logger.info(f"Fetched {len(normalized_models)} OpenRouter models")
            return normalized_models
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch OpenRouter models: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from None
        except Exception as e:
            error_msg = f"Unexpected error fetching OpenRouter models: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from None
    
    # ========== Model Metadata Helpers ==========
    
    def is_model_free(self, model_meta: Any) -> bool:
        """Determine free status strictly using prompt/completion/image pricing and known indicators.
        
        Args:
            model_meta: Either a model metadata dict or a model name/id string
            
        Returns:
            True if the model is free, False otherwise
        """
        try:
            def _val_is_zero(v: Any) -> bool:
                try:
                    if isinstance(v, (int, float)):
                        return v == 0
                    if isinstance(v, str):
                        s = v.strip().lower()
                        return s == "0" or s == "$0" or "free" in s
                    return False
                except Exception:
                    return False

            # Accept either dict meta or name string
            if isinstance(model_meta, dict):
                pricing = model_meta.get("pricing") if isinstance(model_meta.get("pricing"), dict) else None
                supports_image = bool(model_meta.get("supports_image"))
                if not supports_image:
                    # Try to infer supports_image from architecture if flag missing
                    try:
                        arch = model_meta.get("architecture") or {}
                        supports_image = "image" in (arch.get("input_modalities") or [])
                    except Exception:
                        supports_image = False
                prompt_zero = _val_is_zero((pricing or {}).get("prompt"))
                completion_zero = _val_is_zero((pricing or {}).get("completion"))
                image_zero = _val_is_zero((pricing or {}).get("image"))
                if prompt_zero and completion_zero and (not supports_image or image_zero):
                    return True
                # Fallback to name/id indicators
                name = (model_meta.get("name") or "").lower()
                mid = (model_meta.get("id") or "").lower()
                return "(free" in name or mid.endswith(":free")
            # If just a name string
            name_str = str(model_meta).lower()
            return "(free" in name_str or name_str.endswith(":free")
        except Exception:
            return False
    
    def is_model_vision(self, model_id: str) -> bool:
        """Determine vision support using cache metadata; fallback to heuristics.
        
        Args:
            model_id: The model ID to check
            
        Returns:
            True if the model supports vision, False otherwise
        """
        if not model_id:
            return False
        try:
            meta = self.get_model_meta(model_id)
            if isinstance(meta, dict) and "supports_image" in meta:
                return bool(meta.get("supports_image"))
        except Exception:
            pass
        # Fallback to name-based heuristics
        mid = str(model_id).lower()
        patterns = [
            "vision",
            "vl",
            "gpt-4o",
            "gpt-4.1",
            "o-mini",
            "omni",
            "llava",
            "qwen-vl",
            "minicpm-v",
            "moondream",
            "gemma3",
            "image",
        ]
        return any(p in mid for p in patterns)
    
    # ========== ProviderStrategy Interface ==========
    
    def get_models(self, config: 'Config') -> List[str]:
        """Get available OpenRouter models from cache, optionally filtered by free-only setting.
        
        Returns empty list if cache load fails (no fallback presets).
        """
        models = []
        free_only = config.get("OPENROUTER_SHOW_FREE_ONLY", False)
        
        try:
            cached_models = self._load_models_cache()
            if cached_models:
                for model in cached_models:
                    model_id = model.get("id") or model.get("name")
                    if not model_id:
                        continue
                    
                    # Apply free-only filter if enabled
                    if free_only:
                        if not self.is_model_free(model):
                            continue
                    
                    models.append(model_id)
        except Exception:
            pass
        
        # Only return models if we successfully loaded from cache
        # No fallback presets - return empty list if cache load failed
        return models
    
    def get_api_key_name(self) -> str:
        return "OPENROUTER_API_KEY"
    
    def validate_config(self, config: 'Config') -> Tuple[bool, Optional[str]]:
        """Validate OpenRouter configuration."""
        api_key = self.get_api_key(config)
        if not api_key:
            return False, "OPENROUTER_API_KEY is not set in configuration"
        return True, None
    
    def get_api_key(self, config: 'Config', default_url: Optional[str] = None) -> Optional[str]:
        """Get OpenRouter API key from config or environment."""
        # Try config first
        api_key = config.get("OPENROUTER_API_KEY")
        if api_key:
            return api_key
        
        # Fallback to environment variable
        return os.environ.get("OPENROUTER_API_KEY")
    
    def check_dependencies(self) -> Tuple[bool, str]:
        """Check if OpenAI SDK is installed (used by OpenRouter)."""
        try:
            __import__('openai')
            return True, ""
        except ImportError:
            return False, "OpenAI Python SDK not installed. Run: pip install openai"
    
    def supports_image_context(self, config: 'Config', model_name: Optional[str] = None) -> bool:
        """Check if OpenRouter model supports image context."""
        if model_name:
            meta = self.get_model_meta(model_name)
            if meta and isinstance(meta, dict):
                supports_image = meta.get("supports_image")
                if supports_image is not None:
                    return bool(supports_image)
            # Fallback to heuristic
            return self.is_model_vision(model_name)
        return True  # Default to True
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get OpenRouter provider capabilities."""
        return AI_PROVIDER_CAPABILITIES.get("openrouter", {})
    
    # ========== Extended API for Services ==========
    
    def get_models_full(self, config: 'Config', free_only: bool = False, all_models: bool = False) -> Tuple[bool, Optional[List[Dict[str, Any]]]]:
        """Get full model metadata (not just IDs).
        
        Args:
            config: Configuration object
            free_only: If True, only show free models
            all_models: If True, show all models (ignores OPENROUTER_SHOW_FREE_ONLY config)
            
        Returns:
            Tuple of (success, models_list) where models_list contains full model dicts
        """
        models = self._load_models_cache()
        
        if not models:
            return False, None
        
        # Determine if we should filter to free-only models
        should_filter_free = free_only
        if not should_filter_free and not all_models:
            # Use config setting only if neither free_only nor all_models is specified
            should_filter_free = config.get("OPENROUTER_SHOW_FREE_ONLY", False)
        
        # Filter models if should_filter_free is True
        if should_filter_free:
            filtered_models = [m for m in models if self.is_model_free(m)]
            if not filtered_models:
                return False, None
            return True, filtered_models
        else:
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
                    if str(m.get("id")) == str(model_id):
                        return m
                return None
            
            return None
        except Exception as e:
            logger.debug(f"Failed to lookup model meta: {e}")
            return None
    
    def refresh_models(self, config: Optional['Config'], wait_for_completion: bool = False) -> Tuple[bool, Optional[str]]:
        """Refresh OpenRouter models cache.
        
        Args:
            config: Configuration object (optional, will try to get API key from env/config)
            wait_for_completion: If True, wait for the refresh to complete before returning
            
        Returns:
            Tuple of (success, cache_path) where cache_path is the path to the saved cache file
        """
        def refresh_logic():
            # Get API key from config or environment
            api_key = None
            if config:
                api_key = self.get_api_key(config)
            if not api_key:
                api_key = os.environ.get("OPENROUTER_API_KEY")
            
            if not api_key:
                raise RuntimeError("No OPENROUTER_API_KEY found for refresh")
            
            models = self._fetch_models(api_key)
            
            if not models:
                logger.warning("No models received from OpenRouter API")
                return None
            
            cache_path = self._get_cache_path()
            self._save_models_to_cache(models)
            return cache_path

        if wait_for_completion:
            try:
                cache_path = refresh_logic()
                return True, cache_path
            except Exception as e:
                logger.error(f"Failed to refresh OpenRouter models synchronously: {e}", exc_info=True)
                raise  # Re-raise the exception to be handled by the caller
        else:
            # Run in a background thread for non-blocking refresh
            def background_worker():
                try:
                    refresh_logic()
                except Exception as e:
                    logger.error(f"Background refresh for OpenRouter failed: {e}", exc_info=True)
            
            thread = threading.Thread(target=background_worker, daemon=True)
            thread.start()
            return True, None
