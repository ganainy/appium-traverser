import sqlite3
import os
from typing import Any, List, Dict, Optional
from platformdirs import user_config_dir

# Module-level constants for default configuration
DEFAULT_APP_NAME = "traverser"
DEFAULT_APP_AUTHOR = "traverser"
DEFAULT_DB_FILENAME = "config.db"

class UserConfigStore:
    # Type System
    _TYPE_STR = 'str'
    _TYPE_INT = 'int'
    _TYPE_FLOAT = 'float'
    _TYPE_BOOL = 'bool'
    _SUPPORTED_TYPES = (_TYPE_STR, _TYPE_INT, _TYPE_FLOAT, _TYPE_BOOL)
    _BOOL_TRUE_STR = 'true'
    _BOOL_FALSE_STR = 'false'
    
    # Schema: user_preferences
    TABLE_PREFS = 'user_preferences'
    PREFS_KEY = 'key'
    PREFS_VALUE = 'value'
    PREFS_TYPE = 'type'
    PREFS_UPDATED = 'updated_at'
    
    # Schema: focus_areas
    TABLE_FOCUS = 'focus_areas'
    FOCUS_ID = 'id'
    FOCUS_AREA = 'area'
    FOCUS_ENABLED = 'enabled'
    FOCUS_ORDER = 'sort_order'
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        app_name: str = DEFAULT_APP_NAME,
        app_author: str = DEFAULT_APP_AUTHOR,
        db_filename: str = DEFAULT_DB_FILENAME
    ) -> None:
        if db_path is None:
            config_dir = user_config_dir(app_name, app_author)
            os.makedirs(config_dir, exist_ok=True)
            db_path = os.path.join(config_dir, db_filename)
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self):
        if self._conn is None:
            raise RuntimeError("Database connection is not initialized")
        conn = self._conn
        conn.execute("PRAGMA journal_mode=WAL;")
        
        # Dynamically build the CHECK constraint for supported types
        supported_types_sql = ', '.join([f"'{t}'" for t in self._SUPPORTED_TYPES])
        
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_PREFS} (
                {self.PREFS_KEY} TEXT PRIMARY KEY,
                {self.PREFS_VALUE} TEXT NOT NULL,
                {self.PREFS_TYPE} TEXT NOT NULL CHECK ({self.PREFS_TYPE} IN ({supported_types_sql})),
                {self.PREFS_UPDATED} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_FOCUS} (
                {self.FOCUS_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self.FOCUS_AREA} TEXT UNIQUE NOT NULL,
                {self.FOCUS_ENABLED} BOOLEAN DEFAULT TRUE,
                {self.FOCUS_ORDER} INTEGER
            );
        """)

    def get(self, key: str, default: Any = None) -> Any:
        if self._conn is None:
            raise RuntimeError("Database connection is not initialized")
        cur = self._conn.execute(f"SELECT {self.PREFS_VALUE}, {self.PREFS_TYPE} FROM {self.TABLE_PREFS} WHERE {self.PREFS_KEY} = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return default
        value, type_ = row
        return self._coerce_type(value, type_)

    def set(self, key: str, value: Any, type_: Optional[str] = None) -> None:
        if self._conn is None:
            raise RuntimeError("Database connection is not initialized")
        if type_ is None:
            type_ = self._infer_type(value)
        value_str = self._to_storage_str(value, type_)
        self._conn.execute(
            f"REPLACE INTO {self.TABLE_PREFS} ({self.PREFS_KEY}, {self.PREFS_VALUE}, {self.PREFS_TYPE}, {self.PREFS_UPDATED}) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (key, value_str, type_)
        )
        self._conn.commit()

    def get_focus_areas(self) -> List[Dict[str, Any]]:
        if self._conn is None:
            raise RuntimeError("Database connection is not initialized")
        cur = self._conn.execute(f"SELECT {self.FOCUS_AREA}, {self.FOCUS_ENABLED} FROM {self.TABLE_FOCUS} ORDER BY {self.FOCUS_ORDER} ASC, {self.FOCUS_ID} ASC")
        return [{"area": area, "enabled": bool(enabled)} for area, enabled in cur.fetchall()]

    def add_focus_area(self, area: str) -> None:
        if self._conn is None:
            raise RuntimeError("Database connection is not initialized")
        cur = self._conn.execute(f"SELECT MAX({self.FOCUS_ORDER}) FROM {self.TABLE_FOCUS}")
        max_order = cur.fetchone()[0] or 0
        try:
            self._conn.execute(
                f"INSERT INTO {self.TABLE_FOCUS} ({self.FOCUS_AREA}, {self.FOCUS_ENABLED}, {self.FOCUS_ORDER}) VALUES (?, ?, ?)",
                (area, True, max_order + 1)
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Focus area '{area}' already exists.")

    def remove_focus_area(self, area: str) -> None:
        if self._conn is None:
            raise RuntimeError("Database connection is not initialized")
        self._conn.execute(f"DELETE FROM {self.TABLE_FOCUS} WHERE {self.FOCUS_AREA} = ?", (area,))
        self._conn.commit()
    def close(self):
        if hasattr(self, '_conn') and self._conn:
            self._conn.close()
            self._conn = None

    def _coerce_type(self, value: str, type_: str) -> Any:
        if type_ == self._TYPE_INT:
            return int(value)
        elif type_ == self._TYPE_FLOAT:
            return float(value)
        elif type_ == self._TYPE_BOOL:
            return value.lower() == self._BOOL_TRUE_STR
        return value

    def _infer_type(self, value: Any) -> str:
        if isinstance(value, bool):
            return self._TYPE_BOOL
        elif isinstance(value, int):
            return self._TYPE_INT
        elif isinstance(value, float):
            return self._TYPE_FLOAT
        return self._TYPE_STR

    def _to_storage_str(self, value: Any, type_: str) -> str:
        if type_ == self._TYPE_BOOL:
            return self._BOOL_TRUE_STR if value else self._BOOL_FALSE_STR
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
