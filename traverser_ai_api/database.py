# database.py
import logging
import os
import sqlite3
import threading  # Added for thread identification
from typing import Any, List, Optional, Tuple, Union

try:
    from traverser_ai_api.config import Config
except ImportError:
    from config import Config

class DatabaseManager:
    SCREENS_TABLE = "screens"
    TRANSITIONS_TABLE = "transitions"

    def __init__(self, app_config: Config):
        self.cfg = app_config
        self.db_path = str(self.cfg.DB_NAME)
        self.conn: Optional[sqlite3.Connection] = None
        self._conn_thread_ident: Optional[int] = None # Stores the thread ID that owns self.conn

        if not self.db_path:
            raise ValueError("DatabaseManager: DB_NAME must be configured in the Config object.")

    def connect(self) -> bool:
        current_thread_id = threading.get_ident()
        if self.conn:
            if self._conn_thread_ident == current_thread_id:
                try:
                    # Check if the connection is still alive and usable
                    self.conn.execute("SELECT 1").fetchone()
                    logging.debug(f"Database connection is active for current thread {current_thread_id}.")
                    return True
                except sqlite3.Error as e:
                    logging.warning(f"⚠️ Existing database connection for thread {current_thread_id} is not usable ({e}). Reconnecting.")
                    self.conn = None
                    self._conn_thread_ident = None
            else:
                # Connection exists but was created by a different thread. This is the problematic case.
                logging.warning(
                    f"⚠️ Database connection found (owned by thread {self._conn_thread_ident}) "
                    f"but current operation is in thread {current_thread_id}. "
                    f"Closing old connection and creating a new one for current thread."
                )
                try:
                    self.conn.close() # Attempt to close the old connection
                except sqlite3.Error as e_close:
                    logging.warning(f"⚠️ Error closing connection from thread {self._conn_thread_ident} in thread {current_thread_id}: {e_close}")
                finally:
                    self.conn = None
                    self._conn_thread_ident = None

        # If self.conn is None (either initially or cleared above)
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logging.debug(f"Created database directory: {db_dir}")

            connect_timeout_seconds = float(self.cfg.DB_CONNECT_TIMEOUT)
            busy_timeout_ms = int(self.cfg.DB_BUSY_TIMEOUT)

            # Connect with check_same_thread=True (default)
            self.conn = sqlite3.connect(self.db_path, timeout=connect_timeout_seconds)
            self._conn_thread_ident = current_thread_id # Store the creator thread ID

            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms};")

            if not self._create_tables():
                logging.error("Failed to create necessary database tables.")
                self.close() # This will also clear _conn_thread_ident
                return False

            logging.debug(f"Successfully connected to database and verified tables: {self.db_path} (Thread ID: {self._conn_thread_ident})")
            return True
        except sqlite3.Error as e:
            logging.error(f"SQLite error connecting to database {self.db_path} in thread {current_thread_id}: {e}", exc_info=True)
            self.conn = None
            self._conn_thread_ident = None
            return False
        except Exception as e:
            logging.error(f"Unexpected error during database connection to {self.db_path} in thread {current_thread_id}: {e}", exc_info=True)
            self.conn = None
            self._conn_thread_ident = None
            return False

    def close(self) -> None:
        current_thread_id = threading.get_ident()
        if self.conn:
            if self._conn_thread_ident is not None and self._conn_thread_ident != current_thread_id:
                logging.warning(
                    f"⚠️ Attempting to close DB connection from thread {current_thread_id}, "
                    f"but it was created by/owned by thread {self._conn_thread_ident}. "
                    f"This might lead to issues if the original thread still expects to use it."
                )
            # Regardless of which thread is calling close, try to close it.
            try:
                self.conn.close()
                logging.debug(f"Database connection closed: {self.db_path} (Closed by thread: {current_thread_id}, Owned by: {self._conn_thread_ident})")
            except Exception as e: # Catch generic Exception as sqlite3.Error might not cover all scenarios if conn is weird
                logging.error(f"Error closing database connection in thread {current_thread_id}: {e}", exc_info=True)
            finally:
                self.conn = None
                self._conn_thread_ident = None # Clear ownership on close
        else:
            logging.debug(f"Attempted to close an already non-existent database connection (Thread ID: {current_thread_id}).")


    def _execute_sql(self, sql: str, params: tuple = (), fetch_one: bool = False,
                     fetch_all: bool = False, commit: bool = True) -> Any:
        current_thread_id = threading.get_ident()
        # Ensure connection is valid for the current thread.
        # self.connect() will handle creating/validating the connection for current_thread_id.
        if not self.conn or self._conn_thread_ident != current_thread_id:
            logging.debug(f"_execute_sql in thread {current_thread_id}: Connection is None or owned by another thread ({self._conn_thread_ident}). Re-evaluating connection.")
            if not self.connect(): # connect() now ensures conn is for current_thread_id or fails
                logging.error(f"🔴 Failed to establish/validate DB connection for thread {current_thread_id} from _execute_sql.")
                if fetch_all: return []
                return None

        # At this point, self.conn should be valid and owned by current_thread_id
        try:
            if not self.conn:
                logging.error("🔴 Database connection is None")
                if fetch_all: return []
                return None
            cursor = self.conn.cursor()
            cursor.execute(sql, params)
            if fetch_one:
                return cursor.fetchone()
            if fetch_all:
                return cursor.fetchall() or []
            if commit:
                self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e: # sqlite3.Error includes ProgrammingError
            logging.error(f"🔴 Database error executing SQL in thread {current_thread_id}: {sql} | Params: {params} | Error: {e}", exc_info=True)
            if "thread" in str(e).lower(): # Heuristic for threading error
                logging.warning("⚠️ Detected potential threading error during SQL execution. Invalidating connection for this manager instance.")
                self.conn = None # Invalidate the connection
                self._conn_thread_ident = None
            elif self.conn: # If not a threading error and conn exists
                 try: self.conn.rollback()
                 except Exception as rb_err: logging.error(f"🔴 Error during rollback: {rb_err}")

            if fetch_all: return []
            return None
        except Exception as e: # Catch other unexpected errors
            logging.error(f"🔴 Unexpected error executing SQL in thread {current_thread_id}: {sql} | Error: {e}", exc_info=True)
            if fetch_all: return []
            return None

    def _create_tables(self) -> bool:
        sql_create_screens = f"""
        CREATE TABLE IF NOT EXISTS {self.SCREENS_TABLE} (
            screen_id INTEGER PRIMARY KEY AUTOINCREMENT,
            composite_hash TEXT NOT NULL UNIQUE,
            xml_hash TEXT NOT NULL,
            visual_hash TEXT NOT NULL,
            screenshot_path TEXT,
            activity_name TEXT,
            xml_content TEXT,
            first_seen_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            first_seen_run_id INTEGER,
            first_seen_step_number INTEGER
        );
        """
        sql_create_runs = f"""
        CREATE TABLE IF NOT EXISTS runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_package TEXT NOT NULL,
            start_activity TEXT NOT NULL,
            start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            end_time DATETIME,
            status TEXT DEFAULT 'STARTED'
        );
        """
        sql_create_steps_log = f"""
        CREATE TABLE IF NOT EXISTS steps_log (
            step_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            step_number INTEGER NOT NULL,
            from_screen_id INTEGER,
            to_screen_id INTEGER,
            action_description TEXT,
            ai_suggestion_json TEXT,
            mapped_action_json TEXT,
            execution_success BOOLEAN,
            error_message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ai_response_time_ms REAL,
            total_tokens INTEGER,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY (from_screen_id) REFERENCES {self.SCREENS_TABLE}(screen_id) ON DELETE SET NULL,
            FOREIGN KEY (to_screen_id) REFERENCES {self.SCREENS_TABLE}(screen_id) ON DELETE SET NULL,
            UNIQUE (run_id, step_number)
        );
        """
        sql_create_transitions_simplified = f"""
        CREATE TABLE IF NOT EXISTS {self.TRANSITIONS_TABLE} (
            transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_screen_id INTEGER NOT NULL,
            to_screen_id INTEGER,
            action_description TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (from_screen_id) REFERENCES {self.SCREENS_TABLE}(screen_id) ON DELETE CASCADE,
            FOREIGN KEY (to_screen_id) REFERENCES {self.SCREENS_TABLE}(screen_id) ON DELETE SET NULL
        );
        """
        sql_create_run_meta = f"""
        CREATE TABLE IF NOT EXISTS run_meta (
            meta_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            meta_json TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
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
            self._execute_sql(sql_create_transitions_simplified, commit=True)
            self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_transitions_from_screen_id ON {self.TRANSITIONS_TABLE}(from_screen_id);", commit=True)
            self._execute_sql(sql_create_run_meta, commit=True)
            self._execute_sql(f"CREATE INDEX IF NOT EXISTS idx_run_meta_run_id ON run_meta(run_id);", commit=True)
            logging.debug("Database tables created/verified successfully.")
            return True
        except Exception as e:
            logging.error(f"🔴 Failed to create one or more database tables or indexes: {e}", exc_info=True)
            return False

    def get_or_create_run_info(self, app_package: str, start_activity: str) -> Optional[int]:
        sql_find_started = "SELECT run_id FROM runs WHERE app_package = ? AND status = 'STARTED' ORDER BY start_time DESC LIMIT 1"
        result = self._execute_sql(sql_find_started, (app_package,), fetch_one=True, commit=False)
        if result and result[0] is not None:
            run_id = result[0]
            logging.debug(f"Continuing existing 'STARTED' run ID: {run_id} for {app_package}")
            return run_id

        sql_insert_run = "INSERT INTO runs (app_package, start_activity) VALUES (?, ?)"
        run_id = self._execute_sql(sql_insert_run, (app_package, start_activity), commit=True)
        if run_id is not None:
            logging.debug(f"Created new run ID: {run_id} for {app_package}")
            return run_id
        else:
            logging.error(f"🔴 Failed to create new run entry for {app_package}")
            return None

    def update_run_status(self, run_id: int, status: str, end_time: Optional[str] = None) -> bool:
        if end_time:
            sql = "UPDATE runs SET status = ?, end_time = ? WHERE run_id = ?"
            params = (status, end_time, run_id)
        else:
            sql = "UPDATE runs SET status = ? WHERE run_id = ?"
            params = (status, run_id)
        result = self._execute_sql(sql, params, commit=True)
        return result is not None

    def insert_screen(self, composite_hash: str, xml_hash: str, visual_hash: str,
                      screenshot_path: Optional[str], activity_name: Optional[str],
                      xml_content: Optional[str], run_id: int, step_number: int) -> Optional[int]:
        sql_check = f"SELECT screen_id FROM {self.SCREENS_TABLE} WHERE composite_hash = ?"
        existing = self._execute_sql(sql_check, (composite_hash,), fetch_one=True, commit=False)
        if existing:
            return existing[0]

        sql_insert = f"""
        INSERT INTO {self.SCREENS_TABLE}
        (composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content, first_seen_run_id, first_seen_step_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content, run_id, step_number)
        screen_id = self._execute_sql(sql_insert, params, commit=True)
        return screen_id if isinstance(screen_id, int) else None

    def get_screen_by_composite_hash(self, composite_hash: str) -> Optional[Tuple]:
        sql = f"SELECT screen_id, composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content FROM {self.SCREENS_TABLE} WHERE composite_hash = ?"
        return self._execute_sql(sql, (composite_hash,), fetch_one=True, commit=False)

    def get_screen_by_id(self, screen_id: int) -> Optional[Tuple]:
        sql = f"SELECT screen_id, composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content FROM {self.SCREENS_TABLE} WHERE screen_id = ?"
        return self._execute_sql(sql, (screen_id,), fetch_one=True, commit=False)

    def get_all_screens(self) -> List[Tuple[int, str, str, str, Optional[str], Optional[str], Optional[int], Optional[int]]]:
        sql = f"SELECT screen_id, composite_hash, xml_hash, visual_hash, screenshot_path, activity_name, xml_content, first_seen_run_id, first_seen_step_number FROM {self.SCREENS_TABLE}"
        result = self._execute_sql(sql, fetch_all=True, commit=False)
        return result if isinstance(result, list) else []

    def get_max_screen_id(self) -> Optional[int]:
        sql = f"SELECT MAX(screen_id) FROM {self.SCREENS_TABLE}"
        result = self._execute_sql(sql, fetch_one=True, commit=False)
        return result[0] if result and result[0] is not None else 0
        
    def get_screen_visit_count(self, composite_hash: str) -> int:
        """Get the total number of visits to a screen across all runs."""
        sql = f"SELECT COUNT(*) FROM {self.TRANSITIONS_TABLE} WHERE to_screen_hash = ?"
        result = self._execute_sql(sql, (composite_hash,), fetch_one=True, commit=False)
        return result[0] if result and result[0] is not None else 0

    def insert_step_log(self, run_id: int, step_number: int, from_screen_id: Optional[int],
                        to_screen_id: Optional[int], action_description: Optional[str],
                        ai_suggestion_json: Optional[str], mapped_action_json: Optional[str],
                        execution_success: bool, error_message: Optional[str],
                        ai_response_time: Optional[float] = None, total_tokens: Optional[int] = None) -> Optional[int]:
        sql = """
        INSERT INTO steps_log
        (run_id, step_number, from_screen_id, to_screen_id, action_description,
         ai_suggestion_json, mapped_action_json, execution_success, error_message, ai_response_time_ms, total_tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (run_id, step_number, from_screen_id, to_screen_id, action_description,
                  ai_suggestion_json, mapped_action_json, execution_success, error_message, ai_response_time, total_tokens)
        step_log_id = self._execute_sql(sql, params, commit=True)
        return step_log_id if isinstance(step_log_id, int) else None

    def get_steps_for_run(self, run_id: int) -> List[Tuple]:
        sql = "SELECT * FROM steps_log WHERE run_id = ? ORDER BY step_number ASC"
        result = self._execute_sql(sql, (run_id,), fetch_all=True, commit=False)
        return result if isinstance(result, list) else []

    def get_step_count_for_run(self, run_id: int) -> int:
        sql = "SELECT COUNT(*) FROM steps_log WHERE run_id = ?"
        result = self._execute_sql(sql, (run_id,), fetch_one=True, commit=False)
        return result[0] if result and result[0] is not None else 0

    def get_action_history_for_screen(self, screen_id: int) -> List[str]:
        sql = """
        SELECT DISTINCT action_description FROM steps_log
        WHERE from_screen_id = ? AND action_description IS NOT NULL
        ORDER BY timestamp ASC
        """
        results = self._execute_sql(sql, (screen_id,), fetch_all=True, commit=False)
        return [row[0] for row in results] if isinstance(results, list) else []

    def insert_simplified_transition(self, from_screen_id: int, action_description: str, to_screen_id: Optional[int]) -> Optional[int]:
        sql = f"""
        INSERT INTO {self.TRANSITIONS_TABLE}
        (from_screen_id, action_description, to_screen_id)
        VALUES (?, ?, ?)
        """
        params = (from_screen_id, action_description, to_screen_id)
        transition_id = self._execute_sql(sql, params, commit=True)
        return transition_id if isinstance(transition_id, int) else None

    def get_all_simplified_transitions(self) -> List[Tuple[int, str, Optional[int]]]:
        sql = f"SELECT from_screen_id, action_description, to_screen_id FROM {self.TRANSITIONS_TABLE}"
        result = self._execute_sql(sql, fetch_all=True, commit=False)
        return result if isinstance(result, list) else []

    def initialize_db_for_fresh_run(self) -> bool:
        logging.warning("⚠️ Clearing Screens, Simplified Transitions, and Steps Log for a fresh run...")
        try:
            self._execute_sql(f"DELETE FROM {self.TRANSITIONS_TABLE};", commit=True)
            self._execute_sql(f"DELETE FROM steps_log;", commit=True)
            self._execute_sql(f"DELETE FROM {self.SCREENS_TABLE};", commit=True)
            self._execute_sql(f"DELETE FROM sqlite_sequence WHERE name='{self.SCREENS_TABLE}';", commit=True)
            self._execute_sql(f"DELETE FROM sqlite_sequence WHERE name='{self.TRANSITIONS_TABLE}';", commit=True)
            self._execute_sql(f"DELETE FROM sqlite_sequence WHERE name='steps_log';", commit=True)
            logging.debug("Screens, Transitions, and Steps Log tables cleared successfully.")
            return True
        except Exception as e:
            logging.error(f"🔴 Failed to clear tables for fresh run: {e}", exc_info=True)
            return False
            
    def update_run_meta(self, run_id: int, meta_json: str) -> Optional[int]:
        """
        Insert or update metadata for a run (used for storing MobSF analysis results, etc.)
        
        Args:
            run_id: The run ID to update
            meta_json: JSON string containing metadata
            
        Returns:
            ID of the inserted metadata record, or None if it failed
        """
        sql = "INSERT INTO run_meta (run_id, meta_json) VALUES (?, ?)"
        params = (run_id, meta_json)
        meta_id = self._execute_sql(sql, params, commit=True)
        return meta_id if isinstance(meta_id, int) else None
        
    def get_run_meta(self, run_id: int) -> Optional[str]:
        """
        Get the most recent metadata for a run
        
        Args:
            run_id: The run ID to query
            
        Returns:
            The JSON metadata string, or None if not found
        """
        sql = "SELECT meta_json FROM run_meta WHERE run_id = ? ORDER BY timestamp DESC LIMIT 1"
        result = self._execute_sql(sql, (run_id,), fetch_one=True, commit=False)
        return result[0] if result else None