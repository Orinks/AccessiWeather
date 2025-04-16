"""Faulthandler setup for tests.

This module enables faulthandler for all tests to help debug segmentation faults.
Import this module at the top of any test file that might encounter segmentation faults.
"""

import atexit
import faulthandler
import os
import time
import wx

# Enable faulthandler to debug segmentation faults
faulthandler.enable()

# Create a log directory for faulthandler output
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

# Create a log file for faulthandler output
log_file_path = os.path.join(log_dir, "faulthandler.log")
fault_log = open(log_file_path, "w")
faulthandler.enable(file=fault_log)

# Register a cleanup function to close the log file
atexit.register(fault_log.close)


def cleanup_wx_app(app):
    """Safely clean up a wxPython application or window.

    This function safely destroys a wxPython application or window,
    ensuring proper cleanup to prevent memory leaks and segmentation faults.

    Args:
        app: A wxPython application or window to clean up
    """
    if app is None:
        return

    try:
        # Hide the window first
        wx.CallAfter(app.Hide)
        wx.SafeYield()
        time.sleep(0.1)  # Give a moment for events to process

        # Then destroy it
        wx.CallAfter(app.Destroy)
        wx.SafeYield()
        time.sleep(0.1)  # Give a moment for events to process
    except Exception as e:
        print(f"Error during wx cleanup: {e}")
