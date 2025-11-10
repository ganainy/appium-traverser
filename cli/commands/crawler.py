#!/usr/bin/env python3
"""
Crawler control commands.
"""


import argparse
from typing import List

from cli.commands.base import CommandGroup, CommandHandler, CommandResult
from cli.shared.context import CLIContext
from cli.constants import messages as MSG
from cli.constants import keys as KEY


class StartCrawlerCommand(CommandHandler):
    """Start the crawler process."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return MSG.START_CMD_NAME

    @property
    def description(self) -> str:
        """Get command description."""
        return MSG.START_CMD_DESC
    
    def register(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the argument parser."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        self.add_common_arguments(parser)
        parser.add_argument(
            MSG.START_CMD_ANNOTATE_ARG,
            action="store_true",
            help=MSG.START_CMD_ANNOTATE_HELP
        )
        parser.add_argument(
            MSG.START_CMD_ENABLE_TRAFFIC_CAPTURE_ARG,
            action="store_true",
            help=MSG.START_CMD_ENABLE_TRAFFIC_CAPTURE_HELP
        )
        parser.add_argument(
            MSG.START_CMD_ENABLE_VIDEO_RECORDING_ARG,
            action="store_true",
            help=MSG.START_CMD_ENABLE_VIDEO_RECORDING_HELP
        )
        parser.add_argument(
            MSG.START_CMD_ENABLE_MOBSF_ANALYSIS_ARG,
            action="store_true",
            help=MSG.START_CMD_ENABLE_MOBSF_ANALYSIS_HELP
        )
        parser.set_defaults(handler=self)
        return parser
    
    def run(self, args: argparse.Namespace, context: CLIContext) -> CommandResult:
        """Execute the command."""
        crawler_service = context.services.get(KEY.CRAWLER_SERVICE)
        if not crawler_service:
            return CommandResult(
                success=False,
                message=MSG.SERVICE_NOT_AVAILABLE.format(service=KEY.CRAWLER_SERVICE.title()),
                exit_code=1
            )

        # Prepare feature flags from CLI arguments
        # Default behavior: all features are disabled unless explicitly enabled
        feature_flags = {}
        
        # Handle traffic capture flag (argparse converts --enable-traffic-capture to enable_traffic_capture)
        enable_tc = getattr(args, 'enable_traffic_capture', False)
        if enable_tc:
            feature_flags['ENABLE_TRAFFIC_CAPTURE'] = True
        else:
            # Default: disabled (overrides config if it's enabled)
            feature_flags['ENABLE_TRAFFIC_CAPTURE'] = False
        
        # Handle video recording flag
        enable_vr = getattr(args, 'enable_video_recording', False)
        if enable_vr:
            feature_flags['ENABLE_VIDEO_RECORDING'] = True
        else:
            # Default: disabled (overrides config if it's enabled)
            feature_flags['ENABLE_VIDEO_RECORDING'] = False
        
        # Handle MobSF analysis flag
        enable_mobsf = getattr(args, 'enable_mobsf_analysis', False)
        if enable_mobsf:
            # Check if MobSF API key is configured before starting crawler
            mobsf_api_key = context.config.get(KEY.CONFIG_MOBSF_API_KEY)
            if not mobsf_api_key:
                return CommandResult(
                    success=False,
                    message=MSG.START_MOBSF_API_KEY_MISSING,
                    exit_code=1
                )
            feature_flags['ENABLE_MOBSF_ANALYSIS'] = True
        else:
            # Default: disabled (overrides config if it's enabled)
            feature_flags['ENABLE_MOBSF_ANALYSIS'] = False

        success = crawler_service.start_crawler(
            annotate_after_run=args.annotate_offline_after_run,
            feature_flags=feature_flags
        )

        if success:
            result_msg = MSG.START_SUCCESS
            if args.annotate_offline_after_run:
                result_msg += MSG.START_ANNOTATE_WILL_RUN
            return CommandResult(success=True, message=result_msg)
        else:
            return CommandResult(
                success=False,
                message=MSG.START_FAIL,
                exit_code=1
            )


class StopCrawlerCommand(CommandHandler):
    """Stop the crawler process."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return MSG.STOP_CMD_NAME

    @property
    def description(self) -> str:
        """Get command description."""
        return MSG.STOP_CMD_DESC
    
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
        crawler_service = context.services.get(KEY.CRAWLER_SERVICE)
        if not crawler_service:
            return CommandResult(
                success=False,
                message=MSG.SERVICE_NOT_AVAILABLE.format(service=KEY.CRAWLER_SERVICE.title()),
                exit_code=1
            )

        success = crawler_service.stop_crawler()

        if success:
            return CommandResult(
                success=True,
                message=MSG.STOP_SUCCESS
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.STOP_FAIL,
                exit_code=1
            )


