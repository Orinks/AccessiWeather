"""Utilities for safely cleaning up wxPython objects in tests.

This module provides functions to safely clean up wxPython objects to prevent
segmentation faults during test execution.
"""

import gc
import logging
import time
from typing import List, Optional

import wx

logger = logging.getLogger(__name__)


def safe_destroy_windows(windows: Optional[List[wx.Window]] = None) -> None:
    """Safely destroy wxPython windows to prevent segmentation faults.

    Args:
        windows: List of windows to destroy. If None, gets all top-level windows.
    """
    if windows is None:
        windows = list(wx.GetTopLevelWindows())

    logger.debug(f"Safely destroying {len(windows)} windows")

    # First hide all windows
    for win in windows:
        if win and win.IsShown():
            try:
                logger.debug(f"Hiding window {win}")
                win.Hide()
                wx.SafeYield()
            except Exception as e:
                logger.warning(f"Error hiding window {win}: {e}")

    # Process events after hiding
    for _ in range(5):
        wx.SafeYield()
        time.sleep(0.02)

    # Then destroy all windows
    for win in windows:
        try:
            logger.debug(f"Destroying window {win}")
            win.Destroy()
            wx.SafeYield()
        except Exception as e:
            logger.warning(f"Error destroying window {win}: {e}")

    # Process events after destroying
    for _ in range(10):
        wx.SafeYield()
        time.sleep(0.02)

    # Force garbage collection
    logger.debug("Forcing garbage collection")
    gc.collect()
    wx.SafeYield()
    time.sleep(0.05)


def safe_cleanup() -> None:
    """Perform a safe cleanup of all wxPython objects."""
    try:
        # Process any pending events
        for _ in range(5):
            wx.SafeYield()
            time.sleep(0.02)

        # Safely destroy all top-level windows
        safe_destroy_windows()

        # Force garbage collection again
        gc.collect()
        wx.SafeYield()
        time.sleep(0.05)

    except Exception as e:
        logger.warning(f"Error during safe cleanup: {e}")
