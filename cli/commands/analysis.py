#!/usr/bin/env python3
"""
Analysis command group for managing crawl analysis and reporting.
"""

import argparse
from typing import List

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext
from cli.constants.messages import (
    ANALYSIS_GROUP_DESC,
    CMD_LIST_ANALYSIS_TARGETS_DESC,
    ERR_ANALYSIS_TARGET_DISCOVERY_FAILED,
    INFO_NO_ANALYSIS_TARGETS_FOUND,
    HEADER_AVAILABLE_ANALYSIS_TARGETS,
    FOOTER_SECTION_SEPARATOR,
    LABEL_APP_PACKAGE,
    LABEL_DB_FILE,
    LABEL_SESSION_DIR,
    MSG_FOUND_ANALYSIS_TARGETS,
    CMD_LIST_RUNS_FOR_TARGET_DESC,
    ARG_HELP_TARGET_INDEX,
    ARG_HELP_TARGET_APP_PACKAGE,
    MSG_RUNS_LISTED_SUCCESS,
    ERR_FAILED_LIST_RUNS_FOR_TARGET,
    CMD_GENERATE_ANALYSIS_PDF_DESC,
    ARG_HELP_PDF_OUTPUT_NAME,
    MSG_PDF_GENERATION_SUCCESS,
    ERR_PDF_GENERATION_FAILED,
    CMD_PRINT_ANALYSIS_SUMMARY_DESC,
    MSG_ANALYSIS_SUMMARY_SUCCESS,
    ERR_ANALYSIS_SUMMARY_FAILED,
)


class ListAnalysisTargetsCommand(CommandHandler):
    """Handle list-analysis-targets command."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "list-analysis-targets"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return CMD_LIST_ANALYSIS_TARGETS_DESC
    
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
        from cli.services.analysis_service import AnalysisService
        
        service = AnalysisService(context)
        success, targets = service.list_analysis_targets()
        
        if not success:
            return CommandResult(
                success=False,
                message=ERR_ANALYSIS_TARGET_DISCOVERY_FAILED,
                exit_code=1
            )
        
        if not targets:
            print(INFO_NO_ANALYSIS_TARGETS_FOUND)
            return CommandResult(success=True, message=INFO_NO_ANALYSIS_TARGETS_FOUND)
        
        print(f"\n{HEADER_AVAILABLE_ANALYSIS_TARGETS}")
        for target in targets:
            print(f"{target['index']}. {LABEL_APP_PACKAGE} {target['app_package']}")
            print(f"   {LABEL_DB_FILE} {target['db_filename']}")
            print(f"   {LABEL_SESSION_DIR} {target['session_dir']}")
            print()
        print(FOOTER_SECTION_SEPARATOR)
        
        return CommandResult(
            success=True,
            message=MSG_FOUND_ANALYSIS_TARGETS.format(count=len(targets))
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
        return CMD_LIST_RUNS_FOR_TARGET_DESC
    
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
            help=ARG_HELP_TARGET_INDEX
        )
        target_group.add_argument(
            "--target-app-package",
            help=ARG_HELP_TARGET_APP_PACKAGE
        )
        
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        from cli.services.analysis_service import AnalysisService
        
        service = AnalysisService(context)
        
        # Determine if we're using index or package name
        is_index = args.target_index is not None
        identifier = str(args.target_index if is_index else args.target_app_package)
        
        success = service.list_runs_for_target(identifier, is_index)
        
        if success:
            return CommandResult(success=True, message=MSG_RUNS_LISTED_SUCCESS)
        else:
            return CommandResult(
                success=False,
                message=ERR_FAILED_LIST_RUNS_FOR_TARGET,
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
        return CMD_GENERATE_ANALYSIS_PDF_DESC
    
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
            help=ARG_HELP_TARGET_INDEX
        )
        pdf_target_group.add_argument(
            "--target-app-package",
            help=ARG_HELP_TARGET_APP_PACKAGE
        )
        parser.add_argument(
            "--pdf-output-name",
            help=ARG_HELP_PDF_OUTPUT_NAME
        )
        
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        from cli.services.analysis_service import AnalysisService
        
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
            return CommandResult(success=True, message=MSG_PDF_GENERATION_SUCCESS)
        else:
            return CommandResult(
                success=False,
                message=ERR_PDF_GENERATION_FAILED,
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
        return CMD_PRINT_ANALYSIS_SUMMARY_DESC
    
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
            help=ARG_HELP_TARGET_INDEX
        )
        summary_target_group.add_argument(
            "--target-app-package",
            help=ARG_HELP_TARGET_APP_PACKAGE
        )
        
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        from cli.services.analysis_service import AnalysisService
        
        service = AnalysisService(context)
        
        # Determine if we're using index or package name
        is_index = args.target_index is not None
        identifier = str(args.target_index if is_index else args.target_app_package)
        
        success = service.print_analysis_summary(identifier, is_index)
        
        if success:
            return CommandResult(success=True, message=MSG_ANALYSIS_SUMMARY_SUCCESS)
        else:
            return CommandResult(
                success=False,
                message=ERR_ANALYSIS_SUMMARY_FAILED,
                exit_code=1
            )


class AnalysisCommandGroup(CommandGroup):
    """Analysis command group."""
    
    def __init__(self):
        """Initialize Analysis command group."""
        super().__init__("analysis", ANALYSIS_GROUP_DESC)
    
    def get_commands(self) -> List[CommandHandler]:
        """Get commands in this group."""
        return [
            ListAnalysisTargetsCommand(),
            ListRunsForTargetCommand(),
            GenerateAnalysisPDFCommand(),
            PrintAnalysisSummaryCommand(),
        ]
