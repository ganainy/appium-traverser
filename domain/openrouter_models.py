"""
Central OpenRouter models cache utilities usable by both UI and CLI.

This module reuses the existing logic from UIComponents to:
- Determine the cache path
- Save normalized model metadata
- Refresh the cache from OpenRouter API (background thread)

Requirements:
- OPENROUTER_API_KEY must be available via config.config.Config
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


def get_openrouter_cache_path() -> str:
    """Determine the full path to the OpenRouter models cache file."""
    # Use the traverser_ai_api directory as the base
    traverser_ai_api_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(traverser_ai_api_dir, "output_data", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file_path = os.path.join(cache_dir, "openrouter_models.json")
    return cache_file_path


def normalize_openrouter_model(model: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single OpenRouter model for cache storage."""
    return {
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


def save_openrouter_models_to_cache(models: List[Dict[str, Any]]) -> None:
    """Write normalized model list to cache with schema v1 and index mapping."""
    try:
        cache_path = get_openrouter_cache_path()
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
        logging.info(f"OpenRouter cache saved with schema v1; models: {len(models)}")
    except Exception as e:
        logging.error(f"Failed to save OpenRouter cache: {e}", exc_info=True)
        import traceback
        traceback.print_exc()


def background_refresh_openrouter_models(wait_for_completion: bool = False) -> Tuple[bool, Optional[str]]:
    """Start a background thread to refresh OpenRouter models cache.
    
    Args:
        wait_for_completion: If True, wait for the refresh to complete before returning
        
    Returns:
        True if successful (or if background thread started), False on error
    """
    try:
        completion_event = threading.Event()
        success_flag = {"success": False}
        cache_path_ref: Dict[str, Optional[str]] = {"cache_path": None}
        
        def worker_with_event():
            try:
                result = _worker()
                success_flag["success"] = True
                if result is not None:
                    cache_path_ref["cache_path"] = result
                completion_event.set()
                return result
            except Exception as e:
                logging.error(f"Background worker failed: {e}", exc_info=True)
                success_flag["success"] = False
                completion_event.set()
                raise
        
        thread = threading.Thread(target=worker_with_event, daemon=not wait_for_completion)
        thread.start()
        
        if wait_for_completion:
            from utils import LoadingIndicator
            with LoadingIndicator("Refreshing OpenRouter models"):
                completion_event.wait(timeout=30)  # 30 second timeout
            if completion_event.is_set():
                return success_flag["success"], cache_path_ref.get("cache_path")
            else:
                logging.warning("Background refresh timed out after 30 seconds")
                return False, None
        
        return True, None
    
    except Exception as e:
        logging.error(f"Failed to start background refresh thread: {e}", exc_info=True)
        return False, None
def _worker() -> Optional[str]:
    """Background thread worker for refreshing OpenRouter models.
    
    Returns:
        Cache path if successful, None on error
    """
    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logging.warning("No OPENROUTER_API_KEY found for background refresh")
            return None

        url = "https://openrouter.ai/api/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Use a longer timeout for background refresh
        response = requests.get(url, headers=headers, timeout=60)

        if response.status_code != 200:
            logging.warning(f"Non-200 response from OpenRouter: {response.status_code}")
            return None

        data = response.json()
        models = data.get("data", [])

        if not models:
            logging.warning("No models received from OpenRouter API")
            return None
        
        # Normalize and add metadata
        normalized_models = []
        for model in models:
            normalized = normalize_openrouter_model(model)
            normalized_models.append(normalized)
        
        cache_path = get_openrouter_cache_path()
        save_openrouter_models_to_cache(normalized_models)
        return cache_path

    except Exception as e:
        logging.error(f"Error in background OpenRouter refresh: {e}", exc_info=True)
        return None


def load_openrouter_models_cache() -> Optional[List[Dict[str, Any]]]:
    """Load and return the list of models from cache, respecting TTL and triggering background refresh if needed.
    
    Returns:
        List of model dicts if cache exists and valid, None otherwise
    """
    try:
        cache_path = get_openrouter_cache_path()
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
                    logging.info("OpenRouter model cache older than 24h; queuing background refresh.")
                    background_refresh_openrouter_models()
            except Exception as e:
                logging.debug(f"TTL check failed: {e}")
            return models if models else None
        
        return None
    except Exception as e:
        logging.debug(f"Failed to read OpenRouter cache: {e}")
        return None


def get_openrouter_model_meta(model_id: str) -> Optional[Dict[str, Any]]:
    """Lookup a model's metadata by id from the cache.
    
    Args:
        model_id: The model ID to look up
        
    Returns:
        Model metadata dict if found, None otherwise
    """
    try:
        cache_path = get_openrouter_cache_path()
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
        logging.debug(f"Failed to lookup model meta: {e}")
        return None


def is_openrouter_model_free(model_meta: Any) -> bool:
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


def is_openrouter_model_vision(model_id: str) -> bool:
    """Determine vision support using cache metadata; fallback to heuristics.
    
    Args:
        model_id: The model ID to check
        
    Returns:
        True if the model supports vision, False otherwise
    """
    if not model_id:
        return False
    try:
        meta = get_openrouter_model_meta(model_id)
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
