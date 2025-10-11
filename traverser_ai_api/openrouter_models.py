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
from typing import Any, Dict, List, Optional


def get_openrouter_cache_path() -> str:
    """Return the cache path used to store OpenRouter models.

    Matches the path used by UI components: traverser_ai_api/output_data/cache/openrouter_models.json
    """
    base_dir = os.path.dirname(__file__)  # traverser_ai_api
    cache_dir = os.path.join(base_dir, "output_data", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "openrouter_models.json")


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
        logging.debug(f"Failed to save OpenRouter cache: {e}")


def background_refresh_openrouter_models() -> None:
    """Queue a background refresh that fetches and saves models to cache.

    This mirrors UIComponents._background_refresh_openrouter_models but is UI-agnostic.
    """
    def _worker():
        try:
            # Load API key via Config to respect .env
            try:
                from .config import Config
            except ImportError:
                from config import Config  # fallback
            cfg = Config()
            api_key = getattr(cfg, "OPENROUTER_API_KEY", None)
            if not api_key:
                logging.warning("OpenRouter refresh requested but API key is missing.")
                return
            import requests
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            resp = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=20)
            if resp.status_code != 200:
                logging.warning(f"OpenRouter API returned HTTP {resp.status_code}")
                return
            data = resp.json()
            models = data.get("data") or data.get("models") or []
            normalized: List[Dict[str, Any]] = []
            for m in models:
                mid = m.get("id") or m.get("name")
                if not mid:
                    continue
                name = m.get("name") or m.get("canonical_slug") or str(mid)
                architecture = m.get("architecture") or {}
                input_modalities = architecture.get("input_modalities") or []
                output_modalities = architecture.get("output_modalities") or []
                supported_parameters = m.get("supported_parameters") or []
                pricing = m.get("pricing") if isinstance(m.get("pricing"), dict) else None
                top_provider = m.get("top_provider") if isinstance(m.get("top_provider"), dict) else None
                context_length = (
                    m.get("context_length")
                    or (top_provider or {}).get("context_length")
                )
                supports_image = "image" in (input_modalities or [])

                def _pricing_is_free(p: Any) -> bool:
                    try:
                        if isinstance(p, dict):
                            for v in p.values():
                                if isinstance(v, (int, float)) and v == 0:
                                    return True
                                if isinstance(v, str) and ("free" in v.lower() or "$0" in v or v.strip() == "0"):
                                    return True
                                if isinstance(v, dict):
                                    for vv in v.values():
                                        if isinstance(vv, (int, float)) and vv == 0:
                                            return True
                                        if isinstance(vv, str) and ("free" in vv.lower() or "$0" in vv or vv.strip() == "0"):
                                            return True
                        return False
                    except Exception:
                        return False

                is_free = _pricing_is_free(pricing) or ("(free" in name.lower()) or (str(mid).lower().endswith(":free"))
                supports_tools = "tools" in supported_parameters
                supports_structured_outputs = "structured_outputs" in supported_parameters or "response_format" in supported_parameters
                entry = {
                    "id": mid,
                    "name": name,
                    "canonical_slug": m.get("canonical_slug"),
                    "created": m.get("created") or m.get("created_at"),
                    "description": m.get("description"),
                    "context_length": context_length,
                    "architecture": {
                        "input_modalities": input_modalities,
                        "output_modalities": output_modalities,
                        "tokenizer": architecture.get("tokenizer"),
                        "instruct_type": architecture.get("instruct_type"),
                    },
                    "supported_parameters": supported_parameters,
                    "pricing": pricing,
                    "top_provider": top_provider,
                    "per_request_limits": m.get("per_request_limits"),
                    "supports_image": supports_image,
                    "is_free": is_free,
                    "supports_tools": supports_tools,
                    "supports_structured_outputs": supports_structured_outputs,
                }
                normalized.append(entry)
            if normalized:
                save_openrouter_models_to_cache(normalized)
        except Exception as e:
            logging.debug(f"Background OpenRouter refresh failed: {e}")

    try:
        threading.Thread(target=_worker, daemon=True).start()
    except Exception as e:
        logging.debug(f"Failed to start background refresh thread: {e}")