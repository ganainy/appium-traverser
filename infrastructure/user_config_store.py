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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crawler_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                sort_order INTEGER
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crawler_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                template TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                sort_order INTEGER
            );
        """)
        
        # Initialize default prompts on first launch
        self.initialize_default_prompts_if_empty()
        
        # Initialize default focus areas on first launch
        self.initialize_default_focus_areas_if_empty()

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

    def is_first_launch(self) -> bool:
        """Check if this is the first launch by checking if user_preferences table is empty.
        
        Returns:
            True if user_preferences table is empty (first launch), False otherwise
        """
        conn = self._ensure_conn()
        cur = conn.execute("SELECT COUNT(*) FROM user_preferences")
        count = cur.fetchone()[0]
        return count == 0

    def _filter_simple_defaults(self, defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Filter defaults to only include simple types (int, str, bool, float).
        
        Excludes:
        - dict, list, and None values
        - Path templates with placeholders (e.g., "{session_dir}")
        - ACTION_DESC_* constants (documentation strings, not config values)
        - App-specific hardcoded values (APP_PACKAGE, APP_ACTIVITY)
        
        Args:
            defaults: Dictionary of all default values
            
        Returns:
            Dictionary containing only simple type defaults that should be stored
        """
        simple_defaults: Dict[str, Any] = {}
        
        # Keys to exclude (documentation or app-specific)
        excluded_keys = {
            'APP_PACKAGE',  # App-specific, should be set per project
            'APP_ACTIVITY',  # App-specific, should be set per project
        }
        
        for key, value in defaults.items():
            # Skip excluded keys
            if key in excluded_keys:
                continue
            
            # Skip ACTION_DESC_* constants (documentation strings)
            if key.startswith('ACTION_DESC_'):
                continue
            
            # Only include simple types: int, str, bool, float
            if not isinstance(value, (int, str, bool, float)):
                continue
            
            # Exclude path templates with placeholders (they're resolved dynamically)
            if isinstance(value, str) and '{' in value:
                continue
            
            simple_defaults[key] = value
        
        return simple_defaults

    def initialize_simple_defaults(self, defaults: Dict[str, Any]) -> None:
        """Initialize SQLite with simple default values on first launch only.
        
        Filters defaults to only simple types (int, str, bool, float) and
        populates the user_preferences table if it's empty.
        
        Args:
            defaults: Dictionary of all default values from module constants
        """
        if not self.is_first_launch():
            logging.debug("Not first launch, skipping default initialization")
            return
        
        simple_defaults = self._filter_simple_defaults(defaults)
        if not simple_defaults:
            logging.debug("No simple defaults to initialize")
            return
        
        logging.info(f"First launch detected. Initializing {len(simple_defaults)} simple default values in SQLite")
        self.initialize_defaults(simple_defaults)

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
        """Clear stored preferences, focus areas, crawler actions, and crawler prompts, then reapply defaults."""
        conn = self._ensure_conn()

        try:
            # Clear all config-related tables
            conn.execute("DELETE FROM user_preferences")
            
            # Clear focus areas (if table exists)
            try:
                conn.execute("DELETE FROM focus_areas")
            except sqlite3.OperationalError:
                logging.debug("focus_areas table missing during reset; skipping deletion")
            
            # Clear crawler actions (if table exists)
            try:
                conn.execute("DELETE FROM crawler_actions")
            except sqlite3.OperationalError:
                logging.debug("crawler_actions table missing during reset; skipping deletion")
            
            # Clear crawler prompts (if table exists)
            try:
                conn.execute("DELETE FROM crawler_prompts")
            except sqlite3.OperationalError:
                logging.debug("crawler_prompts table missing during reset; skipping deletion")
            
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
    
    # Crawler actions CRUD methods
    def initialize_default_actions(self, default_actions: Dict[str, str]) -> None:
        """Initialize default actions in the database on first launch.
        
        Args:
            default_actions: Dictionary mapping action names to descriptions
        """
        conn = self._ensure_conn()
        
        # Check if any actions exist
        cur = conn.execute("SELECT COUNT(*) FROM crawler_actions")
        count = cur.fetchone()[0]
        
        # Only initialize if table is empty (first launch)
        if count == 0:
            logging.info(f"Initializing {len(default_actions)} default actions in database...")
            from datetime import datetime
            now = datetime.now().isoformat()
            
            for name, description in default_actions.items():
                try:
                    conn.execute("""
                        INSERT INTO crawler_actions (name, description, created_at, updated_at, enabled, sort_order)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (name, description, now, now, True, 0))
                    logging.debug(f"Initialized default action: {name}")
                except sqlite3.IntegrityError:
                    # Action already exists (shouldn't happen on first launch, but handle gracefully)
                    logging.debug(f"Action '{name}' already exists, skipping")
                except Exception as e:
                    logging.error(f"Failed to initialize action '{name}': {e}")
            
            conn.commit()
            logging.info("Default actions initialization complete")
    
    def get_crawler_actions_full(self) -> List[Dict[str, Any]]:
        """Get all crawler actions with full model (enabled and disabled).
        
        Returns:
            List of action dictionaries with full model
        """
        conn = self._ensure_conn()
        cur = conn.execute("""
            SELECT id, name, description, created_at, updated_at, enabled, sort_order 
            FROM crawler_actions 
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
                "sort_order": row[6] or 0,
            }
            for row in cur.fetchall()
        ]
    
    def add_crawler_action_full(self, name: str, description: Optional[str] = None,
                                created_at: Optional[str] = None,
                                updated_at: Optional[str] = None) -> Dict[str, Any]:
        """Add a new crawler action.
        
        Args:
            name: Action name (must be unique)
            description: Optional description
            created_at: Optional creation timestamp (ISO format)
            updated_at: Optional update timestamp (ISO format)
            
        Returns:
            Dict representing the new action
            
        Raises:
            ValueError if name is not unique
        """
        from datetime import datetime, UTC
        
        conn = self._ensure_conn()
        
        # Check for duplicates
        cur = conn.execute("SELECT id FROM crawler_actions WHERE name = ?", (name,))
        if cur.fetchone():
            raise ValueError("Action name must be unique.")
        
        # Get max sort_order
        cur = conn.execute("SELECT MAX(sort_order) FROM crawler_actions")
        max_order = cur.fetchone()[0] or 0
        
        # Create new action
        now = datetime.now(UTC).isoformat()
        try:
            cur = conn.execute("""
                INSERT INTO crawler_actions (name, description, created_at, updated_at, enabled, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, description or "", created_at or now, updated_at or now, True, max_order + 1))
            conn.commit()
            action_id = cur.lastrowid
            
            return {
                "id": action_id,
                "name": name,
                "description": description or "",
                "created_at": created_at or now,
                "updated_at": updated_at or now,
                "enabled": True,
                "sort_order": max_order + 1,
            }
        except sqlite3.IntegrityError:
            raise ValueError("Action name must be unique.")
    
    def update_crawler_action_full(self, action_id: int, name: Optional[str] = None,
                                   description: Optional[str] = None,
                                   enabled: Optional[bool] = None) -> Dict[str, Any]:
        """Update a crawler action by id.
        
        Args:
            action_id: Action ID
            name: New name (optional, must be unique if provided)
            description: New description (optional)
            enabled: New enabled state (optional)
            
        Returns:
            Dict representing the updated action
            
        Raises:
            ValueError if not found or name not unique
        """
        from datetime import datetime, UTC
        
        conn = self._ensure_conn()
        
        # Check if action exists
        cur = conn.execute("SELECT id FROM crawler_actions WHERE id = ?", (action_id,))
        if not cur.fetchone():
            raise ValueError("Action not found.")
        
        # Check for duplicate name if changing name
        if name:
            cur = conn.execute("SELECT id FROM crawler_actions WHERE name = ? AND id != ?", (name, action_id))
            if cur.fetchone():
                raise ValueError("Action name must be unique.")
        
        # Build update query
        updates = []
        params = []
        if name:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(enabled)
        updates.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(action_id)
        
        conn.execute(
            f"UPDATE crawler_actions SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        
        # Return the updated action
        cur = conn.execute("""
            SELECT id, name, description, created_at, updated_at, enabled, sort_order 
            FROM crawler_actions 
            WHERE id = ?
        """, (action_id,))
        row = cur.fetchone()
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2] or "",
            "created_at": row[3],
            "updated_at": row[4],
            "enabled": bool(row[5]),
            "sort_order": row[6] or 0,
        }
    
    def remove_crawler_action_full(self, action_id: int) -> None:
        """Remove a crawler action by id.
        
        Args:
            action_id: Action ID
            
        Raises:
            ValueError if not found
        """
        conn = self._ensure_conn()
        cur = conn.execute("SELECT id FROM crawler_actions WHERE id = ?", (action_id,))
        if not cur.fetchone():
            raise ValueError("Action not found.")
        
        conn.execute("DELETE FROM crawler_actions WHERE id = ?", (action_id,))
        conn.commit()
    
    # Crawler prompts CRUD methods
    def get_crawler_prompts_full(self) -> List[Dict[str, Any]]:
        """Get all crawler prompts with full model.
        
        Returns:
            List of prompt dictionaries with full model
        """
        conn = self._ensure_conn()
        cur = conn.execute("""
            SELECT id, name, template, created_at, updated_at, enabled, sort_order 
            FROM crawler_prompts 
            WHERE enabled = 1
            ORDER BY sort_order ASC, id ASC
        """)
        return [
            {
                "id": row[0],
                "name": row[1],
                "template": row[2] or "",
                "created_at": row[3],
                "updated_at": row[4],
                "enabled": bool(row[5]),
                "sort_order": row[6] or 0,
            }
            for row in cur.fetchall()
        ]
    
    def get_crawler_prompt_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a crawler prompt by name.
        
        Args:
            name: Prompt name (e.g., "ACTION_DECISION_PROMPT")
            
        Returns:
            Dict representing the prompt or None if not found
        """
        conn = self._ensure_conn()
        cur = conn.execute("""
            SELECT id, name, template, created_at, updated_at, enabled, sort_order 
            FROM crawler_prompts 
            WHERE name = ? AND enabled = 1
        """, (name,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "template": row[2] or "",
            "created_at": row[3],
            "updated_at": row[4],
            "enabled": bool(row[5]),
            "sort_order": row[6] or 0,
        }
    
    def add_crawler_prompt_full(self, name: str, template: str,
                                created_at: Optional[str] = None,
                                updated_at: Optional[str] = None) -> Dict[str, Any]:
        """Add a new crawler prompt.
        
        Args:
            name: Prompt name (must be unique, e.g., "ACTION_DECISION_PROMPT")
            template: Prompt template text
            created_at: Optional creation timestamp (ISO format)
            updated_at: Optional update timestamp (ISO format)
            
        Returns:
            Dict representing the new prompt
            
        Raises:
            ValueError if name is not unique
        """
        from datetime import datetime, UTC
        
        conn = self._ensure_conn()
        
        # Check for duplicates
        cur = conn.execute("SELECT id FROM crawler_prompts WHERE name = ?", (name,))
        if cur.fetchone():
            raise ValueError("Prompt name must be unique.")
        
        # Get max sort_order
        cur = conn.execute("SELECT MAX(sort_order) FROM crawler_prompts")
        max_order = cur.fetchone()[0] or 0
        
        # Create new prompt
        now = datetime.now(UTC).isoformat()
        try:
            cur = conn.execute("""
                INSERT INTO crawler_prompts (name, template, created_at, updated_at, enabled, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, template, created_at or now, updated_at or now, True, max_order + 1))
            conn.commit()
            prompt_id = cur.lastrowid
            
            return {
                "id": prompt_id,
                "name": name,
                "template": template,
                "created_at": created_at or now,
                "updated_at": updated_at or now,
                "enabled": True,
                "sort_order": max_order + 1,
            }
        except sqlite3.IntegrityError:
            raise ValueError("Prompt name must be unique.")
    
    def update_crawler_prompt_full(self, prompt_id: int, name: Optional[str] = None,
                                   template: Optional[str] = None,
                                   enabled: Optional[bool] = None) -> Dict[str, Any]:
        """Update a crawler prompt by id.
        
        Args:
            prompt_id: Prompt ID
            name: New name (optional, must be unique if provided)
            template: New template text (optional)
            enabled: New enabled state (optional)
            
        Returns:
            Dict representing the updated prompt
            
        Raises:
            ValueError if not found or name not unique
        """
        from datetime import datetime, UTC
        
        conn = self._ensure_conn()
        
        # Check if prompt exists
        cur = conn.execute("SELECT id FROM crawler_prompts WHERE id = ?", (prompt_id,))
        if not cur.fetchone():
            raise ValueError("Prompt not found.")
        
        # Check for duplicate name if changing name
        if name:
            cur = conn.execute("SELECT id FROM crawler_prompts WHERE name = ? AND id != ?", (name, prompt_id))
            if cur.fetchone():
                raise ValueError("Prompt name must be unique.")
        
        # Build update query
        updates = []
        params = []
        if name:
            updates.append("name = ?")
            params.append(name)
        if template is not None:
            updates.append("template = ?")
            params.append(template)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(enabled)
        updates.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(prompt_id)
        
        conn.execute(
            f"UPDATE crawler_prompts SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        
        # Return the updated prompt
        cur = conn.execute("""
            SELECT id, name, template, created_at, updated_at, enabled, sort_order 
            FROM crawler_prompts 
            WHERE id = ?
        """, (prompt_id,))
        row = cur.fetchone()
        return {
            "id": row[0],
            "name": row[1],
            "template": row[2] or "",
            "created_at": row[3],
            "updated_at": row[4],
            "enabled": bool(row[5]),
            "sort_order": row[6] or 0,
        }
    
    def remove_crawler_prompt_full(self, prompt_id: int) -> None:
        """Remove a crawler prompt by id.
        
        Args:
            prompt_id: Prompt ID
            
        Raises:
            ValueError if not found
        """
        conn = self._ensure_conn()
        cur = conn.execute("SELECT id FROM crawler_prompts WHERE id = ?", (prompt_id,))
        if not cur.fetchone():
            raise ValueError("Prompt not found.")
        
        conn.execute("DELETE FROM crawler_prompts WHERE id = ?", (prompt_id,))
        conn.commit()
    
    def initialize_default_prompts_if_empty(self) -> None:
        """Initialize default prompts from domain.prompts on first launch.
        
        Checks if crawler_prompts table is empty, and if so, populates it
        with default prompts from domain.prompts module. This makes SQLite
        the single source of truth after initialization.
        """
        conn = self._ensure_conn()
        
        # Check if any prompts exist
        cur = conn.execute("SELECT COUNT(*) FROM crawler_prompts")
        count = cur.fetchone()[0]
        
        # Only initialize if table is empty (first launch)
        if count == 0:
            try:
                # Import default prompts from domain.prompts
                from domain import prompts
                
                default_prompts = {
                    "ACTION_DECISION_PROMPT": prompts.ACTION_DECISION_SYSTEM_PROMPT,
                }
                
                logging.info(f"Initializing {len(default_prompts)} default prompts in database...")
                
                for name, template in default_prompts.items():
                    try:
                        self.add_crawler_prompt_full(name, template)
                        logging.debug(f"Initialized default prompt: {name}")
                    except sqlite3.IntegrityError:
                        # Prompt already exists (shouldn't happen on first launch, but handle gracefully)
                        logging.debug(f"Prompt '{name}' already exists, skipping")
                    except Exception as e:
                        logging.error(f"Failed to initialize prompt '{name}': {e}")
                
                logging.info("Default prompts initialization complete")
            except ImportError as e:
                logging.error(f"Failed to import domain.prompts: {e}")
            except Exception as e:
                logging.error(f"Failed to initialize default prompts: {e}")
    
    def initialize_default_focus_areas_if_empty(self) -> None:
        """Initialize default focus area on first launch.
        
        Checks if focus_areas table is empty, and if so, creates a default
        focus area for privacy policies and personally identifiable data.
        """
        conn = self._ensure_conn()
        
        # Check if any focus areas exist
        cur = conn.execute("SELECT COUNT(*) FROM focus_areas")
        count = cur.fetchone()[0]
        
        # Only initialize if table is empty (first launch)
        if count == 0:
            try:
                default_name = "Privacy Policies & Personal Data"
                default_description = (
                    "Focus on privacy policies, terms of service, and areas of code "
                    "that interact with personally identifiable data (personen bezogene Daten). "
                    "This includes data collection notices, consent toggles, permission requests, "
                    "privacy settings, account settings, data usage information, and any UI elements "
                    "related to user data handling, storage, or sharing."
                )
                
                logging.info("Initializing default focus area in database...")
                
                try:
                    self.add_focus_area_full(
                        name=default_name,
                        description=default_description
                    )
                    logging.info(f"Initialized default focus area: {default_name}")
                except sqlite3.IntegrityError:
                    # Focus area already exists (shouldn't happen on first launch, but handle gracefully)
                    logging.debug(f"Focus area '{default_name}' already exists, skipping")
                except Exception as e:
                    logging.error(f"Failed to initialize default focus area: {e}")
                
                logging.info("Default focus area initialization complete")
            except Exception as e:
                logging.error(f"Failed to initialize default focus areas: {e}")
    
    