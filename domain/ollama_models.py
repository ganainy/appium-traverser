"""
Central Ollama models cache utilities usable by both UI and CLI.

This module provides:
- Dynamic discovery of installed Ollama models
- Model metadata normalization and caching
- Vision capability detection (shared across codebase)
- Background refresh support

Requirements:
- Ollama service must be running
- ollama Python package must be installed

This module handles model discovery and metadata. For runtime model
interaction (inference), see domain/model_adapters.py.
"""

import json
import logging
import os
import subprocess
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
    
    # Detect vision support using hybrid approach (metadata → CLI → patterns)
    # Pass base_url to enable metadata/CLI checks with custom Ollama instances
    vision_supported = is_ollama_model_vision(model_name, base_url=base_url)
    
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


def _check_vision_via_sdk_metadata(model_name: str, base_url: Optional[str] = None) -> Optional[bool]:
    """Check vision support via Ollama SDK metadata inspection.
    
    Attempts to inspect model metadata through the Ollama Python SDK to detect
    vision capabilities by looking for architecture indicators like projector or CLIP.
    
    Args:
        model_name: The model name to check
        base_url: Optional base URL for Ollama instance
        
    Returns:
        True if vision is detected, False if confirmed no vision, None if unable to determine
    """
    if not model_name:
        return None
    
    try:
        import ollama
    except ImportError:
        logger.debug("Ollama SDK not available for metadata inspection")
        return None
    
    try:
        # Set base URL if provided
        original_host = os.environ.get('OLLAMA_HOST')
        if base_url:
            os.environ['OLLAMA_HOST'] = base_url
        
        try:
            # Try to get model info - this may not be available in all SDK versions
            # Some SDK versions expose model details through show() or inspect methods
            # For now, we'll try to access any available metadata
            
            # Note: The Ollama Python SDK may not expose detailed architecture info
            # in all versions, so this is a best-effort attempt
            # Try different possible method names for different SDK versions
            response = None
            if hasattr(ollama, 'show'):
                response = ollama.show(model_name)
            elif hasattr(ollama, 'inspect'):
                response = ollama.inspect(model_name)
            else:
                logger.debug("Ollama SDK does not expose show() or inspect() methods")
                return None
            
            if response is None:
                return None
            
            # Check if response contains vision indicators
            if hasattr(response, 'modelfile'):
                modelfile = response.modelfile
                if isinstance(modelfile, str):
                    # Look for vision-related indicators in modelfile
                    modelfile_lower = modelfile.lower()
                    if any(indicator in modelfile_lower for indicator in ['projector', 'clip', 'vision', 'image']):
                        return True
            
            # Check response attributes for architecture info
            if hasattr(response, 'details'):
                details = response.details
                if isinstance(details, dict):
                    # Look for architecture or model family indicators
                    arch = details.get('architecture', '').lower()
                    family = details.get('family', '').lower()
                    if any(indicator in arch or indicator in family for indicator in ['clip', 'vision', 'multimodal']):
                        return True
            
            # Check for projector in any nested structure
            response_dict = response.__dict__ if hasattr(response, '__dict__') else {}
            response_str = str(response).lower()
            if 'projector' in response_str or 'clip' in response_str:
                return True
                
        except AttributeError:
            # SDK version may not support show() or inspect() methods
            logger.debug(f"Ollama SDK show()/inspect() methods not available for {model_name}")
        except Exception as e:
            logger.debug(f"Error inspecting SDK metadata for {model_name}: {e}")
        finally:
            # Restore original OLLAMA_HOST
            if base_url:
                if original_host:
                    os.environ['OLLAMA_HOST'] = original_host
                elif 'OLLAMA_HOST' in os.environ:
                    del os.environ['OLLAMA_HOST']
        
        return None
    except Exception as e:
        logger.debug(f"Failed to check vision via SDK metadata for {model_name}: {e}")
        return None


