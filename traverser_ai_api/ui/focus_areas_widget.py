# ui/focus_areas_widget.py - Widget for managing privacy-focused focus areas

import logging
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QScrollArea, QFrame, QPushButton, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QPixmap, QPainter, QColor, QDrag
from dataclasses import dataclass


@dataclass
class FocusArea:
    """Represents a focus area for AI agent behavior."""
    id: str
    name: str
    description: str
    prompt_modifier: str
    enabled: bool = True
    priority: int = 0


# Default privacy-focused focus areas
DEFAULT_PRIVACY_FOCUS_AREAS = [
    FocusArea(
        id="privacy_policy",
        name="Privacy Policies & Terms",
        description="Prioritize exploring privacy policies, terms of service, and data usage disclosures",
        prompt_modifier="**PRIVACY FOCUS: Policy Documents** - Actively seek out and thoroughly explore privacy policies, terms of service, data processing agreements, and any legal documents. Read and analyze all privacy-related content for data collection practices, third-party sharing, and user rights."
    ),
    FocusArea(
        id="permissions",
        name="App Permissions",
        description="Focus on permission requests and privacy settings",
        prompt_modifier="**PRIVACY FOCUS: Permissions** - Pay special attention to permission requests (location, camera, microphone, contacts, storage, phone). Test how the app handles permission denials and privacy settings. Look for granular permission controls."
    ),
    FocusArea(
        id="data_collection",
        name="Data Collection Forms",
        description="Prioritize forms that collect personal information",
        prompt_modifier="**PRIVACY FOCUS: Data Collection** - Focus on forms and input fields that collect personal data (name, email, phone, address, payment info, health data). Test data validation, storage indications, and sharing disclosures. Look for data minimization practices."
    ),
    FocusArea(
        id="third_party",
        name="Third-Party Integrations",
        description="Identify and analyze third-party services and trackers",
        prompt_modifier="**PRIVACY FOCUS: Third-Party Services** - Look for integrations with analytics services, advertising networks, social media platforms, and other third-party services. Note any data sharing with external companies and tracking mechanisms."
    ),
    FocusArea(
        id="network_requests",
        name="Network Communications",
        description="Monitor and analyze app's network requests and data transmission",
        prompt_modifier="**PRIVACY FOCUS: Network Activity** - Be alert to network requests and data transmissions. Look for API calls, data uploads, and server communications. Identify what data is being sent to which servers and for what purposes."
    ),
    FocusArea(
        id="account_privacy",
        name="Account & Profile Privacy",
        description="Focus on account creation, profile data, and privacy controls",
        prompt_modifier="**PRIVACY FOCUS: Account Privacy** - Examine account creation processes, profile data collection, and privacy control options. Test data sharing settings, account deletion processes, and privacy dashboard features."
    ),
    FocusArea(
        id="advertising_tracking",
        name="Advertising & Tracking",
        description="Identify advertising networks and tracking mechanisms",
        prompt_modifier="**PRIVACY FOCUS: Advertising & Tracking** - Look for advertising networks, tracking pixels, and behavioral data collection. Find opt-out mechanisms, ad personalization controls, and tracking consent options."
    ),
    FocusArea(
        id="data_rights",
        name="Data Subject Rights",
        description="Focus on GDPR/CCPA compliance and user data rights",
        prompt_modifier="**PRIVACY FOCUS: Data Rights** - Search for data export options, account deletion features, data portability tools, and consent management. Test compliance with data protection regulations and user rights."
    ),
    FocusArea(
        id="security_features",
        name="Security & Authentication",
        description="Analyze security measures and authentication methods",
        prompt_modifier="**PRIVACY FOCUS: Security Measures** - Examine authentication methods, encryption indicators, security settings, and data protection measures. Look for secure data transmission (HTTPS) and proper credential handling."
    ),
    FocusArea(
        id="location_tracking",
        name="Location & Device Data",
        description="Focus on location services and device data collection",
        prompt_modifier="**PRIVACY FOCUS: Location & Device Data** - Pay attention to location services, device identifiers, sensor data collection, and background tracking. Test location permission handling and data retention policies."
    )
]


class FocusAreaItem(QWidget):
    """Draggable item representing a single focus area."""

    def __init__(self, area: FocusArea, parent=None):
        super().__init__(parent)
        self.area = area
        self.checkbox = None
        self.drag_handle = None
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

        # Drag handle
        self.drag_handle = QLabel("⋮⋮")
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


class FocusAreasWidget(QWidget):
    """Widget for managing focus areas with drag-and-drop reordering."""

    focus_areas_changed = Signal(list)  # Emitted when focus areas change

    def __init__(self, focus_areas_data=None, parent=None):
        super().__init__(parent)
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
            self.focus_areas = DEFAULT_PRIVACY_FOCUS_AREAS.copy()
        
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

        # Quick action buttons
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
        # Clear existing items
        for item in self.focus_items:
            self.items_layout.removeWidget(item)
            item.hide()
        self.focus_items.clear()

        # Sort by priority
        sorted_areas = sorted(self.focus_areas, key=lambda x: x.priority)

        # Create new items
        for area in sorted_areas:
            item = FocusAreaItem(area)
            if item.checkbox:  # Safety check
                item.checkbox.stateChanged.connect(self.on_focus_area_toggled)
            self.focus_items.append(item)
            self.items_layout.addWidget(item)

        # Update priority labels
        self.update_priority_labels()

        # Add stretch at bottom
        self.items_layout.addStretch()

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

    def get_focus_area_by_id(self, area_id: str) -> Optional[FocusArea]:
        """Get focus area by ID."""
        for area in self.focus_areas:
            if area.id == area_id:
                return area
        return None
