#!/usr/bin/env python3
"""
OpenRouter service for managing AI model selection and metadata.
"""

import logging
from typing import Dict, List, Optional, Tuple

from cli.shared.context import CLIContext
from cli.constants import keys as K
from cli.constants import messages as MSG


class OpenRouterService:
    """Service for managing OpenRouter AI models."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def refresh_models(self, wait_for_completion: bool = False) -> Tuple[bool, Optional[str]]:
        """Refresh OpenRouter models cache.
        
        Args:
            wait_for_completion: Whether to wait for completion
            
        Returns:
            Tuple of (success, cache_path) where cache_path is the path to the saved cache file
        """
        try:
            from domain.openrouter_models import background_refresh_openrouter_models
        except ImportError as e:
            self.logger.error(MSG.ERR_OPENROUTER_IMPORT_FAILED.format(error=e))
            return False, None
        
        try:
            if wait_for_completion:
                from utils import LoadingIndicator
                with LoadingIndicator("Refreshing OpenRouter models"):
                    success, cache_path = background_refresh_openrouter_models(wait_for_completion=wait_for_completion)
            else:
                success, cache_path = background_refresh_openrouter_models(wait_for_completion=wait_for_completion)
            if success and cache_path:
                self.logger.info(
                    MSG.SUCCESS_OPENROUTER_MODELS_REFRESHED.format(cache_path=cache_path)
                )
            else:
                self.logger.error(MSG.ERR_OPENROUTER_REFRESH_FAILED)
            return success, cache_path
        except Exception as e:
            self.logger.error(f"Error refreshing OpenRouter models: {e}", exc_info=True)
            return False, None
    
    def list_models(self, free_only: bool = False, all_models: bool = False) -> Tuple[bool, Optional[List[Dict]]]:
        """List available OpenRouter models.
        
        Args:
            free_only: If True, only show free models
            all_models: If True, show all models (ignores OPENROUTER_SHOW_FREE_ONLY config)
                      
        Returns:
            Tuple of (success, models_list)
        """
        try:
            from domain.openrouter_models import is_openrouter_model_free, load_openrouter_models_cache
        except ImportError as e:
            self.logger.error(MSG.ERR_OPENROUTER_IMPORT_FAILED.format(error=e))
            return False, None
        
        models = load_openrouter_models_cache()
        
        if not models:
            self.logger.error(MSG.ERR_OPENROUTER_MODELS_CACHE_NOT_FOUND)
            return False, None
        
        # Determine if we should filter to free-only models
        should_filter_free = free_only
        if not should_filter_free and not all_models:
            # Use config setting only if neither free_only nor all_models is specified
            should_filter_free = self.context.config.get(K.CONFIG_OPENROUTER_SHOW_FREE_ONLY, False)
        
        # Filter models if should_filter_free is True
        if should_filter_free:
            filtered_models = [m for m in models if is_openrouter_model_free(m)]
            if not filtered_models:
                self.logger.error("No free models found in cache. Run refresh to update.")
                return False, None
            return True, filtered_models
        else:
            return True, models
    
    def select_model(self, model_identifier: str) -> Tuple[bool, Optional[Dict]]:
        """Select an OpenRouter model by index or name/ID fragment.
        
        Args:
            model_identifier: Model index (1-based) or name/ID fragment
            
        Returns:
            Tuple of (success, data_dict) where data_dict contains:
            - success: bool (same as first element)
            - model: dict (selected model data)
            - is_free: bool (whether model is free)
            - show_warning: bool (whether to show warning)
            - error: str (error message if failed)
        """
        try:
            from domain.openrouter_models import is_openrouter_model_free, load_openrouter_models_cache
        except ImportError as e:
            self.logger.error(MSG.ERR_OPENROUTER_IMPORT_FAILED.format(error=e))
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_OPENROUTER_IMPORT_FAILED.format(error=e)}
        
        models = load_openrouter_models_cache()
        
        if not models:
            self.logger.error(MSG.ERR_OPENROUTER_MODELS_CACHE_NOT_FOUND)
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_OPENROUTER_MODELS_CACHE_NOT_FOUND}
        
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
                    model_id = model.get(K.MODEL_ID, "").lower()
                    model_name = model.get(K.MODEL_NAME, "").lower()
                    if model_identifier_lower in model_id or model_identifier_lower in model_name:
                        selected_model = model
                        break
            
            if not selected_model:
                self.logger.error(MSG.ERR_OPENROUTER_MODEL_NOT_FOUND.format(model_identifier=model_identifier))
                return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_OPENROUTER_MODEL_NOT_FOUND.format(model_identifier=model_identifier)}
            
            model_id = selected_model.get(K.MODEL_ID)
            model_name = selected_model.get(K.MODEL_NAME)
            
            # Check if this is a paid model and show warning if needed
            pricing = selected_model.get(K.MODEL_PRICING, {})
            prompt_price = pricing.get(K.MODEL_PROMPT_PRICE, "0")
            completion_price = pricing.get(K.MODEL_COMPLETION_PRICE, "0")
            
            # Show warning if this is a paid model and warnings are enabled
            show_warning = self.context.config.get(K.CONFIG_OPENROUTER_NON_FREE_WARNING, False)
            is_free = is_openrouter_model_free(selected_model)
            
            # Return data for presentation layer
            data = {
                K.KEY_SUCCESS: True,
                K.KEY_MODEL: selected_model,
                K.KEY_IS_FREE: is_free,
                K.KEY_SHOW_WARNING: not is_free and show_warning
            }
            
            return True, data
                
        except Exception as e:
            self.logger.error(MSG.ERR_OPENROUTER_SELECT_MODEL_FAILED.format(error=e), exc_info=True)
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_OPENROUTER_SELECT_MODEL_FAILED.format(error=e)}
    
    def get_selected_model(self) -> Optional[Dict]:
        """Get the currently selected OpenRouter model.
        
        Returns:
            Selected model dictionary or None
        """
        current_provider = self.context.config.get(K.CONFIG_AI_PROVIDER, "")
        current_model = self.context.config.get(K.CONFIG_DEFAULT_MODEL_TYPE, "")
        
        if current_provider.lower() != K.PROVIDER_OPENROUTER:
            return None
        
        try:
            from domain.openrouter_models import get_openrouter_model_meta
        except ImportError as e:
            self.logger.error(MSG.ERR_OPENROUTER_IMPORT_FAILED.format(error=e))
            return None
        
        return get_openrouter_model_meta(current_model)
    
    def configure_image_context(
        self,
        model_identifier: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> Tuple[bool, Optional[Dict]]:
        """Configure image context settings for OpenRouter models.
        
        Args:
            model_identifier: Model ID (uses current if None)
            enabled: Whether to enable image context (None to toggle/verify)
            
        Returns:
            Tuple of (success, data_dict) where data_dict contains:
            - success: bool (same as first element)
            - model_identifier: str (model ID)
            - model_name: str (model name)
            - supports_image: bool/None (image support capability)
            - current_setting: bool (current image context setting)
            - enabled: bool (new setting if changed)
            - action: str (action performed: "checked", "enabled", "disabled")
            - heuristic_supports_image: bool (heuristic result if supports_image is None)
            - error: str (error message if failed)
        """
        current_provider = self.context.config.get("AI_PROVIDER", "")
        if current_provider.lower() != "openrouter":
            return False, {
                "success": False,
                "error": "This command is only available when OpenRouter is selected as the AI provider."
            }
        
        # Get the current model if none specified
        if not model_identifier:
            model_identifier = self.context.config.get("DEFAULT_MODEL_TYPE", "")
            if not model_identifier or model_identifier == "No model selected":
                return False, {
                    "success": False,
                    "error": "No OpenRouter model selected. Use '--select-openrouter-model <model>' first."
                }
        
        # Get model metadata
        try:
            from domain.openrouter_models import get_openrouter_model_meta, is_openrouter_model_vision
        except ImportError as e:
            self.logger.error(f"Failed to import openrouter_models: {e}")
            return False, {"success": False, "error": f"Failed to import openrouter_models: {e}"}
        
        selected_model = get_openrouter_model_meta(model_identifier)
        
        if not selected_model:
            return False, {
                "success": False,
                "error": f"Model '{model_identifier}' not found in cache.",
                "model_identifier": model_identifier
            }
        
        # Check image support
        supports_image = selected_model.get(K.MODEL_SUPPORTS_IMAGE)
        model_name = selected_model.get(K.MODEL_NAME, K.DEFAULT_UNKNOWN)
        
        # Prepare base response data
        data = {
            K.KEY_SUCCESS: True,
            K.KEY_MODEL_IDENTIFIER: model_identifier,
            "model_name": model_name,
            K.KEY_SUPPORTS_IMAGE: supports_image
        }
        
        if supports_image is True:
            # Model supports images - allow user to choose
            if enabled is None:
                current_setting = self.context.config.get(K.CONFIG_ENABLE_IMAGE_CONTEXT, False)
                data.update({
                    K.KEY_CURRENT_SETTING: current_setting,
                    K.KEY_ACTION: "checked"
                })
                return True, data
            else:
                data.update({
                    K.KEY_ENABLED: enabled,
                    K.KEY_ACTION: "enabled" if enabled else "disabled"
                })
                return True, data
        elif supports_image is False:
            # Model doesn't support images - force disable
            data.update({
                K.KEY_ENABLED: False,
                K.KEY_ACTION: "disabled"
            })
            return True, data
        else:
            # Unknown capability - use heuristic
            heuristic = is_openrouter_model_vision(model_identifier)
            data[K.KEY_HEURISTIC_SUPPORTS_IMAGE] = heuristic
            
            if heuristic:
                if enabled is None:
                    current_setting = self.context.config.get(K.CONFIG_ENABLE_IMAGE_CONTEXT, False)
                    data.update({
                        K.KEY_CURRENT_SETTING: current_setting,
                        K.KEY_ACTION: "checked"
                    })
                    return True, data
                else:
                    data.update({
                        K.KEY_ENABLED: enabled,
                        K.KEY_ACTION: "enabled" if enabled else "disabled"
                    })
                    return True, data
            else:
                data.update({
                    K.KEY_ENABLED: False,
                    K.KEY_ACTION: "disabled"
                })
                return True, data
    
    def show_model_details(self, model_identifier: Optional[str] = None) -> Tuple[bool, Optional[Dict]]:
        """Show detailed information about an OpenRouter model.
        
        Args:
            model_identifier: Model ID (uses current if None)
            
        Returns:
            Tuple of (success, data_dict) where data_dict contains:
            - success: bool (same as first element)
            - model: dict (model details)
            - is_free: bool (whether model is free)
            - current_image_context: bool (current image context setting)
            - error: str (error message if failed)
            - model_identifier: str (model ID if error)
        """
        current_provider = self.context.config.get(K.CONFIG_AI_PROVIDER, "")
        if current_provider.lower() != K.PROVIDER_OPENROUTER:
            return False, {
                K.KEY_SUCCESS: False,
                K.KEY_ERROR: MSG.ERR_OPENROUTER_NOT_SELECTED_PROVIDER
            }
        
        # Get the current model if none specified
        if not model_identifier:
            model_identifier = self.context.config.get(K.CONFIG_DEFAULT_MODEL_TYPE, "")
            if not model_identifier or model_identifier == K.CONFIG_NO_MODEL_SELECTED:
                return False, {
                    K.KEY_SUCCESS: False,
                    K.KEY_ERROR: MSG.ERR_OPENROUTER_NO_MODEL_SELECTED
                }
        
        # Get model metadata
        try:
            from domain.openrouter_models import get_openrouter_model_meta, is_openrouter_model_free
        except ImportError as e:
            self.logger.error(MSG.ERR_OPENROUTER_IMPORT_FAILED.format(error=e))
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: MSG.ERR_OPENROUTER_IMPORT_FAILED.format(error=e)}
        
        selected_model = get_openrouter_model_meta(model_identifier)
        
        if not selected_model:
            return False, {
                K.KEY_SUCCESS: False,
                K.KEY_ERROR: MSG.ERR_OPENROUTER_MODEL_NOT_IN_CACHE.format(model_identifier=model_identifier),
                K.KEY_MODEL_IDENTIFIER: model_identifier
            }
        
        # Get additional information for presentation
        is_free = is_openrouter_model_free(selected_model)
        current_image_context = self.context.config.get(K.CONFIG_ENABLE_IMAGE_CONTEXT, False)
        
        # Return data for presentation layer
        data = {
            K.KEY_SUCCESS: True,
            K.KEY_MODEL: selected_model,
            K.KEY_IS_FREE: is_free,
            K.KEY_CURRENT_IMAGE_CONTEXT: current_image_context
        }
        
        return True, data
