"""
Shared signal handling utilities for CLI operations.

This module provides signal handlers that can be used across the application
to handle SIGINT (Ctrl+C) and SIGTERM signals gracefully.
"""

import logging
import signal
import sys
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.controller import CrawlerOrchestrator

logger = logging.getLogger(__name__)


def setup_cli_signal_handler(
    orchestrator: Optional["CrawlerOrchestrator"] = None,
    crawler_service: Optional[Any] = None
) -> None:
    """
    Setup signal handlers for graceful CLI shutdown.
    
    This function registers handlers for SIGINT (Ctrl+C) and SIGTERM signals.
    When a signal is received, it will:
    1. Print a user-friendly interruption message
    2. Stop the crawler if it's running (via orchestrator or crawler_service)
    3. Raise KeyboardInterrupt to trigger existing exception handling
    
    Args:
        orchestrator: Optional CrawlerOrchestrator instance to stop crawler
        crawler_service: Optional crawler service instance with stop_crawler method
    """
    def signal_handler(signum, _frame):
        """Handle shutdown signals."""
        signal_name = signal.Signals(signum).name
        logger.warning(f"\nSignal {signal_name} received. Initiating graceful shutdown...")
        
        # Try to stop crawler if available
        crawler_stopped = False
        if orchestrator:
            try:
                if hasattr(orchestrator, '_is_running') and orchestrator._is_running:
                    logger.info("Stopping crawler...")
                    orchestrator.stop_crawler()
                    crawler_stopped = True
            except Exception as e:
                logger.error(f"Error stopping crawler via orchestrator: {e}")
        elif crawler_service and hasattr(crawler_service, 'stop_crawler'):
            try:
                # The stop_crawler method handles the case where crawler is not running
                logger.info("Attempting to stop crawler...")
                if crawler_service.stop_crawler():
                    crawler_stopped = True
            except Exception as e:
                logger.error(f"Error stopping crawler via service: {e}")
        
        if crawler_stopped:
            logger.info("Crawler stopped successfully.")
        
        # Print user-friendly message
        print("\n[INFO] Operation interrupted by user (Ctrl+C)")
        
        # Raise KeyboardInterrupt to trigger existing exception handling
        raise KeyboardInterrupt("Operation interrupted by user")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.debug("Signal handlers registered for SIGINT and SIGTERM")

