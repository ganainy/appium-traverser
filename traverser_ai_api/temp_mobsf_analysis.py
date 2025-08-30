
import sys
import os
import json
import logging
import requests
import subprocess
import re
import time
from typing import Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ensure unbuffered stdout for real-time streaming to QProcess
try:
    sys.stdout.reconfigure(line_buffering=True, write_through=True)
except Exception:
    try:
        import os as _os
        _os.environ['PYTHONUNBUFFERED'] = '1'
    except Exception:
        pass

# Force all prints to flush immediately
import builtins as _bi
def _print_flush(*args, **kwargs):
    kwargs.setdefault('flush', True)
    return _bi.print(*args, **kwargs)
print = _print_flush

class MobSFAnalyzer:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {"Authorization": api_key}
        self.scan_results_dir = os.path.join(os.path.dirname(__file__), "output_data", "mobsf_scan_results")
        os.makedirs(self.scan_results_dir, exist_ok=True)
        
    def extract_apk(self, package_name):
        print(f"Extracting APK for {package_name} from device...")
        try:
            # Get the path of the APK on the device
            path_cmd = ["adb", "shell", "pm", "path", package_name]
            result = subprocess.run(path_cmd, capture_output=True, text=True)
            
            if result.returncode != 0 or not result.stdout.strip():
                print(f"Error: Failed to get APK path: {result.stderr}")
                return None
            
            # Parse the APK path(s) robustly; output can contain multiple lines for split APKs
            raw_output = result.stdout.strip()
            pkg_lines = [ln.strip() for ln in raw_output.splitlines() if ln.strip().startswith('package:')]
            apk_candidates = [ln.split(':', 1)[1].strip() for ln in pkg_lines if ':' in ln]
            # Prefer base.apk if present
            base_candidates = [p for p in apk_candidates if p.endswith('/base.apk') or 'base.apk' in p]
            if base_candidates:
                apk_path = base_candidates[0]
            elif apk_candidates:
                apk_path = apk_candidates[0]
            else:
                print(f"Error: Failed to parse APK path from output: {raw_output}")
                return None
            
            # Create output directory if it doesn't exist
            output_dir = os.path.join(os.path.dirname(__file__), "output_data", "extracted_apks")
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate the local APK filename
            local_apk = os.path.join(output_dir, f"{package_name}.apk")
            
            # Pull the APK from the device
            print(f"Pulling APK from device: {apk_path} -> {local_apk}")
            pull_cmd = ["adb", "pull", apk_path, local_apk]
            pull_result = subprocess.run(pull_cmd, capture_output=True, text=True)
            
            if pull_result.returncode != 0:
                print(f"Error: Failed to pull APK: {pull_result.stderr}")
                return None
            
            print(f"Successfully extracted APK to {local_apk}")
            return local_apk
            
        except Exception as e:
            print(f"Error extracting APK: {str(e)}")
            return None
            
    def upload_apk(self, apk_path):
        print(f"Uploading APK {apk_path} to MobSF...")
        if not os.path.exists(apk_path):
            print(f"Error: APK file not found: {apk_path}")
            return False, {"error": "APK file not found"}
        
        try:
            with open(apk_path, 'rb') as apk_file:
                files = {'file': (os.path.basename(apk_path), apk_file, 'application/octet-stream')}
                response = requests.post(f"{self.api_url}/upload", headers=self.headers, files=files)
                
                if response.status_code == 200:
                    return True, response.json()
                else:
                    print(f"Error: Upload failed with status code {response.status_code}: {response.text}")
                    return False, {"error": f"Upload failed: {response.text}"}
        except Exception as e:
            print(f"Error uploading APK: {str(e)}")
            return False, {"error": str(e)}
            
    def scan_apk(self, file_hash, rescan=False):
        print(f"Starting scan for file hash: {file_hash}")
        data = {
            'hash': file_hash,
            're_scan': 1 if rescan else 0
        }
        try:
            response = requests.post(f"{self.api_url}/scan", headers=self.headers, data=data)
            if response.status_code == 200:
                return True, response.json()
            else:
                print(f"Error: Scan failed with status code {response.status_code}: {response.text}")
                return False, {"error": f"Scan failed: {response.text}"}
        except Exception as e:
            print(f"Error scanning APK: {str(e)}")
            return False, {"error": str(e)}
            
    def get_scan_logs(self, file_hash):
        data = {'hash': file_hash}
        try:
            response = requests.post(f"{self.api_url}/scan_logs", headers=self.headers, data=data)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, {"error": f"Failed to get logs: {response.text}"}
        except Exception as e:
            return False, {"error": str(e)}
            
    def get_report_json(self, file_hash):
        data = {'hash': file_hash}
        try:
            response = requests.post(f"{self.api_url}/report_json", headers=self.headers, data=data)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, {"error": f"Failed to get JSON report: {response.text}"}
        except Exception as e:
            return False, {"error": str(e)}
            
    def get_pdf_report(self, file_hash):
        data = {'hash': file_hash}
        try:
            response = requests.post(f"{self.api_url}/download_pdf", headers=self.headers, data=data)
            if response.status_code == 200:
                return True, response.content
            else:
                return False, {"error": f"Failed to get PDF report: {response.text}"}
        except Exception as e:
            return False, {"error": str(e)}
            
    def save_pdf_report(self, file_hash, output_path=None):
        success, pdf_content = self.get_pdf_report(file_hash)
        if not success:
            print(f"Error: Failed to get PDF report: {pdf_content}")
            return None
        
        if output_path is None:
            output_path = os.path.join(self.scan_results_dir, f"{file_hash}_report.pdf")
        
        try:
            with open(output_path, 'wb') as pdf_file:
                pdf_file.write(pdf_content)
            print(f"PDF report saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"Error saving PDF report: {str(e)}")
            return None
            
    def save_json_report(self, file_hash, output_path=None):
        success, report = self.get_report_json(file_hash)
        if not success:
            print(f"Error: Failed to get JSON report: {report}")
            return None
        
        if output_path is None:
            output_path = os.path.join(self.scan_results_dir, f"{file_hash}_report.json")
        
        try:
            with open(output_path, 'w', encoding='utf-8') as json_file:
                json.dump(report, json_file, indent=4)
            print(f"JSON report saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"Error saving JSON report: {str(e)}")
            return None
            
    def get_security_score(self, file_hash):
        data = {'hash': file_hash}
        try:
            response = requests.post(f"{self.api_url}/scorecard", headers=self.headers, data=data)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, {"error": f"Failed to get security score: {response.text}"}
        except Exception as e:
            return False, {"error": str(e)}
            
    def run_analysis(self, package_name):
        print(f"Starting MobSF analysis for {package_name}...")
        
        # Extract APK
        apk_path = self.extract_apk(package_name)
        if not apk_path:
            return False, {"error": "Failed to extract APK from device"}
            
        # Upload APK
        upload_success, upload_result = self.upload_apk(apk_path)
        if not upload_success:
            return False, {"error": f"Failed to upload APK: {upload_result}"}
            
        file_hash = upload_result.get('hash')
        if not file_hash:
            return False, {"error": "No file hash in upload response"}
            
        # Start scan (returns quickly); we'll poll logs until completion
        scan_success, scan_result = self.scan_apk(file_hash)
        if not scan_success:
            return False, {"error": f"Failed to scan APK: {scan_result}"}
            
        # Stream scan logs until completion
        print("Streaming MobSF scan logs...")
        last_count = 0
        start_time = time.time()
        timeout = 20 * 60  # 20 minutes.
        while True:
            logs_success, logs = self.get_scan_logs(file_hash)
            if logs_success and isinstance(logs, dict) and isinstance(logs.get('logs'), list):
                entries = logs['logs']
                new_entries = entries[last_count:]
                for entry in new_entries:
                    ts = entry.get('timestamp') or entry.get('time') or ''
                    evt = entry.get('event') or entry.get('title') or ''
                    stat = entry.get('status') or entry.get('result') or entry.get('error') or ''
                    # Build the line within the generated script using its own f-string
                    line = f"{ts} {evt} {stat}".strip()
                    if line:
                        print(line)
                last_count = len(entries)

                if entries:
                    latest_status = (entries[-1].get('status') or '').lower()
                    if 'completed' in latest_status:
                        print("Scan completed.")
                        break
                    if 'error' in latest_status or 'failed' in latest_status:
                        print(f"Scan finished with status: {entries[-1].get('status')}")
                        break
            else:
                print("Waiting for scan logs...")

            if time.time() - start_time > timeout:
                print("Timed out waiting for scan to complete.")
                break
            time.sleep(2)

        # Scan should be completed at this point based on log status
        
        # Save reports
        pdf_path = self.save_pdf_report(file_hash)
        json_path = self.save_json_report(file_hash)        # Get security score
        score_success, scorecard = self.get_security_score(file_hash)
        if score_success:
            print(f"Security Score: {scorecard}")
        
        # Prepare summary
        summary = {
            "package_name": package_name,
            "file_hash": file_hash,
            "apk_path": apk_path,
            "pdf_report": pdf_path,
            "json_report": json_path,
            "security_score": scorecard if score_success else "Unknown"
        }
        
        print("MobSF analysis completed successfully!")
        print(f"PDF Report: {pdf_path}")
        print(f"JSON Report: {json_path}")
        
        return True, summary

# Main analysis function
def main():
    package_name = "de.gesund.app"
    api_url = "http://localhost:8000/api/v1"
    api_key = "64ab822fd55ff843d04b29488abe49ced367e435b2efe577a4ab080ec0280c73"
    
    analyzer = MobSFAnalyzer(api_url, api_key)
    success, result = analyzer.run_analysis(package_name)
    
    if success:
        print("Analysis completed successfully.")
        print(f"Results saved to {result.get('pdf_report')} and {result.get('json_report')}")
        
        if 'security_score' in result and result['security_score'] != "Unknown":
            print("\nSecurity Score Summary:")
            score_data = result['security_score']
            for category, score in score_data.items():
                if isinstance(score, dict) and 'value' in score:
                    print(f"{category}: {score['value']}")
            
    else:
        print(f"Analysis failed: {result.get('error', 'Unknown error')}")
        
if __name__ == "__main__":
    main()
