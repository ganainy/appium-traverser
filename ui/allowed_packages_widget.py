#!/usr/bin/env python3
"""
GUI widget for managing allowed external packages with full CRUD support.
"""

import logging
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QMessageBox, QDialog, QFormLayout
)
from PySide6.QtCore import Qt, Signal


class AllowedPackagesWidget(QWidget):
    """
    Widget for managing allowed external packages with CRUD operations.
    
    Provides a user-friendly interface for add, remove, edit, and clear operations
    on the allowed external packages list.
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
        from core.allowed_packages_service import AllowedPackagesService
        from infrastructure.allowed_packages_adapter import AllowedPackagesAdapter
        
        adapter = AllowedPackagesAdapter(config, self.logger)
        self.manager = AllowedPackagesService(adapter, self.logger)
        
        self.init_ui()
        self.load_packages()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel("Allowed External Packages")
        title_font = title_label.font()
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(
            "Packages the crawler can interact with outside the main target app "
            "(e.g., for authentication, webviews). One package per line."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(desc_label)
        
        # List widget for displaying packages
        self.packages_list = QListWidget()
        self.packages_list.setMinimumHeight(150)
        self.packages_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.packages_list)
        
        # Count label
        count_layout = QHBoxLayout()
        self.count_label = QLabel("Total: 0 packages")
        self.count_label.setStyleSheet("font-size: 11px; color: gray;")
        count_layout.addWidget(self.count_label)
        count_layout.addStretch()
        layout.addLayout(count_layout)
        
        # Control buttons layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        
        # Add button
        self.add_btn = QPushButton("Add")
        self.add_btn.setMinimumWidth(70)
        self.add_btn.clicked.connect(self._on_add_clicked)
        button_layout.addWidget(self.add_btn)
        
        # Edit button
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setMinimumWidth(70)
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        button_layout.addWidget(self.edit_btn)
        
        # Remove button
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setMinimumWidth(70)
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        button_layout.addWidget(self.remove_btn)
        
        button_layout.addStretch()
        
        # Clear button (with warning styling)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setMinimumWidth(70)
        self.clear_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_packages(self):
        """Load packages from configuration and populate the list."""
        try:
            packages = self.manager.get_all()
            self._populate_list(packages)
        except Exception as e:
            self.logger.error(f"Failed to load packages: {e}")
            self.packages_list.clear()
    
    def _populate_list(self, packages: List[str]):
        """
        Populate the list widget with packages.
        
        Args:
            packages: List of package names
        """
        self.packages_list.clear()
        for package in packages:
            item = QListWidgetItem(package)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.packages_list.addItem(item)
        
        self._update_count_label()
    
    def _update_count_label(self):
        """Update the count label to show total packages."""
        count = self.packages_list.count()
        self.count_label.setText(f"Total: {count} package{'s' if count != 1 else ''}")
    
    def _on_selection_changed(self):
        """Handle list selection change."""
        has_selection = self.packages_list.currentItem() is not None
        self.edit_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection)
    
    def _on_add_clicked(self):
        """Handle add button click."""
        dialog = PackageInputDialog(self, "Add Package", "")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            package_name = dialog.get_value()
            if package_name:
                if self.manager.add(package_name):
                    self.load_packages()
                    self.packages_changed.emit(self.manager.get_all())
                    logging.info(f"Added package: {package_name}")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to add package: {package_name}")
    
    def _on_edit_clicked(self):
        """Handle edit button click."""
        current_item = self.packages_list.currentItem()
        if current_item:
            old_name = current_item.text()
            dialog = PackageInputDialog(self, "Edit Package", old_name)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_name = dialog.get_value()
                if new_name and new_name != old_name:
                    if self.manager.update(old_name, new_name):
                        self.load_packages()
                        self.packages_changed.emit(self.manager.get_all())
                        logging.info(f"Updated package: {old_name} -> {new_name}")
                    else:
                        QMessageBox.warning(self, "Error", f"Failed to update package: {old_name}")
    
    def _on_remove_clicked(self):
        """Handle remove button click."""
        current_item = self.packages_list.currentItem()
        if current_item:
            package_name = current_item.text()
            reply = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Remove package: {package_name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                if self.manager.remove(package_name):
                    self.load_packages()
                    self.packages_changed.emit(self.manager.get_all())
                    logging.info(f"Removed package: {package_name}")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to remove package: {package_name}")
    
    def _on_clear_clicked(self):
        """Handle clear all button click."""
        if self.packages_list.count() == 0:
            QMessageBox.information(self, "Info", "No packages to clear.")
            return
        
        reply = QMessageBox.warning(
            self,
            "Confirm Clear",
            "Clear all allowed external packages?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.manager.clear():
                self.load_packages()
                self.packages_changed.emit([])
                logging.info("Cleared all packages")
            else:
                QMessageBox.warning(self, "Error", "Failed to clear packages.")
    
    def get_packages(self) -> List[str]:
        """
        Get current list of packages.
        
        Returns:
            List of package names
        """
        return self.manager.get_all()
    
    def set_packages(self, packages: List[str]):
        """
        Set the list of packages.
        
        Args:
            packages: List of package names
        """
        if self.manager.set_all(packages):
            self.load_packages()
            self.packages_changed.emit(packages)
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
        from core.allowed_packages_service import AllowedPackagesService
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
