#!/usr/bin/env python
"""
Setup script for git hooks.
This script installs pre-commit and sets up the hooks.
"""

import os
import subprocess
import sys


def main():
    """Install pre-commit and set up the hooks."""
    print("Setting up git hooks...")
    
    # Install pre-commit if not already installed
    try:
        subprocess.run(["pre-commit", "--version"], check=True, capture_output=True)
        print("pre-commit is already installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Installing pre-commit...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pre-commit"], check=True)
    
    # Install the pre-commit hooks
    print("Installing pre-commit hooks...")
    subprocess.run(["pre-commit", "install"], check=True)
    
    print("Git hooks setup complete!")
    print("Run 'pre-commit run --all-files' to run the hooks on all files.")


if __name__ == "__main__":
    main()
