#!/usr/bin/env python3
"""Test script to simulate a second instance startup.

This script simulates what happens when a user tries to start AccessiWeather
when another instance is already running.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from accessiweather.simple.app import AccessiWeatherApp


def test_second_instance():
    """Test what happens when a second instance tries to start."""
    print("Testing second instance behavior...")
    
    # Create the app (this will trigger the single instance check in startup)
    app = AccessiWeatherApp(
        'AccessiWeather',
        'net.orinks.accessiweather'
    )
    
    # The startup method will be called automatically when the app runs
    # If another instance is running, it should show a dialog and exit
    print("Starting app (should detect existing instance if one is running)...")
    
    try:
        app.main_loop()
    except Exception as e:
        print(f"App exited with exception: {e}")


if __name__ == "__main__":
    test_second_instance()
