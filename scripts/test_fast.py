#!/usr/bin/env python
"""Run tests with optimized settings for fast local development."""
import os
import subprocess
import sys


def main():
    """Run tests with fast settings."""
    # Set fast Hypothesis profile
    os.environ.setdefault("HYPOTHESIS_PROFILE", "fast")

    # Build pytest command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-n",
        "auto",  # Parallel execution
        "--dist",
        "loadscope",  # Group by module
        "-v",
        "--tb=short",
    ]

    # Add any extra args passed to script
    cmd.extend(sys.argv[1:])

    # Exclude integration tests by default unless specified
    if not any("integration" in arg for arg in sys.argv[1:]):
        cmd.extend(["-m", "not integration"])

    print(f"Running: {' '.join(cmd)}")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
