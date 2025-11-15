# ui/available_actions_widget.py - Widget for managing available crawler actions

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class AvailableActionsWidget(QWidget):
    """Widget for displaying and managing available crawler actions with checkboxes."""
    
    def __init__(self, actions_service: Optional[Any] = None, parent: Optional[QWidget] = None):
        """
        Initialize the available actions widget.
        
        Args:
            actions_service: Optional CrawlerActionsService instance for saving changes
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.actions_service = actions_service
        self.action_checkboxes: Dict[str, QCheckBox] = {}
        self.action_ids: Dict[str, int] = {}  # Map action name to action ID
        self.action_descriptions: Dict[str, str] = {}  # Map action name to description
        
        # Set grey background to match UI
        self.setStyleSheet("background-color: #333333;")
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create scroll area without border/frame
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)  # Remove border/frame
        self.scroll_area.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background-color: #333333;
            }
        """)  # Match UI grey background
        
        # Create content widget with grey background
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: #333333;")  # Match UI grey background
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(5)
        self.content_layout.addStretch()  # Add stretch at the end
        
        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)
        
        # Set minimum height
        self.setMinimumHeight(120)
        self.setMaximumHeight(180)
    
    def load_actions(self, actions: List[Dict[str, Any]], actions_service: Optional[Any] = None):
        """
        Load actions and create checkboxes for each.
        
        Args:
            actions: List of action dictionaries with 'name', 'description', 'enabled', and 'id' keys
            actions_service: Optional service to update (if not provided, uses existing service)
        """
        # Update service reference if provided
        if actions_service is not None:
            self.actions_service = actions_service
        
        # Clear existing checkboxes
        self._clear_checkboxes()
        
        if not actions:
            return
        
        # Create checkboxes for each action
        for action in actions:
            action_name = action.get('name', '')
            action_description = action.get('description', '')
            action_enabled = action.get('enabled', True)
            action_id = action.get('id')
            
            if not action_name:
                continue
            
            # Store action ID (always store, even if None, for debugging)
            self.action_ids[action_name] = action_id
            # Store description for potential auto-creation
            self.action_descriptions[action_name] = action_description
            if action_id is None:
                logging.debug(f"Action '{action_name}' loaded without ID - will need to create in DB when toggling")
            
            # Create checkbox with action name and description
            checkbox = QCheckBox()
            checkbox.setText(f"{action_name}: {action_description}")
            checkbox.setChecked(action_enabled)
            checkbox.setToolTip(f"Enable/disable the '{action_name}' action")
            
            # Connect checkbox state change to save handler
            # stateChanged signal passes an integer: 0 = Unchecked, 2 = Checked
            checkbox.stateChanged.connect(
                lambda state, name=action_name: self._on_action_toggled(name, state == 2)
            )
            
            # Store checkbox reference
            self.action_checkboxes[action_name] = checkbox
            
            # Add to layout (before the stretch)
            self.content_layout.insertWidget(self.content_layout.count() - 1, checkbox)
    
    def _clear_checkboxes(self):
        """Clear all checkboxes from the widget."""
        for checkbox in self.action_checkboxes.values():
            checkbox.setParent(None)
            checkbox.deleteLater()
        
        self.action_checkboxes.clear()
        self.action_ids.clear()
        self.action_descriptions.clear()
        
        # Remove all items except the stretch
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _on_action_toggled(self, action_name: str, enabled: bool):
        """
        Handle checkbox state change.
        
        Args:
            action_name: Name of the action
            enabled: New enabled state
        """
        if not self.actions_service:
            logging.warning("No actions service available to save action state")
            return
        
        try:
            # Get action ID from stored IDs
            # Actions should already exist in database (initialized on first launch)
            action_id = self.action_ids.get(action_name)
            
            if action_id is None:
                # Action not found - this shouldn't happen if initialization worked correctly
                logging.error(
                    f"Action '{action_name}' not found in database. "
                    f"Actions should have been initialized on first launch. "
                    f"Please restart the application."
                )
                # Revert checkbox state
                if action_name in self.action_checkboxes:
                    checkbox = self.action_checkboxes[action_name]
                    checkbox.blockSignals(True)
                    checkbox.setChecked(not enabled)
                    checkbox.blockSignals(False)
                return
            
            # Update action enabled state via service
            success, message = self.actions_service.edit_action(
                str(action_id),
                enabled=enabled
            )
            
            if success:
                logging.debug(f"Action '{action_name}' {'enabled' if enabled else 'disabled'}")
                # No need to reload - checkbox state is already correct and database is updated
                # Reloading would reset scroll position unnecessarily
            else:
                logging.error(f"Failed to update action '{action_name}': {message}")
                # Revert checkbox state on failure
                if action_name in self.action_checkboxes:
                    checkbox = self.action_checkboxes[action_name]
                    checkbox.blockSignals(True)
                    checkbox.setChecked(not enabled)
                    checkbox.blockSignals(False)
        except Exception as e:
            logging.error(f"Error updating action '{action_name}': {e}")
            # Revert checkbox state on error
            if action_name in self.action_checkboxes:
                checkbox = self.action_checkboxes[action_name]
                checkbox.blockSignals(True)
                checkbox.setChecked(not enabled)
                checkbox.blockSignals(False)
    
    def get_enabled_actions(self) -> Dict[str, str]:
        """
        Get dictionary of enabled actions (name -> description).
        
        Returns:
            Dictionary mapping enabled action names to descriptions
        """
        enabled_actions = {}
        for action_name, checkbox in self.action_checkboxes.items():
            if checkbox.isChecked():
                # Extract description from checkbox text
                text = checkbox.text()
                if ': ' in text:
                    description = text.split(': ', 1)[1]
                    enabled_actions[action_name] = description
        return enabled_actions

