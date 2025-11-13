#!/usr/bin/env python3
"""
Crawler actions service for managing available crawler actions.
"""

import logging
from typing import Dict, List, Optional, Tuple

from cli.constants import keys as KEYS
from cli.constants import messages as MSG
from cli.shared.context import CLIContext

_MAX_ACTIONS = 50

class CrawlerActionsService:
    """Service for managing crawler actions using UserConfigStore."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.config = context.config
        self.logger = logging.getLogger(__name__)
        # Get UserConfigStore from config
        self._user_store = self.config._user_store
    
    def get_actions(self) -> List[Dict]:
        """Get current actions from storage.
        
        Returns:
            List of action dictionaries
        """
        try:
            actions = self._user_store.get_crawler_actions_full()
            return actions if isinstance(actions, list) else []
        except Exception as e:
            self.logger.error(f"Failed to load actions from storage: {e}")
            return []
    
    def get_actions_dict(self) -> Dict[str, str]:
        """Get actions as a dictionary mapping name to description.
        
        Returns:
            Dictionary of {action_name: description}
        """
        actions = self.get_actions()
        return {action["name"]: action["description"] for action in actions}
    
    def _find_action_id(self, id_or_name: str) -> Optional[int]:
        """Find action ID by ID or name.
        
        Args:
            id_or_name: Action ID or name
            
        Returns:
            Action ID or None if not found
        """
        actions = self.get_actions()
        try:
            idx = int(id_or_name) - 1
            if 0 <= idx < len(actions):
                return actions[idx]["id"]
        except ValueError:
            name_lower = id_or_name.strip().lower()
            for action in actions:
                if name_lower == action["name"].lower():
                    return action["id"]
        return None
    
    def add_action(
        self,
        name: str,
        description: str = "",
        enabled: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Add a new action.
        
        Args:
            name: Action name
            description: Action description
            enabled: Whether the action is enabled
            
        Returns:
            Tuple of (success, message)
        """
        try:
            actions = self.get_actions()
            if len(actions) >= _MAX_ACTIONS:
                error_msg = f"Maximum of {_MAX_ACTIONS} actions allowed."
                return False, error_msg
            
            # Use UserConfigStore to add action
            self._user_store.add_crawler_action_full(name, description)
            success_msg = f"Action '{name}' added successfully."
            return True, success_msg
        except ValueError as e:
            # Handle validation errors
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error adding action: {e}"
            self.logger.error(f"Failed to add action: {e}")
            return False, error_msg
    
    def edit_action(
        self,
        id_or_name: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> Tuple[bool, Optional[str]]:
        """Edit an existing action.
        
        Args:
            id_or_name: Action ID or name
            name: New name (optional)
            description: New description (optional)
            enabled: New enabled state (optional)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Convert id_or_name to integer ID
            action_id = int(id_or_name) if id_or_name.isdigit() else None
            if action_id is None:
                # Try to find by name
                action_id = self._find_action_id(id_or_name)
                if action_id is None:
                    error_msg = f"Action '{id_or_name}' not found."
                    return False, error_msg
            
            # Use UserConfigStore to update action
            self._user_store.update_crawler_action_full(action_id, name, description, enabled)
            success_msg = f"Action '{id_or_name}' updated successfully."
            return True, success_msg
        except ValueError as e:
            # Handle validation errors
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error updating action: {e}"
            self.logger.error(f"Failed to update action: {e}")
            return False, error_msg
    
    def remove_action(self, id_or_name: str) -> Tuple[bool, Optional[str]]:
        """Remove an action.
        
        Args:
            id_or_name: Action ID or name
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Convert id_or_name to integer ID
            action_id = int(id_or_name) if id_or_name.isdigit() else None
            if action_id is None:
                # Try to find by name
                action_id = self._find_action_id(id_or_name)
                if action_id is None:
                    error_msg = f"Action '{id_or_name}' not found."
                    return False, error_msg
            
            # Use UserConfigStore to remove action
            self._user_store.remove_crawler_action_full(action_id)
            success_msg = f"Action '{id_or_name}' removed successfully."
            return True, success_msg
        except ValueError as e:
            # Handle validation errors
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error removing action: {e}"
            self.logger.error(f"Failed to remove action: {e}")
            return False, error_msg

