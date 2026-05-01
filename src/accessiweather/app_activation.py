"""Notification activation and immediate alert popup helpers for the app."""

from __future__ import annotations

import logging
import sys

import wx

from .notification_activation import NotificationActivationRequest

logger = logging.getLogger(__name__)


def show_alert_dialog(parent, alert, settings=None) -> None:
    """Lazy wrapper for the single-alert details dialog."""
    from .ui.dialogs import show_alert_dialog as _show_alert_dialog

    _show_alert_dialog(parent, alert, settings)


def show_alerts_summary_dialog(parent, alerts) -> None:
    """Lazy wrapper for the combined multi-alert dialog."""
    from .ui.dialogs import show_alerts_summary_dialog as _show_alerts_summary_dialog

    _show_alerts_summary_dialog(parent, alerts)


class AppActivationMixin:
    def _schedule_startup_activation_request(self) -> None:
        """Route any activation request passed directly to this process."""
        if self._activation_request is not None:
            from . import app as app_module

            app_module.wx.CallAfter(
                self._handle_notification_activation_request, self._activation_request
            )

    def _queue_immediate_alert_popup(self, alerts) -> None:
        """Queue an in-app alert popup onto the UI thread."""
        if not alerts:
            return
        from . import app as app_module

        app_module.wx.CallAfter(self._show_immediate_alert_popup, list(alerts))

    def _show_immediate_alert_popup(self, alerts) -> None:
        """Show the opted-in in-app alert popup without restoring the main window."""
        if self.main_window is None or self.config_manager is None or not alerts:
            return

        if len(alerts) == 1:
            from . import app as app_module

            app_module.show_alert_dialog(
                self.main_window, alerts[0], self.config_manager.get_settings()
            )
            return

        from . import app as app_module

        app_module.show_alerts_summary_dialog(self.main_window, alerts)

    def _wire_notifier_activation_callback(self) -> None:
        """Connect the notifier's in-process activation callback to the UI thread."""
        notifier = self._notifier
        if notifier is None or not hasattr(notifier, "on_activation"):
            return

        def _on_toast_activated(result) -> None:
            """Handle toast activation from the notifier worker thread."""
            arguments = getattr(result, "arguments", None)
            if not arguments:
                return
            from .notification_activation import extract_activation_request_from_argv

            request = extract_activation_request_from_argv([arguments])
            if request is not None:
                wx.CallAfter(self._handle_notification_activation_request, request)

        notifier.on_activation = _on_toast_activated

    def _start_activation_handoff_polling(self) -> None:
        """Poll for handoff requests on the UI thread."""
        if self._activation_handoff_timer is not None:
            self._activation_handoff_timer.Stop()
        self._activation_handoff_timer = wx.Timer(self)
        self.Bind(
            wx.EVT_TIMER,
            self._on_activation_handoff_timer,
            self._activation_handoff_timer,
        )
        self._activation_handoff_timer.Start(750)

    def _on_activation_handoff_timer(self, event) -> None:
        """Consume and route any pending notification activation handoff request."""
        if self.single_instance_manager is None:
            return
        request = self.single_instance_manager.consume_activation_handoff()
        if request is not None:
            self._handle_notification_activation_request(request)

    def _handle_notification_activation_request(
        self, request: NotificationActivationRequest
    ) -> None:
        """Route a notification activation request, restoring the window only when needed."""
        if self.main_window is None:
            return

        # For discussion/alert_details, show the dialog directly without
        # restoring the main window — the modal dialog appears on its own.
        if request.kind == "discussion":
            self.main_window._on_discussion()
            return

        if request.kind == "alert_details" and request.alert_id:
            alert_index = self._find_active_alert_index(request.alert_id)
            if alert_index is not None:
                self.main_window._show_alert_details(alert_index)
            return

        # generic_fallback and any unknown kind: just restore the main window.
        if self.tray_icon is not None:
            self.tray_icon.show_main_window()
        else:
            self.main_window.Show(True)
            self.main_window.Iconize(False)
            self._force_foreground_window(self.main_window)

    def _find_active_alert_index(self, alert_id: str) -> int | None:
        """Locate the current active alert index for an activation request."""
        alerts = getattr(getattr(self, "current_weather_data", None), "alerts", None)
        if alerts is None or not hasattr(alerts, "get_active_alerts"):
            return None

        for index, alert in enumerate(alerts.get_active_alerts()):
            get_unique_id = getattr(alert, "get_unique_id", None)
            if callable(get_unique_id) and get_unique_id() == alert_id:
                return index
        return None

    @staticmethod
    def _force_foreground_window(frame) -> None:
        """Use Win32 API to reliably bring window to foreground on Windows."""
        if sys.platform != "win32":
            frame.Raise()
            return
        try:
            import ctypes

            hwnd = frame.GetHandle()
            user32 = ctypes.windll.user32
            SW_RESTORE = 9
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            user32.AllowSetForegroundWindow(ctypes.windll.kernel32.GetCurrentProcessId())
            user32.SetForegroundWindow(hwnd)
        except Exception:
            frame.Raise()
