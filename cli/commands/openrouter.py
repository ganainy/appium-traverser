#!/usr/bin/env python3
"""
OpenRouter CLI command group.
"""


import argparse
from typing import Dict, List, Optional

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import ApplicationContext
from cli.constants import messages as MSG
from cli.constants import keys as K


class RefreshModelsCommand(CommandHandler):
    """Refresh OpenRouter models cache."""
    
    @property
    def name(self) -> str:
        return MSG.REFRESH_MODELS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.REFRESH_MODELS_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "--wait",
            action="store_true",
            help="Wait for refresh to complete before returning"
        )
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        openrouter_service = context.services.get(K.OPENROUTER_SERVICE)
        if not openrouter_service:
            return CommandResult(
                success=False,
                message=MSG.OPENROUTER_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        success, cache_path = openrouter_service.refresh_models(wait_for_completion=args.wait)
        if success:
            return CommandResult(
                success=True,
                message=MSG.SUCCESS_OPENROUTER_MODELS_REFRESHED.format(cache_path=cache_path) if cache_path else MSG.SUCCESS_OPENROUTER_MODELS_REFRESHED.format(cache_path="Unknown")
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.ERR_OPENROUTER_REFRESH_FAILED,
                exit_code=1
            )


class ListModelsCommand(CommandHandler):
    """List OpenRouter models."""
    
    @property
    def name(self) -> str:
        return MSG.LIST_MODELS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.LIST_MODELS_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "--free-only",
            action="store_true",
            help=MSG.LIST_MODELS_FREE_ONLY
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help=MSG.LIST_MODELS_ALL
        )
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        openrouter_service = context.services.get(K.OPENROUTER_SERVICE)
        if not openrouter_service:
            return CommandResult(
                success=False,
                message=MSG.OPENROUTER_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        success, models = openrouter_service.list_models(free_only=args.free_only, all_models=args.all)
        if not success:
            return CommandResult(
                success=False,
                message=MSG.LIST_MODELS_FAIL,
                exit_code=1
            )
        if not models:
            telemetry_service.print_model_list(models)
            return CommandResult(success=True, message=MSG.LIST_MODELS_NONE)
        telemetry_service.print_model_list(models)
        telemetry_service.print_info(MSG.LIST_MODELS_SELECT_HINT)
        return CommandResult(
            success=True,
            message=MSG.LIST_MODELS_SUCCESS.format(count=len(models))
        )


class SelectModelCommand(CommandHandler):
    """Select an OpenRouter model."""
    
    @property
    def name(self) -> str:
        return MSG.SELECT_MODEL_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.SELECT_MODEL_DESC
    
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
            help=MSG.SELECT_MODEL_ARG
        )
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        openrouter_service = context.services.get(K.OPENROUTER_SERVICE)
        if not openrouter_service:
            return CommandResult(
                success=False,
                message=MSG.OPENROUTER_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        success, data = openrouter_service.select_model(args.model_identifier)
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
                message=MSG.SELECT_MODEL_FAIL.format(identifier=args.model_identifier),
                exit_code=1
            )


class ShowSelectionCommand(CommandHandler):
    """Show currently selected OpenRouter model."""
    
    @property
    def name(self) -> str:
        return MSG.SHOW_SELECTION_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.SHOW_SELECTION_DESC
    
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
        openrouter_service = context.services.get(K.OPENROUTER_SERVICE)
        if not openrouter_service:
            return CommandResult(
                success=False,
                message=MSG.OPENROUTER_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        selected_model = openrouter_service.get_selected_model()
        
        # Delegate presentation to telemetry service
        telemetry_service.print_selected_model(selected_model)
        
        if selected_model:
            model_id = selected_model.get(K.MODEL_ID, K.DEFAULT_UNKNOWN)
            model_name = selected_model.get(K.MODEL_NAME, K.DEFAULT_UNKNOWN)
            return CommandResult(
                success=True,
                message=MSG.SHOW_SELECTION_SUCCESS.format(name=model_name, id=model_id)
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.SHOW_SELECTION_FAIL,
                exit_code=1
            )


class ShowModelDetailsCommand(CommandHandler):
    """Show detailed information about selected model."""
    
    @property
    def name(self) -> str:
        return MSG.SHOW_MODEL_DETAILS_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.SHOW_MODEL_DETAILS_DESC
    
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
        openrouter_service = context.services.get(K.OPENROUTER_SERVICE)
        if not openrouter_service:
            return CommandResult(
                success=False,
                message=MSG.OPENROUTER_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        success, data = openrouter_service.show_model_details()
        
        if success:
            # Delegate presentation to telemetry service
            telemetry_service.print_model_details(data)
            return CommandResult(
                success=True,
                message=MSG.SHOW_MODEL_DETAILS_SUCCESS
            )
        else:
            # Handle error presentation using telemetry service
            telemetry_service.print_error(data.get('error', 'Unknown error'))
            return CommandResult(
                success=False,
                message=MSG.SHOW_MODEL_DETAILS_FAIL,
                exit_code=1
            )


class ConfigureImageContextCommand(CommandHandler):
    """Configure image context for vision models."""
    
    @property
    def name(self) -> str:
        return MSG.CONFIGURE_IMAGE_CONTEXT_CMD_NAME

    @property
    def description(self) -> str:
        return MSG.CONFIGURE_IMAGE_CONTEXT_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "--model",
            metavar="MODEL_ID",
            help=MSG.CONFIGURE_IMAGE_CONTEXT_MODEL_ARG
        )
        parser.add_argument(
            "--enable",
            action="store_true",
            help=MSG.CONFIGURE_IMAGE_CONTEXT_ENABLE
        )
        parser.add_argument(
            "--disable",
            action="store_true",
            help=MSG.CONFIGURE_IMAGE_CONTEXT_DISABLE
        )
        parser.set_defaults(**{K.HANDLER: self})
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        openrouter_service = context.services.get(K.OPENROUTER_SERVICE)
        if not openrouter_service:
            return CommandResult(
                success=False,
                message=MSG.OPENROUTER_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        telemetry_service = context.services.get(K.TELEMETRY_SERVICE)
        if not telemetry_service:
            return CommandResult(
                success=False,
                message=MSG.TELEMETRY_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        # Validate arguments
        if args.enable and args.disable:
            return CommandResult(
                success=False,
                message=MSG.CONFIGURE_IMAGE_CONTEXT_CONFLICT,
                exit_code=1
            )
        enabled = None
        if args.enable:
            enabled = True
        elif args.disable:
            enabled = False
        
        success, data = openrouter_service.configure_image_context(
            model_identifier=args.model,
            enabled=enabled
        )
        
        if success:
            # Delegate presentation to telemetry service
            telemetry_service.print_image_context_configuration(data)
            action = data.get("action", "configured")
            return CommandResult(
                success=True,
                message=MSG.CONFIGURE_IMAGE_CONTEXT_SUCCESS.format(action=action)
            )
        else:
            # Handle error presentation using telemetry service
            telemetry_service.print_error(data.get('error', 'Unknown error'))
            return CommandResult(
                success=False,
                message=MSG.CONFIGURE_IMAGE_CONTEXT_FAIL,
                exit_code=1
            )


class OpenRouterCommandGroup(CommandGroup):
    """OpenRouter command group."""
    
    def __init__(self):
        super().__init__(MSG.OPENROUTER_GROUP_NAME, MSG.OPENROUTER_GROUP_DESC)
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            RefreshModelsCommand(),
            ListModelsCommand(),
            SelectModelCommand(),
            ShowSelectionCommand(),
            ShowModelDetailsCommand(),
            ConfigureImageContextCommand(),
        ]
