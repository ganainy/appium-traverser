"""
==========================================================================
Agent Assistant Test Runner
==========================================================================

This script provides a convenient way to run the tests for the AgentAssistant 
implementation. It configures the testing environment with the provided API key 
and runs either all tests or specific tests as requested.

The test runner supports:
- Running all tests in the TestAgentAssistant test case
- Running specific test methods by name
- Configurable verbosity levels
- Skipping API-dependent tests when no API key is provided

Usage:
    python tests/run_agent_tests.py --api-key "your-api-key" --test "test_name" -v

Requirements:
    - Google Generative AI API key for integration tests
    - unittest module for test execution
"""

import os
import sys
import unittest
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def run_tests(api_key=None, test_pattern=None, verbosity=2):
    """Run the agent assistant tests with the provided API key."""
    if api_key:
        os.environ['GOOGLE_API_KEY'] = api_key
        logging.info(f"Using provided API key: {api_key[:5]}***")
    else:
        logging.warning("No API key provided. Some tests will be skipped.")
    
    # Import the test module
    from test_agent_assistant import TestAgentAssistant
    
    # Create a test suite
    loader = unittest.TestLoader()
    if test_pattern:
        suite = loader.loadTestsFromName(f'test_agent_assistant.TestAgentAssistant.{test_pattern}')
    else:
        suite = loader.loadTestsFromTestCase(TestAgentAssistant)
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run AgentAssistant tests')
    parser.add_argument('--api-key', help='Google Generative AI API key')
    parser.add_argument('--test', help='Specific test to run (e.g., test_full_integration)')
    parser.add_argument('--verbose', '-v', action='count', default=1, 
                        help='Increase verbosity (can be used multiple times)')
    
    args = parser.parse_args()
    
    success = run_tests(api_key=args.api_key, test_pattern=args.test, 
                         verbosity=args.verbose + 1)
    
    sys.exit(0 if success else 1)
