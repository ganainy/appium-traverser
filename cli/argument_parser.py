"""
Argument parser builder for the modular CLI.
"""

import argparse
import textwrap
from typing import List


def build_parser() -> argparse.ArgumentParser:
    """
    Build the main argument parser.
    
    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="Modular CLI for Appium Traverser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples (console script):
              traverser-cli device list
              traverser-cli device select emulator-5554
              traverser-cli apps scan-all
              traverser-cli apps list-all
              traverser-cli apps select "Your App Name"
              traverser-cli crawler start
              traverser-cli crawler stop
              traverser-cli analysis list-targets
              traverser-cli focus list
              traverser-cli openrouter list-models
              traverser-cli show-config
              traverser-cli set-config MAX_CRAWL_STEPS=50

            Examples (python entrypoint):
              python run_cli.py device list
              python run_cli.py focus list
            """
        ),
    )
    
    # Global arguments
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )
    
    return parser


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add common arguments to a parser.
    
    Args:
        parser: Parser to add arguments to
    """
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output for this command"
    )


def add_force_argument(parser: argparse.ArgumentParser) -> None:
    """
    Add force argument to a parser.
    
    Args:
        parser: Parser to add argument to
    """
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force operation bypassing confirmations"
    )


def add_target_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add target selection arguments to a parser.
    
    Args:
        parser: Parser to add arguments to
    """
    target_group = parser.add_mutually_exclusive_group(required=False)
    target_group.add_argument(
        "--target-index",
        metavar="NUMBER",
        type=str,
        help="Target index number"
    )
    target_group.add_argument(
        "--target-app-package",
        metavar="PKG_NAME",
        type=str,
        help="Target app package name"
    )


def validate_target_args(args: argparse.Namespace) -> bool:
    """
    Validate target arguments.
    
    Args:
        args: Parsed arguments
        
    Returns:
        True if valid, False otherwise
    """
    has_index = hasattr(args, 'target_index') and args.target_index
    has_package = hasattr(args, 'target_app_package') and args.target_app_package
    
    # If neither is provided, that might be OK for some commands
    # If both are provided, that's an error
    if has_index and has_package:
        return False
    
    return True
