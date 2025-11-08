

import argparse
import sys
import os
from cli import run
from config.config import Config

def main():
    # Use parse_known_args to allow subcommands to pass through
    parser = argparse.ArgumentParser(description="Appium Traverser CLI", add_help=False)
    parser.add_argument("--provider", type=str, default=None, help="AI provider to use (gemini, openrouter, ollama)")
    parser.add_argument("--model", type=str, default=None, help="Model name/alias to use")
    parser.add_argument("--help", "-h", action="store_true", help="Show help message")
    
    args, unknown = parser.parse_known_args()

    config = Config()

    # Set provider if given
    provider = args.provider or os.environ.get("AI_PROVIDER") or config.get("AI_PROVIDER")
    
    # Only prompt for provider if no subcommand is being run and it's not a help request
    if not provider and not unknown and not args.help:
        provider = input("Select AI provider (gemini, openrouter, ollama): ").strip().lower()
    
    if provider:
        provider = provider.lower()
        if provider not in ("gemini", "openrouter", "ollama"):
            print(f"[ERROR] Invalid provider: {provider}")
            sys.exit(1)
        config.set("AI_PROVIDER", provider)

    # Set model if given
    if args.model:
        config.set("DEFAULT_MODEL_TYPE", args.model)

    # Pass through all unknown args (including subcommands and their --help)
    # Reconstruct sys.argv with script name + unknown args
    sys.argv = [sys.argv[0]] + unknown
    
    # Run CLI
    run()

if __name__ == "__main__":
    main()
