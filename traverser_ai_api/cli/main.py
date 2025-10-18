"""
Main entry point for the modular CLI.
"""

import argparse
import logging
import sys
from typing import List, Optional

from .commands.base import CommandRegistry
from .parser import build_parser
from .shared.context import CLIContext


def run(args: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point.
    
    Args:
        args: Command line arguments (defaults to sys.argv[1:])
        
    Returns:
        Exit code
    """
    try:
        # Build argument parser
        parser = build_parser()

        # Set up and register all commands BEFORE parsing args so --help shows them
        registry = CommandRegistry()
        _register_commands(registry)
        registry.register_all(parser)

        # Parse arguments (help will now include all subcommands)
        parsed_args = parser.parse_args(args)

        # Initialize CLI context (after parsing to get verbose flag)
        context = CLIContext(verbose=getattr(parsed_args, 'verbose', False))

        # Register telemetry service
        from .services.telemetry import TelemetryService
        context.services.register("telemetry", TelemetryService())

        # Register core services
        from .services.config_service import ConfigService
        from .services.device_service import DeviceService
        from .services.app_scan_service import AppScanService
        from .services.crawler_service import CrawlerService
        from .services.analysis_service import AnalysisService
        from .services.focus_area_service import FocusAreaService
        from .services.openrouter_service import OpenRouterService

        context.services.register("config", ConfigService(context))
        context.services.register("device", DeviceService(context))
        context.services.register("app_scan", AppScanService(context))
        context.services.register("crawler", CrawlerService(context))
        context.services.register("analysis", AnalysisService(context))
        context.services.register("focus", FocusAreaService(context))
        context.services.register("openrouter", OpenRouterService(context))

        # Execute command
        handler = registry.get_command_handler(parsed_args)
        if handler:
            result = handler.run(parsed_args, context)
            if result.message:
                if result.success:
                    print(result.message)
                else:
                    logging.error(result.message)
            return result.exit_code
        else:
            parser.print_help()
            return 1
            
    except KeyboardInterrupt:
        logging.debug("CLI operation interrupted by user.")
        return 130
    except Exception as e:
        logging.critical(f"Unexpected CLI error: {e}", exc_info=True)
        return 1


def _register_commands(registry: CommandRegistry) -> None:
    """
    Register all command modules.
    
    Args:
        registry: Command registry to register with
    """
    # Import command modules (lazy loading to avoid circular imports)
    try:
        from .commands import config
        from .commands import services_check
        from .commands import device
        from .commands import apps
        from .commands import crawler
        from .commands import focus
        
        logging.debug("Registering standalone commands...")
        # Register standalone commands
        registry.add_standalone_command(config.ShowConfigCommand())
        registry.add_standalone_command(config.SetConfigCommand())
        registry.add_standalone_command(services_check.PrecheckCommand())
        
        logging.debug("Registering command groups...")
        # Register command groups
        device_group = device.DeviceCommandGroup()
        apps_group = apps.AppsCommandGroup()
        crawler_group = crawler.CrawlerCommandGroup()
        focus_group = focus.FocusCommandGroup()
        
        # Register groups instead of individual commands
        registry.add_group(device_group)
        registry.add_group(apps_group)
        registry.add_group(crawler_group)
        registry.add_group(focus_group)
        
        logging.debug(f"Registered {len(registry.groups)} groups and {len(registry.standalone_commands)} standalone commands.")
        
        # TODO: Register remaining command groups as they are implemented
        # analysis_group = analysis.AnalysisCommandGroup()
        # openrouter_group = openrouter.OpenRouterCommandGroup()
        
    except ImportError as e:
        logging.error(f"Failed to import command modules: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(run())