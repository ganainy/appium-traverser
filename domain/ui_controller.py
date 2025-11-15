# ui_controller.py - Main UI controller for the Appium Crawler

import logging
import os
import re
import subprocess
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional


from PySide6.QtCore import QProcess, Qt, QThread, QTimer, Signal, QUrl
from PySide6.QtCore import Slot as slot
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
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
    RunAnalyzer = None
    XHTML2PDF_AVAILABLE = False
from ui.component_factory import ComponentFactory
from ui.ui_state_handler import UIStateHandler
from ui.constants import UI_MODE_BASIC, UI_MODE_EXPERT, UI_MODE_DEFAULT, UI_MODE_CONFIG_KEY
from ui.config_ui_manager import ConfigManager
from ui.crawler_ui_manager import CrawlerManager
from ui.custom_widgets import BusyDialog
from ui.app_scanner_ui import HealthAppScanner
from ui.logo_widget import LogoWidget
from ui.mobsf_ui_manager import MobSFUIManager
from ui.ui_utils import update_screenshot


class CrawlerControllerWindow(QMainWindow):
    """Main window for the Appium Crawler Controller."""

    def __init__(self, config=None, api_dir=None):
        """Initialize the main UI controller window.
        
        Args:
            config: Optional Config instance. If None, creates a new one.
            api_dir: Optional API directory path. If None, uses project root.
        """
        super().__init__()
        
        # Initialize config if not provided
        if config is None:
            from config.app_config import Config
            config = Config()
        self.config = config
        
        # Initialize api_dir if not provided
        if api_dir is None:
            from utils.paths import find_project_root
            from pathlib import Path
            api_dir = str(find_project_root(Path(__file__).resolve().parent))
        self.api_dir = api_dir
        
        # Initialize empty config_widgets dict - will be populated by ComponentFactory
        self.config_widgets = {}
        
        # These will be created by _setup_ui method
        # Initialize as None for now - they'll be set by the UI creation methods
        self.start_btn = None
        self.stop_btn = None
        self.log_output = None
        self.action_history = None
        self.screenshot_label = None
        self.test_mobsf_conn_btn = None
        self.run_mobsf_analysis_btn = None
        self.clear_logs_btn = None
        self.current_health_app_list_file = None
        self.health_apps_data = None

        self._ensure_output_directories_exist()

        # Set the application icon
        self._set_application_icon()
        
        # Set the window title
        self.setWindowTitle("Appium Traverser")

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

        # Setup UI panels
        self._setup_ui(main_layout)

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

    def _setup_ui(self, main_layout: QHBoxLayout):
        """Setup the UI panels and initialize UIStateHandler."""
        # Create left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Create UI mode switch (Basic/Expert)
        mode_layout = QHBoxLayout()
        mode_label = QLabel("UI Mode:")
        self.config_manager.ui_mode_dropdown = QComboBox()
        self.config_manager.ui_mode_dropdown.addItems([
            UI_MODE_BASIC,
            UI_MODE_EXPERT
        ])

        # Get the UI mode from config
        initial_mode = UI_MODE_DEFAULT  # Default if not found

        # Try to get UI_MODE from the Config object's SQLite store
        try:
            stored_mode = self.config.get(UI_MODE_CONFIG_KEY)
            if stored_mode:
                initial_mode = stored_mode
                logging.debug(f"Setting initial UI mode from SQLite config store: {initial_mode}")
        except Exception as e:
            logging.warning(f"Error retrieving {UI_MODE_CONFIG_KEY} from config store: {e}")

        logging.debug(f"Initial UI mode determined as: {initial_mode}")

        # Set the dropdown to the initial mode
        mode_index = self.config_manager.ui_mode_dropdown.findText(initial_mode)
        if mode_index >= 0:
            self.config_manager.ui_mode_dropdown.setCurrentIndex(mode_index)
        else:
            self.config_manager.ui_mode_dropdown.setCurrentIndex(0)  # Default to Basic if not found

        from ui.strings import UI_MODE_TOOLTIP
        self.config_manager.ui_mode_dropdown.setToolTip(UI_MODE_TOOLTIP)
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.config_manager.ui_mode_dropdown)

        from ui.strings import RESET_TO_DEFAULTS_TOOLTIP
        reset_button = QPushButton("Reset Settings")
        reset_button.setToolTip(RESET_TO_DEFAULTS_TOOLTIP)
        reset_button.clicked.connect(self.config_manager.reset_settings)
        mode_layout.addWidget(reset_button)
        left_layout.addLayout(mode_layout)

        # Create scrollable area for config inputs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QFormLayout(scroll_content)

        # Store scroll_content in config_manager for later reference
        self.config_manager.scroll_content = scroll_content

        # Create the config inputs sections
        appium_group = ComponentFactory.create_appium_settings_group(
            scroll_layout, self.config_widgets, self.tooltips, self
        )
        appium_group.setObjectName("appium_settings_group")

        app_group = ComponentFactory.create_app_settings_group(
            scroll_layout, self.config_widgets, self.tooltips, self.config_manager
        )
        app_group.setObjectName("app_settings_group")

        ai_group = ComponentFactory.create_ai_settings_group(
            scroll_layout, self.config_widgets, self.tooltips, self.config_manager
        )
        ai_group.setObjectName("ai_settings_group")

        # Image Preprocessing placed directly after AI for clearer perception grouping
        image_prep_group = ComponentFactory.create_image_preprocessing_group(
            scroll_layout, self.config_widgets, self.tooltips
        )
        image_prep_group.setObjectName("image_preprocessing_group")

        focus_areas_group = ComponentFactory.create_focus_areas_group(
            scroll_layout, self.config_widgets, self.tooltips, self.config_manager
        )
        focus_areas_group.setObjectName("focus_areas_group")

        crawler_group = ComponentFactory.create_crawler_settings_group(
            scroll_layout, self.config_widgets, self.tooltips
        )
        crawler_group.setObjectName("crawler_settings_group")

        # Privacy & Network settings (traffic capture)
        privacy_network_group = ComponentFactory.create_privacy_network_group(
            scroll_layout, self.config_widgets, self.tooltips
        )
        privacy_network_group.setObjectName("privacy_network_group")

        # API Keys group (must be created before MobSF group for visibility control)
        api_keys_group = ComponentFactory.create_api_keys_group(
            scroll_layout, self.config_widgets, self.tooltips, self.config_manager
        )
        api_keys_group.setObjectName("api_keys_group")

        mobsf_group = ComponentFactory.create_mobsf_settings_group(
            scroll_layout, self.config_widgets, self.tooltips, self.config_manager
        )
        mobsf_group.setObjectName("mobsf_settings_group")

        # Recording group
        recording_group = ComponentFactory.create_recording_group(
            scroll_layout, self.config_widgets, self.tooltips
        )
        recording_group.setObjectName("recording_group")

        # Apply default values
        self.config_manager._apply_defaults_from_config_to_widgets()
        self.config_manager._update_crawl_mode_inputs_state()

        # Store the group widgets for mode switching
        self.ui_groups = {
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
        }
        # Also store in config_manager for backward compatibility
        self.config_manager.ui_groups = self.ui_groups

        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)

        # Add control buttons
        controls_group = ComponentFactory.create_control_buttons(self)
        left_layout.addWidget(controls_group)

        # Assign refresh_devices_btn if set by ComponentFactory
        if hasattr(self, "refresh_devices_btn"):
            pass  # Already set by ComponentFactory
        else:
            self.refresh_devices_btn = None

        # Copy UI references from config_manager to self for direct access
        if hasattr(self.config_manager, "health_app_dropdown"):
            self.health_app_dropdown = self.config_manager.health_app_dropdown

        if hasattr(self.config_manager, "refresh_apps_btn"):
            self.refresh_apps_btn = self.config_manager.refresh_apps_btn

        if hasattr(self.config_manager, "app_scan_status_label"):
            self.app_scan_status_label = self.config_manager.app_scan_status_label

        # Create UIStateHandler
        self.ui_state_handler = UIStateHandler(
            main_controller=self,
            config_handler=self.config_manager,
            config_widgets=self.config_widgets,
            ui_groups=self.ui_groups
        )

        # Connect UI mode dropdown to toggle UI complexity
        self.config_manager.ui_mode_dropdown.currentTextChanged.connect(
            self.ui_state_handler.toggle_ui_complexity
        )

        # Connect AI provider selection to update model types
        def _on_provider_changed(provider: str):
            self.ui_state_handler._update_model_types(provider)

        self.config_widgets["AI_PROVIDER"].currentTextChanged.connect(_on_provider_changed)

        # Wire up refresh button
        def _on_refresh_clicked():
            try:
                self.ui_state_handler._refresh_models()
            except Exception as e:
                logging.warning(f"Failed to refresh models: {e}")

        self.config_widgets["OPENROUTER_REFRESH_BTN"].clicked.connect(_on_refresh_clicked)

        # Wire up free-only filter to re-populate models
        def _on_free_only_changed(_state: int):
            try:
                # Save the preference first
                free_only = self.config_widgets["OPENROUTER_SHOW_FREE_ONLY"].isChecked()
                self.config_manager.config.set("OPENROUTER_SHOW_FREE_ONLY", free_only)
                
                # Then update the model list
                current_provider = self.config_widgets["AI_PROVIDER"].currentText()
                self.ui_state_handler._update_model_types(current_provider)
            except Exception as e:
                logging.debug(f"Failed to apply free-only filter: {e}")

        self.config_widgets["OPENROUTER_SHOW_FREE_ONLY"].stateChanged.connect(
            _on_free_only_changed
        )

        # Connect all widgets to auto-save
        self.config_manager.connect_widgets_for_auto_save()

        # Initialize the UI complexity based on the mode we determined
        self.ui_state_handler.toggle_ui_complexity(initial_mode)

        # Create right panel
        right_panel = QWidget()
        right_main_layout = QVBoxLayout(right_panel)

        # Step counter and status at the top (small header)
        header_layout = QHBoxLayout()
        self.step_label = QLabel("Step: 0")
        self.status_label = QLabel("Status: Idle")
        self.progress_bar = QProgressBar()
        header_layout.addWidget(self.step_label)
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.progress_bar)
        right_main_layout.addLayout(header_layout)

        # Main content area: Logs on left (2/3), Screenshot + Action History stacked on right (1/3)
        content_layout = QHBoxLayout()

        # Logs section - takes 2/3 of width and most of vertical space
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)

        # Add a clear button
        self.clear_logs_btn = QPushButton("Clear Logs")

        log_header_layout = QHBoxLayout()
        log_header_layout.addStretch()
        log_header_layout.addWidget(self.clear_logs_btn)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #333333;")

        log_layout.addLayout(log_header_layout)
        log_layout.addWidget(self.log_output)

        # Right side: Screenshot and Action History stacked vertically
        right_side_layout = QVBoxLayout()

        # Screenshot display (top right) - wider than tall
        screenshot_group = QGroupBox("Current Screenshot")
        screenshot_layout = QVBoxLayout(screenshot_group)
        self.screenshot_label = QLabel()
        self.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screenshot_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.screenshot_label.setMinimumHeight(300)
        self.screenshot_label.setMinimumWidth(300)
        self.screenshot_label.setStyleSheet("""
            border: 1px solid #555555;
            background-color: #2a2a2a;
        """)
        screenshot_layout.addWidget(self.screenshot_label)

        # Action history (bottom right) - small, square or slightly taller
        action_history_group = QGroupBox("Action History")
        action_history_layout = QVBoxLayout(action_history_group)
        self.action_history = QTextEdit()
        self.action_history.setReadOnly(True)
        try:
            from ui.strings import ACTION_HISTORY_PLACEHOLDER
            self.action_history.setPlaceholderText(ACTION_HISTORY_PLACEHOLDER)
        except Exception:
            pass
        self.action_history.setStyleSheet("""
            background-color: #333333; 
            color: #FFFFFF; 
            font-size: 11px; 
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            border: 1px solid #555555;
        """)
        try:
            from PySide6.QtWidgets import QTextEdit as _QTextEdit
            self.action_history.setLineWrapMode(_QTextEdit.LineWrapMode.WidgetWidth)
        except Exception:
            pass
        # Action history - small size
        self.action_history.setMinimumHeight(150)
        self.action_history.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        action_history_layout.addWidget(self.action_history)

        # Add screenshot and action history to right side layout
        right_side_layout.addWidget(screenshot_group, 2)  # Screenshot gets more space
        right_side_layout.addWidget(action_history_group, 1)  # Action history gets less space

        # Add logs (left, 2/3) and right side (1/3) to content layout
        content_layout.addWidget(log_group, 2)  # Logs take 2/3 of width
        content_layout.addLayout(right_side_layout, 1)  # Right side takes 1/3 of width

        # Add content layout to main layout
        right_main_layout.addLayout(content_layout, 1)  # Content takes all remaining vertical space

        # Add panels to main layout with stretch factors
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)

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
        """Show a modal busy overlay with the given message.
        
        The overlay will:
        - Cover the entire main window with a semi-transparent backdrop
        - Display a centered loading dialog with the message
        - Disable all interactive widgets in the UI
        - Block all user interactions until hidden
        """
        try:
            if self._busy_dialog is None:
                self._busy_dialog = BusyDialog(self)
            self._busy_dialog.set_message(message)
            # Cover the entire main window - ensure it's properly sized
            try:
                # Use frameGeometry to get the full window including title bar
                main_geometry = self.frameGeometry()
                self._busy_dialog.setGeometry(main_geometry)
            except Exception:
                # Fallback: use the main window geometry
                try:
                    self._busy_dialog.setGeometry(self.geometry())
                except Exception:
                    pass
            # Show and raise the dialog to ensure it's visible
            self._busy_dialog.show()
            self._busy_dialog.raise_()
            self._busy_dialog.activateWindow()
            QApplication.processEvents()
        except Exception as e:
            logging.debug(f"Failed to show busy overlay: {e}")

    def hide_busy(self) -> None:
        """Hide the busy overlay if visible.
        
        This will re-enable all widgets that were disabled during loading.
        """
        try:
            if self._busy_dialog:
                # Use close_dialog to properly reset state
                if hasattr(self._busy_dialog, 'close_dialog'):
                    self._busy_dialog.close_dialog()
                else:
                    self._busy_dialog.hide()
                QApplication.processEvents()
        except Exception as e:
            logging.debug(f"Failed to hide busy overlay: {e}")

    def _audio_alert(self, kind: str = "finish") -> None:
        """Play an audible alert using MP3 sound files.

        kind:
        - 'finish' -> done-soundeffect.mp3
        - 'error'  -> error-soundeffect.mp3

        Falls back to system beep if MP3 files are not available.
        """
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            from pathlib import Path
            from utils.paths import find_project_root
            
            # Find project root to locate sound files
            try:
                project_root = find_project_root(Path(__file__))
            except Exception:
                # Fallback: try to find from current working directory
                project_root = Path.cwd()
            
            # Determine which sound file to play
            if kind == "error":
                sound_file = project_root / "error-soundeffect.mp3"
            else:  # finish or default
                sound_file = project_root / "done-soundeffect.mp3"
            
            # Check if sound file exists
            if sound_file.exists():
                # Create a media player instance
                player = QMediaPlayer()
                # Convert path to QUrl for cross-platform compatibility
                sound_url = QUrl.fromLocalFile(str(sound_file.absolute()))
                player.setSource(sound_url)
                player.play()
                # Note: QMediaPlayer will be garbage collected after play() completes
                # For longer sounds, you might want to keep a reference
                return  # Successfully played MP3
            else:
                logging.debug(f"Sound file not found: {sound_file}")
        except ImportError:
            logging.debug("QMediaPlayer not available, falling back to system beep")
        except Exception as e:
            logging.debug(f"MP3 playback failed: {e}, falling back to system beep")

        # Fallback: use system beep
        try:
            from PySide6.QtWidgets import QApplication
            if kind == "error":
                QApplication.beep()
                # Schedule a second beep shortly after
                QTimer.singleShot(250, lambda: QApplication.beep())
            else:
                QApplication.beep()
        except Exception as e:
            logging.debug(f"Audio alert fallback failed: {e}")

    def _create_tooltips(self) -> Dict[str, str]:
        """Create tooltips for UI elements."""
        from ui.strings import get_tooltips_dict
        return get_tooltips_dict()

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

            # Note: start_btn and stop_btn are already connected in ComponentFactory.create_control_buttons
            # They connect to self.start_crawler and self.stop_crawler (delegate methods)

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
            self.config.update_setting_and_save("AI_PROVIDER", provider)
            self.config.update_setting_and_save("DEFAULT_MODEL_TYPE", model)
            # Re-initialize AgentAssistant
            self._init_agent_assistant()
            self.log_message(f"AI provider switched to '{provider}', model '{model}'. AgentAssistant reloaded.", "blue")
        except Exception as e:
            self.log_message(f"Error switching provider/model: {e}", "red")

    def _init_agent_assistant(self):
        """(Re)initialize the AgentAssistant with current config and model."""
        try:
            from domain.agent_assistant import AgentAssistant
            import logging
            
            # Clean up old logger handlers before creating new AgentAssistant
            # This prevents "I/O operation on closed file" errors when switching AI settings
            if hasattr(self, 'agent_assistant') and self.agent_assistant:
                try:
                    if hasattr(self.agent_assistant, 'ai_interaction_readable_logger'):
                        logger = self.agent_assistant.ai_interaction_readable_logger
                        if logger and logger.handlers:
                            for handler in list(logger.handlers):
                                try:
                                    if isinstance(handler, logging.FileHandler):
                                        handler.close()
                                except Exception:
                                    pass
                                logger.removeHandler(handler)
                except Exception as e:
                    logging.debug(f"Error cleaning up old logger handlers: {e}")
            
            provider = self.config.get("AI_PROVIDER", None)
            model = self.config.get("DEFAULT_MODEL_TYPE", None)
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
            app_icon = LogoWidget.get_icon(self.api_dir)

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
                    "OUTPUT_DATA_DIR", output_base_dir
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

            # Persists automatically via SQLite-backed Config

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
                current_value = self.config.get(setting_name, None)
                if current_value and os.path.isabs(current_value):
                    # Try to make it relative to the api_dir
                    try:
                        rel_path = os.path.relpath(current_value, self.api_dir)
                        # Only update if it's inside the api_dir hierarchy
                        if not rel_path.startswith(".."):
                            self.config.update_setting_and_save(
                                setting_name, rel_path
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
        # New format from stdout parsing
        action_type = action_data.get("action", "unknown")
        reasoning = action_data.get("reasoning", "No reasoning provided")
        focus_ids = action_data.get("focus_ids", [])
        focus_names = action_data.get("focus_names", [])

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

    # Configuration synchronization method
    def _sync_user_config_files(self):
        """Synchronize user configuration files.
        
        This method is used as a callback when configuration settings are updated.
        Currently, synchronization is handled automatically by the config system,
        so this is a no-op method maintained for API compatibility.
        """
        # Configuration synchronization is now handled automatically by the config system
        # This method is kept for backward compatibility with existing callbacks
        pass
    
    # Delegate methods to appropriate managers
    @slot()
    def perform_pre_crawl_validation(self):
        """Perform pre-crawl validation checks."""
        if hasattr(self, 'crawler_manager') and self.crawler_manager:
            self.crawler_manager.perform_pre_crawl_validation()
        else:
            self.log_message("ERROR: Crawler manager not initialized", "red")
    
    @slot()
    def start_crawler(self):
        """Start the crawler process."""
        if hasattr(self, 'crawler_manager') and self.crawler_manager:
            self.crawler_manager.start_crawler()
        else:
            self.log_message("ERROR: Crawler manager not initialized", "red")
    
    @slot()
    def stop_crawler(self):
        """Stop the crawler process."""
        if hasattr(self, 'crawler_manager') and self.crawler_manager:
            self.crawler_manager.stop_crawler()
        else:
            self.log_message("ERROR: Crawler manager not initialized", "red")
    
    @slot()
    def generate_report(self):
        """Generate a PDF report for the latest crawl run."""
        import sqlite3
        from pathlib import Path

        app_package = self.config.get("APP_PACKAGE", None)
        output_data_dir = self.config.get("OUTPUT_DATA_DIR", None)
        session_dir = self.config.SESSION_DIR if hasattr(self.config, 'SESSION_DIR') else None
        db_path = self.config.get("DB_NAME", None)

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
        reports_dir = Path(self.config.get("PDF_REPORT_DIR", ""))
        if not reports_dir:
            reports_dir = resolved_session_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        pdf_filename = f"{app_package}_analysis.pdf"
        final_pdf_path = str(reports_dir / pdf_filename)

        # Run analysis
        if RunAnalyzer is not None:
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
        else:
            self.log_message("Error: PDF analysis not available.", "red")
            ok = False

        if ok:
            self.log_message(f"✅ Report generated: {final_pdf_path}", "green")
            # Play success sound
            if hasattr(self, '_audio_alert'):
                self._audio_alert('finish')
        else:
            self.log_message("Error: Failed to generate report.", "red")
            # Play error sound
            if hasattr(self, '_audio_alert'):
                self._audio_alert('error')

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
        current_udid = self.config.get("TARGET_DEVICE_UDID", None)
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
                    "TARGET_DEVICE_UDID", devices[0]
                )
                self.log_message(f"Auto-selected device UDID: {devices[0]}", "blue")
            except Exception as e:
                self.log_message(f"Failed to auto-save selected device UDID: {e}", "red")
        else:
            # No devices present; ensure config does not keep placeholder as a real UDID
            try:
                self.config.update_setting_and_save(
                    "TARGET_DEVICE_UDID", None
                )
            except Exception:
                pass


if __name__ == "__main__":
    # Import LoggerManager for proper logging setup
    from utils.utils import LoggerManager

    # GUI initialization is now handled in interfaces/gui.py
    # This file contains the controller class only

