"""
Base command infrastructure for CLI operations.
"""

import argparse
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from traverser_ai_api.cli.shared.context import CLIContext


class CommandResult:
    """Result of a command execution."""
    
    def __init__(self, success: bool = True, message: str = "", data: Any = None, exit_code: int = 0):
        """
        Initialize command result.
        
        Args:
            success: Whether the command succeeded
            message: Result message
            data: Additional data returned by command
            exit_code: Exit code for the command
        """
        self.success = success
        self.message = message
        self.data = data
        self.exit_code = exit_code
    
    def __bool__(self) -> bool:
        """Boolean representation of success."""
        return self.success


class CommandHandler(ABC):
    """
    Base class for CLI command handlers.
    
    All command handlers should inherit from this class and implement
    the required methods.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the command name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get the command description."""
        pass
    
    @abstractmethod
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """
        Register the command with the argument parser.
        
        Args:
            subparsers: Subparsers action to register with
            
        Returns:
            The created argument parser for this command
        """
        pass
    
    @abstractmethod
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """
        Execute the command.
        
        Args:
            args: Parsed command arguments
            context: CLI context
            
        Returns:
            Command result
        """
        pass
    
    def add_common_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Add common arguments to the command parser.
        
        Args:
            parser: Argument parser to add arguments to
        """
        parser.add_argument(
            "-v", "--verbose",
            action="store_true",
            help="Enable verbose output for this command"
        )


class CommandGroup:
    """
    Group of related commands.
    
    Used to organize commands into logical groups like "apps", "device", etc.
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize command group.
        
        Args:
            name: Group name
            description: Group description
        """
        self.name = name
        self.description = description
        self.commands: Dict[str, CommandHandler] = {}
    
    def add_command(self, command: CommandHandler) -> None:
        """
        Add a command to this group.
        
        Args:
            command: Command handler to add
        """
        self.commands[command.name] = command
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """
        Register the command group and all its commands.
        
        Args:
            subparsers: Subparsers action to register with
            
        Returns:
            The group parser
        """
        # If the group hasn't explicitly added commands, but implements get_commands(),
        # populate the internal registry before creating subparsers. This keeps backward
        # compatibility with groups that simply expose a list of commands via get_commands().
        if not self.commands and hasattr(self, "get_commands"):
            try:
                for cmd in getattr(self, "get_commands")():
                    self.add_command(cmd)
            except Exception:
                # Fallback silently; group will just have no commands
                pass

        group_parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        
        group_subparsers = group_parser.add_subparsers(
            dest=f"{self.name}_command",
            help=f"Available {self.name} commands"
        )
        
        for command in self.commands.values():
            command.register(group_subparsers)
        
        return group_parser
    
    def get_command(self, name: str) -> Optional[CommandHandler]:
        """
        Get a command by name.
        
        Args:
            name: Command name
            
        Returns:
            Command handler or None if not found
        """
        return self.commands.get(name)


class CommandRegistry:
    """
    Registry for managing all commands and command groups.
    """
    
    def __init__(self):
        """Initialize command registry."""
        self.groups: Dict[str, CommandGroup] = {}
        self.standalone_commands: Dict[str, CommandHandler] = {}
    
    def add_group(self, group: CommandGroup) -> None:
        """
        Add a command group.
        
        Args:
            group: Command group to add
        """
        self.groups[group.name] = group
    
    def add_standalone_command(self, command: CommandHandler) -> None:
        """
        Add a standalone command (not in a group).
        
        Args:
            command: Command handler to add
        """
        self.standalone_commands[command.name] = command
    
    def register_all(self, parser: argparse.ArgumentParser) -> None:
        """
        Register all commands and groups with the parser.
        
        Args:
            parser: Main argument parser
        """
        subparsers = parser.add_subparsers(
            dest="command",
            help="Available commands"
        )
        
        # Register standalone commands
        for command in self.standalone_commands.values():
            command.register(subparsers)
        
        # Register command groups
        for group in self.groups.values():
            group.register(subparsers)
    
    def get_command_handler(self, args: argparse.Namespace) -> Optional[CommandHandler]:
        """
        Get the appropriate command handler for parsed arguments.
        
        Args:
            args: Parsed arguments
            
        Returns:
            Command handler or None if not found
        """
        # Check for group commands first
        for group in self.groups.values():
            group_command_attr = f"{group.name}_command"
            if hasattr(args, group_command_attr):
                command_name = getattr(args, group_command_attr)
                if command_name:
                    return group.get_command(command_name)
        
        # Check for standalone commands
        if hasattr(args, "command") and args.command:
            return self.standalone_commands.get(args.command)
        
        return None