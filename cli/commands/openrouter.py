#!/usr/bin/env python3
"""
OpenRouter CLI command group.
"""

import argparse
from typing import Dict, List, Optional

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext


class RefreshModelsCommand(CommandHandler):
    """Refresh OpenRouter models cache."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "refresh-models"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Refresh OpenRouter models cache"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
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
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        openrouter_service = context.services.get("openrouter")
        if not openrouter_service:
            return CommandResult(
                success=False,
                message="OpenRouter service not available",
                exit_code=1
            )
        
        success = openrouter_service.refresh_models(wait_for_completion=args.wait)
        
        if success:
            return CommandResult(
                success=True,
                message="OpenRouter models cache refreshed successfully"
            )
        else:
            return CommandResult(
                success=False,
                message="Failed to refresh OpenRouter models cache",
                exit_code=1
            )


class ListModelsCommand(CommandHandler):
    """List OpenRouter models."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "list-models"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "List available OpenRouter models"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "--free-only",
            action="store_true",
            help="Show only free models"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Show all models (ignores OPENROUTER_SHOW_FREE_ONLY config)"
        )
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        openrouter_service = context.services.get("openrouter")
        if not openrouter_service:
            return CommandResult(
                success=False,
                message="OpenRouter service not available",
                exit_code=1
            )
        
        # Determine filter setting
        free_only = None
        if args.free_only:
            free_only = True
        elif args.all:
            free_only = False
        
        success, models = openrouter_service.list_models(free_only=free_only)
        
        if not success:
            return CommandResult(
                success=False,
                message="Failed to list OpenRouter models. Try running refresh-models first.",
                exit_code=1
            )
        
        if not models:
            print("No models available.")
            return CommandResult(success=True, message="No models found")
        
        print(f"\n=== OpenRouter Models ({len(models)}) ===")
        for i, model in enumerate(models):
            model_id = model.get("id", "Unknown")
            model_name = model.get("name", "Unknown")
            pricing = model.get("pricing", {})
            
            # Check if free
            is_free = (pricing.get("prompt", "0") == "0" and 
                      pricing.get("completion", "0") == "0")
            
            free_marker = "[FREE]" if is_free else ""
            print(f"{i+1:2d}. {model_name} {free_marker}")
            print(f"    ID: {model_id}")
            print(f"    Prompt: {pricing.get('prompt', 'N/A')} | Completion: {pricing.get('completion', 'N/A')}")
            print()
        
        print("==============================")
        
        return CommandResult(
            success=True,
            message=f"Listed {len(models)} OpenRouter models"
        )


class SelectModelCommand(CommandHandler):
    """Select an OpenRouter model."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "select-model"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Select an OpenRouter model by index or name"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "model_identifier",
            metavar="ID_OR_NAME",
            help="Model index (1-based) or name/ID fragment"
        )
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        openrouter_service = context.services.get("openrouter")
        if not openrouter_service:
            return CommandResult(
                success=False,
                message="OpenRouter service not available",
                exit_code=1
            )
        
        success, selected_model = openrouter_service.select_model(args.model_identifier)
        
        if success:
            model_id = selected_model.get("id", "Unknown")
            model_name = selected_model.get("name", "Unknown")
            return CommandResult(
                success=True,
                message=f"Selected OpenRouter model: {model_name} ({model_id})"
            )
        else:
            return CommandResult(
                success=False,
                message=f"Failed to select model: {args.model_identifier}",
                exit_code=1
            )


class ShowSelectionCommand(CommandHandler):
    """Show currently selected OpenRouter model."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "show-selection"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Show currently selected OpenRouter model"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        openrouter_service = context.services.get("openrouter")
        if not openrouter_service:
            return CommandResult(
                success=False,
                message="OpenRouter service not available",
                exit_code=1
            )
        
        selected_model = openrouter_service.get_selected_model()
        
        if selected_model:
            model_id = selected_model.get("id", "Unknown")
            model_name = selected_model.get("name", "Unknown")
            print(f"\n=== Selected OpenRouter Model ===")
            print(f"Name: {model_name}")
            print(f"ID: {model_id}")
            print("==============================")
            
            return CommandResult(
                success=True,
                message=f"Selected model: {model_name} ({model_id})"
            )
        else:
            print("No OpenRouter model selected.")
            return CommandResult(
                success=False,
                message="No model selected",
                exit_code=1
            )


class ShowModelDetailsCommand(CommandHandler):
    """Show detailed information about selected model."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "show-model-details"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Show detailed information about selected model"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        openrouter_service = context.services.get("openrouter")
        if not openrouter_service:
            return CommandResult(
                success=False,
                message="OpenRouter service not available",
                exit_code=1
            )
        
        success = openrouter_service.show_model_details()
        
        if success:
            return CommandResult(
                success=True,
                message="Model details displayed"
            )
        else:
            return CommandResult(
                success=False,
                message="Failed to show model details",
                exit_code=1
            )


class ConfigureImageContextCommand(CommandHandler):
    """Configure image context for vision models."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "configure-image-context"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Configure image context for vision models"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "--model",
            metavar="MODEL_ID",
            help="Model ID (uses current if not specified)"
        )
        parser.add_argument(
            "--enable",
            action="store_true",
            help="Enable image context"
        )
        parser.add_argument(
            "--disable",
            action="store_true",
            help="Disable image context"
        )
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        openrouter_service = context.services.get("openrouter")
        if not openrouter_service:
            return CommandResult(
                success=False,
                message="OpenRouter service not available",
                exit_code=1
            )
        
        # Validate arguments
        if args.enable and args.disable:
            return CommandResult(
                success=False,
                message="Cannot specify both --enable and --disable",
                exit_code=1
            )
        
        enabled = None
        if args.enable:
            enabled = True
        elif args.disable:
            enabled = False
        
        success = openrouter_service.configure_image_context(
            model_identifier=args.model,
            enabled=enabled
        )
        
        if success:
            action = "enabled" if args.enable else ("disabled" if args.disable else "checked")
            return CommandResult(
                success=True,
                message=f"Image context {action} for model"
            )
        else:
            return CommandResult(
                success=False,
                message="Failed to configure image context",
                exit_code=1
            )


class OpenRouterCommandGroup(CommandGroup):
    """OpenRouter command group."""
    
    def __init__(self):
        """Initialize OpenRouter command group."""
        super().__init__("openrouter", "OpenRouter model management commands")
    
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
