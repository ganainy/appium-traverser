#!/usr/bin/env python3
"""
Analysis command group for managing crawl analysis and reporting.
"""

import argparse
from typing import List

from traverser_ai_api.cli.commands.base import CommandGroup, CommandHandler, CommandResult
from traverser_ai_api.cli.shared.context import CLIContext


class ListAnalysisTargetsCommand(CommandHandler):
    """Handle list-analysis-targets command."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "list-analysis-targets"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "List available analysis targets"
    
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
        from traverser_ai_api.cli.services.analysis_service import AnalysisService
        
        service = AnalysisService(context)
        success, targets = service.list_analysis_targets()
        
        if not success:
            return CommandResult(
                success=False,
                message="Error: Could not discover analysis targets.",
                exit_code=1
            )
        
        if not targets:
            print("No analysis targets found.")
            return CommandResult(success=True, message="No analysis targets found")
        
        print("\n=== Available Analysis Targets ===")
        for target in targets:
            print(f"{target['index']}. App Package: {target['app_package']}")
            print(f"   DB File: {target['db_filename']}")
            print(f"   Session Dir: {target['session_dir']}")
            print()
        print("================================")
        
        return CommandResult(
            success=True,
            message=f"Found {len(targets)} analysis targets"
        )


class ListRunsForTargetCommand(CommandHandler):
    """Handle list-runs-for-target command."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "list-runs-for-target"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "List runs for a specific analysis target"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        
        target_group = parser.add_mutually_exclusive_group(required=True)
        target_group.add_argument(
            "--target-index",
            type=int,
            help="Target index from list-analysis-targets"
        )
        target_group.add_argument(
            "--target-app-package",
            help="Target app package name"
        )
        
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        from traverser_ai_api.cli.services.analysis_service import AnalysisService
        
        service = AnalysisService(context)
        
        # Determine if we're using index or package name
        is_index = args.target_index is not None
        identifier = str(args.target_index if is_index else args.target_app_package)
        
        success = service.list_runs_for_target(identifier, is_index)
        
        if success:
            return CommandResult(success=True, message="Runs listed successfully")
        else:
            return CommandResult(
                success=False,
                message="Failed to list runs for target",
                exit_code=1
            )


class GenerateAnalysisPDFCommand(CommandHandler):
    """Handle generate-analysis-pdf command."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "generate-analysis-pdf"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Generate PDF report for analysis target"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        
        pdf_target_group = parser.add_mutually_exclusive_group(required=True)
        pdf_target_group.add_argument(
            "--target-index",
            type=int,
            help="Target index from list-analysis-targets"
        )
        pdf_target_group.add_argument(
            "--target-app-package",
            help="Target app package name"
        )
        parser.add_argument(
            "--pdf-output-name",
            help="Custom PDF filename (optional)"
        )
        
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        from traverser_ai_api.cli.services.analysis_service import AnalysisService
        
        service = AnalysisService(context)
        
        # Determine if we're using index or package name
        is_index = args.target_index is not None
        identifier = str(args.target_index if is_index else args.target_app_package)
        
        success = service.generate_analysis_pdf(
            identifier,
            is_index,
            args.pdf_output_name
        )
        
        if success:
            return CommandResult(success=True, message="PDF generation completed successfully")
        else:
            return CommandResult(
                success=False,
                message="PDF generation failed",
                exit_code=1
            )


class PrintAnalysisSummaryCommand(CommandHandler):
    """Handle print-analysis-summary command."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "print-analysis-summary"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return "Print summary metrics for analysis target"
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        
        summary_target_group = parser.add_mutually_exclusive_group(required=True)
        summary_target_group.add_argument(
            "--target-index",
            type=int,
            help="Target index from list-analysis-targets"
        )
        summary_target_group.add_argument(
            "--target-app-package",
            help="Target app package name"
        )
        
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        from traverser_ai_api.cli.services.analysis_service import AnalysisService
        
        service = AnalysisService(context)
        
        # Determine if we're using index or package name
        is_index = args.target_index is not None
        identifier = str(args.target_index if is_index else args.target_app_package)
        
        success = service.print_analysis_summary(identifier, is_index)
        
        if success:
            return CommandResult(success=True, message="Analysis summary printed successfully")
        else:
            return CommandResult(
                success=False,
                message="Failed to print analysis summary",
                exit_code=1
            )


class AnalysisCommandGroup(CommandGroup):
    """Analysis command group."""
    
    def __init__(self):
        """Initialize Analysis command group."""
        super().__init__("analysis", "Analysis and reporting commands")
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            ListAnalysisTargetsCommand(),
            ListRunsForTargetCommand(),
            GenerateAnalysisPDFCommand(),
            PrintAnalysisSummaryCommand(),
        ]