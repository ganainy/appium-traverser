

import argparse
import sys
import os
from cli import run
from config.app_config import Config

def main():
    # Check if running in crawler mode (via environment variable or flag)
    crawler_mode = os.environ.get("CRAWLER_MODE") == "1" or "--crawler-run" in sys.argv
    
    if crawler_mode:
        # Remove the flag from argv if present
        if "--crawler-run" in sys.argv:
            sys.argv.remove("--crawler-run")
        
        # Run crawler loop directly
        # Note: run_crawler_loop handles its own exceptions
        from core.crawler_loop import run_crawler_loop
        config = Config()
        run_crawler_loop(config)
        return
    
    # Use parse_known_args to allow subcommands to pass through
    parser = argparse.ArgumentParser(description="Appium Traverser CLI", add_help=False)
    from domain.providers.registry import ProviderRegistry
    valid_providers = ProviderRegistry.get_all_names()
    parser.add_argument("--provider", type=str, default=None, help=f"AI provider to use ({', '.join(valid_providers)})")
    parser.add_argument("--model", type=str, default=None, help="Model name/alias to use")
    parser.add_argument("--help", "-h", action="store_true", help="Show help message")
    
    args, unknown = parser.parse_known_args()

    config = Config()

    # Set provider if given
    provider = args.provider or os.environ.get("AI_PROVIDER") or config.get("AI_PROVIDER")
    
    # Only prompt for provider if no subcommand is being run and it's not a help request
    if not provider and not unknown and not args.help:
        provider = input(f"Select AI provider ({', '.join(valid_providers)}): ").strip().lower()
    
    if provider:
        from domain.providers.enums import AIProvider
        try:
            # Validate provider using enum
            provider_enum = AIProvider.from_string(provider)
            config.set("AI_PROVIDER", provider_enum.value)
        except ValueError as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

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
