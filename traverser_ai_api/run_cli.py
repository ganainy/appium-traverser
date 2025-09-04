#!/usr/bin/env python3
"""
Simple wrapper script to run the CLI controller.
This can be used as an alternative entry point.
"""

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from cli_controller import main_cli

if __name__ == '__main__':
    main_cli()
