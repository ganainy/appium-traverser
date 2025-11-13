#!/usr/bin/env python3
"""
App management commands.
"""

import argparse
from abc import abstractmethod
from typing import List

try:
    from colorama import init, Fore, Style
    init(autoreset=True)  # Initialize colorama for cross-platform support
    COLORAMA_AVAILABLE = True
except ImportError:
    # Fallback if colorama is not available
    class Fore:
        GREEN = ''
        RESET = ''
    class Style:
        RESET_ALL = ''
    COLORAMA_AVAILABLE = False

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext
from cli.constants.keys import (
    SERVICE_APP_SCAN,
    CACHE_KEY_ALL, CACHE_KEY_HEALTH,
    APP_NAME, PACKAGE_NAME, ACTIVITY_NAME,
    CONFIG_LAST_SELECTED_APP, CONFIG_APP_PACKAGE, CONFIG_APP_ACTIVITY,
    CMD_SCAN_ALL, CMD_LIST_ALL,
    CMD_SELECT, CMD_SHOW_SELECTED,
    ARG_FORCE_RESCAN, ARG_APP_IDENTIFIER, ARG_METAVAR_ID_OR_NAME,
    DEFAULT_UNKNOWN, IS_HEALTH_APP
)
from cli.constants.messages import (
    APPS_GROUP_DESC,
    CMD_SCAN_ALL_DESC, ARG_HELP_FORCE_RESCAN, MSG_SCAN_ALL_SUCCESS, MSG_SCAN_ALL_SUCCESS_NO_AI, ERR_SCAN_APPS_FAILED,
    CMD_LIST_ALL_DESC,
    CMD_SELECT_DESC, ARG_HELP_APP_IDENTIFIER, MSG_SELECT_APP_SUCCESS, ERR_SELECT_APP_FAILED,
    CMD_SHOW_SELECTED_DESC, HEADER_SELECTED_APP, LABEL_NAME, LABEL_PACKAGE, LABEL_ACTIVITY,
    FOOTER_SELECTED_APP, MSG_NO_APP_SELECTED, ERR_APP_SCAN_SERVICE_NOT_AVAILABLE,
    MSG_NO_APPS_FOUND, MSG_AUTO_SCANNING, HEADER_APPS_LIST, FORMAT_APP_LIST_ITEM, FOOTER_APPS_LIST,
    MSG_LISTED_APPS_SUCCESS,
    HEADER_ALL_APPS, ERR_NO_APP_CACHE_FOUND
)


class BaseListAppsCommand(CommandHandler):
    """Base class for listing apps commands with shared logic."""
    
    @property
    @abstractmethod
    def _cache_key_type(self) -> str:
        """Cache key type ('all' or 'health')."""
        pass
    
    @property
    @abstractmethod
    def _header_title(self) -> str:
        """Header title for display ('All Apps' or 'Health Apps')."""
        pass
    
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
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        app_service = context.services.get(SERVICE_APP_SCAN)
        if not app_service:
            return CommandResult(
                success=False,
                message=ERR_APP_SCAN_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        # Use the appropriate service method based on cache key type
        if self._cache_key_type == CACHE_KEY_ALL:
            success, apps, error_message = app_service.get_all_cached_apps()
        else:  # health
            success, apps, error_message = app_service.get_health_cached_apps()
        
        # If no cache found, automatically trigger a scan
        if not success and error_message == ERR_NO_APP_CACHE_FOUND:
            print(MSG_AUTO_SCANNING)
            scan_success, cache_path = app_service.scan_apps(force_rescan=False)
            if not scan_success:
                return CommandResult(
                    success=False,
                    message=ERR_SCAN_APPS_FAILED,
                    exit_code=1
                )
            # Retry getting apps after scan
            if self._cache_key_type == CACHE_KEY_ALL:
                success, apps, error_message = app_service.get_all_cached_apps()
            else:  # health
                success, apps, error_message = app_service.get_health_cached_apps()
        
        if not success:
            print(error_message)
            return CommandResult(
                success=False,
                message=error_message,
                exit_code=1
            )

        if not apps:
            print(MSG_NO_APPS_FOUND.format(cache_key_type=self._cache_key_type))
            return CommandResult(success=True, message=MSG_NO_APPS_FOUND.format(cache_key_type=self._cache_key_type))

        print(HEADER_APPS_LIST.format(header_title=self._header_title, count=len(apps)))
        for i, app in enumerate(apps):
            # Handle null/None values from JSON - convert to default
            name = app.get(APP_NAME) or DEFAULT_UNKNOWN
            if name is None:
                name = DEFAULT_UNKNOWN
            package = app.get(PACKAGE_NAME, DEFAULT_UNKNOWN)
            is_health = app.get(IS_HEALTH_APP) is True
            
            # Color code health apps in green
            if is_health and COLORAMA_AVAILABLE:
                colored_name = f"{Fore.GREEN}{name}{Style.RESET_ALL}"
                colored_package = f"{Fore.GREEN}{package}{Style.RESET_ALL}"
                formatted_item = FORMAT_APP_LIST_ITEM.format(index=i+1, name=colored_name, package=colored_package)
            else:
                formatted_item = FORMAT_APP_LIST_ITEM.format(index=i+1, name=name, package=package)
            
            print(formatted_item)
        print(FOOTER_APPS_LIST.format(header_title=self._header_title))

        return CommandResult(
            success=True,
            message=MSG_LISTED_APPS_SUCCESS.format(count=len(apps), cache_key_type=self._cache_key_type)
        )


class ScanAppsCommand(CommandHandler):
    """Scan device and cache all installed apps with AI health filtering."""

    @property
    def name(self) -> str:
        """Get command name."""
        return CMD_SCAN_ALL

    @property
    def description(self) -> str:
        """Get command description."""
        return CMD_SCAN_ALL_DESC

    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            ARG_FORCE_RESCAN,
            action="store_true",
            help=ARG_HELP_FORCE_RESCAN
        )
        parser.set_defaults(handler=self)
        return parser

    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        app_service = context.services.get(SERVICE_APP_SCAN)
        if not app_service:
            return CommandResult(
                success=False,
                message=ERR_APP_SCAN_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )

        # Unified scan with AI filtering always enabled
        success, result = app_service.scan_apps(force_rescan=args.force_rescan)

        if success:
            cache_path, ai_filtered = result
            if ai_filtered:
                message = MSG_SCAN_ALL_SUCCESS.format(cache_path=cache_path)
            else:
                message = MSG_SCAN_ALL_SUCCESS_NO_AI.format(cache_path=cache_path)
            
            return CommandResult(
                success=True,
                message=message
            )
        else:
            return CommandResult(
                success=False,
                message=ERR_SCAN_APPS_FAILED,
                exit_code=1
            )