class PauseCrawlerCommand(CommandHandler):
    """Pause the crawler process."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return MSG.PAUSE_CMD_NAME

    @property
    def description(self) -> str:
        """Get command description."""
        return MSG.PAUSE_CMD_DESC
    
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
        crawler_service = context.services.get(KEY.CRAWLER_SERVICE)
        if not crawler_service:
            return CommandResult(
                success=False,
                message=MSG.SERVICE_NOT_AVAILABLE.format(service=KEY.CRAWLER_SERVICE.title()),
                exit_code=1
            )

        success = crawler_service.pause_crawler()

        if success:
            return CommandResult(
                success=True,
                message=MSG.PAUSE_SUCCESS
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.PAUSE_FAIL,
                exit_code=1
            )


class ResumeCrawlerCommand(CommandHandler):
    """Resume the crawler process."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return MSG.RESUME_CMD_NAME

    @property
    def description(self) -> str:
        """Get command description."""
        return MSG.RESUME_CMD_DESC
    
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
        crawler_service = context.services.get(KEY.CRAWLER_SERVICE)
        if not crawler_service:
            return CommandResult(
                success=False,
                message=MSG.SERVICE_NOT_AVAILABLE.format(service=KEY.CRAWLER_SERVICE.title()),
                exit_code=1
            )

        success = crawler_service.resume_crawler()

        if success:
            return CommandResult(
                success=True,
                message=MSG.RESUME_SUCCESS
            )
        else:
            return CommandResult(
                success=False,
                message=MSG.RESUME_FAIL,
                exit_code=1
            )


class StatusCrawlerCommand(CommandHandler):
    """Show crawler status."""
    
    @property
    def name(self) -> str:
        """Get command name."""
        return MSG.STATUS_CMD_NAME

    @property
    def description(self) -> str:
        """Get command description."""
        return MSG.STATUS_CMD_DESC
    
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
        crawler_service = context.services.get(KEY.CRAWLER_SERVICE)
        if not crawler_service:
            return CommandResult(
                success=False,
                message=MSG.SERVICE_NOT_AVAILABLE.format(service=KEY.CRAWLER_SERVICE.title()),
                exit_code=1
            )

        status = crawler_service.get_status()
        
        telemetry_service = context.services.get("telemetry")
        if telemetry_service:
            telemetry_service.print_crawler_status(status)
        else:
            # Fallback to basic printing if telemetry service is not available
            print(MSG.STATUS_HEADER)
            print(MSG.STATUS_PROCESS.format(process=status[KEY.PROCESS_KEY]))
            print(MSG.STATUS_STATE.format(state=status[KEY.STATE_KEY]))
            print(MSG.STATUS_TARGET_APP.format(target_app=status[KEY.TARGET_APP_KEY]))
            print(MSG.STATUS_OUTPUT_DIR.format(output_dir=status[KEY.OUTPUT_DIR_KEY]))
            print(MSG.STATUS_FOOTER)

        return CommandResult(
            success=True,
            message=MSG.STATUS_SUCCESS
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
