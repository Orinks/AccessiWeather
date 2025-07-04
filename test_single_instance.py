#!/usr/bin/env python3
"""Test script to verify single instance functionality.

This script tests the single instance mechanism by:
1. Starting the first instance
2. Attempting to start a second instance
3. Verifying the second instance shows the dialog and exits
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path


async def test_single_instance():
    """Test the single instance functionality."""
    print("Testing AccessiWeather single instance functionality...")
    
    # Change to the project directory
    project_dir = Path(__file__).parent
    
    # Command to run the app
    cmd = [
        sys.executable, "-m", "briefcase", "dev"
    ]
    
    print("Starting first instance...")
    # Start first instance
    process1 = subprocess.Popen(
        cmd,
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait a bit for the first instance to start and acquire the lock
    await asyncio.sleep(3)
    
    print("Starting second instance (should show dialog and exit)...")
    # Try to start second instance
    process2 = subprocess.Popen(
        cmd,
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for second instance to complete
    stdout2, stderr2 = process2.communicate(timeout=10)
    
    print(f"Second instance exit code: {process2.returncode}")
    if stdout2:
        print(f"Second instance stdout: {stdout2}")
    if stderr2:
        print(f"Second instance stderr: {stderr2}")
    
    # Clean up first instance
    print("Stopping first instance...")
    process1.terminate()
    try:
        process1.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process1.kill()
        process1.wait()
    
    print("Test completed!")


if __name__ == "__main__":
    asyncio.run(test_single_instance())
