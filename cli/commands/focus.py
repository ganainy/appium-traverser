#!/usr/bin/env python3
"""
Focus area management commands.
"""


import argparse
from typing import List

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext
from cli.constants import messages as MSG
from cli.constants import keys as KEY
from cli.constants.config import DEFAULT_FOCUS_PRIORITY


class ListFocusAreasCommand(CommandHandler):
    """List all configured focus areas."""
    
    @property
    def name(self) -> str:
        return MSG.LIST_FOCUS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.LIST_FOCUS_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        focus_service = context.services.get(KEY.FOCUS_SERVICE)
        if not focus_service:
            return CommandResult(
                success=False,
                message=MSG.FOCUS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        telemetry_service = context.services.get(KEY.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

    areas = focus_service.get_focus_areas()
        telemetry_service.print_focus_areas(areas)

        return CommandResult(
            success=True,
            message=MSG.FOUND_FOCUS_AREAS.format(count=len(areas))
        )

class AddFocusAreaCommand(CommandHandler):
    """Add a new focus area."""
    
    @property
    def name(self) -> str:
        return MSG.ADD_FOCUS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.ADD_FOCUS_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            MSG.ADD_FOCUS_ARG_TITLE,
            metavar=MSG.ADD_FOCUS_ARG_TITLE_METAVAR,
            type=str,
            help=MSG.ADD_FOCUS_ARG_TITLE_HELP
        )
        parser.add_argument(
            f"--{MSG.ADD_FOCUS_ARG_DESC}",
            metavar=MSG.ADD_FOCUS_ARG_DESC_METAVAR,
            type=str,
            default="",
            help=MSG.ADD_FOCUS_ARG_DESC_HELP
        )
        parser.add_argument(
            f"--{MSG.ADD_FOCUS_ARG_PRIORITY}",
            metavar=MSG.ADD_FOCUS_ARG_PRIORITY_METAVAR,
            type=int,
            default=DEFAULT_FOCUS_PRIORITY,
            help=MSG.ADD_FOCUS_ARG_PRIORITY_HELP.format(default=DEFAULT_FOCUS_PRIORITY)
        )
        parser.add_argument(
            f"--{MSG.ADD_FOCUS_ARG_ENABLED}",
            action="store_true",
            default=True,
            help=MSG.ADD_FOCUS_ARG_ENABLED_HELP
        )
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        focus_service = context.services.get(KEY.FOCUS_SERVICE)
        if not focus_service:
            return CommandResult(
                success=False,
                message=MSG.FOCUS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        success = focus_service.add_focus_area(
            title=getattr(args, MSG.ADD_FOCUS_ARG_TITLE),
            description=getattr(args, MSG.ADD_FOCUS_ARG_DESC),
            priority=getattr(args, MSG.ADD_FOCUS_ARG_PRIORITY),
            enabled=getattr(args, MSG.ADD_FOCUS_ARG_ENABLED)
        )

        if success:
            return CommandResult(
                success=True,
                message=MSG.ADD_FOCUS_SUCCESS.format(title=getattr(args, MSG.ADD_FOCUS_ARG_TITLE))
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.ADD_FOCUS_FAIL.format(title=getattr(args, MSG.ADD_FOCUS_ARG_TITLE)),
                exit_code=1
            )

class EditFocusAreaCommand(CommandHandler):
    """Edit an existing focus area."""
    
    @property
    def name(self) -> str:
        return MSG.EDIT_FOCUS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.EDIT_FOCUS_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            MSG.EDIT_FOCUS_ARG_ID_OR_NAME,
            metavar=MSG.EDIT_FOCUS_ARG_ID_OR_NAME_METAVAR,
            type=str,
            help=MSG.EDIT_FOCUS_ARG_ID_OR_NAME_HELP
        )
        parser.add_argument(
            f"--{MSG.EDIT_FOCUS_ARG_TITLE}",
            metavar=MSG.EDIT_FOCUS_ARG_TITLE_METAVAR,
            type=str,
            help=MSG.EDIT_FOCUS_ARG_TITLE_HELP,
            default=None
        )
        parser.add_argument(
            f"--{MSG.EDIT_FOCUS_ARG_DESC}",
            metavar=MSG.EDIT_FOCUS_ARG_DESC_METAVAR,
            type=str,
            help=MSG.EDIT_FOCUS_ARG_DESC_HELP,
            default=None
        )
        parser.add_argument(
            f"--{MSG.EDIT_FOCUS_ARG_PRIORITY}",
            metavar=MSG.EDIT_FOCUS_ARG_PRIORITY_METAVAR,
            type=int,
            help=MSG.EDIT_FOCUS_ARG_PRIORITY_HELP,
            default=None
        )
        parser.add_argument(
            f"--{MSG.EDIT_FOCUS_ARG_ENABLED}",
            action="store_true",
            dest="enable",
            help=MSG.EDIT_FOCUS_ARG_ENABLED_HELP
        )
        parser.add_argument(
            f"--{MSG.EDIT_FOCUS_ARG_DISABLED}",
            action="store_false",
            dest="enable",
            help=MSG.EDIT_FOCUS_ARG_DISABLED_HELP
        )
        parser.set_defaults(enable=None)
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        focus_service = context.services.get(KEY.FOCUS_SERVICE)
        if not focus_service:
            return CommandResult(
                success=False,
                message=MSG.FOCUS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        # Only pass parameters that were actually provided
        kwargs = {}
        if getattr(args, MSG.EDIT_FOCUS_ARG_TITLE) is not None:
            kwargs["title"] = getattr(args, MSG.EDIT_FOCUS_ARG_TITLE)
        if getattr(args, MSG.EDIT_FOCUS_ARG_DESC) is not None:
            kwargs["description"] = getattr(args, MSG.EDIT_FOCUS_ARG_DESC)
        if getattr(args, MSG.EDIT_FOCUS_ARG_PRIORITY) is not None:
            kwargs["priority"] = getattr(args, MSG.EDIT_FOCUS_ARG_PRIORITY)
        if args.enable is not None:
            kwargs["enabled"] = args.enable

        if not kwargs:
            return CommandResult(
                success=False,
                message=MSG.EDIT_FOCUS_NO_CHANGES,
                exit_code=1
            )

        id_or_name = getattr(args, MSG.EDIT_FOCUS_ARG_ID_OR_NAME)
        success = focus_service.edit_focus_area(id_or_name, **kwargs)

        if success:
            return CommandResult(
                success=True,
                message=MSG.EDIT_FOCUS_SUCCESS.format(id_or_name=id_or_name)
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.EDIT_FOCUS_FAIL.format(id_or_name=id_or_name),
                exit_code=1
            )

class RemoveFocusAreaCommand(CommandHandler):
    """Remove a focus area."""
    
    @property
    def name(self) -> str:
        return MSG.REMOVE_FOCUS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.REMOVE_FOCUS_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            MSG.REMOVE_FOCUS_ARG_ID_OR_NAME,
            metavar=MSG.REMOVE_FOCUS_ARG_ID_OR_NAME_METAVAR,
            type=str,
            help=MSG.REMOVE_FOCUS_ARG_ID_OR_NAME_HELP
        )
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        focus_service = context.services.get(KEY.FOCUS_SERVICE)
        if not focus_service:
            return CommandResult(
                success=False,
                message=MSG.FOCUS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        id_or_name = getattr(args, MSG.REMOVE_FOCUS_ARG_ID_OR_NAME)
        success = focus_service.remove_focus_area(id_or_name)

        if success:
            return CommandResult(
                success=True,
                message=MSG.REMOVE_FOCUS_SUCCESS.format(id_or_name=id_or_name)
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.REMOVE_FOCUS_FAIL.format(id_or_name=id_or_name),
                exit_code=1
            )

class FocusCommandGroup(CommandGroup):
    """Focus area management command group."""
    
    def __init__(self):
        super().__init__("focus", MSG.FOCUS_COMMAND_GROUP_DESC)
    
    def get_commands(self) -> List['CommandHandler']:
        """Return a list of CommandHandler instances for this group."""
        return [
            ListFocusAreasCommand(),
            AddFocusAreaCommand(),
            EditFocusAreaCommand(),
            RemoveFocusAreaCommand()
        ]
