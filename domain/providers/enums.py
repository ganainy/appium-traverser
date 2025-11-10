"""
Provider enumeration for type-safe provider names.
"""

from enum import Enum


class AIProvider(str, Enum):
    """Enumeration of supported AI providers."""
    
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    
    @classmethod
    def from_string(cls, value: str) -> 'AIProvider':
        """
        Convert a string to an AIProvider enum value.
        
        Args:
            value: String representation of provider name
            
        Returns:
            AIProvider enum value
            
        Raises:
            ValueError: If the provider name is not recognized
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid_providers = [p.value for p in cls]
            raise ValueError(
                f"Invalid provider: {value}. "
                f"Valid providers are: {', '.join(valid_providers)}"
            )
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """
        Check if a string is a valid provider name.
        
        Args:
            value: String to check
            
        Returns:
            True if valid, False otherwise
        """
        try:
            cls.from_string(value)
            return True
        except ValueError:
            return False
    
    @classmethod
    def all_values(cls) -> list[str]:
        """Return all valid provider values as a list."""
        return [p.value for p in cls]
    
    def __str__(self) -> str:
        """Return the string value of the provider."""
        return self.value

