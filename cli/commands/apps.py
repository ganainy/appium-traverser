#!/usr/bin/env python3
"""
App management commands.
"""

import argparse
from typing import List

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext


class ScanAllAppsCommand(CommandHandler):
    """Scan device and cache ALL installed apps with AI health filtering."""

    @property
    def name(self) -> str:
        """Get command name."""
        return "scan-all"

    @property
    def description(self) -> str:
        """Get command description."""
        return "Scan device and cache ALL installed apps with AI health filtering (merged file)"

    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "--force-rescan",
            action="store_true",
            help="Force rescan even if cache exists"
        )
        return parser

    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        app_service = context.services.get("app_scan")
        if not app_service:
            return CommandResult(
                success=False,
                message="App scan service not available",
                exit_code=1
            )

        # Now scan_all_apps actually performs AI filtering too (merged approach)
        success, cache_path = app_service.scan_all_apps(force_rescan=args.force_rescan)

        if success:
            return CommandResult(
                success=True,
                message=f"Successfully scanned and cached apps with AI filtering. Cache at: {cache_path}"
            )
        else:
            return CommandResult(
                success=False,
                message="Failed to scan apps",
                exit_code=1
            )


class ScanHealthAppsCommand(CommandHandler):
    """Scan device and cache apps with AI health filtering (alias for scan-all)."""

    @property
    def name(self) -> str:
        """Get command name."""
        return "scan-health"

    @property
    def description(self) -> str:
        """Get command description."""
        return "Scan device and cache apps with AI health filtering (same as scan-all)"

    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "--force-rescan",
            action="store_true",
            help="Force rescan even if cache exists"
        )
        return parser

    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        app_service = context.services.get("app_scan")
        if not app_service:
            return CommandResult(
                success=False,
                message="App scan service not available",
                exit_code=1
            )

        # Use the same scan method as scan-all (both perform AI filtering now)
        success, cache_path = app_service.scan_health_apps(force_rescan=args.force_rescan)

        if success:
            return CommandResult(
                success=True,
                message=f"Successfully scanned apps with AI health filtering. Cache at: {cache_path}"
            )
        else:
            return CommandResult(
                success=False,
                message="Failed to scan apps",
                exit_code=1
            )


class ListAllAppsCommand(CommandHandler):
    """List ALL apps from the latest merged cache."""

    @property
    def name(self) -> str:
        """Get command name."""
        return "list-all"

    @property
    def description(self) -> str:
        """Get command description."""
        return "List ALL apps from the latest merged cache"

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
        app_service = context.services.get("app_scan")
        if not app_service:
            return CommandResult(
                success=False,
                message="App scan service not available",
                exit_code=1
            )

        # Get the latest merged cache file
        cache_path = app_service.resolve_latest_cache_file("all")
        if not cache_path:
            print("No app cache found. Run 'apps scan-all' or 'apps scan-health' first.")
            return CommandResult(
                success=False,
                message="No app cache found",
                exit_code=1
            )

        # Load all_apps from the merged file by directly reading it
        import json
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "all_apps" in data and isinstance(data["all_apps"], list):
                apps = data["all_apps"]
            else:
                # Fallback to default loading (health_apps)
                success, apps = app_service.load_apps_from_file(cache_path)
                if not success:
                    return CommandResult(
                        success=False,
                        message="Failed to load apps from cache",
                        exit_code=1
                    )
        except Exception as e:
            return CommandResult(
                success=False,
                message=f"Failed to load apps from cache: {e}",
                exit_code=1
            )

        if not apps:
            print("No apps found in cache.")
            return CommandResult(success=True, message="No apps found")

        print(f"\n=== All Apps ({len(apps)}) ===")
        for i, app in enumerate(apps):
            name = app.get("app_name", "Unknown")
            package = app.get("package_name", "Unknown")
            print(f"{i+1:2d}. {name} ({package})")
        print("========================")

        return CommandResult(
            success=True,
            message=f"Listed {len(apps)} apps"
        )


