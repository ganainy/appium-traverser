# ui_controller.py - Main UI controller for the Appium Crawler

import json
import logging
import os
import re
import subprocess
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional


from PySide6.QtCore import QProcess, Qt, QThread, QTimer, Signal
from PySide6.QtCore import Slot as slot
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from domain.analysis_viewer import XHTML2PDF_AVAILABLE, RunAnalyzer
except Exception:
    try:
        from domain.analysis_viewer import XHTML2PDF_AVAILABLE, RunAnalyzer
    except Exception:
        RunAnalyzer = None
        XHTML2PDF_AVAILABLE = False
from ui.components import UIComponents
from ui.config_manager import ConfigManager
from ui.crawler_manager import CrawlerManager
from ui.custom_widgets import BusyDialog
from ui.health_app_scanner import HealthAppScanner
from ui.logo import LogoWidget
from ui.mobsf_ui_manager import MobSFUIManager
from ui.utils import update_screenshot


class CrawlerControllerWindow(QMainWindow):
    """Main window for the Appium Crawler Controller."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Appium Crawler Controller")

        # AgentAssistant instance (initialized after config load)
        self.agent_assistant = None

        # Initialize UI elements that will be created later
        self.health_app_dropdown = None
        self.refresh_apps_btn = None
        self.start_btn = None
        self.stop_btn = None
        self.test_mobsf_conn_btn = None
        self.run_mobsf_analysis_btn = None
        self.clear_logs_btn = None
        self.log_output = None
        self.screenshot_label = None
        self.status_label = None
        self.progress_bar = None
        self.step_label = None
        self.action_history = None
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
        from config.config import Config
        from ui.components import UIComponents
        self.config = Config()

        # Only set default UI_MODE if it hasn't been saved yet (check SQLite, not attributes)
        # This ensures we don't overwrite an existing user preference
        existing_ui_mode = self.config.get(UIComponents.UI_MODE_CONFIG_KEY)
        if not existing_ui_mode:
            logging.debug(f"No existing UI_MODE found in config. Setting default to {UIComponents.UI_MODE_DEFAULT}.")
            if hasattr(self.config, "update_setting_and_save"):
                self.config.update_setting_and_save(
                    UIComponents.UI_MODE_CONFIG_KEY, UIComponents.UI_MODE_DEFAULT, getattr(self, "_sync_user_config_files", None)
                )
        else:
            logging.debug(f"Found existing UI_MODE in config: {existing_ui_mode}")
        
        # Log current UI_MODE setting for debugging
        ui_mode = self.config.get(UIComponents.UI_MODE_CONFIG_KEY, UIComponents.UI_MODE_DEFAULT)
        logging.debug(f"Current UI_MODE setting: {ui_mode}")

        # Initialize instance variables
        self.config_widgets = {}
        self.current_health_app_list_file = getattr(self.config, "CURRENT_HEALTH_APP_LIST_FILE", None)
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
            self.config_widgets, self.tooltips, self.config_manager, self
        )

        # Assign refresh_devices_btn if set by UIComponents (it assigns to controls_handler, which is self)
        if hasattr(self, "refresh_devices_btn"):
            pass  # Already set by UIComponents
        else:
            self.refresh_devices_btn = None

        # Copy UI references from config_manager to self for direct access
        if hasattr(self.config_manager, "health_app_dropdown"):
            self.health_app_dropdown = self.config_manager.health_app_dropdown

        if hasattr(self.config_manager, "refresh_apps_btn"):
            self.refresh_apps_btn = self.config_manager.refresh_apps_btn

        if hasattr(self.config_manager, "app_scan_status_label"):
            self.app_scan_status_label = self.config_manager.app_scan_status_label

        # Note: MobSF buttons are set directly on this controller in the components class

        # Create right panel without logo
        right_panel = UIComponents.create_right_panel(self)

        # Add panels to main layout with stretch factors
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)

        # Load configuration
        self.config_manager.load_config()

        # Initialize AgentAssistant after config is loaded
        self._init_agent_assistant()

        # Attempt to load cached health apps
        self._attempt_load_cached_health_apps()

        # Connect signals to slots
        self._connect_signals()

        # Connect the refresh devices button
        if hasattr(self, "refresh_devices_btn") and self.refresh_devices_btn:
            self.refresh_devices_btn.clicked.connect(self._populate_device_dropdown)

        # Populate device dropdown on startup
        self._populate_device_dropdown()

        # Shutdown flag path for crawler process
        self._shutdown_flag_file_path = self.config.SHUTDOWN_FLAG_PATH
        log_message = f"Shutdown flag path configured: {self._shutdown_flag_file_path}"
        if hasattr(self, "log_output") and self.log_output:
            self.log_output.append(log_message)
        else:
            logging.debug(log_message)

        # Busy overlay dialog (initialized lazily)
        self._busy_dialog = None

    def show_busy(self, message: str = "Working...") -> None:
        """Show a modal busy overlay with the given message."""
        try:
            if self._busy_dialog is None:
                self._busy_dialog = BusyDialog(self)
            self._busy_dialog.set_message(message)
            # Cover the entire main window
            try:
                self._busy_dialog.setGeometry(self.geometry())
            except Exception:
                pass
            self._busy_dialog.show()
            QApplication.processEvents()
        except Exception as e:
            logging.debug(f"Failed to show busy overlay: {e}")

    def hide_busy(self) -> None:
        """Hide the busy overlay if visible."""
        try:
            if self._busy_dialog:
                self._busy_dialog.hide()
        except Exception as e:
            logging.debug(f"Failed to hide busy overlay: {e}")

    def _audio_alert(self, kind: str = "finish") -> None:
        """Play an audible alert.

        kind:
        - 'finish' -> single tone
        - 'error'  -> double tone

        Uses platform-specific methods on Windows for reliability, falls back to
        Qt's QGuiApplication.beep elsewhere.
        """
        # Prefer native Windows sounds if available for more reliable playback
        try:
            import sys
            if sys.platform.startswith("win"):
                try:
                    import winsound
                    if kind == "error":
                        # Two short tones with slight pitch difference
                        winsound.Beep(900, 150)
                        QTimer.singleShot(220, lambda: winsound.Beep(700, 150))
                    else:
                        # Use system default notification sound when possible
                        try:
                            winsound.MessageBeep(winsound.MB_OK)
                        except Exception:
                            winsound.Beep(800, 200)
                    return  # Already played via winsound
                except Exception as e:
                    logging.debug(f"winsound not available or failed: {e}")
        except Exception:
            # Ignore sys import/platform issues
            pass

        # Fallback: use Qt beep
        try:
            from PySide6.QtWidgets import QApplication
            if kind == "error":
                QApplication.beep()
                # Schedule a second beep shortly after; use lambda to ensure call
                QTimer.singleShot(250, lambda: QApplication.beep())
            else:
                QApplication.beep()
        except Exception as e:
            logging.debug(f"Audio alert failed: {e}")

    def _create_tooltips(self) -> Dict[str, str]:
        """Create tooltips for UI elements."""
        return {
            "APPIUM_SERVER_URL": "URL of the Appium server (e.g., http://127.0.0.1:4723). This is the server that handles mobile automation.",
            "MCP_SERVER_URL": "URL of the running MCP server (e.g., http://127.0.0.1:3000).",
            "TARGET_DEVICE_UDID": "Unique Device Identifier (UDID) of the target Android device or emulator. Optional.",
            "DEFAULT_MODEL_TYPE": "The default Gemini model to use for AI operations.",
            "XML_SNIPPET_MAX_LEN": "Maximum characters of the XML page source to send to the AI for context. Minimum 5000 characters to ensure AI has sufficient UI structure information. The system automatically adjusts this limit based on the selected AI provider's payload size constraints to prevent API errors.",
            "CRAWL_MODE": "'steps': Crawl for a fixed number of actions. 'time': Crawl for a fixed duration.",
            "MAX_CRAWL_STEPS": "Maximum number of actions to perform if CRAWL_MODE is 'steps'.",
            "MAX_CRAWL_DURATION_SECONDS": "Maximum duration in seconds for the crawl if CRAWL_MODE is 'time'.",
            "WAIT_AFTER_ACTION": "Seconds to wait for the UI to stabilize after performing an action.",
            "STABILITY_WAIT": "Seconds to wait before capturing the UI state (screenshot/XML) after an action, ensuring UI is stable.",
            "APP_LAUNCH_WAIT_TIME": "Seconds to wait after launching the app for it to stabilize before starting the crawl.",
            "VISUAL_SIMILARITY_THRESHOLD": "Perceptual hash distance threshold for comparing screenshots. Lower values mean screenshots must be more similar to be considered the same state.",
            "ALLOWED_EXTERNAL_PACKAGES": "List of package names (one per line) that the crawler can interact with outside the main target app (e.g., for logins, webviews).",
            "MAX_CONSECUTIVE_AI_FAILURES": "Maximum number of consecutive times the AI can fail to provide a valid action before stopping.",
            "MAX_CONSECUTIVE_MAP_FAILURES": "Maximum number of consecutive times the AI action cannot be mapped to a UI element before stopping.",
            "MAX_CONSECUTIVE_EXEC_FAILURES": "Maximum number of consecutive times an action execution can fail before stopping.",
            "ENABLE_IMAGE_CONTEXT": "Enable to send screenshots to the AI for visual analysis. Disable for text-only analysis using XML only.",
            "ENABLE_TRAFFIC_CAPTURE": "Enable to capture network traffic (PCAP) during the crawl using PCAPdroid (requires PCAPdroid to be installed and configured on the device).",
            "CLEANUP_DEVICE_PCAP_FILE": "If traffic capture is enabled, delete the PCAP file from the device after successfully pulling it to the computer.",
            "CONTINUE_EXISTING_RUN": "Enable to resume a previous crawl session, using its existing database and screenshots. Disable to start a fresh run.",
            "ENABLE_MOBSF_ANALYSIS": "Enable to perform static analysis of the app using MobSF.",
            "MOBSF_API_URL": "URL of the MobSF API (e.g., http://localhost:8000/api/v1)",
            "MOBSF_API_KEY": "API Key for authenticating with MobSF. This can be found in the MobSF web interface or in the config file.",
            "ENABLE_VIDEO_RECORDING": "Enable to record the entire crawl session as an MP4 video.",
            # Image preprocessing tooltips
            "IMAGE_MAX_WIDTH": "Max screenshot width before sending to AI. Smaller widths (e.g., 720â€“1080px) reduce payload and are sufficient for most UI understanding; use larger widths for dense UIs or OCR.",
            "IMAGE_FORMAT": "Screenshot format sent to AI. JPEG offers broad compatibility; WEBP typically yields smaller files with similar quality (great for OpenRouter); PNG is lossless and best for crisp text/OCR but larger.",
            "IMAGE_QUALITY": "Compression quality for JPEG/WEBP. 70â€“85 is a good balance; increase to 90â€“95 if the model struggles to read fine text; decrease to ~60 to minimize payload.",
            "IMAGE_CROP_BARS": "Remove top/bottom system bars to reduce payload while keeping the core app UI. Enable when bars are not needed for analysis.",
            "IMAGE_CROP_TOP_PERCENT": "Percent of image height to crop from the top. 5â€“8% is typical for Android status bars; adjust if needed.",
            "IMAGE_CROP_BOTTOM_PERCENT": "Percent of image height to crop from the bottom. 8â€“12% is typical for Android navigation bars; adjust if needed.",
        }

    def _connect_signals(self):
        """Connect signals to slots safely."""
        try:
            # Connect AI provider/model change to agent reload
            ai_provider_widget = self.config_widgets.get("AI_PROVIDER")
            model_type_widget = self.config_widgets.get("DEFAULT_MODEL_TYPE")
            if ai_provider_widget:
                ai_provider_widget.currentTextChanged.connect(self._on_provider_or_model_changed)
            if model_type_widget:
                model_type_widget.currentTextChanged.connect(self._on_provider_or_model_changed)

            # Connect the health app dropdown change signal
            if self.health_app_dropdown and hasattr(
                self.health_app_dropdown, "currentIndexChanged"
            ):
                self.health_app_dropdown.currentIndexChanged.connect(
                    self.config_manager._on_health_app_selected
                )

            # Connect the refresh apps button - now using self.refresh_apps_btn which has the correct reference
            if self.refresh_apps_btn and hasattr(self.refresh_apps_btn, "clicked"):
                logging.debug(
                    "Connecting refresh_apps_btn.clicked to trigger_scan_for_health_apps"
                )
                self.log_message("DEBUG: Connecting refresh button signal", "blue")
                try:
                    self.refresh_apps_btn.clicked.connect(
                        self.health_app_scanner.trigger_scan_for_health_apps
                    )
                    self.log_message(
                        "DEBUG: Button signal connected successfully", "green"
                    )
                except Exception as button_ex:
                    self.log_message(
                        f"ERROR connecting button signal: {button_ex}", "red"
                    )
                    logging.error(
                        f"Exception connecting button signal: {button_ex}",
                        exc_info=True,
                    )
            else:
                self.log_message(
                    "ERROR: refresh_apps_btn not available for connection", "red"
                )
                logging.error("refresh_apps_btn not available for connection")

            if self.start_btn and hasattr(self.start_btn, "clicked"):
                self.start_btn.clicked.connect(self.crawler_manager.start_crawler)

            if self.stop_btn and hasattr(self.stop_btn, "clicked"):
                self.stop_btn.clicked.connect(self.crawler_manager.stop_crawler)

            # Connect MobSF buttons
            if self.test_mobsf_conn_btn and hasattr(
                self.test_mobsf_conn_btn, "clicked"
            ):
                self.test_mobsf_conn_btn.clicked.connect(
                    self.mobsf_ui_manager.test_mobsf_connection
                )

            if self.run_mobsf_analysis_btn and hasattr(
                self.run_mobsf_analysis_btn, "clicked"
            ):
                self.run_mobsf_analysis_btn.clicked.connect(
                    self.mobsf_ui_manager.run_mobsf_analysis
                )

            if self.clear_logs_btn and hasattr(self.clear_logs_btn, "clicked"):
                self.clear_logs_btn.clicked.connect(self.clear_logs)

            # Connect crawl mode change
            if "CRAWL_MODE" in self.config_widgets and hasattr(
                self.config_widgets["CRAWL_MODE"], "currentTextChanged"
            ):
                self.config_widgets["CRAWL_MODE"].currentTextChanged.connect(
                    self.config_manager._update_crawl_mode_inputs_state
                )

            # The button states are now initialized in the components class

        except Exception as e:
            logging.error(f"Error connecting signals: {e}")

    def _on_provider_or_model_changed(self, _=None):
        """Handle runtime provider/model change: update config, reload AgentAssistant, and log."""
        try:
            provider = self.config_widgets["AI_PROVIDER"].currentText()
            model = self.config_widgets["DEFAULT_MODEL_TYPE"].currentText()
            # Update config
            self.config.update_setting_and_save("AI_PROVIDER", provider, self._sync_user_config_files)
            self.config.update_setting_and_save("DEFAULT_MODEL_TYPE", model, self._sync_user_config_files)
            # Re-initialize AgentAssistant
            self._init_agent_assistant()
            self.log_message(f"AI provider switched to '{provider}', model '{model}'. AgentAssistant reloaded.", "blue")
        except Exception as e:
            self.log_message(f"Error switching provider/model: {e}", "red")

    def _init_agent_assistant(self):
        """(Re)initialize the AgentAssistant with current config and model."""
        try:
            from domain.agent_assistant import AgentAssistant
            provider = getattr(self.config, "AI_PROVIDER", None)
            model = getattr(self.config, "DEFAULT_MODEL_TYPE", None)
            if not provider or not model or str(model).strip() in ["", "No model selected"]:
                self.agent_assistant = None
                self.log_message("AgentAssistant not initialized: provider or model not set.", "orange")
                return
            self.agent_assistant = AgentAssistant(self.config, model_alias_override=model)
        except Exception as e:
            self.agent_assistant = None
            self.log_message(f"Failed to initialize AgentAssistant: {e}", "red")

    @slot()
    def clear_logs(self):
        """Clears the log output."""
        if self.log_output:
            self.log_output.clear()
            self.log_message("Logs cleared.", "green")

    def _attempt_load_cached_health_apps(self):
        """Tries to load health apps from the cached file path if it exists."""
        try:
            # If a health app list file is specified in the config
            if self.current_health_app_list_file:
                # Check if it's a relative path (doesn't start with drive letter or /)
                if not os.path.isabs(self.current_health_app_list_file):
                    # Convert to absolute path relative to the app directory
                    abs_path = os.path.join(
                        self.api_dir, self.current_health_app_list_file
                    )
                    self.current_health_app_list_file = abs_path

                if os.path.exists(self.current_health_app_list_file):
                    self.log_message(
                        f"Attempting to load cached health apps from: {self.current_health_app_list_file}"
                    )
                    self.health_app_scanner._load_health_apps_from_file(
                        self.current_health_app_list_file
                    )
                    return
                else:
                    self.log_message(
                        f"Configured health app file not found: {self.current_health_app_list_file}",
                        "orange",
                    )

                    # No longer support generic alias files; proceed to resolve device-specific path

            # If we reach here, we need to find the health app file for the current device
            self.log_message(
                "Looking for health app list for the current device...", "blue"
            )
            device_id = self.health_app_scanner._get_current_device_id()
            device_file_path = self.health_app_scanner._get_device_health_app_file_path(
                device_id
            )

            if os.path.exists(device_file_path):
                self.log_message(
                    f"Found health app list for device {device_id}: {device_file_path}",
                    "green",
                )
                self.current_health_app_list_file = device_file_path
                self.health_app_scanner._load_health_apps_from_file(device_file_path)

                # Persist device-specific path in config
                # Use a relative path based on UI scanner's api_dir when available
                try:
                    rel_path = os.path.relpath(device_file_path, self.health_app_scanner.api_dir)
                except Exception:
                    rel_path = device_file_path
                self.config.update_setting_and_save(
                    "CURRENT_HEALTH_APP_LIST_FILE",
                    rel_path,
                    self._sync_user_config_files,
                )
                return

            # If no file exists for this device
            self.log_message(
                f"No health app list found for device {device_id}. Scan needed.",
                "orange",
            )
            # Store the path where the file would be created
            self.current_health_app_list_file = device_file_path

            # Persist expected device-specific path in config
            try:
                rel_path = os.path.relpath(device_file_path, self.health_app_scanner.api_dir)
            except Exception:
                rel_path = device_file_path
            self.config.update_setting_and_save(
                "CURRENT_HEALTH_APP_LIST_FILE",
                rel_path,
                self._sync_user_config_files,
            )

            # Clear dropdown if no valid cache
            if self.health_app_dropdown and hasattr(self.health_app_dropdown, "clear"):
                try:
                    self.health_app_dropdown.clear()
                    self.health_app_dropdown.addItem(
                        "Select target app (Scan first)", None
                    )
                except Exception as e:
                    logging.error(f"Error updating health app dropdown: {e}")
            self.health_apps_data = []
        except Exception as e:
            logging.error(f"Error loading cached health apps: {e}", exc_info=True)
            self.log_message(f"Error loading cached health apps: {e}", "red")

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
                logging.debug("Application icon set successfully")
            else:
                logging.warning("Failed to get application icon")
        except Exception as e:
            logging.error(f"Failed to set application icon: {e}")

    def _ensure_output_directories_exist(self):
        """Ensure that all necessary output directories exist."""
        try:
            # The config class now handles creating session-specific directories
            # We just need to ensure the base output directory exists
            output_base_dir = getattr(
                self.config,
                "OUTPUT_DATA_DIR",
                os.path.join(self.api_dir, "output_data"),
            )

            # Handle case where OUTPUT_DATA_DIR might be None
            if output_base_dir is None:
                output_base_dir = os.path.join(self.api_dir, "output_data")
                self.config.update_setting_and_save(
                    "OUTPUT_DATA_DIR", output_base_dir, self._sync_user_config_files
                )

            # Create base output directory if it doesn't exist
            if not os.path.exists(output_base_dir):
                os.makedirs(output_base_dir)
                self.log_message(
                    f"Created base output directory: {output_base_dir}", "blue"
                )

            # The config class will create session-specific directories when paths are resolved
            # Update config with relative paths if using absolute paths
            self._update_relative_paths_in_config()

            # Synchronize the API directory user_config.json with the root user_config.json
            self._sync_user_config_files()

        except Exception as e:
            logging.error(f"Error creating output directories: {e}", exc_info=True)
            if hasattr(self, "log_output") and self.log_output:
                self.log_message(f"Error creating output directories: {e}", "red")

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
                "CURRENT_HEALTH_APP_LIST_FILE",
            ]

            # Process each path setting
            for setting_name in path_settings:
                current_value = getattr(self.config, setting_name, None)
                if current_value and os.path.isabs(current_value):
                    # Try to make it relative to the api_dir
                    try:
                        rel_path = os.path.relpath(current_value, self.api_dir)
                        # Only update if it's inside the api_dir hierarchy
                        if not rel_path.startswith(".."):
                            self.config.update_setting_and_save(
                                setting_name, rel_path, self._sync_user_config_files
                            )
                            logging.debug(
                                f"Updated {setting_name} to use relative path: {rel_path}"
                            )
                    except ValueError:
                        # Different drives, can't make relative
                        pass

        except Exception as e:
            logging.error(
                f"Error updating relative paths in config: {e}", exc_info=True
            )

    def _sync_user_config_files(self):
        """Synchronize ALL settings from the root user_config.json to the API directory user_config.json file."""
        try:
            # Path to the API directory user_config.json
            api_config_path = os.path.join(self.api_dir, "user_config.json")
            # Path to the root user_config.json (already set in self.config.USER_CONFIG_FILE_PATH)
            root_config_path = self.config.USER_CONFIG_FILE_PATH

            # If both files exist, synchronize all settings from root to API
            if os.path.exists(api_config_path) and os.path.exists(root_config_path):
                # Read root config file
                with open(root_config_path, "r", encoding="utf-8") as f:
                    root_config = json.load(f)

                # Read API config file
                with open(api_config_path, "r", encoding="utf-8") as f:
                    api_config = json.load(f)

                # Synchronize ALL settings from root to API config
                changes_made = False
                synchronized_settings = []

                for key, value in root_config.items():
                    # Skip certain settings that should not be synchronized or are handled differently
                    skip_keys = [
                        "CURRENT_HEALTH_APP_LIST_FILE",  # This is device-specific and managed separately
                        "LAST_SELECTED_APP",  # This is also managed separately
                    ]

                    if key in skip_keys:
                        continue

                    # Check if the value is different or missing in API config
                    if key not in api_config or api_config[key] != value:
                        api_config[key] = value
                        synchronized_settings.append(key)
                        changes_made = True

                # Save the updated API config if changes were made
                if changes_made:
                    with open(api_config_path, "w", encoding="utf-8") as f:
                        json.dump(api_config, f, indent=4, ensure_ascii=False)

                    # Log the synchronization
                    if len(synchronized_settings) <= 5:
                        settings_str = ", ".join(synchronized_settings)
                        self.log_message(
                            f"Synchronized settings to API config: {settings_str}",
                            "blue",
                        )
                        logging.debug(
                            f"Synchronized settings to API config file: {settings_str}"
                        )
                    else:
                        self.log_message(
                            f"Synchronized {len(synchronized_settings)} settings to API config file",
                            "blue",
                        )
                        logging.debug(
                            f"Synchronized {len(synchronized_settings)} settings to API config file: {api_config_path}"
                        )
                else:
                    logging.debug(
                        "No settings needed synchronization between root and API config files"
                    )

        except Exception as e:
            logging.error(f"Error synchronizing user config files: {e}", exc_info=True)
            if hasattr(self, "log_output") and self.log_output:
                self.log_message(f"Error synchronizing user config files: {e}", "red")

    def log_message(self, message: str, color: str = "white"):
        """Append a message to the log output with a specified color."""
        if not self.log_output:
            return

        app = QApplication.instance()
        if app and app.thread() != QThread.currentThread():
            logging.debug(f"LOG (from thread): {message}")
            return

        level_map = {
            "red": ("[[ERROR]]", "#FF4136"),
            "orange": ("[[WARNING]]", "#FF851B"),
            "green": ("[[SUCCESS]]", "#2ECC40"),
            "blue": ("[[INFO]]", "#0074D9"),
            "gray": ("[[DEBUG]]", "#AAAAAA"),
            "magenta": ("[[FOCUS]]", "#F012BE"),
            "cyan": ("[[FOCUS]]", "#7FDBFF"),
            "yellow": ("[[FOCUS]]", "#FFDC00"),
        }

        log_level, hex_color = level_map.get(color.lower(), ("", "#FFFFFF"))

        if log_level:
            log_html = f"<font color='{hex_color}'>{log_level}</font> {message}"
        else:
            log_html = message

        try:
            self.log_output.append(log_html)
            scrollbar = self.log_output.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
            QApplication.processEvents()
        except Exception as e:
            logging.error(f"Error updating log output: {e}")

    def log_action_with_focus(self, action_data: Dict[str, Any]):
        """Log action with focus area attribution."""
        # Handle both old format (from direct callback) and new format (from stdout parsing)
        if "focus_ids" in action_data:
            # New format from stdout parsing
            action_type = action_data.get("action", "unknown")
            reasoning = action_data.get("reasoning", "No reasoning provided")
            focus_ids = action_data.get("focus_ids", [])
            focus_names = action_data.get("focus_names", [])
        else:
            # Old format from direct callback
            action_type = action_data.get("action", "unknown")
            reasoning = action_data.get("reasoning", "No reasoning provided")
            focus_influence = action_data.get("focus_influence", [])

            # Get focus area names
            focus_names = []
            for focus_id in focus_influence:
                focus_name = self.get_focus_area_name(focus_id)
                if focus_name:
                    focus_names.append(focus_name)
            focus_ids = focus_influence

        # Format display
        if focus_names:
            focus_text = f" [Focus: {', '.join(focus_names)}]"
        elif focus_ids:
            focus_text = f" [Focus IDs: {', '.join(focus_ids)}]"
        else:
            focus_text = " [No focus influence specified]"

        # Create prefix emoji based on focus areas and action types
        if focus_ids:
            # Privacy-focused actions
            if any(
                fid in ["privacy_policy", "data_rights", "data_collection"]
                for fid in focus_ids
            ):
                prefix = "ðŸ”’ "  # Privacy-related actions
                color = "magenta"
            # Security-focused actions
            elif any(
                fid in ["security_features", "account_privacy"] for fid in focus_ids
            ):
                prefix = "ðŸ” "  # Security-related actions
                color = "cyan"
            # Tracking-related actions
            elif any(
                fid in ["third_party", "advertising_tracking", "network_requests"]
                for fid in focus_ids
            ):
                prefix = "ðŸ‘ï¸ "  # Tracking-related actions
                color = "orange"
            # Location and permissions-related actions
            elif any(fid in ["location_tracking", "permissions"] for fid in focus_ids):
                prefix = "ðŸ“ "  # Location-related actions
                color = "yellow"
            else:
                prefix = "ðŸ”Ž "  # Default for other focus areas
                color = "green"
        else:
            # Prefix by action type if no focus areas
            if action_type == "click":
                prefix = "ðŸ‘† "  # Click action
                color = "blue"
            elif action_type == "input":
                prefix = "âŒ¨ï¸ "  # Input action
                color = "cyan"
            elif action_type == "scroll_down" or action_type == "scroll_up":
                prefix = "ðŸ“œ "  # Scroll action
                color = "gray"
            elif action_type == "swipe_left" or action_type == "swipe_right":
                prefix = "ðŸ‘ˆ "  # Swipe action
                color = "gray"
            elif action_type == "back":
                prefix = "â¬…ï¸ "  # Back action
                color = "orange"
            else:
                prefix = "âš¡ "  # Default for unknown actions
                color = "white"

        # Log to UI with prefix
        log_message = (
            f"{prefix}Action: {action_type}{focus_text}\nReasoning: {reasoning}"
        )

        # Check if log_output exists and is properly initialized
        if hasattr(self, "log_output") and self.log_output:
            self.log_output.append(log_message)
        else:
            logging.debug(
                f"Log output not available, logging to console: {log_message}"
            )

        # Also send to colored logger
        self.log_message(log_message, color)

        # Append structured entry to Action History for easier review
        if hasattr(self, "action_history") and self.action_history:
            try:
                step_num = getattr(getattr(self, "crawler_manager", None), "step_count", None)
                step_label = f"Step {step_num}" if isinstance(step_num, int) else "Step"
                target_identifier = action_data.get("target_identifier")
                result_text = action_data.get("result") or action_data.get("status")

                structured_lines = [f"{step_label}: {action_type}"]
                if target_identifier:
                    structured_lines.append(f"Target: {target_identifier}")
                structured_lines.append(f"Reasoning: {reasoning}")
                if result_text:
                    structured_lines.append(f"Result: {result_text}")

                structured_entry = "\n".join(structured_lines)
                self.action_history.append(structured_entry)
                self.action_history.verticalScrollBar().setValue(self.action_history.verticalScrollBar().maximum())
            except Exception:
                # Fallback to simple append
                try:
                    self.action_history.append(log_message)
                    self.action_history.verticalScrollBar().setValue(self.action_history.verticalScrollBar().maximum())
                except Exception:
                    pass

    def get_focus_area_name(self, focus_id: str) -> Optional[str]:
        """Get human-readable name for focus area ID."""
        focus_areas = getattr(self.config, "FOCUS_AREAS", [])
        for area in focus_areas:
            if isinstance(area, dict) and area.get("id") == focus_id:
                return area.get("name", focus_id)
        return None

    def update_screenshot(self, file_path: str) -> None:
        """Update the screenshot displayed in the UI."""
        try:
            if self.screenshot_label and hasattr(self.screenshot_label, "setPixmap"):
                update_screenshot(self.screenshot_label, file_path)
            else:
                logging.warning(
                    f"Screenshot label not properly initialized for update from: {file_path}"
                )
        except Exception as e:
            logging.error(f"Error updating screenshot: {e}")

    def closeEvent(self, event):
        """Handle the window close event."""
        # Stop crawler process if running
        if hasattr(self, "crawler_manager"):
            self.crawler_manager.stop_crawler()

        # Stop app scan process if running
        if hasattr(self.health_app_scanner, "find_apps_process"):
            find_apps_process = self.health_app_scanner.find_apps_process
            if (
                find_apps_process
                and find_apps_process.state() != QProcess.ProcessState.NotRunning
            ):
                self.log_message(
                    "Closing UI: Terminating app scan process...", "orange"
                )
                find_apps_process.terminate()
                if not find_apps_process.waitForFinished(5000):
                    self.log_message(
                        "App scan process did not terminate gracefully. Killing...",
                        "red",
                    )
                    find_apps_process.kill()

        # Stop MobSF analysis process if running
        if hasattr(self.mobsf_ui_manager, "mobsf_analysis_process"):
            mobsf_process = self.mobsf_ui_manager.mobsf_analysis_process
            if (
                mobsf_process
                and mobsf_process.state() != QProcess.ProcessState.NotRunning
            ):
                self.log_message(
                    "Closing UI: Terminating MobSF analysis process...", "orange"
                )
                mobsf_process.terminate()
                if not mobsf_process.waitForFinished(5000):
                    self.log_message(
                        "MobSF analysis process did not terminate gracefully. Killing...",
                        "red",
                    )
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
    def perform_pre_crawl_validation(self):
        """Perform pre-crawl validation checks."""
        self.crawler_manager.perform_pre_crawl_validation()

    @slot()
    def check_pre_crawl_status(self):
        """Check and display pre-crawl validation status."""
        self.log_message("ðŸ” Checking pre-crawl validation status...", "blue")
        self.show_pre_crawl_validation_details()

    def show_pre_crawl_validation_details(self):
        """Show detailed pre-crawl validation status."""
        # This method is now handled asynchronously by the crawler manager
        # The validation results are displayed through the _display_validation_details method
        pass

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

    @slot()
    def generate_report(self):
        """Generate an analysis PDF for the latest run of the current session/app.

        This mirrors the CLI behavior: determine latest run_id from the session's database
        and write the PDF to the session 'reports' directory.
        """
        try:
            if not RunAnalyzer or not XHTML2PDF_AVAILABLE:
                self.log_message("Error: Analysis module or PDF library (xhtml2pdf) not available.", "red")
                return

            import sqlite3
            from pathlib import Path

            app_package = getattr(self.config, "APP_PACKAGE", None)
            output_data_dir = getattr(self.config, "OUTPUT_DATA_DIR", None)
            session_dir = getattr(self.config, "SESSION_DIR", None)
            db_path = getattr(self.config, "DB_NAME", None)

            if not app_package:
                self.log_message("Error: No target app selected.", "red")
                return
            if not output_data_dir:
                self.log_message("Error: OUTPUT_DATA_DIR is not configured.", "red")
                return

            # Prefer current session's DB if it exists; otherwise try to find latest session for this app
            resolved_db_path: Path = None  # type: ignore
            resolved_session_dir: Path = None  # type: ignore

            if db_path and Path(db_path).exists():
                resolved_db_path = Path(db_path)
                resolved_session_dir = Path(session_dir) if session_dir else Path(db_path).parent.parent
            else:
                # Fallback: discover latest session_dir for the current app
                try:
                    candidates: list[Path] = []
                    for sd in Path(output_data_dir).iterdir():
                        if sd.is_dir() and "_" in sd.name:
                            parts = sd.name.split("_")
                            if len(parts) >= 2 and parts[1] == app_package:
                                candidates.append(sd)
                    if not candidates:
                        self.log_message(f"Error: No session directories found for app '{app_package}'.", "red")
                        return
                    # Sort by timestamp inferred from name suffix; as a simple heuristic, use lexicographic desc
                    candidates.sort(key=lambda p: p.name, reverse=True)
                    resolved_session_dir = candidates[0]
                    db_dir = resolved_session_dir / "database"
                    found_dbs = list(db_dir.glob("*_crawl_data.db")) if db_dir.exists() else []
                    if not found_dbs:
                        self.log_message("Error: No database file found in the latest session.", "red")
                        return
                    resolved_db_path = found_dbs[0]
                except Exception as e:
                    self.log_message(f"Error discovering latest session DB: {e}", "red")
                    return

            # Determine latest run_id
            try:
                conn = sqlite3.connect(str(resolved_db_path))
                cur = conn.cursor()
                cur.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1")
                row = cur.fetchone()
                if row and row[0] is not None:
                    run_id = int(row[0])
                else:
                    cur.execute("SELECT run_id FROM runs LIMIT 1")
                    row2 = cur.fetchone()
                    if row2 and row2[0] is not None:
                        run_id = int(row2[0])
                    else:
                        self.log_message("Error: No runs found in the database. Cannot generate report.", "red")
                        conn.close()
                        return
                conn.close()
            except Exception as e:
                self.log_message(f"Error reading database to determine run_id: {e}", "red")
                return

            # Prepare output directory and filename
            reports_dir = Path(getattr(self.config, "PDF_REPORT_DIR", ""))
            if not reports_dir:
                reports_dir = resolved_session_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)

            pdf_filename = f"{app_package}_analysis.pdf"
            final_pdf_path = str(reports_dir / pdf_filename)

            # Run analysis
            try:
                self.show_busy("Generating report...")
                analyzer = RunAnalyzer(
                    db_path=str(resolved_db_path),
                    output_data_dir=output_data_dir,
                    app_package_for_run=app_package,
                )
                ok = analyzer.analyze_run_to_pdf(run_id, final_pdf_path)
            finally:
                self.hide_busy()

            if ok:
                self.log_message(f"✅ Report generated: {final_pdf_path}", "green")
            else:
                self.log_message("Error: Failed to generate report.", "red")
        except Exception as e:
            self.log_message(f"Error generating report: {e}", "red")

    def _get_connected_devices(self) -> List[str]:
        """Get a list of connected ADB devices."""
        try:
            result = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, check=True
            )
            devices = []
            for line in result.stdout.strip().split("\n")[1:]:
                if "\tdevice" in line:
                    devices.append(line.split("\t")[0])
            return devices
        except FileNotFoundError:
            self.log_message(
                "ERROR: 'adb' command not found. Is Android SDK platform-tools in your PATH?",
                "red",
            )
            return []
        except Exception as e:
            self.log_message(f"Error getting connected devices: {e}", "red")
            return []

    def _populate_device_dropdown(self):
        """Populate the device dropdown with connected devices."""
        self.log_message("Refreshing connected devices...", "blue")
        device_dropdown = self.config_widgets.get("TARGET_DEVICE_UDID")
        if not device_dropdown:
            return

        devices = self._get_connected_devices()
        device_dropdown.clear()

        if devices:
            device_dropdown.addItems(devices)
            self.log_message(f"Found devices: {', '.join(devices)}", "green")
        else:
            device_dropdown.addItem("No devices found")
            self.log_message("No connected devices found.", "orange")

        # Try to set to the currently configured device; otherwise auto-select first available
        current_udid = getattr(self.config, "TARGET_DEVICE_UDID", None)
        # Normalize placeholder values
        normalized_current = (current_udid or "").strip().lower()
        is_placeholder = normalized_current in ("no devices found", "")
        if devices:
            if current_udid and not is_placeholder:
                index = device_dropdown.findText(current_udid)
                if index != -1:
                    device_dropdown.setCurrentIndex(index)
                    return
            # Auto-select the first available device and persist to config
            device_dropdown.setCurrentIndex(0)
            try:
                self.config.update_setting_and_save(
                    "TARGET_DEVICE_UDID", devices[0], self._sync_user_config_files
                )
                self.log_message(f"Auto-selected device UDID: {devices[0]}", "blue")
            except Exception as e:
                self.log_message(f"Failed to auto-save selected device UDID: {e}", "red")
        else:
            # No devices present; ensure config does not keep placeholder as a real UDID
            try:
                self.config.update_setting_and_save(
                    "TARGET_DEVICE_UDID", None, self._sync_user_config_files
                )
            except Exception:
                pass


if __name__ == "__main__":
    # Import LoggerManager for proper logging setup
    try:
        from utils.utils import LoggerManager
    except ImportError:
        from utils.utils import LoggerManager

    app = QApplication(sys.argv)
    window = CrawlerControllerWindow()

    # Set up logging with LoggerManager
    logger_manager = LoggerManager()

    # Set the UI controller reference in LoggerManager for colored logging BEFORE setup_logging
    logger_manager.set_ui_controller(window)

    logger_manager.setup_logging(log_level_str="INFO")

    # Start in full screen mode but allow resizing
    window.showMaximized()
    sys.exit(app.exec())

