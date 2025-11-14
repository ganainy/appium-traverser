"""
Configuration commands for CLI operations.

This module provides CLI commands for managing application-wide settings:
- show: Display current configuration values
- set: Set configuration values using KEY=VALUE pairs
- reset: Reset configuration to defaults (clears all stored config, actions, and prompts)

These commands work with config.app_config.Config to manage user preferences
and application settings stored in SQLite.
"""


import argparse
from typing import List, Optional

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import ApplicationContext
from cli.constants import messages as MSG
from cli.constants import keys as KEYS

__all__ = [
    "ShowConfigCommand",
    "SetConfigCommand",
    "ResetConfigCommand",
    "ConfigCommandGroup",
]


class ShowConfigCommand(CommandHandler):
    """Command to show current configuration."""

    @property
    def name(self) -> str:
        return MSG.SHOW_CONFIG_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.SHOW_CONFIG_CMD_DESC

    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )

        parser.add_argument(
            "filter",
            nargs="?",
            help=MSG.SHOW_CONFIG_FILTER_HELP
        )

        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser

    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        config_data = context.config._get_user_savable_config()
        
        # Filter if needed
        if args.filter:
            filtered_config = {
                k: v for k, v in config_data.items()
                if args.filter.lower() in k.lower()
            }
            config_data = filtered_config

        context.services.get(KEYS.TELEMETRY_SERVICE).print_config_table(config_data, args.filter)

        if args.filter:
            msg = MSG.SHOW_CONFIG_DISPLAYED_FILTERED.format(filter=args.filter)
        else:
            msg = MSG.SHOW_CONFIG_DISPLAYED

        return CommandResult(
            success=True,
            message=msg
        )


class SetConfigCommand(CommandHandler):
    """Command to set configuration values."""

    @property
    def name(self) -> str:
        return MSG.SET_CONFIG_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.SET_CONFIG_CMD_DESC

    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )

        parser.add_argument(
            "key_value_pairs",
            nargs="+",
            help=MSG.SET_CONFIG_KEY_VALUE_HELP
        )

        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser

    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        # Use config directly
        success = context.config.set_and_save_from_pairs(
            args.key_value_pairs, 
            context.services.get(KEYS.TELEMETRY_SERVICE)
        )
        total_count = len(args.key_value_pairs)

        # Calculate success count for the message
        success_count = total_count if success else 0
        message = f"Set {success_count}/{total_count} configuration values"

        return CommandResult(
            success=success,
            message=message,
            exit_code=0 if success else 1
        )


class ResetConfigCommand(CommandHandler):
    """Command to reset configuration to defaults."""

    @property
    def name(self) -> str:
        return MSG.RESET_CONFIG_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.RESET_CONFIG_CMD_DESC

    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )

        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt"
        )

        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser

    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        # Ask for confirmation unless --yes flag is used
        if not args.yes:
            try:
                response = input(MSG.RESET_CONFIG_CONFIRM_PROMPT)
                if response.lower() not in ('yes', 'y'):
                    return CommandResult(
                        success=False,
                        message=MSG.RESET_CONFIG_CANCELLED,
                        exit_code=0
                    )
            except (EOFError, KeyboardInterrupt):
                return CommandResult(
                    success=False,
                    message=MSG.RESET_CONFIG_CANCELLED,
                    exit_code=0
                )

        try:
            # Use the internal reset_settings method
            context.config.reset_settings()
            return CommandResult(
                success=True,
                message=MSG.RESET_CONFIG_SUCCESS,
                exit_code=0
            )
        except Exception as e:
            error_msg = MSG.RESET_CONFIG_FAIL.format(error=str(e))
            context.services.get(KEYS.TELEMETRY_SERVICE).print_error(error_msg)
            return CommandResult(
                success=False,
                message=error_msg,
                exit_code=1
            )


class ConfigCommandGroup(CommandGroup):
    """Command group for configuration operations."""

    def __init__(self):
        super().__init__(
            name=MSG.CONFIG_GROUP_NAME,
            description=MSG.CONFIG_GROUP_DESC
        )
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            ShowConfigCommand(),
            SetConfigCommand(),
            ResetConfigCommand(),
        ]

