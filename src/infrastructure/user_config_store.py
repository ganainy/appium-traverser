import sqlite3
import os
from typing import Any, List, Dict, Optional
from platformdirs import user_config_dir

class UserConfigStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            config_dir = user_config_dir("traverser", "traverser")
            os.makedirs(config_dir, exist_ok=True)
            db_path = os.path.join(config_dir, "config.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('str', 'int', 'float', 'bool')),
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "REPLACE INTO user_preferences (key, value, type, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (key, value_str, type_)
            )

    def get_focus_areas(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT area, enabled FROM focus_areas ORDER BY sort_order ASC, id ASC")
            return [{"area": area, "enabled": bool(enabled)} for area, enabled in cur.fetchall()]

    def add_focus_area(self, area: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT MAX(sort_order) FROM focus_areas")
            max_order = cur.fetchone()[0] or 0
            try:
                conn.execute(
                    "INSERT INTO focus_areas (area, enabled, sort_order) VALUES (?, ?, ?)",
                    (area, True, max_order + 1)
                )
            except sqlite3.IntegrityError:
                raise ValueError(f"Focus area '{area}' already exists.")

    def remove_focus_area(self, area: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM focus_areas WHERE area = ?", (area,))

    def _coerce_type(self, value: str, type_: str) -> Any:
        if type_ == 'int':
            return int(value)
        elif type_ == 'float':
            return float(value)
        elif type_ == 'bool':
            return value.lower() == 'true'
        return value

    def _infer_type(self, value: Any) -> str:
        if isinstance(value, bool):
            return 'bool'
        elif isinstance(value, int):
            return 'int'
        elif isinstance(value, float):
            return 'float'
        return 'str'

    def _to_storage_str(self, value: Any, type_: str) -> str:
        if type_ == 'bool':
            return 'true' if value else 'false'
        return str(value)