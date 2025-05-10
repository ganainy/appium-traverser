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
from PySide6.QtGui import QPixmap, QImage

import config

class CrawlerControllerWindow(QMainWindow):
    """Main window for the Appium Crawler Controller."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Appium Crawler Controller")
        self.resize(1200, 800)
        
        # Initialize instance variables
        self.crawler_process: Optional[QProcess] = None
        self.user_config: Dict[str, Any] = {}
        self.config_file_path = "user_config.json"
        self.current_screenshot: Optional[str] = None
        self.step_count = 0
        
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
        
        # Appium Settings
        layout.addRow(QLabel("Appium Settings"))
        self.config_widgets['APPIUM_SERVER_URL'] = QLineEdit()
        layout.addRow("Server URL:", self.config_widgets['APPIUM_SERVER_URL'])
        
        # App Settings
        layout.addRow(QLabel("App Settings"))
        self.config_widgets['APP_PACKAGE'] = QLineEdit()
        self.config_widgets['APP_ACTIVITY'] = QLineEdit()
        layout.addRow("Package Name:", self.config_widgets['APP_PACKAGE'])
        layout.addRow("Activity:", self.config_widgets['APP_ACTIVITY'])
        
        # Crawler Settings
        layout.addRow(QLabel("Crawler Settings"))
        
        # Crawl Mode
        self.config_widgets['CRAWL_MODE'] = QComboBox()
        self.config_widgets['CRAWL_MODE'].addItems(['steps', 'time'])
        layout.addRow("Crawl Mode:", self.config_widgets['CRAWL_MODE'])
        
        self.config_widgets['MAX_CRAWL_STEPS'] = QSpinBox()
        self.config_widgets['MAX_CRAWL_STEPS'].setRange(1, 1000)
        self.config_widgets['MAX_CRAWL_STEPS'].setValue(100)
        layout.addRow("Max Steps:", self.config_widgets['MAX_CRAWL_STEPS'])
        
        self.config_widgets['MAX_CRAWL_DURATION_SECONDS'] = QSpinBox()
        self.config_widgets['MAX_CRAWL_DURATION_SECONDS'].setRange(60, 7200)
        self.config_widgets['MAX_CRAWL_DURATION_SECONDS'].setValue(600)
        layout.addRow("Max Duration (s):", self.config_widgets['MAX_CRAWL_DURATION_SECONDS'])
        
        # Timing Settings
        self.config_widgets['WAIT_AFTER_ACTION'] = QSpinBox()
        self.config_widgets['WAIT_AFTER_ACTION'].setRange(1, 10)
        self.config_widgets['WAIT_AFTER_ACTION'].setValue(2)
        layout.addRow("Wait After Action (s):", self.config_widgets['WAIT_AFTER_ACTION'])
        
        # Feature Toggles
        self.config_widgets['ENABLE_XML_CONTEXT'] = QCheckBox()
        self.config_widgets['ENABLE_TRAFFIC_CAPTURE'] = QCheckBox()
        self.config_widgets['CONTINUE_EXISTING_RUN'] = QCheckBox()
        
        layout.addRow("Enable XML Context:", self.config_widgets['ENABLE_XML_CONTEXT'])
        layout.addRow("Enable Traffic Capture:", self.config_widgets['ENABLE_TRAFFIC_CAPTURE'])
        layout.addRow("Continue Existing Run:", self.config_widgets['CONTINUE_EXISTING_RUN'])
    
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
        
        # Screenshot display
        self.screenshot_label = QLabel()
        self.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screenshot_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        # Add widgets to layout
        layout.addLayout(status_layout)
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
            self._load_defaults_from_config()
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
            
            self.log_output.append("Configuration loaded successfully.")
        except Exception as e:
            self.log_output.append(f"Error loading configuration: {e}")
            self._load_defaults_from_config()
    
    def _load_defaults_from_config(self):
        """Loads default values from config.py."""
        for key, widget in self.config_widgets.items():
            if hasattr(config, key):
                value = getattr(config, key)
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
    
    @Slot()
    def start_crawler(self):
        """Starts the crawler process."""
        if not self.crawler_process:
            # Save configuration before starting
            self.save_config()
            
            # Create QProcess
            self.crawler_process = QProcess()
            self.crawler_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            
            # Connect signals
            self.crawler_process.readyReadStandardOutput.connect(self.handle_stdout)
            self.crawler_process.finished.connect(self.handle_process_finished)
            
            # Determine project root directory
            # __file__ is the path to ui_controller.py
            # The script's directory is .../traverser_ai_api
            script_path = os.path.abspath(__file__)
            script_dir = os.path.dirname(script_path)
            project_root = os.path.dirname(script_dir)

            # Set the working directory for the subprocess
            self.crawler_process.setWorkingDirectory(project_root)
            
            # Start the process
            self.crawler_process.start(sys.executable, ['-m', 'traverser_ai_api.main'])
            
            # Update UI
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("Status: Running")
            self.log_output.append("Crawler process started.")
    
    @Slot()
    def stop_crawler(self):
        """Stops the crawler process."""
        if self.crawler_process and self.crawler_process.state() == QProcess.ProcessState.Running:
            self.crawler_process.terminate()
            self.crawler_process.waitForFinished(5000)  # Wait up to 5 seconds
            if self.crawler_process.state() == QProcess.ProcessState.Running:
                self.crawler_process.kill()  # Force kill if still running
    
    @Slot()
    def handle_stdout(self):
        """Handles standard output from the crawler process."""
        if self.crawler_process:
            data = self.crawler_process.readAllStandardOutput().data().decode()
            self.log_output.append(data.strip())
            
            # Look for step updates
            if "--- Step " in data:
                try:
                    step = int(data.split("Step ")[1].split("/")[0])
                    self.step_count = step
                    self.update_progress()
                except Exception:
                    pass
            
            # Look for screenshot updates
            if "Saved annotated screenshot:" in data:
                try:
                    screenshot_path = data.split("Saved annotated screenshot: ")[1].split(" (")[0]
                    self.update_screenshot(screenshot_path)
                except Exception:
                    pass
    
    def update_progress(self):
        """Updates the progress bar based on current step."""
        if self.config_widgets['CRAWL_MODE'].currentText() == 'steps':
            max_steps = self.config_widgets['MAX_CRAWL_STEPS'].value()
            self.progress_bar.setMaximum(max_steps)
            self.progress_bar.setValue(self.step_count)
    
    def update_screenshot(self, path: str):
        """Updates the screenshot display."""
        if os.path.exists(path):
            pixmap = QPixmap(path)
            scaled_pixmap = pixmap.scaled(
                self.screenshot_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.screenshot_label.setPixmap(scaled_pixmap)
            self.current_screenshot = path
    
    @Slot()
    def handle_process_finished(self):
        """Handles crawler process completion."""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Status: Finished")
        self.log_output.append("Crawler process finished.")
        self.crawler_process = None

def main():
    app = QApplication(sys.argv)
    window = CrawlerControllerWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()