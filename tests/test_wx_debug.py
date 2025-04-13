"""Test case for demonstrating wxPython debugging tools.

This module provides a test case that demonstrates the use of the wxPython
debugging tools, including faulthandler, memory tracking, and improved cleanup.
"""

import gc
import logging
import time

import pytest
import wx

from accessiweather.utils.faulthandler_utils import dump_traceback
from tests.memory_tracker import log_memory_stats, track_object
from tests.wx_cleanup_utils import safe_destroy_windows

logger = logging.getLogger(__name__)


class TestWxDebug:
    """Test case for demonstrating wxPython debugging tools."""

    @pytest.fixture(autouse=True)
    def setup_method(self, wx_app_isolated):
        """Set up the test fixture.

        Args:
            wx_app_isolated: wxPython application fixture
        """
        self.app = wx_app_isolated
        self.frame = None
        yield
        # Cleanup is handled by the wx_app_isolated fixture

    def test_basic_window_creation(self):
        """Test basic window creation and destruction."""
        logger.info("Creating frame")
        self.frame = wx.Frame(None, title="Test Frame")
        track_object(self.frame, "test_frame")  # Track the frame for memory analysis
        
        # Create some controls
        panel = wx.Panel(self.frame)
        track_object(panel, "panel")
        
        text_ctrl = wx.TextCtrl(panel, value="Test")
        track_object(text_ctrl, "text_ctrl")
        
        button = wx.Button(panel, label="Test Button")
        track_object(button, "button")
        
        # Show the frame
        self.frame.Show()
        wx.SafeYield()
        
        # Verify the frame is shown
        assert self.frame.IsShown()
        
        # Dump traceback for debugging
        dump_traceback(all_threads=False)
        
        # Log memory statistics
        log_memory_stats()
        
        # Hide the frame
        self.frame.Hide()
        wx.SafeYield()
        
        # Process events
        for _ in range(5):
            wx.SafeYield()
            time.sleep(0.01)
        
        # Destroy the frame
        self.frame.Destroy()
        wx.SafeYield()
        
        # Set to None to help garbage collection
        self.frame = None
        
        # Force garbage collection
        gc.collect()
        
        # Log memory statistics again
        log_memory_stats()

    def test_multiple_windows(self):
        """Test creating and destroying multiple windows."""
        logger.info("Creating multiple windows")
        
        # Create multiple frames
        frames = []
        for i in range(5):
            frame = wx.Frame(None, title=f"Test Frame {i}")
            track_object(frame, f"frame_{i}")
            frame.Show()
            frames.append(frame)
        
        # Process events
        wx.SafeYield()
        
        # Verify all frames are shown
        for i, frame in enumerate(frames):
            assert frame.IsShown(), f"Frame {i} is not shown"
        
        # Log memory statistics
        log_memory_stats()
        
        # Safely destroy all windows
        safe_destroy_windows(frames)
        
        # Clear the list to help garbage collection
        frames.clear()
        
        # Force garbage collection
        gc.collect()
        
        # Log memory statistics again
        log_memory_stats()

    @pytest.mark.parametrize("memory_tracker", [True], indirect=True)
    def test_with_memory_tracking(self, memory_tracker):
        """Test with memory tracking enabled.
        
        Args:
            memory_tracker: Memory tracking fixture
        """
        logger.info("Testing with memory tracking")
        
        # Create a frame
        frame = wx.Frame(None, title="Memory Tracked Frame")
        panel = wx.Panel(frame)
        
        # Create a large number of controls to test memory tracking
        for i in range(20):
            ctrl = wx.TextCtrl(panel, value=f"Text {i}")
            track_object(ctrl, f"text_ctrl_{i}")
        
        # Show the frame
        frame.Show()
        wx.SafeYield()
        
        # Hide and destroy the frame
        frame.Hide()
        wx.SafeYield()
        frame.Destroy()
        wx.SafeYield()
        
        # Force garbage collection
        gc.collect()
