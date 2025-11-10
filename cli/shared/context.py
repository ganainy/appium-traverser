"""
CLI context providing shared dependencies to commands and services.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Determine project root
from utils.paths import find_project_root
_project_root = find_project_root(Path(__file__).resolve().parent)
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from config.app_config import Config
    from utils.utils import LoggerManager
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import required modules: {e}\n")
    sys.exit(1)


class ServiceRegistry:
    """Registry for managing service instances."""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
    
    def register(self, name: str, service: Any) -> None:
        """Register a service instance."""
        self._services[name] = service
    
    def get(self, name: str) -> Any:
        """Get a service instance."""
        return self._services.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._services


class CLIContext:
    """
    Shared context for CLI operations.
    
    Provides access to configuration, logging, and shared utilities
    across all CLI commands and services.
    """
    
    def __init__(self, verbose: bool = False):
        """
        Initialize CLI context.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self._config: Optional[Config] = None
        self._logger_manager: Optional[LoggerManager] = None
        self._services = ServiceRegistry()
        self._setup_logging(verbose)
        self._initialize_config()
    
    def _setup_logging(self, verbose: bool) -> None:
        """Setup logging configuration."""
        log_level = "DEBUG" if verbose else "WARNING"
        
        # Clear existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # Configure basic logging first
        logging.basicConfig(
            level=log_level,
            format="[%(levelname)s] %(asctime)s %(module)s: %(message)s",
            datefmt="%H:%M:%S",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        
        # Will be reconfigured after config is loaded
        self._log_level = log_level
    
    def _initialize_config(self) -> None:
        """Initialize configuration and final logging setup."""
        # Find project root using marker files
        api_dir = find_project_root(Path(__file__).resolve().parent)
        logging.debug(f"API directory: {api_dir}")
        
        try:
            self._config = Config()
            
            # Setup final logging with file output
            self._setup_final_logging()
            
        except Exception as e:
            logging.critical(f"Failed to initialize Config: {e}", exc_info=True)
            sys.exit(100)
    
    def _setup_final_logging(self) -> None:
        """Setup final logging with file output."""
        if not self._config:
            return
            
        # Clear handlers again
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # Create logger manager
        self._logger_manager = LoggerManager()
        
        # Setup log file path
        log_file_base = Path(self._config.OUTPUT_DATA_DIR or str(_project_root))
        log_file_path = log_file_base / "logs" / "cli" / f"cli_{self._config.LOG_FILE_NAME}"
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure final logging
        self._logger_manager.setup_logging(
            log_level_str=self._log_level,
            log_file=str(log_file_path)
        )
        
        logging.debug(f"CLI Application Logging Initialized. Level: {self._log_level}. File: '{log_file_path}'")
    
    @property
    def config(self) -> Config:
        """Get the configuration instance."""
        if not self._config:
            raise RuntimeError("Configuration not initialized")
        return self._config
    
    @property
    def logger_manager(self) -> LoggerManager:
        """Get the logger manager instance."""
        if not self._logger_manager:
            raise RuntimeError("Logger manager not initialized")
        return self._logger_manager
    
    @property
    def services(self) -> ServiceRegistry:
        """Get the service registry."""
        return self._services
    
    def get_api_dir(self) -> str:
        """Get the API directory path."""
        return str(_project_root)
    
    def get_project_root(self) -> str:
        """Get the project root directory."""
        return str(_project_root)
