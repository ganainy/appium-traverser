"""
Process utilities for CLI operations.
"""

import errno
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional
import psutil
from cli.constants.messages import (
    PID_FILE_CREATED,
    FAILED_TO_CREATE_PID_FILE,
    ERROR_READING_PID_FILE,
    PID_FILE_REMOVED,
    FAILED_TO_REMOVE_PID_FILE,
    REMOVED_PID_FILE,
    ERROR_DURING_PID_CLEANUP,
    FLAG_FILE_CREATED,
    FAILED_TO_CREATE_FLAG_FILE,
    FLAG_FILE_REMOVED,
    FAILED_TO_REMOVE_FLAG_FILE,
    COMMAND_TIMED_OUT,
    ERROR_RUNNING_COMMAND,
    STARTED_DAEMON_PROCESS,
    FAILED_TO_START_DAEMON_PROCESS,
    PROCESS_EXITED,
    ERROR_MONITORING_PROCESS,
    SIGNAL_RECEIVED,
    SIGHUP_NOT_SUPPORTED
)
from cli.constants.keys import SUBPROCESS_CREATION_FLAG


# Utility functions for process management operations.

def is_process_running(pid: int) -> bool:
    """
    Check if a process is running.

    Args:
        pid: Process ID

    Returns:
        True if process is running, False otherwise
    """
    if pid <= 0:
        return False
    return psutil.pid_exists(pid)

def create_pid_file(pid_file_path: str, pid: int) -> bool:
    """
    Create a PID file.

    Args:
        pid_file_path: Path to PID file
        pid: Process ID

    Returns:
        True if successful, False otherwise
    """
    try:
        pid_file = Path(pid_file_path)
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(pid))
        logging.debug(PID_FILE_CREATED.format(path=pid_file_path, pid=pid))
        return True
    except Exception as e:
        logging.error(FAILED_TO_CREATE_PID_FILE.format(path=pid_file_path, error=e))
        return False

def read_pid_file(pid_file_path: str) -> Optional[int]:
    """
    Read PID from PID file.

    Args:
        pid_file_path: Path to PID file

    Returns:
        Process ID or None if error
    """
    try:
        pid_file = Path(pid_file_path)
        if not pid_file.exists():
            return None

        pid_text = pid_file.read_text().strip()
        return int(pid_text) if pid_text else None

    except (ValueError, OSError) as e:
        logging.warning(ERROR_READING_PID_FILE.format(path=pid_file_path, error=e))
        return None

def remove_pid_file(pid_file_path: str) -> bool:
    """
    Remove a PID file.

    Args:
        pid_file_path: Path to PID file

    Returns:
        True if successful, False otherwise
    """
    try:
        pid_file = Path(pid_file_path)
        if pid_file.exists():
            pid_file.unlink()
            logging.debug(PID_FILE_REMOVED.format(path=pid_file_path))
        return True
    except Exception as e:
        logging.error(FAILED_TO_REMOVE_PID_FILE.format(path=pid_file_path, error=e))
        return False

def cleanup_pid_file_if_matches(pid_file_path: str, pid_to_check: Optional[int]) -> None:
    """
    Clean up PID file if it matches the given PID or if process is not running.

    Args:
        pid_file_path: Path to PID file
        pid_to_check: PID to check against
    """
    pid_file = Path(pid_file_path)
    if not pid_file.exists():
        return

    try:
        pid_in_file = int(pid_file.read_text().strip())

        should_remove = False
        if pid_to_check is not None:
            # Remove if PID matches and process is not running
            should_remove = (pid_in_file == pid_to_check and 
                           not is_process_running(pid_in_file))
        else:
            # Remove if process is not running
            should_remove = not is_process_running(pid_in_file)

        if should_remove:
            pid_file.unlink()
            logging.debug(REMOVED_PID_FILE.format(path=pid_file, pid=pid_in_file))

    except (ValueError, OSError, Exception) as e:
        logging.warning(ERROR_DURING_PID_CLEANUP.format(path=pid_file, error=e))
        try:
            pid_file.unlink()
        except OSError:
            pass

def create_flag_file(flag_file_path: str, content: str = "flag") -> bool:
    """
    Create a flag file.

    Args:
        flag_file_path: Path to flag file
        content: Content to write to flag file

    Returns:
        True if successful, False otherwise
    """
    try:
        flag_file = Path(flag_file_path)
        flag_file.parent.mkdir(parents=True, exist_ok=True)
        flag_file.write_text(content)
        logging.debug(FLAG_FILE_CREATED.format(path=flag_file_path))
        return True
    except Exception as e:
        logging.error(FAILED_TO_CREATE_FLAG_FILE.format(path=flag_file_path, error=e))
        return False

