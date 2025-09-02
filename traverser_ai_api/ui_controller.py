#!/usr/bin/env python3
# ui_controller.py - Main UI controller for the Appium Crawler

import sys
import os
import logging
import json
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QCheckBox, QSpinBox,
    QTextEdit, QFormLayout, QFrame, QComboBox, QGroupBox,
    QScrollArea, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt, QProcess, QTimer, QThread
from PySide6.QtCore import Signal, Slot as slot
from PySide6.QtGui import QPixmap, QColor, QTextCursor, QIcon, QImage

from config import Config
from ui.components import UIComponents
from ui.config_manager import ConfigManager
from ui.crawler_manager import CrawlerManager
from ui.health_app_scanner import HealthAppScanner
from ui.mobsf_ui_manager import MobSFUIManager
from ui.logo import LogoWidget
from ui.utils import update_screenshot


class CrawlerControllerWindow(QMainWindow):
    """Main window for the Appium Crawler Controller."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Appium Crawler Controller")

        # Initialize UI elements that will be created later
        self.health_app_dropdown = None
        self.refresh_apps_btn = None
        self.start_btn = None
        self.stop_btn = None
        self.test_mobsf_conn_btn = None
        self.run_mobsf_analysis_btn = None
        self.log_output = None
        self.screenshot_label = None
        self.status_label = None
        self.progress_bar = None
        self.step_label = None
        self.last_action_label = None
        self.app_scan_status_label = None
        self.logo_widget = None

        # Set window properties to allow resizing
        self.setWindowFlags(Qt.WindowType.Window)
        self.setMinimumSize(800, 600)  # Set a reasonable minimum size
        
        # Get screen geometry for default size if not maximized
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            width = int(screen_geometry.width() * 0.9)  # 90% of screen width
            height = int(screen_geometry.height() * 0.9)  # 90% of screen height
            self.resize(width, height)
        else:
            self.resize(1200, 800)

        # Set paths relative to the current script directory
        self.api_dir = os.path.dirname(__file__)  # Directory containing this script
        self.project_root = os.path.dirname(self.api_dir)  # Parent directory of api_dir
        
        # Initialize Config instance
        defaults_module_path = os.path.join(self.api_dir, "config.py")
        user_config_json_path = os.path.join(self.project_root, "user_config.json")
        self.config = Config(defaults_module_path, user_config_json_path)
        self.config.load_user_config()
        
        # Set default UI_MODE if not already in config
        # This is done after load_user_config to not overwrite existing setting
        if not hasattr(self.config, 'UI_MODE'):
            # Use update_setting_and_save which handles attribute creation
            logging.info(f"Setting default UI_MODE to Expert in config file: {user_config_json_path}")
            self.config.update_setting_and_save('UI_MODE', 'Expert')
            
        # Log current UI_MODE setting
        ui_mode = getattr(self.config, 'UI_MODE', 'Unknown')
        logging.info(f"Current UI_MODE setting: {ui_mode}")
        
        # Initialize instance variables
        self.config_widgets = {}
        self.current_health_app_list_file = self.config.CURRENT_HEALTH_APP_LIST_FILE
        self.health_apps_data = []
        # Initialize last_selected_app as an empty dictionary instead of None
        self.last_selected_app = {}
        
        # Ensure output directories exist
        self._ensure_output_directories_exist()
        
        # Set the application icon
        self._set_application_icon()
        
        # Initialize managers
        self.config_manager = ConfigManager(self.config, self)
        self.crawler_manager = CrawlerManager(self)
        self.health_app_scanner = HealthAppScanner(self)
        self.mobsf_ui_manager = MobSFUIManager(self)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Define tooltips
        self.tooltips = self._create_tooltips()

        # Create left (config) and right (output) panels
        left_panel = UIComponents.create_left_panel(
            self.config_widgets, 
            self.tooltips, 
            self.config_manager,
            self
        )
        
        # Copy UI references from config_manager to self for direct access
        if hasattr(self.config_manager, 'health_app_dropdown'):
            self.health_app_dropdown = self.config_manager.health_app_dropdown
            
        if hasattr(self.config_manager, 'refresh_apps_btn'):
            self.refresh_apps_btn = self.config_manager.refresh_apps_btn
            
        if hasattr(self.config_manager, 'app_scan_status_label'):
            self.app_scan_status_label = self.config_manager.app_scan_status_label
        
        # Note: MobSF buttons are set directly on this controller in the components class
        
        # Create right panel without logo
        right_panel = UIComponents.create_right_panel(self)

        # Add panels to main layout with stretch factors
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)

        # Load configuration
        self.config_manager.load_config()

        # Attempt to load cached health apps
        self._attempt_load_cached_health_apps()
        
        # Connect signals to slots
        self._connect_signals()
        
        # Shutdown flag path for crawler process
        self._shutdown_flag_file_path = self.config.SHUTDOWN_FLAG_PATH
        log_message = f"Shutdown flag path configured: {self._shutdown_flag_file_path}"
        if hasattr(self, 'log_output') and self.log_output:
            self.log_output.append(log_message)
        else:
            logging.info(log_message)

    def _create_tooltips(self) -> Dict[str, str]:
        """Create tooltips for UI elements."""
        return {
            'APPIUM_SERVER_URL': "URL of the running Appium server (e.g., http://127.0.0.1:4723).",
            'TARGET_DEVICE_UDID': "Unique Device Identifier (UDID) of the target Android device or emulator. Optional.",
            'NEW_COMMAND_TIMEOUT': "Seconds Appium waits for a new command before quitting the session. 0 means no timeout.",
            'APPIUM_IMPLICIT_WAIT': "Seconds Appium driver waits when trying to find elements before failing. Affects element finding strategies.",
            'APP_PACKAGE': "Package name of the target application (e.g., com.example.app). Auto-filled by Health App Selector.",
            'APP_ACTIVITY': "Launch activity of the target application (e.g., .MainActivity). Auto-filled by Health App Selector.",
            'DEFAULT_MODEL_TYPE': "The default Gemini model to use for AI operations.",
            'USE_CHAT_MEMORY': "Enable to allow the AI to remember previous interactions in the current session for better context.",
            'MAX_CHAT_HISTORY': "Maximum number of previous interactions to keep in AI's memory if chat memory is enabled.",
            'XML_SNIPPET_MAX_LEN': "Maximum characters of the XML page source to send to the AI for context. Minimum 5000 characters to ensure AI has sufficient UI structure information. The system automatically adjusts this limit based on the selected AI provider's payload size constraints to prevent API errors.",
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
            'ENABLE_IMAGE_CONTEXT': "Enable to send screenshots to the AI for visual analysis. Disable for text-only analysis using XML only. Note: Automatically disabled for DeepSeek due to payload size limits.",
            'ENABLE_TRAFFIC_CAPTURE': "Enable to capture network traffic (PCAP) during the crawl using PCAPdroid (requires PCAPdroid to be installed and configured on the device).",
            'CLEANUP_DEVICE_PCAP_FILE': "If traffic capture is enabled, delete the PCAP file from the device after successfully pulling it to the computer.",
            'CONTINUE_EXISTING_RUN': "Enable to resume a previous crawl session, using its existing database and screenshots. Disable to start a fresh run.",
            'ENABLE_MOBSF_ANALYSIS': "Enable to perform static analysis of the app using MobSF.",
            'MOBSF_API_URL': "URL of the MobSF API (e.g., http://localhost:8000/api/v1)",
            'MOBSF_API_KEY': "API Key for authenticating with MobSF. This can be found in the MobSF web interface or in the config file."
        }

    def _connect_signals(self):
        """Connect signals to slots safely."""
        try:
            # Connect the health app dropdown change signal
            if self.health_app_dropdown and hasattr(self.health_app_dropdown, 'currentIndexChanged'):
                self.health_app_dropdown.currentIndexChanged.connect(
                    self.config_manager._on_health_app_selected
                )
            
            # Connect the refresh apps button - now using self.refresh_apps_btn which has the correct reference
            if self.refresh_apps_btn and hasattr(self.refresh_apps_btn, 'clicked'):
                logging.info("Connecting refresh_apps_btn.clicked to trigger_scan_for_health_apps")
                self.log_message("DEBUG: Connecting refresh button signal", 'blue')
                try:
                    self.refresh_apps_btn.clicked.connect(
                        self.health_app_scanner.trigger_scan_for_health_apps
                    )
                    self.log_message("DEBUG: Button signal connected successfully", 'green')
                except Exception as button_ex:
                    self.log_message(f"ERROR connecting button signal: {button_ex}", 'red')
                    logging.error(f"Exception connecting button signal: {button_ex}", exc_info=True)
            else:
                self.log_message("ERROR: refresh_apps_btn not available for connection", 'red')
                logging.error("refresh_apps_btn not available for connection")
            
            if self.start_btn and hasattr(self.start_btn, 'clicked'):
                self.start_btn.clicked.connect(self.crawler_manager.start_crawler)
            
            if self.stop_btn and hasattr(self.stop_btn, 'clicked'):
                self.stop_btn.clicked.connect(self.crawler_manager.stop_crawler)
            
            # Connect MobSF buttons
            if self.test_mobsf_conn_btn and hasattr(self.test_mobsf_conn_btn, 'clicked'):
                self.test_mobsf_conn_btn.clicked.connect(
                    self.mobsf_ui_manager.test_mobsf_connection
                )
            
            if self.run_mobsf_analysis_btn and hasattr(self.run_mobsf_analysis_btn, 'clicked'):
                self.run_mobsf_analysis_btn.clicked.connect(
                    self.mobsf_ui_manager.run_mobsf_analysis
                )
            
            # Connect crawl mode change
            if 'CRAWL_MODE' in self.config_widgets and hasattr(self.config_widgets['CRAWL_MODE'], 'currentTextChanged'):
                self.config_widgets['CRAWL_MODE'].currentTextChanged.connect(
                    self.config_manager._update_crawl_mode_inputs_state
                )
                
            # The button states are now initialized in the components class
                
        except Exception as e:
            logging.error(f"Error connecting signals: {e}")

    def _attempt_load_cached_health_apps(self):
        """Tries to load health apps from the cached file path if it exists."""
        try:
            # If a health app list file is specified in the config
            if self.current_health_app_list_file:
                # Check if it's a relative path (doesn't start with drive letter or /)
                if not os.path.isabs(self.current_health_app_list_file):
                    # Convert to absolute path relative to the app directory
                    abs_path = os.path.join(self.api_dir, self.current_health_app_list_file)
                    self.current_health_app_list_file = abs_path
                
                if os.path.exists(self.current_health_app_list_file):
                    self.log_message(f"Attempting to load cached health apps from: {self.current_health_app_list_file}")
                    self.health_app_scanner._load_health_apps_from_file(self.current_health_app_list_file)
                    return
                else:
                    self.log_message(f"Configured health app file not found: {self.current_health_app_list_file}", 'orange')
                    
                    # Check if this is the generic health_apps.json file - if so, convert to device-specific
                    filename = os.path.basename(self.current_health_app_list_file)
                    if filename == "health_apps.json":
                        device_id = self.health_app_scanner._get_current_device_id()
                        self.log_message(f"Using generic health apps config with device ID: {device_id}", 'blue')
                    
            # If we reach here, we need to find the health app file for the current device
            self.log_message("Looking for health app list for the current device...", 'blue')
            device_id = self.health_app_scanner._get_current_device_id()
            device_file_path = self.health_app_scanner._get_device_health_app_file_path(device_id)
            
            if os.path.exists(device_file_path):
                self.log_message(f"Found health app list for device {device_id}: {device_file_path}", 'green')
                self.current_health_app_list_file = device_file_path
                self.health_app_scanner._load_health_apps_from_file(device_file_path)
                
                # Update the config with the generic path, not device-specific
                generic_path = os.path.join(getattr(self.config, 'OUTPUT_DATA_DIR', 'output_data'), "app_info", "health_apps.json")
                self.config.update_setting_and_save("CURRENT_HEALTH_APP_LIST_FILE", generic_path)
                return
            
            # If no file exists for this device
            self.log_message(f"No health app list found for device {device_id}. Scan needed.", 'orange')
            # Store the path where the file would be created
            self.current_health_app_list_file = device_file_path
            
            # Update config with generic path
            generic_path = os.path.join(getattr(self.config, 'OUTPUT_DATA_DIR', 'output_data'), "app_info", "health_apps.json")
            self.config.update_setting_and_save("CURRENT_HEALTH_APP_LIST_FILE", generic_path)
            
            # Clear dropdown if no valid cache
            if self.health_app_dropdown and hasattr(self.health_app_dropdown, 'clear'):
                try:
                    self.health_app_dropdown.clear()
                    self.health_app_dropdown.addItem("Select target app (Scan first)", None)
                except Exception as e:
                    logging.error(f"Error updating health app dropdown: {e}")
            self.health_apps_data = []
        except Exception as e:
            logging.error(f"Error loading cached health apps: {e}", exc_info=True)
            self.log_message(f"Error loading cached health apps: {e}", 'red')

    def _set_application_icon(self):
        """Set the application icon for window and taskbar."""
        try:
            # Get the application icon using LogoWidget
            app_icon = LogoWidget.get_icon(os.path.dirname(self.api_dir))
            
            if app_icon:
                # Set window icon (appears in taskbar)
                self.setWindowIcon(app_icon)
                # Set application icon (used by Windows taskbar)
                QApplication.setWindowIcon(app_icon)
                logging.info("Application icon set successfully")
            else:
                logging.warning("Failed to get application icon")
        except Exception as e:
            logging.error(f"Failed to set application icon: {e}")

    def _ensure_output_directories_exist(self):
        """Ensure that all necessary output directories exist."""
        try:
            # The config class now handles creating session-specific directories
            # We just need to ensure the base output directory exists
            output_base_dir = getattr(self.config, 'OUTPUT_DATA_DIR', os.path.join(self.api_dir, 'output_data'))
            
            # Create base output directory if it doesn't exist
            if not os.path.exists(output_base_dir):
                os.makedirs(output_base_dir)
                self.log_message(f"Created base output directory: {output_base_dir}", "blue")
            
            # The config class will create session-specific directories when paths are resolved
            # Update config with relative paths if using absolute paths
            self._update_relative_paths_in_config()
            
            # Synchronize the API directory user_config.json with the root user_config.json
            self._sync_user_config_files()
            
        except Exception as e:
            logging.error(f"Error creating output directories: {e}", exc_info=True)
            if hasattr(self, 'log_output') and self.log_output:
                self.log_message(f"Error creating output directories: {e}", 'red')

    def _update_relative_paths_in_config(self):
        """Update any absolute paths in config to use relative paths."""
        try:
            # Define the paths to check and update
            path_settings = [
                "APP_INFO_OUTPUT_DIR",
                "SCREENSHOTS_DIR",
                "TRAFFIC_CAPTURE_OUTPUT_DIR",
                "LOG_DIR",
                "DB_NAME",
                "CURRENT_HEALTH_APP_LIST_FILE"
            ]
            
            # Process each path setting
            for setting_name in path_settings:
                current_value = getattr(self.config, setting_name, None)
                if current_value and os.path.isabs(current_value):
                    # Try to make it relative to the api_dir
                    try:
                        rel_path = os.path.relpath(current_value, self.api_dir)
                        # Only update if it's inside the api_dir hierarchy
                        if not rel_path.startswith('..'):
                            self.config.update_setting_and_save(setting_name, rel_path)
                            logging.info(f"Updated {setting_name} to use relative path: {rel_path}")
                    except ValueError:
                        # Different drives, can't make relative
                        pass
            
        except Exception as e:
            logging.error(f"Error updating relative paths in config: {e}", exc_info=True)
            
    def _sync_user_config_files(self):
        """Synchronize the user_config.json in API directory with the root user_config.json file."""
        try:
            # Path to the API directory user_config.json
            api_config_path = os.path.join(self.api_dir, "user_config.json")
            # Path to the root user_config.json (already set in self.config.USER_CONFIG_FILE_PATH)
            root_config_path = self.config.USER_CONFIG_FILE_PATH
            
            # If both files exist, make sure they have the same settings
            if os.path.exists(api_config_path) and os.path.exists(root_config_path):
                # Read root config file
                with open(root_config_path, 'r', encoding='utf-8') as f:
                    root_config = json.load(f)
                
                # Read API config file
                with open(api_config_path, 'r', encoding='utf-8') as f:
                    api_config = json.load(f)
                
                # Copy 'UI_MODE' and 'AI_PROVIDER' from root to API config if it exists
                if 'UI_MODE' in root_config and root_config['UI_MODE'] != api_config.get('UI_MODE'):
                    api_config['UI_MODE'] = root_config['UI_MODE']
                    # Save updated API config
                    with open(api_config_path, 'w', encoding='utf-8') as f:
                        json.dump(api_config, f, indent=4, ensure_ascii=False)
                    self.log_message(f"Synchronized UI_MODE '{root_config['UI_MODE']}' to API config file", 'blue')
                    logging.info(f"Synchronized UI_MODE '{root_config['UI_MODE']}' to API config file: {api_config_path}")
                
                if 'AI_PROVIDER' in root_config and root_config['AI_PROVIDER'] != api_config.get('AI_PROVIDER'):
                    api_config['AI_PROVIDER'] = root_config['AI_PROVIDER']
                    # Save updated API config
                    with open(api_config_path, 'w', encoding='utf-8') as f:
                        json.dump(api_config, f, indent=4, ensure_ascii=False)
                    self.log_message(f"Synchronized AI_PROVIDER '{root_config['AI_PROVIDER']}' to API config file", 'blue')
                    logging.info(f"Synchronized AI_PROVIDER '{root_config['AI_PROVIDER']}' to API config file: {api_config_path}")
        except Exception as e:
            logging.error(f"Error synchronizing user config files: {e}", exc_info=True)
            if hasattr(self, 'log_output') and self.log_output:
                self.log_message(f"Error synchronizing user config files: {e}", 'red')
            
    def log_message(self, message: str, color: str = 'white'):
        """Append a message to the log output with a specified color."""
        # Always log to console for backup
        logging.info(message)
        
        # Check if log_output exists and is properly initialized
        if not self.log_output:
            return

        # Ensure operations are on the main thread if called from another thread
        app = QApplication.instance()
        if app and app.thread() != QThread.currentThread():
            # If we are not in the main thread, we cannot directly update the UI.
            # For now, just log to console.
            logging.info(f"LOG (from thread): {message}")
            return

        color_map = {
            'white': QColor('white'),
            'red': QColor('red'),
            'green': QColor('green'),
            'blue': QColor('cyan'),
            'orange': QColor('orange')
        }
        
        text_color = color_map.get(color, QColor('black'))
        
        try:
            if hasattr(self.log_output, 'setTextColor'):
                self.log_output.setTextColor(text_color)
                self.log_output.append(message)
                if hasattr(self.log_output, 'verticalScrollBar'):
                    scrollbar = self.log_output.verticalScrollBar()
                    if scrollbar:
                        scrollbar.setValue(scrollbar.maximum())
                QApplication.processEvents()  # Ensure the UI updates immediately
        except Exception as e:
            logging.error(f"Error updating log output: {e}")
            return

    def update_screenshot(self, file_path: str) -> None:
        """Update the screenshot displayed in the UI."""
        try:
            if self.screenshot_label and hasattr(self.screenshot_label, 'setPixmap'):
                update_screenshot(self.screenshot_label, file_path)
            else:
                logging.warning(f"Screenshot label not properly initialized for update from: {file_path}")
        except Exception as e:
            logging.error(f"Error updating screenshot: {e}")

    def closeEvent(self, event):
        """Handle the window close event."""
        # Stop crawler process if running
        if hasattr(self, 'crawler_manager'):
            self.crawler_manager.stop_crawler()
        
        # Stop app scan process if running
        if hasattr(self.health_app_scanner, 'find_apps_process'):
            find_apps_process = self.health_app_scanner.find_apps_process
            if find_apps_process and find_apps_process.state() != QProcess.ProcessState.NotRunning:
                self.log_message("Closing UI: Terminating app scan process...", 'orange')
                find_apps_process.terminate()
                if not find_apps_process.waitForFinished(5000):
                    self.log_message("App scan process did not terminate gracefully. Killing...", 'red')
                    find_apps_process.kill()
        
        # Stop MobSF analysis process if running
        if hasattr(self.mobsf_ui_manager, 'mobsf_analysis_process'):
            mobsf_process = self.mobsf_ui_manager.mobsf_analysis_process
            if mobsf_process and mobsf_process.state() != QProcess.ProcessState.NotRunning:
                self.log_message("Closing UI: Terminating MobSF analysis process...", 'orange')
                mobsf_process.terminate()
                if not mobsf_process.waitForFinished(5000):
                    self.log_message("MobSF analysis process did not terminate gracefully. Killing...", 'red')
                    mobsf_process.kill()
                    
        super().closeEvent(event)

    # Delegate methods to appropriate managers
    @slot()
    def start_crawler(self):
        """Start the crawler process."""
        self.crawler_manager.start_crawler()
    
    @slot()
    def stop_crawler(self):
        """Stop the crawler process."""
        self.crawler_manager.stop_crawler()
    
    @slot()
    def trigger_scan_for_health_apps(self):
        """Trigger the health app scanning process."""
        self.health_app_scanner.trigger_scan_for_health_apps()
    
    @slot()
    def test_mobsf_connection(self):
        """Test the MobSF connection."""
        self.mobsf_ui_manager.test_mobsf_connection()
    
    @slot()
    def run_mobsf_analysis(self):
        """Run MobSF analysis for the selected app."""
        self.mobsf_ui_manager.run_mobsf_analysis()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    app = QApplication(sys.argv)
    window = CrawlerControllerWindow()
    # Start in full screen mode but allow resizing
    window.showMaximized()
    sys.exit(app.exec())
