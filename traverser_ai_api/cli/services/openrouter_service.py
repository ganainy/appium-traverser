#!/usr/bin/env python3
"""
OpenRouter service for managing AI model selection and metadata.
"""

import logging
from typing import Dict, List, Optional, Tuple

from ..shared.context import CLIContext


class OpenRouterService:
    """Service for managing OpenRouter AI models."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def refresh_models(self, wait_for_completion: bool = False) -> bool:
        """Refresh OpenRouter models cache.
        
        Args:
            wait_for_completion: Whether to wait for completion
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from openrouter_models import background_refresh_openrouter_models
        except ImportError as e:
            self.logger.error(f"Failed to import openrouter_models: {e}")
            return False
        
        try:
            success = background_refresh_openrouter_models(wait_for_completion=wait_for_completion)
            if success:
                self.logger.info(
                    "OpenRouter models cache refreshed successfully; saved to traverser_ai_api/output_data/cache/openrouter_models.json"
                )
            else:
                self.logger.error("Failed to refresh OpenRouter models cache")
            return success
        except Exception as e:
            self.logger.error(f"Error refreshing OpenRouter models: {e}", exc_info=True)
            return False
    
    def list_models(self, free_only: Optional[bool] = None) -> Tuple[bool, Optional[List[Dict]]]:
        """List available OpenRouter models.
        
        Args:
            free_only: If True, only show free models. If False, show all models.
                      If None, use the OPENROUTER_SHOW_FREE_ONLY config setting.
                      
        Returns:
            Tuple of (success, models_list)
        """
        try:
            from openrouter_models import load_openrouter_models_cache, is_openrouter_model_free
        except ImportError as e:
            self.logger.error(f"Failed to import openrouter_models: {e}")
            return False, None
        
        models = load_openrouter_models_cache()
        
        if not models:
            self.logger.error("OpenRouter models cache not found. Run refresh first.")
            return False, None
        
        # Determine if we should filter to free-only models
        if free_only is None:
            config_service = self.context.services.get("config")
            if config_service:
                free_only = config_service.get_value("OPENROUTER_SHOW_FREE_ONLY", False)
            else:
                free_only = False
        
        # Filter models if free_only is True
        if free_only:
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
            Tuple of (success, selected_model_dict)
        """
        try:
            from openrouter_models import load_openrouter_models_cache, is_openrouter_model_free
        except ImportError as e:
            self.logger.error(f"Failed to import openrouter_models: {e}")
            return False, None
        
        models = load_openrouter_models_cache()
        
        if not models:
            self.logger.error("OpenRouter models cache not found. Run refresh first.")
            return False, None
        
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
                    model_id = model.get("id", "").lower()
                    model_name = model.get("name", "").lower()
                    if model_identifier_lower in model_id or model_identifier_lower in model_name:
                        selected_model = model
                        break
            
            if not selected_model:
                self.logger.error(f"Model '{model_identifier}' not found.")
                return False, None
            
            model_id = selected_model.get("id")
            model_name = selected_model.get("name")
            
            # Check if this is a paid model and show warning if needed
            pricing = selected_model.get("pricing", {})
            prompt_price = pricing.get("prompt", "0")
            completion_price = pricing.get("completion", "0")
            
            # Show warning if this is a paid model and warnings are enabled
            config_service = self.context.services.get("config")
            show_warning = config_service.get_value("OPENROUTER_NON_FREE_WARNING", False) if config_service else False
            is_free = is_openrouter_model_free(selected_model)
            
            if not is_free and show_warning:
                print("\n⚠️  WARNING: You've selected a PAID model!")
                print(f"   Prompt price: {prompt_price} | Completion price: {completion_price}")
                print("   This model will incur costs for each API call.")
                print("   To disable this warning, set OPENROUTER_NON_FREE_WARNING=false in config.")
                print("   To see only free models, use --list-openrouter-models --free-only")
                print()
            
            # Set AI provider to OpenRouter and update the model
            if config_service:
                config_service.set_value("AI_PROVIDER", "openrouter")
                config_service.set_value("DEFAULT_MODEL_TYPE", model_id)
                config_service.save()
                
                print(f"✅ Successfully selected OpenRouter model:")
                print(f"   Model ID: {model_id}")
                print(f"   Model Name: {model_name}")
                print(f"   Pricing: Prompt {prompt_price} | Completion {completion_price}")
                
                if not is_free:
                    print(f"   💰 This is a PAID model. Costs will be incurred for usage.")
                else:
                    print(f"   🆓 This is a FREE model.")
                      
                print(f"   Use '--show-openrouter-selection' to view this information again.")
                
                return True, selected_model
            else:
                self.logger.error("Config service not available")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Failed to select OpenRouter model: {e}", exc_info=True)
            return False, None
    
    def get_selected_model(self) -> Optional[Dict]:
        """Get the currently selected OpenRouter model.
        
        Returns:
            Selected model dictionary or None
        """
        config_service = self.context.services.get("config")
        if not config_service:
            self.logger.error("Config service not available")
            return None
        
        current_provider = config_service.get_value("AI_PROVIDER", "")
        current_model = config_service.get_value("DEFAULT_MODEL_TYPE", "")
        
        if current_provider.lower() != "openrouter":
            return None
        
        try:
            from openrouter_models import get_openrouter_model_meta
        except ImportError as e:
            self.logger.error(f"Failed to import openrouter_models: {e}")
            return None
        
        return get_openrouter_model_meta(current_model)
    
    def configure_image_context(
        self, 
        model_identifier: Optional[str] = None, 
        enabled: Optional[bool] = None
    ) -> bool:
        """Configure image context settings for OpenRouter models.
        
        Args:
            model_identifier: Model ID (uses current if None)
            enabled: Whether to enable image context (None to toggle/verify)
            
        Returns:
            True if successful, False otherwise
        """
        config_service = self.context.services.get("config")
        if not config_service:
            self.logger.error("Config service not available")
            return False
        
        current_provider = config_service.get_value("AI_PROVIDER", "")
        if current_provider.lower() != "openrouter":
            print("Error: This command is only available when OpenRouter is selected as the AI provider.")
            return False
        
        # Get the current model if none specified
        if not model_identifier:
            model_identifier = config_service.get_value("DEFAULT_MODEL_TYPE", "")
            if not model_identifier or model_identifier == "No model selected":
                print("Error: No OpenRouter model selected. Use '--select-openrouter-model <model>' first.")
                return False
        
        # Get model metadata
        try:
            from openrouter_models import get_openrouter_model_meta, is_openrouter_model_vision
        except ImportError as e:
            self.logger.error(f"Failed to import openrouter_models: {e}")
            return False
        
        selected_model = get_openrouter_model_meta(model_identifier)
        
        if not selected_model:
            print(f"Error: Model '{model_identifier}' not found in cache.")
            return False
        
        # Check image support
        supports_image = selected_model.get("supports_image")
        model_name = selected_model.get("name", "Unknown")
        
        print(f"\n=== OpenRouter Image Context Configuration ===")
        print(f"Model: {model_name} ({model_identifier})")
        print(f"Image Support: {'Yes' if supports_image else 'No'}")
        
        if supports_image is True:
            # Model supports images - allow user to choose
            if enabled is None:
                current_setting = config_service.get_value("ENABLE_IMAGE_CONTEXT", False)
                print(f"Current image context setting: {'Enabled' if current_setting else 'Disabled'}")
                print("This model supports image inputs.")
                return True
            else:
                config_service.set_value("ENABLE_IMAGE_CONTEXT", enabled)
                config_service.save()
                print(f"✅ Image context {'enabled' if enabled else 'disabled'} for model {model_name}")
                return True
        elif supports_image is False:
            # Model doesn't support images - force disable
            if enabled is True:
                print("⚠️ Warning: This model does not support image inputs. Cannot enable image context.")
            config_service.set_value("ENABLE_IMAGE_CONTEXT", False)
            config_service.save()
            print("✅ Image context disabled (model does not support images)")
            return True
        else:
            # Unknown capability - use heuristic
            heuristic = is_openrouter_model_vision(model_identifier)
            if heuristic:
                if enabled is None:
                    current_setting = config_service.get_value("ENABLE_IMAGE_CONTEXT", False)
                    print(f"Current image context setting: {'Enabled' if current_setting else 'Disabled'}")
                    print("Model capability unknown; heuristic suggests it supports images.")
                    return True
                else:
                    config_service.set_value("ENABLE_IMAGE_CONTEXT", enabled)
                    config_service.save()
                    print(f"✅ Image context {'enabled' if enabled else 'disabled'} (heuristic-based)")
                    return True
            else:
                if enabled is True:
                    print("⚠️ Warning: Model capability unknown; heuristic suggests it does not support images.")
                config_service.set_value("ENABLE_IMAGE_CONTEXT", False)
                config_service.save()
                print("✅ Image context disabled (heuristic-based)")
                return True
    
    def show_model_details(self, model_identifier: Optional[str] = None) -> bool:
        """Show detailed information about an OpenRouter model.
        
        Args:
            model_identifier: Model ID (uses current if None)
            
        Returns:
            True if successful, False otherwise
        """
        config_service = self.context.services.get("config")
        if not config_service:
            self.logger.error("Config service not available")
            return False
        
        current_provider = config_service.get_value("AI_PROVIDER", "")
        if current_provider.lower() != "openrouter":
            print("Error: This command is only available when OpenRouter is selected as the AI provider.")
            return False
        
        # Get the current model if none specified
        if not model_identifier:
            model_identifier = config_service.get_value("DEFAULT_MODEL_TYPE", "")
            if not model_identifier or model_identifier == "No model selected":
                print("Error: No OpenRouter model selected. Use '--select-openrouter-model <model>' first.")
                return False
        
        # Get model metadata
        try:
            from openrouter_models import get_openrouter_model_meta, is_openrouter_model_free
        except ImportError as e:
            self.logger.error(f"Failed to import openrouter_models: {e}")
            return False
        
        selected_model = get_openrouter_model_meta(model_identifier)
        
        if not selected_model:
            print(f"Error: Model '{model_identifier}' not found in cache.")
            return False
        
        # Display detailed information
        print(f"\n=== OpenRouter Model Details ===")
        print(f"ID: {selected_model.get('id', 'N/A')}")
        print(f"Name: {selected_model.get('name', 'N/A')}")
        print(f"Description: {selected_model.get('description', 'N/A')}")
        print(f"Context Length: {selected_model.get('context_length', 'N/A')}")
        
        # Pricing information
        pricing = selected_model.get('pricing', {})
        if pricing:
            print(f"\nPricing:")
            print(f"  Prompt: {pricing.get('prompt', 'N/A')}")
            print(f"  Completion: {pricing.get('completion', 'N/A')}")
            print(f"  Image: {pricing.get('image', 'N/A')}")
            
            # Free status
            is_free = is_openrouter_model_free(selected_model)
            print(f"  Free Model: {'Yes' if is_free else 'No'}")
        else:
            print(f"\nPricing: Not available")
        
        # Capabilities
        architecture = selected_model.get('architecture', {})
        if architecture:
            print(f"\nCapabilities:")
            input_modalities = architecture.get('input_modalities', [])
            output_modalities = architecture.get('output_modalities', [])
            print(f"  Input Modalities: {', '.join(input_modalities) if input_modalities else 'N/A'}")
            print(f"  Output Modalities: {', '.join(output_modalities) if output_modalities else 'N/A'}")
            
            supports_image = selected_model.get('supports_image')
            print(f"  Image Support: {'Yes' if supports_image else 'No'}")
            
            supported_parameters = architecture.get('supported_parameters', [])
            if supported_parameters:
                print(f"  Supported Parameters: {', '.join(supported_parameters)}")
        
        # Provider information
        top_provider = selected_model.get('top_provider', {})
        if top_provider:
            print(f"\nProvider Information:")
            print(f"  Provider Name: {top_provider.get('provider_name', 'N/A')}")
            print(f"  Model Format: {top_provider.get('model_format', 'N/A')}")
        
        # Current configuration
        current_image_context = config_service.get_value("ENABLE_IMAGE_CONTEXT", False)
        print(f"\nCurrent Configuration:")
        print(f"  Image Context: {'Enabled' if current_image_context else 'Disabled'}")
        
        print("=================================")
        return True