def remove_flag_file(flag_file_path: str) -> bool:
    """
    Remove a flag file.

    Args:
        flag_file_path: Path to flag file

    Returns:
        True if successful, False otherwise
    """
    try:
        flag_file = Path(flag_file_path)
        if flag_file.exists():
            flag_file.unlink()
            logging.debug(FLAG_FILE_REMOVED.format(path=flag_file_path))
        return True
    except Exception as e:
        logging.error(FAILED_TO_REMOVE_FLAG_FILE.format(path=flag_file_path, error=e))
        return False

def flag_file_exists(flag_file_path: str) -> bool:
    """
    Check if a flag file exists.

    Args:
        flag_file_path: Path to flag file

    Returns:
        True if flag file exists, False otherwise
    """
    return Path(flag_file_path).exists()

def run_subprocess(
    command: list,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False
) -> subprocess.CompletedProcess:
    """
    Run a subprocess with common parameters.

    Args:
        command: Command to run
        cwd: Working directory
        env: Environment variables
        timeout: Timeout in seconds
        capture_output: Whether to capture output
        text: Whether to return text output
        check: Whether to raise exception on non-zero exit

    Returns:
        Completed process result
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            capture_output=capture_output,
            text=text,
            check=check,
            creationflags=(
                getattr(subprocess, SUBPROCESS_CREATION_FLAG, 0)
            ),
        )
        return result
    except subprocess.TimeoutExpired as e:
        logging.error(COMMAND_TIMED_OUT.format(timeout=timeout, command=' '.join(command)))
        raise
    except Exception as e:
        logging.error(ERROR_RUNNING_COMMAND.format(command=' '.join(command), error=e))
        raise

def start_daemon_process(
    command: list,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    pid_file_path: Optional[str] = None,
    output_callback: Optional[Callable[[str], None]] = None
) -> Optional[subprocess.Popen]:
    """
    Start a daemon process.

    Args:
        command: Command to run
        cwd: Working directory
        env: Environment variables
        pid_file_path: Path to PID file
        output_callback: Callback for output lines

    Returns:
        Process object or None if failed
    """
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        # Create PID file if specified
        if pid_file_path:
            create_pid_file(pid_file_path, process.pid)

        # Start output monitoring if callback provided
        if output_callback:
            threading.Thread(
                target=_monitor_output,
                args=(process, output_callback),
                daemon=True
            ).start()

        logging.debug(STARTED_DAEMON_PROCESS.format(pid=process.pid, command=' '.join(command)))
        return process

    except Exception as e:
        logging.error(FAILED_TO_START_DAEMON_PROCESS.format(error=e))
        return None

def _monitor_output(process: subprocess.Popen, callback: Callable[[str], None]) -> None:
    """
    Monitor process output and call callback for each line.

    Args:
        process: Process to monitor
        callback: Callback function for output lines
    """
    if not process or not process.stdout:
        return

    pid = process.pid
    try:
        for line in iter(process.stdout.readline, ""):
            if line:
                callback(line.rstrip('\n'))

        # Wait for process to complete
        return_code = process.wait()
        logging.debug(PROCESS_EXITED.format(pid=pid, code=return_code))

    except Exception as e:
        logging.error(ERROR_MONITORING_PROCESS.format(pid=pid, error=e))

def setup_signal_handlers(
    shutdown_handler: Callable[[], None],
    reload_handler: Optional[Callable[[], None]] = None
) -> None:
    """
    Setup signal handlers for graceful shutdown.

    Args:
        shutdown_handler: Handler for shutdown signals
        reload_handler: Optional handler for reload signals
    """
    def signal_handler(signum, _):
        signal_name = signal.Signals(signum).name
        logging.warning(SIGNAL_RECEIVED.format(signal=signal_name))
        shutdown_handler()

    # Register shutdown signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Adjusted SIGHUP handling to ensure fallback logic is applied correctly
    if reload_handler:
        if hasattr(signal, 'SIGHUP'):
            try:
                sighup = getattr(signal, 'SIGHUP')
                signal.signal(sighup, lambda _signum, _frame: reload_handler())
            except Exception as e:
                logging.warning(f"Failed to register SIGHUP: {e}")
        else:
            logging.warning(SIGHUP_NOT_SUPPORTED)
