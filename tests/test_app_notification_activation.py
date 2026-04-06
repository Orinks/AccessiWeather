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


def test_handle_activation_restores_via_main_window_when_no_tray() -> None:
    """When tray_icon is None, fall back to Show/Iconize/force_foreground on main_window."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.tray_icon = None
    mw = MagicMock()
    app.main_window = mw
    app.current_weather_data = None

    request = NotificationActivationRequest(kind="discussion")
    with patch.object(app, "_force_foreground_window") as mock_force:
        app._handle_notification_activation_request(request)

    mw.Show.assert_called_once_with(True)
    mw.Iconize.assert_called_once_with(False)
    mock_force.assert_called_once_with(mw)
    mw._on_discussion.assert_called_once()


def test_handle_activation_returns_early_when_no_main_window() -> None:
    """When main_window is None, should return without error."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.tray_icon = SimpleNamespace(show_main_window=MagicMock())
    app.main_window = None
    app.current_weather_data = None

    request = NotificationActivationRequest(kind="discussion")
    # Should not raise
    app._handle_notification_activation_request(request)
    app.tray_icon.show_main_window.assert_called_once()


def test_handle_activation_generic_fallback_only_restores() -> None:
    """generic_fallback should restore but not route to any dialog."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.tray_icon = SimpleNamespace(show_main_window=MagicMock())
    app.main_window = _MainWindowStub()
    app.current_weather_data = None

    request = NotificationActivationRequest(kind="generic_fallback")
    app._handle_notification_activation_request(request)

    app.tray_icon.show_main_window.assert_called_once()
    app.main_window._on_discussion.assert_not_called()
    app.main_window._show_alert_details.assert_not_called()


def test_handle_activation_alert_not_found() -> None:
    """When alert_id doesn't match any active alert, _show_alert_details is not called."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.tray_icon = SimpleNamespace(show_main_window=MagicMock())
    app.main_window = _MainWindowStub()
    app.current_weather_data = SimpleNamespace(alerts=_AlertsStub([_AlertStub("alpha")]))

    request = NotificationActivationRequest(kind="alert_details", alert_id="nonexistent")
    app._handle_notification_activation_request(request)

    app.main_window._show_alert_details.assert_not_called()


def test_find_active_alert_index_no_weather_data() -> None:
    """_find_active_alert_index returns None when current_weather_data is missing."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.current_weather_data = None

    assert app._find_active_alert_index("any-id") is None


def test_find_active_alert_index_no_alerts_attr() -> None:
    """_find_active_alert_index returns None when weather data has no alerts."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.current_weather_data = SimpleNamespace()

    assert app._find_active_alert_index("any-id") is None


def test_on_activation_handoff_timer_consumes_request() -> None:
    """Timer callback should consume handoff and route."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.tray_icon = SimpleNamespace(show_main_window=MagicMock())
    app.main_window = _MainWindowStub()
    app.current_weather_data = None

    request = NotificationActivationRequest(kind="discussion")
    app.single_instance_manager = MagicMock()
    app.single_instance_manager.consume_activation_handoff.return_value = request

    app._on_activation_handoff_timer(None)

    app.single_instance_manager.consume_activation_handoff.assert_called_once()
    app.main_window._on_discussion.assert_called_once()


def test_on_activation_handoff_timer_noop_when_no_request() -> None:
    """Timer callback does nothing when no handoff file exists."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.main_window = _MainWindowStub()
    app.single_instance_manager = MagicMock()
    app.single_instance_manager.consume_activation_handoff.return_value = None

    app._on_activation_handoff_timer(None)
    app.main_window._on_discussion.assert_not_called()


def test_on_activation_handoff_timer_noop_when_no_single_instance_manager() -> None:
    """Timer callback does nothing when single_instance_manager is None."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.single_instance_manager = None
    # Should not raise
    app._on_activation_handoff_timer(None)


def test_schedule_startup_activation_request_calls_handler() -> None:
    """_schedule_startup_activation_request invokes wx.CallAfter."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    request = NotificationActivationRequest(kind="discussion")
    app._activation_request = request

    with patch("accessiweather.app.wx") as mock_wx:
        app._schedule_startup_activation_request()
        mock_wx.CallAfter.assert_called_once_with(
            app._handle_notification_activation_request, request
        )


def test_schedule_startup_activation_request_noop_when_none() -> None:
    """_schedule_startup_activation_request does nothing with no request."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._activation_request = None

    with patch("accessiweather.app.wx") as mock_wx:
        app._schedule_startup_activation_request()
        mock_wx.CallAfter.assert_not_called()


def test_notifier_on_activation_wired_to_handle_request() -> None:
    """App wires notifier.on_activation to route activation requests on UI thread."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.tray_icon = SimpleNamespace(show_main_window=MagicMock())
    app.main_window = _MainWindowStub()
    app.current_weather_data = None

    # Create a mock notifier with on_activation attribute
    mock_notifier = MagicMock()
    mock_notifier.on_activation = None
    app._notifier = mock_notifier

    app._wire_notifier_activation_callback()

    assert mock_notifier.on_activation is not None


def test_handle_activation_uses_force_foreground_on_windows() -> None:
    """On Windows, activation should call _force_foreground_window."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.tray_icon = None
    mw = MagicMock()
    app.main_window = mw
    app.current_weather_data = None

    with patch.object(app, "_force_foreground_window") as mock_force:
        request = NotificationActivationRequest(kind="generic_fallback")
        app._handle_notification_activation_request(request)
        mock_force.assert_called_once_with(mw)
