"""
Data storage layer for crawler entities.
"""
import sqlite3
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from .config import Configuration

logger = logging.getLogger(__name__)


class Storage:
    """
    Handles persistence of crawler sessions and parsed data.
    """

    def __init__(self, db_path: str = "crawler.db"):
        self.db_path = db_path
        logger.info(f"Initializing storage with database path: {self.db_path}")
        self._init_db()

    def _init_db(self) -> None:
        """
        Initialize database tables.
        """
        logger.debug("Initializing database tables")
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS configurations (
                        config_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        settings TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        is_default BOOLEAN NOT NULL DEFAULT 0
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS crawler_sessions (
                        session_id TEXT PRIMARY KEY,
                        config_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        progress REAL NOT NULL DEFAULT 0.0,
                        start_time TEXT,
                        end_time TEXT,
                        error_message TEXT,
                        FOREIGN KEY (config_id) REFERENCES configurations (config_id)
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS parsed_data (
                        data_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        element_type TEXT NOT NULL,
                        identifier TEXT NOT NULL,
                        bounding_box TEXT NOT NULL,
                        properties TEXT,
                        confidence_score REAL NOT NULL,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES crawler_sessions (session_id)
                    )
                """)
            logger.info("Database tables initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def save_configuration(self, config: Configuration) -> None:
        """
        Save configuration to database.
        """
        logger.debug(f"Saving configuration: {config.config_id}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO configurations
                    (config_id, name, settings, created_at, updated_at, is_default)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    config.config_id,
                    config.name,
                    json.dumps(config.settings),
                    config.created_at.isoformat(),
                    config.updated_at.isoformat(),
                    config.is_default
                ))
            logger.info(f"Configuration saved successfully: {config.config_id}")
        except sqlite3.Error as e:
            logger.error(f"Failed to save configuration {config.config_id}: {e}")
            raise

    def get_configuration(self, config_id: str) -> Optional[Configuration]:
        """
        Retrieve configuration by ID.
        """
        logger.debug(f"Retrieving configuration: {config_id}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("""
                    SELECT config_id, name, settings, created_at, updated_at, is_default
                    FROM configurations WHERE config_id = ?
                """, (config_id,)).fetchone()

                if row:
                    config = Configuration(
                        config_id=row[0],
                        name=row[1],
                        settings=json.loads(row[2]),
                        is_default=bool(row[5])
                    )
                    logger.info(f"Configuration retrieved successfully: {config_id}")
                    return config
                else:
                    logger.warning(f"Configuration not found: {config_id}")
                    return None
        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve configuration {config_id}: {e}")
            raise

    def save_session(self, session) -> None:
        """
        Save crawler session to database.
        """
        logger.debug(f"Saving session: {session.session_id}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO crawler_sessions
                    (session_id, config_id, status, progress, start_time, end_time, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_id,
                    session.config_id,
                    session.status,
                    session.progress,
                    session.start_time.isoformat() if session.start_time else None,
                    session.end_time.isoformat() if session.end_time else None,
                    session.error_message
                ))
            logger.info(f"Session saved successfully: {session.session_id} (status: {session.status})")
        except sqlite3.Error as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")
            raise

    def get_session(self, session_id: str) -> Optional[Any]:
        """
        Retrieve crawler session by ID.
        """
        logger.debug(f"Retrieving session: {session_id}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("""
                    SELECT session_id, config_id, status, progress, start_time, end_time, error_message
                    FROM crawler_sessions WHERE session_id = ?
                """, (session_id,)).fetchone()

                if row:
                    # Import here to avoid circular import
                    from .crawler import CrawlerSession
                    
                    # Create session with stored data
                    session = CrawlerSession(session_id=session_id)  # No config needed for retrieval
                    session.config_id = row[1]
                    session.status = row[2]
                    session.progress = row[3]
                    session.start_time = datetime.fromisoformat(row[4]) if row[4] else None
                    session.end_time = datetime.fromisoformat(row[5]) if row[5] else None
                    session.error_message = row[6]
                    
                    logger.info(f"Session retrieved successfully: {session_id} (status: {session.status})")
                    return session
                else:
                    logger.warning(f"Session not found: {session_id}")
                    return None
        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}")
            raise

    def save_parsed_data(self, data_list: List) -> None:
        """
        Save parsed data to database.
        """
        logger.debug(f"Saving {len(data_list)} parsed data items")
        try:
            with sqlite3.connect(self.db_path) as conn:
                for data in data_list:
                    conn.execute("""
                        INSERT INTO parsed_data
                        (data_id, session_id, element_type, identifier, bounding_box, properties, confidence_score, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data.data_id,
                        data.session_id,
                        data.element_type,
                        data.identifier,
                        json.dumps(data.bounding_box),
                        json.dumps(data.properties) if data.properties else None,
                        data.confidence_score,
                        data.timestamp.isoformat()
                    ))
            logger.info(f"Parsed data saved successfully: {len(data_list)} items")
        except sqlite3.Error as e:
            logger.error(f"Failed to save parsed data: {e}")
            raise

    def get_session_results(self, session_id: str) -> List:
        """
        Get all parsed data for a session.
        """
        logger.debug(f"Retrieving session results for: {session_id}")
        try:
            # Implementation would return list of ParsedData
            results = []
            logger.info(f"Retrieved {len(results)} results for session: {session_id}")
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve session results for {session_id}: {e}")
            raise