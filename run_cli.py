

import argparse
import sys
import os
import json
from cli import run

def main():
    parser = argparse.ArgumentParser(description="Appium Traverser CLI")
    parser.add_argument("--provider", type=str, default=None, help="AI provider to use (gemini, openrouter, ollama)")
    parser.add_argument("--model", type=str, default=None, help="Model name/alias to use")
    args, unknown = parser.parse_known_args()

    # Determine config file path
    api_dir = os.path.join(os.path.dirname(__file__), "traverser_ai_api")
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

    # Run CLI (remaining args passed through)
    sys.argv = [sys.argv[0]] + unknown
    run()

if __name__ == "__main__":
    main()
