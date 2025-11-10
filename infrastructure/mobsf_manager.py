#!/usr/bin/env python3
# mobsf_manager.py

import base64
import json
import logging
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests



class MobSFManager:
    """
    Manager class for interacting with MobSF's REST API for static analysis
    of Android applications.
    """

    def __init__(self, app_config: Config):
        """
        Initialize the MobSF Manager with configuration settings
        """
        from config.urls import ServiceURLs
        self.cfg = app_config
        self.api_key = self.cfg.get('MOBSF_API_KEY', '')
        self.api_url = self.cfg.get('MOBSF_API_URL', ServiceURLs.MOBSF)
        self.headers = {
            'Authorization': self.api_key
        }
        
        # Ensure OUTPUT_DATA_DIR exists
        output_dir = str(self.cfg.OUTPUT_DATA_DIR if hasattr(self.cfg, 'OUTPUT_DATA_DIR') else self.cfg.get('OUTPUT_DATA_DIR', 'output_data'))
        # Use session directory for MobSF results if available
        session_dir = self.cfg.SESSION_DIR if hasattr(self.cfg, 'SESSION_DIR') else output_dir
        self.scan_results_dir = os.path.join(session_dir, 'mobsf_scan_results')
        os.makedirs(self.scan_results_dir, exist_ok=True)
        logging.debug(f"MobSFManager initialized with API URL: {self.api_url}")

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

            # Create output directory if it doesn't exist
            output_dir_base = str(self.cfg.OUTPUT_DATA_DIR if hasattr(self.cfg, 'OUTPUT_DATA_DIR') else self.cfg.get('OUTPUT_DATA_DIR', 'output_data'))
            session_dir = self.cfg.SESSION_DIR if hasattr(self.cfg, 'SESSION_DIR') else output_dir_base
            output_dir = os.path.join(session_dir, 'extracted_apk')
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate the local APK filename
            local_apk = os.path.join(output_dir, f"{package_name}.apk")
            
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

    def perform_complete_scan(self, package_name: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Perform a complete scan workflow:
        1. Extract APK from device
        2. Upload to MobSF
        3. Scan the APK
        4. Get and save reports
        
        Args:
            package_name: The package name to scan
            
        Returns:
            Tuple of (success, scan_summary)
        """
        # Extract APK from device
        apk_path = self.extract_apk_from_device(package_name)
        if not apk_path:
            return False, {"error": "Failed to extract APK from device"}
        
        # Upload APK to MobSF
        upload_success, upload_result = self.upload_apk(apk_path)
        if not upload_success:
            return False, {"error": f"Failed to upload APK: {upload_result}"}
        
        file_hash = upload_result.get('hash')
        if not file_hash:
            return False, {"error": "No file hash in upload response"}
        
        # Scan the APK
        scan_success, scan_result = self.scan_apk(file_hash)
        if not scan_success:
            return False, {"error": f"Failed to scan APK: {scan_result}"}
        
        # Wait for scan to complete
        max_retries = 30
        for _ in range(max_retries):
            logs_success, logs = self.get_scan_logs(file_hash)
            if logs_success and 'logs' in logs:
                latest_log = logs['logs'][-1] if logs['logs'] else {}
                status = latest_log.get('status', '')
                if 'Completed' in status or 'Error' in status:
                    break
            time.sleep(2)
        
        # Save reports
        pdf_path = self.save_pdf_report(file_hash)
        json_path = self.save_json_report(file_hash)
        
        # Get security score
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
        
        logging.debug(f"Completed MobSF scan for {package_name}")
        return True, summary
