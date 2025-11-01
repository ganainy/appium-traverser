# ui/focus_areas_widget.py - Widget for managing privacy-focused focus areas

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)


class HelpIcon(QLabel):
    """A clickable help icon that shows tooltip on hover."""
    
    def __init__(self, help_text: str, parent=None):
        super().__init__("?", parent)
        self.help_text = help_text
        self.setToolTip(help_text)
        self.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 1px 5px;
                border-radius: 50%;
                background-color: #6b7280;
                text-align: center;
                min-width: 18px;
                max-width: 18px;
                min-height: 18px;
                max-height: 18px;
            }
        """)
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def enterEvent(self, event):
        """Handle mouse enter event."""
        self.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 1px 5px;
                border-radius: 50%;
                background-color: #3b82f6;
                text-align: center;
                min-width: 18px;
                max-width: 18px;
                min-height: 18px;
                max-height: 18px;
            }
        """)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave event."""
        self.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 1px 5px;
                border-radius: 50%;
                background-color: #6b7280;
                text-align: center;
                min-width: 18px;
                max-width: 18px;
                min-height: 18px;
                max-height: 18px;
            }
        """)
        super().leaveEvent(event)


@dataclass
class FocusArea:
    """Represents a focus area for AI agent behavior."""
    id: str
    name: str
    description: str
    prompt_modifier: str
    enabled: bool = True
    priority: int = 0



