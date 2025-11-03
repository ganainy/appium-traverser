#!/usr/bin/env python3
"""
Device management commands.
"""


import argparse
from typing import List

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.parser import add_common_arguments
from cli.shared.context import CLIContext
from cli.constants import messages as MSG
from cli.constants import keys as KEY


class ListDevicesCommand(CommandHandler):
    """List all connected ADB devices."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return MSG.LIST_DEVICES_CMD_NAME

    @property
    def description(self) -> str:
        """Get command description."""
        return MSG.LIST_DEVICES_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        device_service = context.services.get(KEY.DEVICE_SERVICE)
        if not device_service:
            return CommandResult(
                success=False,
                message=MSG.DEVICE_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        devices = device_service.list_devices()

        # Use telemetry service to handle presentation
        telemetry_service = context.services.get(KEY.TELEMETRY_SERVICE)
        if telemetry_service:
            telemetry_service.print_device_list(devices)

        # Determine the appropriate message based on device count
        if not devices:
            message = MSG.NO_DEVICES_FOUND
        else:
            message = MSG.FOUND_CONNECTED_DEVICES.format(count=len(devices))

        return CommandResult(success=True, message=message)


class SelectDeviceCommand(CommandHandler):
    """Select a device by UDID."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return MSG.SELECT_DEVICE_CMD_NAME

    @property
    def description(self) -> str:
        """Get command description."""
        return MSG.SELECT_DEVICE_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            MSG.SELECT_DEVICE_ARG_NAME,
            metavar=MSG.SELECT_DEVICE_ARG_METAVAR,
            help=MSG.SELECT_DEVICE_ARG_HELP
        )
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        device_service = context.services.get(KEY.DEVICE_SERVICE)
        if not device_service:
            return CommandResult(
                success=False,
                message=MSG.DEVICE_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        device_udid = getattr(args, MSG.SELECT_DEVICE_ARG_NAME)
        success = device_service.is_device_connected(device_udid)

        if success:
            try:
                # Set the config in the command
                context.config.set(KEY.CONFIG_DEVICE_UDID, device_udid)
                context.config.save_user_config()
                return CommandResult(
                    success=True,
                    message=MSG.SELECT_DEVICE_SUCCESS.format(udid=device_udid)
                )
            except Exception as e:
                return CommandResult(
                    success=False,
                    message=f"Error saving device selection: {e}",
                    exit_code=1
                )
        else:
            return CommandResult(
                success=False,
                message=MSG.SELECT_DEVICE_FAIL.format(udid=device_udid),
                exit_code=1
            )


class AutoSelectDeviceCommand(CommandHandler):
    """Automatically select the first available device."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return MSG.AUTO_SELECT_DEVICE_CMD_NAME

    @property
    def description(self) -> str:
        """Get command description."""
        return MSG.AUTO_SELECT_DEVICE_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        device_service = context.services.get(KEY.DEVICE_SERVICE)
        if not device_service:
            return CommandResult(
                success=False,
                message=MSG.DEVICE_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        udid = device_service.auto_select_device()

        if udid is not None:
            try:
                # Set the config in the command
                context.config.set(KEY.CONFIG_DEVICE_UDID, udid)
                context.config.save_user_config()
                return CommandResult(
                    success=True,
                    message=MSG.AUTO_SELECT_DEVICE_SUCCESS
                )
            except Exception as e:
                return CommandResult(
                    success=False,
                    message=f"Error saving device selection: {e}",
                    exit_code=1
                )
        else:
            return CommandResult(
                success=False,
                message=MSG.AUTO_SELECT_DEVICE_FAIL,
                exit_code=1
            )


class DeviceCommandGroup(CommandGroup):
    """Device management command group."""
    
    def __init__(self):
        """Initialize device command group."""
        super().__init__("device", MSG.DEVICE_COMMAND_GROUP_DESC)
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            ListDevicesCommand(),
            SelectDeviceCommand(),
            AutoSelectDeviceCommand(),
        ]
