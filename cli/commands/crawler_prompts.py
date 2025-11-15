#!/usr/bin/env python3
"""
Crawler prompt template management commands.

This module provides CLI commands for managing crawler prompt templates:
- list: Display all configured prompt templates
- edit: Modify an existing prompt template
- remove: Delete a prompt template

Prompt templates are stored in the database and used by the AI agent
to make decisions during app crawling. The default prompt is automatically
initialized on first launch.
"""


import argparse
from typing import List, Dict, Any, Optional

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import ApplicationContext
from cli.constants import messages as MSG
from cli.constants import keys as KEY


class ListCrawlerPromptsCommand(CommandHandler):
    """List all configured crawler prompt templates."""
    
    @property
    def name(self) -> str:
        return MSG.LIST_PROMPTS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.LIST_PROMPTS_CMD_DESC
    
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
        prompts_service: Optional[Any] = context.services.get(KEY.PROMPTS_SERVICE)
        if prompts_service is None:
            return CommandResult(
                success=False,
                message=MSG.PROMPTS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        telemetry_service: Optional[Any] = context.services.get(KEY.TELEMETRY_SERVICE)
        if telemetry_service is None:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        all_prompts: List[Dict[str, Any]] = prompts_service.get_prompts()
        prompt_count: int = len(all_prompts)
        
        # Display prompts in a formatted numbered list
        print(f"\n=== Crawler Prompt Templates ({prompt_count}) ===")
        for index, prompt_data in enumerate(all_prompts, start=1):
            is_enabled: bool = prompt_data.get("enabled", True)
            enabled_indicator: str = "✓" if is_enabled else "✗"
            prompt_name: str = prompt_data.get("name", "Unknown")
            template_text: str = prompt_data.get("template", "")
            
            # Create a preview of the template (first 60 characters)
            template_preview: str = (
                template_text[:60] + "..." 
                if len(template_text) > 60 
                else template_text
            )
            
            print(f"{index:2d}. {enabled_indicator} {prompt_name}")
            print(f"    {template_preview}")
        print("==============================")

        return CommandResult(
            success=True,
            message=MSG.FOUND_PROMPTS.format(count=prompt_count)
        )


class EditCrawlerPromptCommand(CommandHandler):
    """Edit an existing crawler prompt template."""
    
    @property
    def name(self) -> str:
        return MSG.EDIT_PROMPTS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.EDIT_PROMPTS_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            MSG.EDIT_PROMPTS_ARG_ID_OR_NAME,
            metavar=MSG.EDIT_PROMPTS_ARG_ID_OR_NAME_METAVAR,
            type=str,
            help=MSG.EDIT_PROMPTS_ARG_ID_OR_NAME_HELP
        )
        parser.add_argument(
            f"--{MSG.EDIT_PROMPTS_ARG_NAME}",
            metavar=MSG.EDIT_PROMPTS_ARG_NAME_METAVAR,
            type=str,
            help=MSG.EDIT_PROMPTS_ARG_NAME_HELP,
            default=None
        )
        parser.add_argument(
            f"--{MSG.EDIT_PROMPTS_ARG_TEMPLATE}",
            metavar=MSG.EDIT_PROMPTS_ARG_TEMPLATE_METAVAR,
            type=str,
            help=MSG.EDIT_PROMPTS_ARG_TEMPLATE_HELP,
            default=None
        )
        parser.add_argument(
            f"--{MSG.EDIT_PROMPTS_ARG_ENABLED}",
            action="store_true",
            dest="enable",
            help=MSG.EDIT_PROMPTS_ARG_ENABLED_HELP
        )
        parser.add_argument(
            f"--{MSG.EDIT_PROMPTS_ARG_DISABLED}",
            action="store_false",
            dest="enable",
            help=MSG.EDIT_PROMPTS_ARG_DISABLED_HELP
        )
        parser.set_defaults(enable=None)
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the edit command."""
        prompts_service: Optional[Any] = context.services.get(KEY.PROMPTS_SERVICE)
        if prompts_service is None:
            return CommandResult(
                success=False,
                message=MSG.PROMPTS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        # Collect only the parameters that were explicitly provided
        update_parameters: Dict[str, Any] = {}
        
        new_name: Optional[str] = getattr(args, MSG.EDIT_PROMPTS_ARG_NAME, None)
        if new_name is not None:
            update_parameters["name"] = new_name
        
        new_template: Optional[str] = getattr(args, MSG.EDIT_PROMPTS_ARG_TEMPLATE, None)
        if new_template is not None:
            update_parameters["template"] = new_template
        
        enabled_state: Optional[bool] = getattr(args, "enable", None)
        if enabled_state is not None:
            update_parameters["enabled"] = enabled_state

        # Validate that at least one parameter was provided
        if not update_parameters:
            return CommandResult(
                success=False,
                message=MSG.EDIT_PROMPTS_NO_CHANGES,
                exit_code=1
            )

        prompt_identifier: str = getattr(args, MSG.EDIT_PROMPTS_ARG_ID_OR_NAME)
        operation_success: bool
        operation_message: Optional[str]
        operation_success, operation_message = prompts_service.edit_prompt(
            id_or_name=prompt_identifier, 
            **update_parameters
        )

        if operation_success:
            return CommandResult(
                success=True,
                message=MSG.EDIT_PROMPTS_SUCCESS.format(id_or_name=prompt_identifier)
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.EDIT_PROMPTS_FAIL.format(id_or_name=prompt_identifier),
                exit_code=1
            )


class RemoveCrawlerPromptCommand(CommandHandler):
    """Remove a crawler prompt template."""
    
    @property
    def name(self) -> str:
        return MSG.REMOVE_PROMPTS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.REMOVE_PROMPTS_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            MSG.REMOVE_PROMPTS_ARG_ID_OR_NAME,
            metavar=MSG.REMOVE_PROMPTS_ARG_ID_OR_NAME_METAVAR,
            type=str,
            help=MSG.REMOVE_PROMPTS_ARG_ID_OR_NAME_HELP
        )
        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the remove command."""
        prompts_service: Optional[Any] = context.services.get(KEY.PROMPTS_SERVICE)
        if prompts_service is None:
            return CommandResult(
                success=False,
                message=MSG.PROMPTS_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        prompt_identifier: str = getattr(args, MSG.REMOVE_PROMPTS_ARG_ID_OR_NAME)
        operation_success: bool
        operation_message: Optional[str]
        operation_success, operation_message = prompts_service.remove_prompt(prompt_identifier)

        if operation_success:
            return CommandResult(
                success=True,
                message=MSG.REMOVE_PROMPTS_SUCCESS.format(id_or_name=prompt_identifier)
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.REMOVE_PROMPTS_FAIL.format(id_or_name=prompt_identifier),
                exit_code=1
            )


class CrawlerPromptsCommandGroup(CommandGroup):
    """Command group for managing crawler prompt templates."""
    
    def __init__(self):
        super().__init__("prompts", MSG.PROMPTS_COMMAND_GROUP_DESC)
    
    def get_commands(self) -> List[CommandHandler]:
        """Return a list of CommandHandler instances for this group."""
        return [
            ListCrawlerPromptsCommand(),
            EditCrawlerPromptCommand(),
            RemoveCrawlerPromptCommand()
        ]

