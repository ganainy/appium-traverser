#!/usr/bin/env python3
# mobsf_manager.py

import base64
import json
import logging
import os
import re
import subprocess
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union

import requests

if TYPE_CHECKING:
    from config.app_config import Config


class MobSFManager:
    """
    Manager class for interacting with MobSF's REST API for static analysis
    of Android applications.
    """

    def __init__(self, app_config: 'Config'):
        """
        Initialize the MobSF Manager with configuration settings.
        Note: This should only be instantiated when MobSF analysis is enabled.
        """
        from config.urls import ServiceURLs
        self.cfg = app_config
        self.api_key = self.cfg.get('MOBSF_API_KEY') or ''
        # MOBSF_API_URL must be set in configuration (no hardcoded fallback)
        self.api_url = self.cfg.get('MOBSF_API_URL')
        if not self.api_url:
            raise ValueError("MOBSF_API_URL must be set in configuration")
        self.headers = {
            'Authorization': self.api_key
        }
        
        # --- MODIFICATION ---
        # We REMOVE the path resolution from __init__
        # It will be handled by a property method (scan_results_dir)
        # or within the specific methods (extract_apk_from_device)
        
        # self.scan_results_dir = os.path.join(session_dir, 'mobsf_scan_results')
        # os.makedirs(self.scan_results_dir, exist_ok=True)
        logging.debug(f"MobSFManager initialized with API URL: {self.api_url}")

    @property
    def scan_results_dir(self) -> str:
        """
        Lazily resolve the scan results directory path.
        This ensures SESSION_DIR is resolved by the time we need it.
        """
        session_dir = None
        
        # Try 1: Use SESSION_DIR property (resolves template via SessionPathManager)
        try:
            # Trust the SESSION_DIR property to return the fully resolved path
            session_dir = str(self.cfg.SESSION_DIR)
            # A template check is only useful for a *warning*
            if '{' in session_dir or '}' in session_dir:
                logging.warning(f"SESSION_DIR property still contains a template: {session_dir}. Paths may be incorrect.")
                # Don't set to None; let it use the template path if that's what was returned
                # This makes the error more obvious (a folder named "{session_dir}")
                # Re-thinking: No, falling back is safer than creating a literal template dir.
                session_dir = None
        except Exception as e:
            logging.warning(f"Could not get SESSION_DIR property: {e}, trying fallback")
        
        # Try 2: Fall back to OUTPUT_DATA_DIR
        if not session_dir:
            try:
                output_dir = self.cfg.OUTPUT_DATA_DIR if hasattr(self.cfg, 'OUTPUT_DATA_DIR') else self.cfg.get('OUTPUT_DATA_DIR')
                if not output_dir:
                    logging.warning("OUTPUT_DATA_DIR is not set, cannot determine session directory")
                    session_dir = None
                else:
                    session_dir = str(output_dir)
                if '{' in session_dir or '}' in session_dir:
                    logging.warning(f"OUTPUT_DATA_DIR also contains template: {session_dir}, using hardcoded fallback")
                    session_dir = None
            except Exception as e:
                logging.warning(f"Could not get OUTPUT_DATA_DIR: {e}, using hardcoded fallback")
        
        # Try 3: Final hardcoded fallback
        if not session_dir:
            logging.error("All path resolution attempts failed, using hardcoded 'output_data' fallback for MobSF results.")
            session_dir = 'output_data'
        
        # Create scan results directory
        results_path = os.path.join(session_dir, 'mobsf_scan_results')
        results_path = os.path.abspath(results_path) # Ensure it's an absolute path
        os.makedirs(results_path, exist_ok=True)
        return results_path


    def _make_api_request(self, endpoint: str, method: str = 'GET', 
                          data: Optional[Dict[str, Any]] = None, 
                          files: Optional[Dict[str, Any]] = None,
                          stream: bool = False) -> Tuple[bool, Any]:
        """
        Makes an API request to MobSF
        
        Args:
            endpoint: API endpoint (without the base URL)
            method: HTTP method (GET, POST)
            data: Form data for POST requests
            files: Files for multipart form submissions
            stream: Whether to stream the response
            
        Returns:
            Tuple of (success, response_data)
        """
        # Ensure endpoint doesn't start with a slash to prevent double slashes
        endpoint = endpoint.lstrip('/')
        
        # Ensure API URL has a scheme and is properly formatted with a trailing slash
        api_url = self.api_url
        if not api_url.startswith(('http://', 'https://')):
            api_url = f"http://{api_url}"
        api_url = api_url.rstrip('/') + '/'
        
        url = f"{api_url}{endpoint}"
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers, stream=stream)
            else:  # POST
                response = requests.post(url, headers=self.headers, data=data, files=files, stream=stream)
            
            if response.status_code == 200:
                if stream:
                    return True, response
                if response.headers.get('Content-Type') == 'application/pdf':
                    return True, response.content
                try:
                    return True, response.json()
                except ValueError:
                    return True, response.text
            else:
                logging.error(f"API request failed: {url}, Status: {response.status_code}, Response: {response.text}")
                return False, f"API Error: {response.status_code} - {response.text}"
        except requests.RequestException as e:
            logging.error(f"Request exception for {url}: {str(e)}")
            return False, f"Request Error: {str(e)}"
        except Exception as e:
            logging.error(f"Unexpected error during API request to {url}: {str(e)}")
            return False, f"Error: {str(e)}"

    def extract_apk_from_device(self, package_name: str) -> Optional[str]:
        """
        Extract the APK file from a connected Android device using ADB
        
        Args:
            package_name: The package name of the app to extract
            
        Returns:
            Path to the extracted APK file, or None if extraction failed
        """
        # Guard: Only extract APK if MobSF analysis is enabled
        if not self.cfg.get('ENABLE_MOBSF_ANALYSIS', False):
            logging.warning("MobSF analysis is disabled, skipping APK extraction")
            return None
        
        try:
            logging.debug(f"Extracting APK for package {package_name} from connected device")
            
            # Get the path of the APK on the device
            path_cmd = ["adb", "shell", "pm", "path", package_name]
            result = subprocess.run(path_cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode != 0 or not result.stdout.strip():
                logging.error(f"Failed to get APK path: {result.stderr}")
                return None
            
            # The output can contain multiple paths for split APKs.
            # The format is "package:/path/to/apk". We use regex to handle potential variations in line endings.
            raw_output = result.stdout.strip()
            apk_paths = re.findall(r'package:(.*)', raw_output)

            if not apk_paths:
                logging.error(f"Failed to parse APK path from output: {raw_output}")
                return None

            base_apk_path = None
            for path in apk_paths:
                # The relevant path is the one containing "base.apk"
                if 'base.apk' in path:
                    base_apk_path = path.strip()
                    break
            
            # If no base.apk is found, take the first path as a fallback
            if not base_apk_path and apk_paths:
                base_apk_path = apk_paths[0].strip()

            if not base_apk_path:
                logging.error("Could not find a valid APK path from 'pm path' output.")
                return None
            
            logging.debug(f"Found base APK path: {base_apk_path}")

            # --- MODIFIED PATH RESOLUTION ---
            # Resolve the path *now*, not in __init__
            session_dir = None
            
            # Try 1: Use SESSION_DIR property
            try:
                session_dir = str(self.cfg.SESSION_DIR)
                if '{' in session_dir or '}' in session_dir:
                    logging.warning(f"SESSION_DIR property still contains a template: {session_dir}. Fallback.")
                    session_dir = None
            except Exception as e:
                logging.warning(f"Could not get SESSION_DIR property: {e}, trying fallback")
            
            # Try 2: Fall back to OUTPUT_DATA_DIR
            if not session_dir:
                try:
                    output_dir_base = self.cfg.OUTPUT_DATA_DIR if hasattr(self.cfg, 'OUTPUT_DATA_DIR') else self.cfg.get('OUTPUT_DATA_DIR')
                    if not output_dir_base:
                        logging.warning("OUTPUT_DATA_DIR is not set, cannot determine session directory")
                        session_dir = None
                    else:
                        session_dir = str(output_dir_base)
                    # Check if it's still a template
                    if '{' in session_dir or '}' in session_dir:
                        logging.warning(f"OUTPUT_DATA_DIR also contains template: {session_dir}, using hardcoded fallback")
                        session_dir = None
                except Exception as e:
                    logging.warning(f"Could not get OUTPUT_DATA_DIR: {e}, using hardcoded fallback")
            
            # Try 3: Final hardcoded fallback
            if not session_dir:
                logging.error("All path resolution attempts failed, using hardcoded 'output_data' fallback for APK extraction.")
                session_dir = 'output_data'
            
            output_dir = os.path.join(session_dir, 'extracted_apk')
            output_dir = os.path.abspath(output_dir) # Ensure absolute path
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate the local APK filename
            local_apk = os.path.join(output_dir, f"{package_name}.apk")
            # --- END MODIFIED BLOCK ---
            
            # Pull the APK from the device
            logging.debug(f"Pulling APK from {base_apk_path} to {local_apk}")
            pull_cmd = ["adb", "pull", base_apk_path, local_apk]
            pull_result = subprocess.run(pull_cmd, capture_output=True, text=True, encoding='utf-8')
            
            if pull_result.returncode != 0:
                logging.error(f"Failed to pull APK: {pull_result.stderr}")
                return None
            
            logging.debug(f"Successfully extracted APK to {local_apk}")
            return local_apk
            
        except Exception as e:
            logging.error(f"Error extracting APK: {str(e)}")
            return None

    def upload_apk(self, apk_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Upload an APK file to MobSF for analysis
        
        Args:
            apk_path: Path to the APK file
            
        Returns:
            Tuple of (success, response_data)
        """
        if not os.path.exists(apk_path):
            logging.error(f"APK file not found: {apk_path}")
            return False, {"error": "APK file not found"}
        
        try:
            logging.debug(f"Uploading APK {apk_path} to MobSF")
            with open(apk_path, 'rb') as apk_file:
                files = {'file': (os.path.basename(apk_path), apk_file, 'application/octet-stream')}
                return self._make_api_request('upload', 'POST', files=files)
        except Exception as e:
            logging.error(f"Error uploading APK: {str(e)}")
            return False, {"error": str(e)}

    def scan_apk(self, file_hash: str, rescan: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """
        Scan an uploaded APK file
        
        Args:
            file_hash: The hash of the uploaded file
            rescan: Whether to rescan an already analyzed file
            
        Returns:
            Tuple of (success, scan_results)
        """
        data = {
            'hash': file_hash,
            're_scan': 1 if rescan else 0
        }
        logging.debug(f"Starting scan for file hash: {file_hash}")
        return self._make_api_request('scan', 'POST', data=data)

    def get_scan_logs(self, file_hash: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Get scan logs for a file
        
        Args:
            file_hash: The hash of the file
            
        Returns:
            Tuple of (success, logs)
        """
        data = {'hash': file_hash}
        return self._make_api_request('scan_logs', 'POST', data=data)

    def get_report_json(self, file_hash: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Get JSON report for a scanned file
        
        Args:
            file_hash: The hash of the file
            
        Returns:
            Tuple of (success, report)
        """
        data = {'hash': file_hash}
        return self._make_api_request('report_json', 'POST', data=data)

    def get_pdf_report(self, file_hash: str) -> Tuple[bool, bytes]:
        """
        Get PDF report for a scanned file
        
        Args:
            file_hash: The hash of the file
            
        Returns:
            Tuple of (success, pdf_content)
        """
        data = {'hash': file_hash}
        return self._make_api_request('download_pdf', 'POST', data=data)

    def save_pdf_report(self, file_hash: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Save the PDF report to a file
        
        Args:
            file_hash: The hash of the file
            output_path: Optional path to save the PDF, if not provided a default path is used
            
        Returns:
            Path to the saved PDF file, or None if saving failed
        """
        success, pdf_content = self.get_pdf_report(file_hash)
        if not success:
            logging.error(f"Failed to get PDF report: {pdf_content}")
            return None
        
        if output_path is None:
            # --- MODIFICATION ---
            # This now calls the @property method, which resolves the path
            # just-in-time.
            output_path = os.path.join(self.scan_results_dir, f"{file_hash}_report.pdf")
        
        try:
            with open(output_path, 'wb') as pdf_file:
                pdf_file.write(pdf_content)
            logging.debug(f"PDF report saved to: {output_path}")
            return output_path
        except Exception as e:
            logging.error(f"Error saving PDF report: {str(e)}")
            return None

    def save_json_report(self, file_hash: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Save the JSON report to a file
        
        Args:
            file_hash: The hash of the file
            output_path: Optional path to save the JSON, if not provided a default path is used
            
        Returns:
            Path to the saved JSON file, or None if saving failed
        """
        success, report = self.get_report_json(file_hash)
        if not success:
            logging.error(f"Failed to get JSON report: {report}")
            return None
        
        if output_path is None:
            # --- MODIFICATION ---
            # This now calls the @property method, which resolves the path
            # just-in-time.
            output_path = os.path.join(self.scan_results_dir, f"{file_hash}_report.json")
        
        try:
            with open(output_path, 'w', encoding='utf-8') as json_file:
                json.dump(report, json_file, indent=4)
            logging.debug(f"JSON report saved to: {output_path}")
            return output_path
        except Exception as e:
            logging.error(f"Error saving JSON report: {str(e)}")
            return None

    def get_security_score(self, file_hash: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Get security scorecard for a scanned file
        
        Args:
            file_hash: The hash of the file
            
        Returns:
            Tuple of (success, scorecard)
        """
        data = {'hash': file_hash}
        return self._make_api_request('scorecard', 'POST', data=data)

    def perform_complete_scan(self, package_name: str, log_callback: Optional[Callable[[str, Optional[str]], None]] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Perform a complete scan workflow:
        1. Extract APK from device
        2. Upload to MobSF
        3. Scan the APK
        4. Get and save reports
        
        Args:
            package_name: The package name to scan
            log_callback: Optional callback function to display logs. 
                         Should accept (message: str, color: Optional[str] = None)
            
        Returns:
            Tuple of (success, scan_summary)
        """
        def _log(message: str, color: Optional[str] = None):
            """Helper to log messages via callback or standard logging."""
            if log_callback:
                log_callback(message, color)
            else:
                logging.info(message)
        
        # Double-check that MobSF is enabled before proceeding
        # (This is the check I mentioned - it is correct in your original file)
        if not self.cfg.get('ENABLE_MOBSF_ANALYSIS', False):
            logging.warning("MobSF analysis is disabled, skipping APK extraction and scan")
            return False, {"error": "MobSF analysis is disabled"}
        
        # Extract APK from device
        _log("Extracting APK from device...", 'blue')
        apk_path = self.extract_apk_from_device(package_name)
        if not apk_path:
            return False, {"error": "Failed to extract APK from device"}
        _log(f"APK extracted to: {apk_path}", 'green')
        
        # Upload APK to MobSF
        _log("Uploading APK to MobSF...", 'blue')
        upload_success, upload_result = self.upload_apk(apk_path)
        if not upload_success:
            return False, {"error": f"Failed to upload APK: {upload_result}"}
        
        file_hash = upload_result.get('hash')
        if not file_hash:
            return False, {"error": "No file hash in upload response"}
        _log(f"APK uploaded successfully. Hash: {file_hash}", 'green')
        
        # Scan the APK
        _log("Starting MobSF static analysis...", 'blue')
        scan_success, scan_result = self.scan_apk(file_hash)
        if not scan_success:
            return False, {"error": f"Failed to scan APK: {scan_result}"}
        
        # Wait for scan to complete and display logs
        max_retries = 60  # Increased for longer scans
        last_log_count = 0
        seen_logs = set()  # Track which logs we've already displayed
        
        for attempt in range(max_retries):
            logs_success, logs = self.get_scan_logs(file_hash)
            if logs_success and 'logs' in logs:
                log_entries = logs.get('logs', [])
                
                # Display new log entries
                if log_entries:
                    for log_entry in log_entries[last_log_count:]:
                        # Create a unique identifier for this log entry
                        log_id = f"{log_entry.get('timestamp', '')}-{log_entry.get('status', '')}-{log_entry.get('message', '')}"
                        if log_id not in seen_logs:
                            seen_logs.add(log_id)
                            status = log_entry.get('status', '')
                            message = log_entry.get('message', '')
                            timestamp = log_entry.get('timestamp', '')
                            
                            # Format the log message
                            if message:
                                log_message = f"[MobSF] {message}"
                                if timestamp:
                                    log_message = f"[{timestamp}] {log_message}"
                                
                                # Determine color based on status
                                if 'Error' in status or 'Failed' in status:
                                    color = 'red'
                                elif 'Completed' in status or 'Success' in status:
                                    color = 'green'
                                elif 'Warning' in status:
                                    color = 'orange'
                                else:
                                    color = 'blue'
                                
                                _log(log_message, color)
                            
                            # Also show status if different from message
                            if status and status not in message:
                                _log(f"[MobSF] Status: {status}", 'blue')
                    
                    last_log_count = len(log_entries)
                    
                    # Check if scan is complete
                    latest_log = log_entries[-1] if log_entries else {}
                    status = latest_log.get('status', '')
                    if 'Completed' in status or 'Error' in status or 'Failed' in status:
                        _log(f"Scan completed with status: {status}", 'green' if 'Completed' in status else 'red')
                        break
            else:
                # If we can't get logs, just wait
                if attempt == 0:
                    _log("Waiting for scan to start...", 'blue')
            
            time.sleep(2)
        
        if attempt >= max_retries - 1:
            _log("Warning: Scan may still be in progress. Max retries reached.", 'orange')
        
        # Save reports
        _log("Generating reports...", 'blue')
        pdf_path = self.save_pdf_report(file_hash)
        json_path = self.save_json_report(file_hash)
        
        if pdf_path:
            _log(f"PDF report saved: {pdf_path}", 'green')
        if json_path:
            _log(f"JSON report saved: {json_path}", 'green')
        
        # Get security score
        _log("Retrieving security score...", 'blue')
        score_success, scorecard = self.get_security_score(file_hash)
        
        # Prepare summary
        summary = {
            "package_name": package_name,
            "file_hash": file_hash,
            "apk_path": apk_path,
            "pdf_report": pdf_path,
            "json_report": json_path,
            "security_score": scorecard if score_success else "Unknown"
        }
        
        if score_success and isinstance(scorecard, dict):
            score_value = scorecard.get('score', 'N/A')
            _log(f"Security Score: {score_value}", 'green')
        
        _log("MobSF analysis completed successfully!", 'green')
        logging.debug(f"Completed MobSF scan for {package_name}")
        return True, summary