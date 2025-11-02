"""
This test module verifies the behavior of the CrawlerOrchestrator and related core components. It checks:
- Preparation of launch plans for the crawler.
- Orchestrator interactions with configuration and backend.
- Correctness of process management and validation logic.
"""
#!/usr/bin/env python3
"""
Tests for the shared crawler orchestrator.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


try:
    from core.adapters import SubprocessBackend
    from core.controller import CrawlerLaunchPlan, CrawlerOrchestrator, FlagController
    from core.validation import ValidationService
except ImportError:
    from core.adapters import SubprocessBackend
    from core.controller import CrawlerLaunchPlan, CrawlerOrchestrator, FlagController
    from core.validation import ValidationService


class TestCrawlerOrchestrator(unittest.TestCase):
    """Test cases for CrawlerOrchestrator."""
    
    def setUp(self):
        """Set up test fixtures."""
        from config.config import Config
        # Create a mock config
        self.mock_config = Mock(spec=Config)
        self.mock_config.APP_PACKAGE = "com.example.app"
        self.mock_config.APP_ACTIVITY = "com.example.app.MainActivity"
        self.mock_config.BASE_DIR = "/tmp/test"
        self.mock_config.OUTPUT_DATA_DIR = "/tmp/test/output"
        self.mock_config.LOG_DIR = "/tmp/test/logs"
        self.mock_config.LOG_FILE_NAME = "test.log"
        self.mock_config.SHUTDOWN_FLAG_PATH = "/tmp/test/shutdown.flag"
        self.mock_config.PAUSE_FLAG_PATH = "/tmp/test/pause.flag"
        # Create a mock backend
        self.mock_backend = Mock()
        self.mock_backend.start_process.return_value = True
        self.mock_backend.stop_process.return_value = True
        self.mock_backend.is_process_running.return_value = False
        self.mock_backend.get_process_id.return_value = 12345
        # Create the orchestrator
        self.orchestrator = CrawlerOrchestrator(self.mock_config, self.mock_backend)
    
    def test_prepare_plan(self):
        """Test launch plan preparation."""
        plan = self.orchestrator.prepare_plan()
        
        # Check that the plan has the expected attributes
        self.assertIsInstance(plan, CrawlerLaunchPlan)
        self.assertEqual(plan.app_package, "com.example.app")
        self.assertEqual(plan.app_activity, "com.example.app.MainActivity")
        self.assertEqual(plan.python_executable, sys.executable)
        self.assertTrue(plan.script_path.endswith("main.py"))
    
    @patch('core.validation.ValidationService.validate_all')
    def test_prepare_plan_with_validation(self, mock_validate):
        """Test launch plan preparation with validation."""
        # Mock validation to return failure
        mock_validate.return_value = (False, ["Test error"])
        
        plan = self.orchestrator.prepare_plan()
        
        # Check that validation failed
        self.assertFalse(plan.validation_passed)
        self.assertEqual(plan.validation_messages, ["Test error"])
    
    def test_start_crawler_success(self):
        """Test successful crawler start."""
        # Mock the backend to return success
        self.mock_backend.start_process.return_value = True
        self.mock_backend.is_process_running.return_value = True
        self.mock_backend.get_process_id.return_value = 12345
        
        result = self.orchestrator.start_crawler()
        
        # Check that the crawler started
        self.assertTrue(result)
        self.assertTrue(self.orchestrator._is_running)
        self.mock_backend.start_process.assert_called_once()
    
    def test_start_crawler_failure(self):
        """Test failed crawler start."""
        # Mock the backend to return failure
        self.mock_backend.start_process.return_value = False
        
        result = self.orchestrator.start_crawler()
        
        # Check that the crawler failed to start
        self.assertFalse(result)
        self.assertFalse(self.orchestrator._is_running)
    
    def test_stop_crawler(self):
        """Test crawler stop."""
        # Set the crawler as running
        self.orchestrator._is_running = True
        self.mock_backend.is_process_running.return_value = True
        
        result = self.orchestrator.stop_crawler()
        
        # Check that the crawler stopped
        self.assertTrue(result)
        self.assertFalse(self.orchestrator._is_running)
        self.mock_backend.stop_process.assert_called_once()
    
    def test_pause_crawler(self):
        """Test crawler pause."""
        result = self.orchestrator.pause_crawler()
        
        # Check that the pause flag was created
        self.assertTrue(result)
        self.assertTrue(self.orchestrator.flag_controller.is_pause_flag_present())
    
    def test_resume_crawler(self):
        """Test crawler resume."""
        # First pause the crawler
        self.orchestrator.pause_crawler()
        
        # Then resume it
        result = self.orchestrator.resume_crawler()
        
        # Check that the pause flag was removed
        self.assertTrue(result)
        self.assertFalse(self.orchestrator.flag_controller.is_pause_flag_present())
    
    def test_get_status(self):
        """Test status retrieval."""
        # Mock the backend
        self.mock_backend.is_process_running.return_value = True
        self.mock_backend.get_process_id.return_value = 12345
        
        status = self.orchestrator.get_status()
        
        # Check the status
        self.assertTrue(status["is_running"])
        self.assertEqual(status["process_id"], 12345)
        self.assertEqual(status["app_package"], "com.example.app")
        self.assertEqual(status["app_activity"], "com.example.app.MainActivity")
    
    def test_register_callback(self):
        """Test callback registration."""
        # Create a mock callback
        mock_callback = Mock()
        
        # Register the callback
        self.orchestrator.register_callback('step', mock_callback)
        
        # Check that the callback was registered
        self.assertIn(mock_callback, self.orchestrator.output_parser.callbacks['step'])


class TestFlagController(unittest.TestCase):
    """Test cases for FlagController."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = "/tmp/test_flags"
        os.makedirs(self.temp_dir, exist_ok=True)
        self.shutdown_flag_path = os.path.join(self.temp_dir, "shutdown.flag")
        self.pause_flag_path = os.path.join(self.temp_dir, "pause.flag")
        from core.controller import FlagController
        self.flag_controller = FlagController(self.shutdown_flag_path, self.pause_flag_path)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_create_shutdown_flag(self):
        """Test shutdown flag creation."""
        result = self.flag_controller.create_shutdown_flag()
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.shutdown_flag_path))
        self.assertEqual(Path(self.shutdown_flag_path).read_text(), "shutdown")
    
    def test_create_pause_flag(self):
        """Test pause flag creation."""
        result = self.flag_controller.create_pause_flag()
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.pause_flag_path))
        self.assertEqual(Path(self.pause_flag_path).read_text(), "pause")
    
    def test_remove_pause_flag(self):
        """Test pause flag removal."""
        # First create the flag
        self.flag_controller.create_pause_flag()
        
        # Then remove it
        result = self.flag_controller.remove_pause_flag()
        
        self.assertTrue(result)
        self.assertFalse(os.path.exists(self.pause_flag_path))
    
    def test_is_pause_flag_present(self):
        """Test pause flag presence check."""
        # Initially should be False
        self.assertFalse(self.flag_controller.is_pause_flag_present())
        
        # Create the flag
        self.flag_controller.create_pause_flag()
        
        # Now should be True
        self.assertTrue(self.flag_controller.is_pause_flag_present())
        
        # Remove the flag
        self.flag_controller.remove_pause_flag()
        
        # Should be False again
        self.assertFalse(self.flag_controller.is_pause_flag_present())


