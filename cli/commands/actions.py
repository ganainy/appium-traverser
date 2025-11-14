#!/usr/bin/env python3
"""
Crawler actions management commands.

This module provides CLI commands for managing crawler actions:
- list: Display all configured actions
- add: Create a new action
- edit: Modify an existing action
- remove: Delete an action

Actions define what the crawler can do (e.g., click, scroll, swipe)
and are stored in the database for persistence.
"""


import argparse
from typing import List, Dict, Any, Optional

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import ApplicationContext
from cli.constants import messages as MSG
from cli.constants import keys as KEY


class ListCrawlerActionsCommand(CommandHandler):
    """List all configured crawler actions."""
    
    @property
    def name(self) -> str:
        return MSG.LIST_ACTIONS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.LIST_ACTIONS_CMD_DESC
    
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
        """Execute the list command."""
        actions_service: Optional[Any] = context.services.get(KEY.ACTIONS_SERVICE)
        if actions_service is None:
            return CommandResult(
                success=False,
                message=MSG.ACTIONS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        telemetry_service: Optional[Any] = context.services.get(KEY.TELEMETRY_SERVICE)
        if telemetry_service is None:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        all_actions: List[Dict[str, Any]] = actions_service.get_actions()
        action_count: int = len(all_actions)
        
        # Display actions in a formatted numbered list
        print(f"\n=== Crawler Actions ({action_count}) ===")
        for index, action_data in enumerate(all_actions, start=1):
            is_enabled: bool = action_data.get("enabled", True)
            enabled_indicator: str = "✓" if is_enabled else "✗"
            action_name: str = action_data.get("name", "Unknown")
            action_description: str = action_data.get("description", "")
            
            print(f"{index:2d}. {enabled_indicator} {action_name}: {action_description}")
        print("==============================")

        return CommandResult(
            success=True,
            message=MSG.FOUND_ACTIONS.format(count=action_count)
        )


class AddCrawlerActionCommand(CommandHandler):
    """Add a new crawler action."""
    
    @property
    def name(self) -> str:
        return MSG.ADD_ACTIONS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.ADD_ACTIONS_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            MSG.ADD_ACTIONS_ARG_NAME,
            metavar=MSG.ADD_ACTIONS_ARG_NAME_METAVAR,
            type=str,
            help=MSG.ADD_ACTIONS_ARG_NAME_HELP
        )
        parser.add_argument(
            f"--{MSG.ADD_ACTIONS_ARG_DESC}",
            metavar=MSG.ADD_ACTIONS_ARG_DESC_METAVAR,
            type=str,
            default="",
            help=MSG.ADD_ACTIONS_ARG_DESC_HELP
        )
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the add command."""
        actions_service: Optional[Any] = context.services.get(KEY.ACTIONS_SERVICE)
        if actions_service is None:
            return CommandResult(
                success=False,
                message=MSG.ACTIONS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        action_name: str = getattr(args, MSG.ADD_ACTIONS_ARG_NAME)
        action_description: str = getattr(args, MSG.ADD_ACTIONS_ARG_DESC)
        
        operation_success: bool
        operation_message: Optional[str]
        operation_success, operation_message = actions_service.add_action(
            name=action_name,
            description=action_description,
        )

        if operation_success:
            return CommandResult(
                success=True,
                message=MSG.ADD_ACTIONS_SUCCESS.format(name=action_name)
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.ADD_ACTIONS_FAIL.format(name=action_name),
                exit_code=1
            )


class EditCrawlerActionCommand(CommandHandler):
    """Edit an existing crawler action."""
    
    @property
    def name(self) -> str:
        return MSG.EDIT_ACTIONS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.EDIT_ACTIONS_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            MSG.EDIT_ACTIONS_ARG_ID_OR_NAME,
            metavar=MSG.EDIT_ACTIONS_ARG_ID_OR_NAME_METAVAR,
            type=str,
            help=MSG.EDIT_ACTIONS_ARG_ID_OR_NAME_HELP
        )
        parser.add_argument(
            f"--{MSG.EDIT_ACTIONS_ARG_NAME}",
            metavar=MSG.EDIT_ACTIONS_ARG_NAME_METAVAR,
            type=str,
            help=MSG.EDIT_ACTIONS_ARG_NAME_HELP,
            default=None
        )
        parser.add_argument(
            f"--{MSG.EDIT_ACTIONS_ARG_DESC}",
            metavar=MSG.EDIT_ACTIONS_ARG_DESC_METAVAR,
            type=str,
            help=MSG.EDIT_ACTIONS_ARG_DESC_HELP,
            default=None
        )
        parser.add_argument(
            f"--{MSG.EDIT_ACTIONS_ARG_ENABLED}",
            action="store_true",
            dest="enable",
            help=MSG.EDIT_ACTIONS_ARG_ENABLED_HELP
        )
        parser.add_argument(
            f"--{MSG.EDIT_ACTIONS_ARG_DISABLED}",
            action="store_false",
            dest="enable",
            help=MSG.EDIT_ACTIONS_ARG_DISABLED_HELP
        )
        parser.set_defaults(enable=None)
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the edit command."""
        actions_service: Optional[Any] = context.services.get(KEY.ACTIONS_SERVICE)
        if actions_service is None:
            return CommandResult(
                success=False,
                message=MSG.ACTIONS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        # Collect only the parameters that were explicitly provided
        update_parameters: Dict[str, Any] = {}
        
        new_name: Optional[str] = getattr(args, MSG.EDIT_ACTIONS_ARG_NAME, None)
        if new_name is not None:
            update_parameters["name"] = new_name
        
        new_description: Optional[str] = getattr(args, MSG.EDIT_ACTIONS_ARG_DESC, None)
        if new_description is not None:
            update_parameters["description"] = new_description
        
        enabled_state: Optional[bool] = getattr(args, "enable", None)
        if enabled_state is not None:
            update_parameters["enabled"] = enabled_state

        # Validate that at least one parameter was provided
        if not update_parameters:
            return CommandResult(
                success=False,
                message=MSG.EDIT_ACTIONS_NO_CHANGES,
                exit_code=1
            )

        action_identifier: str = getattr(args, MSG.EDIT_ACTIONS_ARG_ID_OR_NAME)
        operation_success: bool
        operation_message: Optional[str]
        operation_success, operation_message = actions_service.edit_action(
            id_or_name=action_identifier, 
            **update_parameters
        )

        if operation_success:
            return CommandResult(
                success=True,
                message=MSG.EDIT_ACTIONS_SUCCESS.format(id_or_name=action_identifier)
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.EDIT_ACTIONS_FAIL.format(id_or_name=action_identifier),
                exit_code=1
            )


class RemoveCrawlerActionCommand(CommandHandler):
    """Remove a crawler action."""
    
    @property
    def name(self) -> str:
        return MSG.REMOVE_ACTIONS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.REMOVE_ACTIONS_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            MSG.REMOVE_ACTIONS_ARG_ID_OR_NAME,
            metavar=MSG.REMOVE_ACTIONS_ARG_ID_OR_NAME_METAVAR,
            type=str,
            help=MSG.REMOVE_ACTIONS_ARG_ID_OR_NAME_HELP
        )
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the remove command."""
        actions_service: Optional[Any] = context.services.get(KEY.ACTIONS_SERVICE)
        if actions_service is None:
            return CommandResult(
                success=False,
                message=MSG.ACTIONS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        action_identifier: str = getattr(args, MSG.REMOVE_ACTIONS_ARG_ID_OR_NAME)
        operation_success: bool
        operation_message: Optional[str]
        operation_success, operation_message = actions_service.remove_action(action_identifier)

        if operation_success:
            return CommandResult(
                success=True,
                message=MSG.REMOVE_ACTIONS_SUCCESS.format(id_or_name=action_identifier)
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.REMOVE_ACTIONS_FAIL.format(id_or_name=action_identifier),
                exit_code=1
            )


class CrawlerActionsCommandGroup(CommandGroup):
    """Command group for managing crawler actions."""
    
    def __init__(self):
        super().__init__("actions", MSG.ACTIONS_COMMAND_GROUP_DESC)
    
    def get_commands(self) -> List[CommandHandler]:
        """Return a list of CommandHandler instances for this group."""
        return [
            ListCrawlerActionsCommand(),
            AddCrawlerActionCommand(),
            EditCrawlerActionCommand(),
            RemoveCrawlerActionCommand()
        ]
