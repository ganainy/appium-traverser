#!/usr/bin/env python3
# ui/config_manager.py - Configuration management for the UI controller

import json
import logging
import os



from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QWidget,
)

# Import UIComponents 
from ui.ui_components import UIComponents


class ConfigManager(QObject):
    """Manages configuration for the Appium Crawler Controller UI."""
    
    # These attributes are dynamically added by UIComponents class
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
        """
        config_data = {}

        if key and key in self.main_controller.config_widgets:
            # Skip service-managed keys - they're handled separately
            if key in ['CRAWLER_AVAILABLE_ACTIONS', 'CRAWLER_ACTION_DECISION_PROMPT', 'CRAWLER_SYSTEM_PROMPT_TEMPLATE']:
                return  # These are managed via services, not config
            
            # Save only the specific key that triggered the change
            widget = self.main_controller.config_widgets[key]
            value = self._get_widget_value(key, widget)
            if value is not None:  # Skip None values (e.g., read-only QLabel widgets)
                config_data[key] = value
        else:
            # Fallback to saving all widgets if no key is provided
            for k, widget in self.main_controller.config_widgets.items():
                # Skip UI indicator widgets that aren't actual config settings
                if k in ['IMAGE_CONTEXT_WARNING']:
                    continue
                # Skip service-managed keys - they're handled separately
                if k in ['CRAWLER_AVAILABLE_ACTIONS', 'CRAWLER_ACTION_DECISION_PROMPT', 'CRAWLER_SYSTEM_PROMPT_TEMPLATE']:
                    continue
                value = self._get_widget_value(k, widget)
                if value is not None:  # Skip None values (e.g., read-only QLabel widgets)
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
        
        # Update the config object and persist to SQLite
        for k, value in config_data.items():
            self.config.set(k, value)

        self.main_controller.log_message("Configuration auto-saved to SQLite successfully.", 'green')

    @Slot()
    def reset_settings(self) -> None:
        """Reset persisted configuration to defaults via Config service."""
        parent_widget = getattr(self.main_controller, 'window', self.main_controller)
        confirmation = QMessageBox.question(
            parent_widget,
            "Reset Settings",
            "Reset all configuration settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            self.config.reset_settings()
            self.load_config()
            if hasattr(self, 'focus_areas_widget') and self.focus_areas_widget:
                try:
                    self.focus_areas_widget.reload_focus_areas()
                except Exception:
                    logging.exception("Failed to reload focus areas after reset; clearing locally.")
                    self.focus_areas_widget.focus_areas = []
                    self.focus_areas_widget.create_focus_items()
            self.main_controller.log_message("Configuration reset to defaults.", 'green')
        except Exception as exc:
            logging.exception("Failed to reset configuration from UI.")
            QMessageBox.critical(parent_widget, "Reset Failed", f"Could not reset configuration:\n{exc}")

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
            if key in ['CRAWLER_AVAILABLE_ACTIONS', 'CRAWLER_ACTION_DECISION_PROMPT', 'CRAWLER_SYSTEM_PROMPT_TEMPLATE']:
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
                    elif isinstance(widget, QCheckBox):
                        widget.setChecked(bool(value))
                        if key == 'ENABLE_MOBSF_ANALYSIS':
                            logging.debug(f"Set ENABLE_MOBSF_ANALYSIS checkbox to: {bool(value)}")
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
                                if key == 'AI_PROVIDER':
                                    UIComponents._update_model_types(value, self.main_controller.config_widgets, self)
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
        ui_mode = self.config.get(UIComponents.UI_MODE_CONFIG_KEY, None)
        if ui_mode and hasattr(self, 'ui_mode_dropdown'):
            index = self.ui_mode_dropdown.findText(ui_mode)
            if index >= 0:
                self.ui_mode_dropdown.setCurrentIndex(index)
                UIComponents.toggle_ui_complexity(ui_mode, self)
        # AI_PROVIDER
        ai_provider = self.config.get('AI_PROVIDER', None)
        if ai_provider:
            UIComponents._update_model_types(ai_provider, self.main_controller.config_widgets, self)
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
        if loaded_any:
            self.main_controller.log_message("Configuration loaded from SQLite successfully.", 'green')
        else:
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
    
    def _load_prompts_from_service(self):
        """Load prompts from service and display in widgets."""
        prompts_service = self._get_prompts_service()
        if not prompts_service:
            return
        
        try:
            prompts = prompts_service.get_prompts()
            prompts_by_name = {p['name']: p['template'] for p in prompts}
            
            # Load ACTION_DECISION_PROMPT
            if 'CRAWLER_ACTION_DECISION_PROMPT' in self.main_controller.config_widgets:
                widget = self.main_controller.config_widgets['CRAWLER_ACTION_DECISION_PROMPT']
                if isinstance(widget, QTextEdit):
                    prompt_text = prompts_by_name.get('ACTION_DECISION_PROMPT') or self.config.CRAWLER_ACTION_DECISION_PROMPT
                    if prompt_text:
                        widget.setPlainText(prompt_text)
            
            # Load SYSTEM_PROMPT_TEMPLATE
            if 'CRAWLER_SYSTEM_PROMPT_TEMPLATE' in self.main_controller.config_widgets:
                widget = self.main_controller.config_widgets['CRAWLER_SYSTEM_PROMPT_TEMPLATE']
                if isinstance(widget, QTextEdit):
                    prompt_text = prompts_by_name.get('SYSTEM_PROMPT_TEMPLATE') or self.config.CRAWLER_SYSTEM_PROMPT_TEMPLATE
                    if prompt_text:
                        widget.setPlainText(prompt_text)
        except Exception as e:
            logging.error(f"Failed to load prompts from service: {e}")
    