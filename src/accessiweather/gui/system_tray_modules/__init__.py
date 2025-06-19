"""System tray functionality for AccessiWeather.

This module provides the TaskBarIcon class for system tray integration,
combining icon management, event handling, and weather data formatting.
"""

import logging
from typing import Any, Dict, List, Optional

import wx.adv

from .event_handlers import TaskBarEventHandler
from .icon_manager import TaskBarIconManager
from .weather_formatter import WeatherDataFormatter

logger = logging.getLogger(__name__)

# Note: We rely on Windows' built-in system tray accessibility instead of global hotkeys
# This provides better compatibility with screen readers and system navigation


class TaskBarIcon(wx.adv.TaskBarIcon, TaskBarIconManager, TaskBarEventHandler, WeatherDataFormatter):
    """System tray icon for AccessiWeather.
    
    Combines icon management, event handling, and weather data formatting
    into a single cohesive system tray interface.
    """

    def __init__(self, frame):
        """Initialize the TaskBarIcon.

        Args:
            frame: The main application frame (WeatherApp)
        """
        # Initialize all parent classes
        wx.adv.TaskBarIcon.__init__(self)
        TaskBarIconManager.__init__(self)
        WeatherDataFormatter.__init__(self)

        self.frame = frame

        # Set the icon
        self.set_icon()

        # Bind events
        self.bind_events()

        logger.debug("TaskBarIcon initialized successfully")


# Export the main class and utility functions for backward compatibility
__all__ = ["TaskBarIcon"]