def _check_vision_via_cli(model_name: str, base_url: Optional[str] = None) -> Optional[bool]:
    """Check vision support via `ollama show` CLI command.
    
    Executes `ollama show <model-name>` and parses the output for vision indicators
    such as "projector", "CLIP", or other vision-related architecture references.
    
    Args:
        model_name: The model name to check
        base_url: Optional base URL for Ollama instance (sets OLLAMA_HOST env var)
        
    Returns:
        True if vision is detected, False if confirmed no vision, None if unable to determine
    """
    if not model_name:
        return None
    
    try:
        # Build command: ollama show <model-name>
        cmd = ['ollama', 'show', model_name]
        
        # Set up environment for custom base URL if provided
        env = os.environ.copy()
        if base_url:
            env['OLLAMA_HOST'] = base_url
        
        # Run command with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,  # 10 second timeout
            check=False,  # Don't raise on non-zero exit
            env=env,
        )
        
        if result.returncode != 0:
            logger.debug(f"`ollama show {model_name}` failed with exit code {result.returncode}")
            if result.stderr:
                logger.debug(f"Error output: {result.stderr}")
            return None
        
        output = result.stdout.lower()
        
        # Look for vision-related indicators in the output
        vision_indicators = [
            'projector',
            'clip',
            'vision encoder',
            'vision model',
            'multimodal',
            'image encoder',
        ]
        
        # Check if any vision indicator is present
        for indicator in vision_indicators:
            if indicator in output:
                logger.debug(f"Vision support detected for {model_name} via CLI (found '{indicator}')")
                return True
        
        # If we got output but no vision indicators, it's likely text-only
        # However, we can't be 100% certain, so return None to allow fallback
        return None
        
    except subprocess.TimeoutExpired:
        logger.debug(f"`ollama show {model_name}` timed out")
        return None
    except FileNotFoundError:
        logger.debug("`ollama` CLI command not found in PATH")
        return None
    except Exception as e:
        logger.debug(f"Error checking vision via CLI for {model_name}: {e}")
        return None


def _check_vision_via_patterns(model_name: str) -> bool:
    """Check vision support via name pattern matching (fallback method).
    
    Args:
        model_name: The model name to check
        
    Returns:
        True if the model name matches known vision patterns, False otherwise
    """
    if not model_name:
        return False
    
    base_name = model_name.split(':')[0].lower()
    
    # Common vision model patterns
    # Note: Using specific patterns (e.g., "llama3.2-vision") instead of generic "llama"
    # to avoid false positives on text-only llama models
    vision_patterns = [
        "vision",
        "llava",
        "bakllava",
        "minicpm-v",
        "moondream",
        "gemma2",
        "gemma3",  # Added: Gemma 3 vision models
        "qwen2.5vl",
        "qwen-vl",
        "llama3.2-vision",
        "llama3.1-vision",
        "llama3-vision",
        "mistral3",  # Added: Mistral 3 vision models
        "vl",  # Added: Generic vision-language indicator
    ]
    
    return any(pattern in base_name for pattern in vision_patterns)


def is_ollama_model_vision(
    model_name: str,
    base_url: Optional[str] = None,
    use_metadata: bool = True,
    use_cli: bool = True,
    use_patterns: bool = True
) -> bool:
    """Determine if an Ollama model supports vision using hybrid detection.
    
    Uses a multi-tier approach:
    1. Primary: Ollama SDK metadata inspection (if available)
    2. Secondary: `ollama show` CLI command parsing
    3. Fallback: Name pattern matching
    
    Args:
        model_name: The model name to check
        base_url: Optional base URL for Ollama instance
        use_metadata: Whether to attempt SDK metadata inspection (default: True)
        use_cli: Whether to attempt CLI command inspection (default: True)
        use_patterns: Whether to use pattern matching as fallback (default: True)
        
    Returns:
        True if the model supports vision, False otherwise
    """
    if not model_name:
        return False
    
    # Tier 1: Try SDK metadata inspection
    if use_metadata:
        result = _check_vision_via_sdk_metadata(model_name, base_url)
        if result is not None:
            logger.debug(f"Vision detection for {model_name} via SDK metadata: {result}")
            return result
    
    # Tier 2: Try CLI command inspection
    if use_cli:
        result = _check_vision_via_cli(model_name, base_url)
        if result is not None:
            logger.debug(f"Vision detection for {model_name} via CLI: {result}")
            return result
    
    # Tier 3: Fallback to pattern matching
    if use_patterns:
        result = _check_vision_via_patterns(model_name)
        logger.debug(f"Vision detection for {model_name} via patterns: {result}")
        return result
    
    # If all methods are disabled, default to False
    return False


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

