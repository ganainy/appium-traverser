"""
Process backend adapters for different execution environments.

This module provides adapters for running crawler processes in different
environments (CLI subprocess vs UI QProcess).
"""

import errno
import logging
import os
import platform
import select
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING
from .controller import ProcessBackend

if TYPE_CHECKING:
    from core.controller import CrawlerLaunchPlan, OutputParser, ProcessBackend

# Module-level constants for Qt callback names
QT_CALLBACK_NAMES = ('step', 'action', 'screenshot', 'status', 'focus', 'end', 'log')

# Timeout constants (in seconds/milliseconds)
SUBPROCESS_GRACEFUL_TIMEOUT_SEC = 5
SUBPROCESS_START_CHECK_TIMEOUT_SEC = 2.0  # Time to wait before checking if process started
SUBPROCESS_OUTPUT_READ_TIMEOUT_SEC = 1.0  # Timeout for reading error output
QT_START_TIMEOUT_MS = 5000
QT_GRACEFUL_FINISH_TIMEOUT_MS = 5000
QT_KILL_FINISH_TIMEOUT_MS = 3000

# Process/Encoding constants
PYTHON_EXEC_ARGS = ["-u"]
DEFAULT_ENCODING = "utf-8"
DEFAULT_ENCODING_ERRORS = "replace"


