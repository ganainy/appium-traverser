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
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                priority INTEGER DEFAULT 0,
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
    
    # Full focus area model methods (using proper SQLite table)
    def get_focus_areas_full(self) -> List[Dict[str, Any]]:
        """Get all focus areas with full model (id, name, description, timestamps).
        
        Returns:
            List of focus area dictionaries with full model
        """
        conn = self._ensure_conn()
        cur = conn.execute("""
            SELECT id, name, description, created_at, updated_at, enabled, priority 
            FROM focus_areas 
            ORDER BY sort_order ASC, id ASC
        """)
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2] or "",
                "created_at": row[3],
                "updated_at": row[4],
                "enabled": bool(row[5]),
                "priority": row[6] or 0,
            }
            for row in cur.fetchall()
        ]
    
    def add_focus_area_full(self, name: str, description: Optional[str] = None, 
                           created_at: Optional[str] = None, 
                           updated_at: Optional[str] = None) -> Dict[str, Any]:
        """Add a new focus area with full model.
        
        Args:
            name: Focus area name (must be unique)
            description: Optional description
            created_at: Optional creation timestamp (ISO format)
            updated_at: Optional update timestamp (ISO format)
            
        Returns:
            Dict representing the new focus area
            
        Raises:
            ValueError if name is not unique
        """
        from datetime import datetime, UTC
        
        conn = self._ensure_conn()
        
        # Check for duplicates
        cur = conn.execute("SELECT id FROM focus_areas WHERE name = ?", (name,))
        if cur.fetchone():
            raise ValueError("Focus area name must be unique.")
        
        # Get max sort_order
        cur = conn.execute("SELECT MAX(sort_order) FROM focus_areas")
        max_order = cur.fetchone()[0] or 0
        
        # Create new focus area
        now = datetime.now(UTC).isoformat()
        try:
            cur = conn.execute("""
                INSERT INTO focus_areas (name, description, created_at, updated_at, enabled, priority, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, description or "", created_at or now, updated_at or now, True, 0, max_order + 1))
            conn.commit()
            area_id = cur.lastrowid
            
            # Return the created area
            return {
                "id": area_id,
                "name": name,
                "description": description or "",
                "created_at": created_at or now,
                "updated_at": updated_at or now,
                "enabled": True,
                "priority": 0,
            }
        except sqlite3.IntegrityError:
            raise ValueError("Focus area name must be unique.")
    
    def update_focus_area_full(self, area_id: int, name: Optional[str] = None, 
                               description: Optional[str] = None) -> Dict[str, Any]:
        """Update a focus area by id.
        
        Args:
            area_id: Focus area ID
            name: New name (optional, must be unique if provided)
            description: New description (optional)
            
        Returns:
            Dict representing the updated focus area
            
        Raises:
            ValueError if not found or name not unique
        """
        from datetime import datetime, UTC
        
        conn = self._ensure_conn()
        
        # Check if area exists
        cur = conn.execute("SELECT id FROM focus_areas WHERE id = ?", (area_id,))
        if not cur.fetchone():
            raise ValueError("Focus area not found.")
        
        # Check for duplicate name if changing name
        if name:
            cur = conn.execute("SELECT id FROM focus_areas WHERE name = ? AND id != ?", (name, area_id))
            if cur.fetchone():
                raise ValueError("Focus area name must be unique.")
        
        # Build update query
        updates = []
        params = []
        if name:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        updates.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(area_id)
        
        conn.execute(
            f"UPDATE focus_areas SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        
        # Return the updated area
        cur = conn.execute("""
            SELECT id, name, description, created_at, updated_at, enabled, priority 
            FROM focus_areas 
            WHERE id = ?
        """, (area_id,))
        row = cur.fetchone()
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2] or "",
            "created_at": row[3],
            "updated_at": row[4],
            "enabled": bool(row[5]),
            "priority": row[6] or 0,
        }
    
    def remove_focus_area_full(self, area_id: int) -> None:
        """Remove a focus area by id.
        
        Args:
            area_id: Focus area ID
            
        Raises:
            ValueError if not found
        """
        conn = self._ensure_conn()
        cur = conn.execute("SELECT id FROM focus_areas WHERE id = ?", (area_id,))
        if not cur.fetchone():
            raise ValueError("Focus area not found.")
        
        conn.execute("DELETE FROM focus_areas WHERE id = ?", (area_id,))
        conn.commit()
    
    