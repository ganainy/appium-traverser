"""
==========================================================================
Agent Assistant Demo Script
==========================================================================

This script demonstrates the AgentAssistant's capabilities in a real-world 
scenario. It initializes the AI agent with a Google Generative AI model and
provides it with either a sample screenshot or a user-provided one. The agent
then analyzes the screen and determines the next best action to take.

The demo can run with default sample data or with custom screenshots and 
XML UI hierarchies provided via command line arguments.

Usage:
    python tests/demo_agent.py --api-key "your-api-key" --screenshot "path/to/screenshot.png" --xml "path/to/xml.xml"

Requirements:
    - Google Generative AI API key
    - PIL (Pillow) for image processing
    - AgentAssistant implementation
"""

import os
import sys
import logging
import argparse
from PIL import Image
import io

# Set up path to import from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from traverser_ai_api.agent_assistant import AgentAssistant
from traverser_ai_api.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def load_sample_screenshot(path):
    """Load a sample screenshot from a file."""
    try:
        with open(path, 'rb') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Failed to load screenshot from {path}: {e}")
        # Create a simple test image as fallback
        img = Image.new('RGB', (300, 500), color=(255, 255, 255))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle((50, 100, 250, 150), fill=(0, 120, 255), outline=(0, 0, 0))
        draw.text((150, 125), "Demo Button", fill=(255, 255, 255))
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()

def load_sample_xml(path):
    """Load a sample XML file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Failed to load XML from {path}: {e}")
        # Return a simple XML as fallback
        return """
        <hierarchy rotation="0">
          <node index="0" text="" resource-id="" class="android.widget.FrameLayout">
            <node index="0" text="" resource-id="" class="android.widget.LinearLayout">
              <node index="0" text="Demo Button" resource-id="button_demo" class="android.widget.Button"
                    clickable="true" enabled="true" focusable="true" bounds="[50,100][250,150]" />
            </node>
          </node>
        </hierarchy>
        """

def run_agent_demo(api_key, screenshot_path=None, xml_path=None):
    """Run a demonstration of the agent assistant."""
    # Set up configuration
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'traverser_ai_api', 'config.py')
    user_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'user_config.json')
    
    # Create a simple config object
    class SimpleConfig:
        def __init__(self, api_key):
            self.GEMINI_API_KEY = api_key
            self.DEFAULT_MODEL_TYPE = 'gemini-pro'
            self.GEMINI_MODELS = {
                'gemini-pro': {
                    'name': 'gemini-2.5-flash-preview-05-20',
                    'description': 'Gemini Pro model for general use',
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
    
    # Initialize the agent assistant
    try:
        config = SimpleConfig(api_key)
        agent = AgentAssistant(config)
        logging.info("AgentAssistant initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize AgentAssistant: {e}")
        return False
    
    # Load sample data
    screenshot_bytes = load_sample_screenshot(screenshot_path) if screenshot_path else None
    xml_context = load_sample_xml(xml_path) if xml_path else None
    
    # Create a default screenshot if none was provided
    if not screenshot_bytes:
        logging.info("Creating default test image...")
        img = Image.new('RGB', (300, 500), color=(255, 255, 255))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle((50, 100, 250, 150), fill=(0, 120, 255), outline=(0, 0, 0))
        draw.text((150, 125), "Demo Button", fill=(255, 255, 255))
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        screenshot_bytes = img_byte_arr.getvalue()
    
    if not screenshot_bytes:
        logging.error("Failed to get screenshot data")
        return False
    
    # Ensure xml_context is not None
    if not xml_context:
        xml_context = """
        <hierarchy rotation="0">
          <node index="0" text="" resource-id="" class="android.widget.FrameLayout">
            <node index="0" text="" resource-id="" class="android.widget.LinearLayout">
              <node index="0" text="Default Button" resource-id="button_default" class="android.widget.Button"
                    clickable="true" enabled="true" focusable="true" bounds="[50,100][250,150]" />
            </node>
          </node>
        </hierarchy>
        """
    
    # Set up additional parameters
    previous_actions = []
    current_screen_visit_count = 1
    current_composite_hash = "demo-hash-123"
    
    # Get the next action
    try:
        result = agent.get_next_action(
            screenshot_bytes=screenshot_bytes,
            xml_context=xml_context,
            previous_actions=previous_actions,
            current_screen_visit_count=current_screen_visit_count,
            current_composite_hash=current_composite_hash
        )
        
        if not result:
            logging.error("Agent returned None response")
            return False
            
        action_data, elapsed_time, token_count = result
        
        # Display the results
        logging.info(f"\n{'='*50}")
        logging.info("AGENT ASSISTANT DEMO RESULTS")
        logging.info(f"{'='*50}")
        logging.info(f"Processing time: {elapsed_time:.2f} seconds")
        logging.info(f"Estimated token count: {token_count}")
        logging.info(f"Action to perform: {action_data['action_to_perform']['action']}")
        logging.info(f"Reasoning: {action_data['action_to_perform'].get('reasoning', 'N/A')}")
        
        # Display target details if available
        if 'target_identifier' in action_data['action_to_perform']:
            logging.info(f"Target identifier: {action_data['action_to_perform']['target_identifier']}")
        if 'target_bounding_box' in action_data['action_to_perform']:
            logging.info(f"Target bounding box: {action_data['action_to_perform']['target_bounding_box']}")
        if 'input_text' in action_data['action_to_perform']:
            logging.info(f"Input text: {action_data['action_to_perform']['input_text']}")
            
        logging.info(f"{'='*50}\n")
        return True
        
    except Exception as e:
        logging.error(f"Error in agent demo: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run AgentAssistant demonstration')
    parser.add_argument('--api-key', help='Google Generative AI API key')
    parser.add_argument('--screenshot', help='Path to a screenshot file')
    parser.add_argument('--xml', help='Path to an XML file')
    
    args = parser.parse_args()
    
    # Use environment variable if no API key is provided
    api_key = args.api_key or os.environ.get('GOOGLE_API_KEY')
    
    if not api_key:
        logging.error("No API key provided. Please provide an API key with --api-key or set the GOOGLE_API_KEY environment variable.")
        sys.exit(1)
    
    success = run_agent_demo(api_key, args.screenshot, args.xml)
    sys.exit(0 if success else 1)
