"""
Central Ollama models cache utilities usable by both UI and CLI.

This module provides:
- Dynamic discovery of installed Ollama models
- Model metadata normalization and caching
- Vision capability detection
- Background refresh support

Requirements:
- Ollama service must be running
- ollama Python package must be installed
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def get_ollama_cache_path() -> str:
    """Determine the full path to the Ollama models cache file."""
    # Use the traverser_ai_api directory as the base
    traverser_ai_api_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(traverser_ai_api_dir, "output_data", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file_path = os.path.join(cache_dir, "ollama_models.json")
    return cache_file_path


def normalize_ollama_model(model_info: Dict[str, Any], base_url: Optional[str] = None) -> Dict[str, Any]:
    """Normalize a single Ollama model for cache storage.
    
    Args:
        model_info: Raw model info from Ollama API (can be dict or object with attributes)
        base_url: Optional base URL for the Ollama instance
        
    Returns:
        Normalized model dictionary
    """
    # Handle both dict and object formats
    if hasattr(model_info, 'model'):
        model_name = model_info.model
        modified_at = getattr(model_info, 'modified_at', '')
        model_dict = {
            'model': model_name,
            'name': getattr(model_info, 'name', model_name),
            'size': getattr(model_info, 'size', 0),
            'digest': getattr(model_info, 'digest', ''),
            'modified_at': modified_at,
        }
    else:
        model_dict = model_info.copy()
        model_name = model_dict.get('model') or model_dict.get('name', '')
        modified_at = model_dict.get('modified_at', '')
    
    # Convert datetime to string if present
    if isinstance(modified_at, datetime):
        modified_at_str = modified_at.isoformat()
    elif modified_at:
        modified_at_str = str(modified_at)
    else:
        modified_at_str = ''
    
    # Extract base name for feature detection
    base_name = model_name.split(':')[0] if model_name else ''
    
    # Detect vision support using name patterns
    vision_supported = is_ollama_model_vision(model_name)
    
    # Build normalized model
    normalized = {
        "id": model_name,
        "name": model_name,
        "base_name": base_name,
        "description": f"Ollama model: {base_name}",
        "vision_supported": vision_supported,
        "size": model_dict.get('size', 0),
        "digest": model_dict.get('digest', ''),
        "modified_at": modified_at_str,
        "base_url": base_url or "http://localhost:11434",
        "provider": "ollama",
        "online": False,  # Ollama models are always local
    }
    
    return normalized


def is_ollama_model_vision(model_name: str) -> bool:
    """Determine if an Ollama model supports vision based on name patterns.
    
    Args:
        model_name: The model name to check
        
    Returns:
        True if the model likely supports vision, False otherwise
    """
    if not model_name:
        return False
    
    base_name = model_name.split(':')[0].lower()
    
    # Common vision model patterns
    vision_patterns = [
        "vision",
        "llava",
        "bakllava",
        "minicpm-v",
        "moondream",
        "gemma2",
        "qwen2.5vl",
        "qwen-vl",
        "llama3.2-vision",
        "llama3.1-vision",
        "llama3-vision",
    ]
    
    return any(pattern in base_name for pattern in vision_patterns)


def fetch_ollama_models(base_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch installed models directly from Ollama.
    
    Args:
        base_url: Optional base URL for Ollama (defaults to localhost:11434)
        
    Returns:
        List of normalized model dictionaries
        
    Raises:
        ImportError: If ollama package is not installed
        RuntimeError: If Ollama service is not available
    """
    try:
        import ollama
    except ImportError:
        raise ImportError("Ollama Python package not installed. Run: pip install ollama")
    
    # Set base URL if provided
    if base_url:
        os.environ['OLLAMA_HOST'] = base_url
    
    try:
        # Fetch models from Ollama
        response = ollama.list()
        
        # Handle different response formats
        models_list = []
        if hasattr(response, 'models'):
            # New SDK format (v0.5.0+)
            models_list = response.models
        elif isinstance(response, dict) and 'models' in response:
            # Dict format
            models_list = response['models']
        elif isinstance(response, list):
            # Direct list format
            models_list = response
        else:
            logger.warning(f"Unexpected Ollama response format: {type(response)}")
            return []
        
        if not models_list:
            logger.info("No Ollama models found")
            return []
        
        # Normalize all models
        normalized_models = []
        for model_info in models_list:
            try:
                normalized = normalize_ollama_model(model_info, base_url)
                normalized_models.append(normalized)
            except Exception as e:
                logger.warning(f"Failed to normalize model {model_info}: {e}")
                continue
        
        logger.info(f"Fetched {len(normalized_models)} Ollama models")
        return normalized_models
        
    except ConnectionError as e:
        # Clean error message for connection issues
        error_msg = str(e)
        raise RuntimeError(error_msg) from None
    except Exception as e:
        error_msg = f"Failed to fetch Ollama models: {e}"
        raise RuntimeError(error_msg) from None


