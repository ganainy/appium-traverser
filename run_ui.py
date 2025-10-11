#!/usr/bin/env python3
"""
Entry point for running the Appium Crawler UI.
"""
import sys
from PyQt6.QtWidgets import QApplication
from traverser_ai_api.ui_controller import CrawlerControllerWindow
from traverser_ai_api.utils import LoggerManager

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CrawlerControllerWindow()

    # Set up logging with LoggerManager
    logger_manager = LoggerManager()

    # Set the UI controller reference in LoggerManager for colored logging BEFORE setup_logging
    logger_manager.set_ui_controller(window)

    logger_manager.setup_logging(log_level_str="INFO")

    # Start in full screen mode but allow resizing
    window.showMaximized()
    sys.exit(app.exec())