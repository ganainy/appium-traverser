#!/usr/bin/env python3
"""
Gemini service for managing AI model selection and metadata.
"""

import logging
from typing import Dict, List, Optional, Tuple

from cli.shared.context import CLIContext
from cli.constants import keys as K
from cli.constants import messages as MSG


class GeminiService:
    """Service for managing Gemini AI models."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def refresh_models(self, wait_for_completion: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
        """Refresh Gemini models cache.
        
        Args:
            wait_for_completion: Whether to wait for completion
            
        Returns:
            Tuple of (success, cache_path, error_message) where:
            - success: bool indicating if operation succeeded
            - cache_path: path to saved cache file if successful, None otherwise
            - error_message: error message if failed, None otherwise
        """
        try:
            from domain.gemini_models import background_refresh_gemini_models, get_gemini_api_key
        except ImportError as e:
            error_msg = MSG.ERR_GEMINI_IMPORT_FAILED.format(error=e)
            return False, None, error_msg
        
        try:
            api_key = get_gemini_api_key()
            if wait_for_completion:
                from utils import LoadingIndicator
                with LoadingIndicator("Refreshing Gemini models"):
                    success, cache_path = background_refresh_gemini_models(
                        api_key=api_key,
                        wait_for_completion=wait_for_completion
                    )
            else:
                success, cache_path = background_refresh_gemini_models(
                    api_key=api_key,
                    wait_for_completion=wait_for_completion
                )
            if success and cache_path:
                self.logger.info(
                    MSG.SUCCESS_GEMINI_MODELS_REFRESHED.format(cache_path=cache_path)
                )
                return True, cache_path, None
            elif not success:
                error_msg = "Failed to refresh Gemini models cache"
                return False, None, error_msg
            else:
                # Background refresh started but not completed yet
                return True, None, None
        except RuntimeError as e:
            error_msg = str(e)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Error refreshing Gemini models: {e}"
            return False, None, error_msg
    
    def list_models(self, refresh: bool = False) -> Tuple[bool, Optional[List[Dict]]]:
        """List available Gemini models.
        
        Args:
            refresh: If True, refresh the cache before listing
            
        Returns:
            Tuple of (success, models_list)
        """
        try:
            from domain.gemini_models import (
                fetch_gemini_models,
                load_gemini_models_cache,
                save_gemini_models_to_cache,
                get_gemini_api_key
            )
        except ImportError as e:
            self.logger.error(MSG.ERR_GEMINI_IMPORT_FAILED.format(error=e))
            return False, None
        
        # If refresh requested, fetch fresh models
        if refresh:
            try:
                from utils import LoadingIndicator
                api_key = get_gemini_api_key()
                with LoadingIndicator("Fetching Gemini models"):
                    models = fetch_gemini_models(api_key)
                if models:
                    save_gemini_models_to_cache(models)
                return True, models if models else []
            except Exception as e:
                self.logger.error(f"Failed to refresh Gemini models: {e}")
                # Fall back to cache
                pass
        
        # Try to load from cache first
        models = load_gemini_models_cache()
        
        # If no cache, try to fetch fresh
        if not models:
            try:
                from utils import LoadingIndicator
                api_key = get_gemini_api_key()
                with LoadingIndicator("Fetching Gemini models"):
                    models = fetch_gemini_models(api_key)
                if models:
                    save_gemini_models_to_cache(models)
            except Exception as e:
                self.logger.error(f"Failed to fetch Gemini models: {e}")
                return False, None
        
        if not models:
            self.logger.error(MSG.ERR_GEMINI_MODELS_NOT_FOUND)
            return False, None
        
        return True, models
    
    def select_model(self, model_identifier: str) -> Tuple[bool, Dict]:
        """Select a Gemini model.
        
        Args:
            model_identifier: Model index (1-based) or name/ID fragment
            
        Returns:
            Tuple of (success, data_dict) where data_dict contains:
            - success: bool (same as first element)
            - model: dict (selected model data)
            - error: str (error message if failed)
        """
        try:
            from domain.gemini_models import get_gemini_model_meta
        except ImportError as e:
            self.logger.error(MSG.ERR_GEMINI_IMPORT_FAILED.format(error=e))
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_GEMINI_IMPORT_FAILED.format(error=e)}
        
        success, models = self.list_models()
        if not success or not models:
            self.logger.error(MSG.ERR_GEMINI_MODELS_NOT_FOUND)
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_GEMINI_MODELS_NOT_FOUND}
        
        try:
            selected_model = None
            
            # Try to find by index first
            try:
                index = int(model_identifier) - 1
                if 0 <= index < len(models):
                    selected_model = models[index]
            except ValueError:
                # Not a number, try to find by name/ID
                model_identifier_lower = model_identifier.lower()
                for model in models:
                    model_id = str(model.get("id", "")).lower()
                    model_name = str(model.get("name", "")).lower()
                    display_name = str(model.get("display_name", "")).lower()
                    if (model_identifier_lower in model_id or 
                        model_identifier_lower in model_name or
                        model_identifier_lower in display_name):
                        selected_model = model
                        break
            
            if not selected_model:
                return False, {
                    K.KEY_SUCCESS: False,
                    K.KEY_ERROR: MSG.ERR_GEMINI_MODEL_NOT_FOUND.format(model_identifier=model_identifier)
                }
            
            # Store selected model in config
            model_id = selected_model.get("id") or selected_model.get("name")
            self.context.config.set(K.CONFIG_DEFAULT_MODEL_TYPE, model_id)
            self.context.config.set(K.CONFIG_AI_PROVIDER, K.AI_PROVIDER_GEMINI)
            
            # Ensure provider is set in the model dict
            if "provider" not in selected_model:
                selected_model["provider"] = "gemini"
            
            return True, {
                K.KEY_SUCCESS: True,
                K.KEY_MODEL: selected_model,
                K.MODEL_ID: model_id,
                K.MODEL_NAME: selected_model.get("display_name") or selected_model.get("name") or model_id
            }
            
        except Exception as e:
            self.logger.error(f"Error selecting Gemini model: {e}", exc_info=True)
            return False, {
                K.KEY_SUCCESS: False,
                K.KEY_ERROR: MSG.ERR_GEMINI_SELECT_MODEL_FAILED.format(error=str(e))
            }
    
    def get_selected_model(self) -> Optional[Dict]:
        """Get the currently selected Gemini model.
        
        Returns:
            Model metadata dict if found, None otherwise
        """
        current_provider = self.context.config.get(K.CONFIG_AI_PROVIDER, "")
        if current_provider.lower() != K.AI_PROVIDER_GEMINI:
            return None
        
        current_model = self.context.config.get(K.CONFIG_DEFAULT_MODEL_TYPE, "")
        if not current_model or current_model == K.CONFIG_NO_MODEL_SELECTED:
            return None
        
        try:
            from domain.gemini_models import get_gemini_model_meta
        except ImportError:
            return None
        
        return get_gemini_model_meta(current_model)
    
    def show_model_details(self, model_identifier: Optional[str] = None) -> Tuple[bool, Optional[Dict]]:
        """Show detailed information about a Gemini model.
        
        Args:
            model_identifier: Model ID (uses current if None)
            
        Returns:
            Tuple of (success, data_dict) where data_dict contains:
            - success: bool (same as first element)
            - model: dict (model details)
            - vision_supported: bool (whether model supports vision)
            - error: str (error message if failed)
            - model_identifier: str (model ID if error)
        """
        current_provider = self.context.config.get(K.CONFIG_AI_PROVIDER, "")
        if current_provider.lower() != K.AI_PROVIDER_GEMINI:
            return False, {
                K.KEY_SUCCESS: False,
                K.KEY_ERROR: MSG.ERR_GEMINI_NOT_SELECTED_PROVIDER
            }
        
        # Get the current model if none specified
        if not model_identifier:
            model_identifier = self.context.config.get(K.CONFIG_DEFAULT_MODEL_TYPE, "")
            if not model_identifier or model_identifier == K.CONFIG_NO_MODEL_SELECTED:
                return False, {
                    K.KEY_SUCCESS: False,
                    K.KEY_ERROR: MSG.ERR_GEMINI_NO_MODEL_SELECTED
                }
        
        # Get model metadata
        try:
            from domain.gemini_models import get_gemini_model_meta
        except ImportError as e:
            self.logger.error(MSG.ERR_GEMINI_IMPORT_FAILED.format(error=e))
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_GEMINI_IMPORT_FAILED.format(error=e)}
        
        selected_model = get_gemini_model_meta(model_identifier)
        
        # If not in cache, try to fetch fresh
        if not selected_model:
            success, models = self.list_models(refresh=True)
            if success and models:
                for model in models:
                    if (str(model.get("id")) == str(model_identifier) or
                        str(model.get("name")) == str(model_identifier) or
                        str(model.get("display_name")) == str(model_identifier)):
                        selected_model = model
                        break
        
        if not selected_model:
            return False, {
                K.KEY_SUCCESS: False,
                K.KEY_ERROR: MSG.ERR_GEMINI_MODEL_NOT_IN_CACHE.format(model_identifier=model_identifier),
                K.KEY_MODEL_IDENTIFIER: model_identifier
            }
        
        # Ensure provider is set in the model dict
        if "provider" not in selected_model:
            selected_model["provider"] = "gemini"
        
        # Get additional information for presentation
        vision_supported = selected_model.get("vision_supported", False)
        
        # Return data for presentation layer
        data = {
            K.KEY_SUCCESS: True,
            K.KEY_MODEL: selected_model,
            "vision_supported": vision_supported,
        }
        
        return True, data

