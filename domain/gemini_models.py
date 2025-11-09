"""
Central Gemini models cache utilities usable by both UI and CLI.

This module provides:
- Dynamic discovery of available Gemini models via Google API
- Model metadata normalization and caching
- Vision capability detection
- Background refresh support

"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


def get_gemini_cache_path() -> str:
    """Determine the full path to the Gemini models cache file."""
    # Use the traverser_ai_api directory as the base
    traverser_ai_api_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(traverser_ai_api_dir, "output_data", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file_path = os.path.join(cache_dir, "gemini_models.json")
    return cache_file_path


def get_gemini_api_key() -> Optional[str]:
    """Get Gemini API key from environment or config."""
    # Try environment variable first
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key
    
    # Try config
    try:
        from config.config import Config
        config = Config()
        api_key = config.get("GEMINI_API_KEY")
        if api_key:
            return api_key
    except Exception:
        pass
    
    return None


def normalize_gemini_model(model_data: Dict[str, Any]) -> Dict[str, Any]:
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


def fetch_gemini_models(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch available models from Google Gemini API.
    
    Args:
        api_key: Optional API key (uses get_gemini_api_key() if not provided)
        
    Returns:
        List of normalized model dictionaries
        
    Raises:
        ImportError: If requests package is not installed
        RuntimeError: If API call fails or API key is missing
    """
    if api_key is None:
        api_key = get_gemini_api_key()
    
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. Set it as an environment variable or in config."
        )
    
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models"
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
                normalized = normalize_gemini_model(model_data)
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


def save_gemini_models_to_cache(models: List[Dict[str, Any]]) -> None:
    """Write normalized model list to cache with schema v1 and index mapping."""
    try:
        cache_path = get_gemini_cache_path()
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


def background_refresh_gemini_models(
    api_key: Optional[str] = None,
    wait_for_completion: bool = False
) -> Tuple[bool, Optional[str]]:
    """Start a background thread to refresh Gemini models cache.
    
    Args:
        api_key: Optional API key (uses get_gemini_api_key() if not provided)
        wait_for_completion: If True, wait for the refresh to complete before returning
        
    Returns:
        Tuple of (success, cache_path) where cache_path is the path to the saved cache file
    """
    try:
        completion_event = threading.Event()
        success_flag = {"success": False}
        cache_path_ref: Dict[str, Optional[str]] = {"cache_path": None}
        error_ref: Dict[str, Optional[Exception]] = {"error": None}
        
        def worker_with_event():
            try:
                result = _worker(api_key)
                success_flag["success"] = True
                if result is not None:
                    cache_path_ref["cache_path"] = result
                completion_event.set()
                return result
            except Exception as e:
                error_ref["error"] = e
                success_flag["success"] = False
                completion_event.set()
                # Don't re-raise, just store the error
        
        thread = threading.Thread(target=worker_with_event, daemon=not wait_for_completion)
        thread.start()
        
        if wait_for_completion:
            from utils import LoadingIndicator
            with LoadingIndicator("Refreshing Gemini models"):
                completion_event.wait(timeout=30)  # 30 second timeout
            if completion_event.is_set():
                if not success_flag["success"] and error_ref["error"]:
                    # Re-raise the error so it can be caught by the service layer
                    raise error_ref["error"]
                return success_flag["success"], cache_path_ref.get("cache_path")
            else:
                # Timeout occurred - raise an error with clear message
                raise RuntimeError(
                    "Refresh timed out after 30 seconds. "
                    "Please check your internet connection and GEMINI_API_KEY."
                )
        
        return True, None
    
    except Exception as e:
        # Re-raise to be caught by service layer
        raise


def _worker(api_key: Optional[str] = None) -> Optional[str]:
    """Background thread worker for refreshing Gemini models.
    
    Args:
        api_key: Optional API key
        
    Returns:
        Cache path if successful, None on error
        
    Raises:
        Exception: Re-raises any exception that occurs during fetch
    """
    models = fetch_gemini_models(api_key)
    
    if not models:
        logger.warning("No Gemini models found during refresh")
        return None
    
    cache_path = get_gemini_cache_path()
    save_gemini_models_to_cache(models)
    return cache_path


def load_gemini_models_cache() -> Optional[List[Dict[str, Any]]]:
    """Load and return the list of models from cache.
    
    Returns:
        List of model dicts if cache exists, None otherwise
    """
    try:
        cache_path = get_gemini_cache_path()
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


def get_gemini_model_meta(model_id: str) -> Optional[Dict[str, Any]]:
    """Lookup a model's metadata by id from the cache.
    
    Args:
        model_id: The model ID to look up
        
    Returns:
        Model metadata dict if found, None otherwise
    """
    try:
        cache_path = get_gemini_cache_path()
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


def refresh_gemini_models_sync(api_key: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Synchronously refresh Gemini models cache.
    
    Args:
        api_key: Optional API key
        
    Returns:
        Tuple of (success, cache_path)
    """
    return background_refresh_gemini_models(api_key, wait_for_completion=True)

