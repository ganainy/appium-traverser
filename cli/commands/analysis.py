#!/usr/bin/env python3
"""
Analysis command group for managing crawl analysis and reporting.
"""

import argparse
from typing import List

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import ApplicationContext
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
    CMD_GENERATE_PDF_DESC,
    CMD_GENERATE_PDF_ARG_SESSION_DIR,
    CMD_GENERATE_PDF_ARG_SESSION_DIR_HELP,
    MSG_GENERATE_PDF_SUCCESS,
    ERR_GENERATE_PDF_FAILED,
    ERR_GENERATE_PDF_NO_SESSION,
    ERR_GENERATE_PDF_SESSION_NOT_FOUND,
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
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
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
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the command."""
        from cli.services.analysis_service import AnalysisService
        
        service = AnalysisService(context)
        
        # Get the target using the appropriate method
        if args.target_index is not None:
            target = service.get_target_by_index(args.target_index)
        else:
            target = service.get_target_by_package(args.target_app_package)
        
        if not target:
            return CommandResult(
                success=False,
                message=ERR_FAILED_LIST_RUNS_FOR_TARGET,
                exit_code=1
            )
        
        success, result_data = service.list_runs_for_target(target)
        
        if success:
            # Print the runs information
            print(f"\nTarget: {result_data['target_info']['app_package']} (Index: {result_data['target_info']['index']})")
            print(f"Database: {result_data['target_info']['db_filename']}")
            
            if result_data.get('message'):
                print(f"\n{result_data['message']}")
            
            if result_data['runs']:
                print("\nAvailable runs:")
                for run in result_data['runs']:
                    print(f"  Run ID: {run.get('run_id', 'N/A')}")
                    print(f"  Start Time: {run.get('start_time', 'N/A')}")
                    print(f"  End Time: {run.get('end_time', 'N/A')}")
                    print(f"  Status: {run.get('status', 'N/A')}")
                    print()
            else:
                print("No runs found for this target.")
            
            return CommandResult(success=True, message=MSG_RUNS_LISTED_SUCCESS)
        else:
            return CommandResult(
                success=False,
                message=result_data.get('error', ERR_FAILED_LIST_RUNS_FOR_TARGET),
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
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the command."""
        from cli.services.analysis_service import AnalysisService
        
        service = AnalysisService(context)
        
        # Get the target using the appropriate method
        if args.target_index is not None:
            target = service.get_target_by_index(args.target_index)
        else:
            target = service.get_target_by_package(args.target_app_package)
        
        if not target:
            return CommandResult(
                success=False,
                message=ERR_PDF_GENERATION_FAILED,
                exit_code=1
            )
        
        success, result_data = service.generate_analysis_pdf(
            target,
            args.pdf_output_name
        )
        
        if success:
            pdf_path = result_data.get('pdf_path', 'Unknown location')
            return CommandResult(
                success=True,
                message=f"{MSG_PDF_GENERATION_SUCCESS} PDF saved to: {pdf_path}"
            )
        else:
            return CommandResult(
                success=False,
                message=result_data.get('error', ERR_PDF_GENERATION_FAILED),
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
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the command."""
        from cli.services.analysis_service import AnalysisService
        
        service = AnalysisService(context)
        
        # Get the target using the appropriate method
        if args.target_index is not None:
            target = service.get_target_by_index(args.target_index)
        else:
            target = service.get_target_by_package(args.target_app_package)
        
        if not target:
            return CommandResult(
                success=False,
                message=ERR_ANALYSIS_SUMMARY_FAILED,
                exit_code=1
            )
        
        success, result_data = service.get_analysis_summary(target)
        
        if success:
            # Print the analysis summary
            run_info = result_data.get('run_info', {})
            metrics = result_data.get('metrics', {})
            
            print(f"\nAnalysis Summary for: {target['app_package']} (Index: {target['index']})")
            print(f"Database: {target['db_filename']}")
            
            if run_info:
                print("\nRun Information:")
                for key, value in run_info.items():
                    print(f"  {key}: {value}")
            
            if metrics:
                print("\nMetrics:")
                for key, value in metrics.items():
                    print(f"  {key}: {value}")
            
            return CommandResult(success=True, message=MSG_ANALYSIS_SUMMARY_SUCCESS)
        else:
            return CommandResult(
                success=False,
                message=result_data.get('error', ERR_ANALYSIS_SUMMARY_FAILED),
                exit_code=1
            )


class GeneratePDFCommand(CommandHandler):
    """Handle generate-pdf command."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return "generate-pdf"
    
    @property
    def description(self) -> str:
        """Get command description."""
        return CMD_GENERATE_PDF_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            CMD_GENERATE_PDF_ARG_SESSION_DIR,
            type=str,
            default=None,
            help=CMD_GENERATE_PDF_ARG_SESSION_DIR_HELP
        )
        parser.add_argument(
            "--pdf-output-name",
            help=ARG_HELP_PDF_OUTPUT_NAME
        )
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: ApplicationContext) -> CommandResult:
        """Execute the command."""
        from cli.services.analysis_service import AnalysisService
        from pathlib import Path
        from utils.paths import SessionPathManager
        
        service = AnalysisService(context)
        
        # Get session directory and parse to get target info
        if args.session_dir:
            session_dir = args.session_dir
            session_path = Path(session_dir)
            if not session_path.exists():
                return CommandResult(
                    success=False,
                    message=ERR_GENERATE_PDF_SESSION_NOT_FOUND.format(session_dir=session_dir),
                    exit_code=1
                )
            target_info = SessionPathManager.parse_session_dir(session_path, context.config)
        else:
            # Use latest session
            session_info = service.find_latest_session_dir()
            if not session_info:
                return CommandResult(
                    success=False,
                    message=ERR_GENERATE_PDF_NO_SESSION,
                    exit_code=1
                )
            session_dir, _ = session_info
            target_info = SessionPathManager.parse_session_dir(Path(session_dir), context.config)
        
        if not target_info:
            return CommandResult(
                success=False,
                message=ERR_GENERATE_PDF_FAILED,
                exit_code=1
            )
        
        # Generate PDF
        success, result_data = service.generate_analysis_pdf(
            target_info,
            getattr(args, 'pdf_output_name', None)
        )
        
        if success:
            pdf_path = result_data.get('pdf_path', 'Unknown location')
            return CommandResult(
                success=True,
                message=f"{MSG_GENERATE_PDF_SUCCESS} PDF saved to: {pdf_path}"
            )
        else:
            return CommandResult(
                success=False,
                message=result_data.get('error', ERR_GENERATE_PDF_FAILED),
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
            GeneratePDFCommand(),
        ]
