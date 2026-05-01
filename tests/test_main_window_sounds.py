"""
Tests for main window sound playback on refresh success and fetch_error events.

Covers lines in _on_weather_data_received and _on_weather_error that call
play_data_updated_sound and play_fetch_error_sound when sound_enabled=True,
and verifies silence when sound_enabled=False.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestMainWindowRefreshSuccessSound:
    """Tests for weather-updated sound playback in _on_weather_data_received."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock app with sound enabled."""
        from accessiweather.models.config import AppSettings

        app = MagicMock()
        settings = AppSettings(sound_enabled=True, sound_pack="default", muted_sound_events=[])
        app.config_manager.get_settings.return_value = settings
        app.config_manager.get_current_location.return_value = MagicMock(name="Test Location")
        app.is_updating = True
        app.alert_notification_system = None
        return app

    @pytest.fixture
    def mock_app_sound_disabled(self):
        """Create a mock app with sound disabled."""
        from accessiweather.models.config import AppSettings

        app = MagicMock()
        settings = AppSettings(sound_enabled=False, sound_pack="default", muted_sound_events=[])
        app.config_manager.get_settings.return_value = settings
        app.config_manager.get_current_location.return_value = MagicMock(name="Test Location")
        app.is_updating = True
        app.alert_notification_system = None
        return app

    def _make_window(self, app):
        """Create a MainWindow instance with __init__ bypassed."""
        from accessiweather.ui.main_window import MainWindow

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)

        win.app = app
        win.set_status = MagicMock()
        win.refresh_button = MagicMock()
        win.current_conditions = MagicMock()
        win.stale_warning_label = MagicMock()
        win.daily_forecast_display = MagicMock()
        win.hourly_forecast_display = MagicMock()
        win.forecast_display = win.daily_forecast_display
        win._set_forecast_sections = MagicMock()
        win._update_alerts = MagicMock()
        win._process_notification_events = MagicMock()
        win._set_last_updated_status = MagicMock()
        win._alert_lifecycle_labels = {}
        # Stub presenter so the method doesn't blow up on presentation logic
        presentation = MagicMock()
        presentation.current_conditions = MagicMock()
        presentation.current_conditions.fallback_text = "70°F"
        presentation.source_attribution = None
        presentation.forecast = None
        presentation.status_messages = []
        app.presenter.present.return_value = presentation
        return win

    def test_weather_updated_sound_called_when_sound_enabled(self, mock_app):
        """play_data_updated_sound is called when sound_enabled=True."""
        win = self._make_window(mock_app)
        weather_data = MagicMock()
        weather_data.alert_lifecycle_diff = None

        with patch(
            "accessiweather.notifications.sound_player.play_data_updated_sound"
        ) as mock_play:
            win._on_weather_data_received(weather_data)

        mock_play.assert_called_once_with("default", muted_events=[])

    def test_weather_updated_sound_not_called_when_sound_disabled(self, mock_app_sound_disabled):
        """play_data_updated_sound is NOT called when sound_enabled=False."""
        win = self._make_window(mock_app_sound_disabled)
        weather_data = MagicMock()
        weather_data.alert_lifecycle_diff = None

        with patch(
            "accessiweather.notifications.sound_player.play_data_updated_sound"
        ) as mock_play:
            win._on_weather_data_received(weather_data)

        mock_play.assert_not_called()

    def test_weather_updated_sound_called_with_muted_events(self, mock_app):
        """play_data_updated_sound receives muted event overrides."""
        mock_app.config_manager.get_settings.return_value.muted_sound_events = ["data_updated"]
        win = self._make_window(mock_app)
        weather_data = MagicMock()
        weather_data.alert_lifecycle_diff = None

        with patch(
            "accessiweather.notifications.sound_player.play_data_updated_sound"
        ) as mock_play:
            win._on_weather_data_received(weather_data)

        mock_play.assert_called_once_with("default", muted_events=["data_updated"])


