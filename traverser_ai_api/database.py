# database.py
import os
import sqlite3
import logging
from typing import List, Tuple, Optional, Union, Any

# Import your main Config class
# Adjust based on your project structure (e.g., from .config import Config)
from config import Config # Assuming config.py (with Config class) is in the same package

class DatabaseManager:
    """Handles SQLite database operations for crawler state, using centralized Config."""

    SCREENS_TABLE = "screens"
    TRANSITIONS_TABLE = "transitions"
    # Add other table names if needed, e.g., for detailed run/step logs
    # RUNS_TABLE = "runs"
    # STEPS_TABLE = "steps"


    def __init__(self, app_config: Config):
        self.cfg = app_config 
        self.db_path = str(self.cfg.DB_NAME) # Get db_path from config
        self.conn: Optional[sqlite3.Connection] = None

        if not self.db_path:
            raise ValueError("DatabaseManager: DB_NAME must be configured in the Config object.")
        
        # Attempt to connect upon initialization
        if not self.connect():
            # Logged in connect(), but good to be aware here too.
            logging.error(f"DatabaseManager failed to connect to {self.db_path} during initialization.")
            # Depending on desired behavior, could raise an error here or allow retries later.

    def connect(self) -> bool:
        """Connects to the SQLite database and creates tables if needed."""
        if self.conn:
            logging.debug("Database connection already active.")
            return True # Already connected

        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logging.info(f"Created database directory: {db_dir}")

            connect_timeout_seconds = float(self.cfg.DB_CONNECT_TIMEOUT) # Get from cfg
            busy_timeout_ms = int(self.cfg.DB_BUSY_TIMEOUT) # Get from cfg
            
            self.conn = sqlite3.connect(self.db_path, timeout=connect_timeout_seconds)
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.execute("PRAGMA journal_mode=WAL;") # Good for concurrency
            self.conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms};")

            if not self._create_tables(): # This includes run and step tables now
                logging.error("Failed to create necessary database tables.")
                self.close() # Ensure connection is closed if table creation fails
                return False

            logging.info(f"Successfully connected to database and verified tables: {self.db_path}")
            return True
        except sqlite3.Error as e:
            logging.error(f"SQLite error connecting to database {self.db_path}: {e}", exc_info=True)
            self.conn = None
            return False
        except Exception as e:
            logging.error(f"Unexpected error during database connection to {self.db_path}: {e}", exc_info=True)
            self.conn = None
            return False

    def close(self) -> None:
        """Closes the database connection."""
        if self.conn:
            try:
                self.conn.close()
                logging.info(f"Database connection closed: {self.db_path}")
            except Exception as e:
                logging.error(f"Error closing database connection: {e}", exc_info=True)
            finally:
                self.conn = None
        else:
            logging.debug("Attempted to close an already non-existent database connection.")


    def _execute_sql(self, sql: str, params: tuple = (), fetch_one: bool = False, 
                     fetch_all: bool = False, commit: bool = True) -> Any: # commit defaults to True now for non-SELECT
        """Helper to execute SQL queries."""
        if not self.conn:
            logging.error("Database not connected. Cannot execute SQL.")
            if fetch_all: return []
            return None
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql, params)
            if fetch_one:
                return cursor.fetchone()
            if fetch_all:
                return cursor.fetchall() or [] # Ensure list for fetch_all
            if commit: # Only commit if not a SELECT query that implies fetch_one/fetch_all
                self.conn.commit()
            return cursor.lastrowid # For INSERT, UPDATE, DELETE if commit is True
        except sqlite3.Error as e:
            logging.error(f"Database error executing SQL: {sql} | Params: {params} | Error: {e}")
            if self.conn: # Check if conn still exists before rollback
                try:
                    self.conn.rollback()
                except Exception as rb_err:
                    logging.error(f"Error during rollback: {rb_err}")
            if fetch_all: return []
            return None
        except Exception as e:
            logging.error(f"Unexpected error executing SQL: {sql} | Error: {e}", exc_info=True)
            if fetch_all: return []
            return None


    def _create_tables(self) -> bool:
        """Creates all necessary database tables. Returns True on success."""
        # Screen Table: Stores unique screen states
        sql_create_screens = f"""
        CREATE TABLE IF NOT EXISTS {self.SCREENS_TABLE} (
            screen_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Auto-incrementing local ID
            composite_hash TEXT NOT NULL UNIQUE,    -- xml_hash + visual_hash
            xml_hash TEXT NOT NULL,
            visual_hash TEXT NOT NULL,
            screenshot_path TEXT,
            activity_name TEXT,                 -- Added
            xml_content TEXT,                   -- Added for full XML storage
            first_seen_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            first_seen_run_id INTEGER,          -- Added
            first_seen_step_number INTEGER      -- Added
        );
        """
        # Runs Table: Stores information about each crawl run
        sql_create_runs = f"""
        CREATE TABLE IF NOT EXISTS runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_package TEXT NOT NULL,
            start_activity TEXT NOT NULL,
            start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            end_time DATETIME,
            status TEXT DEFAULT 'STARTED' -- e.g., STARTED, COMPLETED, FAILED, INTERRUPTED
        );
        """
        # State Transitions / Actions Log Table: Detailed log of each step
        sql_create_steps_log = f"""
        CREATE TABLE IF NOT EXISTS steps_log (
            step_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            step_number INTEGER NOT NULL,
            from_screen_id INTEGER,          -- FK to screens.screen_id
            to_screen_id INTEGER,            -- FK to screens.screen_id (can be NULL if action failed/no nav)
            action_description TEXT,         -- Human-readable general action
            ai_suggestion_json TEXT,         -- Full JSON from AI
            mapped_action_json TEXT,         -- Mapped action details
            execution_success BOOLEAN,
            error_message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY (from_screen_id) REFERENCES {self.SCREENS_TABLE}(screen_id) ON DELETE SET NULL,
            FOREIGN KEY (to_screen_id) REFERENCES {self.SCREENS_TABLE}(screen_id) ON DELETE SET NULL,
            UNIQUE (run_id, step_number) -- Ensures step numbers are unique per run
        );
        """
        # Old Transitions Table (can be kept for simpler graph analysis or removed if steps_log is sufficient)
        # For now, I will keep it as per your original schema, but with screen_id FKs
        sql_create_transitions_simplified = f"""
        CREATE TABLE IF NOT EXISTS {self.TRANSITIONS_TABLE} (
            transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_screen_id INTEGER NOT NULL, 
            to_screen_id INTEGER, -- Can be NULL if action leads nowhere new or fails
            action_description TEXT NOT NULL, -- Simplified action for graph edge
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (from_screen_id) REFERENCES {self.SCREENS_TABLE}(screen_id) ON DELETE CASCADE,
            FOREIGN KEY (to_screen_id) REFERENCES {self.SCREENS_TABLE}(screen_id) ON DELETE SET NULL
        );
        """

        try:
            self._execute_sql(sql_create_screens, commit=True)
            self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_screens_composite_hash ON {self.SCREENS_TABLE}(composite_hash);", commit=True)
            self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_screens_visual_hash ON {self.SCREENS_TABLE}(visual_hash);", commit=True)
            
            self._execute_sql(sql_create_runs, commit=True)
            self._execute_sql(sql_create_steps_log, commit=True)
            self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_steps_log_run_step ON steps_log(run_id, step_number);", commit=True)
            self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_steps_log_from_screen ON steps_log(from_screen_id);", commit=True)

            self._execute_sql(sql_create_transitions_simplified, commit=True) # Simplified transitions
            self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_transitions_from_screen_id ON {self.TRANSITIONS_TABLE}(from_screen_id);", commit=True)

            logging.debug("Database tables created/verified successfully.")
            return True
        except Exception as e:
            logging.error(f"Failed to create one or more database tables or indexes: {e}", exc_info=True)
            return False


    # --- Run Info Methods ---
    def get_or_create_run_info(self, app_package: str, start_activity: str) -> Optional[int]:
        """Gets the ID of the last 'STARTED' run for the app or creates a new one."""
        # Check for an existing 'STARTED' run for this app_package
        sql_find_started = "SELECT run_id FROM runs WHERE app_package = ? AND status = 'STARTED' ORDER BY start_time DESC LIMIT 1"
        result = self._execute_sql(sql_find_started, (app_package,), fetch_one=True)
        if result and result[0] is not None:
            run_id = result[0]
            logging.info(f"Continuing existing 'STARTED' run ID: {run_id} for {app_package}")
            return run_id

        # No 'STARTED' run found, create a new one
        sql_insert_run = "INSERT INTO runs (app_package, start_activity) VALUES (?, ?)"
        run_id = self._execute_sql(sql_insert_run, (app_package, start_activity), commit=True)
        if run_id is not None:
            logging.info(f"Created new run ID: {run_id} for {app_package}")
            return run_id
        else:
            logging.error(f"Failed to create new run entry for {app_package}")
            return None

    def update_run_status(self, run_id: int, status: str, end_time: Optional[str] = None) -> bool:
        """Updates the status and optionally end_time of a run."""
        if end_time:
            sql = "UPDATE runs SET status = ?, end_time = ? WHERE run_id = ?"
            params = (status, end_time, run_id)
        else:
            sql = "UPDATE runs SET status = ? WHERE run_id = ?"
            params = (status, run_id)
        result = self._execute_sql(sql, params, commit=True)
        return result is not None # Returns lastrowid which is not directly useful here, check for None error


    # --- Screen Methods (using screen_id as PK) ---
    def insert_screen(self, composite_hash: str, xml_hash: str, visual_hash: str,
                      screenshot_path: Optional[str], activity_name: Optional[str],
                      xml_content: Optional[str], run_id: int, step_number: int) -> Optional[int]:
        """Inserts a new screen if composite_hash doesn't exist, returns its screen_id."""
        sql_check = f"SELECT screen_id FROM {self.SCREENS_TABLE} WHERE composite_hash = ?"
        existing = self._execute_sql(sql_check, (composite_hash,), fetch_one=True)
        if existing:
            return existing[0] # Return existing screen_id

        sql_insert = f"""
        INSERT INTO {self.SCREENS_TABLE} 
        (composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content, first_seen_run_id, first_seen_step_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content, run_id, step_number)
        screen_id = self._execute_sql(sql_insert, params, commit=True) # This returns lastrowid which is screen_id
        return screen_id if isinstance(screen_id, int) else None


    def get_screen_by_composite_hash(self, composite_hash: str) -> Optional[Tuple]:
        """Retrieves a screen by its composite_hash."""
        # Returns (screen_id, composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content)
        sql = f"SELECT screen_id, composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content FROM {self.SCREENS_TABLE} WHERE composite_hash = ?"
        return self._execute_sql(sql, (composite_hash,), fetch_one=True) # type: ignore

    def get_screen_by_id(self, screen_id: int) -> Optional[Tuple]:
        """Retrieves a screen by its screen_id."""
        sql = f"SELECT screen_id, composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content FROM {self.SCREENS_TABLE} WHERE screen_id = ?"
        return self._execute_sql(sql, (screen_id,), fetch_one=True) # type: ignore

    def get_all_screens(self) -> List[Tuple[int, str, str, str, Optional[str], Optional[str], Optional[int], Optional[int]]]:
        """Retrieves all recorded screens."""
        # screen_id, composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content, first_seen_run_id, first_seen_step_number
        sql = f"SELECT screen_id, composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content, first_seen_run_id, first_seen_step_number FROM {self.SCREENS_TABLE}"
        result = self._execute_sql(sql, fetch_all=True)
        return result if isinstance(result, list) else []

    def get_max_screen_id(self) -> Optional[int]:
        """Gets the maximum screen_id from the database."""
        sql = f"SELECT MAX(screen_id) FROM {self.SCREENS_TABLE}"
        result = self._execute_sql(sql, fetch_one=True)
        return result[0] if result and result[0] is not None else 0


    # --- Step/Action Log Methods ---
    def insert_step_log(self, run_id: int, step_number: int, from_screen_id: Optional[int],
                        to_screen_id: Optional[int], action_description: Optional[str],
                        ai_suggestion_json: Optional[str], mapped_action_json: Optional[str],
                        execution_success: bool, error_message: Optional[str]) -> Optional[int]:
        """Logs a detailed step/action taken during a run."""
        sql = """
        INSERT INTO steps_log 
        (run_id, step_number, from_screen_id, to_screen_id, action_description, 
         ai_suggestion_json, mapped_action_json, execution_success, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (run_id, step_number, from_screen_id, to_screen_id, action_description,
                  ai_suggestion_json, mapped_action_json, execution_success, error_message)
        step_log_id = self._execute_sql(sql, params, commit=True)
        return step_log_id if isinstance(step_log_id, int) else None

    def get_steps_for_run(self, run_id: int) -> List[Tuple]:
        """Retrieves all logged steps for a given run ID."""
        sql = "SELECT * FROM steps_log WHERE run_id = ? ORDER BY step_number ASC"
        result = self._execute_sql(sql, (run_id,), fetch_all=True)
        return result if isinstance(result, list) else []

    def get_step_count_for_run(self, run_id: int) -> int:
        """Gets the number of steps recorded for a given run ID."""
        sql = "SELECT COUNT(*) FROM steps_log WHERE run_id = ?"
        result = self._execute_sql(sql, (run_id,), fetch_one=True)
        return result[0] if result and result[0] is not None else 0
        
    def get_action_history_for_screen(self, screen_id: int) -> List[str]:
        """Gets a list of action_description strings taken from a given screen_id."""
        # This queries the detailed steps_log table.
        sql = """
        SELECT DISTINCT action_description FROM steps_log 
        WHERE from_screen_id = ? AND action_description IS NOT NULL
        ORDER BY timestamp ASC 
        """ 
        # Could also add "AND execution_success = TRUE" if only successful actions are relevant for history
        results = self._execute_sql(sql, (screen_id,), fetch_all=True)
        return [row[0] for row in results] if isinstance(results, list) else []


    # --- Simplified Transitions Methods (using screen_id) ---
    def insert_simplified_transition(self, from_screen_id: int, action_description: str, to_screen_id: Optional[int]) -> Optional[int]:
        """Inserts a simplified transition record between screen IDs."""
        sql = f"""
        INSERT INTO {self.TRANSITIONS_TABLE}
        (from_screen_id, action_description, to_screen_id)
        VALUES (?, ?, ?)
        """
        params = (from_screen_id, action_description, to_screen_id)
        transition_id = self._execute_sql(sql, params, commit=True)
        return transition_id if isinstance(transition_id, int) else None

    def get_all_simplified_transitions(self) -> List[Tuple[int, str, Optional[int]]]:
        """Retrieves all simplified transitions (from_screen_id, action, to_screen_id)."""
        sql = f"SELECT from_screen_id, action_description, to_screen_id FROM {self.TRANSITIONS_TABLE}"
        result = self._execute_sql(sql, fetch_all=True)
        return result if isinstance(result, list) else []


    def initialize_db_for_fresh_run(self) -> bool:
        """
        Prepares the database for a completely fresh run by clearing screens and transitions.
        Run history in 'runs' table is preserved unless explicitly cleared elsewhere.
        This is typically called when config.CONTINUE_EXISTING_RUN is False.
        """
        if not self.conn:
            logging.info("DB not connected. Attempting connect before fresh run init.")
            if not self.connect():
                logging.error("Failed to connect to DB. Cannot initialize for fresh run.")
                return False

        logging.warning("Clearing Screens, Simplified Transitions, and Steps Log for a fresh run...")
        try:
            self._execute_sql(f"DELETE FROM {self.TRANSITIONS_TABLE};", commit=True)
            self._execute_sql(f"DELETE FROM steps_log;", commit=True) # Clear detailed steps
            self._execute_sql(f"DELETE FROM {self.SCREENS_TABLE};", commit=True)
            
            # Reset autoincrement counters for these tables
            self._execute_sql(f"DELETE FROM sqlite_sequence WHERE name='{self.SCREENS_TABLE}';", commit=True)
            self._execute_sql(f"DELETE FROM sqlite_sequence WHERE name='{self.TRANSITIONS_TABLE}';", commit=True)
            self._execute_sql(f"DELETE FROM sqlite_sequence WHERE name='steps_log';", commit=True)

            logging.info("Screens, Transitions, and Steps Log tables cleared successfully.")
            return True
        except Exception as e:
            logging.error(f"Failed to clear tables for fresh run: {e}", exc_info=True)
            return False