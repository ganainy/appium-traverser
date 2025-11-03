#!/usr/bin/env python3
"""
CommandResult class for standardizing service method return values.
"""

from typing import Any, Dict, Optional, Tuple


class CommandResult:
    """Standardized result object for service operations."""
    
    def __init__(self, success: bool, data: Optional[Any] = None, error: Optional[str] = None):
        """
        Initialize a CommandResult.
        
        Args:
            success: Whether the operation was successful
            data: The data returned by the operation (if successful)
            error: Error message (if unsuccessful)
        """
        self.success = success
        self.data = data
        self.error = error
    
    def to_tuple(self) -> Tuple[bool, Any]:
        """
        Convert to tuple format for backward compatibility.
        
        Returns:
            Tuple of (success, data)
        """
        return (self.success, self.data)
    
    @classmethod
    def success_result(cls, data: Any) -> "CommandResult":
        """Create a successful result with data."""
        return cls(success=True, data=data)
    
    @classmethod
    def error_result(cls, error: str) -> "CommandResult":
        """Create an error result with an error message."""
        return cls(success=False, error=error)