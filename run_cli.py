

import argparse
import sys
import os
from cli import run
from config.config import Config

def main():
    parser = argparse.ArgumentParser(description="Appium Traverser CLI")
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

    # Run CLI (remaining args passed through)
    sys.argv = [sys.argv[0]] + unknown
    run()

if __name__ == "__main__":
    main()
