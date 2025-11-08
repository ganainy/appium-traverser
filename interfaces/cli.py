
#!/usr/bin/env python3
"""
CLI Interface for Core Crawler Modules.

This module provides a CLI interface that uses the shared core crawler modules
from the layered architecture, ensuring consistent behavior between CLI and GUI.
"""

import logging
import os
from typing import Dict, Any, Optional


from core.config import Configuration
from core.crawler import Crawler, CrawlerSession
from core.storage import Storage
from cli.services.focus_area_service import FocusAreaService
from cli.shared.context import CLIContext
from config.config import Config

logger = logging.getLogger(__name__)


class CLICrawlerInterface:
    """
    CLI interface that uses core crawler modules.

    This class provides a CLI-specific interface to the core crawler functionality,
    handling CLI-specific concerns like output formatting and user interaction.
    """

    def __init__(self, config_data: Optional[Dict[str, Any]] = None):
        """
        Initialize the CLI crawler interface.

        Args:
            config_data: Optional configuration data to use
        """
        self.config_data = config_data or {}
        self.config: Optional[Configuration] = None
        self.crawler: Optional[Crawler] = None
        self.storage: Optional[Storage] = None
        self.current_session: Optional[CrawlerSession] = None

        logger.info("CLI Crawler Interface initialized")

    def initialize_core(self) -> bool:
        """
        Initialize core modules with CLI-specific configuration.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Create configuration from CLI data
            settings = {
                "max_depth": self.config_data.get("max_depth", 5),
                "timeout": self.config_data.get("timeout", 60),
                "platform": self.config_data.get("platform", "android")
            }

            self.config = Configuration(
                name="CLI Crawler Config",
                settings=settings
            )

            # Validate configuration
            self.config.validate()
            logger.info("Core configuration validated")

            # Initialize storage
            storage_path = self.config_data.get("storage_path", "crawler.db")
            self.storage = Storage(storage_path)
            logger.info(f"Core storage initialized at {storage_path}")

            # Initialize crawler
            self.crawler = Crawler(self.config)
            logger.info("Core crawler initialized")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize core modules: {e}")
            return False

    def start_crawler_session(self) -> Optional[str]:
        """
        Start a new crawler session.

        Returns:
            Session ID if successful, None otherwise
        """
        if not self.crawler:
            logger.error("Crawler not initialized")
            return None

        try:
            logger.debug("DIAGNOSTIC: About to call crawler.start_session()")
            self.current_session = self.crawler.start_session()
            session_id = self.current_session.session_id
            logger.debug(f"DIAGNOSTIC: Session created with ID: {session_id}, status: {self.current_session.status}")

            # FIX: Transition session to "running" state immediately after creation
            self.current_session.start()
            self.crawler.storage.save_session(self.current_session)
            logger.info(f"FIX: Session {session_id} transitioned to 'running' state")

            # Log session start for CLI user
            print(f"UI_STATUS: Crawler session started: {session_id}")
            print(f"UI_STEP: 1")
            logger.info(f"Started crawler session: {session_id}")
            
            # TODO: Replace simulation with actual crawling implementation
            import threading
            import time
            
            def simulate_crawling():
                """Simulate crawling activity since real implementation is missing."""
                try:
                    logger.info("FIX: Starting simulated crawling activity")
                    print("UI_STATUS: Starting crawling simulation...")
                    
                    # Simulate some steps
                    for step in range(2, 6):
                        time.sleep(2)  # Simulate work
                        print(f"UI_STEP: {step}")
                        print(f"UI_ACTION: Simulated action {step}")
                        logger.info(f"FIX: Simulated step {step}")
                    
                    # Complete the session
                    logger.info("FIX: Completing simulated crawling")
                    print("UI_STATUS: Crawling simulation completed")
                    print("UI_END: COMPLETED")
                    
                    self.current_session.complete()
                    self.crawler.storage.save_session(self.current_session)
                    logger.info(f"FIX: Session {session_id} marked as completed")
                    
                except Exception as e:
                    logger.error(f"FIX: Error in crawling simulation: {e}")
                    self.current_session.fail(str(e))
                    self.crawler.storage.save_session(self.current_session)
                    print("UI_STATUS: Crawling simulation failed")
                    print("UI_END: FAILED")
            
            # Start crawling in background thread
            crawling_thread = threading.Thread(target=simulate_crawling, daemon=True)
            crawling_thread.start()
            logger.info("FIX: Started crawling simulation thread")

            return session_id

        except Exception as e:
            logger.error(f"Failed to start crawler session: {e}")
            print(f"UI_STATUS: Failed to start crawler session: {e}")
            return None

    def get_session_status(self, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get status of a crawler session.

        Args:
            session_id: Optional session ID (uses current session if not provided)

        Returns:
            Status dictionary if successful, None otherwise
        """
        if not self.crawler:
            logger.error("Crawler not initialized")
            return None

        try:
            target_session_id = session_id or (self.current_session.session_id if self.current_session else None)
            if not target_session_id:
                logger.error("No session ID available")
                return None

            session = self.crawler.get_status(target_session_id)

            # Format status for CLI output
            status_info = {
                "session_id": session.session_id,
                "status": session.status,
                "progress": session.progress,
                "start_time": session.start_time.isoformat() if session.start_time else None,
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "error_message": session.error_message
            }

            # CLI-specific status output
            print(f"UI_STATUS: Session {session.session_id} - {session.status} ({session.progress:.1%})")

            return status_info

        except Exception as e:
            logger.error(f"Failed to get session status: {e}")
            print(f"UI_STATUS: Failed to get session status: {e}")
            return None

    def stop_crawler_session(self, session_id: Optional[str] = None) -> bool:
        """
        Stop a crawler session.

        Args:
            session_id: Optional session ID (uses current session if not provided)

        Returns:
            True if successful, False otherwise
        """
        if not self.crawler:
            logger.error("Crawler not initialized")
            return False

        try:
            target_session_id = session_id or (self.current_session.session_id if self.current_session else None)
            if not target_session_id:
                logger.error("No session ID available")
                return False

            stopped_session = self.crawler.stop_session(target_session_id)

            # CLI-specific output
            print(f"UI_STATUS: Session {stopped_session.session_id} stopped")
            print("UI_END: Crawler session completed")
            logger.info(f"Stopped crawler session: {target_session_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to stop crawler session: {e}")
            print(f"UI_STATUS: Failed to stop crawler session: {e}")
            return False

    def get_session_results(self, session_id: Optional[str] = None) -> Optional[list]:
        """
        Get results from a crawler session.

        Args:
            session_id: Optional session ID (uses current session if not provided)

        Returns:
            List of results if successful, None otherwise
        """
        if not self.storage:
            logger.error("Storage not initialized")
            return None

        try:
            target_session_id = session_id or (self.current_session.session_id if self.current_session else None)
            if not target_session_id:
                logger.error("No session ID available")
                return None

            # TODO: Implement when parsed data functionality is added
            results = self.storage.get_session_results(target_session_id) if hasattr(self.storage, 'get_session_results') else []

            # CLI-specific output
            print(f"UI_STATUS: Retrieved {len(results)} results for session {target_session_id}")

            return results

        except Exception as e:
            logger.error(f"Failed to get session results: {e}")
            print(f"UI_STATUS: Failed to get session results: {e}")
            return None

    def save_configuration(self) -> bool:
        """
        Save current configuration to storage.

        Returns:
            True if successful, False otherwise
        """
        if not self.config or not self.storage:
            logger.error("Configuration or storage not initialized")
            return False

        try:
            self.storage.save_configuration(self.config)
            logger.info(f"Configuration saved: {self.config.config_id}")
            print(f"UI_STATUS: Configuration saved")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            print(f"UI_STATUS: Failed to save configuration: {e}")
            return False

    def load_configuration(self, config_id: str) -> bool:
        """
        Load configuration from storage.

        Args:
            config_id: Configuration ID to load

        Returns:
            True if successful, False otherwise
        """
        if not self.storage:
            logger.error("Storage not initialized")
            return False

        try:
            loaded_config = self.storage.get_configuration(config_id)
            if loaded_config:
                self.config = loaded_config
                # Reinitialize crawler with new config
                if self.config:
                    self.crawler = Crawler(self.config)
                logger.info(f"Configuration loaded: {config_id}")
                print(f"UI_STATUS: Configuration loaded: {config_id}")
                return True
            else:
                logger.warning(f"Configuration not found: {config_id}")
                print(f"UI_STATUS: Configuration not found: {config_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            print(f"UI_STATUS: Failed to load configuration: {e}")
            return False

    def cleanup(self):
        """
        Clean up resources.
        """
        try:
            if self.current_session and self.crawler:
                # Ensure session is stopped
                self.stop_crawler_session()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

        logger.info("CLI Crawler Interface cleaned up")


    # --- Focus Area CRUD CLI methods ---
    def _get_focus_service(self) -> FocusAreaService:
        """Get a FocusAreaService instance."""
        context = CLIContext()
        context.config = Config()
        return FocusAreaService(context)
    
    def cli_add_focus_area(self, name: str, description: str = ""):
        try:
            service = self._get_focus_service()
            success, msg = service.add_focus_area(name, description)
            if success:
                areas = service.get_focus_areas()
                result = next((a for a in areas if a.get('name') == name), {})
                print(f"UI_STATUS: Focus area added: {result}")
                return result
            else:
                print(f"UI_STATUS: Failed to add focus area: {msg}")
                return None
        except Exception as e:
            print(f"UI_STATUS: Failed to add focus area: {e}")
            return None

    def cli_remove_focus_area(self, id: int):
        try:
            service = self._get_focus_service()
            success, msg = service.remove_focus_area(str(id))
            if success:
                print(f"UI_STATUS: Focus area removed: {id}")
                return True
            else:
                print(f"UI_STATUS: Failed to remove focus area: {msg}")
                return False
        except Exception as e:
            print(f"UI_STATUS: Failed to remove focus area: {e}")
            return False

    def cli_update_focus_area(self, id: int, name: Optional[str] = None, description: Optional[str] = None):
        try:
            service = self._get_focus_service()
            success, msg = service.edit_focus_area(str(id), name, description)
            if success:
                areas = service.get_focus_areas()
                result = next((a for a in areas if a.get('id') == id), {})
                print(f"UI_STATUS: Focus area updated: {result}")
                return result
            else:
                print(f"UI_STATUS: Failed to update focus area: {msg}")
                return None
        except Exception as e:
            print(f"UI_STATUS: Failed to update focus area: {e}")
            return None

    def cli_list_focus_areas(self):
        try:
            service = self._get_focus_service()
            result = service.get_focus_areas()
            print(f"UI_STATUS: Focus areas: {result}")
            return result
        except Exception as e:
            print(f"UI_STATUS: Failed to list focus areas: {e}")
            return []