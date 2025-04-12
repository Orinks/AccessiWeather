#!/usr/bin/env python
"""
CLI test script to fetch a weather discussion directly from the NOAA API.
This helps diagnose issues with the discussion fetching functionality.
"""

import logging
import sys

from accessiweather.api_client import NoaaApiClient
from accessiweather.logging_config import setup_logging

# Set up logging
setup_logging(logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the test script"""
    # Create API client
    api_client = NoaaApiClient()
    
    # Default coordinates (Pemberton, NJ)
    lat, lon = 39.9659459, -74.8051628
    
    # Allow command line arguments for lat/lon
    if len(sys.argv) > 2:
        try:
            lat = float(sys.argv[1])
            lon = float(sys.argv[2])
        except ValueError:
            print(f"Invalid coordinates: {sys.argv[1]}, {sys.argv[2]}")
            print("Using default coordinates instead.")
    
    print(f"Fetching discussion for coordinates: ({lat}, {lon})")
    
    # Fetch discussion
    discussion = api_client.get_discussion(lat, lon)
    
    # Print result
    if discussion:
        print("\n" + "="*80)
        print("DISCUSSION TEXT:")
        print("="*80)
        print(discussion)
        print("="*80)
        print(f"Discussion length: {len(discussion)} characters")
    else:
        print("No discussion available or error occurred.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
