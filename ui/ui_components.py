# ui/components.py - UI components for the Appium Crawler Controller

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
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


class ComponentFactory:
    """Factory class for creating UI components used in the Crawler Controller."""


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
        from ui.constants import UI_MODE_BASIC, UI_MODE_EXPERT, UI_MODE_DEFAULT, UI_MODE_CONFIG_KEY
        mode_layout = QHBoxLayout()
        mode_label = QLabel("UI Mode:")
        config_handler.ui_mode_dropdown = QComboBox()
        config_handler.ui_mode_dropdown.addItems([
            UI_MODE_BASIC,
            UI_MODE_EXPERT
        ])

        # Get the UI mode from config
        initial_mode = UI_MODE_DEFAULT  # Default if not found

        # Try to get UI_MODE from the Config object's SQLite store
        try:
            stored_mode = config_handler.main_controller.config.get(UI_MODE_CONFIG_KEY)
            if stored_mode:
                initial_mode = stored_mode
                logging.debug(f"Setting initial UI mode from SQLite config store: {initial_mode}")
        except Exception as e:
            logging.warning(f"Error retrieving {UI_MODE_CONFIG_KEY} from config store: {e}")

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
        # Note: This will be connected to UIStateHandler in CrawlerControllerWindow
        pass

        # Create scrollable area for config inputs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QFormLayout(scroll_content)

        # Store scroll_content in config_handler for later reference
        config_handler.scroll_content = scroll_content

        # Create the config inputs sections
        appium_group = ComponentFactory.create_appium_settings_group(
            scroll_layout, config_widgets, tooltips, controls_handler
        )
        appium_group.setObjectName("appium_settings_group")

        app_group = ComponentFactory.create_app_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        app_group.setObjectName("app_settings_group")

        ai_group = ComponentFactory.create_ai_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        ai_group.setObjectName("ai_settings_group")

        # Image Preprocessing placed directly after AI for clearer perception grouping
        image_prep_group = ComponentFactory.create_image_preprocessing_group(
            scroll_layout, config_widgets, tooltips
        )
        image_prep_group.setObjectName("image_preprocessing_group")

        focus_areas_group = ComponentFactory.create_focus_areas_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        focus_areas_group.setObjectName("focus_areas_group")

        crawler_group = ComponentFactory.create_crawler_settings_group(
            scroll_layout, config_widgets, tooltips
        )
        crawler_group.setObjectName("crawler_settings_group")

        # Privacy & Network settings (traffic capture)
        privacy_network_group = ComponentFactory.create_privacy_network_group(
            scroll_layout, config_widgets, tooltips
        )
        privacy_network_group.setObjectName("privacy_network_group")

        # API Keys group (must be created before MobSF group for visibility control)
        api_keys_group = ComponentFactory.create_api_keys_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        api_keys_group.setObjectName("api_keys_group")

        mobsf_group = ComponentFactory.create_mobsf_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        mobsf_group.setObjectName("mobsf_settings_group")

        # Recording group
        recording_group = ComponentFactory.create_recording_group(
            scroll_layout, config_widgets, tooltips
        )
        recording_group.setObjectName("recording_group")

        # Error Handling group (at the bottom)
        error_handling_group = ComponentFactory.create_error_handling_group(
            scroll_layout, config_widgets, tooltips
        )
        error_handling_group.setObjectName("error_handling_group")

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
            "privacy_network_group": privacy_network_group,
            "api_keys_group": api_keys_group,
            "mobsf_settings_group": mobsf_group,
            "recording_group": recording_group,
            "error_handling_group": error_handling_group,
        }

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Add control buttons
        controls_group = ComponentFactory.create_control_buttons(controls_handler)
        layout.addWidget(controls_group)

        # Initialize the UI complexity based on the mode we determined
        # Note: This will be handled by UIStateHandler in CrawlerControllerWindow
        pass

        # Connect all widgets to auto-save
        config_handler.connect_widgets_for_auto_save()

        return panel


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
        main_layout = QVBoxLayout(panel)

        # Step counter and status at the top (small header)
        header_layout = QHBoxLayout()
        controller.step_label = QLabel("Step: 0")
        controller.status_label = QLabel("Status: Idle")
        controller.progress_bar = QProgressBar()
        header_layout.addWidget(controller.step_label)
        header_layout.addWidget(controller.status_label)
        header_layout.addWidget(controller.progress_bar)
        main_layout.addLayout(header_layout)

        # Main content area: Logs on left (2/3), Screenshot + Action History stacked on right (1/3)
        content_layout = QHBoxLayout()

        # Logs section - takes 2/3 of width and most of vertical space
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

        # Right side: Screenshot and Action History stacked vertically
        right_side_layout = QVBoxLayout()

        # Screenshot display (top right) - wider than tall
        screenshot_group = QGroupBox("Current Screenshot")
        screenshot_layout = QVBoxLayout(screenshot_group)
        controller.screenshot_label = QLabel()
        controller.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controller.screenshot_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        controller.screenshot_label.setMinimumHeight(300)
        controller.screenshot_label.setMinimumWidth(300)
        controller.screenshot_label.setStyleSheet("""
            border: 1px solid #555555;
            background-color: #2a2a2a;
        """)
        screenshot_layout.addWidget(controller.screenshot_label)

        # Action history (bottom right) - small, square or slightly taller
        action_history_group = QGroupBox("Action History")
        action_history_layout = QVBoxLayout(action_history_group)
        controller.action_history = QTextEdit()
        controller.action_history.setReadOnly(True)
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
        # Action history - small size
        controller.action_history.setMinimumHeight(150)
        controller.action_history.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        action_history_layout.addWidget(controller.action_history)

        # Add screenshot and action history to right side layout
        right_side_layout.addWidget(screenshot_group, 2)  # Screenshot gets more space
        right_side_layout.addWidget(action_history_group, 1)  # Action history gets less space

        # Add logs (left, 2/3) and right side (1/3) to content layout
        content_layout.addWidget(log_group, 2)  # Logs take 2/3 of width
        content_layout.addLayout(right_side_layout, 1)  # Right side takes 1/3 of width

        # Add content layout to main layout
        main_layout.addLayout(content_layout, 1)  # Content takes all remaining vertical space

        return panel

    @staticmethod
    def create_appium_settings_group(
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
    def create_app_settings_group(
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
    def create_ai_settings_group(
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

        # Create refresh button for models (visible for all providers)
        config_widgets["OPENROUTER_REFRESH_BTN"] = QPushButton("Refresh models")
        config_widgets["OPENROUTER_REFRESH_BTN"].setToolTip(
            "Fetch latest models from the selected AI provider"
        )
        config_widgets["OPENROUTER_REFRESH_BTN"].setVisible(True)

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
        # Free-only filter (visible for all providers)
        config_widgets["OPENROUTER_SHOW_FREE_ONLY"] = QCheckBox("Free only")
        config_widgets["OPENROUTER_SHOW_FREE_ONLY"].setToolTip(
            "Show only models with free pricing (0 cost)."
        )
        config_widgets["OPENROUTER_SHOW_FREE_ONLY"].setVisible(True)
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

        # Connect the AI provider selection to update model types
        # Note: These connections will be set up in CrawlerControllerWindow after UIStateHandler is created
        # The callbacks will be connected to UIStateHandler methods
        pass

        # Advanced manual model id entry removed; use dropdown-only selection

        # Enable Image Context has been moved to Image Preprocessing section

        from config.numeric_constants import XML_SNIPPET_MAX_LEN_MIN, XML_SNIPPET_MAX_LEN_MAX
        config_widgets["XML_SNIPPET_MAX_LEN"] = QSpinBox()
        config_widgets["XML_SNIPPET_MAX_LEN"].setRange(XML_SNIPPET_MAX_LEN_MIN, XML_SNIPPET_MAX_LEN_MAX)
        label_xml_snippet_max_len = QLabel("XML Snippet Max Length: ")
        label_xml_snippet_max_len.setToolTip(tooltips["XML_SNIPPET_MAX_LEN"])
        ai_layout.addRow(
            label_xml_snippet_max_len, config_widgets["XML_SNIPPET_MAX_LEN"]
        )

        # Crawler Available Actions (checkable list, managed via CLI: actions list/add/edit/remove)
        from ui.available_actions_widget import AvailableActionsWidget
        # Get actions service for the widget
        actions_service = None
        if config_handler:
            try:
                actions_service = config_handler._get_actions_service()
            except Exception as e:
                logging.debug(f"Could not get actions service for widget: {e}")
        
        config_widgets["CRAWLER_AVAILABLE_ACTIONS"] = AvailableActionsWidget(
            actions_service=actions_service,
            parent=ai_group
        )
        label_available_actions = QLabel("Available Actions: ")
        available_actions_tooltip = (
            "Select which actions the crawler can use. "
            "Unchecked actions will be disabled for the AI model. "
            "Manage actions via CLI: 'python run_cli.py actions list/add/edit/remove'. "
            "Only enabled actions will be shown to the AI model."
        )
        label_available_actions.setToolTip(available_actions_tooltip)
        config_widgets["CRAWLER_AVAILABLE_ACTIONS"].setToolTip(available_actions_tooltip)
        ai_layout.addRow(label_available_actions, config_widgets["CRAWLER_AVAILABLE_ACTIONS"])
        
        # Crawler Action Decision Prompt (editable, saved to SQLite)
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"] = QTextEdit()
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"].setMinimumHeight(120)
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"].setMaximumHeight(180)
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"].setReadOnly(False)  # Editable, saved to SQLite
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"].setStyleSheet("""
            QTextEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #555555;
            }
        """)
        label_action_prompt = QLabel("Action Decision Prompt: ")
        action_prompt_tooltip = (
            "Custom instructions for the AI agent (editable). "
            "The JSON schema and available actions list are automatically appended by the system. "
            "Editable in UI or via CLI: 'python run_cli.py prompts list/add/edit/remove'. "
            "Name: ACTION_DECISION_PROMPT. Changes are saved to SQLite database."
        )
        label_action_prompt.setToolTip(action_prompt_tooltip)
        config_widgets["CRAWLER_ACTION_DECISION_PROMPT"].setToolTip(action_prompt_tooltip)
        ai_layout.addRow(label_action_prompt, config_widgets["CRAWLER_ACTION_DECISION_PROMPT"])

        # Add Focus Areas as a subsection within AI Settings
        focus_areas_widget = ComponentFactory._create_focus_areas_widget(
            config_handler
        )
        label_focus_areas = QLabel("Privacy Focus Areas: ")
        focus_areas_tooltip = (
            "Configure what privacy aspects the AI agent should focus on during exploration. "
            "Drag items to reorder priority, toggle checkboxes to enable/disable."
        )
        label_focus_areas.setToolTip(focus_areas_tooltip)
        ai_layout.addRow(label_focus_areas, focus_areas_widget)

        layout.addRow(ai_group)
        return ai_group

    @staticmethod
    def create_image_preprocessing_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
    ) -> QGroupBox:
        """Create the Image Preprocessing settings group."""
        from PySide6.QtWidgets import QHBoxLayout
        from ui.strings import IMAGE_CONTEXT_ENABLED_TOOLTIP
        
        group = QGroupBox("Image Preprocessing")
        form = QFormLayout(group)

        # Enable Image Context checkbox - placed at the top as the main control
        config_widgets["ENABLE_IMAGE_CONTEXT"] = QCheckBox()
        label_enable_image_context = QLabel("Enable Image Context: ")
        # Use enhanced tooltip that explains the relationship with other options
        enhanced_tooltip = (
            "Enable sending screenshots to the AI for visual analysis. "
            "Disable for text-only analysis using XML only. "
            "The options below only apply when this option is enabled."
        )
        label_enable_image_context.setToolTip(enhanced_tooltip)
        config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(enhanced_tooltip)

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
        form.addRow(image_context_layout)

        # Store references to preprocessing option widgets and labels for visibility control
        preprocessing_widgets = []
        preprocessing_labels = []

        # Max width
        from config.numeric_constants import IMAGE_MAX_WIDTH_MIN, IMAGE_MAX_WIDTH_MAX
        config_widgets["IMAGE_MAX_WIDTH"] = QSpinBox()
        config_widgets["IMAGE_MAX_WIDTH"].setRange(IMAGE_MAX_WIDTH_MIN, IMAGE_MAX_WIDTH_MAX)
        label_max_width = QLabel("Max Screenshot Width (px): ")
        from ui.strings import MAX_SCREENSHOT_WIDTH_TOOLTIP
        label_max_width.setToolTip(tooltips.get("IMAGE_MAX_WIDTH", MAX_SCREENSHOT_WIDTH_TOOLTIP))
        form.addRow(label_max_width, config_widgets["IMAGE_MAX_WIDTH"])
        preprocessing_widgets.append(config_widgets["IMAGE_MAX_WIDTH"])
        preprocessing_labels.append(label_max_width)

        # Format
        config_widgets["IMAGE_FORMAT"] = QComboBox()
        config_widgets["IMAGE_FORMAT"].addItems(["JPEG", "WEBP", "PNG"])
        label_format = QLabel("Image Format: ")
        from ui.strings import IMAGE_FORMAT_TOOLTIP
        label_format.setToolTip(tooltips.get("IMAGE_FORMAT", IMAGE_FORMAT_TOOLTIP))
        form.addRow(label_format, config_widgets["IMAGE_FORMAT"])
        preprocessing_widgets.append(config_widgets["IMAGE_FORMAT"])
        preprocessing_labels.append(label_format)

        # Quality
        from config.numeric_constants import IMAGE_QUALITY_MIN, IMAGE_QUALITY_MAX
        config_widgets["IMAGE_QUALITY"] = QSpinBox()
        config_widgets["IMAGE_QUALITY"].setRange(IMAGE_QUALITY_MIN, IMAGE_QUALITY_MAX)
        label_quality = QLabel("Image Quality (%): ")
        from ui.strings import IMAGE_QUALITY_TOOLTIP
        label_quality.setToolTip(tooltips.get("IMAGE_QUALITY", IMAGE_QUALITY_TOOLTIP))
        form.addRow(label_quality, config_widgets["IMAGE_QUALITY"])
        preprocessing_widgets.append(config_widgets["IMAGE_QUALITY"])
        preprocessing_labels.append(label_quality)

        # Crop bars toggle
        config_widgets["IMAGE_CROP_BARS"] = QCheckBox()
        label_crop_bars = QLabel("Crop Status/Navigation Bars: ")
        from ui.strings import CROP_BARS_TOOLTIP
        label_crop_bars.setToolTip(tooltips.get("IMAGE_CROP_BARS", CROP_BARS_TOOLTIP))
        form.addRow(label_crop_bars, config_widgets["IMAGE_CROP_BARS"])
        preprocessing_widgets.append(config_widgets["IMAGE_CROP_BARS"])
        preprocessing_labels.append(label_crop_bars)

        # Top crop percent
        from config.numeric_constants import CROP_PERCENT_MIN, CROP_PERCENT_MAX
        config_widgets["IMAGE_CROP_TOP_PERCENT"] = QSpinBox()
        config_widgets["IMAGE_CROP_TOP_PERCENT"].setRange(CROP_PERCENT_MIN, CROP_PERCENT_MAX)
        label_crop_top = QLabel("Top Crop (% of height): ")
        from ui.strings import CROP_TOP_PERCENT_TOOLTIP
        label_crop_top.setToolTip(tooltips.get("IMAGE_CROP_TOP_PERCENT", CROP_TOP_PERCENT_TOOLTIP))
        form.addRow(label_crop_top, config_widgets["IMAGE_CROP_TOP_PERCENT"])
        preprocessing_widgets.append(config_widgets["IMAGE_CROP_TOP_PERCENT"])
        preprocessing_labels.append(label_crop_top)

        # Bottom crop percent
        config_widgets["IMAGE_CROP_BOTTOM_PERCENT"] = QSpinBox()
        config_widgets["IMAGE_CROP_BOTTOM_PERCENT"].setRange(CROP_PERCENT_MIN, CROP_PERCENT_MAX)
        label_crop_bottom = QLabel("Bottom Crop (% of height): ")
        from ui.strings import CROP_BOTTOM_PERCENT_TOOLTIP
        label_crop_bottom.setToolTip(tooltips.get("IMAGE_CROP_BOTTOM_PERCENT", CROP_BOTTOM_PERCENT_TOOLTIP))
        form.addRow(label_crop_bottom, config_widgets["IMAGE_CROP_BOTTOM_PERCENT"])
        preprocessing_widgets.append(config_widgets["IMAGE_CROP_BOTTOM_PERCENT"])
        preprocessing_labels.append(label_crop_bottom)

        # Store references for visibility control (attached to group as custom property)
        group.preprocessing_widgets = preprocessing_widgets
        group.preprocessing_labels = preprocessing_labels

        layout.addRow(group)
        return group





    @staticmethod
    def _create_focus_areas_widget(config_handler: Any) -> QWidget:
        """Create the Focus Areas widget (used as a subsection within AI Settings)."""
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

        # Load focus areas from user store (full data with id, name, description, etc.)
        try:
            focus_areas_data = config_handler.config._user_store.get_focus_areas_full()
            if not focus_areas_data:
                focus_areas_data = []
        except Exception as e:
            logging.warning(f"Could not load focus areas from user store: {e}")
            focus_areas_data = []

        # Create the focus areas widget
        focus_widget = FocusAreasWidget(focus_areas_data, parent=None, focus_service=focus_service)

        # Store reference for later access
        # Note: Focus areas are persisted directly through FocusAreaService when CRUD operations occur
        config_handler.focus_areas_widget = focus_widget

        return focus_widget

    @staticmethod
    def create_focus_areas_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
    ) -> QGroupBox:
        """Create the Focus Areas group (legacy method, kept for backward compatibility)."""
        focus_group = QGroupBox("Privacy Focus Areas")
        focus_layout = QVBoxLayout(focus_group)

        # Use the internal widget creation method
        focus_widget = ComponentFactory._create_focus_areas_widget(config_handler)
        focus_layout.addWidget(focus_widget)

        layout.addRow(focus_group)
        return focus_group

    @staticmethod
    def create_crawler_settings_group(
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
        label_allowed_packages = QLabel("Allowed External Packages: ")
        label_allowed_packages.setToolTip(tooltips["ALLOWED_EXTERNAL_PACKAGES"])
        config_widgets["ALLOWED_EXTERNAL_PACKAGES_WIDGET"].setToolTip(tooltips["ALLOWED_EXTERNAL_PACKAGES"])
        crawler_layout.addRow(label_allowed_packages, config_widgets["ALLOWED_EXTERNAL_PACKAGES_WIDGET"])

        layout.addRow(crawler_group)
        return crawler_group


    @staticmethod
    def create_recording_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Recording group for media capture settings."""
        recording_group = QGroupBox("Recording")
        recording_layout = QFormLayout(recording_group)

        config_widgets["ENABLE_VIDEO_RECORDING"] = QCheckBox()
        label_enable_video = QLabel("Enable Video Recording: ")
        label_enable_video.setToolTip(tooltips["ENABLE_VIDEO_RECORDING"])
        recording_layout.addRow(
            label_enable_video, config_widgets["ENABLE_VIDEO_RECORDING"]
        )

        layout.addRow(recording_group)
        return recording_group

    @staticmethod
    def create_error_handling_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Error Handling group for failure threshold settings."""
        error_handling_group = QGroupBox("Error Handling")
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

        layout.addRow(error_handling_group)
        return error_handling_group

    @staticmethod
    def create_privacy_network_group(
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

        layout.addRow(privacy_group)
        return privacy_group

    @staticmethod
    def _create_api_key_field_with_toggle(
        config_widgets: Dict[str, Any],
        key_name: str,
        placeholder: str,
        label_text: str,
        tooltip: str,
    ) -> Tuple[QLineEdit, QWidget, QLabel]:
        """
        Create an API key input field with toggle visibility button.
        
        Args:
            config_widgets: Dictionary to store widgets
            key_name: Key name for the widget (e.g., "OPENROUTER_API_KEY")
            placeholder: Placeholder text for the input field
            label_text: Label text for the field
            tooltip: Tooltip text for the field
            
        Returns:
            Tuple of (QLineEdit, QWidget container, QLabel)
        """
        # Create the API key input field
        api_key_field = QLineEdit()
        api_key_field.setPlaceholderText(placeholder)
        api_key_field.setEchoMode(QLineEdit.EchoMode.Password)
        config_widgets[key_name] = api_key_field
        
        # Create eye icon button to toggle password visibility
        toggle_password_btn = QPushButton()
        toggle_password_btn.setFixedSize(30, 30)
        toggle_password_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_password_btn.setToolTip("Show/Hide API Key")
        toggle_password_btn.setFlat(True)
        
        # Set initial icon (eye icon for hidden password)
        eye_icon = QIcon.fromTheme("view-hidden", QIcon())
        if eye_icon.isNull():
            # Fallback to Unicode eye emoji if theme icon not available
            toggle_password_btn.setText("👁")
        else:
            toggle_password_btn.setIcon(eye_icon)
        
        # Create container widget with horizontal layout
        api_key_container = QWidget()
        api_key_layout = QHBoxLayout(api_key_container)
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        api_key_layout.setSpacing(5)
        api_key_layout.addWidget(api_key_field)
        api_key_layout.addWidget(toggle_password_btn)
        
        # Toggle password visibility on button click
        def toggle_password_visibility():
            if api_key_field.echoMode() == QLineEdit.EchoMode.Password:
                api_key_field.setEchoMode(QLineEdit.EchoMode.Normal)
                # Change to eye-slash icon when visible
                eye_slash_icon = QIcon.fromTheme("view-visible", QIcon())
                if eye_slash_icon.isNull():
                    toggle_password_btn.setText("🙈")
                else:
                    toggle_password_btn.setIcon(eye_slash_icon)
            else:
                api_key_field.setEchoMode(QLineEdit.EchoMode.Password)
                # Change to eye icon when hidden
                eye_icon = QIcon.fromTheme("view-hidden", QIcon())
                if eye_icon.isNull():
                    toggle_password_btn.setText("👁")
                else:
                    toggle_password_btn.setIcon(eye_icon)
        
        toggle_password_btn.clicked.connect(toggle_password_visibility)
        
        # Create label
        label = QLabel(label_text)
        label.setToolTip(tooltip)
        
        return api_key_field, api_key_container, label

    @staticmethod
    def create_api_keys_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
    ) -> QGroupBox:
        """Create the API Keys settings group."""
        from ui.strings import (
            API_KEYS_GROUP,
            OPENROUTER_API_KEY_PLACEHOLDER,
            GEMINI_API_KEY_PLACEHOLDER,
            MOBSF_API_KEY_PLACEHOLDER,
        )
        
        api_keys_group = QGroupBox(API_KEYS_GROUP)
        api_keys_layout = QFormLayout(api_keys_group)
        
        # OpenRouter API Key
        _, openrouter_container, openrouter_label = ComponentFactory._create_api_key_field_with_toggle(
            config_widgets,
            "OPENROUTER_API_KEY",
            OPENROUTER_API_KEY_PLACEHOLDER,
            "OpenRouter API Key: ",
            tooltips.get("OPENROUTER_API_KEY", ""),
        )
        api_keys_layout.addRow(openrouter_label, openrouter_container)
        
        # Load current value from environment/config
        try:
            openrouter_key = config_handler.config.get("OPENROUTER_API_KEY")
            if openrouter_key:
                config_widgets["OPENROUTER_API_KEY"].setText(openrouter_key)
        except Exception:
            pass
        
        # Gemini API Key
        _, gemini_container, gemini_label = ComponentFactory._create_api_key_field_with_toggle(
            config_widgets,
            "GEMINI_API_KEY",
            GEMINI_API_KEY_PLACEHOLDER,
            "Gemini API Key: ",
            tooltips.get("GEMINI_API_KEY", ""),
        )
        api_keys_layout.addRow(gemini_label, gemini_container)
        
        # Load current value from environment/config
        try:
            gemini_key = config_handler.config.get("GEMINI_API_KEY")
            if gemini_key:
                config_widgets["GEMINI_API_KEY"].setText(gemini_key)
        except Exception:
            pass
        
        # MobSF API Key
        _, mobsf_container, mobsf_label = ComponentFactory._create_api_key_field_with_toggle(
            config_widgets,
            "MOBSF_API_KEY",
            MOBSF_API_KEY_PLACEHOLDER,
            "MobSF API Key: ",
            tooltips.get("MOBSF_API_KEY", ""),
        )
        api_keys_layout.addRow(mobsf_label, mobsf_container)
        
        # Store references for visibility control (used by MobSF enable checkbox)
        config_widgets["MOBSF_API_KEY_LABEL"] = mobsf_label
        config_widgets["MOBSF_API_KEY_CONTAINER"] = mobsf_container
        
        # Load current value from environment/config
        try:
            mobsf_key = config_handler.config.get("MOBSF_API_KEY")
            if mobsf_key:
                config_widgets["MOBSF_API_KEY"].setText(mobsf_key)
        except Exception:
            pass
        
        layout.addRow(api_keys_group)
        return api_keys_group

    @staticmethod
    def create_mobsf_settings_group(
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
        # Get current API URL from config (default to ServiceURLs.MOBSF if not set)
        mobsf_api_url = config_handler.config.CONFIG_MOBSF_API_URL
        config_widgets["MOBSF_API_URL"].setText(mobsf_api_url)
        label_mobsf_api_url = QLabel("MobSF API URL: ")
        label_mobsf_api_url.setToolTip(tooltips["MOBSF_API_URL"])
        mobsf_layout.addRow(label_mobsf_api_url, config_widgets["MOBSF_API_URL"])
        # Store label reference for visibility control
        config_widgets["MOBSF_API_URL_LABEL"] = label_mobsf_api_url

        # Note: MobSF API Key is now in the API Keys group, but we still need
        # to reference it for visibility control when MobSF is enabled/disabled
        # The actual field is created in create_api_keys_group

        # MobSF test and analysis buttons - assign to main_controller instead of config_handler
        main_controller = config_handler.main_controller
        main_controller.test_mobsf_conn_btn = QPushButton("Test MobSF Connection")
        mobsf_layout.addRow(main_controller.test_mobsf_conn_btn)
        logging.debug("Created test_mobsf_conn_btn directly on main_controller")

        main_controller.run_mobsf_analysis_btn = QPushButton("Run Static Analysis using")
        mobsf_layout.addRow(main_controller.run_mobsf_analysis_btn)
        logging.debug("Created run_mobsf_analysis_btn directly on main_controller")

        # Set initial visibility and button states based on checkbox
        # Hide/show fields and buttons based on checkbox state
        config_widgets["MOBSF_API_URL"].setVisible(is_mobsf_enabled)
        label_mobsf_api_url.setVisible(is_mobsf_enabled)
        # Note: MobSF API Key is in API Keys group and should always be visible
        # (not controlled by MobSF enable checkbox)
        main_controller.test_mobsf_conn_btn.setVisible(is_mobsf_enabled)
        main_controller.run_mobsf_analysis_btn.setVisible(is_mobsf_enabled)
        
        # Also set enabled state for buttons
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
    def create_control_buttons(controls_handler: Any) -> QGroupBox:
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