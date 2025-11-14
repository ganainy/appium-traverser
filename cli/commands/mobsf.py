#!/usr/bin/env python3
"""
MobSF security analysis commands.
"""

import argparse
from typing import List

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import ApplicationContext
from cli.constants import messages as MSG
from cli.constants import keys as KEY


class TestMobSFConnectionCommand(CommandHandler):
    """Test connection to MobSF server."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return MSG.MOBSF_TEST_CMD_NAME
    
    @property
    def description(self) -> str:
        """Get command description."""
        return MSG.MOBSF_TEST_CMD_DESC
    
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
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the command."""
        mobsf_service = context.services.get(KEY.MOBSF_SERVICE)
        if not mobsf_service:
            return CommandResult(
                success=False,
                message=MSG.SERVICE_NOT_AVAILABLE.format(service=KEY.MOBSF_SERVICE.title()),
                exit_code=1
            )
        
        success, message = mobsf_service.test_connection()
        
        if success:
            return CommandResult(
                success=True,
                message=MSG.MOBSF_TEST_SUCCESS + f": {message}"
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.MOBSF_TEST_FAIL + f": {message}",
                exit_code=1
            )


class AnalyzeAppCommand(CommandHandler):
    """Run MobSF security analysis on an app."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return MSG.MOBSF_ANALYZE_CMD_NAME
    
    @property
    def description(self) -> str:
        """Get command description."""
        return MSG.MOBSF_ANALYZE_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            MSG.MOBSF_ANALYZE_ARG_PACKAGE,
            type=str,
            nargs='?',
            default=None,
            metavar=MSG.MOBSF_ANALYZE_ARG_PACKAGE_METAVAR,
            help=MSG.MOBSF_ANALYZE_ARG_PACKAGE_HELP
        )
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the command."""
        mobsf_service = context.services.get(KEY.MOBSF_SERVICE)
        if not mobsf_service:
            return CommandResult(
                success=False,
                message=MSG.SERVICE_NOT_AVAILABLE.format(service=KEY.MOBSF_SERVICE.title()),
                exit_code=1
            )
        
        package_name = getattr(args, MSG.MOBSF_ANALYZE_ARG_PACKAGE, None)
        success, result = mobsf_service.run_analysis(package_name=package_name)
        
        if success:
            # Format success message with report paths
            message = MSG.MOBSF_ANALYZE_SUCCESS
            if isinstance(result, dict):
                if result.get('pdf_report'):
                    message += f"\nPDF Report: {result['pdf_report']}"
                if result.get('json_report'):
                    message += f"\nJSON Report: {result['json_report']}"
                if result.get('security_score'):
                    score = result['security_score']
                    if isinstance(score, dict):
                        message += f"\nSecurity Score: {score.get('score', 'N/A')}"
                    else:
                        message += f"\nSecurity Score: {score}"
            
            return CommandResult(
                success=True,
                message=message
            )
        else:
            error_msg = result.get('error', 'Unknown error') if isinstance(result, dict) else str(result)
            return CommandResult(
                success=False,
                message=MSG.MOBSF_ANALYZE_FAIL + f": {error_msg}",
                exit_code=1
            )


class MobSFCommandGroup(CommandGroup):
    """Command group for MobSF security analysis operations."""
    
    def __init__(self):
        """Initialize the MobSF command group."""
        super().__init__("mobsf", MSG.MOBSF_COMMAND_GROUP_DESC)
    
    def get_commands(self) -> List[CommandHandler]:
        """
        Return a list of CommandHandler instances for this group.
        
        Returns:
            List of command handlers
        """
        return [
            TestMobSFConnectionCommand(),
            AnalyzeAppCommand()
        ]

