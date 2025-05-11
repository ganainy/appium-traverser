import sys
import os
import logging # Ensure logging is explicitly imported
import json # For save_config/load_config, ensure it's imported
import re # For parsing output from find_app_info.py
from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QCheckBox, QSpinBox,
    QTextEdit, QFormLayout, QFrame, QComboBox, QGroupBox,
    QScrollArea, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt, QProcess, Signal, Slot, QTimer, QIODevice
from PySide6.QtGui import QPixmap

import config # This existing import will be used

class CrawlerControllerWindow(QMainWindow):
    """Main window for the Appium Crawler Controller."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Appium Crawler Controller")

        # Get screen geometry
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            width = int(screen_geometry.width() * 0.9)
            height = int(screen_geometry.height() * 0.9)
            self.resize(width, height)
        else:
            self.resize(1200, 800)

        self.project_root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # Initialize instance variables
        self.crawler_process: Optional[QProcess] = None
        self.user_config: Dict[str, Any] = {}
        self.config_file_path = os.path.join(self.project_root_dir, "user_config.json")
        self.current_screenshot: Optional[str] = None
        self.step_count = 0
        self.step_label: Optional[QLabel] = None
        self.last_action_label: Optional[QLabel] = None

        # --- Health App Discovery ---
        self.find_app_info_script_path = os.path.join(self.project_root_dir, "traverser_ai_api", "find_app_info.py")
        self.find_apps_process: Optional[QProcess] = None
        self.find_apps_stdout_buffer: str = ""
        self.health_apps_data: List[Dict[str, Any]] = []
        self.current_health_app_list_file: Optional[str] = None
        # --- End Health App Discovery ---

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Create left (config) and right (output) panels
        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel() # self.log_output is initialized here

        # Add panels to main layout with stretch factors
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)

        # Load configuration if exists
        self.load_config() # Loads self.current_health_app_list_file

        # Attempt to load cached health apps after UI is set up and config loaded
        self._attempt_load_cached_health_apps()


        self._config_module_dir_path = None
        self._shutdown_flag_file_path = None
        if config and hasattr(config, '__file__') and config.__file__:
            try:
                self._config_module_dir_path = os.path.dirname(os.path.abspath(config.__file__))
                self._shutdown_flag_file_path = os.path.join(self._config_module_dir_path, "crawler_shutdown.flag")
                log_message = f"Shutdown flag path configured: {self._shutdown_flag_file_path}"
                if hasattr(self, 'log_output') and self.log_output:
                    self.log_output.append(log_message)
                else:
                    logging.info(log_message)
            except Exception as e:
                logging.error(f"Error determining shutdown flag path using 'config' module: {e}")
                self._shutdown_flag_file_path = None
        else:
            log_message = "Warning: The 'config' module or its '__file__' attribute was not found or is invalid. Graceful shutdown via flag will be disabled."
            if hasattr(self, 'log_output') and self.log_output:
                 self.log_output.append(log_message)
            else:
                logging.warning(log_message)
            self._shutdown_flag_file_path = None

        self.shutdown_timer = QTimer(self)
        self.shutdown_timer.setSingleShot(True)
        self.shutdown_timer.timeout.connect(self.force_stop_crawler_on_timeout)

        # Check if find_app_info.py script exists
        if not os.path.exists(self.find_app_info_script_path):
            error_msg = f"CRITICAL ERROR: find_app_info.py script not found at: {self.find_app_info_script_path}. App scanning will not work."
            logging.error(error_msg)
            if hasattr(self, 'log_output') and self.log_output:
                self.log_output.append(error_msg)
            if hasattr(self, 'app_scan_status_label'):
                self.app_scan_status_label.setText("App Scan: Script not found!")
            if hasattr(self, 'refresh_apps_btn'):
                self.refresh_apps_btn.setEnabled(False)

    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QFormLayout(scroll_content)
        self._create_config_inputs(scroll_layout)
        controls_group = self._create_control_buttons()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        layout.addWidget(controls_group)
        return panel

    def _create_config_inputs(self, layout: QFormLayout):
        self.config_widgets = {}
        tooltips = {
            'APPIUM_SERVER_URL': "URL of the running Appium server (e.g., http://127.0.0.1:4723).",
            'TARGET_DEVICE_UDID': "Unique Device Identifier (UDID) of the target Android device or emulator. Optional.",
            'NEW_COMMAND_TIMEOUT': "Seconds Appium waits for a new command before quitting the session. 0 means no timeout.",
            'APPIUM_IMPLICIT_WAIT': "Seconds Appium driver waits when trying to find elements before failing. Affects element finding strategies.",
            'APP_PACKAGE': "Package name of the target application (e.g., com.example.app). Auto-filled by Health App Selector.",
            'APP_ACTIVITY': "Launch activity of the target application (e.g., .MainActivity). Auto-filled by Health App Selector.",
            'DEFAULT_MODEL_TYPE': "The default Gemini model to use for AI operations.",
            'USE_CHAT_MEMORY': "Enable to allow the AI to remember previous interactions in the current session for better context.",
            'MAX_CHAT_HISTORY': "Maximum number of previous interactions to keep in AI's memory if chat memory is enabled.",
            'XML_SNIPPET_MAX_LEN': "Maximum characters of the XML page source to send to the AI for context.",
            'CRAWL_MODE': "'steps': Crawl for a fixed number of actions. 'time': Crawl for a fixed duration.",
            'MAX_CRAWL_STEPS': "Maximum number of actions to perform if CRAWL_MODE is 'steps'.",
            'MAX_CRAWL_DURATION_SECONDS': "Maximum duration in seconds for the crawl if CRAWL_MODE is 'time'.",
            'WAIT_AFTER_ACTION': "Seconds to wait for the UI to stabilize after performing an action.",
            'STABILITY_WAIT': "Seconds to wait before capturing the UI state (screenshot/XML) after an action, ensuring UI is stable.",
            'APP_LAUNCH_WAIT_TIME': "Seconds to wait after launching the app for it to stabilize before starting the crawl.",
            'VISUAL_SIMILARITY_THRESHOLD': "Perceptual hash distance threshold for comparing screenshots. Lower values mean screenshots must be more similar to be considered the same state.",
            'ALLOWED_EXTERNAL_PACKAGES': "List of package names (one per line) that the crawler can interact with outside the main target app (e.g., for logins, webviews).",
            'MAX_CONSECUTIVE_AI_FAILURES': "Maximum number of consecutive times the AI can fail to provide a valid action before stopping.",
            'MAX_CONSECUTIVE_MAP_FAILURES': "Maximum number of consecutive times the AI action cannot be mapped to a UI element before stopping.",
            'MAX_CONSECUTIVE_EXEC_FAILURES': "Maximum number of consecutive times an action execution can fail before stopping.",
            'ENABLE_XML_CONTEXT': "Enable to send a snippet of the current screen's XML layout to the AI for better context.",
            'ENABLE_TRAFFIC_CAPTURE': "Enable to capture network traffic (PCAP) during the crawl using PCAPdroid (requires PCAPdroid to be installed and configured on the device).",
            'CLEANUP_DEVICE_PCAP_FILE': "If traffic capture is enabled, delete the PCAP file from the device after successfully pulling it to the computer.",
            'CONTINUE_EXISTING_RUN': "Enable to resume a previous crawl session, using its existing database and screenshots. Disable to start a fresh run."
        }

        appium_group = QGroupBox("Appium Settings")
        appium_layout = QFormLayout(appium_group)
        self.config_widgets['APPIUM_SERVER_URL'] = QLineEdit()
        label_appium_url = QLabel("Server URL: ❔")
        label_appium_url.setToolTip(tooltips['APPIUM_SERVER_URL'])
        appium_layout.addRow(label_appium_url, self.config_widgets['APPIUM_SERVER_URL'])
        self.config_widgets['TARGET_DEVICE_UDID'] = QLineEdit()
        label_device_udid = QLabel("Target Device UDID (Optional): ❔")
        label_device_udid.setToolTip(tooltips['TARGET_DEVICE_UDID'])
        appium_layout.addRow(label_device_udid, self.config_widgets['TARGET_DEVICE_UDID'])
        self.config_widgets['NEW_COMMAND_TIMEOUT'] = QSpinBox()
        self.config_widgets['NEW_COMMAND_TIMEOUT'].setRange(0, 3600)
        label_new_command_timeout = QLabel("New Command Timeout (s): ❔")
        label_new_command_timeout.setToolTip(tooltips['NEW_COMMAND_TIMEOUT'])
        appium_layout.addRow(label_new_command_timeout, self.config_widgets['NEW_COMMAND_TIMEOUT'])
        self.config_widgets['APPIUM_IMPLICIT_WAIT'] = QSpinBox()
        self.config_widgets['APPIUM_IMPLICIT_WAIT'].setRange(0, 300)
        label_implicit_wait = QLabel("Implicit Wait (s): ❔")
        label_implicit_wait.setToolTip(tooltips['APPIUM_IMPLICIT_WAIT'])
        appium_layout.addRow(label_implicit_wait, self.config_widgets['APPIUM_IMPLICIT_WAIT'])
        layout.addRow(appium_group)

        app_group = QGroupBox("App Settings")
        app_layout = QFormLayout(app_group)

        # --- Health App Selector ---
        self.health_app_dropdown = QComboBox()
        self.health_app_dropdown.addItem("Select target app (Scan first)", None) # Add None as userData for default item
        self.health_app_dropdown.currentIndexChanged.connect(self._on_health_app_selected)
        app_layout.addRow(QLabel("Target Health App: ❔"), self.health_app_dropdown)
        self.health_app_dropdown.setToolTip("Select a health-related app discovered on the device. Use button below to scan.")

        self.refresh_apps_btn = QPushButton("Scan/Refresh Health Apps List")
        self.refresh_apps_btn.clicked.connect(self.trigger_scan_for_health_apps)
        self.refresh_apps_btn.setToolTip("Scans the connected device for installed applications and filters for health-related ones using AI.")
        app_layout.addRow(self.refresh_apps_btn)

        self.app_scan_status_label = QLabel("App Scan: Idle")
        app_layout.addRow(QLabel("Scan Status:"), self.app_scan_status_label)
        # --- End Health App Selector ---

        self.config_widgets['APP_PACKAGE'] = QLineEdit()
        self.config_widgets['APP_PACKAGE'].setReadOnly(True) # Made read-only, populated by dropdown
        label_app_package = QLabel("Package Name (Auto-filled): ❔")
        label_app_package.setToolTip(tooltips['APP_PACKAGE'])
        app_layout.addRow(label_app_package, self.config_widgets['APP_PACKAGE'])

        self.config_widgets['APP_ACTIVITY'] = QLineEdit()
        self.config_widgets['APP_ACTIVITY'].setReadOnly(True) # Made read-only, populated by dropdown
        label_app_activity = QLabel("Activity (Auto-filled): ❔")
        label_app_activity.setToolTip(tooltips['APP_ACTIVITY'])
        app_layout.addRow(label_app_activity, self.config_widgets['APP_ACTIVITY'])
        layout.addRow(app_group)

        ai_group = QGroupBox("AI Settings")
        ai_layout = QFormLayout(ai_group)
        self.config_widgets['DEFAULT_MODEL_TYPE'] = QComboBox()
        try:
            self.config_widgets['DEFAULT_MODEL_TYPE'].addItems(config.GEMINI_MODELS.keys())
        except AttributeError:
            self.log_output.append("Warning: Could not load GEMINI_MODELS from config.py for UI dropdown.")
            self.config_widgets['DEFAULT_MODEL_TYPE'].addItems(['flash-latest', 'flash-latest-fast', 'pro-latest-accurate'])
        label_model_type = QLabel("Default Model Type: ❔")
        label_model_type.setToolTip(tooltips['DEFAULT_MODEL_TYPE'])
        ai_layout.addRow(label_model_type, self.config_widgets['DEFAULT_MODEL_TYPE'])
        self.config_widgets['USE_CHAT_MEMORY'] = QCheckBox()
        label_use_chat_memory = QLabel("Use Chat Memory: ❔")
        label_use_chat_memory.setToolTip(tooltips['USE_CHAT_MEMORY'])
        ai_layout.addRow(label_use_chat_memory, self.config_widgets['USE_CHAT_MEMORY'])
        self.config_widgets['MAX_CHAT_HISTORY'] = QSpinBox()
        self.config_widgets['MAX_CHAT_HISTORY'].setRange(0, 100)
        label_max_chat_history = QLabel("Max Chat History: ❔")
        label_max_chat_history.setToolTip(tooltips['MAX_CHAT_HISTORY'])
        ai_layout.addRow(label_max_chat_history, self.config_widgets['MAX_CHAT_HISTORY'])
        self.config_widgets['XML_SNIPPET_MAX_LEN'] = QSpinBox()
        self.config_widgets['XML_SNIPPET_MAX_LEN'].setRange(0, 100000)
        label_xml_snippet_max_len = QLabel("XML Snippet Max Length: ❔")
        label_xml_snippet_max_len.setToolTip(tooltips['XML_SNIPPET_MAX_LEN'])
        ai_layout.addRow(label_xml_snippet_max_len, self.config_widgets['XML_SNIPPET_MAX_LEN'])
        layout.addRow(ai_group)

        crawler_group = QGroupBox("Crawler Settings")
        crawler_layout = QFormLayout(crawler_group)
        self.config_widgets['CRAWL_MODE'] = QComboBox()
        self.config_widgets['CRAWL_MODE'].addItems(['steps', 'time'])
        label_crawl_mode = QLabel("Crawl Mode: ❔")
        label_crawl_mode.setToolTip(tooltips['CRAWL_MODE'])
        crawler_layout.addRow(label_crawl_mode, self.config_widgets['CRAWL_MODE'])
        self.config_widgets['CRAWL_MODE'].currentTextChanged.connect(self._update_crawl_mode_inputs_state)
        self.config_widgets['MAX_CRAWL_STEPS'] = QSpinBox()
        self.config_widgets['MAX_CRAWL_STEPS'].setRange(1, 10000)
        label_max_crawl_steps = QLabel("Max Steps: ❔")
        label_max_crawl_steps.setToolTip(tooltips['MAX_CRAWL_STEPS'])
        crawler_layout.addRow(label_max_crawl_steps, self.config_widgets['MAX_CRAWL_STEPS'])
        self.config_widgets['MAX_CRAWL_DURATION_SECONDS'] = QSpinBox()
        self.config_widgets['MAX_CRAWL_DURATION_SECONDS'].setRange(60, 86400)
        label_max_crawl_duration = QLabel("Max Duration (s): ❔")
        label_max_crawl_duration.setToolTip(tooltips['MAX_CRAWL_DURATION_SECONDS'])
        crawler_layout.addRow(label_max_crawl_duration, self.config_widgets['MAX_CRAWL_DURATION_SECONDS'])
        self.config_widgets['WAIT_AFTER_ACTION'] = QSpinBox()
        self.config_widgets['WAIT_AFTER_ACTION'].setRange(0, 60)
        label_wait_after_action = QLabel("Wait After Action (s): ❔")
        label_wait_after_action.setToolTip(tooltips['WAIT_AFTER_ACTION'])
        crawler_layout.addRow(label_wait_after_action, self.config_widgets['WAIT_AFTER_ACTION'])
        self.config_widgets['STABILITY_WAIT'] = QSpinBox()
        self.config_widgets['STABILITY_WAIT'].setRange(0, 60)
        label_stability_wait = QLabel("Stability Wait (s): ❔")
        label_stability_wait.setToolTip(tooltips['STABILITY_WAIT'])
        crawler_layout.addRow(label_stability_wait, self.config_widgets['STABILITY_WAIT'])
        self.config_widgets['APP_LAUNCH_WAIT_TIME'] = QSpinBox()
        self.config_widgets['APP_LAUNCH_WAIT_TIME'].setRange(0, 300)
        label_app_launch_wait_time = QLabel("App Launch Wait Time (s): ❔")
        label_app_launch_wait_time.setToolTip(tooltips['APP_LAUNCH_WAIT_TIME'])
        crawler_layout.addRow(label_app_launch_wait_time, self.config_widgets['APP_LAUNCH_WAIT_TIME'])
        self.config_widgets['VISUAL_SIMILARITY_THRESHOLD'] = QSpinBox()
        self.config_widgets['VISUAL_SIMILARITY_THRESHOLD'].setRange(0, 100)
        label_visual_similarity = QLabel("Visual Similarity Threshold: ❔")
        label_visual_similarity.setToolTip(tooltips['VISUAL_SIMILARITY_THRESHOLD'])
        crawler_layout.addRow(label_visual_similarity, self.config_widgets['VISUAL_SIMILARITY_THRESHOLD'])
        self.config_widgets['ALLOWED_EXTERNAL_PACKAGES'] = QTextEdit()
        self.config_widgets['ALLOWED_EXTERNAL_PACKAGES'].setPlaceholderText("com.example.package1\\ncom.example.package2")
        self.config_widgets['ALLOWED_EXTERNAL_PACKAGES'].setFixedHeight(80)
        label_allowed_external_packages = QLabel("Allowed External Packages (one per line): ❔")
        label_allowed_external_packages.setToolTip(tooltips['ALLOWED_EXTERNAL_PACKAGES'])
        crawler_layout.addRow(label_allowed_external_packages, self.config_widgets['ALLOWED_EXTERNAL_PACKAGES'])
        layout.addRow(crawler_group)

        error_handling_group = QGroupBox("Error Handling Settings")
        error_handling_layout = QFormLayout(error_handling_group)
        self.config_widgets['MAX_CONSECUTIVE_AI_FAILURES'] = QSpinBox()
        self.config_widgets['MAX_CONSECUTIVE_AI_FAILURES'].setRange(1, 100)
        label_max_ai_failures = QLabel("Max Consecutive AI Failures: ❔")
        label_max_ai_failures.setToolTip(tooltips['MAX_CONSECUTIVE_AI_FAILURES'])
        error_handling_layout.addRow(label_max_ai_failures, self.config_widgets['MAX_CONSECUTIVE_AI_FAILURES'])
        self.config_widgets['MAX_CONSECUTIVE_MAP_FAILURES'] = QSpinBox()
        self.config_widgets['MAX_CONSECUTIVE_MAP_FAILURES'].setRange(1, 100)
        label_max_map_failures = QLabel("Max Consecutive Map Failures: ❔")
        label_max_map_failures.setToolTip(tooltips['MAX_CONSECUTIVE_MAP_FAILURES'])
        error_handling_layout.addRow(label_max_map_failures, self.config_widgets['MAX_CONSECUTIVE_MAP_FAILURES'])
        self.config_widgets['MAX_CONSECUTIVE_EXEC_FAILURES'] = QSpinBox()
        self.config_widgets['MAX_CONSECUTIVE_EXEC_FAILURES'].setRange(1, 100)
        label_max_exec_failures = QLabel("Max Consecutive Exec Failures: ❔")
        label_max_exec_failures.setToolTip(tooltips['MAX_CONSECUTIVE_EXEC_FAILURES'])
        error_handling_layout.addRow(label_max_exec_failures, self.config_widgets['MAX_CONSECUTIVE_EXEC_FAILURES'])
        layout.addRow(error_handling_group)

        feature_toggle_group = QGroupBox("Feature Toggles")
        feature_toggle_layout = QFormLayout(feature_toggle_group)
        self.config_widgets['ENABLE_XML_CONTEXT'] = QCheckBox()
        label_enable_xml_context = QLabel("Enable XML Context: ❔")
        label_enable_xml_context.setToolTip(tooltips['ENABLE_XML_CONTEXT'])
        feature_toggle_layout.addRow(label_enable_xml_context, self.config_widgets['ENABLE_XML_CONTEXT'])
        self.config_widgets['ENABLE_TRAFFIC_CAPTURE'] = QCheckBox()
        label_enable_traffic_capture = QLabel("Enable Traffic Capture: ❔")
        label_enable_traffic_capture.setToolTip(tooltips['ENABLE_TRAFFIC_CAPTURE'])
        feature_toggle_layout.addRow(label_enable_traffic_capture, self.config_widgets['ENABLE_TRAFFIC_CAPTURE'])
        self.config_widgets['CLEANUP_DEVICE_PCAP_FILE'] = QCheckBox()
        label_cleanup_pcap = QLabel("Cleanup Device PCAP after Pull: ❔")
        label_cleanup_pcap.setToolTip(tooltips['CLEANUP_DEVICE_PCAP_FILE'])
        feature_toggle_layout.addRow(label_cleanup_pcap, self.config_widgets['CLEANUP_DEVICE_PCAP_FILE'])
        self.config_widgets['CONTINUE_EXISTING_RUN'] = QCheckBox()
        label_continue_run = QLabel("Continue Existing Run: ❔")
        label_continue_run.setToolTip(tooltips['CONTINUE_EXISTING_RUN'])
        feature_toggle_layout.addRow(label_continue_run, self.config_widgets['CONTINUE_EXISTING_RUN'])
        layout.addRow(feature_toggle_group)

        self._apply_defaults_from_config_to_widgets()
        self._update_crawl_mode_inputs_state()

    def _update_crawl_mode_inputs_state(self, mode: Optional[str] = None):
        if mode is None:
            mode = self.config_widgets['CRAWL_MODE'].currentText()
        if 'MAX_CRAWL_STEPS' in self.config_widgets:
            self.config_widgets['MAX_CRAWL_STEPS'].setEnabled(mode == 'steps')
        if 'MAX_CRAWL_DURATION_SECONDS' in self.config_widgets:
            self.config_widgets['MAX_CRAWL_DURATION_SECONDS'].setEnabled(mode == 'time')

    def _create_control_buttons(self) -> QGroupBox:
        group = QGroupBox("Controls")
        layout = QHBoxLayout(group)
        self.save_config_btn = QPushButton("Save Config")
        self.start_btn = QPushButton("Start Crawler")
        self.stop_btn = QPushButton("Stop Crawler")
        self.stop_btn.setEnabled(False)
        self.save_config_btn.clicked.connect(self.save_config)
        self.start_btn.clicked.connect(self.start_crawler)
        self.stop_btn.clicked.connect(self.stop_crawler)
        layout.addWidget(self.save_config_btn)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        return group

    def _create_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Status: Idle")
        self.progress_bar = QProgressBar()
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        step_action_layout = QHBoxLayout()
        self.step_label = QLabel("Step: 0")
        self.last_action_label = QLabel("Last Action: None")
        step_action_layout.addWidget(self.step_label)
        step_action_layout.addWidget(self.last_action_label)
        self.screenshot_label = QLabel()
        self.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screenshot_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addLayout(status_layout)
        layout.addLayout(step_action_layout)
        layout.addWidget(self.screenshot_label)
        layout.addWidget(self.log_output, 1)
        return panel

    @Slot()
    def save_config(self):
        config_data = {}
        for key, widget in self.config_widgets.items():
            if isinstance(widget, QLineEdit): config_data[key] = widget.text()
            elif isinstance(widget, QSpinBox): config_data[key] = widget.value()
            elif isinstance(widget, QCheckBox): config_data[key] = widget.isChecked()
            elif isinstance(widget, QComboBox): config_data[key] = widget.currentText()
            elif isinstance(widget, QTextEdit):
                config_data[key] = [line.strip() for line in widget.toPlainText().split('\n') if line.strip()]
        
        # Save health app list path
        config_data['CURRENT_HEALTH_APP_LIST_FILE'] = self.current_health_app_list_file

        try:
            with open(self.config_file_path, 'w') as f:
                json.dump(config_data, f, indent=4)
            self.log_output.append("Configuration saved successfully.")
        except Exception as e:
            self.log_output.append(f"Error saving configuration: {e}")

    def load_config(self):
        if not os.path.exists(self.config_file_path):
            self._load_defaults_from_config()
            return
        try:
            with open(self.config_file_path, 'r') as f:
                self.user_config = json.load(f)
            for key, value in self.user_config.items():
                if key == 'CURRENT_HEALTH_APP_LIST_FILE':
                    self.current_health_app_list_file = value
                    continue # Handled separately by _attempt_load_cached_health_apps

                if key in self.config_widgets:
                    widget = self.config_widgets[key]
                    if isinstance(widget, QLineEdit): widget.setText(str(value))
                    elif isinstance(widget, QSpinBox): widget.setValue(int(value))
                    elif isinstance(widget, QCheckBox): widget.setChecked(bool(value))
                    elif isinstance(widget, QComboBox):
                        index = widget.findText(str(value))
                        if index >= 0: widget.setCurrentIndex(index)
                    elif isinstance(widget, QTextEdit):
                        if isinstance(value, list): widget.setPlainText('\n'.join(value))
            self._update_crawl_mode_inputs_state()
            self.log_output.append("Configuration loaded successfully.")
        except Exception as e:
            self.log_output.append(f"Error loading configuration: {e}")
            self._load_defaults_from_config()

    def _apply_defaults_from_config_to_widgets(self):
        for key, widget in self.config_widgets.items():
            if hasattr(config, key):
                value = getattr(config, key)
                if isinstance(widget, QLineEdit): widget.setText(str(value if value is not None else ""))
                elif isinstance(widget, QSpinBox):
                    try: widget.setValue(int(value))
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Could not set QSpinBox '{key}' from config value: '{value}'. Error: {e}.")
                        widget.setValue(widget.minimum())
                elif isinstance(widget, QCheckBox): widget.setChecked(bool(value))
                elif isinstance(widget, QComboBox):
                    index = widget.findText(str(value))
                    if index >= 0: widget.setCurrentIndex(index)
                    else: logging.warning(f"Default value '{value}' for QComboBox '{key}' not found.")
                elif isinstance(widget, QTextEdit):
                    text_to_set = '\n'.join(value) if isinstance(value, list) else str(value if value is not None else "")
                    widget.setPlainText(text_to_set)
            else:
                logging.warning(f"Config key '{key}' not found in config.py module.")

    def _load_defaults_from_config(self):
        self._apply_defaults_from_config_to_widgets()
        if hasattr(self, 'log_output') and self.log_output:
            self.log_output.append("Loaded default values from config.py into UI.")

    # --- Health App Discovery Methods ---
    def _attempt_load_cached_health_apps(self):
        """Tries to load health apps from the cached file path if it exists."""
        if self.current_health_app_list_file and os.path.exists(self.current_health_app_list_file):
            self.log_output.append(f"Attempting to load cached health apps from: {self.current_health_app_list_file}")
            self._load_health_apps_from_file(self.current_health_app_list_file)
        else:
            self.log_output.append("No cached health app list found or path is invalid. Scan needed.")
            # Clear dropdown if no valid cache
            self.health_app_dropdown.clear()
            self.health_app_dropdown.addItem("Select target app (Scan first)", None)
            self.health_apps_data = []


    @Slot()
    def trigger_scan_for_health_apps(self):
        """Starts the process of scanning for health apps, forcing a rescan."""
        self._execute_scan_for_health_apps(force_rescan=True)

    def _execute_scan_for_health_apps(self, force_rescan: bool = False):
        if not force_rescan and self.current_health_app_list_file and os.path.exists(self.current_health_app_list_file):
            self.log_output.append(f"Using cached health app list: {self.current_health_app_list_file}")
            self._load_health_apps_from_file(self.current_health_app_list_file)
            return

        if self.find_apps_process and self.find_apps_process.state() != QProcess.ProcessState.NotRunning:
            self.log_output.append("App scan is already in progress.")
            self.app_scan_status_label.setText("App Scan: Scan in progress...")
            return

        if not os.path.exists(self.find_app_info_script_path):
            msg = f"find_app_info.py script not found at {self.find_app_info_script_path}. Cannot scan."
            self.log_output.append(msg)
            self.app_scan_status_label.setText("App Scan: Script not found!")
            logging.error(msg)
            return

        self.log_output.append("Starting health app scan...")
        self.app_scan_status_label.setText("App Scan: Scanning...")
        self.refresh_apps_btn.setEnabled(False)
        self.health_app_dropdown.setEnabled(False)
        self.find_apps_stdout_buffer = "" # Reset buffer

        self.find_apps_process = QProcess()
        self.find_apps_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.find_apps_process.setWorkingDirectory(self.project_root_dir)

        self.find_apps_process.readyReadStandardOutput.connect(self._on_find_apps_stdout_ready)
        self.find_apps_process.finished.connect(self._on_find_apps_finished)
        
        python_executable = sys.executable
        # Run find_app_info.py as a script. It uses argparse for --mode.
        # Ensure find_app_info.py has ENABLE_AI_FILTERING=True and GEMINI_API_KEY is in .env
        self.find_apps_process.start(python_executable, ['-u', self.find_app_info_script_path, '--mode', 'discover'])

    @Slot()
    def _on_find_apps_stdout_ready(self):
        if not self.find_apps_process: return
        data = self.find_apps_process.readAllStandardOutput().data().decode(errors='ignore')
        self.find_apps_stdout_buffer += data
        # Optionally, could also append to self.log_output for live script output,
        # but it might be noisy. Let's log key messages.
        # For now, just buffer it for final parsing.

    @Slot(int, QProcess.ExitStatus)
    def _on_find_apps_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        self.log_output.append(f"App scan process finished. Exit code: {exit_code}, Status: {exit_status.name}")
        self.app_scan_status_label.setText(f"App Scan: Finished (Code: {exit_code})")
        self.refresh_apps_btn.setEnabled(True)
        self.health_app_dropdown.setEnabled(True)

        if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            # Try to parse the output file path from stdout
            match = re.search(r"Cache file generated at: (.*)", self.find_apps_stdout_buffer)
            if match:
                file_path = match.group(1).strip()
                self.log_output.append(f"App scan successful. Health app data file: {file_path}")
                if os.path.exists(file_path):
                    self.current_health_app_list_file = file_path
                    self._load_health_apps_from_file(file_path)
                    self.save_config() # Save the new path
                else:
                    self.log_output.append(f"Error: App scan reported success, but file not found: {file_path}")
                    self.app_scan_status_label.setText("App Scan: File not found after scan.")
            else:
                self.log_output.append("Error: App scan finished, but could not find generated file path in output.")
                self.log_output.append("--- Script Output ---")
                self.log_output.append(self.find_apps_stdout_buffer)
                self.log_output.append("--- End Script Output ---")
                self.app_scan_status_label.setText("App Scan: Output path parse error.")
        else:
            self.log_output.append(f"Error: App scan process failed.")
            self.log_output.append("--- Script Output ---")
            self.log_output.append(self.find_apps_stdout_buffer)
            self.log_output.append("--- End Script Output ---")
            self.app_scan_status_label.setText(f"App Scan: Failed (Code: {exit_code})")

        self.find_apps_process = None # Clear process reference

    def _load_health_apps_from_file(self, file_path: str):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.health_apps_data = json.load(f)

            self.health_app_dropdown.clear()
            self.health_app_dropdown.addItem("Select target app...", None) # Default item

            if not self.health_apps_data:
                self.log_output.append("No health-related apps found or list is empty.")
                self.app_scan_status_label.setText("App Scan: No health apps found.")
                return

            for app_info in self.health_apps_data:
                display_name = app_info.get('app_name') or app_info.get('package_name', 'Unknown App')
                self.health_app_dropdown.addItem(display_name, app_info) # Store full dict as userData

            self.log_output.append(f"Successfully loaded {len(self.health_apps_data)} health apps into dropdown.")
            self.app_scan_status_label.setText(f"App Scan: Loaded {len(self.health_apps_data)} apps.")
        except Exception as e:
            self.log_output.append(f"Error loading health apps from file {file_path}: {e}")
            self.app_scan_status_label.setText("App Scan: Error loading file.")
            self.health_app_dropdown.clear()
            self.health_app_dropdown.addItem("Select target app (Scan/Load Error)", None)
            self.health_apps_data = []

    @Slot(int)
    def _on_health_app_selected(self, index: int):
        selected_data = self.health_app_dropdown.itemData(index)
        if selected_data and isinstance(selected_data, dict):
            app_package = selected_data.get('package_name', '')
            app_activity = selected_data.get('activity_name', '')
            self.config_widgets['APP_PACKAGE'].setText(app_package)
            self.config_widgets['APP_ACTIVITY'].setText(app_activity)
            self.log_output.append(f"Selected app: {selected_data.get('app_name', app_package)}. Package: {app_package}, Activity: {app_activity}")
        else:
            # "Select target app..." or error item selected
            self.config_widgets['APP_PACKAGE'].setText("")
            self.config_widgets['APP_ACTIVITY'].setText("")
    # --- End Health App Discovery Methods ---


    @Slot()
    def start_crawler(self):
        if self._shutdown_flag_file_path and os.path.exists(self._shutdown_flag_file_path):
            log_msg = f"Found existing shutdown flag: {self._shutdown_flag_file_path}. Removing."
            if hasattr(self, 'log_output'): self.log_output.append(log_msg)
            else: logging.info(log_msg)
            try: os.remove(self._shutdown_flag_file_path)
            except OSError as e:
                err_msg = f"Could not remove existing shutdown flag: {e}."
                if hasattr(self, 'log_output'): self.log_output.append(err_msg)
                else: logging.warning(err_msg)

        if hasattr(self, 'log_output'): self.log_output.append("Attempting to start crawler...")
        else: logging.info("Attempting to start crawler...")

        if not self.crawler_process or self.crawler_process.state() == QProcess.ProcessState.NotRunning:
            if hasattr(self, 'log_output'): self.log_output.append("Crawler process not already running.")
            if hasattr(self, 'save_config'): self.save_config()

            # Critical Check: Ensure an app is selected if health_app_dropdown has items
            if self.health_app_dropdown.count() > 1: # More than just "Select target app..."
                if not self.config_widgets['APP_PACKAGE'].text() or not self.config_widgets['APP_ACTIVITY'].text():
                    error_msg = "Error: An app must be selected from the 'Target Health App' dropdown, or Package/Activity must be manually set if not using the scanner."
                    self.log_output.append(error_msg)
                    self.status_label.setText(f"Status: Error - {error_msg}")
                    logging.error(error_msg)
                    # Optionally, pop up a QMessageBox here
                    return # Prevent crawler start

            self.crawler_process = QProcess()
            self.crawler_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            if hasattr(self, 'read_stdout'): self.crawler_process.readyReadStandardOutput.connect(self.read_stdout)
            self.crawler_process.finished.connect(self.handle_process_finished)
            if hasattr(self, 'handle_process_error'): self.crawler_process.errorOccurred.connect(self.handle_process_error)

            python_executable = sys.executable
            module_to_run = "traverser_ai_api.main"
            self.crawler_process.setWorkingDirectory(self.project_root_dir) # Use project_root_dir
            if hasattr(self, 'log_output'): self.log_output.append(f"Set working directory for subprocess to: {self.project_root_dir}")
            if hasattr(self, 'log_output'): self.log_output.append(f"Executing: {python_executable} -u -m {module_to_run}")
            self.crawler_process.start(python_executable, ['-u', '-m', module_to_run])

            if hasattr(self, 'start_btn'): self.start_btn.setEnabled(False)
            if hasattr(self, 'stop_btn'): self.stop_btn.setEnabled(True)
            if hasattr(self, 'status_label'): self.status_label.setText("Status: Running...")
            if hasattr(self, 'progress_bar'): self.progress_bar.setRange(0,0)
        else:
            if hasattr(self, 'log_output'): self.log_output.append("Crawler process already active.")
            else: logging.info("Crawler process already active.")

    @Slot()
    def stop_crawler(self):
        if self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running:
            if hasattr(self, 'stop_btn'): self.stop_btn.setEnabled(False)
            if self._shutdown_flag_file_path:
                try:
                    with open(self._shutdown_flag_file_path, 'w') as f: f.write("stop")
                    msg = "Shutdown signal sent via flag. Waiting (15s)..."
                    if hasattr(self, 'log_output'): self.log_output.append(msg)
                    else: logging.info(msg)
                    if hasattr(self, 'status_label'): self.status_label.setText("Status: Stopping (graceful)...")
                    self.shutdown_timer.start(15000)
                    return
                except Exception as e:
                    msg_err = f"Error creating shutdown flag: {e}. Terminating."
                    if hasattr(self, 'log_output'): self.log_output.append(msg_err)
                    else: logging.error(msg_err)
            msg_term = "Attempting direct termination (7s timeout)..."
            if hasattr(self, 'log_output'): self.log_output.append(msg_term)
            else: logging.info(msg_term)
            if hasattr(self, 'status_label'): self.status_label.setText("Status: Terminating...")
            self.crawler_process.terminate()
            self.shutdown_timer.start(7000)
        else:
            msg_ign = "Stop ignored: Crawler not running."
            if hasattr(self, 'log_output'): self.log_output.append(msg_ign)
            else: logging.info(msg_ign)
            if not (self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running):
                if hasattr(self, 'stop_btn'): self.stop_btn.setEnabled(False)
                if hasattr(self, 'start_btn'): self.start_btn.setEnabled(True)
                if hasattr(self, 'status_label'): self.status_label.setText("Status: Idle/Stopped")

    @Slot()
    def force_stop_crawler_on_timeout(self):
        if self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running:
            msg_timeout = "Previous stop timed out. Terminating..."
            if hasattr(self, 'log_output'): self.log_output.append(msg_timeout)
            else: logging.warning(msg_timeout)
            if hasattr(self, 'status_label'): self.status_label.setText("Status: Terminating (timeout)...")
            self.crawler_process.terminate()
            if not self.crawler_process.waitForFinished(30000):
                msg_kill = "Process still running after terminate. Killing."
                if hasattr(self, 'log_output'): self.log_output.append(msg_kill)
                else: logging.warning(msg_kill)
                if hasattr(self, 'status_label'): self.status_label.setText("Status: Killing (timeout)...")
                self.crawler_process.kill()
        else:
            msg_not_run = "Force stop timeout, but process not running."
            if hasattr(self, 'log_output'): self.log_output.append(msg_not_run)
            else: logging.info(msg_not_run)

    def read_stdout(self):
        if not self.crawler_process: return
        data = self.crawler_process.readAllStandardOutput().data().decode(errors='ignore')
        lines = data.strip().split('\n')
        processed_once = False
        for line in lines:
            if not line.strip(): continue
            print(line)
            if line.startswith("UI_STATUS:"):
                status = line.replace("UI_STATUS:", "").strip()
                self.status_label.setText(f"Status: {status}")
                self.progress_bar.setRange(0, 0 if status in ["RUNNING", "INITIALIZING"] else 100)
                if status not in ["RUNNING", "INITIALIZING"]: self.progress_bar.setValue(100 if status in ["SUCCESS", "FAILURE_UNHANDLED_EXCEPTION"] else 0)
                processed_once = True
            elif line.startswith("UI_STEP:"):
                try:
                    self.step_count = int(line.replace("UI_STEP:", "").strip())
                    if self.step_label: self.step_label.setText(f"Step: {self.step_count}")
                except ValueError: self.log_output.append(f"Warning: Bad step count: {line}")
                except Exception as e: self.log_output.append(f"Error updating step: {e}")
                processed_once = True
            elif line.startswith("UI_ACTION:"):
                action_desc = line.replace("UI_ACTION:", "").strip()
                if self.last_action_label: self.last_action_label.setText(f"Last Action: {action_desc}")
                processed_once = True
            elif line.startswith("UI_SCREENSHOT:"):
                self.current_screenshot = line.replace("UI_SCREENSHOT:", "").strip()
                if os.path.exists(self.current_screenshot):
                    try:
                        pixmap = QPixmap(self.current_screenshot)
                        scaled = pixmap.scaled(self.screenshot_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.screenshot_label.setPixmap(scaled)
                    except Exception as e:
                        self.log_output.append(f"Error loading screenshot {self.current_screenshot}: {e}")
                        self.screenshot_label.setText("Error loading screenshot.")
                else:
                    self.screenshot_label.setText(f"Screenshot not found: {os.path.basename(self.current_screenshot)}")
                processed_once = True
            elif line.startswith("UI_END:"):
                end_msg = line.replace("UI_END:", "").strip()
                self.status_label.setText(f"Status: Ended ({end_msg})")
                self.progress_bar.setRange(0, 100); self.progress_bar.setValue(100)
                processed_once = True
            else:
                self.log_output.append(line)
                processed_once = True
        if not processed_once and data.strip(): self.log_output.append(data.strip())
        QApplication.processEvents()

    @Slot(int, QProcess.ExitStatus)
    @Slot(int, QProcess.ExitStatus)
    def handle_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        self.shutdown_timer.stop()
        if self._shutdown_flag_file_path and os.path.exists(self._shutdown_flag_file_path):
            try:
                os.remove(self._shutdown_flag_file_path)
                msg = "Cleaned up shutdown flag by UI controller."
                if hasattr(self, 'log_output'): self.log_output.append(msg)
                else: logging.info(msg)
            except OSError as e:
                msg_err = f"UI controller could not remove shutdown flag: {e}"
                if hasattr(self, 'log_output'): self.log_output.append(msg_err)
                else: logging.warning(msg_err)
        status_text = f"Finished. Exit code: {exit_code}"
        if exit_status == QProcess.ExitStatus.CrashExit: status_text = f"Crashed. Exit code: {exit_code}"
        final_msg = f"Status: {status_text}"
        if hasattr(self, 'log_output'): self.log_output.append(final_msg)
        else: logging.info(final_msg)
        if hasattr(self, 'status_label'): self.status_label.setText(final_msg)
        if hasattr(self, 'start_btn'): self.start_btn.setEnabled(True)
        if hasattr(self, 'stop_btn'): self.stop_btn.setEnabled(False)
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setRange(0,100)
            self.progress_bar.setValue(100 if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0 else 0)
        self.crawler_process = None

    @Slot(QProcess.ProcessError)
    def handle_process_error(self, error: QProcess.ProcessError):
        try: error_name = QProcess.ProcessError(error).name
        except Exception: error_name = f"Unknown Error ({error})"
        error_message = f"Crawler process error: {error_name}"
        output_details = ""
        if self.crawler_process and self.crawler_process.isOpen():
            # Simplified output reading attempt
            if self.crawler_process.bytesAvailable() > 0:
                output_details = self.crawler_process.readAll().data().decode(errors='ignore').strip()
        if output_details: error_message += f"\nLast output: {output_details}"
        self.log_output.append(error_message)
        logging.error(error_message)
        # Simplified cleanup
        if self.crawler_process:
            for signal_name in ['finished', 'errorOccurred', 'readyReadStandardOutput']:
                try: getattr(self.crawler_process, signal_name).disconnect()
                except (TypeError, RuntimeError): pass
        self.crawler_process = None
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.status_label.setText(f"Status: Error ({error_name})")
        self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0)

    def update_progress(self):
        if self.config_widgets['CRAWL_MODE'].currentText() == 'steps':
            max_steps = self.config_widgets['MAX_CRAWL_STEPS'].value()
            self.progress_bar.setRange(0, max_steps if max_steps > 0 else 0)
            if max_steps > 0: self.progress_bar.setValue(self.step_count)
        else: self.progress_bar.setRange(0,0)

    def closeEvent(self, event):
        self.stop_crawler()
        # Stop app scan process if running
        if self.find_apps_process and self.find_apps_process.state() != QProcess.ProcessState.NotRunning:
            self.log_output.append("Closing UI: Terminating app scan process...")
            self.find_apps_process.terminate()
            if not self.find_apps_process.waitForFinished(5000): # 5 sec timeout
                self.find_apps_process.kill()
        super().closeEvent(event)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    app = QApplication(sys.argv)
    window = CrawlerControllerWindow()
    window.show()
    sys.exit(app.exec())