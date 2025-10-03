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

# Import UIComponents 
from .components import UIComponents


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
        
        # Use the USER_CONFIG_FILE_PATH from the config object which should be set to the root config file
        self.config_file_path = self.config.USER_CONFIG_FILE_PATH
        logging.debug(f"ConfigManager initialized with config file path: {self.config_file_path}")
    
    def _apply_defaults_from_config_to_widgets(self):
        """Apply default values from the config module to UI widgets."""
        for key, widget in self.main_controller.config_widgets.items():
            # Skip UI indicator widgets that aren't actual config settings
            if key in ['IMAGE_CONTEXT_WARNING']:
                continue
                
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
            # Skip UI indicator widgets that aren't actual config settings
            if key in ['IMAGE_CONTEXT_WARNING']:
                continue
                
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
    def save_config(self, key: Optional[str] = None):
        """
        Save the current configuration to the user config file.
        If a key is provided, only that key's widget value is saved.
        Otherwise, all widget values are saved.
        """
        config_data = {}

        if key and key in self.main_controller.config_widgets:
            # Save only the specific key that triggered the change
            widget = self.main_controller.config_widgets[key]
            config_data[key] = self._get_widget_value(key, widget)
        else:
            # Fallback to saving all widgets if no key is provided
            for k, widget in self.main_controller.config_widgets.items():
                # Skip UI indicator widgets that aren't actual config settings
                if k in ['IMAGE_CONTEXT_WARNING']:
                    continue
                config_data[k] = self._get_widget_value(k, widget)

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
        
        # Update the config object with the new data
        for k, value in config_data.items():
            self.config.update_setting_and_save(k, value, self.main_controller._sync_user_config_files)

        # Synchronize the changes to the API config file
        # Note: Synchronization is now handled automatically by the callback in update_setting_and_save

        self.main_controller.log_message("Configuration auto-saved successfully.", 'green')

    def _get_widget_value(self, key: str, widget: QWidget) -> Any:
        """Extracts the value from a given widget."""
        if isinstance(widget, QLineEdit):
            return widget.text()
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
            else:
                return text
        return None
    
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
                logging.debug(f"Loading ENABLE_MOBSF_ANALYSIS state: {self.user_config['ENABLE_MOBSF_ANALYSIS']}")
            
            if 'UI_MODE' in self.user_config:
                logging.debug(f"Loading UI_MODE from user_config.json: {self.user_config['UI_MODE']}")
                # Update the config object with UI_MODE
                if hasattr(self.config, 'UI_MODE'):
                    self.config.UI_MODE = self.user_config['UI_MODE']


            
            for key, value in self.user_config.items():
                if key in self.main_controller.config_widgets:
                    # Skip UI indicator widgets that aren't actual config settings
                    if key in ['IMAGE_CONTEXT_WARNING']:
                        continue
                        
                    widget = self.main_controller.config_widgets[key]
                    try:
                        if isinstance(widget, QLineEdit):
                            widget.setText(str(value))
                        elif isinstance(widget, QSpinBox):
                            widget.setValue(int(value))
                        elif isinstance(widget, QCheckBox):
                            widget.setChecked(bool(value))
                            if key == 'ENABLE_MOBSF_ANALYSIS':
                                logging.debug(f"Set ENABLE_MOBSF_ANALYSIS checkbox to: {bool(value)}")
                        elif isinstance(widget, QComboBox):
                            if isinstance(value, str):
                                index = widget.findText(value)
                                if index >= 0:
                                    widget.setCurrentIndex(index)
                                    # If this is the AI_PROVIDER combobox, update the model types
                                    if key == 'AI_PROVIDER':
                                        UIComponents._update_model_types(value, self.main_controller.config_widgets)
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
                    # Ensure it's a dictionary, not None
                    if value is None:
                        self.main_controller.last_selected_app = {}
                    else:
                        self.main_controller.last_selected_app = value
            
            # Apply specific config settings that aren't directly tied to widgets
            if 'UI_MODE' in self.user_config and hasattr(self, 'ui_mode_dropdown'):
                mode = self.user_config['UI_MODE']
                logging.debug(f"Setting ui_mode_dropdown to {mode} based on user_config")
                index = self.ui_mode_dropdown.findText(mode)
                if index >= 0:
                    self.ui_mode_dropdown.setCurrentIndex(index)
                    # Call toggle_ui_complexity directly to ensure UI is updated
                    UIComponents.toggle_ui_complexity(mode, self)
            
            # Update model types based on loaded AI_PROVIDER
            if 'AI_PROVIDER' in self.user_config:
                provider = self.user_config['AI_PROVIDER']
                logging.debug(f"Updating model types for loaded AI_PROVIDER: {provider}")
                UIComponents._update_model_types(provider, self.main_controller.config_widgets)
            
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
            logging.debug(f"MobSF enabled state changed: {is_enabled}")
            
            # Update button states - checking both hasattr and that the button is not None
            if hasattr(self.main_controller, 'run_mobsf_analysis_btn') and self.main_controller.run_mobsf_analysis_btn is not None:
                self.main_controller.run_mobsf_analysis_btn.setEnabled(is_enabled)
                logging.debug(f"Set run_mobsf_analysis_btn enabled: {is_enabled}")
            else:
                logging.warning("run_mobsf_analysis_btn is not available")
                
            if hasattr(self.main_controller, 'test_mobsf_conn_btn') and self.main_controller.test_mobsf_conn_btn is not None:
                self.main_controller.test_mobsf_conn_btn.setEnabled(is_enabled)
                logging.debug(f"Set test_mobsf_conn_btn enabled: {is_enabled}")
            else:
                logging.warning("test_mobsf_conn_btn is not available")
                
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
                if 'APP_PACKAGE' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_PACKAGE'].setText(package_name)
                if 'APP_ACTIVITY' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_ACTIVITY'].setText(activity_name)
                self.main_controller.log_message(f"Selected app: {selected_data.get('app_name', '')}", 'blue')
                
                # Save the selected app information to config
                self.save_config()
            else:
                if 'APP_PACKAGE' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_PACKAGE'].setText("")
                if 'APP_ACTIVITY' in self.main_controller.config_widgets:
                    self.main_controller.config_widgets['APP_ACTIVITY'].setText("")
        except Exception as e:
            logging.error(f"Error handling health app selection: {e}")
    
    def connect_widgets_for_auto_save(self):
        """Connect all config widgets to auto-save on change."""
        for key, widget in self.main_controller.config_widgets.items():
            # Skip UI indicator widgets that aren't actual config settings
            if key in ['IMAGE_CONTEXT_WARNING']:
                continue
                
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
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(save_lambda)
            elif isinstance(widget, QTextEdit):
                # QTextEdit doesn't have a simple 'editingFinished' signal.
                # We can connect to textChanged, but it fires on every keystroke.
                # A better approach is to handle it when the widget loses focus,
                # but that requires event filtering. For now, we'll omit auto-save
                # on QTextEdit to avoid excessive saving.
                pass
        logging.debug("Connected widgets for auto-saving.")
    
    def update_focus_areas(self, focus_areas):
        """Update focus areas configuration and save to user config."""
        # Convert FocusArea objects to dictionaries for JSON serialization
        focus_areas_dict = []
        for area in focus_areas:
            if hasattr(area, '__dict__'):
                # It's a FocusArea object
                focus_areas_dict.append({
                    'id': area.id,
                    'name': area.name,
                    'description': area.description,
                    'prompt_modifier': area.prompt_modifier,
                    'enabled': bool(area.enabled),
                    'priority': int(area.priority)
                })
            else:
                # It's already a dict
                focus_areas_dict.append(area)

        # Basic schema validation and unique ID enforcement
        errors = []
        seen_ids = set()
        validated_dicts = []
        for idx, area in enumerate(focus_areas_dict):
            try:
                aid = str(area.get('id', '')).strip()
                name = str(area.get('name', '')).strip()
                desc = str(area.get('description', ''))
                prompt = str(area.get('prompt_modifier', ''))
                enabled = bool(area.get('enabled', True))
                # priority may be string; coerce to int
                try:
                    priority = int(area.get('priority', 0))
                except (TypeError, ValueError):
                    priority = 0

                if not aid:
                    errors.append(f"Focus area at index {idx} missing non-empty 'id'")
                    continue
                if aid in seen_ids:
                    errors.append(f"Duplicate focus area id detected: '{aid}'")
                    continue
                if not name:
                    errors.append(f"Focus area '{aid}' has empty 'name'")
                    continue
                # Limit overly long prompt modifiers to avoid excessive prompt size
                if len(prompt) > 1000:
                    errors.append(f"Focus area '{aid}' prompt_modifier too long ({len(prompt)} > 1000)")
                    continue

                seen_ids.add(aid)
                validated_dicts.append({
                    'id': aid,
                    'name': name,
                    'description': desc,
                    'prompt_modifier': prompt,
                    'enabled': enabled,
                    'priority': priority
                })
            except Exception as e:
                errors.append(f"Error validating focus area at index {idx}: {e}")

        if errors:
            # Do not save invalid configuration; inform the user
            err_text = "; ".join(errors)
            logging.warning(f"Focus areas validation failed: {err_text}")
            try:
                self.main_controller.log_message(f"Focus areas not saved due to validation errors: {err_text}", 'red')
            except Exception:
                pass
            return

        # Update the config object
        self.config.FOCUS_AREAS = validated_dicts

        # Save to user config
        self.config.update_setting_and_save('FOCUS_AREAS', validated_dicts, self.main_controller._sync_user_config_files)

        logging.debug(f"Updated focus areas configuration with {len(validated_dicts)} areas")
