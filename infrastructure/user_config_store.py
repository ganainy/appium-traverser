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
        self._conn: Optional[sqlite3.Connection] = sqlite3.connect(self.db_path)
        self._init_db()

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database connection is not initialized")
        return self._conn

    def _init_db(self):
        conn = self._ensure_conn()
        conn.execute("PRAGMA journal_mode=WAL;")

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
        conn = self._ensure_conn()
        cur = conn.execute("SELECT value, type FROM user_preferences WHERE key = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return default
        value, type_ = row
        return self._coerce_type(value, type_)

    def set(self, key: str, value: Any, type_: Optional[str] = None) -> None:
        if type_ is None:
            type_ = self._infer_type(value)
        value_str = self._to_storage_str(value, type_)
        conn = self._ensure_conn()
        conn.execute(
            "REPLACE INTO user_preferences (key, value, type, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (key, value_str, type_)
        )
        conn.commit()

    def get_focus_areas(self) -> List[Dict[str, Any]]:
        conn = self._ensure_conn()
        cur = conn.execute("SELECT area, enabled FROM focus_areas ORDER BY sort_order ASC, id ASC")
        return [{"area": area, "enabled": bool(enabled)} for area, enabled in cur.fetchall()]

    def add_focus_area(self, area: str) -> None:
        conn = self._ensure_conn()
        cur = conn.execute("SELECT MAX(sort_order) FROM focus_areas")
        max_order = cur.fetchone()[0] or 0
        try:
            conn.execute(
                "INSERT INTO focus_areas (area, enabled, sort_order) VALUES (?, ?, ?)",
                (area, True, max_order + 1)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Focus area '{area}' already exists.")

    def remove_focus_area(self, area: str) -> None:
        conn = self._ensure_conn()
        conn.execute("DELETE FROM focus_areas WHERE area = ?", (area,))
        conn.commit()

    def close(self):
        if hasattr(self, '_conn') and self._conn:
            self._conn.close()
            self._conn = None

    def initialize_defaults(self, defaults: Dict[str, Any]) -> None:
        """Populate missing preference keys using provided defaults."""
        conn = self._ensure_conn()
        if not defaults:
            return

        try:
            cur = conn.execute("SELECT key FROM user_preferences")
            existing_keys = {row[0] for row in cur.fetchall()}

            records: List[tuple] = []
            for key, value in defaults.items():
                if key in existing_keys or value is None:
                    continue
                type_ = self._infer_type(value)
                value_str = self._to_storage_str(value, type_)
                records.append((key, value_str, type_))

            if records:
                conn.executemany(
                    "INSERT INTO user_preferences (key, value, type, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    records,
                )
                conn.commit()
        except sqlite3.Error as exc:
            logging.error(f"Failed to initialize default preferences: {exc}")
            conn.rollback()
            raise

    def reset_preferences(self, defaults: Dict[str, Any]) -> None:
        """Clear stored preferences/focus areas and reapply defaults."""
        conn = self._ensure_conn()

        try:
            conn.execute("DELETE FROM user_preferences")
            try:
                conn.execute("DELETE FROM focus_areas")
            except sqlite3.OperationalError:
                logging.debug("focus_areas table missing during reset; skipping deletion")
            conn.commit()
        except sqlite3.Error as exc:
            logging.error(f"Failed to reset preferences: {exc}")
            conn.rollback()
            raise
        self.initialize_defaults(defaults)

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
    
    