#!/usr/bin/env python3
"""
Hydra OAuth2 Lifecycle Tester Runner
This script provides a convenient way to run the tester from the command line.
"""

import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from src.main import main

if __name__ == "__main__":
    main()
