"""
Main entry point for the modular CLI.
"""

import argparse
import logging
import sys
from typing import List, Optional

from cli.commands.base import CommandRegistry
from cli.parser import build_parser
from cli.shared.context import CLIContext


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
        from cli.services.telemetry import TelemetryService
        context.services.register("telemetry", TelemetryService())

        # Register core services
        from cli.services.analysis_service import AnalysisService
        from cli.services.app_scan_service import AppScanService
        from cli.services.config_service import ConfigService
        from cli.services.crawler_service import CrawlerService
        from cli.services.device_service import DeviceService
        from cli.services.focus_area_service import FocusAreaService
        from cli.services.openrouter_service import OpenRouterService

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
        from cli.commands import (
            analysis,
            apps,
            config,
            crawler,
            device,
            focus,
            openrouter,
            services_check,
            switch_provider
        )

        logging.debug("Registering standalone commands...")
        # Register standalone commands
        registry.add_standalone_command(config.ShowConfigCommand())
        registry.add_standalone_command(config.SetConfigCommand())
        registry.add_standalone_command(services_check.PrecheckCommand())
        registry.add_standalone_command(switch_provider.SwitchProviderCommand())

        logging.debug("Registering command groups...")
        # Register command groups
        device_group = device.DeviceCommandGroup()
        apps_group = apps.AppsCommandGroup()
        crawler_group = crawler.CrawlerCommandGroup()
        focus_group = focus.FocusCommandGroup()
        openrouter_group = openrouter.OpenRouterCommandGroup()
        analysis_group = analysis.AnalysisCommandGroup()

        # Register groups instead of individual commands
        registry.add_group(device_group)
        registry.add_group(apps_group)
        registry.add_group(crawler_group)
        registry.add_group(focus_group)
        registry.add_group(openrouter_group)
        registry.add_group(analysis_group)

        logging.debug(f"Registered {len(registry.groups)} groups and {len(registry.standalone_commands)} standalone commands.")

    except ImportError as e:
        logging.error(f"Failed to import command modules: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(run())
