"""Tests for shared NOAA Weather Radio playback session."""

from unittest.mock import MagicMock, patch

from accessiweather.noaa_radio import Station


def test_session_unbinds_callbacks_without_stopping_player() -> None:
    with patch("accessiweather.noaa_radio.session.RadioPlayer") as player_cls:
        from accessiweather.noaa_radio.session import RadioSession

        session = RadioSession()
        session.bind_callbacks(
            on_playing=MagicMock(),
            on_stopped=MagicMock(),
            on_error=MagicMock(),
            on_stalled=MagicMock(),
            on_reconnecting=MagicMock(),
        )

        session.unbind_callbacks()

    player_cls.return_value.stop.assert_not_called()


def test_session_stop_clears_station_when_player_reports_stopped() -> None:
    callbacks = {}

    def make_player(**kwargs):
        callbacks.update(kwargs)
        player = MagicMock()
        player.is_playing.return_value = True
        return player

    with patch("accessiweather.noaa_radio.session.RadioPlayer", side_effect=make_player):
        from accessiweather.noaa_radio.session import RadioSession

        session = RadioSession()
        session.playing_station = Station("WXK27", 162.4, "Austin", 30.2672, -97.7431, "TX")

        callbacks["on_stopped"]()

    assert session.playing_station is None
