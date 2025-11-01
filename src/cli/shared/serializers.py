"""
Serialization utilities for CLI operations.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class JSONSerializer:
    """Utility class for JSON serialization with error handling."""
    
    @staticmethod
    def load(file_path: Union[str, Path]) -> Optional[Any]:
        """
        Load JSON data from file with error handling.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Parsed JSON data or None if error occurred
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logging.debug(f"File not found: {file_path}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error in {file_path}: {e}")
            return None
        except Exception as e:
            logging.error(f"Error loading {file_path}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def save(data: Any, file_path: Union[str, Path], indent: int = 2) -> bool:
        """
        Save data to JSON file with error handling.
        
        Args:
            data: Data to serialize
            file_path: Output file path
            indent: JSON indentation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"Error saving to {file_path}: {e}", exc_info=True)
            return False
    
    @staticmethod
    def validate_structure(data: Any, required_keys: List[str]) -> bool:
        """
        Validate that data contains required keys.
        
        Args:
            data: Data to validate
            required_keys: List of required keys
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(data, dict):
            return False
        
        for key in required_keys:
            if key not in data:
                return False
        
        return True
    
    @staticmethod
    def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two dictionaries with override taking precedence.
        
        Args:
            base: Base dictionary
            override: Override dictionary
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        result.update(override)
        return result


class CacheManager:
    """Utility class for managing cache files."""
    
    def __init__(self, cache_dir: Union[str, Path]):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_path(self, filename: str) -> Path:
        """
        Get full path for a cache file.
        
        Args:
            filename: Cache filename
            
        Returns:
            Full path to cache file
        """
        return self.cache_dir / filename
    
    def load_cache(self, filename: str) -> Optional[Any]:
        """
        Load data from cache file.
        
        Args:
            filename: Cache filename
            
        Returns:
            Cached data or None if not found/invalid
        """
        cache_path = self.get_cache_path(filename)
        return JSONSerializer.load(cache_path)
    
    def save_cache(self, filename: str, data: Any) -> bool:
        """
        Save data to cache file.
        
        Args:
            filename: Cache filename
            data: Data to cache
            
        Returns:
            True if successful, False otherwise
        """
        cache_path = self.get_cache_path(filename)
        return JSONSerializer.save(data, cache_path)
    
    def clear_cache(self, pattern: str = "*") -> int:
        """
        Clear cache files matching pattern.
        
        Args:
            pattern: Glob pattern for files to delete
            
        Returns:
            Number of files deleted
        """
        count = 0
        for cache_file in self.cache_dir.glob(pattern):
            try:
                cache_file.unlink()
                count += 1
            except Exception as e:
                logging.warning(f"Failed to delete cache file {cache_file}: {e}")
        return count
