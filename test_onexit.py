"""Test script for the OnExit method

This script creates a simple application with a custom App class that
overrides the OnExit method to verify that it's called when the application
exits.
"""

import logging
import sys
import wx

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


class TestFrame(wx.Frame):
    """Test frame for the OnExit test"""

    def __init__(self, parent):
        """Initialize the frame"""
        super().__init__(parent, title="OnExit Test", size=(400, 300))
        
        # Create a panel
        panel = wx.Panel(self)
        
        # Create a button to close the application
        close_btn = wx.Button(panel, label="Close Application", pos=(150, 100))
        close_btn.Bind(wx.EVT_BUTTON, self.OnClose)
        
        # Bind the close event
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        
        # Center the frame
        self.Center()
        
        logger.debug("TestFrame initialized")
    
    def OnClose(self, event):
        """Handle close event"""
        logger.debug("TestFrame.OnClose called")
        self.Destroy()


class TestApp(wx.App):
    """Test application for the OnExit test"""
    
    def __init__(self):
        """Initialize the application"""
        super().__init__(False)
        logger.debug("TestApp initialized")
    
    def OnInit(self):
        """Called when the application is initialized"""
        logger.debug("TestApp.OnInit called")
        
        # Create the main frame
        self.frame = TestFrame(None)
        self.frame.Show()
        
        # Set the top window
        self.SetTopWindow(self.frame)
        
        return True
    
    def OnExit(self):
        """Called when the application is about to exit"""
        logger.debug("TestApp.OnExit called - This is where cleanup would happen")
        
        # Perform any necessary cleanup here
        
        # Call the parent class OnExit
        return super().OnExit()


def main():
    """Main entry point for the test script"""
    logger.info("Starting OnExit test application")
    
    # Create the application
    app = TestApp()
    
    # Start the main loop
    app.MainLoop()
    
    logger.info("OnExit test application exited")


if __name__ == "__main__":
    sys.exit(main())
