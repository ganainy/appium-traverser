"""
Process backend adapters for different execution environments.

This module provides adapters for running crawler processes in different
environments (CLI subprocess vs UI QProcess).
"""

import errno
import logging
import os
import subprocess
import sys
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional

from traverser_ai_api.core.controller import CrawlerLaunchPlan, OutputParser, ProcessBackend


class SubprocessBackend(ProcessBackend):
    """Process backend using subprocess for CLI environments."""
    
    def __init__(self):
        self.process = None
        self.logger = logging.getLogger(__name__)
        self._output_thread = None
        self._output_parser = None
    
    def start_process(self, plan: CrawlerLaunchPlan) -> bool:
        """Start a process using subprocess."""
        try:
            self.process = subprocess.Popen(
                [plan.python_executable, "-u", plan.script_path],
                cwd=plan.working_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                env=plan.environment,
            )
            
            self.logger.debug(f"Started subprocess with PID {self.process.pid}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start subprocess: {e}")
            return False
    
    def stop_process(self) -> bool:
        """Stop the subprocess."""
        if not self.process:
            return False
        
        try:
            # Try graceful termination first
            self.process.terminate()
            
            # Wait a bit for graceful termination
            try:
                self.process.wait(timeout=5)
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
    
    def start_output_monitoring(self, output_parser: OutputParser):
        """Start monitoring the subprocess output."""
        if not self.process or not self.process.stdout:
            return
        
        self._output_parser = output_parser
        
        # Start a thread to monitor output
        self._output_thread = threading.Thread(target=self._monitor_output, daemon=True)
        self._output_thread.start()
    
    def _monitor_output(self):
        """Monitor subprocess output and parse it."""
        if not self.process or not self.process.stdout:
            return
        
        pid = self.process.pid
        try:
            for line in iter(self.process.stdout.readline, ""):
                if line and self._output_parser:
                    self._output_parser.parse_line(line)
            
            rc = self.process.wait()
            self.logger.debug(f"Subprocess (PID {pid}) exited with code {rc}.")
            
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
    
    def start_process(self, plan: CrawlerLaunchPlan) -> bool:
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
            self.process.start(plan.python_executable, ["-u", plan.script_path])
            
            if self.process.waitForStarted(5000):  # Wait up to 5 seconds for start
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
            if self.process.waitForFinished(5000):
                self.logger.debug("QProcess terminated gracefully")
            else:
                # Force kill if it doesn't terminate gracefully
                self.process.kill()
                self.process.waitForFinished(3000)
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
    
    def start_output_monitoring(self, output_parser: OutputParser):
        """Start monitoring the QProcess output."""
        if not self.process or not self.qt_available:
            return
        
        self._output_parser = output_parser
        
        # Connect signals
        self._qt_ready_read_connection = self.process.readyReadStandardOutput.connect(
            self._handle_output
        )
        
        # Set up callbacks to emit Qt signals
        output_parser.register_callback('step', self.signals.step_updated.emit)
        output_parser.register_callback('action', self.signals.action_updated.emit)
        output_parser.register_callback('screenshot', self.signals.screenshot_updated.emit)
        output_parser.register_callback('status', self.signals.status_updated.emit)
        output_parser.register_callback('focus', self.signals.focus_updated.emit)
        output_parser.register_callback('end', self.signals.end_updated.emit)
        output_parser.register_callback('log', self.signals.log_updated.emit)
    
    def _handle_output(self):
        """Handle QProcess output and parse it."""
        if not self.process:
            return
        
        try:
            raw_data = self.process.readAllStandardOutput().data()
            if not raw_data:
                return
            
            output = bytes(raw_data).decode('utf-8', errors='replace')
            
            if self._output_parser:
                for line in output.strip().split('\n'):
                    if line.strip():
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
def create_process_backend(use_qt: bool = False) -> ProcessBackend:
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