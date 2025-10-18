"""
Configuration commands for CLI operations.
"""

import argparse
from typing import Optional

from .base import CommandHandler, CommandResult, CommandGroup
from ..shared.context import CLIContext


class ShowConfigCommand(CommandHandler):
    """Command to show current configuration."""
    
    @property
    def name(self) -> str:
        return "show-config"
    
    @property
    def description(self) -> str:
        return "Show current configuration"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        
        parser.add_argument(
            "filter",
            nargs="?",
            help="Filter configuration by key (optional)"
        )
        
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from ..services.config_service import ConfigService
        
        config_service = ConfigService(context)
        config_data = config_service.show_config(args.filter)
        
        context.services.get("telemetry").print_config_table(config_data, args.filter)
        
        return CommandResult(
            success=True,
            message=f"Configuration displayed{f' (filtered by: {args.filter})' if args.filter else ''}"
        )


class SetConfigCommand(CommandHandler):
    """Command to set configuration values."""
    
    @property
    def name(self) -> str:
        return "set-config"
    
    @property
    def description(self) -> str:
        return "Set configuration values"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        
        parser.add_argument(
            "key_value_pairs",
            nargs="+",
            help="Configuration key=value pairs (e.g., MAX_CRAWL_STEPS=100)"
        )
        
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from ..services.config_service import ConfigService
        
        config_service = ConfigService(context)
        telemetry = context.services.get("telemetry")
        
        success_count = 0
        total_count = len(args.key_value_pairs)
        
        for kv_pair in args.key_value_pairs:
            if "=" not in kv_pair:
                telemetry.print_error(f"Invalid format: {kv_pair}. Use KEY=VALUE format.")
                continue
            
            key, value = kv_pair.split("=", 1)
            if config_service.set_config_value(key.strip(), value.strip()):
                success_count += 1
                telemetry.print_success(f"Set {key} = {value}")
            else:
                telemetry.print_error(f"Failed to set {key}")
        
        # Save all changes
        if success_count > 0:
            if config_service.save_all_changes():
                telemetry.print_success("Configuration saved successfully")
            else:
                telemetry.print_warning("Configuration updated but failed to save")
        
        success = success_count == total_count
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
            name="config",
            description="Configuration management commands"
        )
        
        self.add_command(ShowConfigCommand())
        self.add_command(SetConfigCommand())