class ListAllAppsCommand(BaseListAppsCommand):
    """List ALL apps from the latest merged cache."""

    @property
    def name(self) -> str:
        """Get command name."""
        return CMD_LIST_ALL

    @property
    def description(self) -> str:
        """Get command description."""
        return CMD_LIST_ALL_DESC
    
    @property
    def _cache_key_type(self) -> str:
        """Cache key type."""
        return CACHE_KEY_ALL
    
    @property
    def _header_title(self) -> str:
        """Header title for display."""
        return HEADER_ALL_APPS


class SelectAppCommand(CommandHandler):
    """Select an app by index or name."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return CMD_SELECT
    
    @property
    def description(self) -> str:
        """Get command description."""
        return CMD_SELECT_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            ARG_APP_IDENTIFIER,
            metavar=ARG_METAVAR_ID_OR_NAME,
            help=ARG_HELP_APP_IDENTIFIER
        )
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        app_service = context.services.get(SERVICE_APP_SCAN)
        if not app_service:
            return CommandResult(
                success=False,
                message=ERR_APP_SCAN_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        success, selected_app = app_service.select_app(getattr(args, ARG_APP_IDENTIFIER))
        
        if success:
            # Save app details directly to config
            pkg = selected_app.get(PACKAGE_NAME)
            act = selected_app.get(ACTIVITY_NAME)
            name = selected_app.get(APP_NAME, "Unknown")
            
            # Save to config
            context.config.set(CONFIG_APP_PACKAGE, pkg)
            context.config.set(CONFIG_APP_ACTIVITY, act)
            context.config.set(
                CONFIG_LAST_SELECTED_APP,
                {"package_name": pkg, "activity_name": act, "app_name": name},
            )
            
            name = selected_app.get(APP_NAME, DEFAULT_UNKNOWN)
            package = selected_app.get(PACKAGE_NAME, DEFAULT_UNKNOWN)
            return CommandResult(
                success=True,
                message=""
            )
        else:
            return CommandResult(
                success=False,
                message=ERR_SELECT_APP_FAILED.format(app_identifier=getattr(args, ARG_APP_IDENTIFIER)),
                exit_code=1
            )


class ShowSelectedAppCommand(CommandHandler):
    """Show the currently selected app."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return CMD_SHOW_SELECTED
    
    @property
    def description(self) -> str:
        """Get command description."""
        return CMD_SHOW_SELECTED_DESC
    
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
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        # Get configuration values directly from config
        last_selected = context.config.get_deserialized_config_value(CONFIG_LAST_SELECTED_APP)
        app_package = context.config.get(CONFIG_APP_PACKAGE)
        app_activity = context.config.get(CONFIG_APP_ACTIVITY)
        
        if last_selected and isinstance(last_selected, dict):
            name = last_selected.get(APP_NAME, DEFAULT_UNKNOWN)
            package = last_selected.get(PACKAGE_NAME, DEFAULT_UNKNOWN)
            activity = last_selected.get(ACTIVITY_NAME, DEFAULT_UNKNOWN)
            
            print(f"\n{HEADER_SELECTED_APP}")
            print(f"{LABEL_NAME} {name}")
            print(f"{LABEL_PACKAGE} {package}")
            print(f"{LABEL_ACTIVITY} {activity}")
            print(FOOTER_SELECTED_APP)
            
            return CommandResult(
                success=True,
                message=""
            )
        elif app_package:
            print(f"\n{HEADER_SELECTED_APP}")
            print(f"{LABEL_PACKAGE} {app_package}")
            print(f"{LABEL_ACTIVITY} {app_activity}")
            print(FOOTER_SELECTED_APP)
            
            return CommandResult(
                success=True,
                message=""
            )
        else:
            print(MSG_NO_APP_SELECTED)
            return CommandResult(
                success=False,
                message="No app selected",
                exit_code=1
            )


class AppsCommandGroup(CommandGroup):
    """App management command group."""
    
    def __init__(self):
        """Initialize apps command group."""
        super().__init__("apps", APPS_GROUP_DESC)
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            ScanAppsCommand(),
            ListAllAppsCommand(),
            SelectAppCommand(),
            ShowSelectedAppCommand(),
        ]
