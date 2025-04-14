#!/usr/bin/env python
"""
Test script to directly test the discussion fetching functionality.
"""

import logging
import sys
import time

from accessiweather.api_client import NoaaApiClient
from accessiweather.logging_config import setup_logging

# Set up logging
setup_logging(logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    """Main function to test discussion fetching."""
    # Get coordinates from command line or use defaults
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 39.9659459
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else -74.8051628
    
    print(f"Fetching discussion for coordinates: ({lat}, {lon})")
    
    # Create API client
    api_client = NoaaApiClient(user_agent="AccessiWeather Test", contact_info="test@example.com")
    
    # Fetch discussion
    print("Calling get_discussion...")
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
        print("No discussion available")

if __name__ == "__main__":
    main()
