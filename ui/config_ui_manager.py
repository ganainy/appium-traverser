#!/usr/bin/env python3
# ui/config_manager.py - Configuration management for the UI controller

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QTimer, Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Import constants
from ui.constants import UI_MODE_CONFIG_KEY


class ConfigManager(QObject):
    """Manages configuration for the Appium Crawler Controller UI."""
    
    # These attributes are dynamically added by ComponentFactory and CrawlerControllerWindow
    health_app_dropdown: QComboBox
    refresh_apps_btn: QPushButton
    app_scan_status_label: QLabel
    ui_mode_dropdown: QComboBox
    ui_groups: Dict[str, QGroupBox]
    scroll_content: QWidget
    focus_areas_widget: Optional[Any] = None
    
    def __init__(self, config, main_controller):
        """
        Initialize the configuration manager.
        
        Args:
            config: The application config instance
            main_controller: The main UI controller
        """
        super().__init__()
        self.config = config
        self.main_controller = main_controller  # This is a reference to CrawlerControllerWindow
        # Debounce timers for prompt fields (save after user stops typing)
        self._prompt_save_timers: Dict[str, QTimer] = {}
    # self.user_config = {}  # Removed: not needed
    logging.debug("ConfigManager initialized with new Config interface (SQLite-backed)")
    
    def _apply_defaults_from_config_to_widgets(self):
        """Apply default values from the config module to UI widgets."""
        for key, widget in self.main_controller.config_widgets.items():
            # Skip UI indicator widgets that aren't actual config settings
            if key in ['IMAGE_CONTEXT_WARNING']:
                continue
                
            try:
                value = self.config.get(key)
            except Exception:
                logging.warning(f"Config key '{key}' not found in config.")
                continue
            if value is None:
                logging.debug(f"Config key '{key}' has None value.")
                continue
                
            try:
                if isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QLabel):
                    widget.setText(str(value))
                elif isinstance(widget, QSpinBox):
                    if isinstance(value, (list, dict)):
                        logging.warning(f"Skipping non-numeric value for spinbox '{key}': {value}")
                        continue
                    widget.setValue(int(value))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QComboBox):
                    if isinstance(value, str):
                        index = widget.findText(value)
                        if index >= 0:
                            widget.setCurrentIndex(index)
                elif isinstance(widget, QTextEdit):
                    if isinstance(value, list):
                        widget.setPlainText('\n'.join(value))
                    else:
                        widget.setPlainText(str(value))
            except (ValueError, TypeError) as e:
                logging.warning(f"Error setting config widget for '{key}': {e}")
    
    def _load_defaults_from_config(self):
        """Load configuration values from config.py module."""
        missing_configs = []
        for key, widget in self.main_controller.config_widgets.items():
            # Skip UI indicator widgets that aren't actual config settings
            if key in ['IMAGE_CONTEXT_WARNING']:
                continue
                
            try:
                value = self.config.get(key)
            except Exception:
                missing_configs.append(f"{key}: Not found in config.")
                continue
            if value is None:
                missing_configs.append(f"{key}: Has None value in config module.")
                continue

            try:
                if isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QLabel):
                    widget.setText(str(value))
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(value))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QComboBox):
                    if isinstance(value, str):
                        index = widget.findText(value)
                        if index >= 0:
                            widget.setCurrentIndex(index)
                elif isinstance(widget, QTextEdit):
                    if isinstance(value, list):
                        widget.setPlainText('\n'.join(value))
                    else:
                        widget.setPlainText(str(value))
            except (ValueError, TypeError) as e:
                missing_configs.append(f"{key}: Error setting widget - {e}")

        if missing_configs:
            error_msg = "The following required configurations are missing or invalid:\n" + "\n".join(missing_configs)
            logging.error(error_msg)
            if hasattr(self.main_controller, 'log_output') and self.main_controller.log_output:
                self.main_controller.log_output.append(error_msg)
            raise ValueError(error_msg)
    
    def _update_crawl_mode_inputs_state(self, mode: Optional[str] = None):
        """Update the state of crawl mode related inputs based on selected mode."""
        try:
            if mode is None and 'CRAWL_MODE' in self.main_controller.config_widgets:
                mode = self.main_controller.config_widgets['CRAWL_MODE'].currentText()
            elif mode is None:
                # Default to steps if CRAWL_MODE widget not found
                mode = 'steps'
                
            # Check for existence of mode-dependent widgets
            if 'MAX_CRAWL_STEPS' in self.main_controller.config_widgets:
                self.main_controller.config_widgets['MAX_CRAWL_STEPS'].setEnabled(mode == 'steps')
            if 'MAX_CRAWL_DURATION_SECONDS' in self.main_controller.config_widgets:
                self.main_controller.config_widgets['MAX_CRAWL_DURATION_SECONDS'].setEnabled(mode == 'time')
        except Exception as e:
            logging.error(f"Error updating crawl mode inputs: {e}")
    
    @Slot()
    def save_config(self, key: Optional[str] = None):
        """
        Save the current configuration to the user config file.
        If a key is provided, only that key's widget value is saved.
        Otherwise, all widget values are saved.
        
        API keys are saved to .env file, other settings to SQLite.
        """
        config_data = {}
        api_keys_to_save = {}  # Track API keys separately for .env file

        if key and key in self.main_controller.config_widgets:
            # Skip service-managed keys - they're handled separately
            if key in ['CRAWLER_AVAILABLE_ACTIONS', 'CRAWLER_ACTION_DECISION_PROMPT']:
                return  # These are managed via services, not config
            
            # Save only the specific key that triggered the change
            widget = self.main_controller.config_widgets[key]
            value = self._get_widget_value(key, widget)
            if value is not None:  # Skip None values (e.g., read-only QLabel widgets)
                # Check if this is an API key (secret)
                if self._is_api_key(key):
                    api_keys_to_save[key] = value
                else:
                    config_data[key] = value
        else:
            # Fallback to saving all widgets if no key is provided
            for k, widget in self.main_controller.config_widgets.items():
                # Skip UI indicator widgets that aren't actual config settings
                if k in ['IMAGE_CONTEXT_WARNING']:
                    continue
                # Skip service-managed keys - they're handled separately
                if k in ['CRAWLER_AVAILABLE_ACTIONS', 'CRAWLER_ACTION_DECISION_PROMPT']:
                    continue
                value = self._get_widget_value(k, widget)
                if value is not None:  # Skip None values (e.g., read-only QLabel widgets)
                    # Check if this is an API key (secret)
                    if self._is_api_key(k):
                        api_keys_to_save[k] = value
                    else:
                        config_data[k] = value

        # --- Always save these non-widget settings ---
        # Save UI mode setting
        if hasattr(self, 'ui_mode_dropdown'):
            config_data['UI_MODE'] = self.ui_mode_dropdown.currentText()

        # Save health app list path
        if self.main_controller.current_health_app_list_file:
            config_data['CURRENT_HEALTH_APP_LIST_FILE'] = self.main_controller.current_health_app_list_file

        # Save selected app info
        selected_index = self.main_controller.health_app_dropdown.currentIndex() if self.main_controller.health_app_dropdown else -1
        if selected_index > 0 and self.main_controller.health_app_dropdown:
            selected_data = self.main_controller.health_app_dropdown.itemData(selected_index)
            if selected_data and isinstance(selected_data, dict):
                config_data['LAST_SELECTED_APP'] = {
                    'package_name': selected_data.get('package_name', ''),
                    'activity_name': selected_data.get('activity_name', ''),
                    'app_name': selected_data.get('app_name', '')
                }
        
        # Save API keys to .env file
        if api_keys_to_save:
            self._save_api_keys_to_env(api_keys_to_save)
        
        # Update the config object and persist to SQLite (non-secrets only)
        for k, value in config_data.items():
            self.config.set(k, value)

        # Also update environment variables for API keys (Config.set() handles this)
        for k, value in api_keys_to_save.items():
            self.config.set(k, value)

        # Provide user feedback
        if api_keys_to_save and config_data:
            self.main_controller.log_message(
                f"Configuration saved: {len(config_data)} settings to SQLite, {len(api_keys_to_save)} API key(s) to .env file.", 
                'green'
            )
            # Play success sound
            if hasattr(self.main_controller, '_audio_alert'):
                self.main_controller._audio_alert('finish')
        elif api_keys_to_save:
            self.main_controller.log_message(
                f"API key(s) saved to .env file: {', '.join(api_keys_to_save.keys())}.", 
                'green'
            )
            # Play success sound
            if hasattr(self.main_controller, '_audio_alert'):
                self.main_controller._audio_alert('finish')
        else:
            self.main_controller.log_message("Configuration auto-saved to SQLite successfully.", 'green')
            # Play success sound for auto-save
            if hasattr(self.main_controller, '_audio_alert'):
                self.main_controller._audio_alert('finish')

    def _is_api_key(self, key: str) -> bool:
        """
        Check if a configuration key is an API key (secret).
        
        Args:
            key: Configuration key name
            
        Returns:
            True if the key is an API key, False otherwise
        """
        # Use the same logic as Config._is_secret()
        api_key_names = {"OPENROUTER_API_KEY", "GEMINI_API_KEY", "MOBSF_API_KEY", "OLLAMA_BASE_URL", "PCAPDROID_API_KEY"}
        upper_key = key.upper()
        if upper_key in api_key_names:
            return True
        # Also check if key ends with "_KEY" (pattern matching)
        return key == upper_key and upper_key.endswith("_KEY")

    def _save_api_keys_to_env(self, api_keys: Dict[str, str]) -> None:
        """
        Save API keys to the .env file using python-dotenv.
        
        Args:
            api_keys: Dictionary mapping API key names to their values
        """
        try:
            from dotenv import set_key, load_dotenv
        except ImportError:
            error_msg = "python-dotenv not available. Cannot save API keys to .env file. Please install it with: pip install python-dotenv"
            logging.error(error_msg)
            self.main_controller.log_message(error_msg, 'red')
            return
        
        try:
            # Get project root directory
            from utils.paths import find_project_root
            project_root = find_project_root(Path(self.config.BASE_DIR))
            env_file_path = project_root / '.env'
            
            # Ensure .env file exists (create if it doesn't)
            if not env_file_path.exists():
                env_file_path.touch()
                logging.info(f"Created .env file at {env_file_path}")
            
            # Load existing .env file to preserve other variables
            load_dotenv(env_file_path, override=False)
            
            # Save each API key to .env file
            saved_keys = []
            for key, value in api_keys.items():
                # Normalize key to uppercase (standard for .env files)
                normalized_key = key.upper()
                
                # Only save non-empty values
                if value and value.strip():
                    set_key(str(env_file_path), normalized_key, value.strip())
                    saved_keys.append(normalized_key)
                    logging.debug(f"Saved {normalized_key} to .env file")
                else:
                    # If value is empty, remove the key from .env
                    set_key(str(env_file_path), normalized_key, "")
                    logging.debug(f"Removed {normalized_key} from .env file (empty value)")
            
            if saved_keys:
                logging.info(f"Successfully saved {len(saved_keys)} API key(s) to .env file: {', '.join(saved_keys)}")
            
        except Exception as e:
            error_msg = f"Failed to save API keys to .env file: {e}"
            logging.exception(error_msg)
            self.main_controller.log_message(error_msg, 'red')

    @Slot()
    def reset_settings(self) -> None:
        """Reset persisted configuration to defaults via CLI command."""
        logging.info("Reset Settings button clicked - method called")
        self.main_controller.log_message("Reset Settings button clicked...", 'blue')
        
        # Get parent widget - main_controller is a QMainWindow, so it can be used directly
        parent_widget = self.main_controller if isinstance(self.main_controller, QWidget) else None
        
        # Get list of settings that will be reset
        try:
            default_snapshot = self.config._default_snapshot
            current_settings = {}
            settings_to_reset = []
            
            # Collect current values and identify what will change
            for key in sorted(default_snapshot.keys()):
                try:
                    current_value = self.config.get(key)
                    default_value = default_snapshot[key]
                    current_settings[key] = current_value
                    
                    # Only show settings that differ from defaults
                    if current_value != default_value:
                        settings_to_reset.append({
                            'key': key,
                            'current': current_value,
                            'default': default_value
                        })
                except Exception:
                    pass
            
            # Build confirmation message with details
            if settings_to_reset:
                reset_details = "The following settings will be reset to defaults:\n\n"
                for item in settings_to_reset:
                    current_str = str(item['current'])[:60]  # Truncate long values
                    default_str = str(item['default'])[:60]
                    reset_details += f"• {item['key']}:\n"
                    reset_details += f"  Current: {current_str}\n"
                    reset_details += f"  → Default: {default_str}\n\n"
                
                reset_details += "\nAlso reset:\n"
                reset_details += "• ALLOWED_EXTERNAL_PACKAGES (to default list)\n"
                reset_details += "• Focus Areas (all cleared)\n"
                reset_details += "• Crawler Actions (to defaults)\n"
                reset_details += "• Crawler Prompts (to defaults)\n"
            else:
                reset_details = "All settings are already at default values.\n\n"
                reset_details += "This will still reset:\n"
                reset_details += "• ALLOWED_EXTERNAL_PACKAGES\n"
                reset_details += "• Focus Areas\n"
                reset_details += "• Crawler Actions\n"
                reset_details += "• Crawler Prompts\n"
            
            # Create custom dialog with better formatting
            dialog = QDialog(parent_widget)
            dialog.setWindowTitle("Reset Settings - Confirmation")
            dialog.setMinimumWidth(600)
            dialog.setMinimumHeight(400)
            dialog.setMaximumWidth(800)
            dialog.setMaximumHeight(600)
            
            layout = QVBoxLayout(dialog)
            
            # Title label
            title_label = QLabel("The following will be reset to defaults:")
            title_label.setStyleSheet("font-weight: bold; font-size: 12pt; margin-bottom: 10px;")
            layout.addWidget(title_label)
            
            # Scrollable text area for details
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMinimumHeight(300)
            
            text_widget = QTextEdit()
            text_widget.setReadOnly(True)
            text_widget.setPlainText(reset_details)
            text_widget.setStyleSheet("font-family: monospace; font-size: 9pt;")
            scroll.setWidget(text_widget)
            layout.addWidget(scroll)
            
            # Question label
            question_label = QLabel("Continue with reset?")
            question_label.setStyleSheet("font-weight: bold; margin-top: 10px; margin-bottom: 10px;")
            layout.addWidget(question_label)
            
            # Buttons
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No,
                Qt.Orientation.Horizontal
            )
            button_box.button(QDialogButtonBox.StandardButton.Yes).setText("Yes")
            button_box.button(QDialogButtonBox.StandardButton.No).setText("No")
            button_box.button(QDialogButtonBox.StandardButton.No).setDefault(True)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            # Show dialog and get result
            confirmation = dialog.exec()
            confirmed = (confirmation == QDialog.DialogCode.Accepted)
        except Exception as e:
            logging.warning(f"Could not collect reset details: {e}")
            # Fallback to simple confirmation
            confirmation = QMessageBox.question(
                parent_widget,
                "Reset Settings",
                "Reset all configuration settings to their default values?",
                buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                defaultButton=QMessageBox.StandardButton.No,
            )
            confirmed = (confirmation == QMessageBox.StandardButton.Yes)
            settings_to_reset = []

        if not confirmed:
            logging.info("Reset Settings cancelled by user")
            self.main_controller.log_message("Reset Settings cancelled.", 'orange')
            return

        # Log what will be reset
        if settings_to_reset:
            logging.info(f"Resetting {len(settings_to_reset)} settings to defaults")
            self.main_controller.log_message(f"Resetting {len(settings_to_reset)} settings to defaults...", 'blue')
            for item in settings_to_reset[:10]:  # Log first 10
                log_msg = f"  {item['key']}: {item['current']} → {item['default']}"
                logging.info(log_msg)
                self.main_controller.log_message(log_msg, 'blue')
            if len(settings_to_reset) > 10:
                self.main_controller.log_message(f"  ... and {len(settings_to_reset) - 10} more", 'blue')
        
        logging.info("User confirmed reset - proceeding with CLI command")
        self.main_controller.log_message("Executing reset via CLI...", 'blue')
        
        try:
            # Find project root and run_cli.py path
            from utils.paths import find_project_root
            logging.debug(f"Finding project root from BASE_DIR: {self.config.BASE_DIR}")
            project_root = find_project_root(Path(self.config.BASE_DIR))
            run_cli_path = project_root / "run_cli.py"
            
            logging.info(f"Project root: {project_root}")
            logging.info(f"run_cli.py path: {run_cli_path}")
            self.main_controller.log_message(f"Using CLI: {run_cli_path}", 'blue')
            
            if not run_cli_path.exists():
                error_msg = f"Could not find run_cli.py at {run_cli_path}"
                logging.error(error_msg)
                self.main_controller.log_message(error_msg, 'red')
                raise FileNotFoundError(error_msg)
            
            # Execute CLI command: python run_cli.py config reset --yes
            python_exe = sys.executable
            cmd = [python_exe, str(run_cli_path), "config", "reset", "--yes"]
            logging.info(f"Executing CLI command: {' '.join(cmd)}")
            self.main_controller.log_message(f"Executing: python run_cli.py config reset --yes", 'blue')
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(project_root)
            )
            
            logging.info(f"CLI command completed with return code: {result.returncode}")
            if result.stdout:
                logging.info(f"CLI stdout: {result.stdout}")
                self.main_controller.log_message(f"CLI output: {result.stdout.strip()}", 'blue')
            if result.stderr:
                logging.warning(f"CLI stderr: {result.stderr}")
                self.main_controller.log_message(f"CLI warnings: {result.stderr.strip()}", 'orange')
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                full_error = f"CLI command failed with return code {result.returncode}:\n{error_msg}"
                logging.error(full_error)
                self.main_controller.log_message(f"CLI command failed: {error_msg}", 'red')
                raise RuntimeError(full_error)
            
            # Reload configuration after reset
            logging.info("Reloading configuration after reset")
            self.main_controller.log_message("Reloading configuration...", 'blue')
            
            # Force reload all configuration
            self.load_config()
            
            # Force reload actions widget
            try:
                if 'CRAWLER_AVAILABLE_ACTIONS' in self.main_controller.config_widgets:
                    logging.info("Reloading actions widget after reset")
                    self._load_actions_from_service()
                    # Force widget update
                    actions_widget = self.main_controller.config_widgets['CRAWLER_AVAILABLE_ACTIONS']
                    if hasattr(actions_widget, 'update'):
                        actions_widget.update()
                    if hasattr(actions_widget, 'repaint'):
                        actions_widget.repaint()
            except Exception as e:
                logging.exception(f"Failed to reload actions widget: {e}")
            
            # Force reload prompts widget
            try:
                if 'CRAWLER_ACTION_DECISION_PROMPT' in self.main_controller.config_widgets:
                    logging.info("Reloading prompts widget after reset")
                    self._load_prompts_from_service()
                    # Force widget update
                    prompt_widget = self.main_controller.config_widgets['CRAWLER_ACTION_DECISION_PROMPT']
                    if hasattr(prompt_widget, 'update'):
                        prompt_widget.update()
                    if hasattr(prompt_widget, 'repaint'):
                        prompt_widget.repaint()
            except Exception as e:
                logging.exception(f"Failed to reload prompts widget: {e}")
            
            # Force reload allowed packages widget
            try:
                if 'ALLOWED_EXTERNAL_PACKAGES_WIDGET' in self.main_controller.config_widgets:
                    logging.info("Reloading allowed packages widget after reset")
                    packages_widget = self.main_controller.config_widgets['ALLOWED_EXTERNAL_PACKAGES_WIDGET']
                    from ui.allowed_packages_widget import AllowedPackagesWidget
                    if isinstance(packages_widget, AllowedPackagesWidget):
                        # Get default packages from config
                        default_packages = self.config.get('ALLOWED_EXTERNAL_PACKAGES', [])
                        packages_widget.set_packages(default_packages if default_packages else [])
                        if hasattr(packages_widget, 'update'):
                            packages_widget.update()
                        if hasattr(packages_widget, 'repaint'):
                            packages_widget.repaint()
            except Exception as e:
                logging.exception(f"Failed to reload allowed packages widget: {e}")
            
            # Force reload focus areas widget
            if hasattr(self, 'focus_areas_widget') and self.focus_areas_widget:
                try:
                    logging.info("Reloading focus areas widget after reset")
                    self.focus_areas_widget.reload_focus_areas()
                    if hasattr(self.focus_areas_widget, 'update'):
                        self.focus_areas_widget.update()
                    if hasattr(self.focus_areas_widget, 'repaint'):
                        self.focus_areas_widget.repaint()
                except Exception:
                    logging.exception("Failed to reload focus areas after reset; clearing locally.")
                    self.focus_areas_widget.focus_areas = []
                    self.focus_areas_widget.create_focus_items()
            
            # Force update all other widgets
            try:
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()  # Process pending events to update UI
            except Exception:
                pass
            
            # Show summary of what was reset
            success_msg = "Configuration reset to defaults successfully!"
            logging.info(success_msg)
            self.main_controller.log_message(success_msg, 'green')
            # Play success sound
            if hasattr(self.main_controller, '_audio_alert'):
                self.main_controller._audio_alert('finish')
            
            # Log summary of reset
            if settings_to_reset:
                summary_msg = f"\nReset Summary: {len(settings_to_reset)} settings restored to defaults"
                logging.info(summary_msg)
                self.main_controller.log_message(summary_msg, 'green')
                
                # Show key settings that were reset
                key_settings = [s['key'] for s in settings_to_reset if s['key'] in [
                    'AI_PROVIDER', 'DEFAULT_MODEL_TYPE', 'APPIUM_SERVER_URL', 
                    'TARGET_DEVICE_UDID', 'APP_PACKAGE', 'CRAWL_MODE',
                    'MAX_CRAWL_STEPS', 'ENABLE_IMAGE_CONTEXT', 'ENABLE_MOBSF_ANALYSIS'
                ]]
                if key_settings:
                    key_msg = f"Key settings reset: {', '.join(key_settings)}"
                    logging.info(key_msg)
                    self.main_controller.log_message(key_msg, 'green')
            
            self.main_controller.log_message("Also reset: Focus Areas, Crawler Actions, Crawler Prompts, Allowed Packages", 'green')
            
        except Exception as exc:
            error_msg = f"Failed to reset configuration: {exc}"
            logging.exception(error_msg)
            self.main_controller.log_message(error_msg, 'red')
            QMessageBox.critical(
                parent_widget, 
                "Reset Failed", 
                f"Could not reset configuration:\n{exc}\n\nCheck the log output for details."
            )

    def _get_widget_value(self, key: str, widget: QWidget) -> Any:
        """Extracts the value from a given widget."""
        # Handle AllowedPackagesWidget
        try:
            from ui.allowed_packages_widget import AllowedPackagesWidget
            if isinstance(widget, AllowedPackagesWidget):
                return widget.get_packages()
        except ImportError:
            pass
        
        if isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QLabel):
            # QLabel widgets are read-only (display-only), don't save them
            return None
        elif isinstance(widget, QSpinBox):
            return widget.value()
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        elif isinstance(widget, QTextEdit):
            text = widget.toPlainText()
            if key == 'ALLOWED_EXTERNAL_PACKAGES':
                return [line.strip() for line in text.split('\n') if line.strip()]
            elif key == 'CRAWLER_AVAILABLE_ACTIONS':
                # Actions are now managed via service, not config
                # This widget is display-only, return None to skip saving
                return None
            else:
                return text
        return None
    
    def load_config(self):
        """Load configuration from the SQLite user config store."""
        # Load service-managed data first
        self._load_actions_from_service()
        self._load_prompts_from_service()
        
        # Try to load all config keys from Config (which uses SQLite and env)
        loaded_any = False
        for key, widget in self.main_controller.config_widgets.items():
            if key in ['IMAGE_CONTEXT_WARNING', 'ALLOWED_EXTERNAL_PACKAGES_WIDGET']:
                continue
            # Skip service-managed keys - they're loaded separately
            if key in ['CRAWLER_AVAILABLE_ACTIONS', 'CRAWLER_ACTION_DECISION_PROMPT']:
                continue
            # For checkboxes, we need to handle False values explicitly
            # because config.get(key, None) returns None if key doesn't exist,
            # but we want to load False values too
            if isinstance(widget, QCheckBox):
                value = self.config.get(key, False)  # Default to False for checkboxes
                if value is not None:
                    loaded_any = True
                    try:
                        # Block signals to prevent triggering save during load
                        widget.blockSignals(True)
                        widget.setChecked(bool(value))
                        widget.blockSignals(False)
                        if key == 'ENABLE_MOBSF_ANALYSIS':
                            logging.debug(f"Set ENABLE_MOBSF_ANALYSIS checkbox to: {bool(value)}")
                        elif key == 'OPENROUTER_SHOW_FREE_ONLY':
                            logging.debug(f"Set OPENROUTER_SHOW_FREE_ONLY checkbox to: {bool(value)}")
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Error loading config for '{key}': {e}")
                continue
            
            value = self.config.get(key, None)
            if value is not None:
                loaded_any = True
                try:
                    # Handle AllowedPackagesWidget
                    try:
                        from ui.allowed_packages_widget import AllowedPackagesWidget
                        if isinstance(widget, AllowedPackagesWidget):
                            if isinstance(value, list):
                                # Clean corrupted entries before setting
                                cleaned = [v for v in value if isinstance(v, str) and not (v.strip().startswith('[') or v.strip().startswith('{'))]
                                if cleaned != value:
                                    logging.warning(f"Cleaned corrupted packages data: removed {len(value) - len(cleaned)} items")
                                widget.set_packages(cleaned if cleaned else value)
                            continue
                    except ImportError:
                        pass
                    
                    if isinstance(widget, QLineEdit):
                        widget.setText(str(value))
                    elif isinstance(widget, QLabel):
                        widget.setText(str(value))
                    elif isinstance(widget, QSpinBox):
                        if isinstance(value, (list, dict)):
                            logging.warning(f"Skipping non-numeric value for spinbox '{key}': {value}")
                            continue
                        widget.setValue(int(value))
                    elif isinstance(widget, QComboBox):
                        if key == 'DEFAULT_MODEL_TYPE':
                            # Handle None/empty model selection - set to "No model selected"
                            if not value or (isinstance(value, str) and value.strip() == ''):
                                from ui.strings import NO_MODEL_SELECTED
                                index = widget.findText(NO_MODEL_SELECTED)
                                if index >= 0:
                                    widget.setCurrentIndex(index)
                            elif isinstance(value, str):
                                index = widget.findText(value)
                                if index >= 0:
                                    widget.setCurrentIndex(index)
                        elif isinstance(value, str):
                            index = widget.findText(value)
                            if index >= 0:
                                widget.setCurrentIndex(index)
                                # Note: _update_model_types is called at the end of load_config
                                # after all widgets (including OPENROUTER_SHOW_FREE_ONLY) are loaded
                                # to avoid race conditions
                    elif isinstance(widget, QTextEdit):
                        if isinstance(value, list):
                            widget.setPlainText('\n'.join(value))
                        elif isinstance(value, dict):
                            # For dict values (like CRAWLER_AVAILABLE_ACTIONS), format as JSON
                            widget.setPlainText(json.dumps(value, indent=2))
                        else:
                            widget.setPlainText(str(value))
                except (ValueError, TypeError) as e:
                    logging.warning(f"Error loading config for '{key}': {e}")
        # Load special keys not tied to widgets
        current_health_file = self.config.get('CURRENT_HEALTH_APP_LIST_FILE', None)
        if current_health_file:
            self.main_controller.current_health_app_list_file = current_health_file
        last_selected_app = self.config.get('LAST_SELECTED_APP', None)
        if last_selected_app is not None:
            self.main_controller.last_selected_app = last_selected_app or {}
        # UI_MODE
        ui_mode = self.config.get(UI_MODE_CONFIG_KEY, None)
        if ui_mode and hasattr(self, 'ui_mode_dropdown'):
            index = self.ui_mode_dropdown.findText(ui_mode)
            if index >= 0:
                self.ui_mode_dropdown.setCurrentIndex(index)
                # UI complexity will be handled by UIStateHandler in CrawlerControllerWindow
                if hasattr(self.main_controller, 'ui_state_handler'):
                    self.main_controller.ui_state_handler.toggle_ui_complexity(ui_mode)
        # AI_PROVIDER
        ai_provider = self.config.get('AI_PROVIDER', None)
        if ai_provider:
            # Model types will be updated by UIStateHandler
            if hasattr(self.main_controller, 'ui_state_handler'):
                self.main_controller.ui_state_handler._update_model_types(ai_provider)
            # After updating model types, ensure model dropdown shows correct selection
            model_type = self.config.get('DEFAULT_MODEL_TYPE', None)
            model_dropdown = self.main_controller.config_widgets.get('DEFAULT_MODEL_TYPE')
            if model_dropdown:
                if not model_type or (isinstance(model_type, str) and model_type.strip() == ''):
                    from ui.strings import NO_MODEL_SELECTED
                    index = model_dropdown.findText(NO_MODEL_SELECTED)
                    if index >= 0:
                        model_dropdown.setCurrentIndex(index)
                elif isinstance(model_type, str):
                    index = model_dropdown.findText(model_type)
                    if index >= 0:
                        model_dropdown.setCurrentIndex(index)
        self._update_crawl_mode_inputs_state()
        
        # Update image preprocessing visibility based on ENABLE_IMAGE_CONTEXT state
        if 'ENABLE_IMAGE_CONTEXT' in self.main_controller.config_widgets:
            enable_image_context = self.config.get('ENABLE_IMAGE_CONTEXT', False)
            self._update_image_preprocessing_visibility(bool(enable_image_context))
        
        if loaded_any:
            self.main_controller.log_message("Configuration loaded from SQLite successfully.", 'green')
        else:
            self._load_defaults_from_config()
    
    @Slot(int)
    def _on_mobsf_enabled_state_changed(self, state: int):
        """Handle the MobSF enabled checkbox state change."""
        try:
            is_enabled = bool(state)
            logging.debug(f"MobSF enabled state changed: {is_enabled}")
            
            # Update visibility and enabled state of API URL field and label
            if 'MOBSF_API_URL' in self.main_controller.config_widgets:
                self.main_controller.config_widgets['MOBSF_API_URL'].setVisible(is_enabled)
            if 'MOBSF_API_URL_LABEL' in self.main_controller.config_widgets:
                self.main_controller.config_widgets['MOBSF_API_URL_LABEL'].setVisible(is_enabled)
            
            # Note: MobSF API Key is now in API Keys group and should always be visible
            # (not controlled by MobSF enable checkbox)
                
            # Save the state to config immediately
            if hasattr(self.config, 'ENABLE_MOBSF_ANALYSIS'):
                self.config.ENABLE_MOBSF_ANALYSIS = is_enabled
                self.config.update_setting_and_save('ENABLE_MOBSF_ANALYSIS', is_enabled, self.main_controller._sync_user_config_files)
                
                # Synchronize the changes to the API config file
                # Note: Synchronization is now handled automatically by the callback in update_setting_and_save
                
                self.main_controller.log_message(f"MobSF analysis {'enabled' if is_enabled else 'disabled'}.", 'blue')
        except Exception as e:
            logging.error(f"Error handling MobSF enabled state change: {e}", exc_info=True)
            
    @Slot(int)
    def _on_health_app_selected(self, index: int):
        """Handle selection of an app from the dropdown."""
        try:
            if not self.main_controller.health_app_dropdown:
                return
                
            selected_data = self.main_controller.health_app_dropdown.itemData(index)
            if selected_data and isinstance(selected_data, dict):
                package_name = selected_data.get('package_name', '')
                activity_name = selected_data.get('activity_name', '')
                
                # Update widgets if they exist
                if 'APP_PACKAGE' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_PACKAGE'].setText(package_name)
                if 'APP_ACTIVITY' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_ACTIVITY'].setText(activity_name)
                
                # Directly save APP_PACKAGE and APP_ACTIVITY to config
                # This ensures they are saved even if widgets don't exist
                self.config.set('APP_PACKAGE', package_name)
                self.config.set('APP_ACTIVITY', activity_name)
                
                # Save the selected app information to config (includes LAST_SELECTED_APP)
                self.save_config()
            else:
                # Clear the selection
                if 'APP_PACKAGE' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_PACKAGE'].setText("")
                if 'APP_ACTIVITY' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_ACTIVITY'].setText("")
                
                # Clear from config as well
                self.config.set('APP_PACKAGE', None)
                self.config.set('APP_ACTIVITY', None)
                
                # Save the cleared state
                self.save_config()
        except Exception as e:
            logging.error(f"Error handling health app selection: {e}")
    
    def connect_widgets_for_auto_save(self):
        """Connect all config widgets to auto-save on change."""
        for key, widget in self.main_controller.config_widgets.items():
            # Skip UI indicator widgets that aren't actual config settings
            if key in ['IMAGE_CONTEXT_WARNING', 'ALLOWED_EXTERNAL_PACKAGES_WIDGET']:
                continue
            
            # Skip AllowedPackagesWidget - it has its own signal-based save mechanism
            try:
                from ui.allowed_packages_widget import AllowedPackagesWidget
                if isinstance(widget, AllowedPackagesWidget):
                    # Connect the widget's packages_changed signal to save
                    widget.packages_changed.connect(lambda packages: self.save_config(key='ALLOWED_EXTERNAL_PACKAGES'))
                    continue
            except ImportError:
                pass
                
            # Create a lambda that captures the current key
            save_lambda = lambda *args, k=key: self.save_config(key=k)
            
            if isinstance(widget, QLineEdit):
                widget.editingFinished.connect(save_lambda)
            elif isinstance(widget, QSpinBox):
                widget.editingFinished.connect(save_lambda)
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(save_lambda)
                # If the health-only AI filter checkbox changes, trigger a rescan automatically
                if key == 'USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY':
                    try:
                        if hasattr(self.main_controller, 'health_app_scanner') and self.main_controller.health_app_scanner:
                            # Cache-first behavior: on toggle, try to use cached file first, otherwise rescan
                            widget.stateChanged.connect(lambda *args: self.main_controller.health_app_scanner.on_filter_toggle_state_changed())
                            logging.debug("Connected USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY checkbox to cache-first load-or-scan.")
                    except Exception as e:
                        logging.warning(f"Could not connect AI filter checkbox to rescan: {e}")
                # If Enable Image Context checkbox changes, update visibility of preprocessing options
                elif key == 'ENABLE_IMAGE_CONTEXT':
                    def update_preprocessing_visibility(state: int):
                        enabled = bool(state)
                        self._update_image_preprocessing_visibility(enabled)
                    widget.stateChanged.connect(update_preprocessing_visibility)
                    logging.debug("Connected ENABLE_IMAGE_CONTEXT checkbox to update preprocessing visibility.")
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(save_lambda)
            elif isinstance(widget, QTextEdit):
                # Handle prompt fields specially - they use the prompts service
                if key == 'CRAWLER_ACTION_DECISION_PROMPT':
                    # Save to SQLite via prompts service with debounce (save 1 second after user stops typing)
                    # Double-check widget type before connecting
                    if isinstance(widget, QTextEdit):
                        def on_text_changed():
                            self._debounce_prompt_save(key, 'ACTION_DECISION_PROMPT', widget)
                        widget.textChanged.connect(on_text_changed)
                    else:
                        logging.warning(f"Widget for key '{key}' is not a QTextEdit, skipping prompt auto-save connection")
                else:
                    # Other QTextEdit widgets - omit auto-save to avoid excessive saving
                    pass
        logging.debug("Connected widgets for auto-saving.")
    
    def _update_image_preprocessing_visibility(self, enabled: bool):
        """
        Update visibility of image preprocessing options based on Enable Image Context state.
        
        Args:
            enabled: Whether image context is enabled
        """
        try:
            # Delegate to UIStateHandler if available
            if hasattr(self.main_controller, 'ui_state_handler'):
                self.main_controller.ui_state_handler._update_image_preprocessing_visibility(enabled)
            else:
                logging.warning("UIStateHandler not available for updating image preprocessing visibility")
        except Exception as e:
            logging.error(f"Error updating image preprocessing visibility: {e}", exc_info=True)
    
    def _get_actions_service(self):
        """Get CrawlerActionsService instance."""
        try:
            from cli.services.crawler_actions_service import CrawlerActionsService
            from cli.shared.context import ApplicationContext
            context = ApplicationContext(config=self.config)
            return CrawlerActionsService(context)
        except Exception as e:
            logging.error(f"Failed to get actions service: {e}")
            return None
    
    def _get_prompts_service(self):
        """Get CrawlerPromptsService instance."""
        try:
            from cli.services.crawler_prompts_service import CrawlerPromptsService
            from cli.shared.context import ApplicationContext
            context = ApplicationContext(config=self.config)
            return CrawlerPromptsService(context)
        except Exception as e:
            logging.error(f"Failed to get prompts service: {e}")
            return None
    
    def _debounce_prompt_save(self, widget_key: str, prompt_name: str, widget: QTextEdit):
        """Debounce prompt saving - wait 1 second after user stops typing before saving.
        
        Args:
            widget_key: Widget key in config_widgets
            prompt_name: Prompt name for database
            widget: The QTextEdit widget
        """
        # Validate widget type
        if not isinstance(widget, QTextEdit):
            logging.warning(f"Widget for key '{widget_key}' is not a QTextEdit (got {type(widget).__name__}), skipping prompt save")
            return
        
        # Cancel existing timer if any
        if widget_key in self._prompt_save_timers:
            self._prompt_save_timers[widget_key].stop()
        
        # Create new timer
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._save_prompt_from_ui(prompt_name, widget.toPlainText()))
        timer.start(1000)  # 1 second delay
        
        # Store timer for cancellation
        self._prompt_save_timers[widget_key] = timer
    
    def _save_prompt_from_ui(self, prompt_name: str, template: str):
        """Save a prompt from UI to SQLite via service.
        
        Args:
            prompt_name: Prompt name (e.g., "ACTION_DECISION_PROMPT")
            template: Prompt template text
        """
        prompts_service = self._get_prompts_service()
        if not prompts_service:
            logging.error("Prompts service not available, cannot save prompt")
            return
        
        try:
            # Check if prompt exists
            existing_prompt = prompts_service.get_prompt_by_name(prompt_name)
            
            if existing_prompt:
                # Update existing prompt
                success, message = prompts_service.edit_prompt(
                    prompt_name,
                    template=template
                )
                if success:
                    logging.debug(f"Updated prompt '{prompt_name}' from UI")
                else:
                    logging.error(f"Failed to update prompt '{prompt_name}': {message}")
                    self.main_controller.log_message(
                        f"Failed to save prompt '{prompt_name}': {message}", "orange"
                    )
            else:
                # Add new prompt
                success, message = prompts_service.add_prompt(
                    prompt_name,
                    template
                )
                if success:
                    logging.debug(f"Added prompt '{prompt_name}' from UI")
                else:
                    logging.error(f"Failed to add prompt '{prompt_name}': {message}")
                    self.main_controller.log_message(
                        f"Failed to save prompt '{prompt_name}': {message}", "orange"
                    )
        except Exception as e:
            logging.error(f"Error saving prompt '{prompt_name}' from UI: {e}")
            self.main_controller.log_message(
                f"Error saving prompt '{prompt_name}': {e}", "red"
            )
    
    def _load_actions_from_service(self):
        """Load actions from service and display in widget."""
        if 'CRAWLER_AVAILABLE_ACTIONS' not in self.main_controller.config_widgets:
            return
        
        widget = self.main_controller.config_widgets['CRAWLER_AVAILABLE_ACTIONS']
        
        # Check if it's the new AvailableActionsWidget
        from ui.available_actions_widget import AvailableActionsWidget
        if isinstance(widget, AvailableActionsWidget):
            service = self._get_actions_service()
            if not service:
                # Fall back to config property - convert to list format
                actions_dict = self.config.CRAWLER_AVAILABLE_ACTIONS
                if actions_dict:
                    # Convert dict to list format for widget
                    actions_list = [
                        {'name': name, 'description': desc, 'enabled': True, 'id': None}
                        for name, desc in actions_dict.items()
                    ]
                    widget.load_actions(actions_list, actions_service=service)
                return
            
            try:
                # Always load from database - actions should be initialized on first launch
                actions = service.get_actions()
                
                if actions:
                    widget.load_actions(actions, actions_service=service)
                else:
                    # Database is empty - this shouldn't happen after initialization
                    # Log error but don't crash - widget will show empty list
                    logging.error(
                        "No actions found in database. Actions should have been initialized on first launch. "
                        "Please restart the application to trigger initialization."
                    )
            except Exception as e:
                logging.error(f"Failed to load actions from service: {e}")
                # Don't fall back to config defaults - actions should be in database
                # Widget will show empty list if database is corrupted
            return
        
        # Legacy support for QTextEdit (should not be needed after migration)
        if isinstance(widget, QTextEdit):
            service = self._get_actions_service()
            if not service:
                # Fall back to config property
                actions_dict = self.config.CRAWLER_AVAILABLE_ACTIONS
                if actions_dict:
                    widget.setPlainText(json.dumps(actions_dict, indent=2))
                return
            
            try:
                actions = service.get_actions()
                if actions:
                    # Convert to dict format
                    actions_dict = {action['name']: action['description'] for action in actions}
                    widget.setPlainText(json.dumps(actions_dict, indent=2))
                else:
                    # Fall back to config defaults
                    actions_dict = self.config.CRAWLER_AVAILABLE_ACTIONS
                    if actions_dict:
                        widget.setPlainText(json.dumps(actions_dict, indent=2))
            except Exception as e:
                logging.error(f"Failed to load actions from service: {e}")
                # Fall back to config
                actions_dict = self.config.CRAWLER_AVAILABLE_ACTIONS
                if actions_dict:
                    widget.setPlainText(json.dumps(actions_dict, indent=2))
    
    def _extract_editable_prompt_part(self, full_prompt: str) -> str:
        """Extract the editable part from a prompt that may contain the fixed part.
        
        If the prompt contains the fixed part (schema/actions), extract only the custom part.
        This handles migration from old prompts that stored the full text.
        
        Args:
            full_prompt: The prompt text (may be full or just editable part)
        
        Returns:
            The editable part only
        """
        if not full_prompt:
            return full_prompt
        
        # Check if prompt contains the fixed part markers
        fixed_markers = [
            "Use the following JSON schema",
            "{json_schema}",
            "Available actions:",
            "{action_list}"
        ]
        
        # If any fixed marker is found, extract the editable part
        for marker in fixed_markers:
            if marker in full_prompt:
                # Find where the fixed part starts
                # The fixed part typically starts with "Use the following JSON schema"
                fixed_start = full_prompt.find("Use the following JSON schema")
                if fixed_start > 0:
                    # Extract everything before the fixed part
                    editable_part = full_prompt[:fixed_start].strip()
                    # If we extracted something, return it (and migrate it)
                    if editable_part:
                        logging.info("Migrating prompt: extracting editable part from full prompt")
                        return editable_part
                break
        
        # If no fixed markers found, assume it's already just the editable part
        return full_prompt
    
    def _load_prompts_from_service(self):
        """Load prompts from SQLite (single source of truth) and display in widgets."""
        prompts_service = self._get_prompts_service()
        if not prompts_service:
            # If service unavailable, try reading directly from config (which reads from SQLite)
            try:
                if 'CRAWLER_ACTION_DECISION_PROMPT' in self.main_controller.config_widgets:
                    widget = self.main_controller.config_widgets['CRAWLER_ACTION_DECISION_PROMPT']
                    if isinstance(widget, QTextEdit):
                        prompt_text = self.config.CRAWLER_ACTION_DECISION_PROMPT
                        if prompt_text:
                            # Extract editable part if needed (migration)
                            editable_part = self._extract_editable_prompt_part(prompt_text)
                            widget.setPlainText(editable_part)
                            # If migration happened, save the extracted part
                            if editable_part != prompt_text:
                                self._save_prompt_from_ui('ACTION_DECISION_PROMPT', editable_part)
                
            except Exception as e:
                logging.error(f"Failed to load prompts from config: {e}")
            return
        
        try:
            # Read from SQLite via service (single source of truth)
            prompts = prompts_service.get_prompts()
            prompts_by_name = {p['name']: p['template'] for p in prompts}
            
            # Load ACTION_DECISION_PROMPT
            if 'CRAWLER_ACTION_DECISION_PROMPT' in self.main_controller.config_widgets:
                widget = self.main_controller.config_widgets['CRAWLER_ACTION_DECISION_PROMPT']
                if isinstance(widget, QTextEdit):
                    prompt_text = prompts_by_name.get('ACTION_DECISION_PROMPT')
                    if prompt_text:
                        # Extract editable part if needed (migration)
                        editable_part = self._extract_editable_prompt_part(prompt_text)
                        widget.setPlainText(editable_part)
                        # If migration happened, save the extracted part back to database
                        if editable_part != prompt_text:
                            logging.info("Migrating ACTION_DECISION_PROMPT: removing fixed part")
                            self._save_prompt_from_ui('ACTION_DECISION_PROMPT', editable_part)
        except Exception as e:
            logging.error(f"Failed to load prompts from service: {e}")
    