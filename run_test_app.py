#!/usr/bin/env python3
"""Run the test weather app."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    from accessiweather.simple.test_app import main
    
    app = main()
    app.main_loop()
