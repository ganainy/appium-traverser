"""
Configuration commands for CLI operations.
"""


import argparse
from typing import Optional

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext
from cli.constants import messages as MSG
from cli.constants import keys as KEYS
from cli.commands.switch_provider import SwitchProviderCommand


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

    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
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

    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from cli.services.config_service import ConfigService

        config_service = ConfigService(context)
        success = config_service.set_and_save_from_pairs(args.key_value_pairs)
        total_count = len(args.key_value_pairs)

        # Calculate success count for the message
        success_count = total_count if success else 0
        message = f"Set {success_count}/{total_count} configuration values"

        return CommandResult(
            success=success,
            message=message,
            exit_code=0 if success else 1
        )


class ConfigCommandGroup(CommandGroup):
    """Command group for configuration operations."""

    def __init__(self):
        super().__init__(
            name=MSG.CONFIG_GROUP_NAME,
            description=MSG.CONFIG_GROUP_DESC
        )
        self.add_command(ShowConfigCommand())
        self.add_command(SetConfigCommand())
        self.add_command(SwitchProviderCommand())