class SubprocessBackend(ProcessBackend):
    """Process backend using subprocess for CLI environments."""
    
    def __init__(self):
        self.process = None
        self.logger = logging.getLogger(__name__)
        self._output_thread = None
        self._output_parser = None
    
    def start_process(self, plan: "CrawlerLaunchPlan") -> bool:
        """Start a process using subprocess."""
        try:
            # Log what we're about to start
            cmd = [plan.python_executable] + PYTHON_EXEC_ARGS + [plan.script_path]
            self.logger.info(f"Starting subprocess: {' '.join(cmd)}")
            self.logger.debug(f"Working directory: {plan.working_directory}")
            self.logger.debug(f"Environment CRAWLER_MODE: {plan.environment.get('CRAWLER_MODE', 'NOT SET')}")
            
            self.process = subprocess.Popen(
                cmd,
                cwd=plan.working_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding=DEFAULT_ENCODING,
                errors=DEFAULT_ENCODING_ERRORS,
                env=plan.environment,
            )
            
            # Wait a bit for the process to start, then check if it's still alive
            # Use a configurable timeout instead of hardcoded value
            time.sleep(SUBPROCESS_START_CHECK_TIMEOUT_SEC)
            
            # Check if process exited immediately
            return_code = self.process.poll()
            if return_code is not None:
                # Process exited immediately - try to get error output
                self.logger.error(f"Subprocess exited immediately with code {return_code}")
                error_output = self._read_process_output()
                self._log_process_failure(return_code, error_output)
                return False
            
            self.logger.info(f"Started subprocess with PID {self.process.pid}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start subprocess: {e}", exc_info=True)
            return False
    
    def _read_process_output(self) -> str:
        """
        Safely read output from a terminated subprocess.
        
        Returns:
            The error output as a string, or empty string if reading failed.
        """
        if not self.process or not self.process.stdout:
            return ""
        
        error_output = ""
        try:
            # First, try using communicate() with a timeout - this is the most reliable method
            # for reading output from a terminated process
            try:
                stdout_data, _ = self.process.communicate(timeout=SUBPROCESS_OUTPUT_READ_TIMEOUT_SEC)
                error_output = stdout_data or ""
            except subprocess.TimeoutExpired:
                # This shouldn't happen if process already terminated, but handle it
                self.logger.warning("Timeout while reading from terminated process")
                self.process.kill()  # Clean up
                try:
                    stdout_data, _ = self.process.communicate(timeout=0.5)
                    error_output = stdout_data or ""
                except Exception:
                    pass
            except (ValueError, OSError) as e:
                # Process already finished or pipe closed - try alternative method
                self.logger.debug(f"communicate() failed: {e}, trying alternative read method")
                error_output = self._read_output_alternative()
        except Exception as e:
            self.logger.warning(f"Error reading subprocess output: {e}")
            # Try alternative method as fallback
            error_output = self._read_output_alternative()
        
        return error_output
    
    def _read_output_alternative(self) -> str:
        """
        Alternative method to read output when communicate() fails.
        Uses platform-specific approaches for reading from stdout pipe.
        
        Returns:
            The error output as a string, or empty string if reading failed.
        """
        if not self.process or not self.process.stdout:
            return ""
        
        output_lines = []
        is_windows = platform.system() == "Windows"
        
        try:
            if is_windows:
                # On Windows, select.select() doesn't work with pipes
                # Since the process has already terminated, readline() should return quickly
                # or we can try to read what's available
                try:
                    # Try to read available data
                    # On Windows, readline() may block if pipe is still open but empty,
                    # but since process terminated, this should be safe
                    while True:
                        line = self.process.stdout.readline()
                        if not line:
                            break
                        output_lines.append(line.rstrip())
                except (OSError, ValueError, BrokenPipeError):
                    # Pipe may be closed or invalid
                    pass
            else:
                # Unix-like system: use select for non-blocking reads
                try:
                    # Check if data is available with a short timeout
                    ready, _, _ = select.select([self.process.stdout], [], [], 0.1)
                    if ready:
                        while True:
                            line = self.process.stdout.readline()
                            if not line:
                                break
                            output_lines.append(line.rstrip())
                except (OSError, ValueError):
                    # Pipe may be closed or select may fail
                    pass
        except Exception as e:
            # Catch all other exceptions (but not KeyboardInterrupt/SystemExit)
            self.logger.debug(f"Alternative read method failed: {e}")
        
        return "\n".join(output_lines)
    
    def _log_process_failure(self, return_code: int, error_output: str) -> None:
        """
        Log and display process failure information.
        
        Args:
            return_code: The process return code
            error_output: The error output from the process
        """
        if error_output:
            self.logger.error(f"Subprocess error output:\n{error_output}")
            # Print to stderr so it's visible in CLI
            print(f"\n{'='*60}", file=sys.stderr, flush=True)
            print(f"ERROR: Subprocess exited with code {return_code}", file=sys.stderr, flush=True)
            print(f"{'='*60}", file=sys.stderr, flush=True)
            print(error_output, file=sys.stderr, flush=True)
            print(f"{'='*60}\n", file=sys.stderr, flush=True)
        else:
            self.logger.error("Subprocess exited but produced no output")
            print(f"\nERROR: Subprocess exited with code {return_code} but produced no output", file=sys.stderr, flush=True)
            print("This usually means the process crashed during initialization.", file=sys.stderr, flush=True)
            print("Check the logs or try running the command directly to see the error.\n", file=sys.stderr, flush=True)
    
    def stop_process(self) -> bool:
        """Stop the subprocess."""
        if not self.process:
            return False
        
        try:
            # Try graceful termination first
            self.process.terminate()
            
            # Wait a bit for graceful termination
            try:
                self.process.wait(timeout=SUBPROCESS_GRACEFUL_TIMEOUT_SEC)
                self.logger.debug("Subprocess terminated gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                self.process.kill()
                self.process.wait()
                self.logger.debug("Subprocess killed forcefully")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop subprocess: {e}")
            return False
    
    def is_process_running(self) -> bool:
        """Check if the subprocess is still running."""
        return bool(self.process and self.process.poll() is None)
    
    def get_process_id(self) -> Optional[int]:
        """Get the subprocess PID."""
        return self.process.pid if self.process else None
    
    def start_output_monitoring(self, output_parser: "OutputParser"):
        """Start monitoring the subprocess output."""
        if not self.process or not self.process.stdout:
            return
        
        self._output_parser = output_parser
        
        # Start a thread to monitor output
        # Use daemon=False to ensure the parent process waits for the thread to finish
        # This prevents race conditions during interpreter shutdown
        self._output_thread = threading.Thread(target=self._monitor_output, daemon=False)
        self._output_thread.start()
    
    def _monitor_output(self):
        """Monitor subprocess output and parse it."""
        if not self.process or not self.process.stdout:
            self.logger.warning("Cannot monitor output: no process or stdout")
            return
        
        pid = self.process.pid
        self.logger.debug(f"Output monitoring thread started for PID {pid}, reading lines...")
        try:
            for line in iter(self.process.stdout.readline, ""):
                if not line:  # EOF
                    self.logger.info("Subprocess output stream closed (EOF)")
                    # Check return code
                    if self.process.poll() is not None:
                        return_code = self.process.returncode
                        if return_code != 0:
                            self.logger.error(f"Subprocess (PID {pid}) exited with non-zero code: {return_code}")
                        else:
                            self.logger.info(f"Subprocess (PID {pid}) exited with code: {return_code}")
                    break
                line = line.rstrip()
                if line:
                    # Log the output for debugging
                    self.logger.debug(f"Subprocess output: {line}")
                    # Also print to stderr so it's visible in the parent process
                    # Use try/except to avoid errors during shutdown
                    try:
                        print(line, file=sys.stderr, flush=True)
                    except (OSError, ValueError):
                        # Stream may be closed during shutdown, ignore
                        pass
                    if self._output_parser:
                        try:
                            self._output_parser.parse_line(line)
                        except Exception as e:
                            # Don't let parser errors crash the monitoring thread
                            self.logger.warning(f"Error parsing output line: {e}")
            
            # Wait for process to finish (if not already done)
            try:
                rc = self.process.wait(timeout=0.1)
                self.logger.info(f"Subprocess (PID {pid}) exited with code {rc}.")
            except subprocess.TimeoutExpired:
                # Process still running, that's fine
                pass
            except Exception as wait_error:
                # Process may have already finished
                self.logger.debug(f"Error waiting for process: {wait_error}")
            
        except Exception as e:
            self.logger.error(f"Error monitoring subprocess (PID {pid}): {e}")


class QtProcessBackend(ProcessBackend):
    """Process backend using QProcess for UI environments."""
    
    def __init__(self):
        try:
            from PySide6.QtCore import QObject, QProcess, Signal
            self.QProcess = QProcess
            self.QObject = QObject
            self.Signal = Signal
            self.qt_available = True
        except ImportError:
            self.logger = logging.getLogger(__name__)
            self.logger.warning("PySide6 not available, QtProcessBackend will not work")
            self.qt_available = False
            return
        
        self.process = None
        self.logger = logging.getLogger(__name__)
        self._output_parser = None
        self._qt_ready_read_connection = None
        self._qt_finished_connection = None
        self._output_buffer = ""
        
        # Create a QObject to host signals
        class ProcessSignals(QObject):
            step_updated = Signal(int)
            action_updated = Signal(str)
            screenshot_updated = Signal(str)
            status_updated = Signal(str)
            focus_updated = Signal(str)
            end_updated = Signal(str)
            log_updated = Signal(str)
        
        self.signals = ProcessSignals()
    
    def start_process(self, plan: "CrawlerLaunchPlan") -> bool:
        """Start a process using QProcess."""
        if not self.qt_available:
            self.logger.error("Qt not available, cannot start QProcess")
            return False
        
        try:
            self.process = self.QProcess()
            
            # Set up environment
            env = self.process.processEnvironment()
            for key, value in plan.environment.items():
                env.insert(key, value)
            self.process.setProcessEnvironment(env)
            
            # Set working directory
            self.process.setWorkingDirectory(plan.working_directory)
            
            # Start the process
            self.process.start(plan.python_executable, PYTHON_EXEC_ARGS + [plan.script_path])
            
            if self.process.waitForStarted(QT_START_TIMEOUT_MS):  # Wait up to 5 seconds for start
                self.logger.debug(f"Started QProcess with PID {self.process.processId()}")
                return True
            else:
                self.logger.error("QProcess failed to start")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start QProcess: {e}")
            return False
    
    def stop_process(self) -> bool:
        """Stop the QProcess."""
        if not self.process:
            return False
        
        try:
            # Try graceful termination first
            self.process.terminate()
            
            # Wait a bit for graceful termination
            if self.process.waitForFinished(QT_GRACEFUL_FINISH_TIMEOUT_MS):
                self.logger.debug("QProcess terminated gracefully")
            else:
                # Force kill if it doesn't terminate gracefully
                self.process.kill()
                self.process.waitForFinished(QT_KILL_FINISH_TIMEOUT_MS)
                self.logger.debug("QProcess killed forcefully")
            
            # Clean up signal connections
            self._cleanup_signal_connections()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop QProcess: {e}")
            return False
    
    def is_process_running(self) -> bool:
        """Check if the QProcess is still running."""
        return bool(self.process and self.process.state() == self.QProcess.ProcessState.Running)
    
    def get_process_id(self) -> Optional[int]:
        """Get the QProcess PID."""
        return self.process.processId() if self.process else None
    
    def start_output_monitoring(self, output_parser: "OutputParser"):
        """Start monitoring the QProcess output."""
        if not self.process or not self.qt_available:
            return
        
        self._output_parser = output_parser
        
        # Connect signals
        self._qt_ready_read_connection = self.process.readyReadStandardOutput.connect(
            self._handle_output
        )
        
        # Set up callbacks to emit Qt signals dynamically
        for name in QT_CALLBACK_NAMES:
            try:
                signal = getattr(self.signals, f"{name}_updated")
                output_parser.register_callback(name, signal.emit)
            except AttributeError:
                self.logger.warning(f"Signal '{name}_updated' not found in ProcessSignals.")
    
    def _handle_output(self):
        """Handle QProcess output and parse it line by line."""
        if not self.process:
            return
        
        try:
            # Read all available data
            raw_data = self.process.readAllStandardOutput().data()
            if not raw_data:
                return
            
            # Decode the data using the default encoding
            output = bytes(raw_data).decode(DEFAULT_ENCODING, errors=DEFAULT_ENCODING_ERRORS)
            
            # Append to the buffer
            self._output_buffer += output
            
            # Process complete lines
            while '\n' in self._output_buffer:
                # Split at the first newline
                line, remainder = self._output_buffer.split('\n', 1)
                
                # Update the buffer to the remainder
                self._output_buffer = remainder
                
                # Parse the line if it's not empty
                if line.strip() and self._output_parser:
                    self._output_parser.parse_line(line)
                        
        except Exception as e:
            self.logger.error(f"Error handling QProcess output: {e}")
    
    def _cleanup_signal_connections(self):
        """Clean up Qt signal connections."""
        if self._qt_ready_read_connection and self.process:
            try:
                self.process.readyReadStandardOutput.disconnect(self._qt_ready_read_connection)
            except Exception:
                pass
            self._qt_ready_read_connection = None
        
        if self._qt_finished_connection and self.process:
            try:
                self.process.finished.disconnect(self._qt_finished_connection)
            except Exception:
                pass
            self._qt_finished_connection = None


# Factory function to create appropriate backend
def create_process_backend(use_qt: bool = False) -> "ProcessBackend":
    """
    Create a process backend based on the environment.
    
    Args:
        use_qt: Whether to use Qt backend (for UI environments)
        
    Returns:
        ProcessBackend instance
    """
    if use_qt:
        return QtProcessBackend()
    else:
        return SubprocessBackend()