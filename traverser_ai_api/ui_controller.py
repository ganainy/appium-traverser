import sys
import os
import json
import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QCheckBox, QSpinBox, 
    QTextEdit, QFormLayout, QFrame, QComboBox, QGroupBox,
    QScrollArea, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt, QProcess, Signal, Slot, QTimer
from PySide6.QtGui import QPixmap, QImage # QScreen is part of QtGui but often accessed via QApplication

import config

class CrawlerControllerWindow(QMainWindow):
    """Main window for the Appium Crawler Controller."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Appium Crawler Controller")
        
        # Get screen geometry
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry() # Use availableGeometry to avoid taskbars, etc.
            width = int(screen_geometry.width() * 0.9)
            height = int(screen_geometry.height() * 0.9)
            self.resize(width, height)
        else:
            # Fallback if primary screen is not available for some reason
            self.resize(1200, 800) 
        
        # Initialize instance variables
        self.crawler_process: Optional[QProcess] = None
        self.user_config: Dict[str, Any] = {}
        self.config_file_path = "user_config.json"
        self.current_screenshot: Optional[str] = None
        self.step_count = 0
        self.step_label: Optional[QLabel] = None  # Added
        self.last_action_label: Optional[QLabel] = None  # Added
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create left (config) and right (output) panels
        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()
        
        # Add panels to main layout with stretch factors
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)
        
        # Load configuration if exists
        self.load_config()
    
    def _create_left_panel(self) -> QWidget:
        """Creates the left panel with configuration options."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Create scrollable area for config inputs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QFormLayout(scroll_content)
        
        # Create configuration input widgets
        self._create_config_inputs(scroll_layout)
        
        # Add control buttons at the bottom
        controls_group = self._create_control_buttons()
        
        # Set up layouts
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        layout.addWidget(controls_group)
        
        return panel
    
    def _create_config_inputs(self, layout: QFormLayout):
        """Creates configuration input widgets."""
        # Create and store references to config input widgets
        self.config_widgets = {}

        tooltips = {
            'APPIUM_SERVER_URL': "URL of the running Appium server (e.g., http://127.0.0.1:4723).",
            'TARGET_DEVICE_UDID': "Unique Device Identifier (UDID) of the target Android device or emulator. Optional.",
            'NEW_COMMAND_TIMEOUT': "Seconds Appium waits for a new command before quitting the session. 0 means no timeout.",
            'APPIUM_IMPLICIT_WAIT': "Seconds Appium driver waits when trying to find elements before failing. Affects element finding strategies.",
            'APP_PACKAGE': "Package name of the target application (e.g., com.example.app).",
            'APP_ACTIVITY': "Launch activity of the target application (e.g., .MainActivity).",
            # 'GEMINI_API_KEY': "Your Google Gemini API key for AI-driven interactions.", # Removed
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

        # Appium Settings
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
        self.config_widgets['NEW_COMMAND_TIMEOUT'].setRange(0, 3600) # Allow 0 for no timeout
        label_new_command_timeout = QLabel("New Command Timeout (s): ❔")
        label_new_command_timeout.setToolTip(tooltips['NEW_COMMAND_TIMEOUT'])
        appium_layout.addRow(label_new_command_timeout, self.config_widgets['NEW_COMMAND_TIMEOUT'])
        
        self.config_widgets['APPIUM_IMPLICIT_WAIT'] = QSpinBox()
        self.config_widgets['APPIUM_IMPLICIT_WAIT'].setRange(0, 300)
        label_implicit_wait = QLabel("Implicit Wait (s): ❔")
        label_implicit_wait.setToolTip(tooltips['APPIUM_IMPLICIT_WAIT'])
        appium_layout.addRow(label_implicit_wait, self.config_widgets['APPIUM_IMPLICIT_WAIT'])
        layout.addRow(appium_group)

        # App Settings
        app_group = QGroupBox("App Settings")
        app_layout = QFormLayout(app_group)
        self.config_widgets['APP_PACKAGE'] = QLineEdit()
        label_app_package = QLabel("Package Name: ❔")
        label_app_package.setToolTip(tooltips['APP_PACKAGE'])
        app_layout.addRow(label_app_package, self.config_widgets['APP_PACKAGE'])
        
        self.config_widgets['APP_ACTIVITY'] = QLineEdit()
        label_app_activity = QLabel("Activity: ❔")
        label_app_activity.setToolTip(tooltips['APP_ACTIVITY'])
        app_layout.addRow(label_app_activity, self.config_widgets['APP_ACTIVITY'])
        layout.addRow(app_group)

        # AI Settings
        ai_group = QGroupBox("AI Settings")
        ai_layout = QFormLayout(ai_group)
        self.config_widgets['DEFAULT_MODEL_TYPE'] = QComboBox()
        # Assuming config.GEMINI_MODELS is accessible and has the model names as keys
        try:
            self.config_widgets['DEFAULT_MODEL_TYPE'].addItems(config.GEMINI_MODELS.keys())
        except AttributeError:
            self.log_output.append("Warning: Could not load GEMINI_MODELS from config.py for UI dropdown.")
            self.config_widgets['DEFAULT_MODEL_TYPE'].addItems(['flash-latest', 'flash-latest-fast', 'pro-latest-accurate']) # Fallback
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

        # Crawler Settings
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
        self.config_widgets['MAX_CRAWL_DURATION_SECONDS'].setRange(60, 86400) # Up to 24 hours
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
        self.config_widgets['ALLOWED_EXTERNAL_PACKAGES'].setFixedHeight(80) # Adjust height as needed
        label_allowed_external_packages = QLabel("Allowed External Packages (one per line): ❔")
        label_allowed_external_packages.setToolTip(tooltips['ALLOWED_EXTERNAL_PACKAGES'])
        crawler_layout.addRow(label_allowed_external_packages, self.config_widgets['ALLOWED_EXTERNAL_PACKAGES'])
        layout.addRow(crawler_group)
        
        # Error Handling Settings
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

        # Feature Toggles
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

        self._apply_defaults_from_config_to_widgets() # Apply config.py defaults upon creation
        self._update_crawl_mode_inputs_state() # Initial call to set correct state for crawl mode inputs
    
    def _update_crawl_mode_inputs_state(self, mode: Optional[str] = None):
        """Enables/disables crawl step/duration inputs based on crawl mode."""
        if mode is None:
            mode = self.config_widgets['CRAWL_MODE'].currentText()

        if mode == 'steps':
            if 'MAX_CRAWL_STEPS' in self.config_widgets:
                self.config_widgets['MAX_CRAWL_STEPS'].setEnabled(True)
            if 'MAX_CRAWL_DURATION_SECONDS' in self.config_widgets:
                self.config_widgets['MAX_CRAWL_DURATION_SECONDS'].setEnabled(False)
        elif mode == 'time':
            if 'MAX_CRAWL_STEPS' in self.config_widgets:
                self.config_widgets['MAX_CRAWL_STEPS'].setEnabled(False)
            if 'MAX_CRAWL_DURATION_SECONDS' in self.config_widgets:
                self.config_widgets['MAX_CRAWL_DURATION_SECONDS'].setEnabled(True)
        else: # Default or unknown state, perhaps disable both or enable based on a default
            if 'MAX_CRAWL_STEPS' in self.config_widgets:
                self.config_widgets['MAX_CRAWL_STEPS'].setEnabled(True) # Default to steps enabled
            if 'MAX_CRAWL_DURATION_SECONDS' in self.config_widgets:
                self.config_widgets['MAX_CRAWL_DURATION_SECONDS'].setEnabled(False)

    def _create_control_buttons(self) -> QGroupBox:
        """Creates the control buttons group."""
        group = QGroupBox("Controls")
        layout = QHBoxLayout(group)
        
        # Create buttons
        self.save_config_btn = QPushButton("Save Config")
        self.start_btn = QPushButton("Start Crawler")
        self.stop_btn = QPushButton("Stop Crawler")
        self.stop_btn.setEnabled(False)
        
        # Connect signals
        self.save_config_btn.clicked.connect(self.save_config)
        self.start_btn.clicked.connect(self.start_crawler)
        self.stop_btn.clicked.connect(self.stop_crawler)
        
        # Add buttons to layout
        layout.addWidget(self.save_config_btn)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        
        return group
    
    def _create_right_panel(self) -> QWidget:
        """Creates the right panel with output display."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Status bar with progress
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Status: Idle")
        self.progress_bar = QProgressBar()
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        
        # Step and Action status - Added
        step_action_layout = QHBoxLayout()
        self.step_label = QLabel("Step: 0")
        self.last_action_label = QLabel("Last Action: None")
        step_action_layout.addWidget(self.step_label)
        step_action_layout.addWidget(self.last_action_label)
        
        # Screenshot display
        self.screenshot_label = QLabel()
        self.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screenshot_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        # Add widgets to layout
        layout.addLayout(status_layout)
        layout.addLayout(step_action_layout) # Added
        layout.addWidget(self.screenshot_label)
        layout.addWidget(self.log_output, 1)
        
        return panel
    
    @Slot()
    def save_config(self):
        """Saves the current configuration to a JSON file."""
        config_data = {}
        for key, widget in self.config_widgets.items():
            if isinstance(widget, QLineEdit):
                config_data[key] = widget.text()
            elif isinstance(widget, QSpinBox):
                config_data[key] = widget.value()
            elif isinstance(widget, QCheckBox):
                config_data[key] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                config_data[key] = widget.currentText()
            elif isinstance(widget, QTextEdit): # Handle QTextEdit for ALLOWED_EXTERNAL_PACKAGES
                config_data[key] = [line.strip() for line in widget.toPlainText().split('\\n') if line.strip()]
        
        try:
            with open(self.config_file_path, 'w') as f:
                json.dump(config_data, f, indent=4)
            self.log_output.append("Configuration saved successfully.")
        except Exception as e:
            self.log_output.append(f"Error saving configuration: {e}")
    
    def load_config(self):
        """Loads configuration from the JSON file if it exists."""
        if not os.path.exists(self.config_file_path):
            # Load defaults from config.py
            self._load_defaults_from_config() # This will call the wrapper with logging
            # self.log_output.append("No user_config.json found. Loaded defaults from config.py.") # Logging is now in _load_defaults_from_config
            return
        
        try:
            with open(self.config_file_path, 'r') as f:
                self.user_config = json.load(f)
            
            # Update UI with loaded values
            for key, value in self.user_config.items():
                if key in self.config_widgets:
                    widget = self.config_widgets[key]
                    if isinstance(widget, QLineEdit):
                        widget.setText(str(value))
                    elif isinstance(widget, QSpinBox):
                        widget.setValue(int(value))
                    elif isinstance(widget, QCheckBox):
                        widget.setChecked(bool(value))
                    elif isinstance(widget, QComboBox):
                        index = widget.findText(str(value))
                        if index >= 0:
                            widget.setCurrentIndex(index)
                    elif isinstance(widget, QTextEdit): # Handle QTextEdit for ALLOWED_EXTERNAL_PACKAGES
                        if isinstance(value, list):
                            widget.setPlainText('\n'.join(value))
            
            self._update_crawl_mode_inputs_state() # Update state after loading config
            self.log_output.append("Configuration loaded successfully.")
        except Exception as e:
            self.log_output.append(f"Error loading configuration: {e}")
            self._load_defaults_from_config() # This will call the new wrapper with logging
    
    def _apply_defaults_from_config_to_widgets(self):
        """Applies default values from config.py to UI widgets.
           Does not log directly, intended for internal use or by a logging wrapper.
        """
        logging.debug("Attempting to apply default config values to UI widgets...")
        for key, widget in self.config_widgets.items():
            logging.debug(f"Processing default for UI widget bound to config key: '{key}'")
            if hasattr(config, key):
                value = getattr(config, key)
                logging.debug(f"Key '{key}' found in config.py. Retrieved value: '{value}' (type: {type(value)})")
                
                if isinstance(widget, QLineEdit):
                    widget.setText(str(value if value is not None else ""))
                    logging.debug(f"Set QLineEdit '{key}' to: '{widget.text()}'")
                elif isinstance(widget, QSpinBox):
                    try:
                        val_to_set = int(value)
                        widget.setValue(val_to_set)
                        logging.debug(f"Successfully set QSpinBox '{key}' to: {val_to_set}")
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Could not set QSpinBox '{key}' from config value: '{value}' (type: {type(value)}). Error: {e}. Setting to widget's minimum.")
                        widget.setValue(widget.minimum())
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                    logging.debug(f"Set QCheckBox '{key}' to: {widget.isChecked()}")
                elif isinstance(widget, QComboBox):
                    index = widget.findText(str(value))
                    if index >= 0:
                        widget.setCurrentIndex(index)
                        logging.debug(f"Set QComboBox '{key}' to index: {index} ('{str(value)}')")
                    else:
                        logging.warning(f"Default value '{value}' for QComboBox '{key}' not found in items. Current items: {[widget.itemText(i) for i in range(widget.count())]}")
                        if hasattr(self, 'log_output') and self.log_output: # Also log to UI log for visibility
                            self.log_output.append(f"Warning: Default value '{value}' for {key} not found in ComboBox items.")
                elif isinstance(widget, QTextEdit):
                    text_to_set = ""
                    if isinstance(value, list):
                        text_to_set = '\\n'.join(value)
                    elif value is not None:
                        text_to_set = str(value)
                    widget.setPlainText(text_to_set)
                    logging.debug(f"Set QTextEdit '{key}'") # Avoid logging potentially long text
            else:
                logging.warning(f"Config key '{key}' not found in config.py module using hasattr. Widget will retain its current value or value from user_config.json if loaded.")
                # If this is a QSpinBox, it will retain its initial value (likely its minimum).
                if hasattr(self, 'log_output') and self.log_output: # Also log to UI log for visibility
                    self.log_output.append(f"Warning: Config key '{key}' not found in config.py. Using existing or initial value for this UI field.")

    def _load_defaults_from_config(self):
        """Applies default values from config.py to UI widgets and logs the action."""
        self._apply_defaults_from_config_to_widgets()
        if hasattr(self, 'log_output') and self.log_output: # Check if log_output exists and is not None
            self.log_output.append("Loaded default values from config.py into UI.")
    
    @Slot()
    def start_crawler(self):
        """Starts the crawler process."""
        self.log_output.append("Attempting to start crawler...") # Added log

        if not self.crawler_process:
            self.log_output.append("Crawler process not already running. Proceeding to start.") # Added log
            # Save configuration before starting
            self.save_config()
            
            # Create QProcess
            self.crawler_process = QProcess()
            self.crawler_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            
            # Connect signals
            self.crawler_process.readyReadStandardOutput.connect(self.read_stdout)
            self.crawler_process.finished.connect(self.handle_process_finished)
            self.crawler_process.errorOccurred.connect(self.handle_process_error) 
            
            python_executable = sys.executable 
            module_to_run = "traverser_ai_api.main"

            # Set working directory to the project root
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            self.crawler_process.setWorkingDirectory(project_root)
            self.log_output.append(f"Set working directory for subprocess to: {project_root}")

            self.log_output.append(f"Executing: {python_executable} -u -m {module_to_run}")
            self.crawler_process.start(python_executable, ['-u', '-m', module_to_run])
            
            # Update UI
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("Status: Running...")
            self.progress_bar.setRange(0,0) # Indeterminate progress
        else:
            self.log_output.append("Crawler process is already considered active. Start button press ignored.") # Added log
    
    @Slot()
    def stop_crawler(self):
        """Stops the crawler process."""
        if self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running:
            self.crawler_process.terminate()
            self.crawler_process.waitForFinished(5000)  # Wait up to 5 seconds
            if self.crawler_process.state() == QProcess.ProcessState.Running:
                self.crawler_process.kill()  # Force kill if still running
    
    @Slot()
    def read_stdout(self):
        """Reads and processes standard output from the crawler process."""
        if not self.crawler_process:
            return

        output = self.crawler_process.readAllStandardOutput().data().decode()
        # No need to strip here if we process line by line and append raw lines
        lines = output.splitlines() 

        UI_STEP_PREFIX = "UI_STEP: "
        UI_ACTION_PREFIX = "UI_ACTION: "
        UI_SCREENSHOT_PREFIX = "UI_SCREENSHOT: "

        for line in lines:
            self.log_output.append(line)  # Append raw line to log

            if line.startswith(UI_STEP_PREFIX):
                step_data = line[len(UI_STEP_PREFIX):].strip()
                # Assuming step_data could be "current" or "current/max"
                current_step_str = step_data.split('/')[0]
                try:
                    self.step_count = int(current_step_str)
                    if self.config_widgets['CRAWL_MODE'].currentText() == 'steps':
                        max_steps = self.config_widgets['MAX_CRAWL_STEPS'].value()
                        if self.step_label:
                            self.step_label.setText(f"Step: {self.step_count}/{max_steps}")
                    elif self.step_label: # For time mode or other modes where only current step is relevant
                        self.step_label.setText(f"Step: {self.step_count}")
                    self.update_progress() # Update progress bar as well
                except ValueError:
                    self.log_output.append(f"Error parsing step data: {step_data}")

            elif line.startswith(UI_ACTION_PREFIX):
                action_data = line[len(UI_ACTION_PREFIX):].strip()
                if self.last_action_label:
                    self.last_action_label.setText(f"Last Action: {action_data}")

            elif line.startswith(UI_SCREENSHOT_PREFIX):
                screenshot_path = line[len(UI_SCREENSHOT_PREFIX):].strip()
                if os.path.exists(screenshot_path):
                    image = QImage(screenshot_path) # Load image using QImage
                    if not image.isNull():
                        pixmap = QPixmap.fromImage(image) # Convert QImage to QPixmap
                        # Scale pixmap to fit the label while keeping aspect ratio
                        scaled_pixmap = pixmap.scaled(
                            self.screenshot_label.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.screenshot_label.setPixmap(scaled_pixmap)
                        self.current_screenshot = screenshot_path
                    else:
                        self.log_output.append(f"Error loading screenshot image: {screenshot_path}")
                else:
                    self.log_output.append(f"Screenshot path not found: {screenshot_path}")
    
    # @Slot()
    # def handle_stdout(self):
    #     """Handles standard output from the crawler process."""
    #     # This functionality is now part of read_stdout
    #     if self.crawler_process:
    #         data = self.crawler_process.readAllStandardOutput().data().decode()
    #         self.log_output.append(data.strip())
            
    #         # Look for step updates
    #         if \"--- Step \" in data:
    #             try:
    #                 step = int(data.split("Step ")[1].split("/")[0])
    #                 self.step_count = step
    #                 self.update_progress()
    #             except Exception:
    #                 pass # Or log error
            
    #         # Look for screenshot updates
    #         if "Saved annotated screenshot:" in data:
    #             try:
    #                 screenshot_path = data.split("Saved annotated screenshot: ")[1].split(" (")[0]
    #                 # self.update_screenshot(screenshot_path) # Original call, now handled in read_stdout
    #             except Exception:
    #                 pass # Or log error

    @Slot(QProcess.ExitStatus) # Add type hint for clarity
    def handle_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handles the event when the crawler process finishes."""
        status_message = f"Crawler process finished. Exit code: {exit_code}, Status: {exit_status.name}"
        self.log_output.append(status_message)
        logging.info(status_message)

        self.crawler_process = None # Reset the process variable
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Status: Idle")
        self.progress_bar.setRange(0, 100) # Reset progress bar
        self.progress_bar.setValue(0)

    @Slot(QProcess.ProcessError)
    def handle_process_error(self, error: QProcess.ProcessError):
        """Handles errors that occur with the crawler process."""
        error_message = f"Crawler process error: {error.name}"
        if self.crawler_process:
            error_details = self.crawler_process.readAllStandardError().data().decode().strip()
            if error_details:
                error_message += f"\nDetails: {error_details}"
        
        self.log_output.append(error_message)
        logging.error(error_message)

        # Ensure UI is reset even on error
        if self.crawler_process: # Check if it's not None before trying to access methods
            # It's possible finished signal might also be emitted after an error, 
            # but resetting here ensures UI consistency if only errorOccurred is hit.
            pass # Don't reset self.crawler_process here, finished will handle it or it's already None

        # Reset UI elements regardless of whether finished is also called
        self.crawler_process = None # Crucial reset
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Status: Error")
        self.progress_bar.setRange(0, 100) # Reset progress bar
        self.progress_bar.setValue(0)

    def update_progress(self):
        """Updates the progress bar based on current step and crawl mode."""
        if self.config_widgets['CRAWL_MODE'].currentText() == 'steps':
            max_steps = self.config_widgets['MAX_CRAWL_STEPS'].value()
            if max_steps > 0:
                self.progress_bar.setRange(0, max_steps)
                self.progress_bar.setValue(self.step_count)
            else:
                self.progress_bar.setRange(0,0) # Indeterminate if max_steps is 0
        else: # For 'time' mode or other modes, use indeterminate progress
            self.progress_bar.setRange(0,0)
    
    def closeEvent(self, event):
        """Ensures the crawler process is terminated when the window is closed."""
        self.stop_crawler() # Attempt to gracefully stop
        super().closeEvent(event)

# Main application execution (for standalone testing)
if __name__ == '__main__':
    # Configure basic logging for the UI itself (optional)
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    app = QApplication(sys.argv)
    window = CrawlerControllerWindow()
    window.show()
    sys.exit(app.exec())