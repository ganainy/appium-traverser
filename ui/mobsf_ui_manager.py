#!/usr/bin/env python3
# ui/mobsf_ui_manager.py - MobSF integration UI management

import logging
import os
from typing import Optional

import requests
from PySide6.QtCore import QObject, QProcess, Signal, Slot


class MobSFUIManager(QObject):
    """Manages MobSF integration for the Appium Crawler Controller UI."""
    
    # Signals
    analysis_started = Signal()
    analysis_finished = Signal(bool, str)  # success, message
    
    def __init__(self, main_controller):
        """
        Initialize the MobSF UI manager.
        
        Args:
            main_controller: The main UI controller
        """
        super().__init__()
        self.main_controller = main_controller
        self.config = main_controller.config
        self.api_dir = self.config.BASE_DIR
        self.mobsf_test_process: Optional[QProcess] = None
        self.mobsf_analysis_process: Optional[QProcess] = None
    
    @Slot()
    def test_mobsf_connection(self):
        """Test the connection to the MobSF server."""
        # Check if MobSF analysis is enabled
        if not self.main_controller.config_widgets['ENABLE_MOBSF_ANALYSIS'].isChecked():
            self.main_controller.log_message("Error: MobSF Analysis is not enabled. Please enable it in settings.", 'red')
            return
            
        self.main_controller.log_message("Testing MobSF connection...", 'blue')
        api_url = self.main_controller.config_widgets['MOBSF_API_URL'].text().strip()
        api_key = self.main_controller.config_widgets['MOBSF_API_KEY'].text().strip()

        if not api_url or not api_key:
            self.main_controller.log_message("Error: MobSF API URL and API Key are required.", 'red')
            return

        headers = {'Authorization': api_key}
        
        # Use the /scans endpoint to get recent scans, which is a good way to test the connection
        test_url = f"{api_url.rstrip('/')}/scans"
        
        try:
            response = requests.get(test_url, headers=headers, timeout=10)
            if response.status_code == 200:
                self.main_controller.log_message("MobSF connection successful!", 'green')
                self.main_controller.log_message(f"Server response: {response.json()}", 'blue')
            else:
                self.main_controller.log_message(f"MobSF connection failed with status code: {response.status_code}", 'red')
                self.main_controller.log_message(f"Response: {response.text}", 'red')
        except requests.RequestException as e:
            self.main_controller.log_message(f"MobSF connection error: {e}", 'red')

        self.main_controller.log_message(f"\nAPI URL used: {test_url}", 'blue')
        self.main_controller.log_message("Important Tips:", 'blue')
        self.main_controller.log_message("1. Make sure MobSF server is running.", 'blue')
        self.main_controller.log_message("2. Verify the API URL format - should be 'http://<host>:<port>/api/v1'.", 'blue')
        self.main_controller.log_message("3. Ensure you're using the correct API key from your MobSF instance.", 'blue')
        self.main_controller.log_message("4. Check the MobSF API documentation for valid endpoints.", 'blue')
        self.main_controller.log_message("5. You can find your API key in the MobSF web interface under 'Settings'.", 'blue')
    
    @Slot()
    def run_mobsf_analysis(self):
        """Run MobSF analysis for the currently selected app."""
        # Check if MobSF analysis is enabled
        if not self.main_controller.config_widgets['ENABLE_MOBSF_ANALYSIS'].isChecked():
            self.main_controller.log_message("Error: MobSF Analysis is not enabled. Please enable it in settings.", 'red')
            return
        
        # Check if an app is selected
        app_package = self.main_controller.config_widgets['APP_PACKAGE'].text()
        if not app_package:
            self.main_controller.log_message("Error: No app selected. Please select an app first.", 'red')
            return
            
        # Check if MobSF settings are configured
        api_url = self.main_controller.config_widgets['MOBSF_API_URL'].text()
        api_key = self.main_controller.config_widgets['MOBSF_API_KEY'].text()
        
        if not api_url:
            self.main_controller.log_message("Error: MobSF API URL is required.", 'red')
            return
            
        # Security Check: If API key is empty, prompt user to add it to .env file
        if not api_key:
            self.main_controller.log_message(
                "Error: MobSF API Key is required. Add it to .env file as MOBSF_API_KEY=your_key", 'red'
            )
            return
            
        # Run MobSF analysis in a separate process
        if not hasattr(self, 'mobsf_analysis_process') or self.mobsf_analysis_process is None:
            self.main_controller.log_message(f"Starting MobSF analysis for package: {app_package}...", 'blue')
            self.main_controller.run_mobsf_analysis_btn.setEnabled(False)
            # Show busy overlay
            try:
                self.main_controller.show_busy("Running MobSF analysis...")
            except Exception:
                pass
            
            # Create a temporary script to run the analysis
            temp_script_path = os.path.join(self.api_dir, "temp_mobsf_analysis.py")
            self._create_temp_mobsf_script(temp_script_path, app_package, api_url, api_key)
            
            # Set up and start the process
            self.mobsf_analysis_process = QProcess()
            self.mobsf_analysis_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            self.mobsf_analysis_process.readyReadStandardOutput.connect(self._on_mobsf_analysis_output)
            self.mobsf_analysis_process.finished.connect(self._on_mobsf_analysis_finished)
            
            python_exe = os.path.abspath(sys.executable)
            self.mobsf_analysis_process.start(python_exe, [temp_script_path])
    
    def _create_temp_mobsf_script(self, script_path: str, package_name: str, api_url: str, api_key: str):
        """Create a temporary script to run MobSF analysis."""
        # Convert Windows backslashes to forward slashes for Python paths
        api_dir_path = self.api_dir.replace('\\', '/')
        
        # Create raw strings to avoid Windows path escape issues
        script_content = f"""#!/usr/bin/env python3
# Temporary script for MobSF analysis

import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the parent directory to sys.path to import the MobSF manager
sys.path.insert(0, r'{api_dir_path}')

try:
    from config.app_config import Config
    from mobsf_manager import MobSFManager
    
    # Initialize Config using default SQLite-backed storage
    config = Config()
    
    # Set MobSF configuration
    config.set("MOBSF_API_URL", '{api_url}')
    config.set("MOBSF_API_KEY", '{api_key}')
    config.set("APP_PACKAGE", '{package_name}')
    
    # Initialize MobSF Manager
    mobsf_manager = MobSFManager(config)
    
    # Run the analysis
    print("Starting MobSF analysis for package: {package_name}")
    success, result = mobsf_manager.perform_complete_scan('{package_name}')
    
    if success:
        print("MobSF analysis completed successfully!")
        print(f"PDF Report: {{result.get('pdf_report', 'Not available')}}")
        print(f"JSON Report: {{result.get('json_report', 'Not available')}}")
        security_score = result.get('security_score', {{}})
        if isinstance(security_score, dict):
            print(f"Security Score: {{security_score.get('score', 'Not available')}}")
        else:
            print(f"Security Score: {{security_score}}")
    else:
        print(f"MobSF analysis failed: {{result.get('error', 'Unknown error')}}")
    
except Exception as e:
    print(f"Error running MobSF analysis: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
    
    @Slot()
    def _on_mobsf_analysis_output(self):
        """Handle output from the MobSF analysis process."""
        if self.mobsf_analysis_process and self.mobsf_analysis_process.bytesAvailable() > 0:
            output = bytes(self.mobsf_analysis_process.readAllStandardOutput().data()).decode('utf-8', errors='replace')
            self.main_controller.log_message(output.strip())
    
    @Slot(int, QProcess.ExitStatus)
    def _on_mobsf_analysis_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle completion of the MobSF analysis."""
        # Clean up temporary script
        script_path = os.path.join(self.api_dir, "temp_mobsf_analysis.py")
        if os.path.exists(script_path):
            try:
                os.remove(script_path)
            except Exception as e:
                logging.warning(f"Could not remove temporary script: {e}")
                
        if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            self.main_controller.log_message("MobSF analysis process completed.", 'green')
        else:
            self.main_controller.log_message(f"MobSF analysis process failed with exit code: {exit_code}", 'red')
            
        self.main_controller.run_mobsf_analysis_btn.setEnabled(True)
        # Hide busy overlay
        try:
            self.main_controller.hide_busy()
        except Exception:
            pass
        self.mobsf_analysis_process = None


# Import here to avoid circular imports
import sys