class ListHealthAppsCommand(CommandHandler):
    """List health apps from the latest cache."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "list-health"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "List health apps from the latest cache"
    
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
        app_service = context.services.get("app_scan")
        if not app_service:
            return CommandResult(
                success=False,
                message="App scan service not available",
                exit_code=1
            )
        
        # Get health apps from the merged cache file
        cache_path = app_service.resolve_latest_cache_file("health")
        if not cache_path:
            print("No app cache found. Run 'apps scan-all' or 'apps scan-health' first.")
            return CommandResult(
                success=False,
                message="No app cache found",
                exit_code=1
            )

        # Load health_apps from the merged file by directly reading it
        import json
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "health_apps" in data and isinstance(data["health_apps"], list):
                apps = data["health_apps"]
            else:
                # Fallback to default loading
                success, apps = app_service.load_apps_from_file(cache_path)
                if not success:
                    return CommandResult(
                        success=False,
                        message="Failed to load apps from cache",
                        exit_code=1
                    )
        except Exception as e:
            return CommandResult(
                success=False,
                message=f"Failed to load apps from cache: {e}",
                exit_code=1
            )

        if not apps:
            print("No health apps found in cache.")
            return CommandResult(success=True, message="No health apps found")

        print(f"\n=== Health Apps ({len(apps)}) ===")
        for i, app in enumerate(apps):
            name = app.get("app_name", "Unknown")
            package = app.get("package_name", "Unknown")
            print(f"{i+1:2d}. {name} ({package})")
        print("==========================")

        return CommandResult(
            success=True,
            message=f"Listed {len(apps)} health apps"
        )


class SelectAppCommand(CommandHandler):
    """Select an app by index or name."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "select"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Select an app by index or name"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "app_identifier",
            metavar="ID_OR_NAME",
            help="App index (1-based) or name/package"
        )
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        app_service = context.services.get("app_scan")
        if not app_service:
            return CommandResult(
                success=False,
                message="App scan service not available",
                exit_code=1
            )
        
        success, selected_app = app_service.select_app(args.app_identifier)
        
        if success:
            name = selected_app.get("app_name", "Unknown")
            package = selected_app.get("package_name", "Unknown")
            return CommandResult(
                success=True,
                message=f"Selected app: {name} ({package})"
            )
        else:
            return CommandResult(
                success=False,
                message=f"Failed to select app: {args.app_identifier}",
                exit_code=1
            )


class ShowSelectedAppCommand(CommandHandler):
    """Show the currently selected app."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "show-selected"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Show the currently selected app"
    
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
        config_service = context.services.get("config")
        if not config_service:
            return CommandResult(
                success=False,
                message="Config service not available",
                exit_code=1
            )
        
        import json
        
        last_selected = config_service.get_config_value("LAST_SELECTED_APP")
        app_package = config_service.get_config_value("APP_PACKAGE")
        app_activity = config_service.get_config_value("APP_ACTIVITY")
        
        # Handle case where LAST_SELECTED_APP might be stored as JSON string
        if last_selected and isinstance(last_selected, str):
            try:
                last_selected = json.loads(last_selected)
            except json.JSONDecodeError:
                last_selected = None
        
        if last_selected and isinstance(last_selected, dict):
            name = last_selected.get("app_name", "Unknown")
            package = last_selected.get("package_name", "Unknown")
            activity = last_selected.get("activity_name", "Unknown")
            
            print(f"\n=== Selected App ===")
            print(f"Name: {name}")
            print(f"Package: {package}")
            print(f"Activity: {activity}")
            print("====================")
            
            return CommandResult(
                success=True,
                message=f"Selected app: {name} ({package})"
            )
        elif app_package:
            print(f"\n=== Selected App ===")
            print(f"Package: {app_package}")
            print(f"Activity: {app_activity}")
            print("====================")
            
            return CommandResult(
                success=True,
                message=f"Selected app: {app_package}"
            )
        else:
            print("No app selected. Use 'apps select' to select an app.")
            return CommandResult(
                success=False,
                message="No app selected",
                exit_code=1
            )


class AppsCommandGroup(CommandGroup):
    """App management command group."""
    
    def __init__(self):
        """Initialize apps command group."""
        super().__init__("apps", "App management commands")
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            ScanAllAppsCommand(),
            ScanHealthAppsCommand(),
            ListAllAppsCommand(),
            ListHealthAppsCommand(),
            SelectAppCommand(),
            ShowSelectedAppCommand(),
        ]
