"""Keyboard accelerator setup and handlers for the app."""

from __future__ import annotations

import contextlib
import logging

import wx

from .native_shortcuts import install_accelerator_table_preserving_native_close
from .shortcut_preferences import (
    WINDOW_TRAY_SHORTCUTS,
    resolve_shortcut_binding,
)

logger = logging.getLogger(__name__)


class AppShortcutsMixin:
    def _get_shortcut_settings(self):
        """Return live settings when available, else a default placeholder."""
        config_manager = getattr(self, "config_manager", None)
        if config_manager is None:
            return object()
        try:
            return config_manager.get_settings()
        except Exception:
            logger.debug("Falling back to default shortcut settings", exc_info=True)
            return object()

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
        settings = self._get_shortcut_settings()
        tray_shortcut_bindings: list[tuple[int, int, object, str]] = []
        for preference in WINDOW_TRAY_SHORTCUTS:
            binding = resolve_shortcut_binding(
                getattr(settings, preference.setting_name, preference.default),
                default=preference.default,
            )
            if binding is None:
                continue
            tray_shortcut_bindings.append(
                (
                    binding.accelerator_flags(wx),
                    binding.key_code(wx),
                    getattr(self, preference.handler_name),
                    preference.label,
                )
            )
        accelerators.extend(
            (flags, key, handler) for flags, key, handler, _label in tray_shortcut_bindings
        )

        # Create accelerator table
        # Access the frame directly (MainWindow is now a SizedFrame)
        frame = self.main_window
        accel_entries = []
        for flags, key, handler in accelerators:
            cmd_id = wx.NewIdRef()
            frame.Bind(wx.EVT_MENU, handler, id=cmd_id)
            accel_entries.append((flags, key, cmd_id))

        install_accelerator_table_preserving_native_close(frame, accel_entries)
        self._register_global_hotkeys(settings=settings)
        logger.info("Keyboard accelerators set up successfully")

    def _register_global_hotkeys(self, *, settings) -> None:
        """Register configurable tray/window shortcuts as global hotkeys when supported."""
        frame = self.main_window
        self._unregister_global_hotkeys()
        if frame is None or not hasattr(frame, "RegisterHotKey"):
            return

        hotkey_event = getattr(wx, "EVT_HOTKEY", None)
        if hotkey_event is None:
            return

        registered_ids: list[int] = []
        for preference in WINDOW_TRAY_SHORTCUTS:
            binding = resolve_shortcut_binding(
                getattr(settings, preference.setting_name, preference.default),
                default=preference.default,
            )
            if binding is None:
                continue

            hotkey_id = int(wx.NewIdRef())
            try:
                registered = frame.RegisterHotKey(
                    hotkey_id,
                    binding.hotkey_modifiers(wx),
                    binding.key_code(wx),
                )
            except Exception:
                logger.debug(
                    "Failed to register global hotkey %s for %s",
                    binding.normalized,
                    preference.label,
                    exc_info=True,
                )
                continue
            if not registered:
                logger.warning(
                    "Global hotkey %s for %s could not be registered",
                    binding.normalized,
                    preference.label,
                )
                continue

            frame.Bind(hotkey_event, getattr(self, preference.handler_name), id=hotkey_id)
            registered_ids.append(hotkey_id)

        self._registered_hotkey_ids = registered_ids

    def _unregister_global_hotkeys(self) -> None:
        """Remove previously-registered global hotkeys."""
        frame = self.main_window
        hotkey_event = getattr(wx, "EVT_HOTKEY", None)
        for hotkey_id in getattr(self, "_registered_hotkey_ids", []):
            if frame is not None and hasattr(frame, "UnregisterHotKey"):
                with contextlib.suppress(Exception):
                    frame.UnregisterHotKey(hotkey_id)
            if frame is not None and hotkey_event is not None and hasattr(frame, "Unbind"):
                with contextlib.suppress(Exception):
                    frame.Unbind(hotkey_event, id=hotkey_id)
        self._registered_hotkey_ids = []

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

    def _on_show_main_window_shortcut(self, event) -> None:
        """Show or restore the main window, including from the tray."""
        if getattr(self, "tray_icon", None) is not None:
            self.tray_icon.show_main_window()
            return
        if self.main_window:
            self.main_window.Show(True)
            self.main_window.Iconize(False)
            self.main_window.Raise()
            self.main_window.SetFocus()

    def _on_hide_main_window_shortcut(self, event) -> None:
        """Hide the main window to the tray when available."""
        tray_icon = getattr(self, "tray_icon", None)
        if tray_icon is not None:
            tray_icon.hide_main_window()
            return
        if self.main_window and hasattr(self.main_window, "set_status"):
            self.main_window.set_status("Tray icon unavailable, so the window cannot be hidden.")

    def _on_read_tray_info_shortcut(self, event) -> None:
        """Speak the current tray tooltip text through the app's announcer path."""
        tray_icon = getattr(self, "tray_icon", None)
        if tray_icon is not None:
            tray_icon.announce_tooltip()
            return
        if self.main_window and hasattr(self.main_window, "set_status"):
            self.main_window.set_status("Tray information is unavailable.")
