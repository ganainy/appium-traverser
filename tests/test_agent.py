#!/usr/bin/env python3
# test_agent.py - Test script for the AgentAssistant

import os
import sys
import logging
from PIL import Image
import io

# Add the parent directory to the path to import from traverser_ai_api
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import our AgentAssistant and Config classes
from traverser_ai_api.agent_assistant import AgentAssistant
from traverser_ai_api.config import Config

def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    """Test the AgentAssistant with a sample screenshot."""
    setup_logging()
    logging.info("Testing AgentAssistant...")
    
    # Load configuration
    defaults_module_path = os.path.join(parent_dir, "traverser_ai_api", "config.py")
    user_config_json_path = os.path.join(parent_dir, "traverser_ai_api", "user_config.json")
    config = Config(defaults_module_path, user_config_json_path)
    config.load_user_config()
    
    # Make sure GEMINI_API_KEY is set
    if not config.GEMINI_API_KEY:
        logging.error("GEMINI_API_KEY is not set in the configuration or environment")
        sys.exit(1)
    
    # Initialize the AgentAssistant
    try:
        agent = AgentAssistant(config)
        logging.info("AgentAssistant initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize AgentAssistant: {e}")
        sys.exit(1)
    
    # Load a sample screenshot
    screenshot_path = os.path.join(parent_dir, "traverser_ai_api", "output_data", "screenshots")
    
    # Find the first screenshot file in the directory
    screenshot_files = []
    for root, dirs, files in os.walk(screenshot_path):
        for file in files:
            if file.endswith('.png') or file.endswith('.jpg'):
                screenshot_files.append(os.path.join(root, file))
                break
        if screenshot_files:
            break
    
    if not screenshot_files:
        logging.error(f"No screenshot files found in {screenshot_path}")
        sys.exit(1)
    
    screenshot_file = screenshot_files[0]
    logging.info(f"Using screenshot: {screenshot_file}")
    
    # Load the screenshot
    with open(screenshot_file, 'rb') as f:
        screenshot_bytes = f.read()
    
    # Create a simple XML context
    xml_context = """
    <hierarchy rotation="0">
        <android.widget.FrameLayout index="0" package="com.example.app" bounds="[0,0][1080,2340]">
            <android.widget.LinearLayout index="0" bounds="[0,0][1080,2340]">
                <android.widget.TextView index="0" text="Welcome to the App" bounds="[40,300][1040,400]" />
                <android.widget.Button index="1" text="Login" bounds="[200,600][880,700]" />
                <android.widget.Button index="2" text="Sign Up" bounds="[200,800][880,900]" />
                <android.widget.Button index="3" text="Continue as Guest" bounds="[200,1000][880,1100]" />
            </android.widget.LinearLayout>
        </android.widget.FrameLayout>
    </hierarchy>
    """
    
    # Call the get_next_action method
    previous_actions = []
    visit_count = 1
    composite_hash = "test_hash_123"
    
    try:
        result = agent.get_next_action(
            screenshot_bytes,
            xml_context,
            previous_actions,
            visit_count,
            composite_hash
        )
        
        if result:
            action_data, elapsed_time, token_count = result
            logging.info(f"Action determined in {elapsed_time:.2f} seconds:")
            logging.info(f"Action: {action_data['action_to_perform']['action']}")
            logging.info(f"Target: {action_data['action_to_perform']['target_identifier']}")
            logging.info(f"Reasoning: {action_data['action_to_perform']['reasoning']}")
        else:
            logging.error("Failed to get next action")
    
    except Exception as e:
        logging.error(f"Error getting next action: {e}", exc_info=True)

if __name__ == "__main__":
    main()
