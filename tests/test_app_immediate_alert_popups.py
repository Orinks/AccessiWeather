from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.app import AccessiWeatherApp, show_alert_dialog, show_alerts_summary_dialog


class _AlertStub:
    def __init__(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def get_unique_id(self) -> str:
        return self._unique_id


def _dialogs_module(
    *,
    show_single: MagicMock | None = None,
    show_summary: MagicMock | None = None,
) -> ModuleType:
    module = ModuleType("accessiweather.ui.dialogs")
    module.show_alert_dialog = show_single or MagicMock()
    module.show_alerts_summary_dialog = show_summary or MagicMock()
    return module


def test_show_alert_dialog_lazy_wrapper_forwards_to_dialog_module() -> None:
    parent = object()
    alert = _AlertStub("alpha")
    mock_show_single = MagicMock()
    dialogs_module = _dialogs_module(show_single=mock_show_single)

    with patch.dict(sys.modules, {"accessiweather.ui.dialogs": dialogs_module}):
        show_alert_dialog(parent, alert)

    mock_show_single.assert_called_once_with(parent, alert)


def test_show_alerts_summary_dialog_lazy_wrapper_forwards_to_dialog_module() -> None:
    parent = object()
    alerts = [_AlertStub("alpha"), _AlertStub("beta")]
    mock_show_summary = MagicMock()
    dialogs_module = _dialogs_module(show_summary=mock_show_summary)

    with patch.dict(sys.modules, {"accessiweather.ui.dialogs": dialogs_module}):
        show_alerts_summary_dialog(parent, alerts)

    mock_show_summary.assert_called_once_with(parent, alerts)


def test_queue_immediate_alert_popup_uses_callafter_with_alert_copy() -> None:
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    alerts = (_AlertStub("alpha"), _AlertStub("beta"))

    with patch("accessiweather.app.wx.CallAfter") as mock_call_after:
        app._queue_immediate_alert_popup(alerts)

    mock_call_after.assert_called_once()
    callback, queued_alerts = mock_call_after.call_args.args
    assert callback == app._show_immediate_alert_popup
    assert queued_alerts == list(alerts)
    assert isinstance(queued_alerts, list)


def test_queue_immediate_alert_popup_skips_empty_alert_list() -> None:
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)

    with patch("accessiweather.app.wx.CallAfter") as mock_call_after:
        app._queue_immediate_alert_popup([])

    mock_call_after.assert_not_called()


def test_show_immediate_alert_popup_uses_existing_single_alert_dialog() -> None:
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.main_window = MagicMock()
    app.tray_icon = SimpleNamespace(show_main_window=MagicMock())
    alert = _AlertStub("alpha")

    with (
        patch("accessiweather.app.show_alert_dialog") as mock_show_alert_dialog,
        patch("accessiweather.app.show_alerts_summary_dialog") as mock_show_summary_dialog,
    ):
        app._show_immediate_alert_popup([alert])

    mock_show_alert_dialog.assert_called_once_with(app.main_window, alert)
    mock_show_summary_dialog.assert_not_called()


def test_show_immediate_alert_popup_uses_combined_dialog_for_multiple_alerts() -> None:
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.main_window = MagicMock()
    app.tray_icon = SimpleNamespace(show_main_window=MagicMock())
    alerts = [_AlertStub("alpha"), _AlertStub("beta")]

    with (
        patch("accessiweather.app.show_alert_dialog") as mock_show_alert_dialog,
        patch("accessiweather.app.show_alerts_summary_dialog") as mock_show_summary_dialog,
    ):
        app._show_immediate_alert_popup(alerts)

    mock_show_alert_dialog.assert_not_called()
    mock_show_summary_dialog.assert_called_once_with(app.main_window, alerts)


def test_show_immediate_alert_popup_does_not_restore_main_window() -> None:
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.main_window = MagicMock()
    app.tray_icon = SimpleNamespace(show_main_window=MagicMock())
    alerts = [_AlertStub("alpha"), _AlertStub("beta")]

    with patch("accessiweather.app.show_alerts_summary_dialog"):
        app._show_immediate_alert_popup(alerts)

    app.tray_icon.show_main_window.assert_not_called()
    app.main_window.Show.assert_not_called()
    app.main_window.Iconize.assert_not_called()
    app.main_window.Raise.assert_not_called()


@pytest.mark.parametrize(
    ("main_window", "alerts"),
    [
        (None, [_AlertStub("alpha")]),
        (MagicMock(), []),
    ],
)
def test_show_immediate_alert_popup_ignores_missing_window_or_empty_alerts(
    main_window,
    alerts,
) -> None:
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.main_window = main_window

    with (
        patch("accessiweather.app.show_alert_dialog") as mock_show_alert_dialog,
        patch("accessiweather.app.show_alerts_summary_dialog") as mock_show_summary_dialog,
    ):
        app._show_immediate_alert_popup(alerts)

    mock_show_alert_dialog.assert_not_called()
    mock_show_summary_dialog.assert_not_called()
