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
    from PyQt6.QtWidgets import QApplication
except ImportError:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        from ui.strings import RUN_UI_ERROR_NEITHER_QT
        print(RUN_UI_ERROR_NEITHER_QT)
        sys.exit(1)
from domain.ui_controller import CrawlerControllerWindow
from utils.utils import LoggerManager

def main():
    parser = argparse.ArgumentParser(description="Appium Traverser UI")
    parser.add_argument("--provider", type=str, default=None, help="AI provider to use")
    parser.add_argument("--model", type=str, default=None, help="Model name/alias to use")
    args, unknown = parser.parse_known_args()

    config = Config()

    # Set provider if given
    provider = args.provider or os.environ.get("AI_PROVIDER") or config.get("AI_PROVIDER")
    if not provider:
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
        sys.exit(1)

    # Set model if given
    if args.model:
        config.set("DEFAULT_MODEL_TYPE", args.model)

    # Launch UI (remaining args passed through)
    sys.argv = [sys.argv[0]] + unknown
    app = QApplication(sys.argv)
    window = CrawlerControllerWindow()

    # Set up logging with LoggerManager
    logger_manager = LoggerManager()
    logger_manager.set_ui_controller(window)
    logger_manager.setup_logging(log_level_str="INFO")

    window.showMaximized()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