class TestMainWindowFetchErrorSound:
    """Tests for fetch_error sound playback in _on_weather_error."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock app with sound enabled."""
        from accessiweather.models.config import AppSettings

        app = MagicMock()
        settings = AppSettings(sound_enabled=True, sound_pack="default", muted_sound_events=[])
        app.config_manager.get_settings.return_value = settings
        app.is_updating = True
        return app

    @pytest.fixture
    def mock_app_sound_disabled(self):
        """Create a mock app with sound disabled."""
        from accessiweather.models.config import AppSettings

        app = MagicMock()
        settings = AppSettings(sound_enabled=False, sound_pack="default", muted_sound_events=[])
        app.config_manager.get_settings.return_value = settings
        app.is_updating = True
        return app

    def _make_window(self, app):
        """Create a MainWindow instance with __init__ bypassed."""
        from accessiweather.ui.main_window import MainWindow

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)

        win.app = app
        win.set_status = MagicMock()
        win.refresh_button = MagicMock()
        return win

    def test_fetch_error_sound_called_when_sound_enabled(self, mock_app):
        """play_fetch_error_sound is called when sound_enabled=True."""
        win = self._make_window(mock_app)

        with patch("accessiweather.notifications.sound_player.play_fetch_error_sound") as mock_play:
            win._on_weather_error("Connection timed out")

        mock_play.assert_called_once_with("default", muted_events=[])

    def test_fetch_error_sound_not_called_when_sound_disabled(self, mock_app_sound_disabled):
        """play_fetch_error_sound is NOT called when sound_enabled=False."""
        win = self._make_window(mock_app_sound_disabled)

        with patch("accessiweather.notifications.sound_player.play_fetch_error_sound") as mock_play:
            win._on_weather_error("Connection timed out")

        mock_play.assert_not_called()

    def test_fetch_error_sound_called_with_muted_events(self, mock_app):
        """play_fetch_error_sound receives muted event overrides."""
        mock_app.config_manager.get_settings.return_value.muted_sound_events = ["data_updated"]
        win = self._make_window(mock_app)

        with patch("accessiweather.notifications.sound_player.play_fetch_error_sound") as mock_play:
            win._on_weather_error("Connection timed out")

        mock_play.assert_called_once_with("default", muted_events=["data_updated"])

    def test_weather_updated_sound_exception_is_swallowed(self, mock_app):
        """Exceptions from play_data_updated_sound must not propagate."""
        from accessiweather.ui.main_window import MainWindow

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
        win.app = mock_app
        win.set_status = MagicMock()
        win.refresh_button = MagicMock()
        win.current_conditions = MagicMock()
        win.stale_warning_label = MagicMock()
        win.daily_forecast_display = MagicMock()
        win.hourly_forecast_display = MagicMock()
        win.forecast_display = win.daily_forecast_display
        win._set_forecast_sections = MagicMock()
        win._update_alerts = MagicMock()
        win._process_notification_events = MagicMock()
        win._set_last_updated_status = MagicMock()
        win._alert_lifecycle_labels = {}
        presentation = MagicMock()
        presentation.current_conditions = MagicMock()
        presentation.current_conditions.fallback_text = "70°F"
        presentation.source_attribution = None
        presentation.forecast = None
        presentation.status_messages = []
        mock_app.presenter.present.return_value = presentation

        with patch(
            "accessiweather.notifications.sound_player.play_data_updated_sound",
            side_effect=Exception("sound failure"),
        ):
            win._on_weather_data_received(MagicMock())  # must not raise


class TestMainWindowFetchErrorSoundExceptions(TestMainWindowFetchErrorSound):
    """Exception-swallowing tests for fetch_error sound."""

    def test_fetch_error_sound_exception_is_swallowed(self, mock_app):
        """Exceptions from play_fetch_error_sound must not propagate."""
        from accessiweather.ui.main_window import MainWindow

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
        win.app = mock_app
        win.set_status = MagicMock()
        win.refresh_button = MagicMock()
        win.app.is_updating = True

        with patch(
            "accessiweather.notifications.sound_player.play_fetch_error_sound",
            side_effect=Exception("sound failure"),
        ):
            win._on_weather_error("network error")  # must not raise