class FocusAreaItem(QWidget):
    """Draggable item representing a single focus area."""
    
    delete_requested = Signal(str)  # Emitted when delete button is clicked with area ID

    def __init__(self, area: FocusArea, parent=None):
        super().__init__(parent)
        self.area = area
        self.checkbox = None
        self.drag_handle = None
        self.delete_button = None
        self.setup_ui()

    def setup_ui(self):
        """Setup the UI for this focus area item."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Drag handle with priority number (horizontal for aligned column)
        priority_layout = QHBoxLayout()
        priority_layout.setContentsMargins(0, 0, 0, 0)
        priority_layout.setSpacing(6)

        # Priority number
        priority_label = QLabel(str(self.area.priority + 1))
        priority_label.setStyleSheet("""
            QLabel {
                color: #e5e7eb;
                font-size: 10px;
                font-weight: 600;
                text-align: center;
                background-color: #374151;
                border-radius: 8px;
                padding: 1px 6px;
                min-width: 18px;
                max-width: 18px;
                min-height: 18px;
                max-height: 18px;
            }
        """)
        priority_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        priority_layout.addWidget(priority_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Drag handle (replace vertical dots with up/down arrow)
        self.drag_handle = QLabel("↕")
        self.drag_handle.setStyleSheet("""
            QLabel {
                color: #9ca3af;
                font-size: 12px;
                padding: 2px 5px;
                background-color: transparent;
                border-radius: 3px;
            }
            QLabel:hover {
                color: #d1d5db;
                background-color: #1f2937;
            }
        """)
        self.drag_handle.setFixedWidth(20)
        self.drag_handle.setToolTip("Drag to reorder")
        self.drag_handle.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        priority_layout.addWidget(self.drag_handle)

        priority_widget = QWidget()
        priority_widget.setLayout(priority_layout)
        priority_widget.setFixedWidth(60)
        layout.addWidget(priority_widget)

        # Checkbox for enable/disable
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.area.enabled)
        self.checkbox.setToolTip("Enable/disable this focus area")
        layout.addWidget(self.checkbox)

        # Content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)

        # Name
        name_label = QLabel(self.area.name)
        name_label.setStyleSheet("font-weight: 600; font-size: 11px; color: #e5e7eb;")
        name_label.setWordWrap(True)
        content_layout.addWidget(name_label)

        # Description
        desc_label = QLabel(self.area.description)
        desc_label.setStyleSheet("color: #9ca3af; font-size: 10px;")
        desc_label.setWordWrap(True)
        content_layout.addWidget(desc_label)

        layout.addWidget(content_widget, 1)

        # Delete button
        self.delete_button = QPushButton("Delete")
        self.delete_button.setStyleSheet("""
            QPushButton {
                color: #ef4444;
                background-color: transparent;
                border: 1px solid #ef4444;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: #ef4444;
            }
            QPushButton:pressed {
                background-color: #dc2626;
                border-color: #dc2626;
            }
        """)
        self.delete_button.setToolTip("Delete this focus area")
        self.delete_button.clicked.connect(self.on_delete_clicked)
        layout.addWidget(self.delete_button)

        # Styling
        self.setStyleSheet("""
            FocusAreaItem {
                background-color: #111827;
                border: 1px solid #374151;
                border-radius: 8px;
                margin: 2px;
            }
            FocusAreaItem:hover {
                background-color: #1f2937;
                border-color: #4b5563;
            }
        """)

        # Make draggable
        self.setAcceptDrops(True)

    def on_delete_clicked(self):
        """Handle delete button click."""
        self.delete_requested.emit(self.area.id)

    def mousePressEvent(self, event):
        """Handle mouse press for drag initiation."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is on drag handle
            if self.drag_handle and self.drag_handle.geometry().contains(event.pos()):
                self.start_drag(event)
        super().mousePressEvent(event)

    def start_drag(self, event):
        """Start drag operation."""
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.area.id)
        drag.setMimeData(mime_data)

        # Create a simple drag pixmap instead of rendering the entire widget
        pixmap = QPixmap(200, 40)
        pixmap.fill(QColor(240, 240, 240, 200))  # Light gray with transparency

        painter = QPainter(pixmap)
        painter.setPen(QColor(0, 0, 0))
        painter.setFont(self.font())
        painter.drawText(10, 25, f"{self.area.name}")
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle drop event for reordering."""
        if event.mimeData().hasText():
            dragged_id = event.mimeData().text()

            # Find the parent widget to handle reordering
            parent_widget = self.parent()
            while parent_widget and not isinstance(parent_widget, FocusAreasWidget):
                parent_widget = parent_widget.parent()

            if parent_widget:
                # Find source and target positions
                source_index = None
                target_index = None

                for i, area in enumerate(parent_widget.focus_areas):
                    if area.id == dragged_id:
                        source_index = i
                    if area.id == self.area.id:
                        target_index = i

                if source_index is not None and target_index is not None and source_index != target_index:
                    # Reorder the areas
                    source_area = parent_widget.focus_areas.pop(source_index)
                    parent_widget.focus_areas.insert(target_index, source_area)

                    # Update priorities
                    parent_widget.update_priorities()
                    parent_widget.create_focus_items()

                    # Emit change signal
                    parent_widget.focus_areas_changed.emit(parent_widget.focus_areas.copy())

            event.accept()


class AddFocusAreaDialog(QDialog):
    """Dialog for adding a new focus area."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Focus Area")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Name field (mandatory)
        name_layout = QHBoxLayout()
        name_label = QLabel("Name:")
        name_label.setMinimumWidth(100)
        
        # Add mandatory indicator and help icon
        name_header_layout = QHBoxLayout()
        name_title = QLabel("Name:")
        name_title.setMinimumWidth(80)
        mandatory_label = QLabel("*")
        mandatory_label.setStyleSheet("color: #ef4444; font-weight: bold;")
        name_header_layout.addWidget(name_title)
        name_header_layout.addWidget(mandatory_label)
        name_header_layout.addStretch()
        
        help_icon = HelpIcon("Unique display name for this focus area (e.g., 'Privacy Policy', 'Permission Requests')")
        name_header_layout.addWidget(help_icon)
        
        name_header_widget = QWidget()
        name_header_widget.setLayout(name_header_layout)
        
        name_layout.addWidget(name_header_widget)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Privacy Policy")
        self.name_input.textChanged.connect(self.on_name_changed)
        self.name_input.textChanged.connect(self.validate_form)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Description field (mandatory)
        desc_layout = QVBoxLayout()
        desc_header_layout = QHBoxLayout()
        desc_title = QLabel("Description:")
        desc_mandatory = QLabel("*")
        desc_mandatory.setStyleSheet("color: #ef4444; font-weight: bold;")
        desc_header_layout.addWidget(desc_title)
        desc_header_layout.addWidget(desc_mandatory)
        desc_header_layout.addStretch()
        
        desc_help_icon = HelpIcon(
            "Describe what UI elements or behaviors this focus area should target. "
            "This will be used to generate AI instructions."
        )
        desc_header_layout.addWidget(desc_help_icon)
        
        desc_header_widget = QWidget()
        desc_header_widget.setLayout(desc_header_layout)
        desc_layout.addWidget(desc_header_widget)
        
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText(
            "e.g., Check for privacy-related UI elements such as privacy policies, "
            "data collection notices, permission requests, consent toggles, "
            "or privacy settings that the app uses to collect user information."
        )
        self.desc_input.setMaximumHeight(80)
        self.desc_input.textChanged.connect(self.on_description_changed)
        self.desc_input.textChanged.connect(self.validate_form)
        desc_layout.addWidget(self.desc_input)
        layout.addLayout(desc_layout)
        
        # Prompt Modifier field (optional)
        prompt_layout = QVBoxLayout()
        prompt_header_layout = QHBoxLayout()
        prompt_title = QLabel("Prompt Modifier:")
        prompt_header_layout.addWidget(prompt_title)
        prompt_header_layout.addStretch()
        
        prompt_help_icon = HelpIcon(
            "Custom AI instructions for this focus area. "
            "Auto-generated from name and description, but you can customize it."
        )
        prompt_header_layout.addWidget(prompt_help_icon)
        
        prompt_header_widget = QWidget()
        prompt_header_widget.setLayout(prompt_header_layout)
        prompt_layout.addWidget(prompt_header_widget)
        
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("(Auto-generated from description - edit if needed)")
        self.prompt_input.setMaximumHeight(100)
        self.prompt_input.setReadOnly(False)
        prompt_layout.addWidget(self.prompt_input)
        layout.addLayout(prompt_layout)
        
        # Priority field (optional)
        priority_layout = QHBoxLayout()
        priority_header_layout = QHBoxLayout()
        priority_title = QLabel("Priority:")
        priority_title.setMinimumWidth(80)
        priority_header_layout.addWidget(priority_title)
        priority_header_layout.addStretch()
        
        priority_help_icon = HelpIcon("Lower numbers appear first in the list. Default: 999")
        priority_header_layout.addWidget(priority_help_icon)
        
        priority_header_widget = QWidget()
        priority_header_widget.setLayout(priority_header_layout)
        
        priority_layout.addWidget(priority_header_widget)
        self.priority_input = QSpinBox()
        self.priority_input.setMinimum(0)
        self.priority_input.setMaximum(9999)
        self.priority_input.setValue(999)
        priority_layout.addWidget(self.priority_input)
        priority_layout.addStretch()
        layout.addLayout(priority_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        # Change button text from "OK" to "Add"
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setText("Add")
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Store reference to OK button for enabling/disabling
        self.ok_button = ok_button
        
        # Initial validation
        self.validate_form()
    
    def get_data(self) -> Dict[str, Any]:
        """Get the entered focus area data. ID is auto-generated from name."""
        name = self.name_input.text().strip()
        # Auto-generate ID from name: lowercase, replace spaces with underscores
        auto_id = name.lower().replace(" ", "_").replace("-", "_")
        
        return {
            "id": auto_id,
            "name": name,
            "description": self.desc_input.toPlainText().strip(),
            "prompt_modifier": self.prompt_input.toPlainText().strip(),
            "priority": self.priority_input.value(),
        }
    
    def on_name_changed(self):
        """Handle name field changes to update prompt modifier."""
        # This is called when name changes, but we don't auto-update prompt here
        pass
    
    def on_description_changed(self):
        """Handle description field changes to auto-generate prompt modifier."""
        description = self.desc_input.toPlainText().strip()
        
        # Only auto-generate if description has content and prompt is empty
        if description and not self.prompt_input.toPlainText().strip():
            name = self.name_input.text().strip()
            if name:
                # Auto-generate prompt modifier from name and description
                auto_prompt = f"**FOCUS: {name}** - {description}"
                self.prompt_input.setText(auto_prompt)
    
    def validate_form(self):
        """Validate form and enable/disable OK button based on required fields."""
        name = self.name_input.text().strip()
        description = self.desc_input.toPlainText().strip()
        
        # Both Name and Description are required
        is_valid = bool(name and description)
        
        # Enable/disable OK button
        if self.ok_button:
            self.ok_button.setEnabled(is_valid)


class FocusAreasWidget(QWidget):
    """Widget for managing focus areas with drag-and-drop reordering."""

    focus_areas_changed = Signal(list)  # Emitted when focus areas change
    add_focus_area_requested = Signal()  # Emitted when user wants to add a focus area

    def __init__(self, focus_areas_data=None, parent=None, focus_service=None):
        super().__init__(parent)
        self.focus_service = focus_service
        # Convert data to FocusArea objects if needed
        if focus_areas_data:
            self.focus_areas = []
            for item in focus_areas_data:
                if isinstance(item, dict):
                    # Convert dict to FocusArea object
                    area = FocusArea(
                        id=item.get('id', ''),
                        name=item.get('name', ''),
                        description=item.get('description', ''),
                        prompt_modifier=item.get('prompt_modifier', ''),
                        enabled=item.get('enabled', True),
                        priority=item.get('priority', 0)
                    )
                    self.focus_areas.append(area)
                elif isinstance(item, FocusArea):
                    # Already a FocusArea object
                    self.focus_areas.append(item)
                else:
                    logging.warning(f"Invalid focus area data type: {type(item)}")
        else:
            # No data provided - use empty list
            # Database-backed focus areas should be loaded by caller and passed in
            self.focus_areas = []
        
        self.focus_items = []
        self.setup_ui()

    def setup_ui(self):
        """Setup the main UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("AI Privacy Focus Areas")
        title_label.setStyleSheet("font-weight: 600; font-size: 14px; color: #e5e7eb;")
        header_layout.addWidget(title_label)

        # Orderable list hint
        orderable_hint = QLabel("↕ Drag to reorder")
        orderable_hint.setToolTip("You can drag items to change their priority order.")
        orderable_hint.setStyleSheet("color: #9ca3af; font-size: 10px; padding-left: 8px;")
        header_layout.addWidget(orderable_hint)

        header_layout.addStretch()

        # Add button
        add_btn = QPushButton("+ Add Focus Area")
        add_btn.setStyleSheet("font-size: 10px; padding: 3px 8px;")
        add_btn.clicked.connect(self.show_add_dialog)
        header_layout.addWidget(add_btn)

        # Enable All button
        enable_all_btn = QPushButton("Enable All")
        enable_all_btn.setStyleSheet("font-size: 10px; padding: 3px 8px;")
        enable_all_btn.clicked.connect(self.enable_all_focus_areas)
        header_layout.addWidget(enable_all_btn)

        disable_all_btn = QPushButton("Disable All")
        disable_all_btn.setStyleSheet("font-size: 10px; padding: 3px 8px;")
        disable_all_btn.clicked.connect(self.disable_all_focus_areas)
        header_layout.addWidget(disable_all_btn)

        layout.addLayout(header_layout)

        # Description
        desc_label = QLabel(
            "Configure what privacy aspects the AI agent should focus on during exploration.\n"
            "Drag items to reorder priority, toggle checkboxes to enable/disable."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #9ca3af; font-size: 11px; margin-bottom: 10px;")
        layout.addWidget(desc_label)

        # Scrollable area for focus items
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setMinimumHeight(300)  
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #374151;
                border-radius: 6px;
                background-color: #1f2937;
            }
        """)

        # Container for focus items - make it accept drops
        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setSpacing(3)
        self.items_layout.setContentsMargins(5, 5, 5, 5)

        # Make the container accept drops
        self.items_container.setAcceptDrops(True)

        # Create focus area items
        self.create_focus_items()

        scroll_area.setWidget(self.items_container)
        layout.addWidget(scroll_area)

        # Statistics footer
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #9ca3af; font-size: 10px; margin-top: 5px;")
        layout.addWidget(self.stats_label)

        self.update_stats()

        # Make the widget accept drops for fallback
        self.setAcceptDrops(True)

    def create_focus_items(self):
        """Create focus area items and add them to the layout."""
        # Clear existing items and stretch
        while self.items_layout.count() > 0:
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.focus_items.clear()

        # Sort by priority
        sorted_areas = sorted(self.focus_areas, key=lambda x: x.priority)

        # Create new items
        for area in sorted_areas:
            item = FocusAreaItem(area)
            if item.checkbox:  # Safety check
                item.checkbox.stateChanged.connect(self.on_focus_area_toggled)
            # Connect delete signal
            item.delete_requested.connect(self.on_delete_focus_area)
            self.focus_items.append(item)
            self.items_layout.addWidget(item)

        # If no focus areas, show empty state
        if not self.focus_items:
            empty_label = QLabel("No focus areas added yet.\nClick '+ Add Focus Area' to get started.")
            empty_label.setStyleSheet("color: #9ca3af; font-size: 11px; text-align: center;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.items_layout.addWidget(empty_label)
        else:
            # Add stretch at bottom only if there are items
            self.items_layout.addStretch()

        # Update priority labels
        self.update_priority_labels()

    def update_priority_labels(self):
        """Update priority number labels for all items."""
        for i, item in enumerate(self.focus_items):
            # Find the priority label in the layout
            priority_layout = item.layout().itemAt(0).widget().layout()
            priority_label = priority_layout.itemAt(0).widget()
            priority_label.setText(str(i + 1))

    def on_focus_area_toggled(self):
        """Handle focus area enable/disable toggle."""
        # Update the focus areas data
        for item in self.focus_items:
            if item.checkbox:  # Safety check
                for area in self.focus_areas:
                    if area.id == item.area.id:
                        area.enabled = item.checkbox.isChecked()
                        break

        self.update_stats()
        self.focus_areas_changed.emit(self.focus_areas.copy())

    def on_delete_focus_area(self, area_id: str):
        """Handle focus area deletion."""
        # Remove from local list
        self.focus_areas = [area for area in self.focus_areas if area.id != area_id]
        
        # Remove from service if available
        if self.focus_service:
            try:
                success = self.focus_service.remove_focus_area(area_id)
                if not success:
                    logging.error(f"Failed to delete focus area {area_id} from service")
            except Exception as e:
                logging.error(f"Error deleting focus area {area_id}: {e}")
        
        # Refresh UI
        self.update_priorities()
        self.create_focus_items()
        self.update_stats()
        self.focus_areas_changed.emit(self.focus_areas.copy())

    def enable_all_focus_areas(self):
        """Enable all focus areas."""
        for item in self.focus_items:
            if item.checkbox:  # Safety check
                item.checkbox.setChecked(True)
        self.on_focus_area_toggled()

    def disable_all_focus_areas(self):
        """Disable all focus areas."""
        for item in self.focus_items:
            if item.checkbox:  # Safety check
                item.checkbox.setChecked(False)
        self.on_focus_area_toggled()

    def update_stats(self):
        """Update the statistics display."""
        enabled_count = sum(1 for area in self.focus_areas if area.enabled)
        total_count = len(self.focus_areas)

        if enabled_count == 0:
            self.stats_label.setText("No focus areas enabled")
            self.stats_label.setStyleSheet("color: #dc3545; font-size: 10px; margin-top: 5px;")
        else:
            self.stats_label.setText(f"{enabled_count}/{total_count} focus areas enabled")
            self.stats_label.setStyleSheet("color: #1e40af; font-size: 10px; margin-top: 5px;")

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle drop event for reordering."""
        source_id = event.mimeData().text()

        # Find target position by checking which item the drop occurred on
        target_pos = None
        drop_pos = event.position().toPoint()

        # Convert drop position to items_container coordinates
        container_pos = self.items_container.mapFrom(self, drop_pos)

        for i, item in enumerate(self.focus_items):
            # Check if drop is within this item's bounds
            item_rect = item.geometry()
            if item_rect.contains(container_pos):
                target_pos = i
                break

        # If no specific item was targeted, find the closest position
        if target_pos is None:
            for i, item in enumerate(self.focus_items):
                item_center_y = item.geometry().center().y()
                if container_pos.y() < item_center_y:
                    target_pos = i
                    break
            else:
                target_pos = len(self.focus_items)

        if target_pos is not None:
            # Find source area
            source_area = None
            source_index = None
            for i, area in enumerate(self.focus_areas):
                if area.id == source_id:
                    source_area = area
                    source_index = i
                    break

            if source_area and source_index is not None:
                # Reorder the list
                self.focus_areas.pop(source_index)
                self.focus_areas.insert(target_pos, source_area)

                # Update priorities and refresh display
                self.update_priorities()
                self.create_focus_items()

                # Emit change signal
                self.focus_areas_changed.emit(self.focus_areas.copy())

        event.accept()

    def update_priorities(self):
        """Update priority numbers for all items."""
        for i, area in enumerate(self.focus_areas):
            area.priority = i
        self.update_priority_labels()

    def get_enabled_focus_areas(self) -> List[FocusArea]:
        """Get list of enabled focus areas."""
        return [area for area in self.focus_areas if area.enabled]

    def show_add_dialog(self):
        """Show dialog to add a new focus area."""
        dialog = AddFocusAreaDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            
            # Validate required fields (only Name is user-provided, ID is auto-generated)
            if not data['name']:
                logging.warning("Name is required")
                return
            
            # Add to service if available
            if self.focus_service:
                try:
                    success = self.focus_service.add_focus_area(
                        id_or_name=data['id'],
                        title=data['name'],
                        description=data['description'],
                        prompt_modifier=data['prompt_modifier'],
                        priority=data['priority'],
                        enabled=True
                    )
                    if success:
                        # Reload focus areas from service
                        self.reload_focus_areas()
                    else:
                        logging.error("Failed to add focus area via service")
                except Exception as e:
                    logging.error(f"Error adding focus area: {e}")
            else:
                # Add directly if no service (for backward compatibility)
                new_area = FocusArea(
                    id=data['id'],
                    name=data['name'],
                    description=data['description'],
                    prompt_modifier=data['prompt_modifier'],
                    enabled=True,
                    priority=data['priority']
                )
                self.focus_areas.append(new_area)
                self.update_priorities()
                self.create_focus_items()
                self.focus_areas_changed.emit(self.focus_areas.copy())
    
    def reload_focus_areas(self):
        """Reload focus areas from service."""
        if self.focus_service:
            try:
                areas_data = self.focus_service.get_focus_areas()
                self.focus_areas = []
                for item in areas_data:
                    if isinstance(item, dict):
                        area = FocusArea(
                            id=item.get('id', ''),
                            name=item.get('name', ''),
                            description=item.get('description', ''),
                            prompt_modifier=item.get('prompt_modifier', ''),
                            enabled=item.get('enabled', True),
                            priority=item.get('priority', 0)
                        )
                        self.focus_areas.append(area)
                    elif isinstance(item, FocusArea):
                        self.focus_areas.append(item)
                
                self.update_priorities()
                self.create_focus_items()
                self.focus_areas_changed.emit(self.focus_areas.copy())
            except Exception as e:
                logging.error(f"Error reloading focus areas: {e}")

    def get_focus_area_by_id(self, area_id: str) -> Optional[FocusArea]:
        """Get focus area by ID."""
        for area in self.focus_areas:
            if area.id == area_id:
                return area
        return None
