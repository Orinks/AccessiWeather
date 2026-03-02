"""Tests for alerts list Enter key and double-click activation (issue #410)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import wx


class TestAlertsListActivation:
    """Enter key and double-click on the alerts list should open alert details."""

    def _make_main_window(self):
        """Create a MainWindow with enough mocking to test event bindings."""
        from accessiweather.ui.main_window import MainWindow

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)

        # Minimal widget stubs
        win.alerts_list = MagicMock()
        win.view_alert_button = MagicMock()
        win.app = MagicMock()
        win.app.current_weather_data = None
        return win

    def test_bind_events_registers_dclick_and_key_down(self):
        """_bind_events should bind EVT_LISTBOX_DCLICK and EVT_KEY_DOWN on alerts_list."""
        win = self._make_main_window()

        # Provide remaining widgets that _bind_events touches
        win.Bind = MagicMock()
        win.location_dropdown = MagicMock()
        win.add_button = MagicMock()
        win.remove_button = MagicMock()
        win.refresh_button = MagicMock()
        win.explain_button = MagicMock()
        win.discussion_button = MagicMock()
        win.settings_button = MagicMock()

        win._bind_events()

        # Collect the event types bound on alerts_list
        bound_events = [call.args[0] for call in win.alerts_list.Bind.call_args_list]
        assert wx.EVT_LISTBOX_DCLICK in bound_events
        assert wx.EVT_KEY_DOWN in bound_events

    def test_enter_key_calls_on_view_alert(self):
        """Pressing Enter in alerts list should trigger _on_view_alert."""
        win = self._make_main_window()
        win._on_view_alert = MagicMock()

        event = MagicMock()
        event.GetKeyCode.return_value = wx.WXK_RETURN

        win._on_alerts_list_key(event)

        win._on_view_alert.assert_called_once_with(event)
        event.Skip.assert_not_called()

    def test_numpad_enter_key_calls_on_view_alert(self):
        """Pressing numpad Enter in alerts list should also trigger _on_view_alert."""
        win = self._make_main_window()
        win._on_view_alert = MagicMock()

        event = MagicMock()
        event.GetKeyCode.return_value = wx.WXK_NUMPAD_ENTER

        win._on_alerts_list_key(event)

        win._on_view_alert.assert_called_once_with(event)
        event.Skip.assert_not_called()

    def test_other_key_is_skipped(self):
        """Non-Enter keys should be passed through via event.Skip()."""
        win = self._make_main_window()
        win._on_view_alert = MagicMock()

        event = MagicMock()
        event.GetKeyCode.return_value = ord("A")

        win._on_alerts_list_key(event)

        win._on_view_alert.assert_not_called()
        event.Skip.assert_called_once()