def save_ollama_models_to_cache(models: List[Dict[str, Any]]) -> None:
    """Write normalized model list to cache with schema v1 and index mapping."""
    try:
        cache_path = get_ollama_cache_path()
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
        logger.info(f"Ollama cache saved with schema v1; models: {len(models)}")
    except Exception as e:
        logger.error(f"Failed to save Ollama cache: {e}", exc_info=True)
        import traceback
        traceback.print_exc()


def background_refresh_ollama_models(
    base_url: Optional[str] = None,
    wait_for_completion: bool = False
) -> Tuple[bool, Optional[str]]:
    """Start a background thread to refresh Ollama models cache.
    
    Args:
        base_url: Optional base URL for Ollama
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
                result = _worker(base_url)
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
            with LoadingIndicator("Refreshing Ollama models"):
                completion_event.wait(timeout=20)  # 20 second timeout
            if completion_event.is_set():
                if not success_flag["success"] and error_ref["error"]:
                    # Re-raise the error so it can be caught by the service layer
                    raise error_ref["error"]
                return success_flag["success"], cache_path_ref.get("cache_path")
            else:
                # Timeout occurred - raise an error with clear message
                raise RuntimeError(
                    "Refresh timed out after 20 seconds. "
                    "Please check that Ollama is running and accessible. "
                    "https://ollama.com/download"
                )
        
        return True, None
    
    except Exception as e:
        # Re-raise to be caught by service layer
        raise


def _worker(base_url: Optional[str] = None) -> Optional[str]:
    """Background thread worker for refreshing Ollama models.
    
    Args:
        base_url: Optional base URL for Ollama
        
    Returns:
        Cache path if successful, None on error
        
    Raises:
        Exception: Re-raises any exception that occurs during fetch
    """
    models = fetch_ollama_models(base_url)
    
    if not models:
        logger.warning("No Ollama models found during refresh")
        return None
    
    cache_path = get_ollama_cache_path()
    save_ollama_models_to_cache(models)
    return cache_path


def load_ollama_models_cache() -> Optional[List[Dict[str, Any]]]:
    """Load and return the list of models from cache.
    
    Note: Unlike OpenRouter, Ollama models are always fetched fresh since they
    can change frequently (users can pull/remove models). Cache is mainly for
    offline access or performance.
    
    Returns:
        List of model dicts if cache exists, None otherwise
    """
    try:
        cache_path = get_ollama_cache_path()
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
        logger.debug(f"Failed to read Ollama cache: {e}")
        return None


def get_ollama_model_meta(model_id: str) -> Optional[Dict[str, Any]]:
    """Lookup a model's metadata by id from the cache.
    
    Args:
        model_id: The model ID to look up
        
    Returns:
        Model metadata dict if found, None otherwise
    """
    try:
        cache_path = get_ollama_cache_path()
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


def refresh_ollama_models_sync(base_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Synchronously refresh Ollama models cache.
    
    Args:
        base_url: Optional base URL for Ollama
        
    Returns:
        Tuple of (success, cache_path)
    """
    return background_refresh_ollama_models(base_url, wait_for_completion=True)

