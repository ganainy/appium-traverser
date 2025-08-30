#!/usr/bin/env python3
# ui/health_app_scanner.py - Health app discovery for the UI controller

import os
import sys
import json
import logging
import re
import subprocess
import shutil
from typing import Optional, Dict, Any, List
from PySide6.QtCore import QObject, QProcess, Slot, Signal


class HealthAppScanner(QObject):
    """Manages health app discovery for the Appium Crawler Controller."""
    
    # Signals
    scan_started = Signal()
    scan_finished = Signal(bool, str)  # success, message
    
    def __init__(self, main_controller):
        """
        Initialize the health app scanner.
        
        Args:
            main_controller: The main UI controller
        """
        super().__init__()
        self.main_controller = main_controller
        self.config = main_controller.config
        self.api_dir = self.config.BASE_DIR
        self.find_app_info_script_path = os.path.join(self.api_dir, "find_app_info.py")
        self.find_apps_process: Optional[QProcess] = None
        self.find_apps_stdout_buffer: str = ""
        self.health_apps_data: List[Dict[str, Any]] = []
    
    def _get_current_device_id(self):
        """Get the ID of the currently connected device."""
        try:
            result = subprocess.run(['adb', 'get-serialno'], 
                                   capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != "unknown":
                device_id = result.stdout.strip()
                # Clean the device ID to make it safe for filenames
                safe_device_id = re.sub(r'[^\w\-.]', '_', device_id)
                return safe_device_id
                
            # Fallback to devices command if get-serialno fails
            devices_result = subprocess.run(['adb', 'devices'], 
                                           capture_output=True, text=True, timeout=5)
            if devices_result.returncode == 0:
                lines = devices_result.stdout.strip().splitlines()
                device_lines = [line for line in lines[1:] if line.strip() and '\tdevice' in line]
                if device_lines:
                    device_id = device_lines[0].split('\t')[0].strip()
                    # Clean the device ID to make it safe for filenames
                    safe_device_id = re.sub(r'[^\w\-.]', '_', device_id)
                    return safe_device_id
                    
            return "unknown_device"
        except Exception as e:
            logging.error(f"Error getting device ID: {e}")
            return "unknown_device"
            
    def _get_device_health_app_file_path(self, device_id=None):
        """Get the path to the health app file for the current or specified device."""
        if not device_id:
            device_id = self._get_current_device_id()
            
        # Create app_info directory if it doesn't exist
        app_info_dir = os.path.join(self.api_dir, "output_data", "app_info")
        os.makedirs(app_info_dir, exist_ok=True)
        
        # First, check if there's a direct match for the expected file (without timestamp)
        direct_match_path = os.path.join(app_info_dir, f"{device_id}_app_info_health_filtered.json")
        if os.path.exists(direct_match_path):
            return direct_match_path
            
        # If no direct match, look for any file matching the device ID pattern
        health_app_files = []
        for filename in os.listdir(app_info_dir):
            if filename.startswith(f"{device_id}_app_info_") and filename.endswith(".json"):
                file_path = os.path.join(app_info_dir, filename)
                health_app_files.append((file_path, os.path.getmtime(file_path)))
                
        # If we found files for this device, return the most recent one
        if health_app_files:
            # Sort by modification time (newest first)
            health_app_files.sort(key=lambda x: x[1], reverse=True)
            newest_file = health_app_files[0][0]
            return newest_file
            
        # If no file exists for this device, return a default path where it will be created
        return direct_match_path  # Use the direct match path as the default target

    def trigger_scan_for_health_apps(self):
        """Starts the process of scanning for health apps, forcing a rescan."""
        # Add debug logging
        self.main_controller.log_message("DEBUG: trigger_scan_for_health_apps called", 'blue')
        logging.info("DEBUG: trigger_scan_for_health_apps called")
        
        # Get the current device ID first to update main_controller.current_health_app_list_file
        device_id = self._get_current_device_id()
        self.main_controller.log_message(f"DEBUG: Got device ID: {device_id}", 'blue')
        
        device_file_path = self._get_device_health_app_file_path(device_id)
        self.main_controller.log_message(f"DEBUG: File path: {device_file_path}", 'blue')
        
        # Update the file path in the main controller
        self.main_controller.current_health_app_list_file = device_file_path
        
        # Always use a generic path in the config
        if hasattr(self.config, 'update_setting_and_save'):
            generic_path = os.path.join("output_data", "app_info", "health_apps.json")
            self.config.update_setting_and_save("CURRENT_HEALTH_APP_LIST_FILE", generic_path)
            
        self.main_controller.log_message("DEBUG: About to execute scan", 'blue')
        self._execute_scan_for_health_apps(force_rescan=True)
    
    def _execute_scan_for_health_apps(self, force_rescan: bool = False):
        """Execute the health app scan process."""
        # Add debug logging
        self.main_controller.log_message("DEBUG: _execute_scan_for_health_apps called", 'blue')
        logging.info("DEBUG: _execute_scan_for_health_apps called")
        
        # Get the device ID and determine the file path for this device
        device_id = self._get_current_device_id()
        self.main_controller.log_message(f"DEBUG: Got device ID in execute: {device_id}", 'blue')
        
        device_file_path = self._get_device_health_app_file_path(device_id)
        self.main_controller.log_message(f"DEBUG: File path in execute: {device_file_path}", 'blue')
        
        # Update the path in the main controller
        self.main_controller.current_health_app_list_file = device_file_path
        
        # Check if a cached file exists and we don't need to force a rescan
        if not force_rescan and os.path.exists(device_file_path):
            self.main_controller.log_message(f"Using cached health app list for device {device_id}: {device_file_path}")
            self._load_health_apps_from_file(device_file_path)
            return

        if self.find_apps_process and self.find_apps_process.state() != QProcess.ProcessState.NotRunning:
            self.main_controller.log_message("App scan is already in progress.")
            self.main_controller.app_scan_status_label.setText("App Scan: Scan in progress...")
            return

        if not os.path.exists(self.find_app_info_script_path):
            msg = f"find_app_info.py script not found at {self.find_app_info_script_path}. Cannot scan."
            self.main_controller.log_message(msg, 'red')
            self.main_controller.app_scan_status_label.setText("App Scan: Script not found!")
            logging.error(msg)
            
            # Additional debug information
            self.main_controller.log_message(f"DEBUG: Current directory: {os.getcwd()}", 'red')
            self.main_controller.log_message(f"DEBUG: API directory: {self.api_dir}", 'red')
            
            # Try to find the script in other locations
            for root, dirs, files in os.walk(self.api_dir):
                if "find_app_info.py" in files:
                    found_path = os.path.join(root, "find_app_info.py")
                    self.main_controller.log_message(f"DEBUG: Found script at: {found_path}", 'green')
            
            return

        # Check if ADB is available in PATH before starting the scan
        try:
            # First check if ADB is in PATH
            adb_path = shutil.which("adb")
            if not adb_path:
                self.main_controller.log_message("Error: ADB not found in PATH. Please ensure ADB is installed and in your PATH.", 'red')
                self.main_controller.app_scan_status_label.setText("App Scan: ADB not found in PATH!")
                return
                
            self.main_controller.log_message(f"Found ADB at: {adb_path}", 'green')
                
            # Now check the ADB version
            result = subprocess.run(['adb', 'version'], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.main_controller.log_message(f"Error: ADB found but not working properly. Return code: {result.returncode}", 'red')
                if result.stderr:
                    self.main_controller.log_message(f"ADB error: {result.stderr}", 'red')
                self.main_controller.app_scan_status_label.setText("App Scan: ADB not working!")
                return
                
            self.main_controller.log_message(f"ADB version: {result.stdout.strip()}", 'green')
                
            # Check if any devices are connected
            devices_result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=10)
            device_lines = devices_result.stdout.strip().split('\n')[1:]  # Skip the "List of devices attached" line
            connected_devices = [line for line in device_lines if line.strip() and not line.strip().endswith('offline')]
            
            if not connected_devices:
                self.main_controller.log_message("Error: No Android devices connected. Please connect a device and enable USB debugging.", 'red')
                self.main_controller.log_message("ADB devices output:", 'red')
                self.main_controller.log_message(devices_result.stdout, 'red')
                self.main_controller.app_scan_status_label.setText("App Scan: No devices connected!")
                return
                
            # Check if ADB can list packages (essential for app scanning)
            packages_result = subprocess.run(['adb', 'shell', 'pm', 'list', 'packages', '-3'], 
                                            capture_output=True, text=True, timeout=10)
            if packages_result.returncode != 0:
                self.main_controller.log_message("Error: Unable to list packages on device. Check device permissions.", 'red')
                if packages_result.stderr:
                    self.main_controller.log_message(f"Error details: {packages_result.stderr}", 'red')
                self.main_controller.app_scan_status_label.setText("App Scan: Package access error!")
                return
            
            # Check if we got any third-party packages
            packages = packages_result.stdout.strip()
            if not packages:
                self.main_controller.log_message("Warning: No third-party packages found on device. Device may be too locked down or empty.", 'orange')
                self.main_controller.log_message("Will attempt to scan anyway...", 'orange')
            else:
                package_count = len(packages.split('\n'))
                self.main_controller.log_message(f"Found {package_count} third-party packages on device", 'green')
                
            self.main_controller.log_message("ADB checks passed. Starting app scan...", 'green')
                
        except Exception as e:
            self.main_controller.log_message(f"Error checking ADB: {e}", 'red')
            logging.error(f"Exception checking ADB: {e}", exc_info=True)
            self.main_controller.app_scan_status_label.setText("App Scan: ADB check failed!")
            return

        self.main_controller.log_message("Starting health app scan...", 'blue')
        self.main_controller.app_scan_status_label.setText("App Scan: Scanning...")
        self.main_controller.refresh_apps_btn.setEnabled(False)
        self.main_controller.health_app_dropdown.setEnabled(False)
        self.find_apps_stdout_buffer = ""  # Reset buffer

        self.find_apps_process = QProcess()
        self.find_apps_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.find_apps_process.setWorkingDirectory(self.api_dir)

        self.find_apps_process.readyReadStandardOutput.connect(self._on_find_apps_stdout_ready)
        self.find_apps_process.finished.connect(self._on_find_apps_finished)
        
        python_executable = sys.executable
        # Run find_app_info.py as a script with additional debug logging
        self.main_controller.log_message(f"Running: {python_executable} -u {self.find_app_info_script_path} --mode discover", 'blue')
        self.main_controller.log_message(f"DEBUG: Python executable exists: {os.path.exists(python_executable)}", 'blue')
        
        try:
            self.find_apps_process.start(python_executable, ['-u', self.find_app_info_script_path, '--mode', 'discover'])
            self.main_controller.log_message("DEBUG: Process started successfully", 'green')
        except Exception as e:
            self.main_controller.log_message(f"ERROR starting process: {e}", 'red')
            logging.error(f"Exception starting QProcess: {e}", exc_info=True)
    
    @Slot()
    def _on_find_apps_stdout_ready(self) -> None:
        """Handle stdout data from the app scanning process."""
        if not self.find_apps_process:
            return
            
        # Convert QProcess output to string
        try:
            new_data = bytes(self.find_apps_process.readAllStandardOutput().data()).decode('utf-8', errors='replace')
            self.find_apps_stdout_buffer += new_data
            
            # Split on newlines and process each line
            lines = new_data.strip().split('\n')
            for line in lines:
                stripped_line = line.strip()
                if stripped_line:  # Only log non-empty lines
                    # Color code certain messages for better visibility
                    if "error" in stripped_line.lower() or "fatal" in stripped_line.lower():
                        self.main_controller.log_message(stripped_line, 'red')
                    elif "warning" in stripped_line.lower():
                        self.main_controller.log_message(stripped_line, 'orange')
                    elif "success" in stripped_line.lower() or "found" in stripped_line.lower():
                        self.main_controller.log_message(stripped_line, 'green')
                    else:
                        self.main_controller.log_message(stripped_line)
        except Exception as e:
            self.main_controller.log_message(f"Error reading app scan output: {e}", 'red')
            logging.error(f"Exception in _on_find_apps_stdout_ready: {e}", exc_info=True)
    
    @Slot(int, QProcess.ExitStatus)
    def _on_find_apps_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle completion of the app scanning process."""
        # Re-enable UI controls
        self.main_controller.refresh_apps_btn.setEnabled(True)
        self.main_controller.health_app_dropdown.setEnabled(True)

        # Handle non-zero exit code
        if exit_code != 0:
            self.main_controller.log_message(f"App scan process exited with code {exit_code}", 'red')
            self.main_controller.app_scan_status_label.setText(f"App Scan: Failed (code {exit_code})")
            return

        try:
            # Look for JSON after "SUMMARY_JSON:" marker
            summary_json_match = re.search(r'SUMMARY_JSON:\s*(\{.*?\})', self.find_apps_stdout_buffer)
            if summary_json_match:
                self.main_controller.log_message("Found SUMMARY_JSON marker in output, using that for parsing", 'green')
                json_str = summary_json_match.group(1)
                try:
                    summary_data = json.loads(json_str)
                    self.main_controller.log_message(f"Successfully parsed SUMMARY_JSON: {summary_data}", 'green')
                    
                    # Extract the file path from the summary
                    if 'file_path' in summary_data:
                        output_file = summary_data['file_path']
                        self.main_controller.log_message(f"Found file path in SUMMARY_JSON: {output_file}", 'green')
                        
                        # Try to load the file directly instead of parsing from stdout
                        if os.path.exists(output_file):
                            try:
                                with open(output_file, 'r', encoding='utf-8') as f:
                                    result_data = json.load(f)
                                self.main_controller.log_message(f"Successfully loaded JSON directly from file: {output_file}", 'green')
                            except Exception as file_error:
                                self.main_controller.log_message(f"Error loading from file referenced in SUMMARY_JSON: {file_error}", 'red')
                                result_data = None
                        else:
                            self.main_controller.log_message(f"File specified in SUMMARY_JSON not found: {output_file}", 'red')
                            result_data = None
                    else:
                        self.main_controller.log_message("No file_path found in SUMMARY_JSON", 'red')
                        result_data = None
                except json.JSONDecodeError as e:
                    self.main_controller.log_message(f"Error parsing SUMMARY_JSON: {e}. JSON snippet: {json_str[:100]}...", 'red')
                    result_data = None
            else:
                # Fall back to looking for any JSON object in the output
                self.main_controller.log_message("No SUMMARY_JSON marker found, searching for JSON in output", 'orange')
                # Look for the largest JSON object in the output (to avoid partial matches)
                all_json_matches = list(re.finditer(r'(?s)\{.*?\}', self.find_apps_stdout_buffer))
                if all_json_matches:
                    # Find the longest match which is likely the complete JSON
                    longest_match = max(all_json_matches, key=lambda m: len(m.group(0)))
                    json_str = longest_match.group(0)
                    try:
                        result_data = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        self.main_controller.log_message(f"Error parsing JSON from output: {e}", 'red')
                        result_data = None
                else:
                    self.main_controller.log_message("No JSON found in output", 'red')
                    result_data = None
            
            # If we still don't have result_data, try to find file paths in the output
            if result_data is None:
                # Look for several file path patterns in the output
                file_path_patterns = [
                    r'Successfully saved \d+ app\(s\) to (.*?\.json)',
                    r'Cache file generated at: (.*?\.json)',
                    r'Also saved to generic path: (.*?\.json)',
                    r'health_filtered\.json',  # Simple pattern that might be part of a path
                ]
                
                potential_files = []
                for pattern in file_path_patterns:
                    matches = re.finditer(pattern, self.find_apps_stdout_buffer)
                    for match in matches:
                        if len(match.groups()) > 0:
                            potential_files.append(match.group(1))
                        else:
                            # For patterns without capture groups, try to find the path around the match
                            match_pos = match.start()
                            # Look for the start of the path (could be at the beginning of a line or after a space)
                            path_start = self.find_apps_stdout_buffer.rfind('\n', 0, match_pos)
                            if path_start == -1:
                                path_start = self.find_apps_stdout_buffer.rfind(' ', 0, match_pos)
                            if path_start != -1:
                                # Look for the end of the path (could be at the end of a line or before a space)
                                path_end = self.find_apps_stdout_buffer.find('\n', match_pos)
                                if path_end == -1:
                                    path_end = self.find_apps_stdout_buffer.find(' ', match_pos)
                                if path_end != -1:
                                    potential_path = self.find_apps_stdout_buffer[path_start+1:path_end].strip()
                                    if potential_path.endswith('.json'):
                                        potential_files.append(potential_path)
                
                # Filter to only files that actually exist
                existing_files = [f for f in potential_files if os.path.exists(f)]
                
                if existing_files:
                    self.main_controller.log_message(f"Found {len(existing_files)} potential files in output, trying to load them", 'green')
                    
                    # Try each file until we successfully load one
                    for file_path in existing_files:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                result_data = json.load(f)
                            self.main_controller.log_message(f"Successfully loaded JSON from file: {file_path}", 'green')
                            
                            # Check if it has health_apps data
                            if 'health_apps' in result_data and isinstance(result_data['health_apps'], list):
                                self.main_controller.log_message(f"File contains valid health_apps data with {len(result_data['health_apps'])} apps", 'green')
                                break  # Found a good file, stop looking
                            else:
                                self.main_controller.log_message(f"File doesn't contain valid health_apps data: {file_path}", 'orange')
                                result_data = None  # Reset and try next file
                        except Exception as file_error:
                            self.main_controller.log_message(f"Error loading from file {file_path}: {file_error}", 'red')
                            result_data = None  # Reset and try next file
                else:
                    self.main_controller.log_message("No valid file paths found in output", 'red')
            
            # Process the result_data if we have it
            if result_data and 'health_apps' in result_data and isinstance(result_data['health_apps'], list):
                self.health_apps_data = result_data['health_apps']
                
                # Get current device ID to use in the filename
                device_id = result_data.get('device_id', self._get_current_device_id())
                
                # Get the device-specific health app file path
                output_file = self._get_device_health_app_file_path(device_id)
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                
                # Save the data to the file if it's not already there or was loaded from another file
                if not os.path.exists(output_file) or output_file != getattr(result_data, 'file_path', ''):
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result_data, f, indent=4, ensure_ascii=False)
                    self.main_controller.log_message(f"Saved health apps data to {output_file}", 'green')
                
                # Update the main controller and config with the file path
                self.main_controller.current_health_app_list_file = output_file
                
                # Use a relative path in the config if possible
                rel_path = os.path.relpath(output_file, self.api_dir)
                if hasattr(self.config, 'update_setting_and_save'):
                    self.config.update_setting_and_save("CURRENT_HEALTH_APP_LIST_FILE", rel_path)
                
                self.main_controller.log_message(f"Found {len(self.health_apps_data)} health apps for device {device_id}", 'green')
                
                # Update the dropdown
                self._populate_app_dropdown()
                self.main_controller.app_scan_status_label.setText(f"App Scan: Found {len(self.health_apps_data)} apps")
            else:
                # Look for the generic path as a last resort
                generic_path = os.path.join(self.api_dir, "output_data", "app_info", "health_apps.json")
                if os.path.exists(generic_path):
                    self.main_controller.log_message(f"Trying to load from generic path: {generic_path}", 'orange')
                    try:
                        with open(generic_path, 'r', encoding='utf-8') as f:
                            generic_data = json.load(f)
                        if 'health_apps' in generic_data and isinstance(generic_data['health_apps'], list):
                            self.health_apps_data = generic_data['health_apps']
                            self.main_controller.current_health_app_list_file = generic_path
                            
                            # Use a relative path in the config if possible
                            rel_path = os.path.relpath(generic_path, self.api_dir)
                            if hasattr(self.config, 'update_setting_and_save'):
                                self.config.update_setting_and_save("CURRENT_HEALTH_APP_LIST_FILE", rel_path)
                                
                            self.main_controller.log_message(f"Successfully loaded {len(self.health_apps_data)} health apps from generic path", 'green')
                            self._populate_app_dropdown()
                            self.main_controller.app_scan_status_label.setText(f"App Scan: Found {len(self.health_apps_data)} apps")
                            return
                    except Exception as generic_error:
                        self.main_controller.log_message(f"Error loading from generic path: {generic_error}", 'red')
                
                # Check for specific error patterns in the output
                error_messages = []
                if "device unauthorized" in self.find_apps_stdout_buffer.lower():
                    error_messages.append("Device unauthorized. Please check your device and allow USB debugging.")
                if "device not found" in self.find_apps_stdout_buffer.lower() or "offline" in self.find_apps_stdout_buffer.lower():
                    error_messages.append("Device not found or offline. Ensure device is connected and USB debugging is enabled.")
                if "adb command not found" in self.find_apps_stdout_buffer.lower():
                    error_messages.append("ADB command not found. Make sure ADB is installed and in your system PATH.")
                
                if error_messages:
                    for msg in error_messages:
                        self.main_controller.log_message(msg, 'red')
                    self.main_controller.app_scan_status_label.setText("App Scan: Device/ADB Error")
                else:
                    self.main_controller.log_message("Could not find valid health app data in scan output.", 'red')
                    self.main_controller.log_message(f"The process appeared to run, but we couldn't parse the results.", 'red')
                    self.main_controller.log_message(f"Try restarting the application.", 'red')
                    self.main_controller.app_scan_status_label.setText("App Scan: Error parsing results")
        except Exception as e:
            self.main_controller.log_message(f"Unexpected error processing app scan results: {e}", 'red')
            logging.error(f"Exception in _on_find_apps_finished: {e}", exc_info=True)
            self.main_controller.app_scan_status_label.setText("App Scan: Error")
            
    def _load_health_apps_from_file(self, file_path: str):
        """Load health apps data from a JSON file."""
        try:
            if not os.path.exists(file_path):
                self.main_controller.log_message(f"Health apps file not found: {file_path}", 'red')
                return

            self.main_controller.log_message(f"Attempting to load health apps from: {file_path}", 'blue')
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Handle both old and new format
            if isinstance(data, dict) and 'health_apps' in data and isinstance(data['health_apps'], list):
                # New format - nested under 'health_apps' key
                self.health_apps_data = data['health_apps']
                timestamp = data.get('timestamp', 'unknown')
                self.main_controller.log_message(f"Loaded health apps data from timestamp: {timestamp}", 'blue')
            elif isinstance(data, list):
                # Old format - direct list
                self.main_controller.log_message("Loaded health apps data from legacy format file", 'orange')
                self.health_apps_data = data
            else:
                self.main_controller.log_message(f"Invalid format in health apps file: {file_path}", 'red')
                self.main_controller.log_message(f"Data type: {type(data)}", 'red')
                if isinstance(data, dict):
                    self.main_controller.log_message(f"Dictionary keys: {list(data.keys())}", 'red')
                self.health_apps_data = []

            # Make sure UI components are available before trying to update them
            if hasattr(self.main_controller, 'health_app_dropdown') and self.main_controller.health_app_dropdown:
                self._populate_app_dropdown()
                
                if not self.health_apps_data:
                    self.main_controller.log_message("No health apps found in the cached file.", 'orange')
                    if hasattr(self.main_controller, 'app_scan_status_label') and self.main_controller.app_scan_status_label:
                        self.main_controller.app_scan_status_label.setText("App Scan: No apps in cache")
                    return
                    
                # Update status if UI component exists
                if hasattr(self.main_controller, 'app_scan_status_label') and self.main_controller.app_scan_status_label:
                    self.main_controller.app_scan_status_label.setText(f"App Scan: Loaded {len(self.health_apps_data)} apps")
                
                self.main_controller.log_message(f"Successfully loaded {len(self.health_apps_data)} health apps from {file_path}", 'green')
            else:
                self.main_controller.log_message("Health app dropdown not available yet. Skipping UI update.")

        except json.JSONDecodeError as e:
            self.main_controller.log_message(f"Error parsing JSON from file {file_path}: {e}", 'red')
            logging.error(f"JSON parse error in _load_health_apps_from_file: {e}", exc_info=True)
            
            # Try to read the first few bytes to check if it's a valid file
            try:
                with open(file_path, 'rb') as f:
                    first_bytes = f.read(100)
                self.main_controller.log_message(f"First bytes of file: {first_bytes}", 'red')
            except Exception as read_err:
                self.main_controller.log_message(f"Error reading file contents: {read_err}", 'red')
                
            self._reset_ui_after_load_error()
        except Exception as e:
            self.main_controller.log_message(f"Error loading health apps from file {file_path}: {e}", 'red')
            logging.error(f"Exception in _load_health_apps_from_file: {e}", exc_info=True)
            self._reset_ui_after_load_error()
    
    def _reset_ui_after_load_error(self):
        """Reset UI elements after a load error."""
        # Only try to update UI if components exist
        if hasattr(self.main_controller, 'app_scan_status_label') and self.main_controller.app_scan_status_label:
            self.main_controller.app_scan_status_label.setText("App Scan: Error loading file.")
            
        if hasattr(self.main_controller, 'health_app_dropdown') and self.main_controller.health_app_dropdown:
            self.main_controller.health_app_dropdown.clear()
            self.main_controller.health_app_dropdown.addItem("Select target app (Scan/Load Error)", None)
            
        self.health_apps_data = []
        
        # Clear the package and activity fields if they exist
        if hasattr(self.main_controller, 'config_widgets'):
            config_widgets = self.main_controller.config_widgets
            if 'APP_PACKAGE' in config_widgets and config_widgets['APP_PACKAGE']:
                config_widgets['APP_PACKAGE'].setText("")
            if 'APP_ACTIVITY' in config_widgets and config_widgets['APP_ACTIVITY']:
                config_widgets['APP_ACTIVITY'].setText("")
    
    def _populate_app_dropdown(self):
        """Populate the health app dropdown with the loaded data."""
        try:
            # Check if UI components are available
            if not hasattr(self.main_controller, 'health_app_dropdown') or not self.main_controller.health_app_dropdown:
                self.main_controller.log_message("Health app dropdown not available. Cannot populate.", 'orange')
                return

            self.main_controller.health_app_dropdown.clear()
            self.main_controller.health_app_dropdown.addItem("Select target app...", None)  # Default item

            if not self.health_apps_data:
                self.main_controller.log_message("No health apps available to populate dropdown.", 'orange')
                return

            # Try to restore last selected app if it exists
            last_selected_app = getattr(self.main_controller, 'last_selected_app', {})
            last_selected_package = last_selected_app.get('package_name', '')
            selected_index = 0  # Default to 0 (Select target app...)

            for i, app_info in enumerate(self.health_apps_data, start=1):
                app_name = app_info.get('app_name', 'Unknown App')
                package_name = app_info.get('package_name', '')
                display_name = f"{app_name} ({package_name})"
                self.main_controller.health_app_dropdown.addItem(display_name, app_info)
                
                # Check if this matches the last selected app
                if package_name == last_selected_package:
                    selected_index = i

            # Set the current index to restore last selection
            self.main_controller.health_app_dropdown.setCurrentIndex(selected_index)
        except Exception as e:
            self.main_controller.log_message(f"Error populating app dropdown: {e}", 'red')
