"""
Data storage layer for crawler entities.
"""
import sqlite3
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from .crawler_config import Configuration

logger = logging.getLogger(__name__)

# Module-level constant for default database path
DEFAULT_DB_PATH = "crawler.db"


class Storage:
    """
    Handles persistence of crawler sessions and parsed data.
    """
    
    # Table Names
    TABLE_CONFIGS = "configurations"
    TABLE_SESSIONS = "crawler_sessions"
    
    # Column Lists
    COLS_CONFIG = ("config_id", "name", "settings", "created_at", "updated_at", "is_default")
    COLS_SESSION = ("session_id", "config_id", "status", "progress", "start_time", "end_time", "error_message")

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        Initialize storage with database path.
        """
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
                # Create configurations table
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.TABLE_CONFIGS} (
                        config_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        settings TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        is_default BOOLEAN NOT NULL DEFAULT 0
                    )
                """)

                # Create crawler_sessions table
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.TABLE_SESSIONS} (
                        session_id TEXT PRIMARY KEY,
                        config_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        progress REAL NOT NULL DEFAULT 0.0,
                        start_time TEXT,
                        end_time TEXT,
                        error_message TEXT,
                        FOREIGN KEY (config_id) REFERENCES {self.TABLE_CONFIGS} (config_id)
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
                cols = ', '.join(self.COLS_CONFIG)
                placeholders = ', '.join(['?'] * len(self.COLS_CONFIG))
                sql = f"INSERT OR REPLACE INTO {self.TABLE_CONFIGS} ({cols}) VALUES ({placeholders})"
                conn.execute(sql, (
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
                cols = ', '.join(self.COLS_CONFIG)
                sql = f"SELECT {cols} FROM {self.TABLE_CONFIGS} WHERE config_id = ?"
                row = conn.execute(sql, (config_id,)).fetchone()

                if row:
                    config_data = {
                        "config_id": row[0],
                        "name": row[1],
                        "settings": json.loads(row[2]),
                        "created_at": row[3],
                        "updated_at": row[4],
                        "is_default": bool(row[5]),
                    }
                    config = Configuration.from_dict(config_data)
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
                cols = ', '.join(self.COLS_SESSION)
                placeholders = ', '.join(['?'] * len(self.COLS_SESSION))
                sql = f"INSERT OR REPLACE INTO {self.TABLE_SESSIONS} ({cols}) VALUES ({placeholders})"
                conn.execute(sql, (
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
                cols = ', '.join(self.COLS_SESSION)
                sql = f"SELECT {cols} FROM {self.TABLE_SESSIONS} WHERE session_id = ?"
                row = conn.execute(sql, (session_id,)).fetchone()

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

    def get_session_results(self, session_id: str) -> List:
        """
        Get all parsed data for a session.
        
        Note: Currently returns empty list as parsed data functionality is not yet implemented.
        """
        logger.debug(f"Retrieving session results for: {session_id}")
        # TODO: Implement when parsed data functionality is added
        return []