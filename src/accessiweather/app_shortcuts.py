"""Keyboard accelerator setup and handlers for the app."""

from __future__ import annotations

import logging

import wx

from .native_shortcuts import install_accelerator_table_preserving_native_close

logger = logging.getLogger(__name__)


class AppShortcutsMixin:
    def _setup_accelerators(self) -> None:
        """Set up keyboard accelerators (shortcuts)."""
        if not self.main_window:
            return

        # Define keyboard shortcuts
        accelerators = [
            (wx.ACCEL_CTRL, ord("R"), self._on_refresh_shortcut),
            (wx.ACCEL_CTRL, ord("L"), self._on_add_location_shortcut),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("L"), self._on_edit_location_shortcut),
            (wx.ACCEL_CTRL, ord("D"), self._on_remove_location_shortcut),
            (wx.ACCEL_CTRL, ord("H"), self._on_history_shortcut),
            (wx.ACCEL_CTRL, ord("1"), self._on_focus_current_conditions_shortcut),
            (wx.ACCEL_CTRL, ord("2"), self._on_focus_hourly_shortcut),
            (wx.ACCEL_CTRL, ord("3"), self._on_focus_daily_shortcut),
            (wx.ACCEL_CTRL, ord("4"), self._on_focus_alerts_shortcut),
            (wx.ACCEL_CTRL, ord("5"), self._on_focus_event_center_shortcut),
            (wx.ACCEL_CTRL, ord("S"), self._on_settings_shortcut),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("W"), self._on_show_window_shortcut),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("H"), self._on_hide_window_shortcut),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("I"), self._on_read_tray_info_shortcut),
            (wx.ACCEL_CTRL, ord("Q"), self._on_exit_shortcut),
            (wx.ACCEL_NORMAL, wx.WXK_F5, self._on_refresh_shortcut),
            (wx.ACCEL_NORMAL, getattr(wx, "WXK_F6", wx.WXK_F5), self._on_cycle_sections_shortcut),
        ]

        # Create accelerator table
        # Access the frame directly (MainWindow is now a SizedFrame)
        frame = self.main_window
        accel_entries = []
        for flags, key, handler in accelerators:
            cmd_id = wx.NewIdRef()
            frame.Bind(wx.EVT_MENU, handler, id=cmd_id)
            accel_entries.append((flags, key, cmd_id))

        install_accelerator_table_preserving_native_close(frame, accel_entries)
        logger.info("Keyboard accelerators set up successfully")

    def _on_refresh_shortcut(self, event) -> None:
        """Handle Ctrl+R / F5 shortcut."""
        if self.main_window:
            self.main_window.on_refresh()

    def _on_add_location_shortcut(self, event) -> None:
        """Handle Ctrl+L shortcut."""
        if self.main_window:
            self.main_window.on_add_location()

    def _on_edit_location_shortcut(self, event) -> None:
        """Handle Ctrl+Shift+L shortcut."""
        if self.main_window:
            self.main_window.on_edit_location()

    def _on_remove_location_shortcut(self, event) -> None:
        """Handle Ctrl+D shortcut."""
        if self.main_window:
            self.main_window.on_remove_location()

    def _on_history_shortcut(self, event) -> None:
        """Handle Ctrl+H shortcut."""
        if self.main_window:
            self.main_window.on_view_history()

    def _focus_section_shortcut(self, number: int) -> None:
        """Delegate a numbered section-focus shortcut to the main window."""
        if self.main_window:
            self.main_window.focus_section_by_number(number)

    def _on_focus_current_conditions_shortcut(self, event) -> None:
        """Handle Ctrl+1 shortcut."""
        self._focus_section_shortcut(1)

    def _on_focus_hourly_shortcut(self, event) -> None:
        """Handle Ctrl+2 shortcut."""
        self._focus_section_shortcut(2)

    def _on_focus_daily_shortcut(self, event) -> None:
        """Handle Ctrl+3 shortcut."""
        self._focus_section_shortcut(3)

    def _on_focus_alerts_shortcut(self, event) -> None:
        """Handle Ctrl+4 shortcut."""
        self._focus_section_shortcut(4)

    def _on_focus_event_center_shortcut(self, event) -> None:
        """Handle Ctrl+5 shortcut."""
        self._focus_section_shortcut(5)

    def _on_cycle_sections_shortcut(self, event) -> None:
        """Handle F6 shortcut."""
        if self.main_window and hasattr(self.main_window, "cycle_section_focus"):
            self.main_window.cycle_section_focus()

    def _on_settings_shortcut(self, event) -> None:
        """Handle Ctrl+S shortcut."""
        if self.main_window:
            self.main_window.on_settings()

    def _on_show_window_shortcut(self, event) -> None:
        """Handle Ctrl+Shift+W shortcut."""
        tray_icon = getattr(self, "tray_icon", None)
        if tray_icon and hasattr(tray_icon, "show_main_window"):
            tray_icon.show_main_window()
            return
        if self.main_window:
            self.main_window.Show(True)
            self.main_window.Iconize(False)
            self.main_window.Raise()
            self.main_window.SetFocus()

    def _on_hide_window_shortcut(self, event) -> None:
        """Handle Ctrl+Shift+H shortcut."""
        if self.main_window and getattr(self, "tray_icon", None):
            self.main_window._minimize_to_tray()
            return
        self._announce_shortcut_status("System tray is unavailable.")

    def _on_read_tray_info_shortcut(self, event) -> None:
        """Handle Ctrl+Shift+I shortcut."""
        tray_icon = getattr(self, "tray_icon", None)
        if tray_icon and hasattr(tray_icon, "get_tooltip_text"):
            tooltip = tray_icon.get_tooltip_text()
            self._announce_shortcut_status(f"Tray information: {tooltip}")
            return
        self._announce_shortcut_status("System tray information is unavailable.")

    def _announce_shortcut_status(self, message: str) -> None:
        """Announce shortcut feedback via the main window status channel."""
        if self.main_window and hasattr(self.main_window, "set_status"):
            self.main_window.set_status(message)

    def _on_exit_shortcut(self, event) -> None:
        """Handle Ctrl+Q shortcut."""
        self.request_exit()
