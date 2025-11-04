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
from config.config import Config
try:
    from PyQt6.QtWidgets import QApplication
except ImportError:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("ERROR: Neither PyQt6 nor PySide6 is installed. Please install one of them.")
        sys.exit(1)
from domain.ui_controller import CrawlerControllerWindow
from utils.utils import LoggerManager

def main():
    parser = argparse.ArgumentParser(description="Appium Traverser UI")
    parser.add_argument("--provider", type=str, default=None, help="AI provider to use (gemini, openrouter, ollama)")
    parser.add_argument("--model", type=str, default=None, help="Model name/alias to use")
    args, unknown = parser.parse_known_args()

    config = Config()

    # Set provider if given
    provider = args.provider or os.environ.get("AI_PROVIDER") or config.get("AI_PROVIDER")
    if not provider:
        provider = input("Select AI provider (gemini, openrouter, ollama): ").strip().lower()
    provider = provider.lower()
    if provider not in ("gemini", "openrouter", "ollama"):
        print(f"[ERROR] Invalid provider: {provider}")
        sys.exit(1)
    config.set("AI_PROVIDER", provider)

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
