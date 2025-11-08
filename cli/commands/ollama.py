#!/usr/bin/env python3
"""
Ollama CLI command group.
"""


import argparse
from typing import Dict, List, Optional

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext
from cli.constants import messages as MSG
from cli.constants import keys as K


class RefreshModelsCommand(CommandHandler):
    """Refresh Ollama models cache."""
    
    @property
    def name(self) -> str:
        return MSG.OLLAMA_REFRESH_MODELS_CMD_NAME
    
    @property
    def description(self) -> str:
        return MSG.OLLAMA_REFRESH_MODELS_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "--no-wait",
            action="store_true",
            help="Don't wait for refresh to complete (run in background)"
        )
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        ollama_service = context.services.get(K.OLLAMA_SERVICE)
        if not ollama_service:
            return CommandResult(
                success=False,
                message=MSG.OLLAMA_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        # Default to waiting (invert the --no-wait flag)
        wait_for_completion = not getattr(args, 'no_wait', False)
        success, cache_path, error_msg = ollama_service.refresh_models(wait_for_completion=wait_for_completion)
        if success:
            if cache_path:
                # Refresh completed successfully
                return CommandResult(
                    success=True,
                    message=MSG.SUCCESS_OLLAMA_MODELS_REFRESHED.format(cache_path=cache_path)
                )
            else:
                # Background refresh started (only happens with --no-wait)
                return CommandResult(
                    success=True,
                    message="Ollama models refresh started in background"
                )
        else:
            # Use the error message from service, or fall back to generic message
            message = error_msg if error_msg else MSG.ERR_OLLAMA_REFRESH_FAILED
            return CommandResult(
                success=False,
                message=message,
                exit_code=1
            )


class ListModelsCommand(CommandHandler):
    """List Ollama models."""
    
    @property
    def name(self) -> str:
        return MSG.OLLAMA_LIST_MODELS_CMD_NAME
    
    @property
    def description(self) -> str:
        return MSG.OLLAMA_LIST_MODELS_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "--no-refresh",
            action="store_true",
            help="Don't refresh models from Ollama (use cache only)"
        )
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        ollama_service = context.services.get(K.OLLAMA_SERVICE)
        if not ollama_service:
            return CommandResult(
                success=False,
                message=MSG.OLLAMA_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        # Default to refreshing (invert the --no-refresh flag)
        refresh = not getattr(args, 'no_refresh', False)
        success, models = ollama_service.list_models(refresh=refresh)
        if not success:
            return CommandResult(
                success=False,
                message=MSG.OLLAMA_LIST_MODELS_FAIL,
                exit_code=1
            )
        if not models:
            telemetry_service.print_model_list(models)
            return CommandResult(success=True, message=MSG.OLLAMA_LIST_MODELS_NONE)
        telemetry_service.print_model_list(models)
        telemetry_service.print_info(MSG.OLLAMA_LIST_MODELS_SELECT_HINT)
        return CommandResult(
            success=True,
            message=MSG.OLLAMA_LIST_MODELS_SUCCESS.format(count=len(models))
        )


class SelectModelCommand(CommandHandler):
    """Select an Ollama model."""
    
    @property
    def name(self) -> str:
        return MSG.OLLAMA_SELECT_MODEL_CMD_NAME
    
    @property
    def description(self) -> str:
        return MSG.OLLAMA_SELECT_MODEL_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "model_identifier",
            metavar="ID_OR_NAME",
            help=MSG.OLLAMA_SELECT_MODEL_ARG
        )
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        ollama_service = context.services.get(K.OLLAMA_SERVICE)
        if not ollama_service:
            return CommandResult(
                success=False,
                message=MSG.OLLAMA_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        success, data = ollama_service.select_model(args.model_identifier)
        if success:
            # Delegate presentation to telemetry service
            telemetry_service.print_model_selection(data)
            
            # Return success without duplicate message (already printed by telemetry service)
            return CommandResult(success=True, message="")
        else:
            # Handle error presentation using telemetry service
            telemetry_service.print_error(data.get('error', 'Unknown error'))
            return CommandResult(
                success=False,
                message=MSG.OLLAMA_SELECT_MODEL_FAIL.format(identifier=args.model_identifier),
                exit_code=1
            )


class ShowSelectionCommand(CommandHandler):
    """Show currently selected Ollama model."""
    
    @property
    def name(self) -> str:
        return MSG.OLLAMA_SHOW_SELECTION_CMD_NAME
    
    @property
    def description(self) -> str:
        return MSG.OLLAMA_SHOW_SELECTION_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        ollama_service = context.services.get(K.OLLAMA_SERVICE)
        if not ollama_service:
            return CommandResult(
                success=False,
                message=MSG.OLLAMA_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        selected_model = ollama_service.get_selected_model()
        
        if not selected_model:
            # Show Ollama-specific message when no model is selected
            print(MSG.UI_NO_OLLAMA_MODEL_SELECTED)
            return CommandResult(
                success=False,
                message=MSG.OLLAMA_SHOW_SELECTION_FAIL,
                exit_code=1
            )
        
        # Delegate presentation to telemetry service
        telemetry_service.print_selected_model(selected_model)
        model_id = selected_model.get(K.MODEL_ID, K.DEFAULT_UNKNOWN)
        model_name = selected_model.get(K.MODEL_NAME, K.DEFAULT_UNKNOWN)
        return CommandResult(
            success=True,
            message=MSG.OLLAMA_SHOW_SELECTION_SUCCESS.format(name=model_name, id=model_id)
        )


class ShowModelDetailsCommand(CommandHandler):
    """Show detailed information about selected model."""
    
    @property
    def name(self) -> str:
        return MSG.OLLAMA_SHOW_MODEL_DETAILS_CMD_NAME
    
    @property
    def description(self) -> str:
        return MSG.OLLAMA_SHOW_MODEL_DETAILS_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        ollama_service = context.services.get(K.OLLAMA_SERVICE)
        if not ollama_service:
            return CommandResult(
                success=False,
                message=MSG.OLLAMA_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        success, data = ollama_service.show_model_details()
        
        if success:
            # Delegate presentation to telemetry service
            telemetry_service.print_model_details(data)
            return CommandResult(
                success=True,
                message=MSG.OLLAMA_SHOW_MODEL_DETAILS_SUCCESS
            )
        else:
            # Handle error presentation using telemetry service
            telemetry_service.print_error(data.get('error', 'Unknown error'))
            return CommandResult(
                success=False,
                message=MSG.OLLAMA_SHOW_MODEL_DETAILS_FAIL,
                exit_code=1
            )


class OllamaCommandGroup(CommandGroup):
    """Ollama command group."""
    
    def __init__(self):
        super().__init__(MSG.OLLAMA_GROUP_NAME, MSG.OLLAMA_GROUP_DESC)
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            RefreshModelsCommand(),
            ListModelsCommand(),
            SelectModelCommand(),
            ShowSelectionCommand(),
            ShowModelDetailsCommand(),
        ]

