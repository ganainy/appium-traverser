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
        
        # Create scrollable area for config inputs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QFormLayout(scroll_content)
        
        # Create the config inputs sections
        UIComponents._create_appium_settings_group(scroll_layout, config_widgets, tooltips)
        UIComponents._create_app_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        UIComponents._create_ai_settings_group(scroll_layout, config_widgets, tooltips)
        UIComponents._create_crawler_settings_group(scroll_layout, config_widgets, tooltips)
        UIComponents._create_error_handling_group(scroll_layout, config_widgets, tooltips)
        UIComponents._create_feature_toggles_group(scroll_layout, config_widgets, tooltips)
        UIComponents._create_mobsf_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        
        # Apply default values
        config_handler._apply_defaults_from_config_to_widgets()
        config_handler._update_crawl_mode_inputs_state()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Add control buttons
        controls_group = UIComponents._create_control_buttons(controls_handler)
        layout.addWidget(controls_group)
        
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
        tooltips: Dict[str, str]
    ) -> None:
        """Create the Appium settings group."""
        appium_group = QGroupBox("Appium Settings")
        appium_layout = QFormLayout(appium_group)
        
        config_widgets['APPIUM_SERVER_URL'] = QLineEdit()
        label_appium_url = QLabel("Server URL:")
        label_appium_url.setToolTip(tooltips['APPIUM_SERVER_URL'])
        appium_layout.addRow(label_appium_url, config_widgets['APPIUM_SERVER_URL'])
        
        config_widgets['TARGET_DEVICE_UDID'] = QLineEdit()
        label_device_udid = QLabel("Target Device UDID (Optional):")
        label_device_udid.setToolTip(tooltips['TARGET_DEVICE_UDID'])
        appium_layout.addRow(label_device_udid, config_widgets['TARGET_DEVICE_UDID'])
        
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
    
    @staticmethod
    def _create_app_settings_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any
    ) -> None:
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
    
    @staticmethod
    def _create_ai_settings_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str]
    ) -> None:
        """Create the AI settings group."""
        ai_group = QGroupBox("AI Settings")
        ai_layout = QFormLayout(ai_group)
        
        config_widgets['DEFAULT_MODEL_TYPE'] = QComboBox()
        config_widgets['DEFAULT_MODEL_TYPE'].addItems([
            'flash-latest', 'flash-latest-fast', 'pro-latest-accurate'
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
        config_widgets['XML_SNIPPET_MAX_LEN'].setRange(0, 100000)
        label_xml_snippet_max_len = QLabel("XML Snippet Max Length: ")
        label_xml_snippet_max_len.setToolTip(tooltips['XML_SNIPPET_MAX_LEN'])
        ai_layout.addRow(label_xml_snippet_max_len, config_widgets['XML_SNIPPET_MAX_LEN'])
        
        layout.addRow(ai_group)
    
    @staticmethod
    def _create_crawler_settings_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str]
    ) -> None:
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
    
    @staticmethod
    def _create_error_handling_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str]
    ) -> None:
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
    
    @staticmethod
    def _create_feature_toggles_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str]
    ) -> None:
        """Create the Feature Toggles group."""
        feature_toggle_group = QGroupBox("Feature Toggles")
        feature_toggle_layout = QFormLayout(feature_toggle_group)
        
        config_widgets['ENABLE_XML_CONTEXT'] = QCheckBox()
        label_enable_xml_context = QLabel("Enable XML Context: ")
        label_enable_xml_context.setToolTip(tooltips['ENABLE_XML_CONTEXT'])
        feature_toggle_layout.addRow(label_enable_xml_context, config_widgets['ENABLE_XML_CONTEXT'])
        
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
    
    @staticmethod
    def _create_mobsf_settings_group(
        layout: QFormLayout, 
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any
    ) -> None:
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
        logging.info(f"Setting initial MobSF checkbox state: {is_mobsf_enabled}")
        
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
        logging.info("Created test_mobsf_conn_btn directly on main_controller")
        
        main_controller.run_mobsf_analysis_btn = QPushButton("Run MobSF Analysis")
        mobsf_layout.addRow(main_controller.run_mobsf_analysis_btn)
        logging.info("Created run_mobsf_analysis_btn directly on main_controller")
        
        # Set initial button states based on checkbox
        main_controller.test_mobsf_conn_btn.setEnabled(is_mobsf_enabled)
        main_controller.run_mobsf_analysis_btn.setEnabled(is_mobsf_enabled)
        
        # Connect the checkbox to update button state - using a direct slot reference
        # Connect after buttons are created
        config_widgets['ENABLE_MOBSF_ANALYSIS'].stateChanged.connect(
            config_handler._on_mobsf_enabled_state_changed
        )
        
        layout.addRow(mobsf_group)
    
    @staticmethod
    def _create_control_buttons(controls_handler: Any) -> QGroupBox:
        """Create the control buttons group."""
        group = QGroupBox("Controls")
        layout = QHBoxLayout(group)
        
        controls_handler.save_config_btn = QPushButton("Save Config")
        controls_handler.start_btn = QPushButton("Start Crawler")
        controls_handler.stop_btn = QPushButton("Stop Crawler")
        controls_handler.stop_btn.setEnabled(False)
        
        controls_handler.save_config_btn.clicked.connect(controls_handler.save_config)
        controls_handler.start_btn.clicked.connect(controls_handler.start_crawler)
        controls_handler.stop_btn.clicked.connect(controls_handler.stop_crawler)
        
        layout.addWidget(controls_handler.save_config_btn)
        layout.addWidget(controls_handler.start_btn)
        layout.addWidget(controls_handler.stop_btn)
        
        return group
