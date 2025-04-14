#!/usr/bin/env python
"""
Debug script to help identify segmentation faults in wxPython tests.
"""

import faulthandler
import gc
import logging
import os
import sys
import time
import traceback
from pathlib import Path

import wx

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create a log file for faulthandler
log_dir = Path(".").absolute()
fault_log_path = log_dir / "debug_segfault.log"

# Enable faulthandler to stderr first
faulthandler.enable()

# Then enable it to the log file
try:
    with open(fault_log_path, "w") as f:
        f.write("Faulthandler log file created\n")

    # Keep the file open for faulthandler
    log_file = open(fault_log_path, "a")
    faulthandler.enable(file=log_file)
    logger.info(f"Faulthandler enabled, logging to {fault_log_path}")
except Exception as e:
    logger.error(f"Failed to set up faulthandler log file: {e}")
    log_file = None


class TestApp(wx.App):
    def OnInit(self):
        self.frame = wx.Frame(None, title="Debug Segfault")
        self.frame.Show()
        return True

    def run_test(self):
        """Run a simple test that might trigger segmentation faults."""
        logger.info("Starting test")

        # Create some wxPython objects
        panel = wx.Panel(self.frame)
        text_ctrl = wx.TextCtrl(panel, value="Test")
        combo = wx.ComboBox(panel, choices=["Item 1", "Item 2", "Item 3"])

        # Force garbage collection
        logger.info("Forcing garbage collection")
        gc.collect()

        # Schedule app exit
        wx.CallLater(1000, self.cleanup_and_exit)

    def cleanup_and_exit(self):
        """Clean up and exit the application."""
        logger.info("Cleaning up")

        # Hide the frame
        if self.frame:
            self.frame.Hide()
            wx.SafeYield()

        # Process pending events
        for _ in range(5):
            wx.SafeYield()
            time.sleep(0.05)

        # Destroy the frame
        if self.frame:
            self.frame.Destroy()
            wx.SafeYield()

        # Process pending events again
        for _ in range(5):
            wx.SafeYield()
            time.sleep(0.05)

        # Force garbage collection again
        logger.info("Final garbage collection")
        gc.collect()

        # Exit the main loop
        logger.info("Exiting main loop")
        self.ExitMainLoop()


def main():
    """Main function to run the test."""
    logger.info("Starting application")

    # Create the application
    app = TestApp(False)  # False means don't redirect stdout/stderr

    # Schedule the test to run after the app is initialized
    wx.CallAfter(app.run_test)

    # Start the main loop
    app.MainLoop()

    logger.info("Application exited normally")

    # Close the log file
    if log_file is not None:
        try:
            # Dump a final traceback before closing
            faulthandler.dump_traceback(file=log_file, all_threads=True)
            log_file.flush()
            log_file.close()
        except Exception as e:
            print(f"Error closing log file: {e}")


if __name__ == "__main__":
    main()
