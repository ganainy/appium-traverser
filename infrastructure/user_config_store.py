import sqlite3
import os
import json
import logging
from typing import Any, List, Dict, Optional
from platformdirs import user_config_dir

class UserConfigStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            config_dir = user_config_dir("traverser", "traverser")
            os.makedirs(config_dir, exist_ok=True)
            db_path = os.path.join(config_dir, "config.db")
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self):
        conn = self._conn
        conn.execute("PRAGMA journal_mode=WAL;")
        
        # Check if the table exists and has the old CHECK constraint
        try:
            cur = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='user_preferences'"
            )
            existing_table_sql = cur.fetchone()
            
            if existing_table_sql and "CHECK" in existing_table_sql[0]:
                # Old schema with CHECK constraint detected - need to recreate the table
                try:
                    # Backup existing data
                    conn.execute(
                        "CREATE TABLE user_preferences_backup AS SELECT * FROM user_preferences"
                    )
                    # Drop old table
                    conn.execute("DROP TABLE user_preferences")
                    # Create new table without CHECK constraint
                    conn.execute("""
                        CREATE TABLE user_preferences (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL,
                            type TEXT NOT NULL,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    # Restore data from backup
                    conn.execute(
                        "INSERT INTO user_preferences SELECT * FROM user_preferences_backup"
                    )
                    # Clean up backup
                    conn.execute("DROP TABLE user_preferences_backup")
                    conn.commit()
                    logging.info("Successfully migrated user_preferences table schema")
                except Exception as e:
                    logging.error(f"Error migrating schema: {e}")
                    conn.rollback()
        except Exception as e:
            logging.debug(f"Could not check for schema migration: {e}")
        
        # Create table if it doesn't exist (for fresh databases)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                type TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS focus_areas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area TEXT UNIQUE NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                sort_order INTEGER
            );
        """)

    def get(self, key: str, default: Any = None) -> Any:
        cur = self._conn.execute("SELECT value, type FROM user_preferences WHERE key = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return default
        value, type_ = row
        return self._coerce_type(value, type_)

    def set(self, key: str, value: Any, type_: Optional[str] = None) -> None:
        if type_ is None:
            type_ = self._infer_type(value)
        value_str = self._to_storage_str(value, type_)
        self._conn.execute(
            "REPLACE INTO user_preferences (key, value, type, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (key, value_str, type_)
        )
        self._conn.commit()

    def get_focus_areas(self) -> List[Dict[str, Any]]:
        cur = self._conn.execute("SELECT area, enabled FROM focus_areas ORDER BY sort_order ASC, id ASC")
        return [{"area": area, "enabled": bool(enabled)} for area, enabled in cur.fetchall()]

    def add_focus_area(self, area: str) -> None:
        cur = self._conn.execute("SELECT MAX(sort_order) FROM focus_areas")
        max_order = cur.fetchone()[0] or 0
        try:
            self._conn.execute(
                "INSERT INTO focus_areas (area, enabled, sort_order) VALUES (?, ?, ?)",
                (area, True, max_order + 1)
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Focus area '{area}' already exists.")

    def remove_focus_area(self, area: str) -> None:
        self._conn.execute("DELETE FROM focus_areas WHERE area = ?", (area,))
        self._conn.commit()
    def close(self):
        if hasattr(self, '_conn') and self._conn:
            self._conn.close()
            self._conn = None

    def _coerce_type(self, value: str, type_: str) -> Any:
        if type_ == 'int':
            return int(value)
        elif type_ == 'float':
            return float(value)
        elif type_ == 'bool':
            return value.lower() == 'true'
        elif type_ == 'json':
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value
        return value

    def _infer_type(self, value: Any) -> str:
        if isinstance(value, bool):
            return 'bool'
        elif isinstance(value, int):
            return 'int'
        elif isinstance(value, float):
            return 'float'
        elif isinstance(value, (dict, list)):
            return 'json'
        return 'str'

    def _to_storage_str(self, value: Any, type_: str) -> str:
        if type_ == 'bool':
            return 'true' if value else 'false'
        elif type_ == 'json':
            return json.dumps(value)
        return str(value)
    
    
    # Backwards-compatible methods expected by tests and older code
    def set_config(self, key: str, value: Any) -> None:
        """
        Backward-compatible wrapper for legacy API `set_config`.
        Delegates to the newer `set` method which handles type inference.
        """
        self.set(key, value)
    
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Backward-compatible wrapper for legacy API `get_config_value`.
        Delegates to the newer `get` method.
        """
        return self.get(key, default)