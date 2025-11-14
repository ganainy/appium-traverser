"""
GUI Interface for Crawler Operations

This module provides a GUI-specific interface to the core crawler functionality,
ensuring consistent behavior between CLI and GUI interfaces.
"""

import logging
from typing import Any, Dict, List, Optional

from core.crawler_config import Configuration, ConfigurationError
from core.storage import Storage
from core.crawler import Crawler, CrawlerSession
from cli.services.focus_area_service import FocusAreaService
from cli.shared.context import ApplicationContext
from config.app_config import Config

logger = logging.getLogger(__name__)


class GUICrawlerInterface:
    """
    GUI interface for crawler operations using core modules.

    This class provides GUI-specific formatting and interaction patterns
    while delegating all business logic to the core modules.
    """

    def __init__(self, config_data: Optional[Dict[str, Any]] = None):
        """
        Initialize GUI crawler interface.

        Args:
            config_data: Optional configuration data to initialize with
        """
        self.config: Optional[Configuration] = None
        self.storage: Optional[Storage] = None
        self.crawler: Optional[Crawler] = None
        self.current_session: Optional[CrawlerSession] = None

        # Store initial config data for later initialization
        self._initial_config_data = config_data

        logger.info("GUI Crawler Interface initialized")

    def initialize_core(self) -> bool:
        """
        Initialize core modules with configuration.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize configuration (validation happens automatically)
            if self._initial_config_data:
                self.config = Configuration.from_dict(self._initial_config_data)
            else:
                # Use default configuration
                default_settings = {
                    "max_depth": 10,
                    "timeout": 300,
                    "platform": "android"
                }
                self.config = Configuration(name="default", settings=default_settings, is_default=True)

            # Initialize storage
            self.storage = Storage()

            # Initialize crawler
            self.crawler = Crawler(self.config)

            logger.info("Core modules initialized successfully for GUI interface")
            return True

        except ConfigurationError as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
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
            self.current_session = self.crawler.start_session()
            session_id = self.current_session.session_id

            # GUI-specific session start notification
            logger.info(f"Started crawler session: {session_id}")

            return session_id

        except Exception as e:
            logger.error(f"Failed to start crawler session: {e}")
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

            # Format status for GUI consumption
            status_info = {
                "session_id": session.session_id,
                "status": session.status,
                "progress": session.progress,
                "start_time": session.start_time.isoformat() if session.start_time else None,
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "error_message": session.error_message
            }

            return status_info

        except Exception as e:
            logger.error(f"Failed to get session status: {e}")
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

            logger.info(f"Stopped crawler session: {target_session_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to stop crawler session: {e}")
            return False

    def get_session_results(self, session_id: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
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

            return results

        except Exception as e:
            logger.error(f"Failed to get session results: {e}")
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
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
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
                return True
            else:
                logger.warning(f"Configuration not found: {config_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
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

        logger.info("GUI Crawler Interface cleaned up")


    # --- Focus Area CRUD GUI methods ---
    def _get_focus_service(self) -> FocusAreaService:
        """Get a FocusAreaService instance."""
        context = ApplicationContext()
        context.config = Config()
        return FocusAreaService(context)
    
    def gui_add_focus_area(self, name: str, description: str = ""):
        try:
            service = self._get_focus_service()
            success, msg = service.add_focus_area(name, description)
            if success:
                areas = service.get_focus_areas()
                result = next((a for a in areas if a.get('name') == name), {})
                logger.info(f"Focus area added: {result}")
                return result
            else:
                logger.error(f"Failed to add focus area: {msg}")
                return None
        except Exception as e:
            logger.error(f"Failed to add focus area: {e}")
            return None

    def gui_remove_focus_area(self, id: int):
        try:
            service = self._get_focus_service()
            success, msg = service.remove_focus_area(str(id))
            if success:
                logger.info(f"Focus area removed: {id}")
                return True
            else:
                logger.error(f"Failed to remove focus area: {msg}")
                return False
        except Exception as e:
            logger.error(f"Failed to remove focus area: {e}")
            return False

    def gui_update_focus_area(self, id: int, name: Optional[str] = None, description: Optional[str] = None):
        try:
            service = self._get_focus_service()
            success, msg = service.edit_focus_area(str(id), name, description)
            if success:
                areas = service.get_focus_areas()
                result = next((a for a in areas if a.get('id') == id), {})
                logger.info(f"Focus area updated: {result}")
                return result
            else:
                logger.error(f"Failed to update focus area: {msg}")
                return None
        except Exception as e:
            logger.error(f"Failed to update focus area: {e}")
            return None

    def gui_list_focus_areas(self):
        try:
            service = self._get_focus_service()
            result = service.get_focus_areas()
            logger.info(f"Focus areas: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to list focus areas: {e}")
            return []


# Convenience function for GUI usage

def create_gui_interface(config_data: Optional[Dict[str, Any]] = None) -> GUICrawlerInterface:
    """
    Create and initialize a GUI crawler interface.

    Args:
        config_data: Optional configuration data

    Returns:
        Initialized GUI crawler interface
    """
    interface = GUICrawlerInterface(config_data)
    if interface.initialize_core():
        return interface
    else:
        raise RuntimeError("Failed to initialize GUI crawler interface")