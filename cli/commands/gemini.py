#!/usr/bin/env python3
"""
Gemini CLI command group.
"""


import argparse
from typing import Dict, List, Optional

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import ApplicationContext
from cli.constants import messages as MSG
from cli.constants import keys as K


class RefreshModelsCommand(CommandHandler):
    """Refresh Gemini models cache."""
    
    @property
    def name(self) -> str:
        return MSG.GEMINI_REFRESH_MODELS_CMD_NAME
    
    @property
    def description(self) -> str:
        return MSG.GEMINI_REFRESH_MODELS_DESC
    
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
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        gemini_service = context.services.get(K.GEMINI_SERVICE)
        if not gemini_service:
            return CommandResult(
                success=False,
                message=MSG.GEMINI_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        # Default to waiting (invert the --no-wait flag)
        wait_for_completion = not getattr(args, 'no_wait', False)
        success, cache_path, error_msg = gemini_service.refresh_models(wait_for_completion=wait_for_completion)
        if success:
            if cache_path:
                # Refresh completed successfully
                return CommandResult(
                    success=True,
                    message=MSG.SUCCESS_GEMINI_MODELS_REFRESHED.format(cache_path=cache_path)
                )
            else:
                # Background refresh started (only happens with --no-wait)
                return CommandResult(
                    success=True,
                    message="Gemini models refresh started in background"
                )
        else:
            # Use the error message from service, or fall back to generic message
            message = error_msg if error_msg else MSG.ERR_GEMINI_REFRESH_FAILED
            return CommandResult(
                success=False,
                message=message,
                exit_code=1
            )


class ListModelsCommand(CommandHandler):
    """List Gemini models."""
    
    @property
    def name(self) -> str:
        return MSG.GEMINI_LIST_MODELS_CMD_NAME
    
    @property
    def description(self) -> str:
        return MSG.GEMINI_LIST_MODELS_DESC
    
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
            help="Don't refresh models from API (use cache only)"
        )
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        gemini_service = context.services.get(K.GEMINI_SERVICE)
        if not gemini_service:
            return CommandResult(
                success=False,
                message=MSG.GEMINI_SERVICE_NOT_AVAILABLE,
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
        success, models = gemini_service.list_models(refresh=refresh)
        if not success:
            return CommandResult(
                success=False,
                message=MSG.GEMINI_LIST_MODELS_FAIL,
                exit_code=1
            )
        if not models:
            telemetry_service.print_model_list(models)
            return CommandResult(success=True, message=MSG.GEMINI_LIST_MODELS_NONE)
        telemetry_service.print_model_list(models)
        telemetry_service.print_info(MSG.GEMINI_LIST_MODELS_SELECT_HINT)
        return CommandResult(
            success=True,
            message=MSG.GEMINI_LIST_MODELS_SUCCESS.format(count=len(models))
        )


class SelectModelCommand(CommandHandler):
    """Select a Gemini model."""
    
    @property
    def name(self) -> str:
        return MSG.GEMINI_SELECT_MODEL_CMD_NAME
    
    @property
    def description(self) -> str:
        return MSG.GEMINI_SELECT_MODEL_DESC
    
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
            help=MSG.GEMINI_SELECT_MODEL_ARG
        )
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        gemini_service = context.services.get(K.GEMINI_SERVICE)
        if not gemini_service:
            return CommandResult(
                success=False,
                message=MSG.GEMINI_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        success, data = gemini_service.select_model(args.model_identifier)
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
                message=MSG.GEMINI_SELECT_MODEL_FAIL.format(identifier=args.model_identifier),
                exit_code=1
            )


class ShowSelectionCommand(CommandHandler):
    """Show currently selected Gemini model."""
    
    @property
    def name(self) -> str:
        return MSG.GEMINI_SHOW_SELECTION_CMD_NAME
    
    @property
    def description(self) -> str:
        return MSG.GEMINI_SHOW_SELECTION_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        gemini_service = context.services.get(K.GEMINI_SERVICE)
        if not gemini_service:
            return CommandResult(
                success=False,
                message=MSG.GEMINI_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        selected_model = gemini_service.get_selected_model()
        
        if not selected_model:
            telemetry_service.print_error(MSG.GEMINI_SHOW_SELECTION_FAIL)
            return CommandResult(
                success=False,
                message=MSG.GEMINI_SHOW_SELECTION_FAIL,
                exit_code=1
            )
        
        model_name = selected_model.get("display_name") or selected_model.get("name") or selected_model.get("id", "")
        model_id = selected_model.get("id", "")
        
        telemetry_service.print_info(
            message=MSG.GEMINI_SHOW_SELECTION_SUCCESS.format(name=model_name, id=model_id)
        )
        
        return CommandResult(
            success=True,
            message=MSG.GEMINI_SHOW_SELECTION_SUCCESS.format(name=model_name, id=model_id)
        )


class ShowModelDetailsCommand(CommandHandler):
    """Show detailed information about selected model."""
    
    @property
    def name(self) -> str:
        return MSG.GEMINI_SHOW_MODEL_DETAILS_CMD_NAME
    
    @property
    def description(self) -> str:
        return MSG.GEMINI_SHOW_MODEL_DETAILS_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        gemini_service = context.services.get(K.GEMINI_SERVICE)
        if not gemini_service:
            return CommandResult(
                success=False,
                message=MSG.GEMINI_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        success, data = gemini_service.show_model_details()
        
        if success:
            # Delegate presentation to telemetry service
            telemetry_service.print_model_details(data)
            return CommandResult(
                success=True,
                message=MSG.GEMINI_SHOW_MODEL_DETAILS_SUCCESS
            )
        else:
            # Handle error presentation using telemetry service
            telemetry_service.print_error(data.get('error', 'Unknown error'))
            return CommandResult(
                success=False,
                message=MSG.GEMINI_SHOW_MODEL_DETAILS_FAIL,
                exit_code=1
            )


class GeminiCommandGroup(CommandGroup):
    """Gemini command group."""
    
    def __init__(self):
        super().__init__(MSG.GEMINI_GROUP_NAME, MSG.GEMINI_GROUP_DESC)
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            RefreshModelsCommand(),
            ListModelsCommand(),
            SelectModelCommand(),
            ShowSelectionCommand(),
            ShowModelDetailsCommand(),
        ]

