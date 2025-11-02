"""
Commands for managing allowed external packages in CLI.
"""

import argparse
import logging
from typing import Optional

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext


class ListPackagesCommand(CommandHandler):
    """Command to list allowed external packages."""
    
    @property
    def name(self) -> str:
        return "list-packages"
    
    @property
    def description(self) -> str:
        return "List all allowed external packages"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        
        parser.add_argument(
            "-j", "--json",
            action="store_true",
            help="Output as JSON"
        )
        
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from cli.services.packages_service import PackagesService
        
        packages_service = PackagesService(context)
        packages = packages_service.list_packages()
        
        telemetry = context.services.get("telemetry")
        
        if args.json:
            import json
            telemetry.print_json({"packages": packages, "count": len(packages)})
        else:
            if not packages:
                telemetry.print_info("No allowed external packages configured.")
            else:
                telemetry.print_info(f"Allowed external packages ({len(packages)}):")
                for i, pkg in enumerate(packages, 1):
                    telemetry.print_info(f"  {i}. {pkg}")
        
        return CommandResult(
            success=True,
            message=f"Listed {len(packages)} allowed packages"
        )


class AddPackageCommand(CommandHandler):
    """Command to add a package to allowed external packages."""
    
    @property
    def name(self) -> str:
        return "add-package"
    
    @property
    def description(self) -> str:
        return "Add a package to allowed external packages"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        
        parser.add_argument(
            "package_name",
            help="Package name to add (e.g., com.example.app)"
        )
        
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from cli.services.packages_service import PackagesService
        
        packages_service = PackagesService(context)
        telemetry = context.services.get("telemetry")
        
        if packages_service.add_package(args.package_name):
            telemetry.print_success(f"Added package: {args.package_name}")
            return CommandResult(success=True, message=f"Package added: {args.package_name}")
        else:
            telemetry.print_error(f"Failed to add package: {args.package_name}")
            return CommandResult(success=False, message=f"Failed to add package: {args.package_name}")


class RemovePackageCommand(CommandHandler):
    """Command to remove a package from allowed external packages."""
    
    @property
    def name(self) -> str:
        return "remove-package"
    
    @property
    def description(self) -> str:
        return "Remove a package from allowed external packages"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        
        parser.add_argument(
            "package_name",
            help="Package name to remove"
        )
        
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from cli.services.packages_service import PackagesService
        
        packages_service = PackagesService(context)
        telemetry = context.services.get("telemetry")
        
        if packages_service.remove_package(args.package_name):
            telemetry.print_success(f"Removed package: {args.package_name}")
            return CommandResult(success=True, message=f"Package removed: {args.package_name}")
        else:
            telemetry.print_error(f"Failed to remove package: {args.package_name}")
            return CommandResult(success=False, message=f"Failed to remove package: {args.package_name}")


class ClearPackagesCommand(CommandHandler):
    """Command to clear all allowed external packages."""
    
    @property
    def name(self) -> str:
        return "clear-packages"
    
    @property
    def description(self) -> str:
        return "Clear all allowed external packages"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        
        parser.add_argument(
            "-y", "--yes",
            action="store_true",
            help="Skip confirmation prompt"
        )
        
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from cli.services.packages_service import PackagesService
        
        telemetry = context.services.get("telemetry")
        
        if not args.yes:
            telemetry.print_warning("This will clear all allowed external packages.")
            response = input("Are you sure? (yes/no): ").strip().lower()
            if response not in ("yes", "y"):
                telemetry.print_info("Cancelled.")
                return CommandResult(success=False, message="Operation cancelled")
        
        packages_service = PackagesService(context)
        
        if packages_service.clear_packages():
            telemetry.print_success("Cleared all allowed packages")
            return CommandResult(success=True, message="All packages cleared")
        else:
            telemetry.print_error("Failed to clear packages")
            return CommandResult(success=False, message="Failed to clear packages")


class UpdatePackageCommand(CommandHandler):
    """Command to update (rename) a package in allowed external packages."""
    
    @property
    def name(self) -> str:
        return "update-package"
    
    @property
    def description(self) -> str:
        return "Update (rename) an allowed external package"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        
        parser.add_argument(
            "old_name",
            help="Current package name"
        )
        
        parser.add_argument(
            "new_name",
            help="New package name"
        )
        
        self.add_common_arguments(parser)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        from cli.services.packages_service import PackagesService
        
        packages_service = PackagesService(context)
        telemetry = context.services.get("telemetry")
        
        if packages_service.update_package(args.old_name, args.new_name):
            telemetry.print_success(f"Updated package: {args.old_name} -> {args.new_name}")
            return CommandResult(
                success=True,
                message=f"Package updated: {args.old_name} -> {args.new_name}"
            )
        else:
            telemetry.print_error(f"Failed to update package: {args.old_name}")
            return CommandResult(
                success=False,
                message=f"Failed to update package: {args.old_name}"
            )


class PackagesCommandGroup(CommandGroup):
    """Group of commands for managing allowed external packages."""
    
    def __init__(self):
        """Initialize packages command group."""
        super().__init__("packages", "Manage allowed external packages")
    
    @property
    def name(self) -> str:
        return "packages"
    
    @property
    def description(self) -> str:
        return "Manage allowed external packages"
    
    def get_commands(self) -> list:
        return [
            ListPackagesCommand(),
            AddPackageCommand(),
            RemovePackageCommand(),
            UpdatePackageCommand(),
            ClearPackagesCommand(),
        ]
