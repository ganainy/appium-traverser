# ui/components.py - UI components for the Appium Crawler Controller

import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.custom_widgets import NoScrollComboBox as QComboBox
from ui.custom_widgets import NoScrollSpinBox as QSpinBox


class UIComponents:
    """Factory class for creating UI components used in the Crawler Controller."""

    # UI Mode Constants
    UI_MODE_BASIC = "Basic"
    UI_MODE_EXPERT = "Expert"
    UI_MODE_DEFAULT = UI_MODE_BASIC
    UI_MODE_CONFIG_KEY = "UI_MODE"

    # Define which settings groups and fields are considered advanced
    # These will be hidden in basic mode
    ADVANCED_GROUPS = [
        "appium_settings_group",
        "error_handling_group",
        "focus_areas_group",  # Focus areas can be advanced for basic users
        "image_preprocessing_group",  # Image preprocessing controls are advanced
    ]

    @staticmethod
    def _configure_image_context_for_provider(
        strategy, config, config_widgets, capabilities, model_dropdown, no_selection_label
    ):
        """Configure image context UI based on provider strategy and capabilities."""
        from domain.providers.enums import AIProvider
        
        auto_disable = capabilities.get("auto_disable_image_context", False)
        if auto_disable:
            config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
            config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
            from ui.strings import IMAGE_CONTEXT_DISABLED_PAYLOAD_LIMIT
            config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(
                IMAGE_CONTEXT_DISABLED_PAYLOAD_LIMIT.format(max_kb=capabilities.get('payload_max_size_kb', 500))
            )
            if "IMAGE_CONTEXT_WARNING" in config_widgets:
                config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(True)
            UIComponents._add_image_context_warning(strategy.name, capabilities)
        else:
            # Enable image context - provider supports it
            from ui.strings import IMAGE_CONTEXT_ENABLED_TOOLTIP
            config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
            config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(IMAGE_CONTEXT_ENABLED_TOOLTIP)
            config_widgets["ENABLE_IMAGE_CONTEXT"].setStyleSheet("")
            if "IMAGE_CONTEXT_WARNING" in config_widgets:
                config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
            
            # For OpenRouter, handle model-specific image support
            if strategy.provider == AIProvider.OPENROUTER:
                UIComponents._setup_openrouter_image_context_handler(
                    strategy, config, config_widgets, model_dropdown, no_selection_label
                )

    @staticmethod
    def _setup_openrouter_image_context_handler(
        strategy, config, config_widgets, model_dropdown, no_selection_label
    ):
        """Set up OpenRouter-specific image context handling with model change listener."""
        def _on_openrouter_model_changed(name: str):
            try:
                if "ENABLE_IMAGE_CONTEXT" not in config_widgets:
                    return
                
                if name == no_selection_label:
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                    from ui.strings import SELECT_MODEL_TO_CONFIGURE
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(SELECT_MODEL_TO_CONFIGURE)
                    if "IMAGE_CONTEXT_WARNING" in config_widgets:
                        config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
                    if "OPENROUTER_NON_FREE_WARNING" in config_widgets:
                        config_widgets["OPENROUTER_NON_FREE_WARNING"].setVisible(False)
                    return
                
                # Check model-specific image support
                supports_image = strategy.supports_image_context(config, name)
                if supports_image:
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(True)
                    from ui.strings import MODEL_SUPPORTS_IMAGE_INPUTS
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(MODEL_SUPPORTS_IMAGE_INPUTS)
                    if "IMAGE_CONTEXT_WARNING" in config_widgets:
                        config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
                else:
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                    from ui.strings import MODEL_DOES_NOT_SUPPORT_IMAGE_INPUTS, WARNING_MODEL_NO_IMAGE_SUPPORT
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(MODEL_DOES_NOT_SUPPORT_IMAGE_INPUTS)
                    if "IMAGE_CONTEXT_WARNING" in config_widgets:
                        try:
                            config_widgets["IMAGE_CONTEXT_WARNING"].setText(WARNING_MODEL_NO_IMAGE_SUPPORT)
                        except Exception:
                            pass
                        config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(True)
                
                # Show/hide non-free warning
                try:
                    if "OPENROUTER_NON_FREE_WARNING" in config_widgets:
                        from domain.providers.registry import ProviderRegistry
                        from domain.providers.enums import AIProvider
                        
                        provider = ProviderRegistry.get(AIProvider.OPENROUTER)
                        if provider:
                            is_free = provider.is_model_free(name)
                            config_widgets["OPENROUTER_NON_FREE_WARNING"].setVisible(not is_free)
                except Exception as e:
                    logging.debug(f"Error toggling non-free warning: {e}")
            except Exception as e:
                logging.debug(f"Error toggling image context on model change: {e}")
        
        model_dropdown.currentTextChanged.connect(_on_openrouter_model_changed)

    @staticmethod
    def _update_model_types(provider: str, config_widgets: Dict[str, Any], config_handler: Any = None) -> None:
        """Update the model types based on the selected AI provider using provider strategy."""
        from domain.providers.registry import ProviderRegistry
        from domain.providers.enums import AIProvider
        
        model_dropdown = config_widgets["DEFAULT_MODEL_TYPE"]
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
        
        # Get provider capabilities
        capabilities = strategy.get_capabilities()
        
        # Get config for provider methods
        config = config_handler.config if config_handler and hasattr(config_handler, 'config') else None
        if not config:
            try:
                from config.app_config import Config
                config = Config()
            except Exception:
                logging.warning("Could not get config for provider strategy")
                model_dropdown.blockSignals(False)
                return

        # Get models using provider strategy
        try:
            models = strategy.get_models(config)
            if models:
                model_dropdown.addItems(models)
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
        if "ENABLE_IMAGE_CONTEXT" in config_widgets:
            UIComponents._configure_image_context_for_provider(
                strategy, config, config_widgets, capabilities, model_dropdown, NO_SELECTION_LABEL
            )

        # Provider-specific UI updates (OpenRouter needs special handling for free-only filter)
        provider_enum = AIProvider.from_string(provider) if AIProvider.is_valid(provider) else None
        if provider_enum == AIProvider.OPENROUTER:
            # OpenRouter-specific: Handle free-only filter and ensure presets are available
            # Note: Models are already populated by strategy.get_models() above
            # This section only handles the free-only filter UI logic
            try:
                if "OPENROUTER_SHOW_FREE_ONLY" in config_widgets:
                    # Wire up free-only filter to re-populate models when toggled
                    def _on_free_only_changed(_state: int):
                        try:
                            UIComponents._update_model_types(provider, config_widgets, config_handler)
                        except Exception as e:
                            logging.debug(f"Failed to apply free-only filter: {e}")
                    
                    config_widgets["OPENROUTER_SHOW_FREE_ONLY"].stateChanged.connect(_on_free_only_changed)
            except Exception:
                pass

        # Unblock signals after updating
        model_dropdown.blockSignals(False)

    @staticmethod
    def _add_image_context_warning(provider: str, capabilities: Dict[str, Any]) -> None:
        """Add visual warning when image context is auto-disabled."""
        import logging

        try:
            payload_limit = capabilities.get("payload_max_size_kb", 150)
            warning_msg = f"⚠️ IMAGE CONTEXT AUTO-DISABLED: {provider} has strict payload limits ({payload_limit}KB max). Image context automatically disabled to prevent API errors."

            # Log the warning
            logging.warning(
                f"Image context auto-disabled for {provider} due to payload limits"
            )

            # Try to show warning in UI if main controller is available
            try:
                from PySide6.QtWidgets import QApplication

                from domain.ui_controller import CrawlerControllerWindow

                # Get the main window instance if it exists
                app = QApplication.instance()
                if app and isinstance(app, QApplication):
                    for widget in app.topLevelWidgets():
                        if isinstance(widget, CrawlerControllerWindow):
                            widget.log_message(warning_msg, "orange")
                            break
            except Exception as e:
                logging.debug(f"Could not show UI warning: {e}")

        except Exception as e:
            logging.error(f"Error adding image context warning: {e}")

    ADVANCED_FIELDS = {
        "TARGET_DEVICE_UDID": True,  # True means hide in basic mode
        "DEFAULT_MODEL_TYPE": False,
        "XML_SNIPPET_MAX_LEN": True,
        "STABILITY_WAIT": True,
        "VISUAL_SIMILARITY_THRESHOLD": True,
        "ALLOWED_EXTERNAL_PACKAGES": True,
        "MAX_CONSECUTIVE_AI_FAILURES": True,
        "MAX_CONSECUTIVE_MAP_FAILURES": True,
        "MAX_CONSECUTIVE_EXEC_FAILURES": True,
        "ENABLE_IMAGE_CONTEXT": False,
        "ENABLE_TRAFFIC_CAPTURE": False,
        "CLEANUP_DEVICE_PCAP_FILE": True,
        "CONTINUE_EXISTING_RUN": False,
        "MOBSF_API_URL": True,
        "MOBSF_API_KEY": True,
        "OPENROUTER_SHOW_FREE_ONLY": False,
        # Image preprocessing controls
        "IMAGE_MAX_WIDTH": True,
        "IMAGE_FORMAT": True,
        "IMAGE_QUALITY": True,
        "IMAGE_CROP_BARS": True,
        "IMAGE_CROP_TOP_PERCENT": True,
        "IMAGE_CROP_BOTTOM_PERCENT": True,
        # Crawler prompt templates
        "CRAWLER_ACTION_DECISION_PROMPT": True,
        "CRAWLER_SYSTEM_PROMPT_TEMPLATE": True,
        "CRAWLER_AVAILABLE_ACTIONS": True,
    }

    @staticmethod
    def create_left_panel(
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
        controls_handler: Any,
    ) -> QWidget:
        """
        Create the left panel with configuration options

        Args:
            config_widgets: Dictionary to store the config UI widgets
            tooltips: Dictionary of tooltips for the UI elements
            config_handler: Object with methods for handling config-related actions
            controls_handler: Object with methods for handling control buttons

        Returns:
            QWidget containing the left panel
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Create UI mode switch (Basic/Expert)
        mode_layout = QHBoxLayout()
        mode_label = QLabel("UI Mode:")
        config_handler.ui_mode_dropdown = QComboBox()
        config_handler.ui_mode_dropdown.addItems([
            UIComponents.UI_MODE_BASIC,
            UIComponents.UI_MODE_EXPERT
        ])

        # Get the UI mode from config
        initial_mode = UIComponents.UI_MODE_DEFAULT  # Default if not found

        # Try to get UI_MODE from the Config object's SQLite store
        try:
            stored_mode = config_handler.main_controller.config.get(UIComponents.UI_MODE_CONFIG_KEY)
            if stored_mode:
                initial_mode = stored_mode
                logging.debug(f"Setting initial UI mode from SQLite config store: {initial_mode}")
        except Exception as e:
            logging.warning(f"Error retrieving {UIComponents.UI_MODE_CONFIG_KEY} from config store: {e}")

        logging.debug(f"Initial UI mode determined as: {initial_mode}")

        # Set the dropdown to the initial mode
        mode_index = config_handler.ui_mode_dropdown.findText(initial_mode)
        if mode_index >= 0:
            config_handler.ui_mode_dropdown.setCurrentIndex(mode_index)
        else:
            config_handler.ui_mode_dropdown.setCurrentIndex(
                0
            )  # Default to Basic if not found

        from ui.strings import UI_MODE_TOOLTIP
        config_handler.ui_mode_dropdown.setToolTip(UI_MODE_TOOLTIP)
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(config_handler.ui_mode_dropdown)

        from ui.strings import RESET_TO_DEFAULTS_TOOLTIP
        reset_button = QPushButton("Reset Settings")
        reset_button.setToolTip(RESET_TO_DEFAULTS_TOOLTIP)
        reset_button.clicked.connect(config_handler.reset_settings)
        mode_layout.addWidget(reset_button)
        layout.addLayout(mode_layout)

        # Connect UI mode dropdown to toggle UI complexity
        config_handler.ui_mode_dropdown.currentTextChanged.connect(
            lambda mode: UIComponents.toggle_ui_complexity(mode, config_handler)
        )

        # Create scrollable area for config inputs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QFormLayout(scroll_content)

        # Store scroll_content in config_handler for later reference
        config_handler.scroll_content = scroll_content

        # Create the config inputs sections
        appium_group = UIComponents._create_appium_settings_group(
            scroll_layout, config_widgets, tooltips, controls_handler
        )
        appium_group.setObjectName("appium_settings_group")

        app_group = UIComponents._create_app_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        app_group.setObjectName("app_settings_group")

        ai_group = UIComponents._create_ai_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        ai_group.setObjectName("ai_settings_group")

        # Image Preprocessing placed directly after AI for clearer perception grouping
        image_prep_group = UIComponents._create_image_preprocessing_group(
            scroll_layout, config_widgets, tooltips
        )
        image_prep_group.setObjectName("image_preprocessing_group")

        focus_areas_group = UIComponents._create_focus_areas_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        focus_areas_group.setObjectName("focus_areas_group")

        crawler_group = UIComponents._create_crawler_settings_group(
            scroll_layout, config_widgets, tooltips
        )
        crawler_group.setObjectName("crawler_settings_group")

        error_handling_group = UIComponents._create_error_handling_group(
            scroll_layout, config_widgets, tooltips
        )
        error_handling_group.setObjectName("error_handling_group")

        # Privacy & Network settings (traffic capture)
        privacy_network_group = UIComponents._create_privacy_network_group(
            scroll_layout, config_widgets, tooltips
        )
        privacy_network_group.setObjectName("privacy_network_group")

        mobsf_group = UIComponents._create_mobsf_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        mobsf_group.setObjectName("mobsf_settings_group")

        # Run Control and Recording groups (split from previous combined group)
        run_control_group = UIComponents._create_run_control_group(
            scroll_layout, config_widgets, tooltips
        )
        run_control_group.setObjectName("run_control_group")

        recording_group = UIComponents._create_recording_group(
            scroll_layout, config_widgets, tooltips
        )
        recording_group.setObjectName("recording_group")

        # Apply default values
        config_handler._apply_defaults_from_config_to_widgets()
        config_handler._update_crawl_mode_inputs_state()

        # Store the group widgets for mode switching
        config_handler.ui_groups = {
            "appium_settings_group": appium_group,
            "app_settings_group": app_group,
            "ai_settings_group": ai_group,
            "image_preprocessing_group": image_prep_group,
            "focus_areas_group": focus_areas_group,
            "crawler_settings_group": crawler_group,
            "error_handling_group": error_handling_group,
            "privacy_network_group": privacy_network_group,
            "mobsf_settings_group": mobsf_group,
            "run_control_group": run_control_group,
            "recording_group": recording_group,
        }

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Add control buttons
        controls_group = UIComponents._create_control_buttons(controls_handler)
        layout.addWidget(controls_group)

        # Initialize the UI complexity based on the mode we determined
        UIComponents.toggle_ui_complexity(initial_mode, config_handler)

        # Connect all widgets to auto-save
        config_handler.connect_widgets_for_auto_save()

        return panel

    @staticmethod
    def toggle_ui_complexity(mode: str, config_handler):
        """
        Toggle between basic and expert UI modes

        Args:
            mode: "Basic" or "Expert" mode (use UIComponents.UI_MODE_BASIC or UIComponents.UI_MODE_EXPERT)
            config_handler: The config handler with references to UI widgets
        """
        is_basic = mode == UIComponents.UI_MODE_BASIC

        # Toggle group visibility based on mode
        for group_name, group_widget in config_handler.ui_groups.items():
            # Hide advanced groups in basic mode
            if group_name in UIComponents.ADVANCED_GROUPS:
                group_widget.setVisible(not is_basic)

        # Toggle individual field visibility based on mode
        for field_name, is_advanced in UIComponents.ADVANCED_FIELDS.items():
            # Skip if widget not in config_widgets
            if field_name not in config_handler.main_controller.config_widgets:
                continue

            # Get widget reference
            widget = config_handler.main_controller.config_widgets.get(field_name)

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
        if hasattr(config_handler, "ui_mode_dropdown"):
            index = config_handler.ui_mode_dropdown.findText(mode)
            if index >= 0 and config_handler.ui_mode_dropdown.currentIndex() != index:
                # Only set if it's different to avoid triggering change events
                config_handler.ui_mode_dropdown.setCurrentIndex(index)

        # Save the current mode to user config
        config_handler.config.update_setting_and_save(
            UIComponents.UI_MODE_CONFIG_KEY, mode, config_handler.main_controller._sync_user_config_files
        )

        # Synchronize the changes to the API config file
        # Note: Synchronization is now handled automatically by the callback in update_setting_and_save

        # Ensure the config.UI_MODE attribute is updated
        if hasattr(config_handler.config, "UI_MODE"):
            config_handler.config.UI_MODE = mode
        logging.debug(f"UI mode switched to and saved: {mode}")
        logging.debug(
            f"Config file location: {config_handler.config.USER_CONFIG_FILE_PATH}"
        )
        config_handler.main_controller.log_message(f"Switched to {mode} mode", "blue")

    @staticmethod
    def create_right_panel(controller) -> QWidget:
        """
        Create the right panel with status, log output, and screenshot display

        Args:
            controller: The controller object that will handle the UI interactions

        Returns:
            QWidget containing the right panel
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Step counter placed above the status text
        step_layout = QHBoxLayout()
        controller.step_label = QLabel("Step: 0")
        step_layout.addWidget(controller.step_label)

        # Status section
        status_layout = QHBoxLayout()
        controller.status_label = QLabel("Status: Idle")
        controller.progress_bar = QProgressBar()
        status_layout.addWidget(controller.status_label)
        status_layout.addWidget(controller.progress_bar)

        # Create side-by-side layout for Action History and Screenshot
        history_screenshot_layout = QHBoxLayout()
        
        # Action history (left side)
        action_history_group = QGroupBox("Action History")
        action_history_layout = QVBoxLayout(action_history_group)
        controller.action_history = QTextEdit()
        controller.action_history.setReadOnly(True)
        # Improve visibility and usability
        try:
            from ui.strings import ACTION_HISTORY_PLACEHOLDER
            controller.action_history.setPlaceholderText(ACTION_HISTORY_PLACEHOLDER)
        except Exception:
            pass
        controller.action_history.setStyleSheet("""
            background-color: #333333; 
            color: #FFFFFF; 
            font-size: 11px; 
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            border: 1px solid #555555;
        """)
        try:
            from PySide6.QtWidgets import QTextEdit as _QTextEdit
            controller.action_history.setLineWrapMode(_QTextEdit.LineWrapMode.WidgetWidth)
        except Exception:
            pass
        # Significantly increase minimum height and make it expandable
        controller.action_history.setMinimumHeight(400)
        controller.action_history.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        action_history_layout.addWidget(controller.action_history)

        # Screenshot display (right side)
        screenshot_group = QGroupBox("Current Screenshot")
        screenshot_layout = QVBoxLayout(screenshot_group)
        controller.screenshot_label = QLabel()
        controller.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controller.screenshot_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        controller.screenshot_label.setMinimumHeight(400)
        controller.screenshot_label.setStyleSheet("""
            border: 1px solid #555555;
            background-color: #2a2a2a;
        """)
        screenshot_layout.addWidget(controller.screenshot_label)
        
        # Add both to the horizontal layout with equal space allocation
        history_screenshot_layout.addWidget(action_history_group, 1)
        history_screenshot_layout.addWidget(screenshot_group, 1)

        # Log output section
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)

        # Add a clear button
        controller.clear_logs_btn = QPushButton("Clear Logs")

        log_header_layout = QHBoxLayout()
        log_header_layout.addStretch()
        log_header_layout.addWidget(controller.clear_logs_btn)

        controller.log_output = QTextEdit()
        controller.log_output.setReadOnly(True)
        controller.log_output.setStyleSheet("background-color: #333333;")

        log_layout.addLayout(log_header_layout)
        log_layout.addWidget(controller.log_output)

        # Add all sections to the layout
        # Add step counter first, then status underneath
        layout.addLayout(step_layout)
        layout.addLayout(status_layout)
        # Add the side-by-side action history and screenshot layout with more space
        layout.addLayout(history_screenshot_layout, 2)  # Give more space to this section
        layout.addWidget(log_group, 1)  # Logs get less space

        return panel

    @staticmethod
    def _create_appium_settings_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        controls_handler: Any,
    ) -> QGroupBox:
        """Create the Appium settings group."""
        appium_group = QGroupBox("Appium Settings")
        appium_layout = QFormLayout(appium_group)

        config_widgets["APPIUM_SERVER_URL"] = QLabel()
        label_appium_url = QLabel("Server URL:")
        from config.urls import ServiceURLs
        from ui.strings import APPIUM_URL_TOOLTIP
        label_appium_url.setToolTip(tooltips.get("APPIUM_SERVER_URL", APPIUM_URL_TOOLTIP.format(url=ServiceURLs.APPIUM)))
        appium_layout.addRow(label_appium_url, config_widgets["APPIUM_SERVER_URL"])

        config_widgets["TARGET_DEVICE_UDID"] = QComboBox()
        label_device_udid = QLabel("Target Device UDID:")
        label_device_udid.setToolTip(tooltips["TARGET_DEVICE_UDID"])

        device_layout = QHBoxLayout()
        device_layout.addWidget(config_widgets["TARGET_DEVICE_UDID"])
        refresh_devices_btn = QPushButton("Refresh")
        controls_handler.refresh_devices_btn = refresh_devices_btn
        device_layout.addWidget(refresh_devices_btn)
        appium_layout.addRow(label_device_udid, device_layout)

        layout.addRow(appium_group)
        return appium_group

    @staticmethod
    def _create_app_settings_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
    ) -> QGroupBox:
        """Create the App settings group with health app selection."""
        app_group = QGroupBox("App Settings")
        app_layout = QFormLayout(app_group)

        # Health App Selector with Discovery Filter checkbox
        config_handler.health_app_dropdown = QComboBox()
        config_handler.health_app_dropdown.addItem(
            "Select target app (Scan first)", None
        )
        config_handler.health_app_dropdown.currentIndexChanged.connect(
            config_handler._on_health_app_selected
        )
        config_handler.health_app_dropdown.setToolTip(
            "Select a health-related app discovered on the device. Use button below to scan."
        )

        # Create a horizontal layout for dropdown and discovery filter checkbox
        health_app_layout = QHBoxLayout()
        health_app_layout.addWidget(config_handler.health_app_dropdown)
        
        # Health-only filter toggle (AI)
        # This controls whether the discovery script applies AI filtering to only show health-related apps
        config_widgets["USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY"] = QCheckBox("Health-only filter (AI)")
        config_widgets["USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY"].setToolTip(
            "If enabled, the scanner uses AI to keep only health-related apps (fitness, wellness, medical, medication, mental health)."
        )
        health_app_layout.addWidget(config_widgets["USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY"])
        
        app_layout.addRow(
            QLabel("Target Health App:"), health_app_layout
        )

        config_handler.refresh_apps_btn = QPushButton("Scan/Refresh Health Apps List")
        config_handler.refresh_apps_btn.setToolTip(
            "Scans the connected device for installed applications and filters for health-related ones using AI."
        )
        app_layout.addRow(config_handler.refresh_apps_btn)

        config_handler.app_scan_status_label = QLabel("App Scan: Idle")
        app_layout.addRow(QLabel("Scan Status:"), config_handler.app_scan_status_label)

        layout.addRow(app_group)
        return app_group

    @staticmethod
    def _create_ai_settings_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any = None,
    ) -> QGroupBox:
        """Create the AI settings group."""
        ai_group = QGroupBox("AI Settings")
        ai_layout = QFormLayout(ai_group)

        # AI Provider Selection
        config_widgets["AI_PROVIDER"] = QComboBox()
        # Use provider registry to get all available providers
        from domain.providers.registry import ProviderRegistry
        provider_names = ProviderRegistry.get_all_names()
        config_widgets["AI_PROVIDER"].addItems(provider_names)
        label_ai_provider = QLabel("AI Provider: ")
        label_ai_provider.setToolTip(
            "The AI model provider to use for analysis and decision making."
        )
        ai_layout.addRow(label_ai_provider, config_widgets["AI_PROVIDER"])

        # Create refresh button for OpenRouter models (hidden by default)
        config_widgets["OPENROUTER_REFRESH_BTN"] = QPushButton("Refresh models")
        config_widgets["OPENROUTER_REFRESH_BTN"].setToolTip(
            "Fetch latest models from OpenRouter API"
        )
        config_widgets["OPENROUTER_REFRESH_BTN"].setVisible(False)

        config_widgets["DEFAULT_MODEL_TYPE"] = QComboBox()
        # Start with explicit no-selection placeholder; provider change will populate
        try:
            from ui.strings import NO_MODEL_SELECTED
            config_widgets["DEFAULT_MODEL_TYPE"].addItem(NO_MODEL_SELECTED)
        except Exception:
            from ui.strings import NO_MODEL_SELECTED
            config_widgets["DEFAULT_MODEL_TYPE"].addItems([NO_MODEL_SELECTED])
        label_model_type = QLabel("Default Model Type: ")
        label_model_type.setToolTip(tooltips["DEFAULT_MODEL_TYPE"])
        # Place dropdown and refresh button side-by-side
        _model_row_layout = QHBoxLayout()
        _model_row_layout.addWidget(config_widgets["DEFAULT_MODEL_TYPE"])
        _model_row_layout.addWidget(config_widgets["OPENROUTER_REFRESH_BTN"])
        # Free-only filter (hidden by default; shown for OpenRouter)
        config_widgets["OPENROUTER_SHOW_FREE_ONLY"] = QCheckBox("Free only")
        config_widgets["OPENROUTER_SHOW_FREE_ONLY"].setToolTip(
            "Show only models with free pricing (0 cost)."
        )
        config_widgets["OPENROUTER_SHOW_FREE_ONLY"].setVisible(False)
        _model_row_layout.addWidget(config_widgets["OPENROUTER_SHOW_FREE_ONLY"])

        # Add a warning label for non-free models
        config_widgets["OPENROUTER_NON_FREE_WARNING"] = QLabel("⚠️ This model may use your OpenRouter credit.")
        config_widgets["OPENROUTER_NON_FREE_WARNING"].setStyleSheet("color: orange;")
        config_widgets["OPENROUTER_NON_FREE_WARNING"].setVisible(False)
        config_widgets["OPENROUTER_NON_FREE_WARNING"].setWordWrap(True)

        warning_layout = QVBoxLayout()
        warning_layout.addWidget(config_widgets["OPENROUTER_NON_FREE_WARNING"])

        ai_layout.addRow(label_model_type, _model_row_layout)
        ai_layout.addRow(warning_layout)

        # Connect the AI provider selection to update model types and toggle refresh visibility
        def _on_provider_changed(provider: str):
            UIComponents._update_model_types(provider, config_widgets, config_handler)
            from domain.providers.enums import AIProvider
            is_or = AIProvider.is_valid(provider) and AIProvider.from_string(provider) == AIProvider.OPENROUTER
            # Show OpenRouter controls only when OpenRouter is selected
            config_widgets["OPENROUTER_REFRESH_BTN"].setVisible(is_or)
            config_widgets["OPENROUTER_SHOW_FREE_ONLY"].setVisible(is_or)

        config_widgets["AI_PROVIDER"].currentTextChanged.connect(_on_provider_changed)

        # Wire up refresh button
        def _on_refresh_clicked():
            try:
                UIComponents._refresh_openrouter_models(config_handler, config_widgets)
            except Exception as e:
                logging.warning(f"Failed to refresh OpenRouter models: {e}")

        config_widgets["OPENROUTER_REFRESH_BTN"].clicked.connect(_on_refresh_clicked)

        # Wire up free-only filter to re-populate models
        def _on_free_only_changed(_state: int):
            try:
                current_provider = config_widgets["AI_PROVIDER"].currentText()
                from domain.providers.enums import AIProvider
                if AIProvider.is_valid(current_provider) and AIProvider.from_string(current_provider) == AIProvider.OPENROUTER:
                    UIComponents._update_model_types(current_provider, config_widgets, config_handler)
            except Exception as e:
                logging.debug(f"Failed to apply free-only filter: {e}")

        config_widgets["OPENROUTER_SHOW_FREE_ONLY"].stateChanged.connect(
            _on_free_only_changed
        )

        # Advanced manual model id entry removed; use dropdown-only selection

        # Enable Image Context moved here from Feature Toggles
        config_widgets["ENABLE_IMAGE_CONTEXT"] = QCheckBox()
        label_enable_image_context = QLabel("Enable Image Context: ")
        label_enable_image_context.setToolTip(
            "Enable sending screenshots to AI for visual analysis. Disable for text-only analysis."
        )

        # Warning label (used when auto-disabled by provider capabilities)
        config_widgets["IMAGE_CONTEXT_WARNING"] = QLabel("⚠️ Auto-disabled")
        config_widgets["IMAGE_CONTEXT_WARNING"].setStyleSheet(
            "color: #ff6b35; font-weight: bold;"
        )
        config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)

        # Horizontal layout for checkbox and warning
        image_context_layout = QHBoxLayout()
        image_context_layout.addWidget(label_enable_image_context)
        image_context_layout.addWidget(config_widgets["ENABLE_IMAGE_CONTEXT"])
        image_context_layout.addWidget(config_widgets["IMAGE_CONTEXT_WARNING"])
        image_context_layout.addStretch()
        ai_layout.addRow(image_context_layout)

        from config.numeric_constants import XML_SNIPPET_MAX_LEN_MIN, XML_SNIPPET_MAX_LEN_MAX
        config_widgets["XML_SNIPPET_MAX_LEN"] = QSpinBox()
        config_widgets["XML_SNIPPET_MAX_LEN"].setRange(XML_SNIPPET_MAX_LEN_MIN, XML_SNIPPET_MAX_LEN_MAX)
        label_xml_snippet_max_len = QLabel("XML Snippet Max Length: ")
        label_xml_snippet_max_len.setToolTip(tooltips["XML_SNIPPET_MAX_LEN"])
        ai_layout.addRow(
            label_xml_snippet_max_len, config_widgets["XML_SNIPPET_MAX_LEN"]
        )

        # Crawler Available Actions (read-only, managed via CLI: actions list/add/edit/remove)
        config_widgets["CRAWLER_AVAILABLE_ACTIONS"] = QTextEdit()
        config_widgets["CRAWLER_AVAILABLE_ACTIONS"].setMinimumHeight(120)
        config_widgets["CRAWLER_AVAILABLE_ACTIONS"].setMaximumHeight(180)
        config_widgets["CRAWLER_AVAILABLE_ACTIONS"].setReadOnly(True)  # Read-only, managed via CLI
        label_available_actions = QLabel("Available Actions: ")
        available_actions_tooltip = (
            "JSON dict defining which actions the crawler can use (read-only). "
            "Manage via CLI: 'python run_cli.py actions list/add/edit/remove'. "
            "Format: {\"action_name\": \"description\", ...}. "
            "Example: {\"click\": \"Click the element\", \"scroll_down\": \"Scroll down\"}"
        )
        label_available_actions.setToolTip(available_actions_tooltip)
        config_widgets["CRAWLER_AVAILABLE_ACTIONS"].setToolTip(available_actions_tooltip)
        ai_layout.addRow(label_available_actions, config_widgets["CRAWLER_AVAILABLE_ACTIONS"])
        
        # Crawler Action Decision Prompt (read-only, managed via CLI: prompts list/add/edit/remove)
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"] = QTextEdit()
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"].setMinimumHeight(120)
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"].setMaximumHeight(180)
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"].setReadOnly(True)  # Read-only, managed via CLI
        label_action_prompt = QLabel("Action Decision Prompt: ")
        action_prompt_tooltip = (
            "Prompt template for action decisions (read-only). "
            "Manage via CLI: 'python run_cli.py prompts list/add/edit/remove'. "
            "Name: ACTION_DECISION_PROMPT"
        )
        label_action_prompt.setToolTip(action_prompt_tooltip)
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"].setToolTip(action_prompt_tooltip)
        ai_layout.addRow(label_action_prompt, config_widgets["CRAWLER_ACTION_DECISION_PROMPT"])
        
        # Crawler System Prompt Template (read-only, managed via CLI: prompts list/add/edit/remove)
        config_widgets["CRAWLER_SYSTEM_PROMPT_TEMPLATE"] = QTextEdit()
        config_widgets["CRAWLER_SYSTEM_PROMPT_TEMPLATE"].setMinimumHeight(120)
        config_widgets["CRAWLER_SYSTEM_PROMPT_TEMPLATE"].setMaximumHeight(180)
        config_widgets["CRAWLER_SYSTEM_PROMPT_TEMPLATE"].setReadOnly(True)  # Read-only, managed via CLI
        label_system_prompt = QLabel("System Prompt Template: ")
        system_prompt_tooltip = (
            "System prompt template for the AI agent (read-only). "
            "Manage via CLI: 'python run_cli.py prompts list/add/edit/remove'. "
            "Name: SYSTEM_PROMPT_TEMPLATE"
        )
        label_system_prompt.setToolTip(system_prompt_tooltip)
        config_widgets["CRAWLER_SYSTEM_PROMPT_TEMPLATE"].setToolTip(system_prompt_tooltip)
        ai_layout.addRow(label_system_prompt, config_widgets["CRAWLER_SYSTEM_PROMPT_TEMPLATE"])

        layout.addRow(ai_group)
        return ai_group

    @staticmethod
    def _create_image_preprocessing_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
    ) -> QGroupBox:
        """Create the Image Preprocessing settings group."""
        group = QGroupBox("Image Preprocessing")
        form = QFormLayout(group)

        # Max width
        from config.numeric_constants import IMAGE_MAX_WIDTH_MIN, IMAGE_MAX_WIDTH_MAX
        config_widgets["IMAGE_MAX_WIDTH"] = QSpinBox()
        config_widgets["IMAGE_MAX_WIDTH"].setRange(IMAGE_MAX_WIDTH_MIN, IMAGE_MAX_WIDTH_MAX)
        label_max_width = QLabel("Max Screenshot Width (px): ")
        from ui.strings import MAX_SCREENSHOT_WIDTH_TOOLTIP
        label_max_width.setToolTip(tooltips.get("IMAGE_MAX_WIDTH", MAX_SCREENSHOT_WIDTH_TOOLTIP))
        form.addRow(label_max_width, config_widgets["IMAGE_MAX_WIDTH"])

        # Format
        config_widgets["IMAGE_FORMAT"] = QComboBox()
        config_widgets["IMAGE_FORMAT"].addItems(["JPEG", "WEBP", "PNG"])
        label_format = QLabel("Image Format: ")
        from ui.strings import IMAGE_FORMAT_TOOLTIP
        label_format.setToolTip(tooltips.get("IMAGE_FORMAT", IMAGE_FORMAT_TOOLTIP))
        form.addRow(label_format, config_widgets["IMAGE_FORMAT"])

        # Quality
        from config.numeric_constants import IMAGE_QUALITY_MIN, IMAGE_QUALITY_MAX
        config_widgets["IMAGE_QUALITY"] = QSpinBox()
        config_widgets["IMAGE_QUALITY"].setRange(IMAGE_QUALITY_MIN, IMAGE_QUALITY_MAX)
        label_quality = QLabel("Image Quality (%): ")
        from ui.strings import IMAGE_QUALITY_TOOLTIP
        label_quality.setToolTip(tooltips.get("IMAGE_QUALITY", IMAGE_QUALITY_TOOLTIP))
        form.addRow(label_quality, config_widgets["IMAGE_QUALITY"])

        # Crop bars toggle
        config_widgets["IMAGE_CROP_BARS"] = QCheckBox()
        label_crop_bars = QLabel("Crop Status/Navigation Bars: ")
        from ui.strings import CROP_BARS_TOOLTIP
        label_crop_bars.setToolTip(tooltips.get("IMAGE_CROP_BARS", CROP_BARS_TOOLTIP))
        form.addRow(label_crop_bars, config_widgets["IMAGE_CROP_BARS"])

        # Top crop percent
        from config.numeric_constants import CROP_PERCENT_MIN, CROP_PERCENT_MAX
        config_widgets["IMAGE_CROP_TOP_PERCENT"] = QSpinBox()
        config_widgets["IMAGE_CROP_TOP_PERCENT"].setRange(CROP_PERCENT_MIN, CROP_PERCENT_MAX)
        label_crop_top = QLabel("Top Crop (% of height): ")
        from ui.strings import CROP_TOP_PERCENT_TOOLTIP
        label_crop_top.setToolTip(tooltips.get("IMAGE_CROP_TOP_PERCENT", CROP_TOP_PERCENT_TOOLTIP))
        form.addRow(label_crop_top, config_widgets["IMAGE_CROP_TOP_PERCENT"])

        # Bottom crop percent
        config_widgets["IMAGE_CROP_BOTTOM_PERCENT"] = QSpinBox()
        config_widgets["IMAGE_CROP_BOTTOM_PERCENT"].setRange(CROP_PERCENT_MIN, CROP_PERCENT_MAX)
        label_crop_bottom = QLabel("Bottom Crop (% of height): ")
        from ui.strings import CROP_BOTTOM_PERCENT_TOOLTIP
        label_crop_bottom.setToolTip(tooltips.get("IMAGE_CROP_BOTTOM_PERCENT", CROP_BOTTOM_PERCENT_TOOLTIP))
        form.addRow(label_crop_bottom, config_widgets["IMAGE_CROP_BOTTOM_PERCENT"])

        layout.addRow(group)
        return group

    @staticmethod
    def _get_openrouter_cache_path() -> str:
        from domain.providers.registry import ProviderRegistry
        from domain.providers.enums import AIProvider
        
        provider = ProviderRegistry.get(AIProvider.OPENROUTER)
        if provider:
            return provider._get_cache_path()
        # Fallback if provider not available
        traverser_ai_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_dir = os.path.join(traverser_ai_api_dir, "output_data", "cache")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, "openrouter_models.json")

    @staticmethod
    def _load_openrouter_models_from_cache() -> Optional[list]:
        try:
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.OPENROUTER)
            if provider:
                # Create a dummy config for the provider method
                from config.app_config import Config
                config = Config()
                return provider._load_models_cache()
            return None
        except Exception as e:
            logging.debug(f"Failed to read OpenRouter cache: {e}")
            return None

    @staticmethod
    def _save_openrouter_models_to_cache(models: List[Dict[str, Any]]) -> None:
        try:
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.OPENROUTER)
            if provider:
                provider._save_models_to_cache(models)
        except Exception as e:
            logging.debug(f"Failed to save OpenRouter cache: {e}")

    @staticmethod
    def _is_openrouter_model_vision(model_id: str) -> bool:
        """Determine vision support using cache metadata; fallback to heuristics."""
        try:
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.OPENROUTER)
            if provider:
                return provider.is_model_vision(model_id)
            return False
        except Exception as e:
            logging.debug(f"Failed to determine vision support: {e}")
            return False

    @staticmethod
    def _refresh_openrouter_models(
        config_handler: Any, config_widgets: Dict[str, Any]
    ) -> None:
        # Disable refresh button and show busy overlay to indicate long-running operation
        btn = config_widgets.get("OPENROUTER_REFRESH_BTN")
        try:
            if btn:
                btn.setEnabled(False)
        except Exception:
            pass
        try:
            config_handler.main_controller.show_busy("Refreshing AI models...")
        except Exception:
            pass
        try:
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.OPENROUTER)
            if not provider:
                logging.warning("OpenRouter provider not found")
                return
            
            api_key = config_handler.config.get("OPENROUTER_API_KEY", None)
            if not api_key:
                logging.warning("OpenRouter refresh requested but API key is missing.")
                config_handler.main_controller.log_message(
                    "OpenRouter API key missing. Set OPENROUTER_API_KEY in .env.",
                    "orange",
                )
                return

            # Proactively delete any stale cache before fetching fresh data
            try:
                cache_path = UIComponents._get_openrouter_cache_path()
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                    logging.info("Deleted stale OpenRouter model cache before refresh.")
                    try:
                        config_handler.main_controller.log_message(
                            "Deleted local OpenRouter cache.", "gray"
                        )
                    except Exception:
                        pass
            except Exception as cache_err:
                logging.debug(f"Could not delete OpenRouter cache: {cache_err}")

            # Use provider to fetch and normalize models
            normalized = provider._fetch_models(api_key)
            
            if not normalized:
                raise RuntimeError("No models returned from OpenRouter")
            
            UIComponents._save_openrouter_models_to_cache(normalized)
            try:
                logging.info(f"Fetched {len(normalized)} OpenRouter models from API.")
            except Exception:
                pass
            config_handler.main_controller.log_message(
                f"Fetched {len(normalized)} OpenRouter models.", "green"
            )
            # Re-populate dropdown from cache
            UIComponents._update_model_types("openrouter", config_widgets, config_handler)
        except Exception as e:
            logging.warning(f"OpenRouter model fetch failed: {e}")
            try:
                config_handler.main_controller.log_message(
                    f"OpenRouter model fetch failed: {e}", "orange"
                )
            except Exception:
                pass
        finally:
            # Ensure the overlay is hidden and button re-enabled regardless of success or failure
            try:
                config_handler.main_controller.hide_busy()
            except Exception:
                pass
            try:
                if btn:
                    btn.setEnabled(True)
            except Exception:
                pass

    @staticmethod
    def _is_openrouter_model_free(model_meta: Any) -> bool:
        """Determine free status strictly using prompt/completion/image pricing and known indicators."""
        try:
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.OPENROUTER)
            if provider:
                return provider.is_model_free(model_meta)
            return False
        except Exception as e:
            logging.debug(f"Failed to determine free status: {e}")
            return False

    @staticmethod
    def _get_openrouter_model_meta(model_id: str) -> Optional[Dict[str, Any]]:
        """Lookup a model's metadata by id from the cache (supports both schemas)."""
        try:
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            
            provider = ProviderRegistry.get(AIProvider.OPENROUTER)
            if provider:
                return provider.get_model_meta(model_id)
            return None
        except Exception as e:
            logging.debug(f"Failed to lookup model meta: {e}")
            return None

    @staticmethod
    def _background_refresh_openrouter_models() -> None:
        """Background refresh delegating to provider (UI-agnostic)."""
        try:
            from domain.providers.registry import ProviderRegistry
            from domain.providers.enums import AIProvider
            from config.app_config import Config
            
            provider = ProviderRegistry.get(AIProvider.OPENROUTER)
            if provider:
                config = Config()
                provider.refresh_models(config, wait_for_completion=False)
        except Exception as e:
            logging.debug(f"Failed to queue background OpenRouter refresh: {e}")

    @staticmethod
    def _create_focus_areas_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
    ) -> QGroupBox:
        """Create the Focus Areas group."""
        focus_group = QGroupBox("AI Privacy Focus Areas")
        focus_layout = QVBoxLayout(focus_group)

        # Import the focus areas widget
        try:
            from ui.focus_areas_widget import FocusAreasWidget
        except ImportError:
            from ui.focus_areas_widget import FocusAreasWidget

        # Try to get focus service from main controller
        focus_service = None
        try:
            if hasattr(config_handler, 'main_controller'):
                main_controller = config_handler.main_controller
                if hasattr(main_controller, 'focus_service'):
                    focus_service = main_controller.focus_service
        except Exception as e:
            logging.warning(f"Could not get focus_service from main_controller: {e}")

        # Load focus areas from config
        focus_areas_data = config_handler.config.get("FOCUS_AREAS", None)

        # Start with empty list - users must add focus areas through CRUD operations
        # If config has saved focus areas, load them
        if focus_areas_data:
            # Convert to proper format if needed
            pass
        else:
            focus_areas_data = []

        # Create the focus areas widget
        focus_widget = FocusAreasWidget(focus_areas_data, parent=None, focus_service=focus_service)
        focus_layout.addWidget(focus_widget)

        # Store reference for later access
        # Note: Focus areas are persisted directly through FocusAreaService when CRUD operations occur
        config_handler.focus_areas_widget = focus_widget

        layout.addRow(focus_group)
        return focus_group

    @staticmethod
    def _create_crawler_settings_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Crawler settings group."""
        crawler_group = QGroupBox("Crawler Settings")
        crawler_layout = QFormLayout(crawler_group)

        config_widgets["CRAWL_MODE"] = QComboBox()
        config_widgets["CRAWL_MODE"].addItems(["steps", "time"])
        label_crawl_mode = QLabel("Crawl Mode: ")
        label_crawl_mode.setToolTip(tooltips["CRAWL_MODE"])
        crawler_layout.addRow(label_crawl_mode, config_widgets["CRAWL_MODE"])

        from config.numeric_constants import MAX_CRAWL_STEPS_MIN, MAX_CRAWL_STEPS_MAX
        config_widgets["MAX_CRAWL_STEPS"] = QSpinBox()
        config_widgets["MAX_CRAWL_STEPS"].setRange(MAX_CRAWL_STEPS_MIN, MAX_CRAWL_STEPS_MAX)
        label_max_crawl_steps = QLabel("Max Steps: ")
        label_max_crawl_steps.setToolTip(tooltips["MAX_CRAWL_STEPS"])
        crawler_layout.addRow(label_max_crawl_steps, config_widgets["MAX_CRAWL_STEPS"])

        from config.numeric_constants import MAX_CRAWL_DURATION_MIN_SECONDS, MAX_CRAWL_DURATION_MAX_SECONDS
        config_widgets["MAX_CRAWL_DURATION_SECONDS"] = QSpinBox()
        config_widgets["MAX_CRAWL_DURATION_SECONDS"].setRange(MAX_CRAWL_DURATION_MIN_SECONDS, MAX_CRAWL_DURATION_MAX_SECONDS)
        label_max_crawl_duration = QLabel("Max Duration (s): ")
        label_max_crawl_duration.setToolTip(tooltips["MAX_CRAWL_DURATION_SECONDS"])
        crawler_layout.addRow(
            label_max_crawl_duration, config_widgets["MAX_CRAWL_DURATION_SECONDS"]
        )

        config_widgets["WAIT_AFTER_ACTION"] = QSpinBox()
        config_widgets["WAIT_AFTER_ACTION"].setRange(0, 60)
        label_wait_after_action = QLabel("Wait After Action (s): ")
        label_wait_after_action.setToolTip(tooltips["WAIT_AFTER_ACTION"])
        crawler_layout.addRow(
            label_wait_after_action, config_widgets["WAIT_AFTER_ACTION"]
        )

        config_widgets["STABILITY_WAIT"] = QSpinBox()
        config_widgets["STABILITY_WAIT"].setRange(0, 60)
        label_stability_wait = QLabel("Stability Wait (s): ")
        label_stability_wait.setToolTip(tooltips["STABILITY_WAIT"])
        crawler_layout.addRow(label_stability_wait, config_widgets["STABILITY_WAIT"])

        from config.numeric_constants import APP_LAUNCH_WAIT_TIME_MIN, APP_LAUNCH_WAIT_TIME_MAX
        config_widgets["APP_LAUNCH_WAIT_TIME"] = QSpinBox()
        config_widgets["APP_LAUNCH_WAIT_TIME"].setRange(APP_LAUNCH_WAIT_TIME_MIN, APP_LAUNCH_WAIT_TIME_MAX)
        label_app_launch_wait_time = QLabel("App Launch Wait Time (s): ")
        label_app_launch_wait_time.setToolTip(tooltips["APP_LAUNCH_WAIT_TIME"])
        crawler_layout.addRow(
            label_app_launch_wait_time, config_widgets["APP_LAUNCH_WAIT_TIME"]
        )

        # Visual Similarity Threshold
        from config.numeric_constants import VISUAL_SIMILARITY_THRESHOLD_MIN, VISUAL_SIMILARITY_THRESHOLD_MAX
        config_widgets["VISUAL_SIMILARITY_THRESHOLD"] = QSpinBox()
        config_widgets["VISUAL_SIMILARITY_THRESHOLD"].setRange(VISUAL_SIMILARITY_THRESHOLD_MIN, VISUAL_SIMILARITY_THRESHOLD_MAX)
        label_visual_similarity = QLabel("Visual Similarity Threshold: ")
        label_visual_similarity.setToolTip(tooltips["VISUAL_SIMILARITY_THRESHOLD"])
        crawler_layout.addRow(
            label_visual_similarity, config_widgets["VISUAL_SIMILARITY_THRESHOLD"]
        )

        # Allowed External Packages - Use dedicated widget with CRUD support
        from ui.allowed_packages_widget import AllowedPackagesWidget
        from config.app_config import Config
        config = Config()
        config_widgets["ALLOWED_EXTERNAL_PACKAGES_WIDGET"] = AllowedPackagesWidget(config)
        # Store a reference to the widget for compatibility with config manager
        config_widgets["ALLOWED_EXTERNAL_PACKAGES"] = config_widgets["ALLOWED_EXTERNAL_PACKAGES_WIDGET"]
        crawler_layout.addRow(config_widgets["ALLOWED_EXTERNAL_PACKAGES_WIDGET"])

        layout.addRow(crawler_group)
        return crawler_group

    @staticmethod
    def _create_error_handling_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Error Handling settings group."""
        error_handling_group = QGroupBox("Error Handling Settings")
        error_handling_layout = QFormLayout(error_handling_group)

        from config.numeric_constants import MAX_CONSECUTIVE_FAILURES_MIN, MAX_CONSECUTIVE_FAILURES_MAX
        config_widgets["MAX_CONSECUTIVE_AI_FAILURES"] = QSpinBox()
        config_widgets["MAX_CONSECUTIVE_AI_FAILURES"].setRange(MAX_CONSECUTIVE_FAILURES_MIN, MAX_CONSECUTIVE_FAILURES_MAX)
        label_max_ai_failures = QLabel("Max Consecutive AI Failures: ")
        label_max_ai_failures.setToolTip(tooltips["MAX_CONSECUTIVE_AI_FAILURES"])
        error_handling_layout.addRow(
            label_max_ai_failures, config_widgets["MAX_CONSECUTIVE_AI_FAILURES"]
        )

        config_widgets["MAX_CONSECUTIVE_MAP_FAILURES"] = QSpinBox()
        config_widgets["MAX_CONSECUTIVE_MAP_FAILURES"].setRange(MAX_CONSECUTIVE_FAILURES_MIN, MAX_CONSECUTIVE_FAILURES_MAX)
        label_max_map_failures = QLabel("Max Consecutive Map Failures: ")
        label_max_map_failures.setToolTip(tooltips["MAX_CONSECUTIVE_MAP_FAILURES"])
        error_handling_layout.addRow(
            label_max_map_failures, config_widgets["MAX_CONSECUTIVE_MAP_FAILURES"]
        )

        config_widgets["MAX_CONSECUTIVE_EXEC_FAILURES"] = QSpinBox()
        config_widgets["MAX_CONSECUTIVE_EXEC_FAILURES"].setRange(MAX_CONSECUTIVE_FAILURES_MIN, MAX_CONSECUTIVE_FAILURES_MAX)
        label_max_exec_failures = QLabel("Max Consecutive Exec Failures: ")
        label_max_exec_failures.setToolTip(tooltips["MAX_CONSECUTIVE_EXEC_FAILURES"])
        error_handling_layout.addRow(
            label_max_exec_failures, config_widgets["MAX_CONSECUTIVE_EXEC_FAILURES"]
        )

        layout.addRow(error_handling_group)
        return error_handling_group

    @staticmethod
    def _create_run_control_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Run Control group for session-related controls."""
        run_control_group = QGroupBox("Run Control")
        run_control_layout = QFormLayout(run_control_group)

        config_widgets["CONTINUE_EXISTING_RUN"] = QCheckBox()
        label_continue_run = QLabel("Continue Existing Run: ")
        label_continue_run.setToolTip(tooltips["CONTINUE_EXISTING_RUN"])
        run_control_layout.addRow(
            label_continue_run, config_widgets["CONTINUE_EXISTING_RUN"]
        )

        layout.addRow(run_control_group)
        return run_control_group

    @staticmethod
    def _create_recording_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Recording group for media capture settings."""
        recording_group = QGroupBox("Recording")
        recording_layout = QFormLayout(recording_group)

        config_widgets["ENABLE_VIDEO_RECORDING"] = QCheckBox()
        label_enable_video = QLabel("Enable Video Recording: ")
        recording_layout.addRow(
            label_enable_video, config_widgets["ENABLE_VIDEO_RECORDING"]
        )

        layout.addRow(recording_group)
        return recording_group

    @staticmethod
    def _create_privacy_network_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Privacy & Network group for traffic capture-related settings."""
        privacy_group = QGroupBox("Privacy & Network")
        privacy_layout = QFormLayout(privacy_group)

        # Traffic capture toggles moved from Feature Toggles
        config_widgets["ENABLE_TRAFFIC_CAPTURE"] = QCheckBox()
        label_enable_traffic_capture = QLabel("Enable Traffic Capture: ")
        label_enable_traffic_capture.setToolTip(tooltips["ENABLE_TRAFFIC_CAPTURE"])
        privacy_layout.addRow(
            label_enable_traffic_capture, config_widgets["ENABLE_TRAFFIC_CAPTURE"]
        )

        config_widgets["CLEANUP_DEVICE_PCAP_FILE"] = QCheckBox()
        label_cleanup_pcap = QLabel("Cleanup Device PCAP after Pull: ")
        label_cleanup_pcap.setToolTip(tooltips["CLEANUP_DEVICE_PCAP_FILE"])
        privacy_layout.addRow(
            label_cleanup_pcap, config_widgets["CLEANUP_DEVICE_PCAP_FILE"]
        )

        layout.addRow(privacy_group)
        return privacy_group

    @staticmethod
    def _create_mobsf_settings_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
    ) -> QGroupBox:
        """Create the MobSF settings group."""
        mobsf_group = QGroupBox("MobSF Static Analysis")
        mobsf_layout = QFormLayout(mobsf_group)

        # MobSF Enable Checkbox
        config_widgets["ENABLE_MOBSF_ANALYSIS"] = QCheckBox()
        label_enable_mobsf = QLabel("Enable MobSF Analysis: ")
        label_enable_mobsf.setToolTip(tooltips["ENABLE_MOBSF_ANALYSIS"])
        mobsf_layout.addRow(label_enable_mobsf, config_widgets["ENABLE_MOBSF_ANALYSIS"])

        # Get current enabled state (default to False if not set)
        is_mobsf_enabled = getattr(
            config_handler.config, "ENABLE_MOBSF_ANALYSIS", False
        )
        config_widgets["ENABLE_MOBSF_ANALYSIS"].setChecked(is_mobsf_enabled)
        logging.debug(f"Setting initial MobSF checkbox state: {is_mobsf_enabled}")

        # API URL field
        from config.urls import ServiceURLs
        config_widgets["MOBSF_API_URL"] = QLineEdit()
        from ui.strings import MOBSF_API_URL_PLACEHOLDER
        config_widgets["MOBSF_API_URL"].setPlaceholderText(MOBSF_API_URL_PLACEHOLDER)
        label_mobsf_api_url = QLabel("MobSF API URL: ")
        label_mobsf_api_url.setToolTip(tooltips["MOBSF_API_URL"])
        mobsf_layout.addRow(label_mobsf_api_url, config_widgets["MOBSF_API_URL"])

        config_widgets["MOBSF_API_KEY"] = QLineEdit()
        from ui.strings import MOBSF_API_KEY_PLACEHOLDER
        config_widgets["MOBSF_API_KEY"].setPlaceholderText(MOBSF_API_KEY_PLACEHOLDER)
        config_widgets["MOBSF_API_KEY"].setEchoMode(QLineEdit.EchoMode.Password)
        label_mobsf_api_key = QLabel("MobSF API Key: ")
        label_mobsf_api_key.setToolTip(tooltips["MOBSF_API_KEY"])
        mobsf_layout.addRow(label_mobsf_api_key, config_widgets["MOBSF_API_KEY"])

        # MobSF test and analysis buttons - assign to main_controller instead of config_handler
        main_controller = config_handler.main_controller
        main_controller.test_mobsf_conn_btn = QPushButton("Test MobSF Connection")
        mobsf_layout.addRow(main_controller.test_mobsf_conn_btn)
        logging.debug("Created test_mobsf_conn_btn directly on main_controller")

        main_controller.run_mobsf_analysis_btn = QPushButton("Run MobSF Analysis")
        mobsf_layout.addRow(main_controller.run_mobsf_analysis_btn)
        logging.debug("Created run_mobsf_analysis_btn directly on main_controller")

        # Set initial button states based on checkbox
        main_controller.test_mobsf_conn_btn.setEnabled(is_mobsf_enabled)
        main_controller.run_mobsf_analysis_btn.setEnabled(is_mobsf_enabled)

        # Connect the checkbox to update button state - using a direct slot reference
        # Connect after buttons are created
        config_widgets["ENABLE_MOBSF_ANALYSIS"].stateChanged.connect(
            config_handler._on_mobsf_enabled_state_changed
        )

        layout.addRow(mobsf_group)
        return mobsf_group

    @staticmethod
    def _create_control_buttons(controls_handler: Any) -> QGroupBox:
        """Create the control buttons group."""
        group = QGroupBox("Controls")
        layout = QHBoxLayout(group)

        controls_handler.start_btn = QPushButton("Start Crawler")
        controls_handler.stop_btn = QPushButton("Stop Crawler")
        controls_handler.stop_btn.setEnabled(False)

        # Add pre-check button
        pre_check_btn = QPushButton("🔍 Pre-Check Services")
        pre_check_btn.setToolTip(
            "Check the status of all required services (Appium, Ollama, MobSF) before starting"
        )
        pre_check_btn.clicked.connect(controls_handler.perform_pre_crawl_validation)

        # Add generate report button
        controls_handler.generate_report_btn = QPushButton("📄 Generate Report (PDF)")
        controls_handler.generate_report_btn.setToolTip(
            "Create an analysis PDF for the latest run in the current session"
        )
        # Enabled by default; will be disabled during crawling and re-enabled on finish
        controls_handler.generate_report_btn.setEnabled(True)
        controls_handler.generate_report_btn.clicked.connect(controls_handler.generate_report)

        controls_handler.start_btn.clicked.connect(controls_handler.start_crawler)
        controls_handler.stop_btn.clicked.connect(controls_handler.stop_crawler)

        layout.addWidget(pre_check_btn)
        layout.addWidget(controls_handler.generate_report_btn)
        layout.addWidget(controls_handler.start_btn)
        layout.addWidget(controls_handler.stop_btn)

        return group
