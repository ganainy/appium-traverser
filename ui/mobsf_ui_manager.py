#!/usr/bin/env python3
# ui/mobsf_ui_manager.py - MobSF integration UI management

import logging
import os
from typing import Optional

import requests
from PySide6.QtCore import QObject, QProcess, Signal, Slot


class MobSFUIManager(QObject):
    """Manages MobSF integration for the Appium Crawler Controller UI."""
    
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
                # Play success sound
                if hasattr(self.main_controller, '_audio_alert'):
                    self.main_controller._audio_alert('finish')
            else:
                self.main_controller.log_message(f"MobSF connection failed with status code: {response.status_code}", 'red')
                self.main_controller.log_message(f"Response: {response.text}", 'red')
                # Play error sound
                if hasattr(self.main_controller, '_audio_alert'):
                    self.main_controller._audio_alert('error')
        except requests.RequestException as e:
            self.main_controller.log_message(f"MobSF connection error: {e}", 'red')
            # Play error sound
            if hasattr(self.main_controller, '_audio_alert'):
                self.main_controller._audio_alert('error')

        self.main_controller.log_message(f"\nAPI URL used: {test_url}", 'blue')
        self.main_controller.log_message("Important Tips:", 'blue')
        self.main_controller.log_message("1. Make sure MobSF server is running.", 'blue')
        self.main_controller.log_message("2. Verify the API URL format - should be 'http://<host>:<port>/api/v1'.", 'blue')
        self.main_controller.log_message("3. Ensure you're using the correct API key from your MobSF instance.", 'blue')
        self.main_controller.log_message("4. Check the MobSF API documentation for valid endpoints.", 'blue')
        self.main_controller.log_message("5. You can find your API key in the MobSF web interface under 'Settings'.", 'blue')


# Import here to avoid circular imports
import sys
