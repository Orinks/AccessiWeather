"""Keyboard accelerator setup and handlers for the app."""

from __future__ import annotations

import logging

import wx

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
            (wx.ACCEL_CTRL, ord("D"), self._on_remove_location_shortcut),
            (wx.ACCEL_CTRL, ord("H"), self._on_history_shortcut),
            (wx.ACCEL_CTRL, ord("1"), self._on_focus_current_conditions_shortcut),
            (wx.ACCEL_CTRL, ord("2"), self._on_focus_hourly_shortcut),
            (wx.ACCEL_CTRL, ord("3"), self._on_focus_daily_shortcut),
            (wx.ACCEL_CTRL, ord("4"), self._on_focus_alerts_shortcut),
            (wx.ACCEL_CTRL, ord("5"), self._on_focus_event_center_shortcut),
            (wx.ACCEL_CTRL, ord("S"), self._on_settings_shortcut),
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
            accel_entries.append(wx.AcceleratorEntry(flags, key, cmd_id))

        accel_table = wx.AcceleratorTable(accel_entries)
        frame.SetAcceleratorTable(accel_table)
        logger.info("Keyboard accelerators set up successfully")

    def _on_refresh_shortcut(self, event) -> None:
        """Handle Ctrl+R / F5 shortcut."""
        if self.main_window:
            self.main_window.on_refresh()

    def _on_add_location_shortcut(self, event) -> None:
        """Handle Ctrl+L shortcut."""
        if self.main_window:
            self.main_window.on_add_location()

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

    def _on_exit_shortcut(self, event) -> None:
        """Handle Ctrl+Q shortcut."""
        self.request_exit()
