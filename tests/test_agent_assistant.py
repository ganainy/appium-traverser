"""
==========================================================================
Agent Assistant Test Suite
==========================================================================

This file contains the comprehensive test suite for the AgentAssistant 
implementation that uses Google Generative AI. It includes both unit tests 
with mocks and integration tests that interact with the actual API.

The test suite covers:
1. API key configuration and environment setup
2. Model initialization and configuration
3. Image processing and optimization for AI analysis
4. Mock testing of the action generation pipeline
5. Full integration testing with real API calls
6. Response parsing and error handling

Requirements:
    - Google Generative AI API key for integration tests
    - unittest and mock modules
    - PIL (Pillow) for image processing
"""

import os
import sys
import logging
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
import io
import base64

# Set up path to import from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from traverser_ai_api.agent_assistant import AgentAssistant

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class MockConfig:
    """Mock configuration for testing the AgentAssistant."""
    def __init__(self, api_key=None):
        self.GEMINI_API_KEY = api_key or os.environ.get('GOOGLE_API_KEY', 'test-key')
        self.DEFAULT_MODEL_TYPE = 'test-model'
        self.GEMINI_MODELS = {
            'test-model': {
                'name': 'gemini-2.5-flash-preview-05-20',
                'description': 'Test model for unit tests',
                'generation_config': {
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40,
                    'max_output_tokens': 1024
                },
                'online': True
            }
        }
        self.USE_CHAT_MEMORY = False
        self.AVAILABLE_ACTIONS = ["click", "input", "scroll_down", "back"]
        
