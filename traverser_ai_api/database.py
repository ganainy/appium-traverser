import os
import sqlite3
import logging
from typing import List, Tuple, Optional

class DatabaseManager:
    """Handles SQLite database operations for crawler state."""

    SCREENS_TABLE = "screens"
    TRANSITIONS_TABLE = "transitions"

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> bool: # Added return type hint -> bool
        """Connects to the SQLite database and creates tables if needed.

        Returns:
            bool: True if connection and table creation were successful, False otherwise.
        """
        # Close existing connection if any, before trying to reconnect
        if self.conn:
            logging.warning("Closing existing database connection before reconnecting.")
            self.close()

        try:
            # Create database directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logging.info(f"Created database directory: {db_dir}")

            # Attempt connection
            self.conn = sqlite3.connect(self.db_path, timeout=10) # Added timeout
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.execute("PRAGMA journal_mode=WAL;") # Optional: Improve concurrency
            self.conn.execute("PRAGMA busy_timeout = 5000;") # Optional: Wait if DB is locked

            # Create tables (check for success)
            if not self._create_tables():
                 logging.error("Failed to create necessary database tables.")
                 self.close() # Close connection if table creation fails
                 return False # Indicate failure

            logging.info(f"Successfully connected to database and verified tables: {self.db_path}")
            return True # Explicitly return True on success

        except sqlite3.Error as e:
            logging.error(f"Error connecting to database {self.db_path}: {e}", exc_info=True) # Added exc_info
            self.conn = None # Ensure connection is None on error
            return False # Explicitly return False on failure
        except Exception as e: # Catch other potential errors like permission issues
             logging.error(f"An unexpected error occurred during database connection: {e}", exc_info=True)
             self.conn = None
             return False

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed.")
            self.conn = None

    def _execute_sql(self, sql: str, params: tuple = (), fetch_one=False, fetch_all=False):
        """Helper to execute SQL queries."""
        if not self.conn:
            logging.error("Database not connected.")
            return None
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql, params)
            if fetch_one:
                return cursor.fetchone()
            if fetch_all:
                return cursor.fetchall()
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Database error executing SQL: {sql} Params: {params} Error: {e}")
            self.conn.rollback()
            return None

    def _create_tables(self) -> bool: # Added return type hint -> bool
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
            -- Optional FOREIGN KEY constraints if needed, ensure they match PKs
            -- FOREIGN KEY (source_composite_hash) REFERENCES {self.SCREENS_TABLE}(composite_hash) ON DELETE CASCADE,
            -- FOREIGN KEY (dest_composite_hash) REFERENCES {self.SCREENS_TABLE}(composite_hash) ON DELETE SET NULL
        );
        """
        # Execute creation statements and check results
        # _execute_sql returns True on successful commit (CREATE TABLE is committed)
        if self._execute_sql(sql_create_screens_v2) is None: success = False
        if self._execute_sql(sql_create_transitions) is None: success = False

        # Add indexes - check results too
        if self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_screen_visual_hash ON {self.SCREENS_TABLE}(visual_hash);") is None: success = False
        if self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_transition_source ON {self.TRANSITIONS_TABLE}(source_composite_hash);") is None: success = False

        if success:
            logging.debug("Database tables created or already exist.")
        else:
            logging.error("Failed to create one or more database tables or indexes.")

        return success


    # --- Other methods remain the same, but rely on _execute_sql handling ---
    def insert_screen(self, screen_id: int, xml_hash: str, visual_hash: str, screenshot_path: str) -> Optional[str]:
        """Inserts or updates screen information. Returns composite_hash on success/ignore, None on error."""
        composite_hash = f"{xml_hash}_{visual_hash}"
        sql = f"""
        INSERT OR IGNORE INTO {self.SCREENS_TABLE}
        (composite_hash, screen_id, xml_hash, visual_hash, screenshot_path)
        VALUES (?, ?, ?, ?, ?)
        """
        params = (composite_hash, screen_id, xml_hash, visual_hash, screenshot_path)
        # _execute_sql returns True on successful commit (which INSERT OR IGNORE does)
        # or None on error.
        result = self._execute_sql(sql, params)
        return composite_hash if result is not None else None


    def insert_screen(self, screen_id: int, xml_hash: str, visual_hash: str, screenshot_path: str) -> Optional[str]:
        """Inserts or updates screen information."""
        composite_hash = f"{xml_hash}_{visual_hash}"
        # Use INSERT OR IGNORE to avoid errors if hash already exists (e.g., loaded from previous run)
        # If using composite_hash as PK, this handles uniqueness.
        sql = f"""
        INSERT OR IGNORE INTO {self.SCREENS_TABLE}
        (composite_hash, screen_id, xml_hash, visual_hash, screenshot_path)
        VALUES (?, ?, ?, ?, ?)
        """
        params = (composite_hash, screen_id, xml_hash, visual_hash, screenshot_path)
        result = self._execute_sql(sql, params)
        # Return the composite hash whether inserted or ignored
        return composite_hash if result is not None else None


    def insert_transition(self, source_hash: str, action_desc: str, dest_hash: Optional[str]) -> Optional[int]:
        """Inserts a transition record."""
        sql = f"""
        INSERT INTO {self.TRANSITIONS_TABLE}
        (source_composite_hash, action_description, dest_composite_hash)
        VALUES (?, ?, ?)
        """
        params = (source_hash, action_desc, dest_hash)
        return self._execute_sql(sql, params)

    def get_all_screens(self) -> List[Tuple]:
        """Retrieves all recorded screens."""
        # Adjust based on final schema (V2)
        sql = f"SELECT screen_id, xml_hash, visual_hash, screenshot_path FROM {self.SCREENS_TABLE}"
        return self._execute_sql(sql, fetch_all=True) or []

    def get_all_transitions(self) -> List[Tuple]:
        """Retrieves all recorded transitions."""
        sql = f"SELECT source_composite_hash, action_description, dest_composite_hash FROM {self.TRANSITIONS_TABLE}"
        return self._execute_sql(sql, fetch_all=True) or []