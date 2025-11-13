#!/usr/bin/env python3
"""
Crawler prompts service for managing crawler prompt templates.
"""

import logging
from typing import Dict, List, Optional, Tuple

from cli.constants import keys as KEYS
from cli.constants import messages as MSG
from cli.shared.context import CLIContext

_MAX_PROMPTS = 20

class CrawlerPromptsService:
    """Service for managing crawler prompts using UserConfigStore."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.config = context.config
        self.logger = logging.getLogger(__name__)
        # Get UserConfigStore from config
        self._user_store = self.config._user_store
    
    def get_prompts(self) -> List[Dict]:
        """Get current prompts from storage.
        
        Returns:
            List of prompt dictionaries
        """
        try:
            prompts = self._user_store.get_crawler_prompts_full()
            return prompts if isinstance(prompts, list) else []
        except Exception as e:
            self.logger.error(f"Failed to load prompts from storage: {e}")
            return []
    
    def get_prompt_by_name(self, name: str) -> Optional[str]:
        """Get a prompt template by name.
        
        Args:
            name: Prompt name (e.g., "ACTION_DECISION_PROMPT", "SYSTEM_PROMPT_TEMPLATE")
            
        Returns:
            Prompt template string or None if not found
        """
        try:
            prompt = self._user_store.get_crawler_prompt_by_name(name)
            return prompt["template"] if prompt else None
        except Exception as e:
            self.logger.error(f"Failed to get prompt '{name}': {e}")
            return None
    
    def _find_prompt_id(self, id_or_name: str) -> Optional[int]:
        """Find prompt ID by ID or name.
        
        Args:
            id_or_name: Prompt ID or name
            
        Returns:
            Prompt ID or None if not found
        """
        prompts = self.get_prompts()
        try:
            idx = int(id_or_name) - 1
            if 0 <= idx < len(prompts):
                return prompts[idx]["id"]
        except ValueError:
            name_lower = id_or_name.strip().lower()
            for prompt in prompts:
                if name_lower == prompt["name"].lower():
                    return prompt["id"]
        return None
    
    def add_prompt(
        self,
        name: str,
        template: str,
        enabled: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Add a new prompt.
        
        Args:
            name: Prompt name (e.g., "ACTION_DECISION_PROMPT")
            template: Prompt template text
            enabled: Whether the prompt is enabled
            
        Returns:
            Tuple of (success, message)
        """
        try:
            prompts = self.get_prompts()
            if len(prompts) >= _MAX_PROMPTS:
                error_msg = f"Maximum of {_MAX_PROMPTS} prompts allowed."
                return False, error_msg
            
            # Use UserConfigStore to add prompt
            self._user_store.add_crawler_prompt_full(name, template)
            success_msg = f"Prompt '{name}' added successfully."
            return True, success_msg
        except ValueError as e:
            # Handle validation errors
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error adding prompt: {e}"
            self.logger.error(f"Failed to add prompt: {e}")
            return False, error_msg
    
    def edit_prompt(
        self,
        id_or_name: str,
        name: Optional[str] = None,
        template: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> Tuple[bool, Optional[str]]:
        """Edit an existing prompt.
        
        Args:
            id_or_name: Prompt ID or name
            name: New name (optional)
            template: New template text (optional)
            enabled: New enabled state (optional)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Convert id_or_name to integer ID
            prompt_id = int(id_or_name) if id_or_name.isdigit() else None
            if prompt_id is None:
                # Try to find by name
                prompt_id = self._find_prompt_id(id_or_name)
                if prompt_id is None:
                    error_msg = f"Prompt '{id_or_name}' not found."
                    return False, error_msg
            
            # Use UserConfigStore to update prompt
            self._user_store.update_crawler_prompt_full(prompt_id, name, template, enabled)
            success_msg = f"Prompt '{id_or_name}' updated successfully."
            return True, success_msg
        except ValueError as e:
            # Handle validation errors
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error updating prompt: {e}"
            self.logger.error(f"Failed to update prompt: {e}")
            return False, error_msg
    
    def remove_prompt(self, id_or_name: str) -> Tuple[bool, Optional[str]]:
        """Remove a prompt.
        
        Args:
            id_or_name: Prompt ID or name
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Convert id_or_name to integer ID
            prompt_id = int(id_or_name) if id_or_name.isdigit() else None
            if prompt_id is None:
                # Try to find by name
                prompt_id = self._find_prompt_id(id_or_name)
                if prompt_id is None:
                    error_msg = f"Prompt '{id_or_name}' not found."
                    return False, error_msg
            
            # Use UserConfigStore to remove prompt
            self._user_store.remove_crawler_prompt_full(prompt_id)
            success_msg = f"Prompt '{id_or_name}' removed successfully."
            return True, success_msg
        except ValueError as e:
            # Handle validation errors
            error_msg = str(e)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error removing prompt: {e}"
            self.logger.error(f"Failed to remove prompt: {e}")
            return False, error_msg

