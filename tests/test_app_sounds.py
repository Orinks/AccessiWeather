"""Tests for application-level sound helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from accessiweather.app import AccessiWeatherApp


def test_startup_sound_defaults_to_no_muted_events_when_setting_missing():
    """Legacy settings without muted_sound_events should not mute startup sounds."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.config_manager = MagicMock()
    app.config_manager.get_settings.return_value = SimpleNamespace(
        sound_enabled=True,
        sound_pack="default",
    )

    with patch("accessiweather.notifications.sound_player.play_startup_sound") as mock_play:
        app._play_startup_sound()

    mock_play.assert_called_once_with("default", muted_events=[])
