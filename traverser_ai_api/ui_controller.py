import sys
import os
import logging # Ensure logging is explicitly imported
import json # For save_config/load_config, ensure it's imported
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QCheckBox, QSpinBox, 
    QTextEdit, QFormLayout, QFrame, QComboBox, QGroupBox,
    QScrollArea, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt, QProcess, Signal, Slot, QTimer, QIODevice
from PySide6.QtGui import QPixmap

# --- (Assuming config.py is in the same directory or package) ---
# This is used to determine where to place the shutdown flag.
# It's placed here to ensure `config` is imported before CrawlerControllerWindow uses it.
# If this causes issues, the import can be moved into __init__ with more robust error handling.
# try:
#     from . import config as traverser_config
# except ImportError:
#     traverser_config = None
#     logging.warning("Could not import .config module at the top level of ui_controller.py. Shutdown flag path may not be configured correctly.")
# Removed the above block

import config # This existing import will be used

class CrawlerControllerWindow(QMainWindow):
    """Main window for the Appium Crawler Controller."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
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
        right_panel = self._create_right_panel() # self.log_output is initialized here
        
        # Add panels to main layout with stretch factors
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)
        
        # Load configuration if exists
        self.load_config()

        self._config_module_dir_path = None
        self._shutdown_flag_file_path = None
        # Use the 'config' module (from 'import config') to determine the path,
        # as 'traverser_config' (from relative import) might be None when run as a script.
        # Also ensure config.__file__ is not None or empty string.
        if config and hasattr(config, '__file__') and config.__file__:
            try:
                # Ensure config.__file__ is not None before calling abspath
                self._config_module_dir_path = os.path.dirname(os.path.abspath(config.__file__)) # Use config.__file__
                self._shutdown_flag_file_path = os.path.join(self._config_module_dir_path, "crawler_shutdown.flag")
                log_message = f"Shutdown flag path configured: {self._shutdown_flag_file_path}"
                # Defer logging to log_output until it's initialized, or use standard logging
                if hasattr(self, 'log_output') and self.log_output:
                    self.log_output.append(log_message)
                else:
                    # If log_output is not yet available, use standard logging.
                    logging.info(log_message)
            except Exception as e:
                # Log error using standard logging as self.log_output might not be available
                logging.error(f"Error determining shutdown flag path using 'config' module: {e}") # Updated error message
                self._shutdown_flag_file_path = None # Ensure it's None on error
        else:
            # This case means 'import config' failed or config.__file__ is not set.
            log_message = "Warning: The 'config' module or its '__file__' attribute was not found or is invalid. Graceful shutdown via flag will be disabled." # Updated warning message
            if hasattr(self, 'log_output') and self.log_output:
                 self.log_output.append(log_message)
            else:
                # If log_output is not yet available, use standard logging.
                logging.warning(log_message)
            self._shutdown_flag_file_path = None

        self.shutdown_timer = QTimer(self)
        self.shutdown_timer.setSingleShot(True)
        self.shutdown_timer.timeout.connect(self.force_stop_crawler_on_timeout)
    
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
        for key, widget in self.config_widgets.items():
            if hasattr(config, key):
                value = getattr(config, key)
                
                if isinstance(widget, QLineEdit):
                    widget.setText(str(value if value is not None else ""))
                elif isinstance(widget, QSpinBox):
                    try:
                        val_to_set = int(value)
                        widget.setValue(val_to_set)
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Could not set QSpinBox '{key}' from config value: '{value}' (type: {type(value)}). Error: {e}. Setting to widget's minimum.")
                        widget.setValue(widget.minimum())
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QComboBox):
                    index = widget.findText(str(value))
                    if index >= 0:
                        widget.setCurrentIndex(index)
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
            else:
                logging.warning(f"Config key '{key}' not found in config.py module using hasattr. Widget will retain its current value or value from user_config.json if loaded.")
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
        # Ensure flag is not present from a previous unclean shutdown
        if self._shutdown_flag_file_path and os.path.exists(self._shutdown_flag_file_path):
            log_msg = f"Found existing shutdown flag: {self._shutdown_flag_file_path}. Removing."
            if hasattr(self, 'log_output') and self.log_output: self.log_output.append(log_msg)
            else: logging.info(log_msg)
            try:
                os.remove(self._shutdown_flag_file_path)
            except OSError as e:
                err_msg = f"Could not remove existing shutdown flag: {e}. Crawler might not start correctly."
                if hasattr(self, 'log_output') and self.log_output: self.log_output.append(err_msg)
                else: logging.warning(err_msg)
        
        if hasattr(self, 'log_output') and self.log_output:
            self.log_output.append("Attempting to start crawler...")
        else: # Fallback if log_output not ready (e.g. during early init)
            logging.info("Attempting to start crawler...")

        # Ensure crawler_process is either None or not running before starting
        if not self.crawler_process or self.crawler_process.state() == QProcess.ProcessState.NotRunning:
            if hasattr(self, 'log_output') and self.log_output:
                 self.log_output.append("Crawler process not already running. Proceeding to start.")
            
            if hasattr(self, 'save_config'): # Check if method exists
                self.save_config() 
            
            self.crawler_process = QProcess()
            self.crawler_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            
            # Connect signals
            if hasattr(self, 'read_stdout'): self.crawler_process.readyReadStandardOutput.connect(self.read_stdout)
            self.crawler_process.finished.connect(self.handle_process_finished)
            if hasattr(self, 'handle_process_error'): self.crawler_process.errorOccurred.connect(self.handle_process_error) 
            
            python_executable = sys.executable 
            module_to_run = "traverser_ai_api.main" # Ensure this is the correct module

            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            self.crawler_process.setWorkingDirectory(project_root)
            if hasattr(self, 'log_output'): self.log_output.append(f"Set working directory for subprocess to: {project_root}")

            if hasattr(self, 'log_output'): self.log_output.append(f"Executing: {python_executable} -u -m {module_to_run}")
            self.crawler_process.start(python_executable, ['-u', '-m', module_to_run])
            
            # Update UI
            if hasattr(self, 'start_btn'): self.start_btn.setEnabled(False)
            if hasattr(self, 'stop_btn'): self.stop_btn.setEnabled(True)
            if hasattr(self, 'status_label'): self.status_label.setText("Status: Running...")
            if hasattr(self, 'progress_bar'): self.progress_bar.setRange(0,0) # Indeterminate progress
        else:
            if hasattr(self, 'log_output') and self.log_output:
                self.log_output.append("Crawler process is already considered active. Start button press ignored.")
            else:
                logging.info("Crawler process is already considered active. Start button press ignored.")
    
    @Slot()
    def stop_crawler(self):
        """Initiates graceful shutdown of the crawler process."""
        if self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running:
            if hasattr(self, 'stop_btn'): self.stop_btn.setEnabled(False) # Disable button early

            if self._shutdown_flag_file_path:
                try:
                    with open(self._shutdown_flag_file_path, 'w') as f:
                        f.write("stop")
                    msg_graceful = "Shutdown signal sent via flag file. Waiting for graceful exit (15s)..."
                    if hasattr(self, 'log_output'): self.log_output.append(msg_graceful)
                    else: logging.info(msg_graceful)
                    if hasattr(self, 'status_label'): self.status_label.setText("Status: Stopping (graceful)...")
                    self.shutdown_timer.start(15000) # 15 seconds for graceful shutdown
                    return # Wait for timer or process finished signal
                except Exception as e:
                    msg_err_flag = f"Error creating shutdown flag: {e}. Proceeding with direct termination."
                    if hasattr(self, 'log_output'): self.log_output.append(msg_err_flag)
                    else: logging.error(msg_err_flag)
                    # Fall through to terminate if flag creation failed

            # Fallback: Flag path not set, or flag creation failed
            msg_terminate = "Attempting direct termination (7s timeout)..."
            if hasattr(self, 'log_output'): self.log_output.append(msg_terminate)
            else: logging.info(msg_terminate)
            if hasattr(self, 'status_label'): self.status_label.setText("Status: Terminating...")
            self.crawler_process.terminate()
            self.shutdown_timer.start(7000) # 7 seconds for terminate to work before force_stop_crawler_on_timeout
        else:
            msg_ignored = "Stop command ignored: Crawler process not running or not initialized."
            if hasattr(self, 'log_output'): self.log_output.append(msg_ignored)
            else: logging.info(msg_ignored)
            # Ensure UI consistency if process is already stopped or never started
            if not (self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running):
                if hasattr(self, 'stop_btn'): self.stop_btn.setEnabled(False)
                if hasattr(self, 'start_btn'): self.start_btn.setEnabled(True)
                if hasattr(self, 'status_label'): self.status_label.setText("Status: Idle/Stopped")

    @Slot()
    def force_stop_crawler_on_timeout(self):
        """Called by QTimer if graceful shutdown or initial terminate takes too long."""
        if self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running:
            msg_timeout = "Previous stop attempt timed out. Attempting terminate..."
            if hasattr(self, 'log_output'): self.log_output.append(msg_timeout)
            else: logging.warning(msg_timeout)
            if hasattr(self, 'status_label'): self.status_label.setText("Status: Terminating (timeout)...")
            
            self.crawler_process.terminate() # Attempt terminate 
            if not self.crawler_process.waitForFinished(30000): # Wait up to 30 seconds
                msg_kill = "Process still running after terminate. Killing."
                if hasattr(self, 'log_output'): self.log_output.append(msg_kill)
                else: logging.warning(msg_kill)
                if hasattr(self, 'status_label'): self.status_label.setText("Status: Killing (timeout)...")
                self.crawler_process.kill()
        else:
            msg_not_running = "Force stop timeout triggered, but process is no longer running."
            if hasattr(self, 'log_output'): self.log_output.append(msg_not_running)
            else: logging.info(msg_not_running)
        # UI updates (button states etc.) will be handled by handle_process_finished if the process exits

    def read_stdout(self):
        """Reads standard output from the crawler process."""
        if not self.crawler_process:
            return
        
        data = self.crawler_process.readAllStandardOutput().data().decode(errors='ignore')
        
        lines = data.strip().split('\n')
        processed_for_ui_widget_at_least_once = False
        for line in lines:
            if not line.strip():  # Skip empty or whitespace-only lines
                continue

            print(line)  # Print to ui_controller's stdout (VS Code terminal)

            if line.startswith("UI_STATUS:"):
                status = line.replace("UI_STATUS:", "").strip()
                self.status_label.setText(f"Status: {status}")
                if status == "RUNNING":
                    self.progress_bar.setRange(0, 0)  # Indeterminate
                elif status == "INITIALIZING":
                    self.progress_bar.setRange(0, 0)
                    self.progress_bar.setValue(0)  # Reset value for indeterminate
                else:  # IDLE, SUCCESS, FAILURE etc.
                    self.progress_bar.setRange(0, 100)  # Determinate
                    self.progress_bar.setValue(100 if status in ["SUCCESS", "FAILURE_UNHANDLED_EXCEPTION"] else 0)
                processed_for_ui_widget_at_least_once = True

            elif line.startswith("UI_STEP:"):
                try:
                    step_val_str = line.replace("UI_STEP:", "").strip()
                    self.step_count = int(step_val_str)
                    if self.step_label:
                        self.step_label.setText(f"Step: {self.step_count}")
                except ValueError:
                    self.log_output.append(f"Warning: Could not parse step count from: {line}")
                except Exception as e:
                    self.log_output.append(f"Error updating step label: {e}")
                processed_for_ui_widget_at_least_once = True

            elif line.startswith("UI_ACTION:"):
                action_desc = line.replace("UI_ACTION:", "").strip()
                if self.last_action_label:
                    self.last_action_label.setText(f"Last Action: {action_desc}")
                processed_for_ui_widget_at_least_once = True

            elif line.startswith("UI_SCREENSHOT:"):
                screenshot_path = line.replace("UI_SCREENSHOT:", "").strip()
                self.current_screenshot = screenshot_path
                if os.path.exists(self.current_screenshot):
                    try:
                        pixmap = QPixmap(self.current_screenshot)
                        scaled_pixmap = pixmap.scaled(
                            self.screenshot_label.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.screenshot_label.setPixmap(scaled_pixmap)
                    except Exception as e:
                        self.log_output.append(f"Error loading screenshot {screenshot_path}: {e}")
                        self.screenshot_label.setText("Error loading screenshot.")
                else:
                    self.screenshot_label.setText(f"Screenshot not found: {os.path.basename(screenshot_path)}")
                processed_for_ui_widget_at_least_once = True

            elif line.startswith("UI_END:"):
                end_message = line.replace("UI_END:", "").strip()
                self.status_label.setText(f"Status: Ended ({end_message})")
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(100)  # Mark as complete
                processed_for_ui_widget_at_least_once = True
            else:
                self.log_output.append(line)
                processed_for_ui_widget_at_least_once = True

        if not processed_for_ui_widget_at_least_once and data.strip():
            self.log_output.append(data.strip())

        QApplication.processEvents()  # Keep UI responsive

    @Slot(int, QProcess.ExitStatus)
    def handle_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handles the crawler process finishing."""
        self.shutdown_timer.stop() # Stop the timer if it's running

        # Clean up the shutdown flag file if it exists (crawler should ideally do this, UI is a fallback)
        if self._shutdown_flag_file_path and os.path.exists(self._shutdown_flag_file_path):
            try:
                os.remove(self._shutdown_flag_file_path)
                msg_cleaned = "Cleaned up shutdown flag file from UI controller."
                if hasattr(self, 'log_output'): self.log_output.append(msg_cleaned)
                else: logging.info(msg_cleaned)
            except OSError as e:
                msg_err_remove = f"UI controller could not remove shutdown flag file: {e}"
                if hasattr(self, 'log_output'): self.log_output.append(msg_err_remove)
                else: logging.warning(msg_err_remove)

        # --- Integrating existing handle_process_finished logic from your context ---
        current_status_text = f"Finished. Exit code: {exit_code}"
        if exit_status == QProcess.ExitStatus.CrashExit:
            current_status_text = f"Crashed. Exit code: {exit_code}"
        
        final_status_message = f"Status: {current_status_text}"
        if hasattr(self, 'log_output'): self.log_output.append(final_status_message)
        else: logging.info(final_status_message) 
        
        if hasattr(self, 'status_label'): self.status_label.setText(final_status_message)
        
        if hasattr(self, 'start_btn'): self.start_btn.setEnabled(True)
        if hasattr(self, 'stop_btn'): self.stop_btn.setEnabled(False)
        
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setRange(0,100) 
            self.progress_bar.setValue(100 if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0 else 0)
        
        self.crawler_process = None # Clear the process reference

    @Slot(QProcess.ProcessError)
    def handle_process_error(self, error: QProcess.ProcessError):
        """Handles errors that occur with the crawler process."""
        error_name_str = "Unknown Error"
        try:
            error_name_str = QProcess.ProcessError(error).name 
        except Exception:
            if error == QProcess.ProcessError.FailedToStart: error_name_str = "FailedToStart"
            elif error == QProcess.ProcessError.Crashed: error_name_str = "Crashed"
            elif error == QProcess.ProcessError.Timedout: error_name_str = "Timedout"
            elif error == QProcess.ProcessError.ReadError: error_name_str = "ReadError"
            elif error == QProcess.ProcessError.WriteError: error_name_str = "WriteError"
            elif error == QProcess.ProcessError.UnknownError: error_name_str = "UnknownError"

        error_message = f"Crawler process error: {error_name_str}"
        
        output_details = ""
        if self.crawler_process and self.crawler_process.isOpen():
            if self.crawler_process.processChannelMode() == QProcess.ProcessChannelMode.MergedChannels:
                if self.crawler_process.bytesAvailable() > 0:
                    output_details = self.crawler_process.readAllStandardOutput().data().decode(errors='ignore').strip()
            elif self.crawler_process.processChannelMode() == QProcess.ProcessChannelMode.SeparateChannels:
                if self.crawler_process.bytesAvailableOnStandardError() > 0:
                    output_details = self.crawler_process.readAllStandardError().data().decode(errors='ignore').strip()
                elif self.crawler_process.bytesAvailable() > 0:
                    output_details = self.crawler_process.readAllStandardOutput().data().decode(errors='ignore').strip()
            
        if output_details:
            error_message += f"\nLast output from process: {output_details}"
        
        self.log_output.append(error_message)
        logging.error(error_message)

        current_process_obj = self.crawler_process

        self.crawler_process = None 

        if current_process_obj:
            try:
                current_process_obj.finished.disconnect(self.handle_process_finished)
            except (TypeError, RuntimeError): pass 
            try:
                current_process_obj.errorOccurred.disconnect(self.handle_process_error)
            except (TypeError, RuntimeError): pass
            try:
                current_process_obj.readyReadStandardOutput.disconnect(self.read_stdout)
            except (TypeError, RuntimeError): pass
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText(f"Status: Error ({error_name_str})")
        self.progress_bar.setRange(0, 100)
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