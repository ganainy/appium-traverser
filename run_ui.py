#!/usr/bin/env python3
"""
Entry point for running the Appium Crawler UI.

# Activate the virtual environment
& E:/VS-projects/appium-traverser-master-arbeit/.venv/Scripts/Activate.ps1

# Then run the UI
python run_ui.py
"""

import sys
import argparse
import os
from config.app_config import Config
try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    from ui.strings import RUN_UI_ERROR_PYSIDE6
    print(RUN_UI_ERROR_PYSIDE6)
    sys.exit(1)
from domain.ui_controller import CrawlerControllerWindow
from utils.utils import LoggerManager

def main():
    # Parse arguments first (but don't do heavy processing yet)
    parser = argparse.ArgumentParser(description="Appium Traverser")
    parser.add_argument("--provider", type=str, default=None, help="AI provider to use")
    parser.add_argument("--model", type=str, default=None, help="Model name/alias to use")
    args, unknown = parser.parse_known_args()
    
    # Create QApplication FIRST to enable GUI immediately
    # Save original argv for QApplication, then restore for later use
    original_argv = sys.argv[:]
    sys.argv = [sys.argv[0]] + unknown
    app = QApplication(sys.argv)
    app.setApplicationName("Appium Traverser")
    app.setApplicationDisplayName("Appium Traverser")
    
    # Show splash screen IMMEDIATELY - before any processing
    from ui.custom_widgets import LoadingSplashScreen
    import time
    
    splash = LoadingSplashScreen()
    
    # Center the splash screen on the screen
    screen = QApplication.primaryScreen().geometry()
    splash_rect = splash.geometry()
    splash_rect.moveCenter(screen.center())
    splash.move(splash_rect.topLeft())
    
    # Make splash screen visible immediately
    splash.show()
    splash.raise_()
    splash.activateWindow()
    splash.show_message("Starting...")
    # Force multiple processEvents to ensure splash is displayed
    for _ in range(5):
        app.processEvents()
    # Small delay to ensure splash is fully rendered and visible
    time.sleep(0.1)
    app.processEvents()
    
    splash.show_message("Loading configuration...")
    app.processEvents()
    
    config = Config()

    # Set provider if given
    provider = args.provider or os.environ.get("AI_PROVIDER") or config.get("AI_PROVIDER")
    if not provider:
        splash.show_message("Selecting AI provider...")
        app.processEvents()
        from domain.providers.registry import ProviderRegistry
        valid_providers = ProviderRegistry.get_all_names()
        from ui.strings import CLI_SELECT_PROVIDER_PROMPT
        provider = input(CLI_SELECT_PROVIDER_PROMPT.format(providers=', '.join(valid_providers))).strip().lower()
    
    from domain.providers.enums import AIProvider
    from ui.strings import CLI_ERROR_PREFIX
    try:
        # Validate provider using enum
        provider_enum = AIProvider.from_string(provider)
        config.set("AI_PROVIDER", provider_enum.value)
    except ValueError as e:
        print(f"{CLI_ERROR_PREFIX} {e}")
        splash.close()
        sys.exit(1)

    # Set model if given
    if args.model:
        config.set("DEFAULT_MODEL_TYPE", args.model)
    
    splash.show_message("Initializing interface...")
    app.processEvents()
    
    # Create window (this may take time)
    window = CrawlerControllerWindow()
    
    # Set up logging with LoggerManager
    splash.show_message("Configuring logging system...")
    app.processEvents()
    
    logger_manager = LoggerManager()
    logger_manager.set_ui_controller(window)
    logger_manager.setup_logging(log_level_str="INFO")
    
    # Update splash message
    splash.show_message("Finalizing...")
    app.processEvents()
    
    # Show main window
    window.showMaximized()
    
    # Close splash screen after a short delay to ensure window is visible
    splash.finish(window)
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
