#!/usr/bin/env python3
"""
Configuration service for CLI operations.
"""

import logging
from typing import List

from cli.shared.context import CLIContext


class ConfigService:
    """Service for managing configuration settings."""
    
    def __init__(self, context: CLIContext):
        self.context = context
        self.logger = logging.getLogger(__name__)
    
    def set_and_save_from_pairs(self, kv_pairs: List[str]) -> bool:
        """
        Set and save configuration values from a list of KEY=VALUE pairs.
        
        Args:
            kv_pairs: List of key=value pairs
            
        Returns:
            True if all pairs were processed successfully, False otherwise
        """
        return self.context.config.set_and_save_from_pairs(kv_pairs, self.context.services.get('telemetry_service'))