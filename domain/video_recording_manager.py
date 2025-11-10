# video_recording_manager.py
import logging
import os
import time
from typing import TYPE_CHECKING, Optional

# Assuming AppiumDriver is type hinted correctly
if TYPE_CHECKING:
    from infrastructure.appium_driver import AppiumDriver

# Import your main Config class
try:
    from config.app_config import Config
except ImportError:
    from config.app_config import Config


class VideoRecordingManager:
    """Manager for video recording during crawl sessions."""
    
    def __init__(self, driver: 'AppiumDriver', app_config: Config):
        """
        Initialize the VideoRecordingManager.

        Args:
            driver (AppiumDriver): An instance of the AppiumDriver wrapper.
            app_config (Config): The main application Config object instance.
        """
        self.driver = driver
        self.cfg = app_config
        self.video_recording_enabled: bool = bool(self.cfg.get('ENABLE_VIDEO_RECORDING'))
        
        self.video_file_path: Optional[str] = None
        self._is_recording: bool = False
        
        if self.video_recording_enabled:
            # Validate necessary configs
            required_configs = ['APP_PACKAGE', 'VIDEO_RECORDING_DIR']
            for cfg_key in required_configs:
                if self.cfg.get(cfg_key) is None:
                    raise ValueError(f"VideoRecordingManager: Required config '{cfg_key}' not found or is None.")
            logging.debug("VideoRecordingManager initialized and enabled.")
        else:
            logging.debug("VideoRecordingManager initialized but video recording is DISABLED in config.")
    
    def is_recording(self) -> bool:
        """Returns whether recording is currently active."""
        return self._is_recording
    
    def start_recording(self, run_id: Optional[int] = None, step_num: Optional[int] = None) -> bool:
        """Starts video recording.
        
        Args:
            run_id: Optional run ID for filename
            step_num: Optional step number for filename
            
        Returns:
            True if recording started successfully, False otherwise
        """
        if not self.video_recording_enabled:
            logging.debug("Video recording disabled by config, not starting.")
            return False
        
        if self._is_recording:
            logging.warning("Video recording already started by this manager.")
            return True
        
        try:
            # Generate filename
            target_app_package = str(self.cfg.get('APP_PACKAGE'))
            sanitized_package = target_app_package.replace('.', '_')
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            if run_id is not None and step_num is not None:
                video_filename = f"{sanitized_package}_run{run_id}_step{step_num}_{timestamp}.mp4"
            else:
                video_filename = f"{sanitized_package}_{timestamp}.mp4"
            
            # Get output directory
            # Get the raw template string from config
            video_dir_template = str(self.cfg.get('VIDEO_RECORDING_DIR'))
            
            # Get the *resolved* session directory path from the config property
            resolved_session_dir = str(self.cfg.SESSION_DIR)
            
            # Manually replace the placeholder
            video_output_dir = video_dir_template.replace("{session_dir}", resolved_session_dir)

            os.makedirs(video_output_dir, exist_ok=True)
            
            # Set the full path (we'll save here when stopping)
            self.video_file_path = os.path.join(video_output_dir, video_filename)
            
            # Start recording using Appium's built-in method (no device_path or options needed)
            logging.debug(f"Starting video recording for app: {target_app_package}")
            logging.debug(f"Video will be saved to: {self.video_file_path}")
            
            success = self.driver.start_video_recording()
            
            if success:
                self._is_recording = True
                logging.debug("Video recording started successfully")
            else:
                logging.error("Failed to start video recording")
                self.video_file_path = None
            
            return success
            
        except Exception as e:
            logging.error(f"Error starting video recording: {e}", exc_info=True)
            self.video_file_path = None
            self._is_recording = False
            return False
    
    def stop_recording_and_save(self) -> Optional[str]:
        """Stops video recording and saves the file.
        
        Returns:
            Path to saved video file, or None on error
        """
        if not self.video_recording_enabled:
            logging.debug("Video recording not enabled, skipping stop/save.")
            return None
        
        if not self._is_recording:
            logging.warning("Video recording not started by this manager. Cannot stop/save.")
            return None
        
        try:
            logging.debug("Stopping video recording...")
            
            # Stop recording and get video data (base64 string)
            video_data = self.driver.stop_video_recording()
            self._is_recording = False
            
            if not video_data:
                logging.error("Video recording stopped but no data returned")
                self.video_file_path = None
                return None
            
            if not self.video_file_path:
                logging.error("Video file path not set. Cannot save.")
                return None
            
            # Save video to file (video_data is base64 string)
            success = self.driver.save_video_recording(video_data, self.video_file_path)
            
            if success and os.path.exists(self.video_file_path):
                file_size = os.path.getsize(self.video_file_path)
                if file_size > 0:
                    logging.debug(f"Video recording saved successfully: {os.path.abspath(self.video_file_path)} (size: {file_size} bytes)")
                    saved_path = os.path.abspath(self.video_file_path)
                    self.video_file_path = None  # Reset after successful save
                    return saved_path
                else:
                    logging.warning(f"Video file saved but is EMPTY: {self.video_file_path}")
                    return self.video_file_path
            else:
                logging.error(f"Failed to save video recording to: {self.video_file_path}")
                self.video_file_path = None
                return None
                
        except Exception as e:
            logging.error(f"Error stopping/saving video recording: {e}", exc_info=True)
            self._is_recording = False
            self.video_file_path = None
            return None


