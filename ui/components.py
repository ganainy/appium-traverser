# ui/components.py - UI components for the Appium Crawler Controller

import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.custom_widgets import NoScrollComboBox as QComboBox
from ui.custom_widgets import NoScrollSpinBox as QSpinBox


class UIComponents:
    """Factory class for creating UI components used in the Crawler Controller."""

    # UI Mode Constants
    UI_MODE_BASIC = "Basic"
    UI_MODE_EXPERT = "Expert"
    UI_MODE_DEFAULT = UI_MODE_BASIC
    UI_MODE_CONFIG_KEY = "UI_MODE"

    # Define which settings groups and fields are considered advanced
    # These will be hidden in basic mode
    ADVANCED_GROUPS = [
        "appium_settings_group",
        "error_handling_group",
        "focus_areas_group",  # Focus areas can be advanced for basic users
        "image_preprocessing_group",  # Image preprocessing controls are advanced
    ]

    @staticmethod
    def _update_model_types(provider: str, config_widgets: Dict[str, Any]) -> None:
        """Update the model types based on the selected AI provider."""
        model_dropdown = config_widgets["DEFAULT_MODEL_TYPE"]
        # Capture the current selection to restore it after repopulating
        previous_text = model_dropdown.currentText()

        # Block signals to prevent auto-save from triggering with an empty value
        model_dropdown.blockSignals(True)

        model_dropdown.clear()

        # Always start with an explicit no-selection placeholder
        NO_SELECTION_LABEL = "No model selected"
        try:
            model_dropdown.addItem(NO_SELECTION_LABEL)
        except Exception:
            # Fallback: ensure dropdown has at least one item
            model_dropdown.addItem("No model selected")

        # Get provider capabilities from config
        from config.config import AI_PROVIDER_CAPABILITIES

        capabilities = AI_PROVIDER_CAPABILITIES.get(
            provider.lower(), AI_PROVIDER_CAPABILITIES.get("gemini", {})
        )

        if provider.lower() == "gemini":
            # Populate Gemini models using direct model IDs; do not auto-select
            model_dropdown.addItems([
                "gemini-2.5-flash-preview-05-20",
                "gemini-2.5-flash-image",
            ])
            # Try to restore saved selection if present
            try:
                if previous_text:
                    idx = model_dropdown.findText(previous_text)
                    if idx >= 0:
                        model_dropdown.setCurrentIndex(idx)
            except Exception:
                pass
            # Enable image context for Gemini
            if "ENABLE_IMAGE_CONTEXT" in config_widgets:
                config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
                config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(
                    "Enable sending screenshots to AI for visual analysis. Disable for text-only analysis."
                )

                # Reset styling when enabling
                config_widgets["ENABLE_IMAGE_CONTEXT"].setStyleSheet("")

                # Hide warning label
                if "IMAGE_CONTEXT_WARNING" in config_widgets:
                    config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
        elif provider.lower() == "ollama":
            # Get available Ollama models dynamically
            try:
                import ollama

                available_models = ollama.list()
                model_items = []
                vision_models = []

                for model_info in available_models.get("models", []):
                    model_name = model_info.get("model", model_info.get("name", ""))
                    if not model_name:
                        continue

                    # Keep full model name with tag for display and API usage
                    display_name = model_name

                    # Extract base name for feature detection
                    base_name = model_name.split(":")[0]

                    # Check if this model supports vision by directly querying Ollama
                    # We'll try to get model metadata or tags that indicate vision support
                    vision_supported = False
                    try:
                        # Try to get model info to determine vision capabilities
                        # First attempt: check model tags or metadata
                        # For now, we'll still use name-based detection as a fallback
                        vision_supported = any(
                            pattern in base_name.lower()
                            for pattern in [
                                "vision",
                                "llava",
                                "bakllava",
                                "minicpm-v",
                                "moondream",
                                "gemma3",
                                "llama",
                                "qwen2.5vl",
                            ]
                        )
                        logging.debug(
                            f"Vision capability for {model_name}: {vision_supported}"
                        )
                    except Exception as e:
                        logging.debug(
                            f"Error checking vision capability for {model_name}: {e}"
                        )
                        # Fallback to name-based detection

                    # Use the original model name without adding suffixes
                    display_name = model_name
                    if vision_supported:
                        vision_models.append(display_name)

                    model_items.append(display_name)

                # If no models found, show a message
                if not model_items:
                    model_items = [
                        "No Ollama models available - run 'ollama pull <model>'"
                    ]
                    logging.warning("No Ollama models found")

                model_dropdown.addItems(model_items)

                # Try to restore saved selection if present among items
                try:
                    if previous_text:
                        idx = model_dropdown.findText(previous_text)
                        if idx >= 0:
                            model_dropdown.setCurrentIndex(idx)
                except Exception:
                    pass

                logging.debug(f"Loaded {len(model_items)} Ollama models: {model_items}")

            except ImportError:
                # Fallback if ollama package not installed
                model_dropdown.addItems(
                    ['Ollama not installed - run "pip install ollama"']
                )
                logging.warning("Ollama package not installed")
            except Exception as e:
                # Fallback if Ollama is not running or other error
                logging.warning(f"Could not fetch Ollama models: {e}")
                model_dropdown.addItems(
                    [
                        "Ollama not running - start Ollama service",
                        "llama3.2(local)",
                        "llama3.2-vision(local) 👁️",
                    ]
                )

            # Enable image context for Ollama (vision models will handle it)
            if "ENABLE_IMAGE_CONTEXT" in config_widgets:
                config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
                config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(
                    "Enable sending screenshots to AI for visual analysis. Vision-capable models will process images, others will use text-only."
                )

                # Reset styling when enabling
                config_widgets["ENABLE_IMAGE_CONTEXT"].setStyleSheet("")

                # Hide warning label
                if "IMAGE_CONTEXT_WARNING" in config_widgets:
                    config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
        elif provider.lower() == "openrouter":
            # Try to populate from cached OpenRouter models; fallback to presets
            cached_models = UIComponents._load_openrouter_models_from_cache()
            vision_models = []
            free_only = False
            try:
                if "OPENROUTER_SHOW_FREE_ONLY" in config_widgets:
                    free_only = bool(
                        config_widgets["OPENROUTER_SHOW_FREE_ONLY"].isChecked()
                    )
            except Exception:
                free_only = False
            if cached_models:
                try:
                    # Add dynamic models (id values), honoring free-only filter by model metadata
                    model_ids = []
                    total_models = len(cached_models)
                    free_candidates = 0
                    for m in cached_models:
                        mid = m.get("id") or m.get("name")
                        if not mid:
                            continue
                        if free_only:
                            if UIComponents._is_openrouter_model_free(m):
                                model_ids.append(mid)
                        else:
                            model_ids.append(mid)
                        try:
                            if UIComponents._is_openrouter_model_free(m):
                                free_candidates += 1
                        except Exception:
                            pass
                    # Consult cache-derived vision capability first; fallback to heuristics
                    for mid in model_ids:
                        if UIComponents._is_openrouter_model_vision(mid):
                            vision_models.append(mid)
                    model_dropdown.addItems(model_ids)
                    try:
                        logging.info(
                            f"OpenRouter models displayed: {len(model_ids)} (free-only={'on' if free_only else 'off'}; free-candidates={free_candidates}/{total_models})"
                        )
                    except Exception:
                        pass
                except Exception as e:
                    logging.warning(f"Error loading cached OpenRouter models: {e}")
                    model_dropdown.addItems(["openrouter-auto", "openrouter-auto-fast"])
            else:
                model_dropdown.addItems(["openrouter-auto", "openrouter-auto-fast"])

            # Always include presets as safe options just after the placeholder if not already
            for preset in ["openrouter-auto", "openrouter-auto-fast"]:
                if model_dropdown.findText(preset) == -1:
                    # Ensure placeholder remains at index 0
                    insert_index = 1
                    try:
                        # Find first index after placeholder that doesn't equal NO_SELECTION_LABEL
                        for i in range(model_dropdown.count()):
                            if model_dropdown.itemText(i) != NO_SELECTION_LABEL:
                                insert_index = max(1, i)
                                break
                    except Exception:
                        insert_index = 1
                    model_dropdown.insertItem(insert_index, preset)


            # Restore saved selection if available; otherwise keep placeholder (no auto-selection)
            try:
                if previous_text:
                    idx = model_dropdown.findText(previous_text)
                    if idx >= 0:
                        model_dropdown.setCurrentIndex(idx)
            except Exception:
                pass

            # Handle image context tri-state based on provider capabilities and model metadata
            if "ENABLE_IMAGE_CONTEXT" in config_widgets:
                auto_disable = capabilities.get("auto_disable_image_context", False)
                if auto_disable:
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
                    config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(
                        f"Image context disabled due to provider payload limits (max {capabilities.get('payload_max_size_kb', 500)} KB)."
                    )
                    if "IMAGE_CONTEXT_WARNING" in config_widgets:
                        config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(True)
                    UIComponents._add_image_context_warning(provider, capabilities)
                else:
                    selected = model_dropdown.currentText()
                    meta = UIComponents._get_openrouter_model_meta(selected)
                    supports_image = None
                    if isinstance(meta, dict):
                        supports_image = meta.get("supports_image")
                    # Determine tri-state: enabled, disabled, or unavailable
                    if selected == NO_SELECTION_LABEL:
                        # No model selected: disable image context and hide warnings
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(
                            "Select a model to configure image inputs."
                        )
                        if "IMAGE_CONTEXT_WARNING" in config_widgets:
                            config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
                    elif supports_image is True:
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(True)
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(
                            "This model supports image inputs."
                        )
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setStyleSheet("")
                        if "IMAGE_CONTEXT_WARNING" in config_widgets:
                            config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
                    elif supports_image is False:
                        # Disable and uncheck for non-vision models; show visible warning text
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(
                            "This model does not support image inputs."
                        )
                        config_widgets["ENABLE_IMAGE_CONTEXT"].setStyleSheet("")
                        if "IMAGE_CONTEXT_WARNING" in config_widgets:
                            try:
                                config_widgets["IMAGE_CONTEXT_WARNING"].setText("⚠️ This model does not support image inputs.")
                            except Exception:
                                pass
                            config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(True)
                    else:
                        # Unknown capability: apply unknown policy and heuristics for check state
                        heuristic = UIComponents._is_openrouter_model_vision(selected)
                        if heuristic:
                            config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
                            config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(True)
                            config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(
                                "Capability unknown; metadata not available."
                            )
                            config_widgets["ENABLE_IMAGE_CONTEXT"].setStyleSheet("")
                            if "IMAGE_CONTEXT_WARNING" in config_widgets:
                                config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
                        else:
                            # Keep enabled but unchecked to avoid breaking inference
                            config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
                            config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                            config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip(
                                "Capability unknown; metadata not available."
                            )
                            if "IMAGE_CONTEXT_WARNING" in config_widgets:
                                config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)

            # React to model changes to auto-toggle image context
            def _on_openrouter_model_changed(name: str):
                try:
                    if "ENABLE_IMAGE_CONTEXT" in config_widgets:
                        auto_disable_local = capabilities.get(
                            "auto_disable_image_context", False
                        )
                        if not auto_disable_local:
                            if name == NO_SELECTION_LABEL:
                                # No model selected: disable image context and hide warnings
                                config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
                                config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                                config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip("Select a model to configure image inputs.")
                                if "IMAGE_CONTEXT_WARNING" in config_widgets:
                                    config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
                                # Also hide non-free warning explicitly when no selection
                                if "OPENROUTER_NON_FREE_WARNING" in config_widgets:
                                    config_widgets["OPENROUTER_NON_FREE_WARNING"].setVisible(False)
                                return
                            meta = UIComponents._get_openrouter_model_meta(name)
                            supports_image = None
                            if isinstance(meta, dict):
                                supports_image = meta.get("supports_image")
                            if supports_image is True:
                                config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
                                config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(True)
                                config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip("This model supports image inputs.")
                                if "IMAGE_CONTEXT_WARNING" in config_widgets:
                                    config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)
                            elif supports_image is False:
                                # Disable and uncheck for non-vision models; show visible warning text
                                config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(False)
                                config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                                config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip("This model does not support image inputs.")
                                if "IMAGE_CONTEXT_WARNING" in config_widgets:
                                    try:
                                        config_widgets["IMAGE_CONTEXT_WARNING"].setText("⚠️ This model does not support image inputs.")
                                    except Exception:
                                        pass
                                    config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(True)
                            else:
                                heuristic = UIComponents._is_openrouter_model_vision(name)
                                if heuristic:
                                    config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
                                    config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(True)
                                    config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip("Capability unknown; metadata not available.")
                                else:
                                    config_widgets["ENABLE_IMAGE_CONTEXT"].setEnabled(True)
                                    config_widgets["ENABLE_IMAGE_CONTEXT"].setChecked(False)
                                    config_widgets["ENABLE_IMAGE_CONTEXT"].setToolTip("Capability unknown; metadata not available.")
                                if "IMAGE_CONTEXT_WARNING" in config_widgets:
                                    config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)

                except Exception as e:
                    logging.debug(f"Error toggling image context on model change: {e}")



                # Show or hide the non-free model warning
                try:
                    if "OPENROUTER_NON_FREE_WARNING" in config_widgets:
                        if name == NO_SELECTION_LABEL:
                            config_widgets["OPENROUTER_NON_FREE_WARNING"].setVisible(False)
                        else:
                            is_free = UIComponents._is_openrouter_model_free(name)
                            config_widgets["OPENROUTER_NON_FREE_WARNING"].setVisible(not is_free)
                except Exception as e:
                    logging.debug(f"Error toggling non-free warning: {e}")

            model_dropdown.currentTextChanged.connect(_on_openrouter_model_changed)

        # Unblock signals after updating
        model_dropdown.blockSignals(False)

    @staticmethod
    def _add_image_context_warning(provider: str, capabilities: Dict[str, Any]) -> None:
        """Add visual warning when image context is auto-disabled."""
        import logging

        try:
            payload_limit = capabilities.get("payload_max_size_kb", 150)
            warning_msg = f"⚠️ IMAGE CONTEXT AUTO-DISABLED: {provider} has strict payload limits ({payload_limit}KB max). Image context automatically disabled to prevent API errors."

            # Log the warning
            logging.warning(
                f"Image context auto-disabled for {provider} due to payload limits"
            )

            # Try to show warning in UI if main controller is available
            try:
                from PySide6.QtWidgets import QApplication

                from domain.ui_controller import CrawlerControllerWindow

                # Get the main window instance if it exists
                app = QApplication.instance()
                if app and isinstance(app, QApplication):
                    for widget in app.topLevelWidgets():
                        if isinstance(widget, CrawlerControllerWindow):
                            widget.log_message(warning_msg, "orange")
                            break
            except Exception as e:
                logging.debug(f"Could not show UI warning: {e}")

        except Exception as e:
            logging.error(f"Error adding image context warning: {e}")

    ADVANCED_FIELDS = {
        "MCP_SERVER_URL": True,  # True means hide in basic mode
        "TARGET_DEVICE_UDID": True,  # True means hide in basic mode
        "DEFAULT_MODEL_TYPE": False,
        "XML_SNIPPET_MAX_LEN": True,
        "STABILITY_WAIT": True,
        "VISUAL_SIMILARITY_THRESHOLD": True,
        "ALLOWED_EXTERNAL_PACKAGES": True,
        "MAX_CONSECUTIVE_AI_FAILURES": True,
        "MAX_CONSECUTIVE_MAP_FAILURES": True,
        "MAX_CONSECUTIVE_EXEC_FAILURES": True,
        "ENABLE_IMAGE_CONTEXT": False,
        "ENABLE_TRAFFIC_CAPTURE": False,
        "CLEANUP_DEVICE_PCAP_FILE": True,
        "CONTINUE_EXISTING_RUN": False,
        "MOBSF_API_URL": True,
        "MOBSF_API_KEY": True,
        "OPENROUTER_SHOW_FREE_ONLY": False,
        # Image preprocessing controls
        "IMAGE_MAX_WIDTH": True,
        "IMAGE_FORMAT": True,
        "IMAGE_QUALITY": True,
        "IMAGE_CROP_BARS": True,
        "IMAGE_CROP_TOP_PERCENT": True,
        "IMAGE_CROP_BOTTOM_PERCENT": True,
    }

    @staticmethod
    def create_left_panel(
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
        controls_handler: Any,
    ) -> QWidget:
        """
        Create the left panel with configuration options

        Args:
            config_widgets: Dictionary to store the config UI widgets
            tooltips: Dictionary of tooltips for the UI elements
            config_handler: Object with methods for handling config-related actions
            controls_handler: Object with methods for handling control buttons

        Returns:
            QWidget containing the left panel
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Create UI mode switch (Basic/Expert)
        mode_layout = QHBoxLayout()
        mode_label = QLabel("UI Mode:")
        config_handler.ui_mode_dropdown = QComboBox()
        config_handler.ui_mode_dropdown.addItems([
            UIComponents.UI_MODE_BASIC,
            UIComponents.UI_MODE_EXPERT
        ])

        # Get the UI mode from config
        initial_mode = UIComponents.UI_MODE_DEFAULT  # Default if not found

        # Try to get UI_MODE from the Config object's SQLite store
        try:
            stored_mode = config_handler.main_controller.config.get(UIComponents.UI_MODE_CONFIG_KEY)
            if stored_mode:
                initial_mode = stored_mode
                logging.debug(f"Setting initial UI mode from SQLite config store: {initial_mode}")
        except Exception as e:
            logging.warning(f"Error retrieving {UIComponents.UI_MODE_CONFIG_KEY} from config store: {e}")

        logging.debug(f"Initial UI mode determined as: {initial_mode}")

        # Set the dropdown to the initial mode
        mode_index = config_handler.ui_mode_dropdown.findText(initial_mode)
        if mode_index >= 0:
            config_handler.ui_mode_dropdown.setCurrentIndex(mode_index)
        else:
            config_handler.ui_mode_dropdown.setCurrentIndex(
                0
            )  # Default to Basic if not found

        config_handler.ui_mode_dropdown.setToolTip(
            "Basic mode hides advanced settings. Expert mode shows all settings."
        )
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(config_handler.ui_mode_dropdown)

        reset_button = QPushButton("Reset Settings")
        reset_button.setToolTip("Restore all configuration values to their defaults.")
        reset_button.clicked.connect(config_handler.reset_settings)
        mode_layout.addWidget(reset_button)
        layout.addLayout(mode_layout)

        # Connect UI mode dropdown to toggle UI complexity
        config_handler.ui_mode_dropdown.currentTextChanged.connect(
            lambda mode: UIComponents.toggle_ui_complexity(mode, config_handler)
        )

        # Create scrollable area for config inputs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QFormLayout(scroll_content)

        # Store scroll_content in config_handler for later reference
        config_handler.scroll_content = scroll_content

        # Create the config inputs sections
        appium_group = UIComponents._create_appium_settings_group(
            scroll_layout, config_widgets, tooltips, controls_handler
        )
        appium_group.setObjectName("appium_settings_group")

        app_group = UIComponents._create_app_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        app_group.setObjectName("app_settings_group")

        ai_group = UIComponents._create_ai_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        ai_group.setObjectName("ai_settings_group")

        # Image Preprocessing placed directly after AI for clearer perception grouping
        image_prep_group = UIComponents._create_image_preprocessing_group(
            scroll_layout, config_widgets, tooltips
        )
        image_prep_group.setObjectName("image_preprocessing_group")

        focus_areas_group = UIComponents._create_focus_areas_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        focus_areas_group.setObjectName("focus_areas_group")

        crawler_group = UIComponents._create_crawler_settings_group(
            scroll_layout, config_widgets, tooltips
        )
        crawler_group.setObjectName("crawler_settings_group")

        error_handling_group = UIComponents._create_error_handling_group(
            scroll_layout, config_widgets, tooltips
        )
        error_handling_group.setObjectName("error_handling_group")

        # Privacy & Network settings (traffic capture)
        privacy_network_group = UIComponents._create_privacy_network_group(
            scroll_layout, config_widgets, tooltips
        )
        privacy_network_group.setObjectName("privacy_network_group")

        mobsf_group = UIComponents._create_mobsf_settings_group(
            scroll_layout, config_widgets, tooltips, config_handler
        )
        mobsf_group.setObjectName("mobsf_settings_group")

        # Run Control and Recording groups (split from previous combined group)
        run_control_group = UIComponents._create_run_control_group(
            scroll_layout, config_widgets, tooltips
        )
        run_control_group.setObjectName("run_control_group")

        recording_group = UIComponents._create_recording_group(
            scroll_layout, config_widgets, tooltips
        )
        recording_group.setObjectName("recording_group")

        # Apply default values
        config_handler._apply_defaults_from_config_to_widgets()
        config_handler._update_crawl_mode_inputs_state()

        # Store the group widgets for mode switching
        config_handler.ui_groups = {
            "appium_settings_group": appium_group,
            "app_settings_group": app_group,
            "ai_settings_group": ai_group,
            "image_preprocessing_group": image_prep_group,
            "focus_areas_group": focus_areas_group,
            "crawler_settings_group": crawler_group,
            "error_handling_group": error_handling_group,
            "privacy_network_group": privacy_network_group,
            "mobsf_settings_group": mobsf_group,
            "run_control_group": run_control_group,
            "recording_group": recording_group,
        }

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Add control buttons
        controls_group = UIComponents._create_control_buttons(controls_handler)
        layout.addWidget(controls_group)

        # Initialize the UI complexity based on the mode we determined
        UIComponents.toggle_ui_complexity(initial_mode, config_handler)

        # Connect all widgets to auto-save
        config_handler.connect_widgets_for_auto_save()

        return panel

    @staticmethod
    def toggle_ui_complexity(mode: str, config_handler):
        """
        Toggle between basic and expert UI modes

        Args:
            mode: "Basic" or "Expert" mode (use UIComponents.UI_MODE_BASIC or UIComponents.UI_MODE_EXPERT)
            config_handler: The config handler with references to UI widgets
        """
        is_basic = mode == UIComponents.UI_MODE_BASIC

        # Toggle group visibility based on mode
        for group_name, group_widget in config_handler.ui_groups.items():
            # Hide advanced groups in basic mode
            if group_name in UIComponents.ADVANCED_GROUPS:
                group_widget.setVisible(not is_basic)

        # Toggle individual field visibility based on mode
        for field_name, is_advanced in UIComponents.ADVANCED_FIELDS.items():
            # Skip if widget not in config_widgets
            if field_name not in config_handler.main_controller.config_widgets:
                continue

            # Get widget reference
            widget = config_handler.main_controller.config_widgets.get(field_name)

            # Skip None widgets
            if widget is None:
                continue

            try:
                # Skip widgets that don't have a parent (not yet added to layout)
                if not hasattr(widget, "parent") or widget.parent() is None:
                    continue

                # Get parent layout
                parent_layout = widget.parent().layout() if widget.parent() else None
                if parent_layout is None:
                    continue

                # If in basic mode and field is advanced, hide it
                # If in expert mode, show all
                widget_visible = not (is_basic and is_advanced)

                # Find and set visibility of associated QLabel
                for i in range(parent_layout.count()):
                    label_item = parent_layout.itemAt(i)
                    if (
                        label_item
                        and label_item.widget()
                        and isinstance(label_item.widget(), QLabel)
                        and i + 1 < parent_layout.count()
                        and parent_layout.itemAt(i + 1).widget() == widget
                    ):
                        label_item.widget().setVisible(widget_visible)
                        break

                # Set widget visibility
                widget.setVisible(widget_visible)
            except Exception as e:
                # Log but don't crash if there's an issue with a specific widget
                logging.warning(f"Error toggling visibility for {field_name}: {e}")

        # Set the dropdown to the current mode
        if hasattr(config_handler, "ui_mode_dropdown"):
            index = config_handler.ui_mode_dropdown.findText(mode)
            if index >= 0 and config_handler.ui_mode_dropdown.currentIndex() != index:
                # Only set if it's different to avoid triggering change events
                config_handler.ui_mode_dropdown.setCurrentIndex(index)

        # Save the current mode to user config
        config_handler.config.update_setting_and_save(
            UIComponents.UI_MODE_CONFIG_KEY, mode, config_handler.main_controller._sync_user_config_files
        )

        # Synchronize the changes to the API config file
        # Note: Synchronization is now handled automatically by the callback in update_setting_and_save

        # Ensure the config.UI_MODE attribute is updated
        if hasattr(config_handler.config, "UI_MODE"):
            config_handler.config.UI_MODE = mode
        logging.debug(f"UI mode switched to and saved: {mode}")
        logging.debug(
            f"Config file location: {config_handler.config.USER_CONFIG_FILE_PATH}"
        )
        config_handler.main_controller.log_message(f"Switched to {mode} mode", "blue")

    @staticmethod
    def create_right_panel(controller) -> QWidget:
        """
        Create the right panel with status, log output, and screenshot display

        Args:
            controller: The controller object that will handle the UI interactions

        Returns:
            QWidget containing the right panel
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Step counter placed above the status text
        step_layout = QHBoxLayout()
        controller.step_label = QLabel("Step: 0")
        step_layout.addWidget(controller.step_label)

        # Status section
        status_layout = QHBoxLayout()
        controller.status_label = QLabel("Status: Idle")
        controller.progress_bar = QProgressBar()
        status_layout.addWidget(controller.status_label)
        status_layout.addWidget(controller.progress_bar)

        # Create side-by-side layout for Action History and Screenshot
        history_screenshot_layout = QHBoxLayout()
        
        # Action history (left side)
        action_history_group = QGroupBox("Action History")
        action_history_layout = QVBoxLayout(action_history_group)
        controller.action_history = QTextEdit()
        controller.action_history.setReadOnly(True)
        # Improve visibility and usability
        try:
            controller.action_history.setPlaceholderText(
                "No actions yet. Actions performed will appear here.")
        except Exception:
            pass
        controller.action_history.setStyleSheet("""
            background-color: #333333; 
            color: #FFFFFF; 
            font-size: 11px; 
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            border: 1px solid #555555;
        """)
        try:
            from PySide6.QtWidgets import QTextEdit as _QTextEdit
            controller.action_history.setLineWrapMode(_QTextEdit.LineWrapMode.WidgetWidth)
        except Exception:
            pass
        # Significantly increase minimum height and make it expandable
        controller.action_history.setMinimumHeight(400)
        controller.action_history.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        action_history_layout.addWidget(controller.action_history)

        # Screenshot display (right side)
        screenshot_group = QGroupBox("Current Screenshot")
        screenshot_layout = QVBoxLayout(screenshot_group)
        controller.screenshot_label = QLabel()
        controller.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controller.screenshot_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        controller.screenshot_label.setMinimumHeight(400)
        controller.screenshot_label.setStyleSheet("""
            border: 1px solid #555555;
            background-color: #2a2a2a;
        """)
        screenshot_layout.addWidget(controller.screenshot_label)
        
        # Add both to the horizontal layout with equal space allocation
        history_screenshot_layout.addWidget(action_history_group, 1)
        history_screenshot_layout.addWidget(screenshot_group, 1)

        # Log output section
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)

        # Add a clear button
        controller.clear_logs_btn = QPushButton("Clear Logs")

        log_header_layout = QHBoxLayout()
        log_header_layout.addStretch()
        log_header_layout.addWidget(controller.clear_logs_btn)

        controller.log_output = QTextEdit()
        controller.log_output.setReadOnly(True)
        controller.log_output.setStyleSheet("background-color: #333333;")

        log_layout.addLayout(log_header_layout)
        log_layout.addWidget(controller.log_output)

        # Add all sections to the layout
        # Add step counter first, then status underneath
        layout.addLayout(step_layout)
        layout.addLayout(status_layout)
        # Add the side-by-side action history and screenshot layout with more space
        layout.addLayout(history_screenshot_layout, 2)  # Give more space to this section
        layout.addWidget(log_group, 1)  # Logs get less space

        return panel

    @staticmethod
    def _create_appium_settings_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        controls_handler: Any,
    ) -> QGroupBox:
        """Create the Appium settings group."""
        appium_group = QGroupBox("Appium Settings")
        appium_layout = QFormLayout(appium_group)

        config_widgets["APPIUM_SERVER_URL"] = QLabel()
        label_appium_url = QLabel("Server URL:")
        label_appium_url.setToolTip(tooltips.get("APPIUM_SERVER_URL", "Appium server URL (e.g., http://127.0.0.1:4723)"))
        appium_layout.addRow(label_appium_url, config_widgets["APPIUM_SERVER_URL"])

        config_widgets["TARGET_DEVICE_UDID"] = QComboBox()
        label_device_udid = QLabel("Target Device UDID:")
        label_device_udid.setToolTip(tooltips["TARGET_DEVICE_UDID"])

        device_layout = QHBoxLayout()
        device_layout.addWidget(config_widgets["TARGET_DEVICE_UDID"])
        refresh_devices_btn = QPushButton("Refresh")
        controls_handler.refresh_devices_btn = refresh_devices_btn
        device_layout.addWidget(refresh_devices_btn)
        appium_layout.addRow(label_device_udid, device_layout)

        layout.addRow(appium_group)
        return appium_group

    @staticmethod
    def _create_app_settings_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
    ) -> QGroupBox:
        """Create the App settings group with health app selection."""
        app_group = QGroupBox("App Settings")
        app_layout = QFormLayout(app_group)

        # Health App Selector with Discovery Filter checkbox
        config_handler.health_app_dropdown = QComboBox()
        config_handler.health_app_dropdown.addItem(
            "Select target app (Scan first)", None
        )
        config_handler.health_app_dropdown.currentIndexChanged.connect(
            config_handler._on_health_app_selected
        )
        config_handler.health_app_dropdown.setToolTip(
            "Select a health-related app discovered on the device. Use button below to scan."
        )

        # Create a horizontal layout for dropdown and discovery filter checkbox
        health_app_layout = QHBoxLayout()
        health_app_layout.addWidget(config_handler.health_app_dropdown)
        
        # Health-only filter toggle (AI)
        # This controls whether the discovery script applies AI filtering to only show health-related apps
        config_widgets["USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY"] = QCheckBox("Health-only filter (AI)")
        config_widgets["USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY"].setToolTip(
            "If enabled, the scanner uses AI to keep only health-related apps (fitness, wellness, medical, medication, mental health)."
        )
        health_app_layout.addWidget(config_widgets["USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY"])
        
        app_layout.addRow(
            QLabel("Target Health App:"), health_app_layout
        )

        config_handler.refresh_apps_btn = QPushButton("Scan/Refresh Health Apps List")
        config_handler.refresh_apps_btn.setToolTip(
            "Scans the connected device for installed applications and filters for health-related ones using AI."
        )
        app_layout.addRow(config_handler.refresh_apps_btn)

        config_handler.app_scan_status_label = QLabel("App Scan: Idle")
        app_layout.addRow(QLabel("Scan Status:"), config_handler.app_scan_status_label)

        layout.addRow(app_group)
        return app_group

    @staticmethod
    def _create_ai_settings_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any = None,
    ) -> QGroupBox:
        """Create the AI settings group."""
        ai_group = QGroupBox("AI Settings")
        ai_layout = QFormLayout(ai_group)

        # AI Provider Selection
        config_widgets["AI_PROVIDER"] = QComboBox()
        config_widgets["AI_PROVIDER"].addItems(["gemini", "ollama", "openrouter"])
        label_ai_provider = QLabel("AI Provider: ")
        label_ai_provider.setToolTip(
            "The AI model provider to use for analysis and decision making."
        )
        ai_layout.addRow(label_ai_provider, config_widgets["AI_PROVIDER"])

        # Create refresh button for OpenRouter models (hidden by default)
        config_widgets["OPENROUTER_REFRESH_BTN"] = QPushButton("Refresh models")
        config_widgets["OPENROUTER_REFRESH_BTN"].setToolTip(
            "Fetch latest models from OpenRouter API"
        )
        config_widgets["OPENROUTER_REFRESH_BTN"].setVisible(False)

        config_widgets["DEFAULT_MODEL_TYPE"] = QComboBox()
        # Start with explicit no-selection placeholder; provider change will populate
        try:
            config_widgets["DEFAULT_MODEL_TYPE"].addItem("No model selected")
        except Exception:
            config_widgets["DEFAULT_MODEL_TYPE"].addItems(["No model selected"])
        label_model_type = QLabel("Default Model Type: ")
        label_model_type.setToolTip(tooltips["DEFAULT_MODEL_TYPE"])
        # Place dropdown and refresh button side-by-side
        _model_row_layout = QHBoxLayout()
        _model_row_layout.addWidget(config_widgets["DEFAULT_MODEL_TYPE"])
        _model_row_layout.addWidget(config_widgets["OPENROUTER_REFRESH_BTN"])
        # Free-only filter (hidden by default; shown for OpenRouter)
        config_widgets["OPENROUTER_SHOW_FREE_ONLY"] = QCheckBox("Free only")
        config_widgets["OPENROUTER_SHOW_FREE_ONLY"].setToolTip(
            "Show only models with free pricing (0 cost)."
        )
        config_widgets["OPENROUTER_SHOW_FREE_ONLY"].setVisible(False)
        _model_row_layout.addWidget(config_widgets["OPENROUTER_SHOW_FREE_ONLY"])

        # Add a warning label for non-free models
        config_widgets["OPENROUTER_NON_FREE_WARNING"] = QLabel("⚠️ This model may use your OpenRouter credit.")
        config_widgets["OPENROUTER_NON_FREE_WARNING"].setStyleSheet("color: orange;")
        config_widgets["OPENROUTER_NON_FREE_WARNING"].setVisible(False)
        config_widgets["OPENROUTER_NON_FREE_WARNING"].setWordWrap(True)

        warning_layout = QVBoxLayout()
        warning_layout.addWidget(config_widgets["OPENROUTER_NON_FREE_WARNING"])

        ai_layout.addRow(label_model_type, _model_row_layout)
        ai_layout.addRow(warning_layout)

        # Connect the AI provider selection to update model types and toggle refresh visibility
        def _on_provider_changed(provider: str):
            UIComponents._update_model_types(provider, config_widgets)
            is_or = provider.lower() == "openrouter"
            # Show OpenRouter controls only when OpenRouter is selected
            config_widgets["OPENROUTER_REFRESH_BTN"].setVisible(is_or)
            config_widgets["OPENROUTER_SHOW_FREE_ONLY"].setVisible(is_or)

        config_widgets["AI_PROVIDER"].currentTextChanged.connect(_on_provider_changed)

        # Wire up refresh button
        def _on_refresh_clicked():
            try:
                UIComponents._refresh_openrouter_models(config_handler, config_widgets)
            except Exception as e:
                logging.warning(f"Failed to refresh OpenRouter models: {e}")

        config_widgets["OPENROUTER_REFRESH_BTN"].clicked.connect(_on_refresh_clicked)

        # Wire up free-only filter to re-populate models
        def _on_free_only_changed(_state: int):
            try:
                current_provider = config_widgets["AI_PROVIDER"].currentText().lower()
                if current_provider == "openrouter":
                    UIComponents._update_model_types("openrouter", config_widgets)
            except Exception as e:
                logging.debug(f"Failed to apply free-only filter: {e}")

        config_widgets["OPENROUTER_SHOW_FREE_ONLY"].stateChanged.connect(
            _on_free_only_changed
        )

        # Advanced manual model id entry removed; use dropdown-only selection

        # Enable Image Context moved here from Feature Toggles
        config_widgets["ENABLE_IMAGE_CONTEXT"] = QCheckBox()
        label_enable_image_context = QLabel("Enable Image Context: ")
        label_enable_image_context.setToolTip(
            "Enable sending screenshots to AI for visual analysis. Disable for text-only analysis."
        )

        # Warning label (used when auto-disabled by provider capabilities)
        config_widgets["IMAGE_CONTEXT_WARNING"] = QLabel("⚠️ Auto-disabled")
        config_widgets["IMAGE_CONTEXT_WARNING"].setStyleSheet(
            "color: #ff6b35; font-weight: bold;"
        )
        config_widgets["IMAGE_CONTEXT_WARNING"].setVisible(False)

        # Horizontal layout for checkbox and warning
        image_context_layout = QHBoxLayout()
        image_context_layout.addWidget(label_enable_image_context)
        image_context_layout.addWidget(config_widgets["ENABLE_IMAGE_CONTEXT"])
        image_context_layout.addWidget(config_widgets["IMAGE_CONTEXT_WARNING"])
        image_context_layout.addStretch()
        ai_layout.addRow(image_context_layout)

        config_widgets["XML_SNIPPET_MAX_LEN"] = QSpinBox()
        config_widgets["XML_SNIPPET_MAX_LEN"].setRange(5000, 500000)
        label_xml_snippet_max_len = QLabel("XML Snippet Max Length: ")
        label_xml_snippet_max_len.setToolTip(tooltips["XML_SNIPPET_MAX_LEN"])
        ai_layout.addRow(
            label_xml_snippet_max_len, config_widgets["XML_SNIPPET_MAX_LEN"]
        )

        layout.addRow(ai_group)
        return ai_group

    @staticmethod
    def _create_image_preprocessing_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
    ) -> QGroupBox:
        """Create the Image Preprocessing settings group."""
        group = QGroupBox("Image Preprocessing")
        form = QFormLayout(group)

        # Max width
        config_widgets["IMAGE_MAX_WIDTH"] = QSpinBox()
        config_widgets["IMAGE_MAX_WIDTH"].setRange(240, 4000)
        label_max_width = QLabel("Max Screenshot Width (px): ")
        label_max_width.setToolTip(tooltips.get("IMAGE_MAX_WIDTH", "Max width to resize screenshots before sending to AI. Smaller reduces payload; larger preserves detail."))
        form.addRow(label_max_width, config_widgets["IMAGE_MAX_WIDTH"])

        # Format
        config_widgets["IMAGE_FORMAT"] = QComboBox()
        config_widgets["IMAGE_FORMAT"].addItems(["JPEG", "WEBP", "PNG"])
        label_format = QLabel("Image Format: ")
        label_format.setToolTip(tooltips.get("IMAGE_FORMAT", "Choose output format for screenshots sent to AI."))
        form.addRow(label_format, config_widgets["IMAGE_FORMAT"])

        # Quality
        config_widgets["IMAGE_QUALITY"] = QSpinBox()
        config_widgets["IMAGE_QUALITY"].setRange(10, 100)
        label_quality = QLabel("Image Quality (%): ")
        label_quality.setToolTip(tooltips.get("IMAGE_QUALITY", "Compression quality for lossy formats (JPEG/WEBP). Lower = smaller payload, higher = more detail."))
        form.addRow(label_quality, config_widgets["IMAGE_QUALITY"])

        # Crop bars toggle
        config_widgets["IMAGE_CROP_BARS"] = QCheckBox()
        label_crop_bars = QLabel("Crop Status/Navigation Bars: ")
        label_crop_bars.setToolTip(tooltips.get("IMAGE_CROP_BARS", "Remove top/bottom bars to reduce payload while keeping UI content."))
        form.addRow(label_crop_bars, config_widgets["IMAGE_CROP_BARS"])

        # Top crop percent
        config_widgets["IMAGE_CROP_TOP_PERCENT"] = QSpinBox()
        config_widgets["IMAGE_CROP_TOP_PERCENT"].setRange(0, 50)
        label_crop_top = QLabel("Top Crop (% of height): ")
        label_crop_top.setToolTip(tooltips.get("IMAGE_CROP_TOP_PERCENT", "Percentage of image height to crop from the top when cropping bars is enabled."))
        form.addRow(label_crop_top, config_widgets["IMAGE_CROP_TOP_PERCENT"])

        # Bottom crop percent
        config_widgets["IMAGE_CROP_BOTTOM_PERCENT"] = QSpinBox()
        config_widgets["IMAGE_CROP_BOTTOM_PERCENT"].setRange(0, 50)
        label_crop_bottom = QLabel("Bottom Crop (% of height): ")
        label_crop_bottom.setToolTip(tooltips.get("IMAGE_CROP_BOTTOM_PERCENT", "Percentage of image height to crop from the bottom when cropping bars is enabled."))
        form.addRow(label_crop_bottom, config_widgets["IMAGE_CROP_BOTTOM_PERCENT"])

        layout.addRow(group)
        return group

    @staticmethod
    def _get_openrouter_cache_path() -> str:
        # Delegate to central utility to avoid UI-only coupling
        try:
            from domain.openrouter_models import get_openrouter_cache_path
        except ImportError:
            from domain.openrouter_models import get_openrouter_cache_path
        return get_openrouter_cache_path()

    @staticmethod
    def _load_openrouter_models_from_cache() -> Optional[list]:
        try:
            # Delegate to central utility
            try:
                from domain.openrouter_models import load_openrouter_models_cache
            except ImportError:
                from domain.openrouter_models import load_openrouter_models_cache
            return load_openrouter_models_cache()
        except Exception as e:
            logging.debug(f"Failed to read OpenRouter cache: {e}")
            return None

    @staticmethod
    def _save_openrouter_models_to_cache(models: List[Dict[str, Any]]) -> None:
        try:
            try:
                from domain.openrouter_models import save_openrouter_models_to_cache
            except ImportError:
                from domain.openrouter_models import save_openrouter_models_to_cache
            save_openrouter_models_to_cache(models)
        except Exception as e:
            logging.debug(f"Failed to save OpenRouter cache via central utility: {e}")

    @staticmethod
    def _is_openrouter_model_vision(model_id: str) -> bool:
        """Determine vision support using cache metadata; fallback to heuristics."""
        try:
            # Delegate to central utility
            try:
                from domain.openrouter_models import is_openrouter_model_vision
            except ImportError:
                from domain.openrouter_models import is_openrouter_model_vision
            return is_openrouter_model_vision(model_id)
        except Exception as e:
            logging.debug(f"Failed to determine vision support: {e}")
            return False

    @staticmethod
    def _refresh_openrouter_models(
        config_handler: Any, config_widgets: Dict[str, Any]
    ) -> None:
        # Disable refresh button and show busy overlay to indicate long-running operation
        btn = config_widgets.get("OPENROUTER_REFRESH_BTN")
        try:
            if btn:
                btn.setEnabled(False)
        except Exception:
            pass
        try:
            config_handler.main_controller.show_busy("Refreshing AI models...")
        except Exception:
            pass
        try:
            api_key = getattr(config_handler.config, "OPENROUTER_API_KEY", None)
            if not api_key:
                logging.warning("OpenRouter refresh requested but API key is missing.")
                config_handler.main_controller.log_message(
                    "OpenRouter API key missing. Set OPENROUTER_API_KEY in .env.",
                    "orange",
                )
                return
            import requests

            # Proactively delete any stale cache before fetching fresh data
            try:
                cache_path = UIComponents._get_openrouter_cache_path()
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                    logging.info("Deleted stale OpenRouter model cache before refresh.")
                    try:
                        config_handler.main_controller.log_message(
                            "Deleted local OpenRouter cache.", "gray"
                        )
                    except Exception:
                        pass
            except Exception as cache_err:
                logging.debug(f"Could not delete OpenRouter cache: {cache_err}")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            resp = requests.get(
                "https://openrouter.ai/api/v1/models", headers=headers, timeout=20
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            # OpenRouter returns {'data': [ ...models... ]}
            models = data.get("data") or data.get("models") or []
            # Enrich normalization using standardized fields and derived flags
            normalized: List[Dict[str, Any]] = []
            for m in models:
                mid = m.get("id") or m.get("name")
                if not mid:
                    continue
                name = m.get("name") or m.get("canonical_slug") or str(mid)
                architecture = m.get("architecture") or {}
                input_modalities = architecture.get("input_modalities") or []
                output_modalities = architecture.get("output_modalities") or []
                supported_parameters = m.get("supported_parameters") or []
                pricing = m.get("pricing") if isinstance(m.get("pricing"), dict) else None
                top_provider = m.get("top_provider") if isinstance(m.get("top_provider"), dict) else None
                context_length = (
                    m.get("context_length")
                    or (top_provider or {}).get("context_length")
                )
                # Derived flags
                supports_image = False
                try:
                    supports_image = "image" in (input_modalities or [])
                except Exception:
                    supports_image = False
                def _val_is_zero(v: Any) -> bool:
                    try:
                        if isinstance(v, (int, float)):
                            return v == 0
                        if isinstance(v, str):
                            s = v.strip().lower()
                            return s == "0" or s == "$0" or "free" in s
                        return False
                    except Exception:
                        return False

                # Stricter free detection: prompt and completion must be zero; if image is supported, it must be zero too
                prompt_zero = _val_is_zero((pricing or {}).get("prompt"))
                completion_zero = _val_is_zero((pricing or {}).get("completion"))
                image_zero = _val_is_zero((pricing or {}).get("image"))
                is_free = (
                    (prompt_zero and completion_zero and (not supports_image or image_zero))
                    or ("(free" in name.lower())
                    or (str(mid).lower().endswith(":free"))
                )
                supports_tools = "tools" in supported_parameters
                supports_structured_outputs = "structured_outputs" in supported_parameters or "response_format" in supported_parameters

                entry: Dict[str, Any] = {
                    "id": mid,
                    "name": name,
                    "canonical_slug": m.get("canonical_slug"),
                    "created": m.get("created") or m.get("created_at"),
                    "description": m.get("description"),
                    "context_length": context_length,
                    "architecture": {
                        "input_modalities": input_modalities,
                        "output_modalities": output_modalities,
                        "tokenizer": architecture.get("tokenizer"),
                        "instruct_type": architecture.get("instruct_type"),
                    },
                    "supported_parameters": supported_parameters,
                    "pricing": pricing,
                    "top_provider": top_provider,
                    "per_request_limits": m.get("per_request_limits"),
                    # Derived flags
                    "supports_image": supports_image,
                    "is_free": is_free,
                    "supports_tools": supports_tools,
                    "supports_structured_outputs": supports_structured_outputs,
                }
                normalized.append(entry)
            if not normalized:
                raise RuntimeError("No models returned from OpenRouter")
            UIComponents._save_openrouter_models_to_cache(normalized)
            try:
                logging.info(f"Fetched {len(normalized)} OpenRouter models from API.")
            except Exception:
                pass
            config_handler.main_controller.log_message(
                f"Fetched {len(normalized)} OpenRouter models.", "green"
            )
            # Re-populate dropdown from cache
            UIComponents._update_model_types("openrouter", config_widgets)
        except Exception as e:
            logging.warning(f"OpenRouter model fetch failed: {e}")
            try:
                config_handler.main_controller.log_message(
                    f"OpenRouter model fetch failed: {e}", "orange"
                )
            except Exception:
                pass
        finally:
            # Ensure the overlay is hidden and button re-enabled regardless of success or failure
            try:
                config_handler.main_controller.hide_busy()
            except Exception:
                pass
            try:
                if btn:
                    btn.setEnabled(True)
            except Exception:
                pass

    @staticmethod
    def _is_openrouter_model_free(model_meta: Any) -> bool:
        """Determine free status strictly using prompt/completion/image pricing and known indicators."""
        try:
            # Delegate to central utility
            try:
                from domain.openrouter_models import is_openrouter_model_free
            except ImportError:
                from domain.openrouter_models import is_openrouter_model_free
            return is_openrouter_model_free(model_meta)
        except Exception as e:
            logging.debug(f"Failed to determine free status: {e}")
            return False

    @staticmethod
    def _get_openrouter_model_meta(model_id: str) -> Optional[Dict[str, Any]]:
        """Lookup a model's metadata by id from the cache (supports both schemas)."""
        try:
            # Delegate to central utility
            try:
                from domain.openrouter_models import get_openrouter_model_meta
            except ImportError:
                from domain.openrouter_models import get_openrouter_model_meta
            return get_openrouter_model_meta(model_id)
        except Exception as e:
            logging.debug(f"Failed to lookup model meta: {e}")
            return None

    @staticmethod
    def _background_refresh_openrouter_models() -> None:
        """Background refresh delegating to central utility (UI-agnostic)."""
        try:
            # Delegate to central utility
            try:
                from domain.openrouter_models import background_refresh_openrouter_models
            except ImportError:
                from domain.openrouter_models import background_refresh_openrouter_models
            background_refresh_openrouter_models()
        except Exception as e:
            logging.debug(f"Failed to queue background OpenRouter refresh via central utility: {e}")

    @staticmethod
    def _create_focus_areas_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
    ) -> QGroupBox:
        """Create the Focus Areas group."""
        focus_group = QGroupBox("AI Privacy Focus Areas")
        focus_layout = QVBoxLayout(focus_group)

        # Import the focus areas widget
        try:
            from ui.focus_areas_widget import FocusAreasWidget
        except ImportError:
            from ui.focus_areas_widget import FocusAreasWidget

        # Try to get focus service from main controller
        focus_service = None
        try:
            if hasattr(config_handler, 'main_controller'):
                main_controller = config_handler.main_controller
                if hasattr(main_controller, 'focus_service'):
                    focus_service = main_controller.focus_service
        except Exception as e:
            logging.warning(f"Could not get focus_service from main_controller: {e}")

        # Load focus areas from config
        focus_areas_data = getattr(config_handler.config, "FOCUS_AREAS", None)

        # Start with empty list - users must add focus areas through CRUD operations
        # If config has saved focus areas, load them
        if focus_areas_data:
            # Convert to proper format if needed
            pass
        else:
            focus_areas_data = []

        # Create the focus areas widget
        focus_widget = FocusAreasWidget(focus_areas_data, parent=None, focus_service=focus_service)
        focus_layout.addWidget(focus_widget)

        # Connect to config changes
        focus_widget.focus_areas_changed.connect(
            lambda areas: config_handler.update_focus_areas(areas)
        )

        # Store reference for later access
        config_handler.focus_areas_widget = focus_widget

        layout.addRow(focus_group)
        return focus_group

    @staticmethod
    def _create_crawler_settings_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Crawler settings group."""
        crawler_group = QGroupBox("Crawler Settings")
        crawler_layout = QFormLayout(crawler_group)

        config_widgets["CRAWL_MODE"] = QComboBox()
        config_widgets["CRAWL_MODE"].addItems(["steps", "time"])
        label_crawl_mode = QLabel("Crawl Mode: ")
        label_crawl_mode.setToolTip(tooltips["CRAWL_MODE"])
        crawler_layout.addRow(label_crawl_mode, config_widgets["CRAWL_MODE"])

        config_widgets["MAX_CRAWL_STEPS"] = QSpinBox()
        config_widgets["MAX_CRAWL_STEPS"].setRange(1, 10000)
        label_max_crawl_steps = QLabel("Max Steps: ")
        label_max_crawl_steps.setToolTip(tooltips["MAX_CRAWL_STEPS"])
        crawler_layout.addRow(label_max_crawl_steps, config_widgets["MAX_CRAWL_STEPS"])

        config_widgets["MAX_CRAWL_DURATION_SECONDS"] = QSpinBox()
        config_widgets["MAX_CRAWL_DURATION_SECONDS"].setRange(60, 86400)
        label_max_crawl_duration = QLabel("Max Duration (s): ")
        label_max_crawl_duration.setToolTip(tooltips["MAX_CRAWL_DURATION_SECONDS"])
        crawler_layout.addRow(
            label_max_crawl_duration, config_widgets["MAX_CRAWL_DURATION_SECONDS"]
        )

        config_widgets["WAIT_AFTER_ACTION"] = QSpinBox()
        config_widgets["WAIT_AFTER_ACTION"].setRange(0, 60)
        label_wait_after_action = QLabel("Wait After Action (s): ")
        label_wait_after_action.setToolTip(tooltips["WAIT_AFTER_ACTION"])
        crawler_layout.addRow(
            label_wait_after_action, config_widgets["WAIT_AFTER_ACTION"]
        )

        config_widgets["STABILITY_WAIT"] = QSpinBox()
        config_widgets["STABILITY_WAIT"].setRange(0, 60)
        label_stability_wait = QLabel("Stability Wait (s): ")
        label_stability_wait.setToolTip(tooltips["STABILITY_WAIT"])
        crawler_layout.addRow(label_stability_wait, config_widgets["STABILITY_WAIT"])

        config_widgets["APP_LAUNCH_WAIT_TIME"] = QSpinBox()
        config_widgets["APP_LAUNCH_WAIT_TIME"].setRange(0, 300)
        label_app_launch_wait_time = QLabel("App Launch Wait Time (s): ")
        label_app_launch_wait_time.setToolTip(tooltips["APP_LAUNCH_WAIT_TIME"])
        crawler_layout.addRow(
            label_app_launch_wait_time, config_widgets["APP_LAUNCH_WAIT_TIME"]
        )

        # Visual Similarity Threshold
        config_widgets["VISUAL_SIMILARITY_THRESHOLD"] = QSpinBox()
        config_widgets["VISUAL_SIMILARITY_THRESHOLD"].setRange(0, 100)
        label_visual_similarity = QLabel("Visual Similarity Threshold: ")
        label_visual_similarity.setToolTip(tooltips["VISUAL_SIMILARITY_THRESHOLD"])
        crawler_layout.addRow(
            label_visual_similarity, config_widgets["VISUAL_SIMILARITY_THRESHOLD"]
        )

        # Allowed External Packages - Use dedicated widget with CRUD support
        from ui.allowed_packages_widget import AllowedPackagesWidget
        from config.config import Config
        config = Config()
        config_widgets["ALLOWED_EXTERNAL_PACKAGES_WIDGET"] = AllowedPackagesWidget(config)
        # Store a reference to the widget for compatibility with config manager
        config_widgets["ALLOWED_EXTERNAL_PACKAGES"] = config_widgets["ALLOWED_EXTERNAL_PACKAGES_WIDGET"]
        crawler_layout.addRow(config_widgets["ALLOWED_EXTERNAL_PACKAGES_WIDGET"])

        layout.addRow(crawler_group)
        return crawler_group

    @staticmethod
    def _create_error_handling_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Error Handling settings group."""
        error_handling_group = QGroupBox("Error Handling Settings")
        error_handling_layout = QFormLayout(error_handling_group)

        config_widgets["MAX_CONSECUTIVE_AI_FAILURES"] = QSpinBox()
        config_widgets["MAX_CONSECUTIVE_AI_FAILURES"].setRange(1, 100)
        label_max_ai_failures = QLabel("Max Consecutive AI Failures: ")
        label_max_ai_failures.setToolTip(tooltips["MAX_CONSECUTIVE_AI_FAILURES"])
        error_handling_layout.addRow(
            label_max_ai_failures, config_widgets["MAX_CONSECUTIVE_AI_FAILURES"]
        )

        config_widgets["MAX_CONSECUTIVE_MAP_FAILURES"] = QSpinBox()
        config_widgets["MAX_CONSECUTIVE_MAP_FAILURES"].setRange(1, 100)
        label_max_map_failures = QLabel("Max Consecutive Map Failures: ")
        label_max_map_failures.setToolTip(tooltips["MAX_CONSECUTIVE_MAP_FAILURES"])
        error_handling_layout.addRow(
            label_max_map_failures, config_widgets["MAX_CONSECUTIVE_MAP_FAILURES"]
        )

        config_widgets["MAX_CONSECUTIVE_EXEC_FAILURES"] = QSpinBox()
        config_widgets["MAX_CONSECUTIVE_EXEC_FAILURES"].setRange(1, 100)
        label_max_exec_failures = QLabel("Max Consecutive Exec Failures: ")
        label_max_exec_failures.setToolTip(tooltips["MAX_CONSECUTIVE_EXEC_FAILURES"])
        error_handling_layout.addRow(
            label_max_exec_failures, config_widgets["MAX_CONSECUTIVE_EXEC_FAILURES"]
        )

        layout.addRow(error_handling_group)
        return error_handling_group

    @staticmethod
    def _create_run_control_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Run Control group for session-related controls."""
        run_control_group = QGroupBox("Run Control")
        run_control_layout = QFormLayout(run_control_group)

        config_widgets["CONTINUE_EXISTING_RUN"] = QCheckBox()
        label_continue_run = QLabel("Continue Existing Run: ")
        label_continue_run.setToolTip(tooltips["CONTINUE_EXISTING_RUN"])
        run_control_layout.addRow(
            label_continue_run, config_widgets["CONTINUE_EXISTING_RUN"]
        )

        layout.addRow(run_control_group)
        return run_control_group

    @staticmethod
    def _create_recording_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Recording group for media capture settings."""
        recording_group = QGroupBox("Recording")
        recording_layout = QFormLayout(recording_group)

        config_widgets["ENABLE_VIDEO_RECORDING"] = QCheckBox()
        label_enable_video = QLabel("Enable Video Recording: ")
        recording_layout.addRow(
            label_enable_video, config_widgets["ENABLE_VIDEO_RECORDING"]
        )

        layout.addRow(recording_group)
        return recording_group

    @staticmethod
    def _create_privacy_network_group(
        layout: QFormLayout, config_widgets: Dict[str, Any], tooltips: Dict[str, str]
    ) -> QGroupBox:
        """Create the Privacy & Network group for traffic capture-related settings."""
        privacy_group = QGroupBox("Privacy & Network")
        privacy_layout = QFormLayout(privacy_group)

        # Traffic capture toggles moved from Feature Toggles
        config_widgets["ENABLE_TRAFFIC_CAPTURE"] = QCheckBox()
        label_enable_traffic_capture = QLabel("Enable Traffic Capture: ")
        label_enable_traffic_capture.setToolTip(tooltips["ENABLE_TRAFFIC_CAPTURE"])
        privacy_layout.addRow(
            label_enable_traffic_capture, config_widgets["ENABLE_TRAFFIC_CAPTURE"]
        )

        config_widgets["CLEANUP_DEVICE_PCAP_FILE"] = QCheckBox()
        label_cleanup_pcap = QLabel("Cleanup Device PCAP after Pull: ")
        label_cleanup_pcap.setToolTip(tooltips["CLEANUP_DEVICE_PCAP_FILE"])
        privacy_layout.addRow(
            label_cleanup_pcap, config_widgets["CLEANUP_DEVICE_PCAP_FILE"]
        )

        layout.addRow(privacy_group)
        return privacy_group

    @staticmethod
    def _create_mobsf_settings_group(
        layout: QFormLayout,
        config_widgets: Dict[str, Any],
        tooltips: Dict[str, str],
        config_handler: Any,
    ) -> QGroupBox:
        """Create the MobSF settings group."""
        mobsf_group = QGroupBox("MobSF Static Analysis")
        mobsf_layout = QFormLayout(mobsf_group)

        # MobSF Enable Checkbox
        config_widgets["ENABLE_MOBSF_ANALYSIS"] = QCheckBox()
        label_enable_mobsf = QLabel("Enable MobSF Analysis: ")
        label_enable_mobsf.setToolTip(tooltips["ENABLE_MOBSF_ANALYSIS"])
        mobsf_layout.addRow(label_enable_mobsf, config_widgets["ENABLE_MOBSF_ANALYSIS"])

        # Get current enabled state (default to False if not set)
        is_mobsf_enabled = getattr(
            config_handler.config, "ENABLE_MOBSF_ANALYSIS", False
        )
        config_widgets["ENABLE_MOBSF_ANALYSIS"].setChecked(is_mobsf_enabled)
        logging.debug(f"Setting initial MobSF checkbox state: {is_mobsf_enabled}")

        # API URL field
        config_widgets["MOBSF_API_URL"] = QLineEdit()
        config_widgets["MOBSF_API_URL"].setPlaceholderText(
            "http://localhost:8000/api/v1"
        )
        label_mobsf_api_url = QLabel("MobSF API URL: ")
        label_mobsf_api_url.setToolTip(tooltips["MOBSF_API_URL"])
        mobsf_layout.addRow(label_mobsf_api_url, config_widgets["MOBSF_API_URL"])

        config_widgets["MOBSF_API_KEY"] = QLineEdit()
        config_widgets["MOBSF_API_KEY"].setPlaceholderText("Your MobSF API Key")
        config_widgets["MOBSF_API_KEY"].setEchoMode(QLineEdit.EchoMode.Password)
        label_mobsf_api_key = QLabel("MobSF API Key: ")
        label_mobsf_api_key.setToolTip(tooltips["MOBSF_API_KEY"])
        mobsf_layout.addRow(label_mobsf_api_key, config_widgets["MOBSF_API_KEY"])

        # MobSF test and analysis buttons - assign to main_controller instead of config_handler
        main_controller = config_handler.main_controller
        main_controller.test_mobsf_conn_btn = QPushButton("Test MobSF Connection")
        mobsf_layout.addRow(main_controller.test_mobsf_conn_btn)
        logging.debug("Created test_mobsf_conn_btn directly on main_controller")

        main_controller.run_mobsf_analysis_btn = QPushButton("Run MobSF Analysis")
        mobsf_layout.addRow(main_controller.run_mobsf_analysis_btn)
        logging.debug("Created run_mobsf_analysis_btn directly on main_controller")

        # Set initial button states based on checkbox
        main_controller.test_mobsf_conn_btn.setEnabled(is_mobsf_enabled)
        main_controller.run_mobsf_analysis_btn.setEnabled(is_mobsf_enabled)

        # Connect the checkbox to update button state - using a direct slot reference
        # Connect after buttons are created
        config_widgets["ENABLE_MOBSF_ANALYSIS"].stateChanged.connect(
            config_handler._on_mobsf_enabled_state_changed
        )

        layout.addRow(mobsf_group)
        return mobsf_group

    @staticmethod
    def _create_control_buttons(controls_handler: Any) -> QGroupBox:
        """Create the control buttons group."""
        group = QGroupBox("Controls")
        layout = QHBoxLayout(group)

        controls_handler.start_btn = QPushButton("Start Crawler")
        controls_handler.stop_btn = QPushButton("Stop Crawler")
        controls_handler.stop_btn.setEnabled(False)

        # Add pre-check button
        pre_check_btn = QPushButton("🔍 Pre-Check Services")
        pre_check_btn.setToolTip(
            "Check the status of all required services (Appium, Ollama, MobSF) before starting"
        )
        pre_check_btn.clicked.connect(controls_handler.perform_pre_crawl_validation)

        # Add generate report button
        controls_handler.generate_report_btn = QPushButton("📄 Generate Report (PDF)")
        controls_handler.generate_report_btn.setToolTip(
            "Create an analysis PDF for the latest run in the current session"
        )
        # Enabled by default; will be disabled during crawling and re-enabled on finish
        controls_handler.generate_report_btn.setEnabled(True)
        controls_handler.generate_report_btn.clicked.connect(controls_handler.generate_report)

        controls_handler.start_btn.clicked.connect(controls_handler.start_crawler)
        controls_handler.stop_btn.clicked.connect(controls_handler.stop_crawler)

        layout.addWidget(pre_check_btn)
        layout.addWidget(controls_handler.generate_report_btn)
        layout.addWidget(controls_handler.start_btn)
        layout.addWidget(controls_handler.stop_btn)

        return group
