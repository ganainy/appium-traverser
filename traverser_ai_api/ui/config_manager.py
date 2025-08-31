#!/usr/bin/env python3
# ui/config_manager.py - Configuration management for the UI controller

import os
import json
import logging
from typing import Dict, Any, Optional, List
from PySide6.QtWidgets import (
    QLineEdit, QSpinBox, QCheckBox, QComboBox, QTextEdit, 
    QPushButton, QLabel, QGroupBox, QWidget
)
from PySide6.QtCore import Slot
from PySide6.QtCore import QObject


class ConfigManager(QObject):
    """Manages configuration for the Appium Crawler Controller UI."""
    
    # These attributes are dynamically added by UIComponents class
    health_app_dropdown: QComboBox
    refresh_apps_btn: QPushButton
    app_scan_status_label: QLabel
    ui_mode_dropdown: QComboBox
    ui_groups: Dict[str, QGroupBox]
    scroll_content: QWidget
    
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
        self.user_config = {}
        self.config_file_path = os.path.join(config.BASE_DIR, "user_config.json")
    
    def _apply_defaults_from_config_to_widgets(self):
        """Apply default values from the config module to UI widgets."""
        for key, widget in self.main_controller.config_widgets.items():
            if not hasattr(self.config, key):
                logging.warning(f"Config key '{key}' not found in config module.")
                continue
                
            value = getattr(self.config, key)
            if value is None:
                logging.debug(f"Config key '{key}' has None value.")
                continue
                
            try:
                if isinstance(widget, QLineEdit):
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
                logging.warning(f"Error setting config widget for '{key}': {e}")
    
    def _load_defaults_from_config(self):
        """Load configuration values from config.py module."""
        missing_configs = []
        for key, widget in self.main_controller.config_widgets.items():
            if not hasattr(self.config, key):
                missing_configs.append(f"{key}: Not found in config module.")
                continue

            value = getattr(self.config, key)
            if value is None:
                missing_configs.append(f"{key}: Has None value in config module.")
                continue

            try:
                if isinstance(widget, QLineEdit):
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
    def save_config(self):
        """Save the current configuration to the user config file."""
        config_data = {}
        for key, widget in self.main_controller.config_widgets.items():
            if isinstance(widget, QLineEdit):
                config_data[key] = widget.text()
            elif isinstance(widget, QSpinBox):
                config_data[key] = widget.value()
            elif isinstance(widget, QCheckBox):
                config_data[key] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                config_data[key] = widget.currentText()
            elif isinstance(widget, QTextEdit):
                text = widget.toPlainText()
                if key == 'ALLOWED_EXTERNAL_PACKAGES':
                    config_data[key] = [line.strip() for line in text.split('\n') if line.strip()]
                else:
                    config_data[key] = text
        
        # Save UI mode setting
        if hasattr(self, 'ui_mode_dropdown'):
            config_data['UI_MODE'] = self.ui_mode_dropdown.currentText()
        
        # Save health app list path
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

        # Log important states for debugging
        if 'ENABLE_MOBSF_ANALYSIS' in config_data:
            logging.info(f"Saving ENABLE_MOBSF_ANALYSIS state: {config_data['ENABLE_MOBSF_ANALYSIS']}")

        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            
            # Update the config object
            for key, value in config_data.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            
            self.main_controller.log_message("Configuration saved successfully.", 'green')
        except Exception as e:
            self.main_controller.log_message(f"Error saving configuration: {e}", 'red')
    
    def load_config(self):
        """Load configuration from the user config file."""
        if not os.path.exists(self.config_file_path):
            self._load_defaults_from_config()
            return

        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                self.user_config = json.load(f)
            
            # Log important config values for debugging
            if 'ENABLE_MOBSF_ANALYSIS' in self.user_config:
                logging.info(f"Loading ENABLE_MOBSF_ANALYSIS state: {self.user_config['ENABLE_MOBSF_ANALYSIS']}")
            
            for key, value in self.user_config.items():
                if key in self.main_controller.config_widgets:
                    widget = self.main_controller.config_widgets[key]
                    try:
                        if isinstance(widget, QLineEdit):
                            widget.setText(str(value))
                        elif isinstance(widget, QSpinBox):
                            widget.setValue(int(value))
                        elif isinstance(widget, QCheckBox):
                            widget.setChecked(bool(value))
                            if key == 'ENABLE_MOBSF_ANALYSIS':
                                logging.info(f"Set ENABLE_MOBSF_ANALYSIS checkbox to: {bool(value)}")
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
                        logging.warning(f"Error loading config for '{key}': {e}")
                elif key == 'CURRENT_HEALTH_APP_LIST_FILE':
                    self.main_controller.current_health_app_list_file = value
                elif key == 'LAST_SELECTED_APP':
                    # Store for later use when populating health app dropdown
                    self.main_controller.last_selected_app = value
            
            # Apply specific config settings that aren't directly tied to widgets
            if 'UI_MODE' in self.user_config and hasattr(self, 'ui_mode_dropdown'):
                mode = self.user_config['UI_MODE']
                index = self.ui_mode_dropdown.findText(mode)
                if index >= 0:
                    self.ui_mode_dropdown.setCurrentIndex(index)
            
            self._update_crawl_mode_inputs_state()
            self.main_controller.log_message("Configuration loaded successfully.", 'green')
        except Exception as e:
            self.main_controller.log_message(f"Error loading configuration: {e}", 'red')
            self._load_defaults_from_config()
    
    @Slot(int)
    def _on_mobsf_enabled_state_changed(self, state: int):
        """Handle the MobSF enabled checkbox state change."""
        try:
            # Update the run_mobsf_analysis_btn and test_mobsf_conn_btn state
            is_enabled = bool(state)
            logging.info(f"MobSF enabled state changed: {is_enabled}")
            
            # Update button states - checking both hasattr and that the button is not None
            if hasattr(self.main_controller, 'run_mobsf_analysis_btn') and self.main_controller.run_mobsf_analysis_btn is not None:
                self.main_controller.run_mobsf_analysis_btn.setEnabled(is_enabled)
                logging.info(f"Set run_mobsf_analysis_btn enabled: {is_enabled}")
            else:
                logging.warning("run_mobsf_analysis_btn is not available")
                
            if hasattr(self.main_controller, 'test_mobsf_conn_btn') and self.main_controller.test_mobsf_conn_btn is not None:
                self.main_controller.test_mobsf_conn_btn.setEnabled(is_enabled)
                logging.info(f"Set test_mobsf_conn_btn enabled: {is_enabled}")
            else:
                logging.warning("test_mobsf_conn_btn is not available")
                
            # Save the state to config immediately
            if hasattr(self.config, 'ENABLE_MOBSF_ANALYSIS'):
                self.config.ENABLE_MOBSF_ANALYSIS = is_enabled
                self.config.update_setting_and_save('ENABLE_MOBSF_ANALYSIS', is_enabled)
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
                if 'APP_PACKAGE' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_PACKAGE'].setText(package_name)
                if 'APP_ACTIVITY' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_ACTIVITY'].setText(activity_name)
                self.main_controller.log_message(f"Selected app: {selected_data.get('app_name', '')}", 'blue')
            else:
                if 'APP_PACKAGE' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_PACKAGE'].setText("")
                if 'APP_ACTIVITY' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_ACTIVITY'].setText("")
        except Exception as e:
            logging.error(f"Error handling health app selection: {e}")
