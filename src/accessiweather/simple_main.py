"""Main entry point for the simplified AccessiWeather application.

This module provides the main entry point for running the simplified version
of AccessiWeather with the new Toga-based architecture.
"""

import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("accessiweather_simple.log")],
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the simplified AccessiWeather application."""
    try:
        logger.info("Starting simplified AccessiWeather application")

        # Import and run the simplified app
        from accessiweather.toga_app import main as simple_main

        app = simple_main()
        app.main_loop()

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
