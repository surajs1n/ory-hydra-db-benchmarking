#!/usr/bin/env python3
"""
Hydra OAuth2 Lifecycle Tester Runner
This script provides a convenient way to run the tester from the command line.
"""

import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

# Ensure output directory exists
os.makedirs("output", exist_ok=True)

def print_usage():
    """Print usage information"""
    print("""
Hydra OAuth2 Lifecycle Tester

Usage:
    ./run.py [options]

Options:
    --clients N             Number of clients to manage (max 100)
    --threads-per-client N  Number of parallel threads per client (max 100)
    --refresh-count N       Number of refresh cycles per client
    --refresh-interval N    Seconds between refresh calls
    --hydra-admin-url URL  Hydra admin API URL
    --hydra-public-url URL Hydra public API URL
    --redirect-uri URI     Redirect URI used in flow
    --scope SCOPE         OAuth2 scope string
    --config PATH         Path to config file
    --log-file PATH       Path to log file
    --verbose            Enable verbose logging
    --cleanup           Clean up clients after test

Example:
    ./run.py --clients 5 --threads-per-client 10 --refresh-count 5 --refresh-interval 60

Each client will have N threads running parallel OAuth flows, where each thread:
1. Runs the complete OAuth2 authorization code flow
2. Obtains access and refresh tokens
3. Performs token refresh cycles based on refresh-count and interval
4. Saves results to a thread-specific output file
""")

if len(sys.argv) == 1 or "--help" in sys.argv or "-h" in sys.argv:
    print_usage()
    sys.exit(0)

from src.main import main

if __name__ == "__main__":
    main()
