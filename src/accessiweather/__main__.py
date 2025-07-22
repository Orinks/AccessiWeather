"""Main entry point for running the module directly

Allows running the module with `python -m accessiweather`
"""

from accessiweather.toga_app import main

if __name__ == "__main__":
    main().main_loop()
