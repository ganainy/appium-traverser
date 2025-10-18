#!/usr/bin/env python3
"""
Test CLI functionality.
"""

import sys
import os

def test_cli():
    """Test CLI functionality."""
    try:
        # Change to traverser_ai_api directory
        api_dir = os.path.join(os.path.dirname(__file__), 'traverser_ai_api')
        os.chdir(api_dir)
        
        # Test CLI context creation
        from cli.shared.context import CLIContext
        ctx = CLIContext()
        
        # Write success to file
        with open('../cli_test_result.txt', 'w') as f:
            f.write(f"SUCCESS: CLI context created. Config path: {ctx.config.DEFAULTS_MODULE_PATH}")
        
        return True
        
    except Exception as e:
        # Write error to file
        with open('../cli_test_result.txt', 'w') as f:
            f.write(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_cli()
    sys.exit(0 if success else 1)