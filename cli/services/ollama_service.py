#!/usr/bin/env python3
"""
Ollama service for managing AI model selection and metadata.
"""

import logging
from typing import Dict, List, Optional, Tuple

from cli.shared.context import CLIContext
from cli.constants import keys as K
from cli.constants import messages as MSG


class OllamaService:
    """Service for managing Ollama AI models."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def refresh_models(self, wait_for_completion: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
        """Refresh Ollama models cache.
        
        Args:
            wait_for_completion: Whether to wait for completion
            
        Returns:
            Tuple of (success, cache_path, error_message) where:
            - success: bool indicating if operation succeeded
            - cache_path: path to saved cache file if successful, None otherwise
            - error_message: error message if failed, None otherwise
        """
        try:
            from domain.ollama_models import background_refresh_ollama_models
        except ImportError as e:
            error_msg = MSG.ERR_OLLAMA_IMPORT_FAILED.format(error=e)
            return False, None, error_msg
        
        try:
            base_url = self.context.config.get(K.CONFIG_OLLAMA_BASE_URL)
            success, cache_path = background_refresh_ollama_models(
                base_url=base_url,
                wait_for_completion=wait_for_completion
            )
            if success and cache_path:
                self.logger.info(
                    MSG.SUCCESS_OLLAMA_MODELS_REFRESHED.format(cache_path=cache_path)
                )
                return True, cache_path, None
            elif not success:
                # Refresh failed - get error message from domain layer
                error_msg = "Failed to refresh Ollama models cache"
                return False, None, error_msg
            else:
                # Background refresh started but not completed yet
                return True, None, None
        except RuntimeError as e:
            # Clean error message from domain layer
            error_msg = str(e)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Error refreshing Ollama models: {e}"
            return False, None, error_msg
    
    def list_models(self, refresh: bool = False) -> Tuple[bool, Optional[List[Dict]]]:
        """List available Ollama models.
        
        Args:
            refresh: If True, refresh the cache before listing
            
        Returns:
            Tuple of (success, models_list)
        """
        try:
            from domain.ollama_models import (
                fetch_ollama_models,
                load_ollama_models_cache,
                save_ollama_models_to_cache
            )
        except ImportError as e:
            self.logger.error(MSG.ERR_OLLAMA_IMPORT_FAILED.format(error=e))
            return False, None
        
        # If refresh requested, fetch fresh models
        if refresh:
            try:
                base_url = self.context.config.get(K.CONFIG_OLLAMA_BASE_URL)
                models = fetch_ollama_models(base_url)
                if models:
                    save_ollama_models_to_cache(models)
                return True, models if models else []
            except Exception as e:
                self.logger.error(f"Failed to refresh Ollama models: {e}")
                # Fall back to cache
                pass
        
        # Try to load from cache first
        models = load_ollama_models_cache()
        
        # If no cache, try to fetch fresh
        if not models:
            try:
                base_url = self.context.config.get(K.CONFIG_OLLAMA_BASE_URL)
                models = fetch_ollama_models(base_url)
                if models:
                    save_ollama_models_to_cache(models)
            except Exception as e:
                self.logger.error(f"Failed to fetch Ollama models: {e}")
                return False, None
        
        if not models:
            self.logger.error(MSG.ERR_OLLAMA_MODELS_NOT_FOUND)
            return False, None
        
        return True, models
    
    def select_model(self, model_identifier: str) -> Tuple[bool, Optional[Dict]]:
        """Select an Ollama model by index or name/ID fragment.
        
        Args:
            model_identifier: Model index (1-based) or name/ID fragment
            
        Returns:
            Tuple of (success, data_dict) where data_dict contains:
            - success: bool (same as first element)
            - model: dict (selected model data)
            - vision_supported: bool (whether model supports vision)
            - error: str (error message if failed)
        """
        try:
            from domain.ollama_models import is_ollama_model_vision
        except ImportError as e:
            self.logger.error(MSG.ERR_OLLAMA_IMPORT_FAILED.format(error=e))
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_OLLAMA_IMPORT_FAILED.format(error=e)}
        
        success, models = self.list_models()
        if not success or not models:
            self.logger.error(MSG.ERR_OLLAMA_MODELS_NOT_FOUND)
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_OLLAMA_MODELS_NOT_FOUND}
        
        try:
            selected_model = None
            
            # Try to find by index first
            try:
                index = int(model_identifier) - 1
                if 0 <= index < len(models):
                    selected_model = models[index]
            except ValueError:
                # Not an index, search by name or ID
                model_identifier_lower = model_identifier.lower()
                for model in models:
                    model_id = str(model.get(K.MODEL_ID, "")).lower()
                    model_name = str(model.get(K.MODEL_NAME, "")).lower()
                    base_name = str(model.get("base_name", "")).lower()
                    if (model_identifier_lower in model_id or 
                        model_identifier_lower in model_name or
                        model_identifier_lower in base_name):
                        selected_model = model
                        break
            
            if not selected_model:
                self.logger.error(MSG.ERR_OLLAMA_MODEL_NOT_FOUND.format(model_identifier=model_identifier))
                return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_OLLAMA_MODEL_NOT_FOUND.format(model_identifier=model_identifier)}
            
            model_id = selected_model.get(K.MODEL_ID)
            model_name = selected_model.get(K.MODEL_NAME)
            vision_supported = selected_model.get("vision_supported", False)
            
            # Save selection to config
            try:
                # Ensure provider is set to ollama
                self.context.config.set(K.CONFIG_AI_PROVIDER, K.AI_PROVIDER_OLLAMA)
                # Save the model ID
                self.context.config.set(K.CONFIG_DEFAULT_MODEL_TYPE, model_id)
                self.logger.info(f"Selected Ollama model '{model_id}' saved to config")
            except Exception as e:
                self.logger.warning(f"Failed to save model selection to config: {e}")
                # Continue anyway - selection still works for this session
            
            # Return data for presentation layer
            data = {
                K.KEY_SUCCESS: True,
                K.KEY_MODEL: selected_model,
                "vision_supported": vision_supported
            }
            
            return True, data
                
        except Exception as e:
            self.logger.error(MSG.ERR_OLLAMA_SELECT_MODEL_FAILED.format(error=e), exc_info=True)
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_OLLAMA_SELECT_MODEL_FAILED.format(error=e)}
    
    def get_selected_model(self) -> Optional[Dict]:
        """Get the currently selected Ollama model.
        
        Returns:
            Selected model dictionary or None
        """
        current_provider = self.context.config.get(K.CONFIG_AI_PROVIDER, "")
        current_model = self.context.config.get(K.CONFIG_DEFAULT_MODEL_TYPE, "")
        
        if current_provider.lower() != K.AI_PROVIDER_OLLAMA:
            return None
        
        try:
            from domain.ollama_models import get_ollama_model_meta
        except ImportError as e:
            self.logger.error(MSG.ERR_OLLAMA_IMPORT_FAILED.format(error=e))
            return None
        
        return get_ollama_model_meta(current_model)
    
    def show_model_details(self, model_identifier: Optional[str] = None) -> Tuple[bool, Optional[Dict]]:
        """Show detailed information about an Ollama model.
        
        Args:
            model_identifier: Model ID (uses current if None)
            
        Returns:
            Tuple of (success, data_dict) where data_dict contains:
            - success: bool (same as first element)
            - model: dict (model details)
            - vision_supported: bool (whether model supports vision)
            - current_image_context: bool (current image context setting)
            - error: str (error message if failed)
            - model_identifier: str (model ID if error)
        """
        current_provider = self.context.config.get(K.CONFIG_AI_PROVIDER, "")
        if current_provider.lower() != K.AI_PROVIDER_OLLAMA:
            return False, {
                K.KEY_SUCCESS: False,
                K.KEY_ERROR: MSG.ERR_OLLAMA_NOT_SELECTED_PROVIDER
            }
        
        # Get the current model if none specified
        if not model_identifier:
            model_identifier = self.context.config.get(K.CONFIG_DEFAULT_MODEL_TYPE, "")
            if not model_identifier or model_identifier == K.CONFIG_NO_MODEL_SELECTED:
                return False, {
                    K.KEY_SUCCESS: False,
                    K.KEY_ERROR: MSG.ERR_OLLAMA_NO_MODEL_SELECTED
                }
        
        # Get model metadata
        try:
            from domain.ollama_models import get_ollama_model_meta
        except ImportError as e:
            self.logger.error(MSG.ERR_OLLAMA_IMPORT_FAILED.format(error=e))
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_OLLAMA_IMPORT_FAILED.format(error=e)}
        
        selected_model = get_ollama_model_meta(model_identifier)
        
        # If not in cache, try to fetch fresh
        if not selected_model:
            success, models = self.list_models(refresh=True)
            if success and models:
                for model in models:
                    if (str(model.get(K.MODEL_ID)) == str(model_identifier) or
                        str(model.get(K.MODEL_NAME)) == str(model_identifier)):
                        selected_model = model
                        break
        
        if not selected_model:
            return False, {
                K.KEY_SUCCESS: False,
                K.KEY_ERROR: MSG.ERR_OLLAMA_MODEL_NOT_IN_CACHE.format(model_identifier=model_identifier),
                K.KEY_MODEL_IDENTIFIER: model_identifier
            }
        
        # Get additional information for presentation
        vision_supported = selected_model.get("vision_supported", False)
        current_image_context = self.context.config.get(K.CONFIG_ENABLE_IMAGE_CONTEXT, False)
        
        # Return data for presentation layer
        data = {
            K.KEY_SUCCESS: True,
            K.KEY_MODEL: selected_model,
            "vision_supported": vision_supported,
            K.KEY_CURRENT_IMAGE_CONTEXT: current_image_context
        }
        
        return True, data

