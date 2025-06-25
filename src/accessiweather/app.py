"""Main app entry point for Briefcase.

This module provides the main entry point that Briefcase expects
for the simplified AccessiWeather application.
"""

from accessiweather.simple import main as simple_main


def main():
    """Main entry point for Briefcase."""
    return simple_main()


if __name__ == "__main__":
    main().main_loop()
