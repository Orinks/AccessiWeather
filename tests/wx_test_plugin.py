"""Pytest plugin for wxPython testing.

This module provides a pytest plugin for enhancing wxPython testing with
features like memory tracking, segmentation fault handling, and improved
cleanup.
"""

import gc
import logging
import time
from typing import Dict, List, Optional, Set

import pytest
import wx

from tests.memory_tracker import memory_tracker
from tests.wx_cleanup_utils import safe_cleanup, safe_destroy_windows

logger = logging.getLogger(__name__)


# Track wxPython objects created during tests
class WxObjectTracker:
    """Track wxPython objects created during tests."""

    def __init__(self):
        """Initialize the tracker."""
        self.objects_by_test: Dict[str, Set[int]] = {}
        self.current_test: Optional[str] = None

    def start_tracking(self, nodeid: str):
        """Start tracking objects for a test.

        Args:
            nodeid: Test node ID
        """
        self.current_test = nodeid
        self.objects_by_test[nodeid] = set()
        logger.debug(f"Started tracking wxPython objects for {nodeid}")

    def stop_tracking(self):
        """Stop tracking objects for the current test."""
        if self.current_test:
            logger.debug(
                f"Stopped tracking wxPython objects for {self.current_test}, "
                f"tracked {len(self.objects_by_test.get(self.current_test, set()))} objects"
            )
            self.current_test = None

    def register_object(self, obj: wx.Object):
        """Register a wxPython object.

        Args:
            obj: wxPython object to register
        """
        if self.current_test and isinstance(obj, wx.Object):
            obj_id = id(obj)
            self.objects_by_test.setdefault(self.current_test, set()).add(obj_id)

    def get_objects_for_test(self, nodeid: str) -> Set[int]:
        """Get objects created during a test.

        Args:
            nodeid: Test node ID

        Returns:
            Set of object IDs
        """
        return self.objects_by_test.get(nodeid, set())


# Global tracker instance
wx_object_tracker = WxObjectTracker()


# Define pytest hooks
def pytest_addoption(parser):
    """Add plugin options to pytest."""
    group = parser.getgroup("wxpython")
    group.addoption(
        "--memory-tracking",
        action="store_true",
        default=False,
        help="Enable memory tracking for wxPython tests",
    )
    group.addoption(
        "--wx-cleanup-delay",
        type=float,
        default=0.01,
        help="Delay in seconds between wxPython cleanup operations",
    )


def pytest_configure(config):
    """Configure the plugin."""
    # Register the plugin
    config.pluginmanager.register(WxPytestPlugin(config), "wx_pytest_plugin")


class WxPytestPlugin:
    """Pytest plugin for wxPython testing."""

    def __init__(self, config):
        """Initialize the plugin.

        Args:
            config: Pytest config object
        """
        self.config = config
        self.memory_tracking = config.getoption("--memory-tracking")
        self.cleanup_delay = config.getoption("--wx-cleanup-delay")
        self.active_app = None

    def pytest_sessionstart(self, session):
        """Set up the test session.

        Args:
            session: Pytest session object
        """
        logger.info("Starting wxPython test session")
        if self.memory_tracking:
            logger.info("Memory tracking enabled")
            memory_tracker.start()

    def pytest_sessionfinish(self, session, exitstatus):
        """Clean up after the test session.

        Args:
            session: Pytest session object
            exitstatus: Exit status
        """
        logger.info("Finishing wxPython test session")
        
        # Clean up any remaining wxPython objects
        try:
            safe_cleanup()
        except Exception as e:
            logger.warning(f"Error during final cleanup: {e}")
            
        # Log memory statistics if tracking is enabled
        if self.memory_tracking:
            try:
                memory_tracker.log_memory_stats()
                memory_tracker.stop()
            except Exception as e:
                logger.warning(f"Error during memory tracking cleanup: {e}")
                
        # Force garbage collection
        gc.collect()

    def pytest_runtest_setup(self, item):
        """Set up a test.

        Args:
            item: Test item
        """
        if self.memory_tracking:
            wx_object_tracker.start_tracking(item.nodeid)

    def pytest_runtest_teardown(self, item, nextitem):
        """Clean up after a test.

        Args:
            item: Test item
            nextitem: Next test item
        """
        if self.memory_tracking:
            wx_object_tracker.stop_tracking()
            
        # Process events and force garbage collection
        try:
            for _ in range(5):
                wx.SafeYield()
                time.sleep(self.cleanup_delay)
            gc.collect()
        except Exception as e:
            logger.warning(f"Error during test teardown: {e}")


# Monkey patch wx.Object to track creation
original_init = wx.Object.__init__

def tracked_init(self, *args, **kwargs):
    """Tracked version of wx.Object.__init__."""
    original_init(self, *args, **kwargs)
    wx_object_tracker.register_object(self)

# Apply the monkey patch if not already applied
if wx.Object.__init__ is original_init:
    wx.Object.__init__ = tracked_init
    logger.debug("Monkey patched wx.Object.__init__ for tracking")
