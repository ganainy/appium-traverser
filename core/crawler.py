"""
Core crawling logic and session management.
"""
import uuid
import logging
from datetime import datetime
from typing import List, Optional
from .config import Configuration
from .storage import Storage

logger = logging.getLogger(__name__)


class CrawlerSession:
    """
    Represents a complete crawling operation.
    """

    def __init__(self, config: Optional[Configuration] = None, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.config_id = config.config_id if config else None
        self.status = "pending"
        self.progress = 0.0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.results: List = []
        self.error_message: Optional[str] = None

    def validate(self) -> None:
        """
        Validate session state.
        """
        valid_statuses = ["pending", "running", "completed", "failed", "stopped"]
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status: {self.status}")

        if not (0.0 <= self.progress <= 1.0):
            raise ValueError("Progress must be between 0.0 and 1.0")

        if self.end_time and self.start_time and self.end_time < self.start_time:
            raise ValueError("End time cannot be before start time")

        if self.status == "failed" and not self.error_message:
            raise ValueError("Error message required for failed sessions")

    def start(self) -> None:
        """
        Start the crawling session.
        """
        if self.status != "pending":
            raise ValueError("Can only start pending sessions")

        self.status = "running"
        self.start_time = datetime.now()

    def complete(self) -> None:
        """
        Mark session as completed.
        """
        if self.status != "running":
            raise ValueError("Can only complete running sessions")

        self.status = "completed"
        self.progress = 1.0
        self.end_time = datetime.now()

    def fail(self, error_message: str) -> None:
        """
        Mark session as failed.
        """
        self.status = "failed"
        self.error_message = error_message
        self.end_time = datetime.now()

    def stop(self) -> None:
        """
        Stop the crawling session.
        """
        if self.status not in ["running", "pending"]:
            raise ValueError("Can only stop running or pending sessions")

        self.status = "stopped"
        self.end_time = datetime.now()


class Crawler:
    """
    Core crawling logic that can be used by any interface.
    """

    def __init__(self, config: Configuration):
        self.config = config
        self.storage = Storage()

    def start_session(self) -> CrawlerSession:
        """
        Start a new crawling session.
        """
        try:
            self.config.validate()
            session = CrawlerSession(self.config)
            self.storage.save_session(session)
            logger.info(f"Started crawler session {session.session_id} with config {self.config.name}")
            return session
        except Exception as e:
            logger.error(f"Failed to start crawler session: {e}")
            raise

    def get_status(self, session_id: str) -> CrawlerSession:
        """
        Get the current status of a crawling session.
        """
        try:
            session = self.storage.get_session(session_id)
            if session:
                logger.debug(f"Retrieved status for session {session_id}: {session.status}")
                return session
            else:
                # Session not found, create a new one (for backward compatibility)
                session = CrawlerSession(self.config, session_id)
                logger.debug(f"Created new session for {session_id}: {session.status}")
                return session
        except Exception as e:
            logger.error(f"Failed to get status for session {session_id}: {e}")
            raise

    def stop_session(self, session_id: str) -> CrawlerSession:
        """
        Stop a running crawling session.
        """
        try:
            session = self.get_status(session_id)
            session.stop()
            self.storage.save_session(session)
            logger.info(f"Stopped crawler session {session_id}")
            return session
        except Exception as e:
            logger.error(f"Failed to stop session {session_id}: {e}")
            raise