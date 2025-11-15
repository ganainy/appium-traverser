# ui_state_handler.py - UI State Management Handler
# Handles dynamic UI state and logic, separated from component creation

import logging
from typing import Any, Dict

from PySide6.QtWidgets import QGroupBox, QLabel, QApplication

from config.app_config import Config
from domain.providers.registry import ProviderRegistry
from domain.providers.enums import AIProvider
from ui.constants import (
    UI_MODE_BASIC, UI_MODE_EXPERT,
    ADVANCED_GROUPS, ADVANCED_FIELDS,
    UI_MODE_CONFIG_KEY
)


class UIStateHandler:
    """Handles dynamic UI state management and logic."""
    
    def __init__(self, main_controller: Any, config_handler: Any, config_widgets: Dict[str, Any], ui_groups: Dict[str, QGroupBox]):
        """
        Initialize the UI state handler.
        
        Args:
            main_controller: The main CrawlerControllerWindow instance
            config_handler: The ConfigManager instance
            config_widgets: Dictionary of config UI widgets
            ui_groups: Dictionary of UI group widgets
        """
        self.main_controller = main_controller
        self.config_handler = config_handler
        self.config_widgets = config_widgets
        self.ui_groups = ui_groups
        self.config: Config = main_controller.config

    def toggle_ui_complexity(self, mode: str):
        """
        Toggle between basic and expert UI modes

        Args:
            mode: "Basic" or "Expert" mode (use UI_MODE_BASIC or UI_MODE_EXPERT)
        """
        is_basic = mode == UI_MODE_BASIC

        # Toggle group visibility based on mode
        for group_name, group_widget in self.ui_groups.items():
            # Hide advanced groups in basic mode
            if group_name in ADVANCED_GROUPS:
                group_widget.setVisible(not is_basic)

        # Toggle individual field visibility based on mode
        for field_name, is_advanced in ADVANCED_FIELDS.items():
            # Skip if widget not in config_widgets
            if field_name not in self.config_widgets:
                continue

            # Get widget reference
            widget = self.config_widgets.get(field_name)

            # Skip None widgets
            if widget is None:
                continue

            try:
                # Skip widgets that don't have a parent (not yet added to layout)
                if not hasattr(widget, "parent") or widget.parent() is None:
                    continue

                # Get parent layout
                parent_layout = widget.parent().layout() if widget.parent() else None
                if parent_layout is None:
                    continue

                # If in basic mode and field is advanced, hide it
                # If in expert mode, show all
                widget_visible = not (is_basic and is_advanced)

                # Find and set visibility of associated QLabel
                for i in range(parent_layout.count()):
                    label_item = parent_layout.itemAt(i)
                    if (
                        label_item
                        and label_item.widget()
                        and isinstance(label_item.widget(), QLabel)
                        and i + 1 < parent_layout.count()
                        and parent_layout.itemAt(i + 1).widget() == widget
                    ):
                        label_item.widget().setVisible(widget_visible)
                        break

                # Set widget visibility
                widget.setVisible(widget_visible)
            except Exception as e:
                # Log but don't crash if there's an issue with a specific widget
                logging.warning(f"Error toggling visibility for {field_name}: {e}")

        # Set the dropdown to the current mode
        if hasattr(self.config_handler, "ui_mode_dropdown"):
            index = self.config_handler.ui_mode_dropdown.findText(mode)
            if index >= 0 and self.config_handler.ui_mode_dropdown.currentIndex() != index:
                # Only set if it's different to avoid triggering change events
                self.config_handler.ui_mode_dropdown.setCurrentIndex(index)

        # Save the current mode to user config
        self.config_handler.config.update_setting_and_save(
            UI_MODE_CONFIG_KEY, mode, self.main_controller._sync_user_config_files
        )

        # Synchronize the changes to the API config file
        # Note: Synchronization is now handled automatically by the callback in update_setting_and_save

        # Ensure the config.UI_MODE attribute is updated
        if hasattr(self.config_handler.config, "UI_MODE"):
            self.config_handler.config.UI_MODE = mode
        logging.debug(f"UI mode switched to and saved: {mode}")
        logging.debug(
            f"Config file location: {self.config_handler.config.USER_CONFIG_FILE_PATH}"
        )
        self.main_controller.log_message(f"Switched to {mode} mode", "blue")

    def _configure_image_context_for_provider(
        self, strategy, config, capabilities, model_dropdown, no_selection_label
    ):
        """Configure image context UI based on provider strategy and capabilities."""
        auto_disable = capabilities.get("auto_disable_image_context", False)
        if auto_disable:
            self.config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
            self.config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
            from ui.strings import IMAGE_CONTEXT_DISABLED_PAYLOAD_LIMIT
            self.config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(
                IMAGE_CONTEXT_DISABLED_PAYLOAD_LIMIT.format(max_kb=capabilities.get('payload_max_size_kb', 500))
            )
            if "IMAGE_CONTEXT_WARNING" in self.config_widgets:
                self.config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(True)
            self._add_image_context_warning(strategy.name, capabilities)
            # Update preprocessing visibility (disabled)
            try:
                self._update_image_preprocessing_visibility(False)
            except Exception as e:
                logging.debug(f"Could not update preprocessing visibility: {e}")
        else:
            # Enable image context - provider supports it
            from ui.strings import IMAGE_CONTEXT_ENABLED_TOOLTIP
            self.config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
            # Get current checked state to determine visibility
            current_checked = self.config_widgets["ENABLE_IMAGE_CONTEXT"].isChecked()
            self.config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(IMAGE_CONTEXT_ENABLED_TOOLTIP)
            self.config_widgets["ENABLE_IMAGE_CONTEXT"].setStyleSheet("")
            if "IMAGE_CONTEXT_WARNING" in self.config_widgets:
                self.config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
            
            # Update preprocessing visibility based on current checked state
            try:
                self._update_image_preprocessing_visibility(current_checked)
            except Exception as e:
                logging.debug(f"Could not update preprocessing visibility: {e}")
            
            # For OpenRouter, handle model-specific image support
            if strategy.provider == AIProvider.OPENROUTER:
                self._setup_openrouter_image_context_handler(
                    strategy, config, model_dropdown, no_selection_label
                )

    def _setup_openrouter_image_context_handler(
        self, strategy, config, model_dropdown, no_selection_label
    ):
        """Set up OpenRouter-specific image context handling with model change listener."""
        def _on_openrouter_model_changed(name: str):
            try:
                if "ENABLE_IMAGE_CONTEXT" not in self.config_widgets:
                    return
                
                if name == no_selection_label:
                    self.config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
                    self.config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                    from ui.strings import SELECT_MODEL_TO_CONFIGURE
                    self.config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(SELECT_MODEL_TO_CONFIGURE)
                    if "IMAGE_CONTEXT_WARNING" in self.config_widgets:
                        self.config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
                    if "OPENROUTER_NON_FREE_WARNING" in self.config_widgets:
                        self.config_widgets["OPENROUTER_NON_FREE_WARNING"].setVisible(False)
                    # Update preprocessing visibility (disabled)
                    try:
                        self._update_image_preprocessing_visibility(False)
                    except Exception as e:
                        logging.debug(f"Could not update preprocessing visibility: {e}")
                    return
                
                # Check model-specific image support
                supports_image = strategy.supports_image_context(config, name)
                if supports_image:
                    self.config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
                    self.config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(True)
                    from ui.strings import MODEL_SUPPORTS_IMAGE_INPUTS
                    self.config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(MODEL_SUPPORTS_IMAGE_INPUTS)
                    if "IMAGE_CONTEXT_WARNING" in self.config_widgets:
                        self.config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
                    # Update preprocessing visibility (enabled)
                    try:
                        self._update_image_preprocessing_visibility(True)
                    except Exception as e:
                        logging.debug(f"Could not update preprocessing visibility: {e}")
                else:
                    self.config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
                    self.config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                    from ui.strings import MODEL_DOES_NOT_SUPPORT_IMAGE_INPUTS, WARNING_MODEL_NO_IMAGE_SUPPORT
                    self.config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(MODEL_DOES_NOT_SUPPORT_IMAGE_INPUTS)
                    if "IMAGE_CONTEXT_WARNING" in self.config_widgets:
                        try:
                            self.config_widgets["IMAGE_CONTEXT_WARNING"].setText(WARNING_MODEL_NO_IMAGE_SUPPORT)
                        except Exception:
                            pass
                        self.config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(True)
                    # Update preprocessing visibility (disabled)
                    try:
                        self._update_image_preprocessing_visibility(False)
                    except Exception as e:
                        logging.debug(f"Could not update preprocessing visibility: {e}")
                
                # Show/hide non-free warning
                try:
                    if "OPENROUTER_NON_FREE_WARNING" in self.config_widgets:
                        provider = ProviderRegistry.get(AIProvider.OPENROUTER)
                        if provider:
                            is_free = provider.is_model_free(name)
                            self.config_widgets["OPENROUTER_NON_FREE_WARNING"].setVisible(not is_free)
                except Exception as e:
                    logging.debug(f"Error toggling non-free warning: {e}")
            except Exception as e:
                logging.debug(f"Error toggling image context on model change: {e}")
        
        model_dropdown.currentTextChanged.connect(_on_openrouter_model_changed)

    def _update_model_types(self, provider: str) -> None:
        """Update the model types based on the selected AI provider using provider strategy."""
        model_dropdown = self.config_widgets["DEFAULT_MODEL_TYPE"]
        # Capture the current selection to restore it after repopulating
        previous_text = model_dropdown.currentText()

        # Block signals to prevent auto-save from triggering with an empty value
        model_dropdown.blockSignals(True)

        model_dropdown.clear()

        # Always start with an explicit no-selection placeholder
        from ui.strings import NO_MODEL_SELECTED
        NO_SELECTION_LABEL = NO_MODEL_SELECTED
        try:
            model_dropdown.addItem(NO_SELECTION_LABEL)
        except Exception:
            # Fallback: ensure dropdown has at least one item
            model_dropdown.addItem(NO_MODEL_SELECTED)

        # Get provider strategy
        strategy = ProviderRegistry.get_by_name(provider)
        if not strategy:
            logging.warning(f"Unknown provider: {provider}")
            model_dropdown.blockSignals(False)
            return
        
        # Get provider enum for type checking
        provider_enum = AIProvider.from_string(provider) if AIProvider.is_valid(provider) else None
        
        # Get provider capabilities
        capabilities = strategy.get_capabilities()
        
        # Get config for provider methods
        # Always create a fresh config object to avoid SQLite thread-safety issues
        # The config object may have been accessed in a worker thread, making its SQLite connection thread-local
        try:
            from config.app_config import Config
            config = Config()  # Create fresh config in current (main) thread
        except Exception:
            logging.warning("Could not create config for provider strategy")
            model_dropdown.blockSignals(False)
            return

        # Get models using provider strategy
        # Check free-only filter state from the config object (reliable source of truth)
        # Reading from config instead of UI prevents race conditions during load_config
        free_only = False
        if "OPENROUTER_SHOW_FREE_ONLY" in self.config_widgets:
            # Read from the temporary config object, which loaded from DB
            free_only = config.get("OPENROUTER_SHOW_FREE_ONLY", False)
            # Update config to reflect checkbox state (for OpenRouter's get_models to use)
            # This is technically redundant if config.get worked, but ensures
            # the in-memory config object has the value set for get_models()
            if provider_enum == AIProvider.OPENROUTER:
                config.set("OPENROUTER_SHOW_FREE_ONLY", free_only)
        
        try:
            models = strategy.get_models(config)
            if models:
                # Process models in batches to avoid blocking UI thread
                # Add items in chunks and process events between chunks
                batch_size = 50
                for i in range(0, len(models), batch_size):
                    batch = models[i:i + batch_size]
                    model_dropdown.addItems(batch)
                    # Process events to keep UI responsive
                    QApplication.processEvents()
        except Exception as e:
            logging.warning(f"Failed to get models from provider strategy: {e}")
        
        # Restore previous selection if available
        try:
            if previous_text:
                idx = model_dropdown.findText(previous_text)
                if idx >= 0:
                    model_dropdown.setCurrentIndex(idx)
        except Exception:
            pass

        # Configure image context based on provider capabilities
        if "ENABLE_IMAGE_CONTEXT" in self.config_widgets:
            self._configure_image_context_for_provider(
                strategy, config, capabilities, model_dropdown, NO_SELECTION_LABEL
            )

        # Provider-specific UI updates
        # Note: Free-only filter is now handled generically above for all providers
        # The checkbox change handler is already connected in _create_ai_settings_group

        # Unblock signals after updating
        model_dropdown.blockSignals(False)

    def _add_image_context_warning(self, provider: str, capabilities: Dict[str, Any]) -> None:
        """Add visual warning when image context is auto-disabled."""
        try:
            payload_limit = capabilities.get("payload_max_size_kb", 150)
            warning_msg = f"⚠️ IMAGE CONTEXT AUTO-DISABLED: {provider} has strict payload limits ({payload_limit}KB max). Image context automatically disabled to prevent API errors."

            # Log the warning
            logging.warning(
                f"Image context auto-disabled for {provider} due to payload limits"
            )

            # Try to show warning in UI if main controller is available
            try:
                # Get the main window instance if it exists
                app = QApplication.instance()
                if app and isinstance(app, QApplication):
                    for widget in app.topLevelWidgets():
                        if isinstance(widget, type(self.main_controller)):
                            widget.log_message(warning_msg, "orange")
                            break
            except Exception as e:
                logging.debug(f"Could not show UI warning: {e}")

        except Exception as e:
            logging.error(f"Error adding image context warning: {e}")

    def _update_image_preprocessing_visibility(self, enabled: bool):
        """
        Update visibility of image preprocessing options based on Enable Image Context state.
        
        Args:
            enabled: Whether image context is enabled
        """
        if 'image_preprocessing_group' not in self.ui_groups:
            return
        
        image_prep_group = self.ui_groups['image_preprocessing_group']
        if not hasattr(image_prep_group, 'preprocessing_widgets') or not hasattr(image_prep_group, 'preprocessing_labels'):
            return
        
        # Update visibility of all preprocessing widgets and labels
        for widget in image_prep_group.preprocessing_widgets:
            if widget:
                widget.setVisible(enabled)
        
        for label in image_prep_group.preprocessing_labels:
            if label:
                label.setVisible(enabled)

    def _refresh_models(self) -> None:
        """Generic refresh function that works for all AI providers."""
        try:
            current_provider_name = self.config_widgets["AI_PROVIDER"].currentText()
            self.main_controller.log_message(
                f"Starting {current_provider_name} model refresh...", "blue"
            )
            
            provider = ProviderRegistry.get_by_name(current_provider_name)
            if not provider:
                error_msg = f"Unknown provider: {current_provider_name}"
                logging.error(error_msg)
                self.main_controller.log_message(error_msg, "red")
                return
            
            # Refresh models synchronously
            try:
                self.main_controller.log_message(
                    f"Refreshing {current_provider_name} models...", "blue"
                )
                
                success, cache_path = provider.refresh_models(
                    config=self.config_handler.config,
                    wait_for_completion=True
                )
                
                if success:
                    # Success means models were downloaded from API
                    try:
                        models = provider.get_models(self.config_handler.config)
                        model_count = len(models) if models else 0
                        source = "Downloaded from API"
                        final_message = f"{current_provider_name} models refreshed successfully. Found {model_count} models. {source}"
                    except Exception as e:
                        logging.debug(f"Could not count models: {e}")
                        source = "Downloaded from API"
                        final_message = f"{current_provider_name} models refreshed successfully. {source}"
                    
                    self.main_controller.log_message(final_message, "green")
                    self._update_model_types(current_provider_name)
                else:
                    error_message = f"{current_provider_name} refresh failed"
                    if cache_path:
                        error_message += f" (cache path: {cache_path})"
                    else:
                        error_message += ". Check network connection and API key."
                    self.main_controller.log_message(error_message, "orange")
            
            except RuntimeError as e:
                error_str = str(e)
                # Try to load from cache if refresh failed
                try:
                    models = provider.get_models(self.config_handler.config)
                    if models:
                        model_count = len(models) if models else 0
                        source = "Loaded from cache"
                        final_message = f"{current_provider_name} models loaded successfully. Found {model_count} models. {source}"
                        self.main_controller.log_message(final_message, "green")
                        self._update_model_types(current_provider_name)
                        return
                except Exception:
                    pass
                
                # If we couldn't load from cache, show error
                if "timed out" in error_str.lower():
                    error_msg = f"{current_provider_name} model refresh timed out. {error_str}"
                else:
                    error_msg = f"{current_provider_name} model refresh failed: {error_str}"
                logging.error(error_msg, exc_info=True)
                self.main_controller.log_message(error_msg, "orange")
            except Exception as e:
                # Try to load from cache if refresh failed
                try:
                    models = provider.get_models(self.config_handler.config)
                    if models:
                        model_count = len(models) if models else 0
                        source = "Loaded from cache"
                        final_message = f"{current_provider_name} models loaded successfully. Found {model_count} models. {source}"
                        self.main_controller.log_message(final_message, "green")
                        self._update_model_types(current_provider_name)
                        return
                except Exception:
                    pass
                
                # If we couldn't load from cache, show error
                error_msg = f"{current_provider_name} model refresh failed: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.main_controller.log_message(error_msg, "orange")
        
        except Exception as e:
            logging.error(f"Error starting refresh: {e}", exc_info=True)
            try:
                self.main_controller.log_message(
                    f"Failed to start refresh: {e}", "orange"
                )
            except Exception:
                pass

