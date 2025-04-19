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

    def connect(self):
        """Connects to the SQLite database and creates tables if needed."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.execute("PRAGMA foreign_keys = ON;") # Enforce foreign keys if used
            self._create_tables()
            logging.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logging.error(f"Error connecting to database {self.db_path}: {e}")
            self.conn = None

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

    def _create_tables(self):
        """Creates the necessary database tables."""
        sql_create_screens = f"""
        CREATE TABLE IF NOT EXISTS {self.SCREENS_TABLE} (
            screen_id INTEGER PRIMARY KEY,
            xml_hash TEXT NOT NULL,
            visual_hash TEXT NOT NULL UNIQUE, -- Visual hash should ideally be unique identifier for screen state
            screenshot_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            -- composite_hash TEXT UNIQUE -- Alternative: Use composite hash as unique key
        );
        """
        # Using composite hash as primary key might simplify lookups
        sql_create_screens_v2 = f"""
        CREATE TABLE IF NOT EXISTS {self.SCREENS_TABLE} (
            composite_hash TEXT PRIMARY KEY, -- xml_visual hash combo
            screen_id INTEGER NOT NULL UNIQUE, -- Keep original numeric ID
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
            dest_composite_hash TEXT, -- Can be NULL if destination unknown
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            -- FOREIGN KEY (source_composite_hash) REFERENCES {self.SCREENS_TABLE}(composite_hash), -- If using composite PK
            -- FOREIGN KEY (dest_composite_hash) REFERENCES {self.SCREENS_TABLE}(composite_hash)
        );
        """
        self._execute_sql(sql_create_screens_v2) # Using V2 with composite hash PK
        self._execute_sql(sql_create_transitions)
        # Add indexes for faster lookups
        self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_screen_visual_hash ON {self.SCREENS_TABLE}(visual_hash);")
        self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_transition_source ON {self.TRANSITIONS_TABLE}(source_composite_hash);")


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