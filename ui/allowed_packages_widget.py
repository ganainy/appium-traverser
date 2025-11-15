#!/usr/bin/env python3
"""
GUI widget for managing allowed external packages with full CRUD support.
"""

import logging
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, 
    QMessageBox, QDialog, QFormLayout, QScrollArea, QFrame, QCheckBox
)
from PySide6.QtCore import Qt, Signal


class PackageItemWidget(QWidget):
    """Widget for displaying a single package with delete icon and checkbox."""
    
    delete_clicked = Signal(str)  # Emitted with package name when delete is clicked
    enabled_changed = Signal(str, bool)  # Emitted with package name and enabled state
    
    def __init__(self, package_name: str, enabled: bool = True, parent=None):
        super().__init__(parent)
        self.package_name = package_name
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # Delete button (icon before checkbox)
        self.delete_btn = QPushButton("×")
        self.delete_btn.setFixedSize(20, 20)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6b6b;
            }
        """)
        self.delete_btn.setToolTip(f"Remove {package_name}")
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.package_name))
        layout.addWidget(self.delete_btn)
        
        # Checkbox for enable/disable
        self.checkbox = QCheckBox(package_name)
        self.checkbox.setChecked(enabled)
        self.checkbox.setStyleSheet("color: white;")
        self.checkbox.setToolTip(f"Enable/disable {package_name}")
        self.checkbox.stateChanged.connect(
            lambda state: self.enabled_changed.emit(self.package_name, state == 2)
        )
        layout.addWidget(self.checkbox)
        
        layout.addStretch()
    
    def set_enabled(self, enabled: bool):
        """Set the enabled state of the checkbox."""
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(enabled)
        self.checkbox.blockSignals(False)
    
    def is_enabled(self) -> bool:
        """Get the enabled state of the checkbox."""
        return self.checkbox.isChecked()


class AllowedPackagesWidget(QWidget):
    """
    Widget for managing allowed external packages with CRUD operations.
    
    Provides a user-friendly interface matching the AvailableActionsWidget style
    with inline delete buttons for each package.
    """
    
    packages_changed = Signal(list)  # Emitted when packages list changes
    
    def __init__(self, config, parent=None):
        """
        Initialize the packages widget.
        
        Args:
            config: Configuration object
            parent: Parent widget
        """
        super().__init__(parent)
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Import here to avoid circular imports
        from core.packages_crud import AllowedPackagesService
        from infrastructure.allowed_packages_adapter import AllowedPackagesAdapter
        
        adapter = AllowedPackagesAdapter(config, self.logger)
        self.manager = AllowedPackagesService(adapter, self.logger)
        
        # Store package item widgets
        self.package_items: dict[str, PackageItemWidget] = {}
        # Track enabled state for each package (default: all enabled)
        self.package_enabled: dict[str, bool] = {}
        
        self.init_ui()
        self.load_packages()
    
    def init_ui(self):
        """Initialize the user interface."""
        # Set grey background to match UI
        self.setStyleSheet("background-color: #333333;")
        
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
        self.content_widget.setStyleSheet("background-color: #333333;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(2)
        self.content_layout.addStretch()  # Add stretch at the end
        
        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)
        
        # Bottom section with Add button and counter
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        bottom_layout.setSpacing(5)
        
        # Add button
        self.add_btn = QPushButton("Add")
        self.add_btn.setMinimumWidth(70)
        self.add_btn.clicked.connect(self._on_add_clicked)
        bottom_layout.addWidget(self.add_btn)
        
        bottom_layout.addStretch()
        
        # Counter label (subtle, bottom right)
        self.count_label = QLabel("Total: 0 packages")
        self.count_label.setStyleSheet("font-size: 11px; color: #888888;")
        bottom_layout.addWidget(self.count_label)
        
        layout.addLayout(bottom_layout)
        
        # Set minimum height
        self.setMinimumHeight(120)
        self.setMaximumHeight(180)
    
    def load_packages(self):
        """Load packages from configuration and populate the list."""
        try:
            packages = self.manager.get_all()
            self._populate_list(packages)
        except Exception as e:
            self.logger.error(f"Failed to load packages: {e}")
            self._clear_package_items()
    
    def _populate_list(self, packages: List[str]):
        """
        Populate the widget with package items.
        
        Args:
            packages: List of package names
        """
        # Clear existing items
        self._clear_package_items()
        
        # Create items for each package (all enabled by default when loading)
        for package in packages:
            # Preserve enabled state if package was already loaded, otherwise default to True
            enabled = self.package_enabled.get(package, True)
            self._add_package_item(package, enabled=enabled)
        
        self._update_count_label()
    
    def _add_package_item(self, package_name: str, enabled: bool = True):
        """Add a package item widget to the list."""
        if package_name in self.package_items:
            return  # Already exists
        
        # Store enabled state
        self.package_enabled[package_name] = enabled
        
        item_widget = PackageItemWidget(package_name, enabled, self.content_widget)
        item_widget.delete_clicked.connect(self._on_delete_package)
        item_widget.enabled_changed.connect(self._on_package_enabled_changed)
        
        # Insert before the stretch
        self.content_layout.insertWidget(self.content_layout.count() - 1, item_widget)
        self.package_items[package_name] = item_widget
    
    def _remove_package_item(self, package_name: str):
        """Remove a package item widget from the list."""
        if package_name not in self.package_items:
            return
        
        item_widget = self.package_items[package_name]
        item_widget.setParent(None)
        item_widget.deleteLater()
        del self.package_items[package_name]
        # Also remove from enabled state tracking
        if package_name in self.package_enabled:
            del self.package_enabled[package_name]
    
    def _clear_package_items(self):
        """Clear all package item widgets."""
        for item_widget in self.package_items.values():
            item_widget.setParent(None)
            item_widget.deleteLater()
        self.package_items.clear()
        self.package_enabled.clear()
    
    def _update_count_label(self):
        """Update the count label to show total packages."""
        total_count = len(self.package_items)
        enabled_count = sum(1 for enabled in self.package_enabled.values() if enabled)
        if enabled_count == total_count:
            self.count_label.setText(f"Total: {total_count} package{'s' if total_count != 1 else ''}")
        else:
            self.count_label.setText(f"Total: {total_count} ({enabled_count} enabled)")
    
    def _on_delete_package(self, package_name: str):
        """Handle delete button click on a package item."""
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove package: {package_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.manager.remove(package_name):
                self._remove_package_item(package_name)
                self._update_count_label()
                self.packages_changed.emit(self.get_packages())
                logging.info(f"Removed package: {package_name}")
            else:
                QMessageBox.warning(self, "Error", f"Failed to remove package: {package_name}")
    
    def _on_package_enabled_changed(self, package_name: str, enabled: bool):
        """Handle checkbox state change for a package."""
        self.package_enabled[package_name] = enabled
        self._update_count_label()
        self.packages_changed.emit(self.get_packages())
        logging.debug(f"Package {package_name} {'enabled' if enabled else 'disabled'}")
    
    def _on_add_clicked(self):
        """Handle add button click."""
        dialog = PackageInputDialog(self, "Add Package", "")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            package_name = dialog.get_value()
            if package_name:
                if self.manager.add(package_name):
                    # Add with enabled=True by default
                    self._add_package_item(package_name, enabled=True)
                    self._update_count_label()
                    self.packages_changed.emit(self.get_packages())
                    logging.info(f"Added package: {package_name}")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to add package: {package_name}")
    
    def get_packages(self) -> List[str]:
        """
        Get current list of enabled packages.
        
        Returns:
            List of enabled package names
        """
        # Return only enabled packages
        return [pkg for pkg, enabled in self.package_enabled.items() if enabled]
    
    def set_packages(self, packages: List[str]):
        """
        Set the list of packages (all will be enabled by default).
        
        Args:
            packages: List of package names
        """
        if self.manager.set_all(packages):
            # Reload and mark all as enabled
            self.load_packages()
            # Ensure all loaded packages are marked as enabled
            for package_name in packages:
                if package_name in self.package_items:
                    self.package_enabled[package_name] = True
                    self.package_items[package_name].set_enabled(True)
            self._update_count_label()
            self.packages_changed.emit(self.get_packages())
        else:
            self.logger.error("Failed to set packages")


class PackageInputDialog(QDialog):
    """
    Dialog for adding/editing a single package name.
    
    Provides input validation for package names.
    """
    
    def __init__(self, parent=None, title: str = "Enter Package", initial_value: str = ""):
        """
        Initialize the input dialog.
        
        Args:
            parent: Parent widget
            title: Dialog title
            initial_value: Initial package name value
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.logger = logging.getLogger(__name__)
        
        layout = QFormLayout(self)
        
        # Input field
        self.input_field = QLineEdit()
        self.input_field.setText(initial_value)
        self.input_field.setPlaceholderText("e.g., com.example.app")
        layout.addRow("Package Name:", self.input_field)
        
        # Help text
        help_label = QLabel(
            "Valid format: lowercase letters, digits, underscores, and dots.\n"
            "Example: com.google.android.gms"
        )
        help_label.setStyleSheet("font-size: 10px; color: gray;")
        layout.addRow("", help_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok_clicked)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addRow("", button_layout)
        
        self.setLayout(layout)
        self.input_field.setFocus()
    
    def _on_ok_clicked(self):
        """Handle OK button click."""
        package_name = self.input_field.text().strip()
        
        if not package_name:
            QMessageBox.warning(self, "Error", "Package name cannot be empty.")
            return
        
        # Validate package name
        from core.packages_crud import AllowedPackagesService
        if not AllowedPackagesService._is_valid_package_name(package_name):
            QMessageBox.warning(
                self,
                "Invalid Format",
                "Invalid package name format.\nUse lowercase letters, digits, underscores, and dots."
            )
            return
        
        self.accept()
    
    def get_value(self) -> str:
        """
        Get the entered package name.
        
        Returns:
            Package name
        """
        return self.input_field.text().strip()
