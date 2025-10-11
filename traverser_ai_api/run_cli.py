#!/usr/bin/env python3
"""
Simple wrapper script to run the CLI controller.
This can be used as an alternative entry point.
"""

import sys
import os

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from traverser_ai_api.cli_controller import main_cli

if __name__ == "__main__":
    main_cli()