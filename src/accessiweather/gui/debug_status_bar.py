"""Debug status bar for AccessiWeather

This module provides a status bar panel that shows debug information.
"""

import logging
import time
from typing import Optional

import wx

logger = logging.getLogger(__name__)


class DebugStatusBar(wx.StatusBar):
    """Status bar with debug information panels."""

    def __init__(self, parent, update_interval_key):
        """Initialize the debug status bar.

        Args:
            parent: Parent window
            update_interval_key: Config key for update interval
        """
        super().__init__(parent, style=wx.STB_SIZEGRIP)

        self.parent = parent
        self.update_interval_key = update_interval_key

        # Create the status bar fields
        self.SetFieldsCount(4)

        # Set the relative widths of the fields
        self.SetStatusWidths([-1, 150, 150, 200])

        # Create a timer for updating the status bar
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.timer.Start(1000)  # Update every second

        # Initialize the status bar
        self.UpdateStatusBar()

    def OnTimer(self, event):  # event is required by wx
        """Handle timer event.

        Args:
            event: Timer event
        """
        self.UpdateStatusBar()

    def UpdateStatusBar(self):
        """Update the status bar with current information."""
        # Field 0: Main status text (set by the application)

        # Field 1: Update interval and time since last update
        update_interval = self._get_update_interval()
        time_since_last = self._get_time_since_last_update()
        next_update_in = max(0, update_interval * 60 - time_since_last)

        self.SetStatusText(f"Update: {int(next_update_in)}s", 1)

        # Field 2: Current location
        location_name = self._get_current_location()
        if location_name:
            self.SetStatusText(f"Location: {location_name}", 2)
        else:
            self.SetStatusText("No location selected", 2)

        # Field 3: Memory usage
        memory_usage = self._get_memory_usage()
        self.SetStatusText(f"Memory: {memory_usage:.1f} MB", 3)

    def _get_update_interval(self) -> int:
        """Get the update interval from the config.

        Returns:
            Update interval in minutes
        """
        if hasattr(self.parent, "config"):
            settings = self.parent.config.get("settings", {})
            return int(settings.get(self.update_interval_key, 30))
        return 30

    def _get_time_since_last_update(self) -> float:
        """Get the time since the last update.

        Returns:
            Time since last update in seconds
        """
        if hasattr(self.parent, "last_update"):
            return float(time.time() - self.parent.last_update)
        return 0.0

    def _get_current_location(self) -> Optional[str]:
        """Get the current location name.

        Returns:
            Current location name or None
        """
        if hasattr(self.parent, "location_service"):
            location_name = self.parent.location_service.get_current_location_name()
            return str(location_name) if location_name is not None else None
        return None

    def _get_memory_usage(self) -> float:
        """Get the current memory usage.

        Returns:
            Memory usage in MB
        """
        try:
            import psutil  # type: ignore

            process = psutil.Process()
            memory_info = process.memory_info()
            return float(memory_info.rss / 1024 / 1024)  # Convert to MB
        except ImportError:
            return 0.0
