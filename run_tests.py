"""Script to run tests for the NOAA Weather App

This script runs all tests and reports coverage.
"""

import subprocess
import sys

def main():
    """Run the tests with pytest"""
    print("Running tests for NOAA Weather App...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        capture_output=True,
        text=True
    )
    
    # Print output
    print(result.stdout)
    
    if result.stderr:
        print("Errors:")
        print(result.stderr)
    
    # Return the exit code
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
