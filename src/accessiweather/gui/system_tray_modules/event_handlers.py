"""System tray event handling functionality.

This module provides event handling for system tray interactions including:
- Mouse click events
- Keyboard accessibility events
- Context menu creation and handling
- Menu item event binding
"""

import logging

import wx
import wx.adv

logger = logging.getLogger(__name__)


class TaskBarEventHandler:
    """Mixin class for handling system tray events.

    This mixin expects the following methods to be provided by the implementing class:
    - Bind(event_type, handler, source=None)
    - PopupMenu(menu)

    And the following attributes:
    - frame: The main application frame
    """

    # These methods must be implemented by the class that uses this mixin (wx.adv.TaskBarIcon)
    def Bind(self, event_type, handler, source=None):
        """Bind an event handler. Must be implemented by wx.adv.TaskBarIcon."""
        raise NotImplementedError("Bind must be implemented by wx.adv.TaskBarIcon")

    def PopupMenu(self, menu):
        """Show popup menu. Must be implemented by wx.adv.TaskBarIcon."""
        raise NotImplementedError("PopupMenu must be implemented by wx.adv.TaskBarIcon")

    @property
    def frame(self):
        """The main application frame. Must be set by the implementing class."""
        if not hasattr(self, "_frame"):
            raise NotImplementedError("frame must be set by the implementing class")
        return self._frame

    @frame.setter
    def frame(self, value):
        """Set the main application frame."""
        self._frame = value

    def bind_events(self):
        """Bind all system tray events."""
        # Bind primary events
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_UP, self.on_right_click)

        # Bind additional events for better accessibility
        # These events are sent by Windows when users access the tray icon via keyboard
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_UP, self.on_left_click)
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, self.on_right_down)

        # Note: We no longer register global hotkeys as they interfere with
        # Windows' built-in system tray accessibility (Windows+B navigation)

        logger.debug("TaskBarIcon events bound successfully")

    def on_left_click(self, event):
        """Handle left click event (including keyboard activation).

        This event is triggered when users activate the tray icon via keyboard
        (e.g., pressing Enter when the icon is selected in system tray navigation).

        Args:
            event: The event object
        """
        # For keyboard accessibility, left click should show/hide the main window
        logger.debug("Tray icon activated (left click or keyboard Enter)")
        self.on_show_hide(event)

    def on_left_dclick(self, event):
        """Handle left double-click event.

        Args:
            event: The event object
        """
        self.on_show_hide(event)

    def on_right_click(self, event):
        """Handle right-click event.

        Args:
            event: The event object
        """
        # Create and show the popup menu with proper accessibility focus
        menu = self.CreatePopupMenu()
        if menu:
            # Use PopupMenu which properly handles focus for screen readers
            # This ensures the menu gets keyboard focus and is accessible
            self.PopupMenu(menu)
            menu.Destroy()

    def on_right_down(self, event):
        """Handle right mouse button down event.

        This can be triggered by keyboard (Applications key) when the tray icon is focused.

        Args:
            event: The event object
        """
        # This event can be triggered by Applications key for accessibility
        logger.debug("Right mouse down event (may be from Applications key)")
        # Let the event continue to be processed normally
        event.Skip()

    def CreatePopupMenu(self):
        """Create the popup menu.

        Returns:
            wx.Menu: The popup menu
        """
        # Use the menu handler from the frame to create the menu
        menu, items = self.frame.CreateTaskBarMenu()

        # Check if we have debug items
        if len(items) > 4:
            show_hide_item, refresh_item, settings_item, exit_item, *debug_items = items

            # Bind debug menu events if present
            if debug_items:
                test_alerts_item, verify_interval_item = debug_items
                self.Bind(wx.EVT_MENU, self.on_test_alerts, test_alerts_item)
                self.Bind(wx.EVT_MENU, self.on_verify_interval, verify_interval_item)
        else:
            show_hide_item, refresh_item, settings_item, exit_item = items

        # Bind standard menu events
        self.Bind(wx.EVT_MENU, self.on_show_hide, show_hide_item)
        self.Bind(wx.EVT_MENU, self.on_refresh, refresh_item)
        self.Bind(wx.EVT_MENU, self.on_settings, settings_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)

        return menu

    def on_show_hide(self, event):
        """Handle show/hide menu item.

        Args:
            event: The event object
        """
        # Use the menu handler from the frame
        self.frame.OnTaskBarShowHide(event)

    def on_refresh(self, event):
        """Handle refresh menu item.

        Args:
            event: The event object
        """
        # Call the frame's OnRefresh method
        self.frame.OnRefresh(event)

    def on_settings(self, event):
        """Handle settings menu item.

        Args:
            event: The event object
        """
        # Call the frame's OnSettings method
        self.frame.OnSettings(event)

    def on_exit(self, event):
        """Handle exit menu item.

        Args:
            event: The event object
        """
        # Use the menu handler from the frame
        self.frame.OnTaskBarExit(event)

    def on_test_alerts(self, event):
        """Handle test alerts menu item.

        Args:
            event: The event object
        """
        # Call the frame's test_alert_update method
        if hasattr(self.frame, "test_alert_update"):
            self.frame.test_alert_update()
        else:
            logger.error("Frame does not have test_alert_update method")

    def on_verify_interval(self, event):
        """Handle verify interval menu item.

        Args:
            event: The event object
        """
        # Call the frame's verify_alert_interval method
        if hasattr(self.frame, "verify_alert_interval"):
            self.frame.verify_alert_interval()
        else:
            logger.error("Frame does not have verify_alert_interval method")