class TestAgentAssistant(unittest.TestCase):
    """Test cases for the AgentAssistant class."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests."""
        # Check if API key is available
        cls.api_key = os.environ.get('GOOGLE_API_KEY')
        if not cls.api_key:
            logging.warning("No GOOGLE_API_KEY found in environment. Some tests will be skipped.")
    
    def setUp(self):
        """Set up before each test."""
        self.config = MockConfig(api_key=self.api_key)
        
    def create_test_image(self, width=300, height=500, color=(255, 255, 255)):
        """Create a test image for testing."""
        img = Image.new('RGB', (width, height), color=color)
        # Add some basic shapes to make it more realistic
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        # Draw a button
        draw.rectangle((50, 100, 250, 150), fill=(0, 120, 255), outline=(0, 0, 0))
        draw.text((150, 125), "Click Me", fill=(255, 255, 255))
        # Convert to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
        
    def test_initialization(self):
        """Test basic initialization of the AgentAssistant."""
        # This test only verifies the class can be instantiated without errors
        try:
            agent = AgentAssistant(self.config)
            self.assertIsNotNone(agent)
            logging.info("AgentAssistant initialized successfully")
        except Exception as e:
            if not self.api_key:
                self.skipTest("Skipping test_initialization as no API key is available")
            else:
                self.fail(f"Failed to initialize AgentAssistant: {e}")
                
    def test_api_key_setting(self):
        """Test that the API key is properly set."""
        if not self.api_key:
            self.skipTest("Skipping test_api_key_setting as no API key is available")
            
        with patch('os.environ', {}) as mock_environ:
            agent = AgentAssistant(self.config)
            self.assertEqual(mock_environ.get('GOOGLE_API_KEY'), self.api_key)
            logging.info("API key correctly set in environment variables")
    
    def test_prepare_image_part(self):
        """Test image preparation functionality."""
        agent = AgentAssistant(self.config)
        test_image_bytes = self.create_test_image()
        
        # Test image preparation
        processed_image = agent._prepare_image_part(test_image_bytes)
        self.assertIsNotNone(processed_image)
        self.assertIsInstance(processed_image, Image.Image)
        if processed_image:
            logging.info(f"Image processed successfully, size: {processed_image.size}")
        
        # Test with an oversized image
        large_image_bytes = self.create_test_image(width=1200, height=2000)
        processed_large_image = agent._prepare_image_part(large_image_bytes)
        self.assertIsNotNone(processed_large_image)
        if processed_large_image:
            self.assertLessEqual(processed_large_image.width, 720)  # Check resizing
            logging.info(f"Large image correctly resized to: {processed_large_image.size}")
    
    @patch('google.generativeai.generative_models.GenerativeModel')
    def test_model_initialization(self, mock_generative_model):
        """Test model initialization with mocked GenerativeModel."""
        # Setup the mock
        mock_instance = MagicMock()
        mock_generative_model.return_value = mock_instance
        
        # Create the agent
        agent = AgentAssistant(self.config)
        
        # Verify GenerativeModel was called with correct parameters
        mock_generative_model.assert_called_once()
        args, kwargs = mock_generative_model.call_args
        self.assertEqual(kwargs['model_name'], 'gemini-2.5-flash-preview-05-20')
        logging.info("Model initialized with correct parameters")
    
    @patch('google.generativeai.generative_models.GenerativeModel')
    def test_get_next_action(self, mock_generative_model):
        """Test get_next_action with a mocked model response."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = """
        I'll help you navigate this app.
        
        ```json
        {
            "action": "click",
            "target_identifier": "button-1",
            "target_bounding_box": {"top_left": [100, 50], "bottom_right": [150, 80]},
            "reasoning": "This button appears to be the main call-to-action"
        }
        ```
        """
        
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_response
        mock_generative_model.return_value = mock_instance
        
        # Create the agent
        agent = AgentAssistant(self.config)
        
        # Test get_next_action
        test_image = self.create_test_image()
        test_xml = "<View><Button text='Click Me' /></View>"
        
        result = agent.get_next_action(
            screenshot_bytes=test_image,
            xml_context=test_xml,
            previous_actions=[],
            current_screen_visit_count=1,
            current_composite_hash="test-hash-123"
        )
        
        # Check if result is not None before unpacking
        self.assertIsNotNone(result, "get_next_action returned None")
        
        if result:
            action_data, elapsed_time, token_count = result
            
            # Verify the response was processed correctly
            self.assertIsNotNone(action_data)
            self.assertIn('action_to_perform', action_data)
            self.assertEqual(action_data['action_to_perform']['action'], 'click')
            logging.info(f"Successfully parsed action: {action_data['action_to_perform']}")
    
    @unittest.skipIf(not os.environ.get('GOOGLE_API_KEY'), "Skipping full integration test without API key")
    def test_full_integration(self):
        """Full integration test with actual API call.
        
        This test will be skipped if no API key is available.
        """
        # Create the agent
        agent = AgentAssistant(self.config)
        
        # Test get_next_action with real API
        test_image = self.create_test_image()
        test_xml = """
        <hierarchy rotation="0">
          <node index="0" text="" resource-id="" class="android.widget.FrameLayout" 
                package="com.example.testapp" content-desc="" checkable="false" 
                checked="false" clickable="false" enabled="true" focusable="false" 
                focused="false" scrollable="false" long-clickable="false" password="false" 
                selected="false" bounds="[0,0][1080,2340]">
            <node index="0" text="" resource-id="" class="android.widget.LinearLayout" 
                  package="com.example.testapp" content-desc="" checkable="false" 
                  checked="false" clickable="false" enabled="true" focusable="false" 
                  focused="false" scrollable="false" long-clickable="false" password="false" 
                  selected="false" bounds="[0,0][1080,2340]">
              <node index="0" text="Click Me" resource-id="button_1" class="android.widget.Button" 
                    package="com.example.testapp" content-desc="Click this button" checkable="false" 
                    checked="false" clickable="true" enabled="true" focusable="true" 
                    focused="false" scrollable="false" long-clickable="false" password="false" 
                    selected="false" bounds="[50,100][250,150]" />
            </node>
          </node>
        </hierarchy>
        """
        
        try:
            result = agent.get_next_action(
                screenshot_bytes=test_image,
                xml_context=test_xml,
                previous_actions=[],
                current_screen_visit_count=1,
                current_composite_hash="test-hash-456"
            )
            
            # Check if result is not None before unpacking
            self.assertIsNotNone(result, "Full integration test: get_next_action returned None")
            
            if result:
                action_data, elapsed_time, token_count = result
                
                # Verify we got a valid response
                self.assertIsNotNone(action_data)
                self.assertIn('action_to_perform', action_data)
                self.assertIn('action', action_data['action_to_perform'])
                logging.info(f"Full integration test successful. Action: {action_data['action_to_perform']['action']}")
                logging.info(f"Processing time: {elapsed_time:.2f}s, estimated tokens: {token_count}")
            
        except Exception as e:
            self.fail(f"Full integration test failed: {e}")

if __name__ == '__main__':
    unittest.main()
