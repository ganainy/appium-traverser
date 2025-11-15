"""
Service check commands for CLI operations.
"""

import argparse
from typing import Any, Dict, List

from cli.commands.base import CommandHandler, CommandResult, CommandGroup
from core.health_check import ValidationService
from cli.shared.context import ApplicationContext
from cli.constants import messages as MSG
from cli.constants import keys as KEYS


class PrecheckCommand(CommandHandler):
    """Command to run pre-crawl service checks."""
    
    @property
    def name(self) -> str:
        return MSG.PRECHECK_NAME

    @property
    def description(self) -> str:
        return MSG.PRECHECK_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        telemetry = context.services.get(KEYS.SERVICE_TELEMETRY)

        # Instantiate ValidationService with config
        health_service = ValidationService(context.config)
        
        # Check services
        services_status = health_service.check_all_services()
        
        # Get the telemetry service and call telemetry.print_status_table(services_status)
        telemetry.print_status_table(services_status)

        # Perform the final aggregation and return the CommandResult
        issues = [s for s in services_status.values() if s.get(KEYS.STATUS_KEY_STATUS) == KEYS.STATUS_ERROR]
        warnings = [s for s in services_status.values() if s.get(KEYS.STATUS_KEY_STATUS) == KEYS.STATUS_WARNING]

        if not issues and not warnings:
            return CommandResult(success=True, message=MSG.PRECHECK_RESULT_SUCCESS)
        elif not issues:
            return CommandResult(success=True, message="")
        else:
            return CommandResult(success=False, message="", exit_code=1)


class UtilityCommandGroup(CommandGroup):
    """Command group for utility and validation commands."""
    
    def __init__(self):
        """Initialize the utility command group."""
        super().__init__("utils", "Utility and validation commands")
    
    def get_commands(self) -> List[CommandHandler]:
        """
        Return a list of CommandHandler instances for this group.
        
        Returns:
            List of command handlers
        """
        return [PrecheckCommand()]
