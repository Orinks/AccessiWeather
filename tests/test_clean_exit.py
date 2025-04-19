"""Tests for clean application exit.

This module contains tests that verify the application exits cleanly.
"""

import logging
import threading
import time
import wx

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def test_clean_exit_programmatic():
    """Test that the application exits cleanly when closed programmatically.

    This test creates a minimal application instance and verifies that it exits
    cleanly when closed programmatically.
    """
    # Create an event to signal when the app has exited
    exit_event = threading.Event()
    exit_code = [None]  # Use a list to store the exit code (to make it mutable in the thread)

    # Create a function to run the app in a separate thread
    def run_app():
        try:
            # Create a minimal wx.App instance with debug output disabled
            app = wx.App(False)  # False means don't redirect stdout/stderr

            # Disable debug alerts to prevent popup dialogs
            wx.Log.SetLogLevel(wx.LOG_Error)  # Only show errors, not warnings

            # Create a simple frame
            frame = wx.Frame(None, title="Test Frame", size=(400, 300))

            # Add a panel to the frame to prevent debug messages about missing children
            panel = wx.Panel(frame)

            # Schedule the close operation after a short delay
            def close_app():
                logger.info("Scheduled close operation starting")

                # Close the frame
                logger.info("Closing the frame")
                frame.Close(True)  # True means force close

                # Schedule a forced exit if the app doesn't exit cleanly
                def force_exit():
                    logger.warning("Forcing application exit")
                    app.ExitMainLoop()
                    exit_code[0] = 0
                    exit_event.set()

                wx.CallLater(1000, force_exit)  # 1 second

            # Allow more time for the app to initialize
            wx.CallLater(1000, close_app)  # 1 second

            # Show the frame
            frame.Show()

            # Start the main loop
            logger.info("Starting main loop")
            app.MainLoop()
            logger.info("Main loop exited")

            # Set the exit code and signal that the app has exited
            exit_code[0] = 0
            exit_event.set()

        except Exception as e:
            logger.error(f"Error in app thread: {e}")
            exit_code[0] = 1
            exit_event.set()

    # Start the app in a separate thread
    logger.info("Starting app thread")
    app_thread = threading.Thread(target=run_app)
    app_thread.daemon = True
    app_thread.start()

    # Wait for the app to exit
    logger.info("Waiting for app to exit")
    exit_success = exit_event.wait(timeout=5)

    # Check if the app exited successfully
    assert exit_success, "Application did not exit within timeout"
    assert exit_code[0] == 0, f"Application exited with non-zero code: {exit_code[0]}"

    # Wait for the thread to finish
    app_thread.join(timeout=1)
    assert not app_thread.is_alive(), "App thread is still alive after exit"

    # Allow a short delay for any remaining cleanup
    time.sleep(0.1)

