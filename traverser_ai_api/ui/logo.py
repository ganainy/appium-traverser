#!/usr/bin/env python3
# ui/logo.py - Logo widget for the Appium Crawler UI

import os
import logging
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt


class LogoWidget(QLabel):
    """A widget to display the app logo."""

    def __init__(self, parent=None, logo_width=200, logo_height=80):
        """
        Initialize the logo widget.
        
        Args:
            parent: Parent widget
            logo_width: Desired width of the logo
            logo_height: Desired height of the logo
        """
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_width = logo_width
        self.logo_height = logo_height
        
    def load_logo(self, base_dir=None):
        """
        Load the logo from the project directory.
        
        Args:
            base_dir: Base directory of the project. If None, will try to determine it.
            
        Returns:
            bool: True if logo was loaded successfully, False otherwise.
        """
        try:
            # If base_dir not provided, find it dynamically
            if base_dir is None:
                # Get the directory of this script
                current_dir = os.path.dirname(os.path.abspath(__file__))
                # Go up to the project root (2 levels up from ui folder)
                base_dir = os.path.dirname(os.path.dirname(current_dir))
            
            # Logo is located at the project root
            logo_path = os.path.join(base_dir, "crawler_logo.png")
            
            if os.path.exists(logo_path):
                logging.info(f"Loading logo from: {logo_path}")
                pixmap = QPixmap(logo_path)
                scaled_pixmap = pixmap.scaled(
                    self.logo_width, self.logo_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.setPixmap(scaled_pixmap)
                return True
            else:
                logging.warning(f"Logo file not found at: {logo_path}")
                self.setText("Appium Traverser")
                return False
        except Exception as e:
            logging.error(f"Failed to load logo: {e}")
            self.setText("Appium Traverser")
            return False
            
    @staticmethod
    def get_logo_path(base_dir=None):
        """
        Get the path to the logo file.
        
        Args:
            base_dir: Base directory of the project. If None, will try to determine it.
            
        Returns:
            str: Path to the logo file, or None if not found.
        """
        try:
            # If base_dir not provided, find it dynamically
            if base_dir is None:
                # Get the directory of this script
                current_dir = os.path.dirname(os.path.abspath(__file__))
                # Go up to the project root (2 levels up from ui folder)
                base_dir = os.path.dirname(os.path.dirname(current_dir))
            
            # Logo is located at the project root
            logo_path = os.path.join(base_dir, "crawler_logo.png")
            
            if os.path.exists(logo_path):
                return logo_path
            else:
                logging.warning(f"Logo file not found at: {logo_path}")
                return None
        except Exception as e:
            logging.error(f"Failed to get logo path: {e}")
            return None
            
    @staticmethod
    def get_icon(base_dir=None):
        """
        Create a QIcon from the logo file.
        
        Args:
            base_dir: Base directory of the project. If None, will try to determine it.
            
        Returns:
            QIcon: Icon created from the logo, or None if logo not found.
        """
        logo_path = LogoWidget.get_logo_path(base_dir)
        if logo_path:
            try:
                return QIcon(logo_path)
            except Exception as e:
                logging.error(f"Failed to create icon from logo: {e}")
        return None
