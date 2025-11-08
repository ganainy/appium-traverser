"""
Shared crawler orchestration controller.

This module provides the core orchestration logic used by both CLI and UI interfaces
to manage crawler lifecycle, validation, and process handling.
"""

import logging
import os
import signal
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from config.config import Config

# Module-level constants for default fallback strings
DEFAULT_SHUTDOWN_FLAG = 'crawler_shutdown.flag'
DEFAULT_PAUSE_FLAG = 'crawler_pause.flag'
DEFAULT_OUTPUT_DIR = 'output_data'
DEFAULT_LOG_SUBDIR = 'logs'
DEFAULT_LOG_FILE = 'crawler.log'


@dataclass
class CrawlerLaunchPlan:
    """Encapsulates all parameters needed to launch a crawler process."""
    
    # Execution parameters
    python_executable: str
    script_path: str
    working_directory: str
    
    # Configuration
    app_package: str
    app_activity: str
    output_data_dir: str
    log_file_path: str
    
    # Paths for flags and PID
    shutdown_flag_path: str
    pause_flag_path: str
    pid_file_path: str
    
    # Optional fields with defaults
    environment: Dict[str, str] = field(default_factory=dict)
    validation_passed: bool = True
    validation_messages: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Post-initialization to ensure paths are absolute."""
        self.script_path = os.path.abspath(self.script_path)
        self.working_directory = os.path.abspath(self.working_directory)
        self.shutdown_flag_path = os.path.abspath(self.shutdown_flag_path)
        self.pause_flag_path = os.path.abspath(self.pause_flag_path)
        self.pid_file_path = os.path.abspath(self.pid_file_path)


class FlagController:
    """Manages flag files for crawler process control."""
    
    SHUTDOWN_FLAG_CONTENT = "shutdown"
    PAUSE_FLAG_CONTENT = "pause"
    
    def __init__(self, shutdown_flag_path: str, pause_flag_path: str):
        self.shutdown_flag_path = shutdown_flag_path
        self.pause_flag_path = pause_flag_path
        self.logger = logging.getLogger(__name__)
    
    def create_shutdown_flag(self) -> bool:
        """Create a shutdown flag to signal the crawler to stop."""
        try:
            Path(self.shutdown_flag_path).write_text(self.SHUTDOWN_FLAG_CONTENT)
            self.logger.debug(f"Created shutdown flag: {self.shutdown_flag_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create shutdown flag: {e}")
            return False
    
    def create_pause_flag(self) -> bool:
        """Create a pause flag to signal the crawler to pause."""
        try:
            Path(self.pause_flag_path).write_text(self.PAUSE_FLAG_CONTENT)
            self.logger.debug(f"Created pause flag: {self.pause_flag_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create pause flag: {e}")
            return False
    
    def remove_pause_flag(self) -> bool:
        """Remove the pause flag to signal the crawler to resume."""
        try:
            if Path(self.pause_flag_path).exists():
                Path(self.pause_flag_path).unlink()
                self.logger.debug(f"Removed pause flag: {self.pause_flag_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove pause flag: {e}")
            return False
    
    def remove_shutdown_flag(self) -> bool:
        """Remove the shutdown flag if it exists."""
        try:
            if Path(self.shutdown_flag_path).exists():
                Path(self.shutdown_flag_path).unlink()
                self.logger.debug(f"Removed shutdown flag: {self.shutdown_flag_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove shutdown flag: {e}")
            return False
    
    def is_pause_flag_present(self) -> bool:
        """Check if the pause flag exists."""
        return Path(self.pause_flag_path).exists()
    
    def is_shutdown_flag_present(self) -> bool:
        """Check if the shutdown flag exists."""
        return Path(self.shutdown_flag_path).exists()


class ProcessBackend(ABC):
    """Abstract base class for process backends."""
    
    @abstractmethod
    def start_process(self, plan: CrawlerLaunchPlan) -> bool:
        """Start a process using the launch plan."""
        pass
    
    @abstractmethod
    def stop_process(self) -> bool:
        """Stop the running process."""
        pass
    
    @abstractmethod
    def is_process_running(self) -> bool:
        """Check if the process is still running."""
        pass
    
    @abstractmethod
    def get_process_id(self) -> Optional[int]:
        """Get the process ID if available."""
        pass
    
    def start_output_monitoring(self, output_parser: 'OutputParser') -> None:
        """Start monitoring process output (optional implementation)."""
        # TODO: Implement process output monitoring functionality
        pass


class OutputParser:
    """Handles parsing of crawler output for standardized callbacks."""
    
    EVENT_PREFIX_MAP = {
        'step': 'UI_STEP:',
        'action': 'UI_ACTION:',
        'screenshot': 'UI_SCREENSHOT:',
        'status': 'UI_STATUS:',
        'focus': 'UI_FOCUS:',
        'end': 'UI_END:',
    }
    
    def __init__(self):
        self.callbacks = {key: [] for key in self.EVENT_PREFIX_MAP}
        self.callbacks['log'] = []
    
    def register_callback(self, event_type: str, callback: Callable):
        """Register a callback for a specific event type."""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
    
    def parse_line(self, line: str):
        """Parse a line of output and trigger appropriate callbacks."""
        line = line.strip()
        if not line:
            return
        
        # Iterate through event types and their prefixes
        for event_type, prefix in self.EVENT_PREFIX_MAP.items():
            if line.startswith(prefix):
                try:
                    value = line.split(prefix, 1)[1].strip()
                    
                    # Handle step case specifically to cast to int
                    if event_type == 'step':
                        try:
                            value = int(value)
                        except ValueError:
                            return  # Skip if step value is not a valid integer
                    
                    # Trigger all registered callbacks for this event type
                    for cb in self.callbacks[event_type]:
                        cb(value)
                    
                    return  # Successfully parsed and dispatched
                except IndexError:
                    continue  # Try next event type if split fails
        
        # If no matches found, treat as a log line
        for cb in self.callbacks['log']:
            cb(line)


class CrawlerOrchestrator:
    """Main orchestrator for crawler lifecycle management."""
    
    def __init__(self, config: "Config", backend: ProcessBackend):
        self.config = config
        self.backend = backend
        self.logger = logging.getLogger(__name__)
        self.output_parser = OutputParser()
        self._current_plan = None
        self._is_running = False
        
        # Set up flag paths from config
        shutdown_flag_path = getattr(config, 'SHUTDOWN_FLAG_PATH',
                                os.path.join(config.BASE_DIR or '.', DEFAULT_SHUTDOWN_FLAG))
        pause_flag_path = getattr(config, 'PAUSE_FLAG_PATH',
                                os.path.join(config.BASE_DIR or '.', DEFAULT_PAUSE_FLAG))
        
        self.flag_controller = FlagController(shutdown_flag_path, pause_flag_path)
    
    def prepare_plan(self) -> CrawlerLaunchPlan:
        """Prepare a launch plan with validation."""
        # Get paths from configuration
        project_root = getattr(self.config, 'PROJECT_ROOT')
        main_script_name = getattr(self.config, 'MAIN_SCRIPT_NAME', 'run_cli.py')
        main_script = os.path.join(project_root, main_script_name)
        
        # Resolve paths
        output_data_dir = getattr(self.config, 'OUTPUT_DATA_DIR',
                                os.path.join(project_root, DEFAULT_OUTPUT_DIR))
        log_dir = getattr(self.config, 'LOG_DIR',
                        os.path.join(output_data_dir, DEFAULT_LOG_SUBDIR))
        log_file_path = os.path.join(log_dir, getattr(self.config, 'LOG_FILE_NAME', DEFAULT_LOG_FILE))
        
        # PID file path (use property to resolve placeholders)
        pid_file_path = getattr(self.config, 'CRAWLER_PID_PATH')
        
        # Prepare environment
        env = os.environ.copy()
        env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")
        
        # Create the plan
        plan = CrawlerLaunchPlan(
            python_executable=sys.executable,
            script_path=main_script,
            working_directory=project_root,
            environment=env,
            app_package=getattr(self.config, 'APP_PACKAGE', ''),
            app_activity=getattr(self.config, 'APP_ACTIVITY', ''),
            output_data_dir=output_data_dir,
            log_file_path=log_file_path,
            shutdown_flag_path=self.flag_controller.shutdown_flag_path,
            pause_flag_path=self.flag_controller.pause_flag_path,
            pid_file_path=pid_file_path
        )
        
        # Perform validation
        self._validate_plan(plan)
        
        self._current_plan = plan
        return plan
    
    def _validate_plan(self, plan: CrawlerLaunchPlan):
        """Validate the launch plan."""
        from core.validation import ValidationService
        
        validation_service = ValidationService(self.config)
        is_valid, messages = validation_service.validate_all()
        
        plan.validation_passed = is_valid
        plan.validation_messages = messages
        
        if not is_valid:
            self.logger.warning(f"Crawler validation failed: {messages}")
    
    def start_crawler(self) -> bool:
        """Start the crawler process."""
        if self._is_running and self.backend.is_process_running():
            self.logger.warning("Crawler is already running")
            return False
        
        # Prepare launch plan
        plan = self.prepare_plan()
        
        if not plan.validation_passed:
            self.logger.error("Crawler validation failed. Not starting.")
            return False
        
        # Remove existing shutdown flag
        self.flag_controller.remove_shutdown_flag()
        
        # Ensure output directories exist
        os.makedirs(os.path.dirname(plan.log_file_path), exist_ok=True)
        
        # Start the process
        self.logger.info(f"Starting crawler with: {plan.python_executable} {plan.script_path}")
        success = self.backend.start_process(plan)
        
        if success:
            self._is_running = True
            
            # Write PID file if we have a PID
            pid = self.backend.get_process_id()
            if pid:
                try:
                    Path(plan.pid_file_path).write_text(str(pid))
                    self.logger.debug(f"Wrote PID {pid} to {plan.pid_file_path}")
                except Exception as e:
                    self.logger.error(f"Failed to write PID file: {e}")
            
            # Start output monitoring
            self.backend.start_output_monitoring(self.output_parser)
        else:
            self.logger.error("Failed to start crawler process")
        
        return success
    
    def stop_crawler(self) -> bool:
        """Stop the crawler process."""
        if not self._is_running:
            self.logger.warning("No crawler process is running")
            return False
        
        # Create shutdown flag for graceful shutdown
        self.flag_controller.create_shutdown_flag()
        
        # Stop the process via backend
        success = self.backend.stop_process()
        
        if success:
            self._is_running = False
            
            # Clean up PID file
            if self._current_plan and os.path.exists(self._current_plan.pid_file_path):
                try:
                    os.remove(self._current_plan.pid_file_path)
                    self.logger.debug(f"Removed PID file: {self._current_plan.pid_file_path}")
                except Exception as e:
                    self.logger.error(f"Failed to remove PID file: {e}")
        else:
            self.logger.error("Failed to stop crawler process")
        
        return success
    
    def pause_crawler(self) -> bool:
        """Pause the crawler process."""
        if not self._is_running:
            self.logger.warning("No crawler process is running")
            return False
        
        return self.flag_controller.create_pause_flag()
    
    def resume_crawler(self) -> bool:
        """Resume the crawler process."""
        if not self._is_running:
            self.logger.warning("No crawler process is running")
            return False
        
        return self.flag_controller.remove_pause_flag()
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the crawler."""
        status = {
            "is_running": self._is_running and self.backend.is_process_running(),
            "is_paused": self.flag_controller.is_pause_flag_present(),
            "process_id": self.backend.get_process_id(),
            "validation_passed": self._current_plan.validation_passed if self._current_plan else False,
            "validation_messages": self._current_plan.validation_messages if self._current_plan else [],
            "app_package": getattr(self.config, 'APP_PACKAGE', 'Not Set'),
            "app_activity": getattr(self.config, 'APP_ACTIVITY', 'Not Set'),
            "output_dir": getattr(self.config, 'OUTPUT_DATA_DIR', 'Not Set')
        }
        
        return status
    
    def register_callback(self, event_type: str, callback: Callable):
        """Register a callback for crawler events."""
        self.output_parser.register_callback(event_type, callback)
