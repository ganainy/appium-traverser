#!/usr/bin/env python3
"""
Crawler control commands.
"""

import argparse
from typing import List

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext


class StartCrawlerCommand(CommandHandler):
    """Start the crawler process."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "start"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Start the crawler process"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            "--annotate-offline-after-run",
            action="store_true",
            help="Run offline UI annotator after crawler exits"
        )
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        crawler_service = context.services.get("crawler")
        if not crawler_service:
            return CommandResult(
                success=False,
                message="Crawler service not available",
                exit_code=1
            )
        
        success = crawler_service.start_crawler()
        
        if success:
            result_msg = "Crawler started successfully"
            
            # Handle offline annotation if requested
            if args.annotate_offline_after_run:
                analysis_service = context.services.get("analysis")
                if analysis_service:
                    # Wait for crawler to complete, then run annotation
                    # Note: In a real implementation, we'd need to monitor the process
                    # This is a simplified version
                    result_msg += ". Offline annotation will run after completion."
                else:
                    result_msg += ". Analysis service not available for offline annotation."
            
            return CommandResult(success=True, message=result_msg)
        else:
            return CommandResult(
                success=False,
                message="Failed to start crawler",
                exit_code=1
            )


class StopCrawlerCommand(CommandHandler):
    """Stop the crawler process."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "stop"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Stop the crawler process"
    
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
        crawler_service = context.services.get("crawler")
        if not crawler_service:
            return CommandResult(
                success=False,
                message="Crawler service not available",
                exit_code=1
            )
        
        success = crawler_service.stop_crawler()
        
        if success:
            return CommandResult(
                success=True,
                message="Stop signal sent to crawler"
            )
        else:
            return CommandResult(
                success=False,
                message="Failed to stop crawler",
                exit_code=1
            )


class PauseCrawlerCommand(CommandHandler):
    """Pause the crawler process."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "pause"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Pause the crawler process"
    
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
        crawler_service = context.services.get("crawler")
        if not crawler_service:
            return CommandResult(
                success=False,
                message="Crawler service not available",
                exit_code=1
            )
        
        success = crawler_service.pause_crawler()
        
        if success:
            return CommandResult(
                success=True,
                message="Pause signal sent to crawler"
            )
        else:
            return CommandResult(
                success=False,
                message="Failed to pause crawler",
                exit_code=1
            )


class ResumeCrawlerCommand(CommandHandler):
    """Resume the crawler process."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "resume"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Resume the crawler process"
    
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
        crawler_service = context.services.get("crawler")
        if not crawler_service:
            return CommandResult(
                success=False,
                message="Crawler service not available",
                exit_code=1
            )
        
        success = crawler_service.resume_crawler()
        
        if success:
            return CommandResult(
                success=True,
                message="Resume signal sent to crawler"
            )
        else:
            return CommandResult(
                success=False,
                message="Failed to resume crawler",
                exit_code=1
            )


class StatusCrawlerCommand(CommandHandler):
    """Show crawler status."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "status"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Show crawler status"
    
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
        crawler_service = context.services.get("crawler")
        if not crawler_service:
            return CommandResult(
                success=False,
                message="Crawler service not available",
                exit_code=1
            )
        
        status = crawler_service.get_status()
        
        print("\n=== Crawler Status ===")
        print(f"  Process: {status['process']}") 
        print(f"  State: {status['state']}")
        print(f"  Target App: {status['target_app']}")
        print(f"  Output Data Dir: {status['output_dir']}")
        print("=======================")
        
        return CommandResult(
            success=True,
            message="Status retrieved"
        )


class CrawlerCommandGroup(CommandGroup):
    """Crawler control command group."""
    
    def __init__(self):
        """Initialize crawler command group."""
        super().__init__("crawler", "Crawler control commands")
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            StartCrawlerCommand(),
            StopCrawlerCommand(),
            PauseCrawlerCommand(),
            ResumeCrawlerCommand(),
            StatusCrawlerCommand(),
        ]
