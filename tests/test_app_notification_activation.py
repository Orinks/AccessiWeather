from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from accessiweather.app import AccessiWeatherApp
from accessiweather.notification_activation import NotificationActivationRequest
from accessiweather.paths import RuntimeStoragePaths


class _MainWindowStub:
    def __init__(self) -> None:
        self._on_discussion = MagicMock()
        self._show_alert_details = MagicMock()


class _AlertStub:
    def __init__(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def get_unique_id(self) -> str:
        return self._unique_id


class _AlertsStub:
    def __init__(self, alerts) -> None:
        self._alerts = list(alerts)

    def get_active_alerts(self):
        return list(self._alerts)


class _SingleInstanceManagerStub:
    def __init__(self, _app, runtime_paths=None):
        self.runtime_paths = runtime_paths
        self.try_acquire_lock = MagicMock(return_value=False)
        self.write_activation_handoff = MagicMock(return_value=True)


def test_handle_notification_activation_restores_and_routes_discussion() -> None:
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.tray_icon = SimpleNamespace(show_main_window=MagicMock())
    app.main_window = _MainWindowStub()
    app.current_weather_data = None

    request = NotificationActivationRequest(kind="discussion")

    app._handle_notification_activation_request(request)

    app.tray_icon.show_main_window.assert_called_once_with()
    app.main_window._on_discussion.assert_called_once_with()
    app.main_window._show_alert_details.assert_not_called()


def test_handle_notification_activation_restores_and_routes_alert_details() -> None:
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.tray_icon = SimpleNamespace(show_main_window=MagicMock())
    app.main_window = _MainWindowStub()
    app.current_weather_data = SimpleNamespace(
        alerts=_AlertsStub([_AlertStub("alpha"), _AlertStub("beta")])
    )

    request = NotificationActivationRequest(kind="alert_details", alert_id="beta")

    app._handle_notification_activation_request(request)

    app.tray_icon.show_main_window.assert_called_once_with()
    app.main_window._show_alert_details.assert_called_once_with(1)
    app.main_window._on_discussion.assert_not_called()


def test_on_init_forwards_activation_to_running_instance_and_exits(tmp_path) -> None:
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.runtime_paths = runtime_paths
    app._updated = False
    app._activation_request = NotificationActivationRequest(kind="discussion")
    show_force_start_dialog = MagicMock()

    with (
        patch("accessiweather.app.SingleInstanceManager", _SingleInstanceManagerStub),
        patch.object(app, "_show_force_start_dialog", show_force_start_dialog),
    ):
        started = app.OnInit()

    assert started is False
    assert app.single_instance_manager.write_activation_handoff.called is True
    show_force_start_dialog.assert_not_called()