class TestValidationService(unittest.TestCase):
    """Test cases for ValidationService."""
    
    def setUp(self):
        """Set up test fixtures."""
        from config.config import Config
        self.mock_config = Mock(spec=Config)
        self.mock_config.APP_PACKAGE = "com.example.app"
        self.mock_config.AI_PROVIDER = "gemini"
        self.mock_config.ENABLE_TRAFFIC_CAPTURE = False
        self.mock_config.ENABLE_MOBSF_ANALYSIS = False
        from core.validation import ValidationService
        self.validation_service = ValidationService(self.mock_config)
    
    @patch('core.validation.requests.get')
    def test_check_appium_server_success(self, mock_get):
        """Test successful Appium server check."""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ready": True}
        mock_get.return_value = mock_response
        
        result = self.validation_service._check_appium_server()
        
        self.assertTrue(result)
    
    @patch('core.validation.requests.get')
    def test_check_appium_server_failure(self, mock_get):
        """Test failed Appium server check."""
        # Mock the response to raise an exception
        mock_get.side_effect = Exception("Connection failed")
        
        result = self.validation_service._check_appium_server()
        
        self.assertFalse(result)
    
    def test_check_api_keys_and_env(self):
        """Test API keys and environment variables check."""
        # Set up the mock config
        self.mock_config.GEMINI_API_KEY = "test_key"
        
        issues, warnings = self.validation_service._check_api_keys_and_env()
        
        # Should have no issues or warnings
        self.assertEqual(len(issues), 0)
        self.assertEqual(len(warnings), 0)
    
    def test_check_api_keys_and_env_missing_key(self):
        """Test API keys check with missing key."""
        # Set up the mock config with no API key
        self.mock_config.GEMINI_API_KEY = None
        
        issues, warnings = self.validation_service._check_api_keys_and_env()
        
        # Should have one issue
        self.assertEqual(len(issues), 1)
        self.assertIn("Gemini API key is not set", issues[0])


if __name__ == '__main__':
    unittest.main()
