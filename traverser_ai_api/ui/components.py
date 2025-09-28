# ui/components.py - UI components for the Appium Crawler Controller

import os
import logging
from typing import Dict, Any, Callable, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QCheckBox, QSpinBox,
    QTextEdit, QFormLayout, QGroupBox, QComboBox,
    QScrollArea, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap

class UIComponents:
    """Factory class for creating UI components used in the Crawler Controller."""
    
    # Define which settings groups and fields are considered advanced
    # These will be hidden in basic mode
    ADVANCED_GROUPS = [
        "appium_settings_group",
        "error_handling_group",
        "focus_areas_group"  # Focus areas can be advanced for basic users
    ]
    
    @staticmethod
    def _update_model_types(provider: str, config_widgets: Dict[str, Any]) -> None:
        """Update the model types based on the selected AI provider."""
        model_dropdown = config_widgets['DEFAULT_MODEL_TYPE']
        
        # Block signals to prevent auto-save from triggering with an empty value
        model_dropdown.blockSignals(True)
        
        model_dropdown.clear()
        
        # Get provider capabilities from config
        try:
            from ..config import AI_PROVIDER_CAPABILITIES
        except ImportError:
            from config import AI_PROVIDER_CAPABILITIES
        
        capabilities = AI_PROVIDER_CAPABILITIES.get(provider.lower(), AI_PROVIDER_CAPABILITIES.get('gemini', {}))
        
        if provider.lower() == 'gemini':
            model_dropdown.addItems([
                'flash-latest', 'flash-latest-fast'
            ])
            # Enable image context for Gemini
            if 'ENABLE_IMAGE_CONTEXT' in config_widgets:
                config_widgets['ENABLE_IMAGE_CONTEXT'].setEnabled(True)
                config_widgets['ENABLE_IMAGE_CONTEXT'].setToolTip("Enable sending screenshots to AI for visual analysis. Disable for text-only analysis.")
                
                # Reset styling when enabling
                config_widgets['ENABLE_IMAGE_CONTEXT'].setStyleSheet("")
                
                # Hide warning label
                if 'IMAGE_CONTEXT_WARNING' in config_widgets:
                    config_widgets['IMAGE_CONTEXT_WARNING'].setVisible(False)
        elif provider.lower() == 'deepseek':
            model_dropdown.addItems([
                'deepseek-vision', 'deepseek-vision-fast'
            ])
            # Handle image context based on provider capabilities
            if 'ENABLE_IMAGE_CONTEXT' in config_widgets:
                auto_disable = capabilities.get('auto_disable_image_context', False)
                if auto_disable:
                    config_widgets['ENABLE_IMAGE_CONTEXT'].setChecked(False)
                    config_widgets['ENABLE_IMAGE_CONTEXT'].setEnabled(False)
                    config_widgets['ENABLE_IMAGE_CONTEXT'].setToolTip(f"⚠️ DISABLED: {provider} has strict payload limits ({capabilities.get('payload_max_size_kb', 150)}KB max). Image context automatically disabled to prevent API errors.")
                    
                    # Add visual styling to make the disabled state more obvious
                    config_widgets['ENABLE_IMAGE_CONTEXT'].setStyleSheet("""
                        QCheckBox {
                            color: #ff6b35;
                            font-weight: bold;
                        }
                        QCheckBox::indicator {
                            background-color: #ff6b35;
                            border: 2px solid #ff6b35;
                            border-radius: 3px;
                        }
                        QCheckBox::indicator:unchecked {
                            background-color: #ffeaa7;
                        }
                    """)
                    
                    # Show warning label
                    if 'IMAGE_CONTEXT_WARNING' in config_widgets:
                        config_widgets['IMAGE_CONTEXT_WARNING'].setVisible(True)
                    
                    # Add visual warning indicator
                    UIComponents._add_image_context_warning(provider, capabilities)
                else:
                    config_widgets['ENABLE_IMAGE_CONTEXT'].setEnabled(True)
                    config_widgets['ENABLE_IMAGE_CONTEXT'].setToolTip("Enable sending screenshots to AI for visual analysis. Disable for text-only analysis.")
                    
                    # Reset styling when enabling
                    config_widgets['ENABLE_IMAGE_CONTEXT'].setStyleSheet("")
                    
                    # Hide warning label
                    if 'IMAGE_CONTEXT_WARNING' in config_widgets:
                        config_widgets['IMAGE_CONTEXT_WARNING'].setVisible(False)
        elif provider.lower() == 'ollama':
            # Get available Ollama models dynamically
            try:
                import ollama
                available_models = ollama.list()
                model_items = []
                vision_models = []
                
                for model_info in available_models.get('models', []):
                    model_name = model_info.get('model', model_info.get('name', ''))
                    if not model_name:
                        continue
                        
                    # Keep full model name with tag for display and API usage
                    display_name = model_name
                    
                    # Extract base name for feature detection
                    base_name = model_name.split(':')[0]
                    
                    # Check if this model supports vision by directly querying Ollama
                    # We'll try to get model metadata or tags that indicate vision support
                    vision_supported = False
                    try:
                        # Try to get model info to determine vision capabilities
                        # First attempt: check model tags or metadata
                        # For now, we'll still use name-based detection as a fallback
                        vision_supported = any(pattern in base_name.lower() for pattern in [
                            'vision', 'llava', 'bakllava', 'minicpm-v', 'moondream', 'gemma3', 'llama', 'qwen2.5vl'
                        ])
                        logging.debug(f"Vision capability for {model_name}: {vision_supported}")
                    except Exception as e:
                        logging.debug(f"Error checking vision capability for {model_name}: {e}")
                        # Fallback to name-based detection
                    
                    # Use the original model name without adding suffixes
                    display_name = model_name
                    if vision_supported:
                        vision_models.append(display_name)
                    
                    model_items.append(display_name)
                
                # If no models found, show a message
                if not model_items:
                    model_items = ["No Ollama models available - run 'ollama pull <model>'"]
                    logging.warning("No Ollama models found")
                
                model_dropdown.addItems(model_items)
                
                # Set default to first vision-capable model if available, otherwise first model
                if vision_models:
                    model_dropdown.setCurrentText(vision_models[0])
                    logging.debug(f"Set default to vision model: {vision_models[0]}")
                elif model_items and model_items[0] != "No Ollama models available - run 'ollama pull <model>'":
                    model_dropdown.setCurrentText(model_items[0])
                    logging.debug(f"Set default to first available model: {model_items[0]}")
                
                logging.debug(f"Loaded {len(model_items)} Ollama models: {model_items}")
                
            except ImportError:
                # Fallback if ollama package not installed
                model_dropdown.addItems([
                    'Ollama not installed - run "pip install ollama"'
                ])
                logging.warning("Ollama package not installed")
            except Exception as e:
                # Fallback if Ollama is not running or other error
                logging.warning(f"Could not fetch Ollama models: {e}")
                model_dropdown.addItems([
                    'Ollama not running - start Ollama service',
                    'llama3.2(local)',
                    'llama3.2-vision(local) 👁️'
                ])
            
            # Enable image context for Ollama (vision models will handle it)
            if 'ENABLE_IMAGE_CONTEXT' in config_widgets:
                config_widgets['ENABLE_IMAGE_CONTEXT'].setEnabled(True)
                config_widgets['ENABLE_IMAGE_CONTEXT'].setToolTip("Enable sending screenshots to AI for visual analysis. Vision-capable models will process images, others will use text-only.")
                
                # Reset styling when enabling
                config_widgets['ENABLE_IMAGE_CONTEXT'].setStyleSheet("")
                
                # Hide warning label
                if 'IMAGE_CONTEXT_WARNING' in config_widgets:
                    config_widgets['IMAGE_CONTEXT_WARNING'].setVisible(False)
        
        # Unblock signals after updating
        model_dropdown.blockSignals(False)
    
    @staticmethod
    def _add_image_context_warning(provider: str, capabilities: Dict[str, Any]) -> None:
        """Add visual warning when image context is auto-disabled."""
        import logging
        
        try:
            payload_limit = capabilities.get('payload_max_size_kb', 150)
            warning_msg = f"⚠️ IMAGE CONTEXT AUTO-DISABLED: {provider} has strict payload limits ({payload_limit}KB max). Image context automatically disabled to prevent API errors."
            
            # Log the warning
            logging.warning(f"Image context auto-disabled for {provider} due to payload limits")
            
            # Try to show warning in UI if main controller is available
            try:
                from PySide6.QtWidgets import QApplication
                from ..ui_controller import CrawlerControllerWindow
                
                # Get the main window instance if it exists
                app = QApplication.instance()
                if app and isinstance(app, QApplication):
                    for widget in app.topLevelWidgets():
                        if isinstance(widget, CrawlerControllerWindow):
                            widget.log_message(warning_msg, 'orange')
                            break
            except Exception as e:
                logging.debug(f"Could not show UI warning: {e}")
                
        except Exception as e:
            logging.error(f"Error adding image context warning: {e}")
    
    ADVANCED_FIELDS = {
        "APPIUM_SERVER_URL": True,  # True means hide in basic mode
        "TARGET_DEVICE_UDID": True,  # True means hide in basic mode
        "NEW_COMMAND_TIMEOUT": True,
        "APPIUM_IMPLICIT_WAIT": True,
        "DEFAULT_MODEL_TYPE": False,
        "USE_CHAT_MEMORY": True,
        "MAX_CHAT_HISTORY": True,
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
    }
    
    @staticmethod
    def create_left_panel(
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
        controls_handler: Any
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
        config_handler.ui_mode_dropdown.addItems(["Basic", "Expert"])
        
        # Get the UI mode from config
        initial_mode = "Basic"  # Default if not found
        
        # Check if the user_config has a UI_MODE (loaded from user_config.json)
        if hasattr(config_handler, 'user_config') and 'UI_MODE' in config_handler.user_config:
            initial_mode = config_handler.user_config['UI_MODE']
            logging.debug(f"Setting initial UI mode from user_config: {initial_mode}")
        # Fallback to config attribute if it exists
        elif hasattr(config_handler.main_controller.config, 'UI_MODE'):
            initial_mode = config_handler.main_controller.config.UI_MODE
            logging.debug(f"Setting initial UI mode from config attribute: {initial_mode}")
        
        logging.debug(f"Initial UI mode determined as: {initial_mode}")
        
        # Set the dropdown to the initial mode
        mode_index = config_handler.ui_mode_dropdown.findText(initial_mode)
        if mode_index >= 0:
            config_handler.ui_mode_dropdown.setCurrentIndex(mode_index)
        else:
            config_handler.ui_mode_dropdown.setCurrentIndex(0)  # Default to Basic if not found
            
        config_handler.ui_mode_dropdown.setToolTip("Basic mode hides advanced settings. Expert mode shows all settings.")
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(config_handler.ui_mode_dropdown)
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
        appium_group = UIComponents._create_appium_settings_group(scroll_layout, config_widgets, tooltips, controls_handler)
        appium_group.setObjectName("appium_settings_group")
        
        app_group = UIComponents._create_app_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        app_group.setObjectName("app_settings_group")
        
        ai_group = UIComponents._create_ai_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        ai_group.setObjectName("ai_settings_group")
        
        focus_areas_group = UIComponents._create_focus_areas_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        focus_areas_group.setObjectName("focus_areas_group")
        
        crawler_group = UIComponents._create_crawler_settings_group(scroll_layout, config_widgets, tooltips)
        crawler_group.setObjectName("crawler_settings_group")
        
        error_handling_group = UIComponents._create_error_handling_group(scroll_layout, config_widgets, tooltips)
        error_handling_group.setObjectName("error_handling_group")
        
        feature_toggle_group = UIComponents._create_feature_toggles_group(scroll_layout, config_widgets, tooltips)
        feature_toggle_group.setObjectName("feature_toggles_group")
        
        mobsf_group = UIComponents._create_mobsf_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        mobsf_group.setObjectName("mobsf_settings_group")
        
        # Apply default values
        config_handler._apply_defaults_from_config_to_widgets()
        config_handler._update_crawl_mode_inputs_state()
        
        # Store the group widgets for mode switching
        config_handler.ui_groups = {
            "appium_settings_group": appium_group,
            "app_settings_group": app_group,
            "ai_settings_group": ai_group,
            "focus_areas_group": focus_areas_group,
            "crawler_settings_group": crawler_group,
            "error_handling_group": error_handling_group,
            "feature_toggles_group": feature_toggle_group,
            "mobsf_settings_group": mobsf_group
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
            mode: "Basic" or "Expert" mode
            config_handler: The config handler with references to UI widgets
        """
        is_basic = mode == "Basic"
        
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
                if not hasattr(widget, 'parent') or widget.parent() is None:
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
                    if (label_item and label_item.widget() and 
                        isinstance(label_item.widget(), QLabel) and
                        i + 1 < parent_layout.count() and
                        parent_layout.itemAt(i + 1).widget() == widget):
                        label_item.widget().setVisible(widget_visible)
                        break
                
                # Set widget visibility
                widget.setVisible(widget_visible)
            except Exception as e:
                # Log but don't crash if there's an issue with a specific widget
                logging.warning(f"Error toggling visibility for {field_name}: {e}")
        
        # Set the dropdown to the current mode
        if hasattr(config_handler, 'ui_mode_dropdown'):
            index = config_handler.ui_mode_dropdown.findText(mode)
            if index >= 0 and config_handler.ui_mode_dropdown.currentIndex() != index:
                # Only set if it's different to avoid triggering change events
                config_handler.ui_mode_dropdown.setCurrentIndex(index)
        
        # Save the current mode to user config
        config_handler.config.update_setting_and_save("UI_MODE", mode, config_handler.main_controller._sync_user_config_files)
        
        # Synchronize the changes to the API config file
        # Note: Synchronization is now handled automatically by the callback in update_setting_and_save
        
        # Ensure the config.UI_MODE attribute is updated
        if hasattr(config_handler.config, 'UI_MODE'):
            config_handler.config.UI_MODE = mode
        logging.debug(f"UI mode switched to and saved: {mode}")
        logging.debug(f"Config file location: {config_handler.config.USER_CONFIG_FILE_PATH}")
        config_handler.main_controller.log_message(f"Switched to {mode} mode", 'blue')
    
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
        
        # Status section
        status_layout = QHBoxLayout()
        controller.status_label = QLabel("Status: Idle")
        controller.progress_bar = QProgressBar()
        status_layout.addWidget(controller.status_label)
        status_layout.addWidget(controller.progress_bar)
        
        # Step and action section
        step_action_layout = QHBoxLayout()
        controller.step_label = QLabel("Step: 0")
        controller.last_action_label = QLabel("Last Action: None")
        step_action_layout.addWidget(controller.step_label)
        step_action_layout.addWidget(controller.last_action_label)
        
        # Screenshot display
        controller.screenshot_label = QLabel()
        controller.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controller.screenshot_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        
        # Log output
        controller.log_output = QTextEdit()
        controller.log_output.setReadOnly(True)
        # Set dark background for log output to make white text visible
        controller.log_output.setStyleSheet("background-color: #333333;")
        
        # Add all sections to the layout
        layout.addLayout(status_layout)
        layout.addLayout(step_action_layout)
        layout.addWidget(controller.screenshot_label)
        layout.addWidget(controller.log_output, 1)
        
        return panel
    
    @staticmethod
    def _create_appium_settings_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        controls_handler: Any
    ) -> QGroupBox:
        """Create the Appium settings group."""
        appium_group = QGroupBox("Appium Settings")
        appium_layout = QFormLayout(appium_group)
        
        config_widgets['APPIUM_SERVER_URL'] = QLineEdit()
        label_appium_url = QLabel("Server URL:")
        label_appium_url.setToolTip(tooltips['APPIUM_SERVER_URL'])
        appium_layout.addRow(label_appium_url, config_widgets['APPIUM_SERVER_URL'])
        
        config_widgets['TARGET_DEVICE_UDID'] = QComboBox()
        label_device_udid = QLabel("Target Device UDID:")
        label_device_udid.setToolTip(tooltips['TARGET_DEVICE_UDID'])
        
        device_layout = QHBoxLayout()
        device_layout.addWidget(config_widgets['TARGET_DEVICE_UDID'])
        refresh_devices_btn = QPushButton("Refresh")
        controls_handler.refresh_devices_btn = refresh_devices_btn
        device_layout.addWidget(refresh_devices_btn)
        appium_layout.addRow(label_device_udid, device_layout)
        
        config_widgets['NEW_COMMAND_TIMEOUT'] = QSpinBox()
        config_widgets['NEW_COMMAND_TIMEOUT'].setRange(0, 3600)
        label_new_command_timeout = QLabel("New Command Timeout (s):")
        label_new_command_timeout.setToolTip(tooltips['NEW_COMMAND_TIMEOUT'])
        appium_layout.addRow(label_new_command_timeout, config_widgets['NEW_COMMAND_TIMEOUT'])
        
        config_widgets['APPIUM_IMPLICIT_WAIT'] = QSpinBox()
        config_widgets['APPIUM_IMPLICIT_WAIT'].setRange(0, 300)
        label_implicit_wait = QLabel("Implicit Wait (s):")
        label_implicit_wait.setToolTip(tooltips['APPIUM_IMPLICIT_WAIT'])
        appium_layout.addRow(label_implicit_wait, config_widgets['APPIUM_IMPLICIT_WAIT'])
        
        layout.addRow(appium_group)
        return appium_group
    
    @staticmethod
    def _create_app_settings_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any
    ) -> QGroupBox:
        """Create the App settings group with health app selection."""
        app_group = QGroupBox("App Settings")
        app_layout = QFormLayout(app_group)
        
        # Health App Selector
        config_handler.health_app_dropdown = QComboBox()
        config_handler.health_app_dropdown.addItem("Select target app (Scan first)", None)
        config_handler.health_app_dropdown.currentIndexChanged.connect(
            config_handler._on_health_app_selected
        )
        app_layout.addRow(QLabel("Target Health App:"), config_handler.health_app_dropdown)
        config_handler.health_app_dropdown.setToolTip(
            "Select a health-related app discovered on the device. Use button below to scan."
        )
        
        config_handler.refresh_apps_btn = QPushButton("Scan/Refresh Health Apps List")
        config_handler.refresh_apps_btn.setToolTip(
            "Scans the connected device for installed applications and filters for health-related ones using AI."
        )
        app_layout.addRow(config_handler.refresh_apps_btn)
        
        config_handler.app_scan_status_label = QLabel("App Scan: Idle")
        app_layout.addRow(QLabel("Scan Status:"), config_handler.app_scan_status_label)
        
        # App package and activity (auto-filled)
        config_widgets['APP_PACKAGE'] = QLineEdit()
        config_widgets['APP_PACKAGE'].setReadOnly(True)
        label_app_package = QLabel("Package Name (Auto-filled):")
        label_app_package.setToolTip(tooltips['APP_PACKAGE'])
        app_layout.addRow(label_app_package, config_widgets['APP_PACKAGE'])
        
        config_widgets['APP_ACTIVITY'] = QLineEdit()
        config_widgets['APP_ACTIVITY'].setReadOnly(True)
        label_app_activity = QLabel("Activity (Auto-filled):")
        label_app_activity.setToolTip(tooltips['APP_ACTIVITY'])
        app_layout.addRow(label_app_activity, config_widgets['APP_ACTIVITY'])
        
        layout.addRow(app_group)
        return app_group
    
    @staticmethod
    def _create_ai_settings_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any = None
    ) -> QGroupBox:
        """Create the AI settings group."""
        ai_group = QGroupBox("AI Settings")
        ai_layout = QFormLayout(ai_group)
        
        # AI Provider Selection
        config_widgets['AI_PROVIDER'] = QComboBox()
        config_widgets['AI_PROVIDER'].addItems(['gemini', 'deepseek', 'ollama'])
        label_ai_provider = QLabel("AI Provider: ")
        label_ai_provider.setToolTip("The AI model provider to use for analysis and decision making.")
        ai_layout.addRow(label_ai_provider, config_widgets['AI_PROVIDER'])
        
        # Connect the AI provider selection to update model types
        config_widgets['AI_PROVIDER'].currentTextChanged.connect(
            lambda provider: UIComponents._update_model_types(provider, config_widgets)
        )
        
        config_widgets['DEFAULT_MODEL_TYPE'] = QComboBox()
        config_widgets['DEFAULT_MODEL_TYPE'].addItems([
            'flash-latest', 'flash-latest-fast'
        ])
        label_model_type = QLabel("Default Model Type: ")
        label_model_type.setToolTip(tooltips['DEFAULT_MODEL_TYPE'])
        ai_layout.addRow(label_model_type, config_widgets['DEFAULT_MODEL_TYPE'])
        
        config_widgets['USE_CHAT_MEMORY'] = QCheckBox()
        label_use_chat_memory = QLabel("Use Chat Memory: ")
        label_use_chat_memory.setToolTip(tooltips['USE_CHAT_MEMORY'])
        ai_layout.addRow(label_use_chat_memory, config_widgets['USE_CHAT_MEMORY'])
        
        config_widgets['MAX_CHAT_HISTORY'] = QSpinBox()
        config_widgets['MAX_CHAT_HISTORY'].setRange(0, 100)
        label_max_chat_history = QLabel("Max Chat History: ")
        label_max_chat_history.setToolTip(tooltips['MAX_CHAT_HISTORY'])
        ai_layout.addRow(label_max_chat_history, config_widgets['MAX_CHAT_HISTORY'])
        
        config_widgets['XML_SNIPPET_MAX_LEN'] = QSpinBox()
        config_widgets['XML_SNIPPET_MAX_LEN'].setRange(5000, 500000)
        label_xml_snippet_max_len = QLabel("XML Snippet Max Length: ")
        label_xml_snippet_max_len.setToolTip(tooltips['XML_SNIPPET_MAX_LEN'])
        ai_layout.addRow(label_xml_snippet_max_len, config_widgets['XML_SNIPPET_MAX_LEN'])
        
        layout.addRow(ai_group)
        return ai_group
    
    @staticmethod
    def _create_focus_areas_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any
    ) -> QGroupBox:
        """Create the Focus Areas group."""
        focus_group = QGroupBox("AI Privacy Focus Areas")
        focus_layout = QVBoxLayout(focus_group)
        
        # Import the focus areas widget
        try:
            from .focus_areas_widget import FocusAreasWidget
        except ImportError:
            from focus_areas_widget import FocusAreasWidget
        
        # Load focus areas from config or use defaults
        focus_areas_data = getattr(config_handler.config, 'FOCUS_AREAS', None)
        
        # Check if focus areas have been loaded from user config
        # If FOCUS_AREAS is None or empty list, use defaults
        if focus_areas_data is None or len(focus_areas_data) == 0:
            # Import defaults if not set or empty
            try:
                from .focus_areas_widget import DEFAULT_PRIVACY_FOCUS_AREAS
            except ImportError:
                from focus_areas_widget import DEFAULT_PRIVACY_FOCUS_AREAS
            focus_areas_data = DEFAULT_PRIVACY_FOCUS_AREAS
            # Convert dataclass objects to dictionaries for consistency
            focus_areas_data = [
                {
                    'id': area.id,
                    'name': area.name,
                    'description': area.description,
                    'prompt_modifier': area.prompt_modifier,
                    'enabled': area.enabled,
                    'priority': area.priority
                }
                for area in focus_areas_data
            ]
        
        # Create the focus areas widget
        focus_widget = FocusAreasWidget(focus_areas_data)
        focus_layout.addWidget(focus_widget)
        
        # Connect to config changes
        focus_widget.focus_areas_changed.connect(
            lambda areas: config_handler.update_focus_areas(areas)
        )
        
        # Store reference for later access
        config_handler.focus_areas_widget = focus_widget
        
        layout.addRow(focus_group)
        return focus_group
    
    @staticmethod
    def _create_crawler_settings_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Crawler settings group."""
        crawler_group = QGroupBox("Crawler Settings")
        crawler_layout = QFormLayout(crawler_group)
        
        config_widgets['CRAWL_MODE'] = QComboBox()
        config_widgets['CRAWL_MODE'].addItems(['steps', 'time'])
        label_crawl_mode = QLabel("Crawl Mode: ")
        label_crawl_mode.setToolTip(tooltips['CRAWL_MODE'])
        crawler_layout.addRow(label_crawl_mode, config_widgets['CRAWL_MODE'])
        
        config_widgets['MAX_CRAWL_STEPS'] = QSpinBox()
        config_widgets['MAX_CRAWL_STEPS'].setRange(1, 10000)
        label_max_crawl_steps = QLabel("Max Steps: ")
        label_max_crawl_steps.setToolTip(tooltips['MAX_CRAWL_STEPS'])
        crawler_layout.addRow(label_max_crawl_steps, config_widgets['MAX_CRAWL_STEPS'])
        
        config_widgets['MAX_CRAWL_DURATION_SECONDS'] = QSpinBox()
        config_widgets['MAX_CRAWL_DURATION_SECONDS'].setRange(60, 86400)
        label_max_crawl_duration = QLabel("Max Duration (s): ")
        label_max_crawl_duration.setToolTip(tooltips['MAX_CRAWL_DURATION_SECONDS'])
        crawler_layout.addRow(label_max_crawl_duration, config_widgets['MAX_CRAWL_DURATION_SECONDS'])
        
        config_widgets['WAIT_AFTER_ACTION'] = QSpinBox()
        config_widgets['WAIT_AFTER_ACTION'].setRange(0, 60)
        label_wait_after_action = QLabel("Wait After Action (s): ")
        label_wait_after_action.setToolTip(tooltips['WAIT_AFTER_ACTION'])
        crawler_layout.addRow(label_wait_after_action, config_widgets['WAIT_AFTER_ACTION'])
        
        config_widgets['STABILITY_WAIT'] = QSpinBox()
        config_widgets['STABILITY_WAIT'].setRange(0, 60)
        label_stability_wait = QLabel("Stability Wait (s): ")
        label_stability_wait.setToolTip(tooltips['STABILITY_WAIT'])
        crawler_layout.addRow(label_stability_wait, config_widgets['STABILITY_WAIT'])
        
        config_widgets['APP_LAUNCH_WAIT_TIME'] = QSpinBox()
        config_widgets['APP_LAUNCH_WAIT_TIME'].setRange(0, 300)
        label_app_launch_wait_time = QLabel("App Launch Wait Time (s): ")
        label_app_launch_wait_time.setToolTip(tooltips['APP_LAUNCH_WAIT_TIME'])
        crawler_layout.addRow(label_app_launch_wait_time, config_widgets['APP_LAUNCH_WAIT_TIME'])
        
        # Visual Similarity Threshold
        config_widgets['VISUAL_SIMILARITY_THRESHOLD'] = QSpinBox()
        config_widgets['VISUAL_SIMILARITY_THRESHOLD'].setRange(0, 100)
        label_visual_similarity = QLabel("Visual Similarity Threshold: ")
        label_visual_similarity.setToolTip(tooltips['VISUAL_SIMILARITY_THRESHOLD'])
        crawler_layout.addRow(label_visual_similarity, config_widgets['VISUAL_SIMILARITY_THRESHOLD'])
        
        # Allowed External Packages
        config_widgets['ALLOWED_EXTERNAL_PACKAGES'] = QTextEdit()
        config_widgets['ALLOWED_EXTERNAL_PACKAGES'].setPlaceholderText("com.example.package1\\ncom.example.package2")
        config_widgets['ALLOWED_EXTERNAL_PACKAGES'].setFixedHeight(80)
        label_allowed_external_packages = QLabel("Allowed External Packages (one per line): ")
        label_allowed_external_packages.setToolTip(tooltips['ALLOWED_EXTERNAL_PACKAGES'])
        crawler_layout.addRow(label_allowed_external_packages, config_widgets['ALLOWED_EXTERNAL_PACKAGES'])
        
        layout.addRow(crawler_group)
        return crawler_group
    
    @staticmethod
    def _create_error_handling_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Error Handling settings group."""
        error_handling_group = QGroupBox("Error Handling Settings")
        error_handling_layout = QFormLayout(error_handling_group)
        
        config_widgets['MAX_CONSECUTIVE_AI_FAILURES'] = QSpinBox()
        config_widgets['MAX_CONSECUTIVE_AI_FAILURES'].setRange(1, 100)
        label_max_ai_failures = QLabel("Max Consecutive AI Failures: ")
        label_max_ai_failures.setToolTip(tooltips['MAX_CONSECUTIVE_AI_FAILURES'])
        error_handling_layout.addRow(label_max_ai_failures, config_widgets['MAX_CONSECUTIVE_AI_FAILURES'])
        
        config_widgets['MAX_CONSECUTIVE_MAP_FAILURES'] = QSpinBox()
        config_widgets['MAX_CONSECUTIVE_MAP_FAILURES'].setRange(1, 100)
        label_max_map_failures = QLabel("Max Consecutive Map Failures: ")
        label_max_map_failures.setToolTip(tooltips['MAX_CONSECUTIVE_MAP_FAILURES'])
        error_handling_layout.addRow(label_max_map_failures, config_widgets['MAX_CONSECUTIVE_MAP_FAILURES'])
        
        config_widgets['MAX_CONSECUTIVE_EXEC_FAILURES'] = QSpinBox()
        config_widgets['MAX_CONSECUTIVE_EXEC_FAILURES'].setRange(1, 100)
        label_max_exec_failures = QLabel("Max Consecutive Exec Failures: ")
        label_max_exec_failures.setToolTip(tooltips['MAX_CONSECUTIVE_EXEC_FAILURES'])
        error_handling_layout.addRow(label_max_exec_failures, config_widgets['MAX_CONSECUTIVE_EXEC_FAILURES'])
        
        layout.addRow(error_handling_group)
        return error_handling_group
    
    @staticmethod
    def _create_feature_toggles_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Feature Toggles group."""
        feature_toggle_group = QGroupBox("Feature Toggles")
        feature_toggle_layout = QFormLayout(feature_toggle_group)
        
        config_widgets['ENABLE_IMAGE_CONTEXT'] = QCheckBox()
        label_enable_image_context = QLabel("Enable Image Context: ")
        label_enable_image_context.setToolTip("Enable sending screenshots to AI for visual analysis. Disable for text-only analysis. Note: Automatically disabled for DeepSeek due to payload size limits.")
        
        # Create warning label (initially hidden)
        config_widgets['IMAGE_CONTEXT_WARNING'] = QLabel("⚠️ Auto-disabled")
        config_widgets['IMAGE_CONTEXT_WARNING'].setStyleSheet("color: #ff6b35; font-weight: bold;")
        config_widgets['IMAGE_CONTEXT_WARNING'].setVisible(False)
        
        # Create horizontal layout for checkbox and warning
        image_context_layout = QHBoxLayout()
        image_context_layout.addWidget(label_enable_image_context)
        image_context_layout.addWidget(config_widgets['ENABLE_IMAGE_CONTEXT'])
        image_context_layout.addWidget(config_widgets['IMAGE_CONTEXT_WARNING'])
        image_context_layout.addStretch()
        
        feature_toggle_layout.addRow(image_context_layout)
        
        config_widgets['ENABLE_TRAFFIC_CAPTURE'] = QCheckBox()
        label_enable_traffic_capture = QLabel("Enable Traffic Capture: ")
        label_enable_traffic_capture.setToolTip(tooltips['ENABLE_TRAFFIC_CAPTURE'])
        feature_toggle_layout.addRow(label_enable_traffic_capture, config_widgets['ENABLE_TRAFFIC_CAPTURE'])
        
        config_widgets['CLEANUP_DEVICE_PCAP_FILE'] = QCheckBox()
        label_cleanup_pcap = QLabel("Cleanup Device PCAP after Pull: ")
        label_cleanup_pcap.setToolTip(tooltips['CLEANUP_DEVICE_PCAP_FILE'])
        feature_toggle_layout.addRow(label_cleanup_pcap, config_widgets['CLEANUP_DEVICE_PCAP_FILE'])
        
        config_widgets['CONTINUE_EXISTING_RUN'] = QCheckBox()
        label_continue_run = QLabel("Continue Existing Run: ")
        label_continue_run.setToolTip(tooltips['CONTINUE_EXISTING_RUN'])
        feature_toggle_layout.addRow(label_continue_run, config_widgets['CONTINUE_EXISTING_RUN'])
        
        layout.addRow(feature_toggle_group)
        return feature_toggle_group
    
    @staticmethod
    def _create_mobsf_settings_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any
    ) -> QGroupBox:
        """Create the MobSF settings group."""
        mobsf_group = QGroupBox("MobSF Static Analysis")
        mobsf_layout = QFormLayout(mobsf_group)
        
        # MobSF Enable Checkbox
        config_widgets['ENABLE_MOBSF_ANALYSIS'] = QCheckBox()
        label_enable_mobsf = QLabel("Enable MobSF Analysis: ")
        label_enable_mobsf.setToolTip(tooltips['ENABLE_MOBSF_ANALYSIS'])
        mobsf_layout.addRow(label_enable_mobsf, config_widgets['ENABLE_MOBSF_ANALYSIS'])
        
        # Get current enabled state (default to False if not set)
        is_mobsf_enabled = getattr(config_handler.config, 'ENABLE_MOBSF_ANALYSIS', False)
        config_widgets['ENABLE_MOBSF_ANALYSIS'].setChecked(is_mobsf_enabled)
        logging.debug(f"Setting initial MobSF checkbox state: {is_mobsf_enabled}")
        
        # API URL field
        config_widgets['MOBSF_API_URL'] = QLineEdit()
        config_widgets['MOBSF_API_URL'].setPlaceholderText("http://localhost:8000/api/v1")
        label_mobsf_api_url = QLabel("MobSF API URL: ")
        label_mobsf_api_url.setToolTip(tooltips['MOBSF_API_URL'])
        mobsf_layout.addRow(label_mobsf_api_url, config_widgets['MOBSF_API_URL'])
        
        config_widgets['MOBSF_API_KEY'] = QLineEdit()
        config_widgets['MOBSF_API_KEY'].setPlaceholderText("Your MobSF API Key")
        config_widgets['MOBSF_API_KEY'].setEchoMode(QLineEdit.EchoMode.Password)
        label_mobsf_api_key = QLabel("MobSF API Key: ")
        label_mobsf_api_key.setToolTip(tooltips['MOBSF_API_KEY'])
        mobsf_layout.addRow(label_mobsf_api_key, config_widgets['MOBSF_API_KEY'])
        
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
        config_widgets['ENABLE_MOBSF_ANALYSIS'].stateChanged.connect(
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
        pre_check_btn.setToolTip("Check the status of all required services (Appium, Ollama, MobSF) before starting")
        pre_check_btn.clicked.connect(controls_handler.perform_pre_crawl_validation)
        
        controls_handler.start_btn.clicked.connect(controls_handler.start_crawler)
        controls_handler.stop_btn.clicked.connect(controls_handler.stop_crawler)
        
        layout.addWidget(pre_check_btn)
        layout.addWidget(controls_handler.start_btn)
        layout.addWidget(controls_handler.stop_btn)
        
        return group
