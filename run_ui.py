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
import json
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

    # Determine config file path
    api_dir = os.path.dirname(__file__)
    user_config_path = os.path.join(api_dir, "user_config.json")

    # Load or create user_config.json
    user_config = {}
    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
        except Exception:
            pass

    # Set provider if given
    provider = args.provider or os.environ.get("AI_PROVIDER") or user_config.get("AI_PROVIDER")
    if not provider:
        provider = input("Select AI provider (gemini, openrouter, ollama): ").strip().lower()
    provider = provider.lower()
    if provider not in ("gemini", "openrouter", "ollama"):
        print(f"[ERROR] Invalid provider: {provider}")
        sys.exit(1)
    user_config["AI_PROVIDER"] = provider

    # Set model if given
    if args.model:
        user_config["DEFAULT_MODEL_TYPE"] = args.model

    # Save updated config
    try:
        with open(user_config_path, "w", encoding="utf-8") as f:
            json.dump(user_config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to update user_config.json: {e}")
        sys.exit(1)

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
