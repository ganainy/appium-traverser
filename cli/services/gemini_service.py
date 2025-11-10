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
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.GEMINI)
            if not provider:
                error_msg = "Gemini provider not found"
                return False, None, error_msg
        except Exception as e:
            error_msg = f"Failed to get Gemini provider: {e}"
            return False, None, error_msg
        
        try:
            if wait_for_completion:
                from utils import LoadingIndicator
                with LoadingIndicator("Refreshing Gemini models"):
                    success, cache_path = provider.refresh_models(
                        self.context.config,
                        wait_for_completion=wait_for_completion
                    )
            else:
                success, cache_path = provider.refresh_models(
                    self.context.config,
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
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.GEMINI)
            if not provider:
                self.logger.error("Gemini provider not found")
                return False, None
        except Exception as e:
            self.logger.error(f"Failed to get Gemini provider: {e}")
            return False, None
        
        success, models = provider.get_models_full(self.context.config, refresh=refresh)
        
        if not success or not models:
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
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.GEMINI)
            if not provider:
                return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: "Gemini provider not found"}
        except Exception as e:
            self.logger.error(f"Failed to get Gemini provider: {e}")
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: f"Failed to get Gemini provider: {e}"}
        
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
            from domain.providers.enums import AIProvider
            self.context.config.set(K.CONFIG_AI_PROVIDER, AIProvider.GEMINI.value)
            
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
        from domain.providers.enums import AIProvider
        current_provider = self.context.config.get(K.CONFIG_AI_PROVIDER, "")
        if current_provider.lower() != AIProvider.GEMINI.value:
            return None
        
        current_model = self.context.config.get(K.CONFIG_DEFAULT_MODEL_TYPE, "")
        if not current_model or current_model == K.CONFIG_NO_MODEL_SELECTED:
            return None
        
        try:
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.GEMINI)
            if not provider:
                return None
        except Exception:
            return None
        
        return provider.get_model_meta(current_model)
    
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
        from domain.providers.enums import AIProvider
        current_provider = self.context.config.get(K.CONFIG_AI_PROVIDER, "")
        if current_provider.lower() != AIProvider.GEMINI.value:
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
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.GEMINI)
            if not provider:
                return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: "Gemini provider not found"}
        except Exception as e:
            self.logger.error(f"Failed to get Gemini provider: {e}")
            return False, {K.KEY_SUCCESS: False, K.KEY_ERROR: f"Failed to get Gemini provider: {e}"}
        
        selected_model = provider.get_model_meta(model_identifier)
        
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

