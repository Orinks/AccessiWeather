"""Tests for shared NOAA Weather Radio playback session."""

import importlib
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


def test_session_forwards_callbacks_and_player_state() -> None:
    callbacks = {}
    player = MagicMock()
    player.is_playing.return_value = True

    def make_player(**kwargs):
        callbacks.update(kwargs)
        return player

    with patch("accessiweather.noaa_radio.session.RadioPlayer", side_effect=make_player):
        from accessiweather.noaa_radio.session import RadioSession

        session = RadioSession()
        on_playing = MagicMock()
        on_stopped = MagicMock()
        on_error = MagicMock()
        on_stalled = MagicMock()
        on_reconnecting = MagicMock()
        session.bind_callbacks(
            on_playing=on_playing,
            on_stopped=on_stopped,
            on_error=on_error,
            on_stalled=on_stalled,
            on_reconnecting=on_reconnecting,
        )
        session.playing_station = Station("WXK27", 162.4, "Austin", 30.2672, -97.7431, "TX")

        assert session.is_playing() is True
        session.stop(notify=False)
        callbacks["on_playing"]()
        callbacks["on_stopped"]()
        callbacks["on_error"]("lost")
        callbacks["on_stalled"]()
        callbacks["on_reconnecting"](2)

    player.stop.assert_called_once_with(notify=False)
    assert session.playing_station is None
    on_playing.assert_called_once_with()
    on_stopped.assert_called_once_with()
    on_error.assert_called_once_with("lost")
    on_stalled.assert_called_once_with()
    on_reconnecting.assert_called_once_with(2)


def test_shared_session_helpers_create_and_stop_existing_session() -> None:
    import accessiweather.noaa_radio.session as session_module

    session_module = importlib.reload(session_module)
    fake_session = MagicMock()

    with patch.object(session_module, "RadioSession", return_value=fake_session):
        assert session_module.get_shared_radio_session() is fake_session
        assert session_module.get_shared_radio_session() is fake_session
        session_module.stop_shared_radio_session()

    fake_session.stop.assert_called_once_with()
