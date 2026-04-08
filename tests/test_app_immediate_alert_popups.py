from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from accessiweather.app import AccessiWeatherApp


class _AlertStub:
    def __init__(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def get_unique_id(self) -> str:
        return self._unique_id


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
