#!/usr/bin/env python3
"""
Focus area management commands.
"""

import argparse
import json
import os
from typing import List

from traverser_ai_api.cli.commands.base import CommandGroup, CommandHandler, CommandResult
from traverser_ai_api.cli.shared.context import CLIContext


class ListFocusAreasCommand(CommandHandler):
    """List all configured focus areas."""
    
    @property
    def name(self) -> str:
        return "list"
    
    @property
    def description(self) -> str:
        return "List all configured focus areas"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        focus_service = context.services.get("focus")
        if not focus_service:
            return CommandResult(
                success=False,
                message="Focus area service not available",
                exit_code=1
            )
        
        areas = focus_service.list_focus_areas()
        
        if not areas:
            print("No focus areas configured.")
            return CommandResult(success=True, message="No focus areas found")
        
        print("\n=== Focus Areas ===")
        for i, area in enumerate(areas):
            name = area.get("title") or area.get("name") or f"Area {i+1}"
            enabled = area.get("enabled", True)
            priority = area.get("priority", i)
            print(f"{i+1:2d}. {name} | enabled={enabled} | priority={priority}")
        print("===================")
        
        return CommandResult(
            success=True,
            message=f"Found {len(areas)} focus areas"
        )

class AddFocusAreaCommand(CommandHandler):
    """Add a new focus area."""
    
    @property
    def name(self) -> str:
        return "add"
    
    @property
    def description(self) -> str:
        return "Add a new focus area"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            "title",
            metavar="TITLE",
            type=str,
            help="Title of the focus area"
        )
        parser.add_argument(
            "--description",
            metavar="TEXT",
            type=str,
            default="",
            help="Description of the focus area"
        )
        parser.add_argument(
            "--priority",
            metavar="NUMBER",
            type=int,
            default=999,
            help="Priority of the focus area (default: 999)"
        )
        parser.add_argument(
            "--enabled",
            action="store_true",
            default=True,
            help="Enable the focus area (default: enabled)"
        )
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        focus_service = context.services.get("focus")
        if not focus_service:
            return CommandResult(
                success=False,
                message="Focus area service not available",
                exit_code=1
            )
        
        success = focus_service.add_focus_area(
            title=args.title,
            description=args.description,
            priority=args.priority,
            enabled=args.enabled
        )
        
        if success:
            return CommandResult(
                success=True,
                message=f"Successfully added focus area: {args.title}"
            )
        else:
            return CommandResult(
                success=False,
                message=f"Failed to add focus area: {args.title}",
                exit_code=1
            )

class EditFocusAreaCommand(CommandHandler):
    """Edit an existing focus area."""
    
    @property
    def name(self) -> str:
        return "edit"
    
    @property
    def description(self) -> str:
        return "Edit an existing focus area"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            "id_or_name",
            metavar="ID_OR_NAME",
            type=str,
            help="ID or name of the focus area to edit"
        )
        parser.add_argument(
            "--title",
            metavar="TITLE",
            type=str,
            help="New title for the focus area"
        )
        parser.add_argument(
            "--description",
            metavar="TEXT",
            type=str,
            help="New description for the focus area"
        )
        parser.add_argument(
            "--priority",
            metavar="NUMBER",
            type=int,
            help="New priority for the focus area"
        )
        parser.add_argument(
            "--enabled",
            action="store_true",
            dest="enable",
            help="Enable the focus area"
        )
        parser.add_argument(
            "--disabled",
            action="store_false",
            dest="enable",
            help="Disable the focus area"
        )
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        focus_service = context.services.get("focus")
        if not focus_service:
            return CommandResult(
                success=False,
                message="Focus area service not available",
                exit_code=1
            )
        
        # Only pass parameters that were actually provided
        kwargs = {}
        if args.title is not None:
            kwargs["title"] = args.title
        if args.description is not None:
            kwargs["description"] = args.description
        if args.priority is not None:
            kwargs["priority"] = args.priority
        if hasattr(args, "enable"):
            kwargs["enabled"] = args.enable
        
        if not kwargs:
            return CommandResult(
                success=False,
                message="No changes specified. Use --title, --description, --priority, or --enabled/--disabled.",
                exit_code=1
            )
        
        success = focus_service.edit_focus_area(args.id_or_name, **kwargs)
        
        if success:
            return CommandResult(
                success=True,
                message=f"Successfully updated focus area: {args.id_or_name}"
            )
        else:
            return CommandResult(
                success=False,
                message=f"Failed to update focus area: {args.id_or_name}",
                exit_code=1
            )

class RemoveFocusAreaCommand(CommandHandler):
    """Remove a focus area."""
    
    @property
    def name(self) -> str:
        return "remove"
    
    @property
    def description(self) -> str:
        return "Remove a focus area"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            "id_or_name",
            metavar="ID_OR_NAME",
            type=str,
            help="ID or name of the focus area to remove"
        )
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        focus_service = context.services.get("focus")
        if not focus_service:
            return CommandResult(
                success=False,
                message="Focus area service not available",
                exit_code=1
            )
        
        success = focus_service.remove_focus_area(args.id_or_name)
        
        if success:
            return CommandResult(
                success=True,
                message=f"Successfully removed focus area: {args.id_or_name}"
            )
        else:
            return CommandResult(
                success=False,
                message=f"Failed to remove focus area: {args.id_or_name}",
                exit_code=1
            )

class ImportFocusAreasCommand(CommandHandler):
    """Import focus areas from a JSON file."""
    
    @property
    def name(self) -> str:
        return "import"
    
    @property
    def description(self) -> str:
        return "Import focus areas from a JSON file"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            "file_path",
            metavar="FILE_PATH",
            type=str,
            help="Path to the JSON file to import"
        )
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        focus_service = context.services.get("focus")
        if not focus_service:
            return CommandResult(
                success=False,
                message="Focus area service not available",
                exit_code=1
            )
        
        success = focus_service.import_focus_areas(args.file_path)
        
        if success:
            return CommandResult(
                success=True,
                message=f"Successfully imported focus areas from: {args.file_path}"
            )
        else:
            return CommandResult(
                success=False,
                message=f"Failed to import focus areas from: {args.file_path}",
                exit_code=1
            )

class ExportFocusAreasCommand(CommandHandler):
    """Export focus areas to a JSON file."""
    
    @property
    def name(self) -> str:
        return "export"
    
    @property
    def description(self) -> str:
        return "Export focus areas to a JSON file"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            "file_path",
            metavar="FILE_PATH",
            type=str,
            help="Path to the JSON file to export to"
        )
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        focus_service = context.services.get("focus")
        if not focus_service:
            return CommandResult(
                success=False,
                message="Focus area service not available",
                exit_code=1
            )
        
        success = focus_service.export_focus_areas(args.file_path)
        
        if success:
            return CommandResult(
                success=True,
                message=f"Successfully exported focus areas to: {args.file_path}"
            )
        else:
            return CommandResult(
                success=False,
                message=f"Failed to export focus areas to: {args.file_path}",
                exit_code=1
            )

class FocusCommandGroup(CommandGroup):
    """Focus area management command group."""
    
    def __init__(self):
        super().__init__("focus", "Focus area management commands")
        
        # Add commands to the group
        self.add_command(ListFocusAreasCommand())
        self.add_command(AddFocusAreaCommand())
        self.add_command(EditFocusAreaCommand())
        self.add_command(RemoveFocusAreaCommand())
        self.add_command(ImportFocusAreasCommand())
        self.add_command(ExportFocusAreasCommand())
