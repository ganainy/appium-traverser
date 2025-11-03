#!/usr/bin/env python3
"""
App management commands.
"""

import argparse
from abc import abstractmethod
from typing import List

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext
from cli.constants.keys import (
    SERVICE_APP_SCAN, SERVICE_CONFIG,
    CACHE_KEY_ALL, CACHE_KEY_HEALTH,
    JSON_KEY_ALL_APPS, JSON_KEY_HEALTH_APPS,
    APP_NAME, PACKAGE_NAME, ACTIVITY_NAME,
    CONFIG_LAST_SELECTED_APP, CONFIG_APP_PACKAGE, CONFIG_APP_ACTIVITY,
    CMD_SCAN_ALL, CMD_SCAN_HEALTH, CMD_LIST_ALL, CMD_LIST_HEALTH,
    CMD_SELECT, CMD_SHOW_SELECTED,
    ARG_FORCE_RESCAN, ARG_APP_IDENTIFIER, ARG_METAVAR_ID_OR_NAME,
    DEFAULT_UNKNOWN
)
from cli.constants.messages import (
    APPS_GROUP_DESC,
    CMD_SCAN_ALL_DESC, ARG_HELP_FORCE_RESCAN, MSG_SCAN_ALL_SUCCESS, ERR_SCAN_APPS_FAILED,
    CMD_SCAN_HEALTH_DESC, MSG_SCAN_HEALTH_SUCCESS,
    CMD_LIST_ALL_DESC, CMD_LIST_HEALTH_DESC,
    CMD_SELECT_DESC, ARG_HELP_APP_IDENTIFIER, MSG_SELECT_APP_SUCCESS, ERR_SELECT_APP_FAILED,
    CMD_SHOW_SELECTED_DESC, HEADER_SELECTED_APP, LABEL_NAME, LABEL_PACKAGE, LABEL_ACTIVITY,
    FOOTER_SELECTED_APP, MSG_NO_APP_SELECTED, ERR_APP_SCAN_SERVICE_NOT_AVAILABLE,
    ERR_CONFIG_SERVICE_NOT_AVAILABLE,
    MSG_NO_APPS_FOUND, HEADER_APPS_LIST, FORMAT_APP_LIST_ITEM, FOOTER_APPS_LIST,
    MSG_LISTED_APPS_SUCCESS,
    HEADER_ALL_APPS, HEADER_HEALTH_APPS
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
    def _json_key(self) -> str:
        """JSON key in the cache file ('all_apps' or 'health_apps')."""
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
            name = app.get(APP_NAME, DEFAULT_UNKNOWN)
            package = app.get(PACKAGE_NAME, DEFAULT_UNKNOWN)
            print(FORMAT_APP_LIST_ITEM.format(index=i+1, name=name, package=package))
        print(FOOTER_APPS_LIST.format(header_title=self._header_title))

        return CommandResult(
            success=True,
            message=MSG_LISTED_APPS_SUCCESS.format(count=len(apps), cache_key_type=self._cache_key_type)
        )


class ScanAllAppsCommand(CommandHandler):
    """Scan device and cache ALL installed apps with AI health filtering."""

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

        # Now scan_all_apps actually performs AI filtering too (merged approach)
        success, cache_path = app_service.scan_all_apps(force_rescan=args.force_rescan)

        if success:
            return CommandResult(
                success=True,
                message=MSG_SCAN_ALL_SUCCESS.format(cache_path=cache_path)
            )
        else:
            return CommandResult(
                success=False,
                message=ERR_SCAN_APPS_FAILED,
                exit_code=1
            )




class ScanHealthAppsCommand(CommandHandler):
    """Scan device and cache apps with AI health filtering (alias for scan-all)."""

    @property
    def name(self) -> str:
        """Get command name."""
        return CMD_SCAN_HEALTH

    @property
    def description(self) -> str:
        """Get command description."""
        return CMD_SCAN_HEALTH_DESC

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

        # Use the same scan method as scan-all (both perform AI filtering now)
        success, cache_path = app_service.scan_all_apps(force_rescan=args.force_rescan)

        if success:
            return CommandResult(
                success=True,
                message=MSG_SCAN_HEALTH_SUCCESS.format(cache_path=cache_path)
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
    def _json_key(self) -> str:
        """JSON key in the cache file."""
        return JSON_KEY_ALL_APPS
    
    @property
    def _header_title(self) -> str:
        """Header title for display."""
        return HEADER_ALL_APPS


class ListHealthAppsCommand(BaseListAppsCommand):
    """List health apps from the latest cache."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return CMD_LIST_HEALTH
    
    @property
    def description(self) -> str:
        """Get command description."""
        return CMD_LIST_HEALTH_DESC
    
    @property
    def _cache_key_type(self) -> str:
        """Cache key type."""
        return CACHE_KEY_HEALTH
    
    @property
    def _json_key(self) -> str:
        """JSON key in the cache file."""
        return JSON_KEY_HEALTH_APPS
    
    @property
    def _header_title(self) -> str:
        """Header title for display."""
        return HEADER_HEALTH_APPS


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
            # Get config service to save app details
            config_service = context.services.get(SERVICE_CONFIG)
            if config_service:
                pkg = selected_app.get(PACKAGE_NAME)
                act = selected_app.get(ACTIVITY_NAME)
                name = selected_app.get(APP_NAME, "Unknown")
                
                # Save to config
                config_service.set_config_value(CONFIG_APP_PACKAGE, pkg)
                config_service.set_config_value(CONFIG_APP_ACTIVITY, act)
                config_service.set_config_value(
                    CONFIG_LAST_SELECTED_APP,
                    {"package_name": pkg, "activity_name": act, "app_name": name},
                )
                config_service.save_all_changes()
            
            name = selected_app.get(APP_NAME, DEFAULT_UNKNOWN)
            package = selected_app.get(PACKAGE_NAME, DEFAULT_UNKNOWN)
            return CommandResult(
                success=True,
                message=MSG_SELECT_APP_SUCCESS.format(name=name, package=package)
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
        config_service = context.services.get(SERVICE_CONFIG)
        if not config_service:
            return CommandResult(
                success=False,
                message=ERR_CONFIG_SERVICE_NOT_AVAILABLE,
                exit_code=1
            )
        
        # Use the new method that handles JSON deserialization internally
        last_selected = config_service.get_deserialized_config_value(CONFIG_LAST_SELECTED_APP)
        app_package = config_service.get_config_value(CONFIG_APP_PACKAGE)
        app_activity = config_service.get_config_value(CONFIG_APP_ACTIVITY)
        
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
                message=MSG_SELECT_APP_SUCCESS.format(name=name, package=package)
            )
        elif app_package:
            print(f"\n{HEADER_SELECTED_APP}")
            print(f"{LABEL_PACKAGE} {app_package}")
            print(f"{LABEL_ACTIVITY} {app_activity}")
            print(FOOTER_SELECTED_APP)
            
            return CommandResult(
                success=True,
                message=MSG_SELECT_APP_SUCCESS.format(name=app_package, package=app_package)
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
            ScanAllAppsCommand(),
            ScanHealthAppsCommand(),
            ListAllAppsCommand(),
            ListHealthAppsCommand(),
            SelectAppCommand(),
            ShowSelectedAppCommand(),
        ]
