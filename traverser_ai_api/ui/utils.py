#!/usr/bin/env python3
# ui/utils.py - Utility functions for the UI controller

import os
import logging
from typing import Optional
from PySide6.QtGui import QPixmap


def update_screenshot(screenshot_label, file_path: str) -> None:
    """
    Update the screenshot displayed in the UI.
    
    Args:
        screenshot_label: The QLabel to display the screenshot
        file_path: Path to the screenshot file
    """
    if not file_path or not os.path.exists(file_path):
        logging.error(f"Screenshot file not found: {file_path}")
        return
            
    try:
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            # Scale the pixmap to fit the label while maintaining aspect ratio
            label_size = screenshot_label.size()
            scaled_pixmap = pixmap.scaled(
                label_size.width(), 
                label_size.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            screenshot_label.setPixmap(scaled_pixmap)
        else:
            logging.error(f"Error loading screenshot: {file_path}")
    except Exception as e:
        logging.error(f"Error updating screenshot: {e}")


# Import here to avoid circular imports
from PySide6.QtCore import Qt
