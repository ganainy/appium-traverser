#!/usr/bin/env python3
"""
Device management commands.
"""

import argparse
from typing import List

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.parser import add_common_arguments
from cli.shared.context import CLIContext


class ListDevicesCommand(CommandHandler):
    """List all connected ADB devices."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "list"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "List all connected ADB devices"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        device_service = context.services.get("device")
        if not device_service:
            return CommandResult(
                success=False,
                message="Device service not available",
                exit_code=1
            )
        
        devices = device_service.list_devices()
        
        if not devices:
            print("No connected devices found.")
            return CommandResult(success=True, message="No devices found")
        
        print("\n=== Connected Devices ===")
        for i, device in enumerate(devices):
            print(f"{i+1}. {device}")
        print("==========================")
        
        return CommandResult(
            success=True,
            message=f"Found {len(devices)} connected devices"
        )


class SelectDeviceCommand(CommandHandler):
    """Select a device by UDID."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "select"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Select a device by UDID"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "device_udid",
            metavar="UDID",
            help="Device UDID to select"
        )
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        device_service = context.services.get("device")
        if not device_service:
            return CommandResult(
                success=False,
                message="Device service not available",
                exit_code=1
            )
        
        success = device_service.select_device(args.device_udid)
        
        if success:
            return CommandResult(
                success=True,
                message=f"Successfully selected device: {args.device_udid}"
            )
        else:
            return CommandResult(
                success=False,
                message=f"Failed to select device: {args.device_udid}",
                exit_code=1
            )


class AutoSelectDeviceCommand(CommandHandler):
    """Automatically select the first available device."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "auto-select"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Automatically select the first available device"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        device_service = context.services.get("device")
        if not device_service:
            return CommandResult(
                success=False,
                message="Device service not available",
                exit_code=1
            )
        
        success = device_service.auto_select_device()
        
        if success:
            return CommandResult(
                success=True,
                message="Successfully auto-selected device"
            )
        else:
            return CommandResult(
                success=False,
                message="Failed to auto-select device",
                exit_code=1
            )


class DeviceCommandGroup(CommandGroup):
    """Device management command group."""
    
    def __init__(self):
        """Initialize device command group."""
        super().__init__("device", "Device management commands")
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            ListDevicesCommand(),
            SelectDeviceCommand(),
            AutoSelectDeviceCommand(),
        ]
