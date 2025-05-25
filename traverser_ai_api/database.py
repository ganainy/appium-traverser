import os
import sqlite3
import logging
from typing import List, Tuple, Optional, Union, Any
from . import config  # Import the config module

class DatabaseManager:
    """Handles SQLite database operations for crawler state."""

    SCREENS_TABLE = "screens"
    TRANSITIONS_TABLE = "transitions"

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> bool:
        """Connects to the SQLite database and creates tables if needed.

        Returns:
            bool: True if connection and table creation were successful, False otherwise.
        """
        if self.conn:
            logging.warning("Closing existing database connection before reconnecting.")
            self.close()

        try:
            # Create database directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logging.info(f"Created database directory: {db_dir}")

            self.conn = sqlite3.connect(self.db_path, timeout=config.DB_CONNECT_TIMEOUT)
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute(f"PRAGMA busy_timeout = {config.DB_BUSY_TIMEOUT};")

            if not self._create_tables():
                logging.error("Failed to create necessary database tables.")
                self.close()
                return False

            logging.info(f"Successfully connected to database and verified tables: {self.db_path}")
            return True

        except sqlite3.Error as e:
            logging.error(f"Error connecting to database {self.db_path}: {e}", exc_info=True)
            self.conn = None
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred during database connection: {e}", exc_info=True)
            self.conn = None
            return False

    def close(self) -> None:
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed.")
            self.conn = None

    def _execute_sql(self, sql: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False) -> Optional[Union[int, Tuple, List[Tuple]]]:
        """Helper to execute SQL queries.
        
        Args:
            sql: The SQL query to execute
            params: Query parameters to substitute
            fetch_one: If True, return a single row
            fetch_all: If True, return all rows
            
        Returns:
            - For INSERT/UPDATE/DELETE (no fetch): lastrowid or None on error
            - For fetch_one=True: A tuple (row) or None if no results/error
            - For fetch_all=True: A list of tuples (rows) or [] if no results/error
        """
        if not self.conn:
            logging.error("Database not connected.")
            return None
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql, params)
            if fetch_one:
                return cursor.fetchone()
            if fetch_all:
                return cursor.fetchall() or []
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Database error executing SQL: {sql} Params: {params} Error: {e}")
            self.conn.rollback()
            return None if not fetch_all else []

    def _create_tables(self) -> bool:
        """Creates the necessary database tables. Returns True on success, False on failure."""
        success = True
        # Using V2 schema with composite hash PK
        sql_create_screens_v2 = f"""
        CREATE TABLE IF NOT EXISTS {self.SCREENS_TABLE} (
            composite_hash TEXT PRIMARY KEY,
            screen_id INTEGER NOT NULL UNIQUE,
            xml_hash TEXT NOT NULL,
            visual_hash TEXT NOT NULL,
            screenshot_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
        sql_create_transitions = f"""
        CREATE TABLE IF NOT EXISTS {self.TRANSITIONS_TABLE} (
            transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_composite_hash TEXT NOT NULL,
            action_description TEXT NOT NULL,
            dest_composite_hash TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
        if self._execute_sql(sql_create_screens_v2) is None:
            success = False
        if self._execute_sql(sql_create_transitions) is None:
            success = False
        if self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_screen_visual_hash ON {self.SCREENS_TABLE}(visual_hash);") is None:
            success = False
        if self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_transition_source ON {self.TRANSITIONS_TABLE}(source_composite_hash);") is None:
            success = False

        if success:
            logging.debug("Database tables created or already exist.")
        else:
            logging.error("Failed to create one or more database tables or indexes.")
        return success

    def insert_screen(self, screen_id: int, xml_hash: str, visual_hash: str, screenshot_path: str) -> Optional[str]:
        """Inserts or updates screen information. Returns composite_hash on success/ignore, None on error.
        
        Args:
            screen_id: The unique identifier for this screen state
            xml_hash: The hash of the screen's XML structure
            visual_hash: The hash of the screen's visual appearance
            screenshot_path: Path to the saved screenshot file
            
        Returns:
            The composite hash if the operation succeeded (whether inserted or ignored), 
            None if there was an error.
        """
        composite_hash = f"{xml_hash}_{visual_hash}"
        sql = f"""
        INSERT OR IGNORE INTO {self.SCREENS_TABLE}
        (composite_hash, screen_id, xml_hash, visual_hash, screenshot_path)
        VALUES (?, ?, ?, ?, ?)
        """
        params = (composite_hash, screen_id, xml_hash, visual_hash, screenshot_path)
        result = self._execute_sql(sql, params)
        return composite_hash if result is not None else None

    def insert_transition(self, source_hash: str, action_desc: str, dest_hash: Optional[str]) -> Optional[int]:
        """Inserts a transition record.
        
        Returns:
            The transition ID if successful, None on error.
        """
        sql = f"""
        INSERT INTO {self.TRANSITIONS_TABLE}
        (source_composite_hash, action_description, dest_composite_hash)
        VALUES (?, ?, ?)
        """
        params = (source_hash, action_desc, dest_hash)
        result = self._execute_sql(sql, params)
        return result if isinstance(result, int) else None

    def get_all_screens(self) -> List[Tuple[int, str, str, str]]:
        """Retrieves all recorded screens.
        
        Returns:
            List of tuples (screen_id, xml_hash, visual_hash, screenshot_path)
        """
        sql = f"SELECT screen_id, xml_hash, visual_hash, screenshot_path FROM {self.SCREENS_TABLE}"
        result = self._execute_sql(sql, fetch_all=True)
        return result if isinstance(result, list) else []

    def get_all_transitions(self) -> List[Tuple[str, str, Optional[str]]]:
        """Retrieves all recorded transitions.
        
        Returns:
            List of tuples (source_composite_hash, action_description, dest_composite_hash)
        """
        sql = f"SELECT source_composite_hash, action_description, dest_composite_hash FROM {self.TRANSITIONS_TABLE}"
        result = self._execute_sql(sql, fetch_all=True)
        return result if isinstance(result, list) else []

    def get_total_transitions(self) -> int:
        """Gets the total number of transitions recorded in the database.
        
        Returns:
            int: The number of transitions, or -1 if there was an error, or 0 if no database.
        """
        if not self.conn:
            return 0
        try:
            sql = f"SELECT COUNT(*) FROM {self.TRANSITIONS_TABLE}"
            result = self._execute_sql(sql, fetch_one=True)
            if result and isinstance(result, tuple) and len(result) > 0:
                return result[0]
            return 0
        except Exception as e:
            logging.error(f"Failed to get total transitions count from DB: {e}")
            return -1

    def initialize_db(self) -> bool:
        """Clears all data from crawler tables for a fresh start. Returns True on success."""
        if not self.conn:
            logging.info("Database not connected. Attempting to connect before initializing.")
            if not self.connect():
                logging.error("Failed to connect to DB. Cannot initialize (clear) tables.")
                return False

        logging.info("Clearing data from crawler tables for a fresh run...")
        try:
            self._execute_sql(f"DELETE FROM {self.TRANSITIONS_TABLE};")
            self._execute_sql(f"DELETE FROM {self.SCREENS_TABLE};")
            self._execute_sql(f"DELETE FROM sqlite_sequence WHERE name='{self.TRANSITIONS_TABLE}';")
            logging.info("Crawler tables cleared successfully.")
            return True
        except Exception as e:
            logging.error(f"Failed to clear tables during initialization: {e}", exc_info=True)
            return False