"""
Entry point for `python -m accessiweather`.

Delegates entirely to main.py to keep a single source of truth for CLI args.
"""

from accessiweather.main import main

if __name__ == "__main__":
    main()
