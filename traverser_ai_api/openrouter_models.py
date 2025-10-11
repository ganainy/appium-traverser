"""
Central OpenRouter models cache utilities usable by both UI and CLI.

This module reuses the existing logic from UIComponents to:
- Determine the cache path
- Save normalized model metadata
- Refresh the cache from OpenRouter API (background thread)

Requirements:
- OPENROUTER_API_KEY must be available via traverser_ai_api.config.Config
"""

import os
import json
import time
import threading
import logging
import requests
from typing import Any, Dict, List, Optional


def get_openrouter_cache_path() -> str:
    """Determine the full path to the OpenRouter models cache file."""
    # Use the traverser_ai_api directory as the base
    traverser_ai_api_dir = os.path.dirname(os.path.abspath(__file__))
    logging.debug(f"Traverser AI API Dir: {traverser_ai_api_dir}")
    cache_dir = os.path.join(traverser_ai_api_dir, "output_data", "cache")
    logging.debug(f"Cache Dir: {cache_dir}")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file_path = os.path.join(cache_dir, "openrouter_models.json")
    logging.debug(f"Cache File Path: {cache_file_path}")
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
        logging.debug(f"Saving OpenRouter models to: {cache_path}")
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
        logging.debug(f"Successfully wrote {len(models)} models to cache.")
    except Exception as e:
        logging.debug(f"Failed to save OpenRouter cache: {e}", exc_info=True)
        logging.debug(f"ERROR saving to cache: {e}")
        import traceback
        traceback.print_exc()


def background_refresh_openrouter_models(wait_for_completion: bool = False) -> bool:
    """Start a background thread to refresh OpenRouter models cache.
    
    Args:
        wait_for_completion: If True, wait for the refresh to complete before returning
        
    Returns:
        True if successful (or if background thread started), False on error
    """
    try:
        logging.debug("Starting background OpenRouter refresh thread")
        completion_event = threading.Event()
        success_flag = {"success": False}
        
        def worker_with_event():
            try:
                result = _worker()
                success_flag["success"] = True
                completion_event.set()
                return result
            except Exception as e:
                logging.error(f"Background worker failed: {e}", exc_info=True)
                success_flag["success"] = False
                completion_event.set()
                raise
        
        thread = threading.Thread(target=worker_with_event, daemon=not wait_for_completion)
        thread.start()
        logging.debug("Background thread started successfully")
        
        if wait_for_completion:
            logging.debug("Waiting for background refresh to complete...")
            completion_event.wait(timeout=30)  # 30 second timeout
            if completion_event.is_set():
                logging.debug("Background refresh completed")
                return success_flag["success"]
            else:
                logging.warning("Background refresh timed out after 30 seconds")
                return False
        
        return True
        
    except Exception as e:
        logging.debug(f"Failed to start background refresh thread: {e}")
        return False
def _worker() -> bool:
    """Background thread worker for refreshing OpenRouter models.
    
    Returns:
        True if successful, False on error
    """
    try:
        logging.debug("_worker() thread started")
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logging.debug("ERROR - No OPENROUTER_API_KEY found in environment")
            logging.warning("No OPENROUTER_API_KEY found for background refresh")
            return False
        logging.debug(f"Found API key (length: {len(api_key)})")
        
        url = "https://openrouter.ai/api/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        logging.debug(f"Making request to {url}")
        
        # Use a longer timeout for background refresh
        response = requests.get(url, headers=headers, timeout=60)
        logging.debug(f"Response status code: {response.status_code}")
        
        if response.status_code != 200:
            logging.debug(f"ERROR - Non-200 response: {response.status_code}")
            logging.warning(f"Non-200 response from OpenRouter: {response.status_code}")
            return False
        
        data = response.json()
        models = data.get("data", [])
        logging.debug(f"Received {len(models)} models from API")
        
        if not models:
            logging.debug("ERROR - No models received from API")
            logging.warning("No models received from OpenRouter API")
            return False
        
        # Normalize and add metadata
        normalized_models = []
        for model in models:
            normalized = normalize_openrouter_model(model)
            normalized_models.append(normalized)
        
        logging.debug(f"Normalized {len(normalized_models)} models")
        logging.debug("Calling save_openrouter_models_to_cache()")
        save_openrouter_models_to_cache(normalized_models)
        logging.debug("_worker() completed successfully")
        return True
        
    except Exception as e:
        logging.debug(f"ERROR in _worker(): {e}")
        logging.error(f"Error in background OpenRouter refresh: {e}", exc_info=True)
        return False