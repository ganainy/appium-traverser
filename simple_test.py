#!/usr/bin/env python3
"""
Simple test to verify refactoring is working.
"""

import sys
import os

def test_basic_functionality():
    """Test basic functionality."""
    try:
        # Change to traverser_ai_api directory
        api_dir = os.path.join(os.path.dirname(__file__), 'traverser_ai_api')
        os.chdir(api_dir)
        
        # Test imports
        from traverser_ai_api.core.controller import CrawlerOrchestrator, CrawlerLaunchPlan
        from traverser_ai_api.core.validation import ValidationService
        from traverser_ai_api.core.adapters import SubprocessBackend, QtProcessBackend
        
        # Test creating objects
        backend = SubprocessBackend()
        # Note: We can't create orchestrator without a config, so just test backend creation
        
        # Write success to file
        with open('../test_result.txt', 'w') as f:
            f.write("SUCCESS: All imports and basic object creation working")
        
        return True
        
    except Exception as e:
        # Write error to file
        with open('../test_result.txt', 'w') as f:
            f.write(f"ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)