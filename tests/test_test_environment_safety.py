"""Regression tests for keeping the test process away from desktop backends."""

from __future__ import annotations

import wx

from accessiweather.notifications import toast_notifier


def test_pytest_uses_wx_stub_by_default():
    """The default pytest run should not construct real wxPython windows."""
    assert wx.App.__module__.endswith("conftest")
    assert wx.Frame.__module__.endswith("conftest")
    assert wx.Dialog.__module__.endswith("conftest")


def test_pytest_suppresses_real_notification_backends():
    """The default pytest run should not reach real OS notification backends."""
    assert toast_notifier.TOASTED_AVAILABLE is False
    assert toast_notifier.WINRT_AVAILABLE is False
    assert toast_notifier.DESKTOP_NOTIFIER_AVAILABLE is False
    assert toast_notifier.NOTIFIER_AVAILABLE is False
    assert toast_notifier._Toast is None
    assert toast_notifier.DesktopNotifier is None
    assert toast_notifier.SafeDesktopNotifier is toast_notifier._TestModeNotifier
