# tests/conftest.py
import faulthandler
import gc
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest
import wx

from accessiweather.utils.faulthandler_utils import enable_faulthandler, dump_traceback
from tests.wx_cleanup_utils import safe_destroy_windows, safe_cleanup

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
log_dir = Path("tests/logs")
log_dir.mkdir(exist_ok=True, parents=True)

# Enable faulthandler at the module level
fault_log_path = log_dir / "test_faulthandler.log"
enable_faulthandler(log_file_path=fault_log_path, all_threads=True, register_all_signals=True)

# Define pytest hooks
def pytest_configure(config):
    """Configure pytest before test collection."""
    logger.info("Configuring pytest for wxPython testing")
    # Register any additional plugins or configurations here


def pytest_unconfigure(config):
    """Clean up after all tests have completed."""
    logger.info("Cleaning up after all tests")
    # Perform final cleanup
    try:
        # Dump a final traceback before exiting
        dump_traceback(all_threads=True)
        # Force garbage collection
        gc.collect()
    except Exception as e:
        logger.error(f"Error during final cleanup: {e}")


@pytest.fixture(scope="function")
def wx_app_isolated():
    """Create a wx App for testing with enhanced isolation.

    This fixture creates a new wx.App for each test function and performs
    thorough cleanup afterward to prevent segmentation faults.

    Use this instead of wx_app when you need better isolation between tests.
    """
    # Create a new app for each test
    app = wx.App(False)  # False means don't redirect stdout/stderr

    # Process initial events
    for _ in range(5):
        wx.SafeYield()
        time.sleep(0.01)

    # Provide the app to the test
    yield app

    # Clean up after the test
    logger.debug("Cleaning up wx_app_isolated fixture")

    # Process any pending events
    for _ in range(5):
        wx.SafeYield()
        time.sleep(0.01)

    # Safely destroy all top-level windows
    safe_destroy_windows()

    # Process events again
    for _ in range(5):
        wx.SafeYield()
        time.sleep(0.01)

    # Force garbage collection
    gc.collect()

    # Dump traceback for debugging
    dump_traceback(all_threads=False)


@pytest.fixture(scope="function")
def memory_tracker():
    """Track memory usage during a test.

    This fixture tracks memory usage before and after a test to help identify
    potential memory leaks.
    """
    # Get initial memory usage
    gc.collect()  # Force collection before measuring
    objects_before = len(gc.get_objects())

    # Run the test
    yield

    # Get final memory usage
    gc.collect()  # Force collection before measuring
    objects_after = len(gc.get_objects())

    # Log the difference
    diff = objects_after - objects_before
    logger.info(f"Memory usage: {diff:+d} objects")

    # If there's a significant increase, log more details
    if diff > 100:  # Arbitrary threshold
        logger.warning(f"Possible memory leak: {diff:+d} objects")
        # Could add more detailed memory analysis here


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing"""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a temporary config file
        config_path = os.path.join(temp_dir, "config.json")
        config_data = {
            "locations": {"Test City": {"lat": 35.0, "lon": -80.0}},
            "current": "Test City",
            "settings": {"update_interval_minutes": 30},
            "api_settings": {"contact_info": "test@example.com"},
        }

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        yield config_path
