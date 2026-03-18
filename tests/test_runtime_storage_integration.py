from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from accessiweather.app_initialization import initialize_components
from accessiweather.paths import RuntimeStoragePaths


def test_initialize_components_uses_runtime_cache_dir(tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    settings = SimpleNamespace(
        data_source="auto",
        visual_crossing_api_key="",
        avwx_api_key="",
        to_alert_settings=lambda: object(),
        sound_enabled=True,
        sound_pack="default",
        muted_sound_events=["data_updated"],
        ai_cache_ttl=300,
        weather_history_enabled=False,
    )
    config = SimpleNamespace(settings=settings)
    config_manager = MagicMock()
    config_manager.config_dir = runtime_paths.config_root
    config_manager.load_config.return_value = config
    config_manager.get_config.return_value = config

    app = SimpleNamespace(
        runtime_paths=runtime_paths,
        _config_dir=None,
        _portable_mode=False,
        debug_mode=False,
    )

    with (
        patch("accessiweather.app_initialization.ConfigManager", return_value=config_manager),
        patch("accessiweather.app_initialization.wx.CallLater", create=True),
        patch("accessiweather.cache.WeatherDataCache") as mock_weather_cache,
        patch("accessiweather.weather_client.WeatherClient"),
        patch("accessiweather.location_manager.LocationManager"),
        patch("accessiweather.display.WeatherPresenter"),
        patch("accessiweather.notifications.toast_notifier.SafeDesktopNotifier"),
        patch("accessiweather.cache.Cache"),
        patch("accessiweather.alert_manager.AlertManager"),
        patch("accessiweather.alert_notification_system.AlertNotificationSystem"),
    ):
        initialize_components(app)

    mock_weather_cache.assert_called_once_with(runtime_paths.cache_dir)
