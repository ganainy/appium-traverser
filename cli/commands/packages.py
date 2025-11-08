"""
Commands for managing allowed external packages in CLI.
"""

import argparse
import logging
from typing import Optional

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext
from cli.constants import messages as MSG
from cli.constants import keys as KEYS


class ListPackagesCommand(CommandHandler):
    """Command to list allowed external packages."""
    
    @property
    def name(self) -> str:
        return MSG.LIST_PACKAGES_NAME

    @property
    def description(self) -> str:
        return MSG.LIST_PACKAGES_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )

        parser.add_argument(
            "-j", "--json",
            action="store_true",
            help=MSG.LIST_PACKAGES_JSON_HELP
        )

        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from cli.services.packages_service import PackagesService

        packages_service = PackagesService(context)
        packages = packages_service.list_packages()

        telemetry = context.services.get(KEYS.TELEMETRY_SERVICE)

        if args.json:
            telemetry.print_json({KEYS.JSON_KEY_PACKAGES: packages, KEYS.JSON_KEY_COUNT: len(packages)})
        else:
            telemetry.print_package_list(packages)

        return CommandResult(
            success=True,
            message=MSG.LIST_PACKAGES_RESULT.format(count=len(packages))
        )


class AddPackageCommand(CommandHandler):
    """Command to add a package to allowed external packages."""
    
    @property
    def name(self) -> str:
        return MSG.ADD_PACKAGE_NAME

    @property
    def description(self) -> str:
        return MSG.ADD_PACKAGE_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )

        parser.add_argument(
            "package_name",
            help=MSG.ADD_PACKAGE_ARG_HELP
        )

        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from cli.services.packages_service import PackagesService

        packages_service = PackagesService(context)
        telemetry = context.services.get(KEYS.TELEMETRY_SERVICE)

        if packages_service.add_package(args.package_name):
            telemetry.print_success(MSG.ADD_PACKAGE_SUCCESS.format(package_name=args.package_name))
            return CommandResult(success=True, message=MSG.ADD_PACKAGE_RESULT.format(package_name=args.package_name))
        else:
            telemetry.print_error(MSG.ADD_PACKAGE_FAIL.format(package_name=args.package_name))
            return CommandResult(success=False, message=MSG.ADD_PACKAGE_RESULT_FAIL.format(package_name=args.package_name))


class RemovePackageCommand(CommandHandler):
    """Command to remove a package from allowed external packages."""
    
    @property
    def name(self) -> str:
        return MSG.REMOVE_PACKAGE_NAME

    @property
    def description(self) -> str:
        return MSG.REMOVE_PACKAGE_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )

        parser.add_argument(
            "package_name",
            help=MSG.REMOVE_PACKAGE_ARG_HELP
        )

        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from cli.services.packages_service import PackagesService

        packages_service = PackagesService(context)
        telemetry = context.services.get(KEYS.TELEMETRY_SERVICE)

        if packages_service.remove_package(args.package_name):
            telemetry.print_success(MSG.REMOVE_PACKAGE_SUCCESS.format(package_name=args.package_name))
            return CommandResult(success=True, message=MSG.REMOVE_PACKAGE_RESULT.format(package_name=args.package_name))
        else:
            telemetry.print_error(MSG.REMOVE_PACKAGE_FAIL.format(package_name=args.package_name))
            return CommandResult(success=False, message=MSG.REMOVE_PACKAGE_RESULT_FAIL.format(package_name=args.package_name))


class ClearPackagesCommand(CommandHandler):
    """Command to clear all allowed external packages."""
    
    @property
    def name(self) -> str:
        return MSG.CLEAR_PACKAGES_NAME

    @property
    def description(self) -> str:
        return MSG.CLEAR_PACKAGES_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )

        parser.add_argument(
            "-y", "--yes",
            action="store_true",
            help=MSG.CLEAR_PACKAGES_YES_HELP
        )

        self.add_common_arguments(parser)
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from cli.services.packages_service import PackagesService

        telemetry = context.services.get(KEYS.TELEMETRY_SERVICE)
        
        if not args.yes:
            if not telemetry.confirm_action(MSG.CLEAR_PACKAGES_CONFIRM):
                return CommandResult(success=False, message=MSG.CLEAR_PACKAGES_RESULT_CANCEL)

        packages_service = PackagesService(context)

        if packages_service.clear_packages():
            telemetry.print_success(MSG.CLEAR_PACKAGES_SUCCESS)
            return CommandResult(success=True, message=MSG.CLEAR_PACKAGES_RESULT)
        else:
            telemetry.print_error(MSG.CLEAR_PACKAGES_FAIL)
            return CommandResult(success=False, message=MSG.CLEAR_PACKAGES_RESULT_FAIL)


class PackagesCommandGroup(CommandGroup):
    """Group of commands for managing allowed external packages."""
    
    def __init__(self):
        """Initialize packages command group."""
        super().__init__("packages", "Manage allowed external packages")  # Group name/desc not externalized for backward compat
    
    def get_commands(self) -> list:
        return [
            ListPackagesCommand(),
            AddPackageCommand(),
            RemovePackageCommand(),
            ClearPackagesCommand(),
        ]
