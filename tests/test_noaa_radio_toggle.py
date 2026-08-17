"""Tests for the focus-free NOAA Weather Radio play/stop toggle."""

from unittest.mock import MagicMock

from accessiweather.noaa_radio.stations import Station
from accessiweather.noaa_radio.toggle import RadioToggleController

WXK27 = Station("WXK27", 162.4, "Austin", 30.2672, -97.7431, "TX")
WXL58 = Station("WXL58", 162.55, "Dallas", 32.7767, -96.797, "TX")


class _InlineThread:
    """Runs the worker body synchronously so toggle tests stay deterministic."""

    def __init__(self, target) -> None:
        self._target = target

    def start(self) -> None:
        self._target()


def _make_controller(
    *,
    playing: bool = False,
    last_station: str | None = "WXK27",
    favorites: list[str] | None = None,
    stations: list[Station] | None = None,
    urls: list[str] | None = None,
    play_results: list[bool] | None = None,
    auto_tuner: MagicMock | None = None,
):
    session = MagicMock()
    session.is_playing.return_value = playing
    session.playing_station = WXK27 if playing else None
    session.player.play.side_effect = play_results if play_results is not None else [True]

    preferences = MagicMock()
    preferences.get_last_station.return_value = last_station
    preferences.get_favorite_stations.return_value = list(favorites or [])
    preferences.reorder_urls.side_effect = lambda _call_sign, values: list(values)

    station_database = MagicMock()
    station_database.get_stations_by_call_signs.return_value = (
        [WXK27] if stations is None else stations
    )

    url_provider = MagicMock()
    url_provider.get_stream_urls.return_value = ["http://a", "http://b"] if urls is None else urls

    notify = MagicMock()
    controller = RadioToggleController(
        session=session,
        preferences=preferences,
        station_database=station_database,
        url_provider=url_provider,
        notify=notify,
        auto_tuner_provider=lambda: auto_tuner,
        thread_factory=_InlineThread,
    )
    return controller, session, preferences, station_database, url_provider, notify


class TestToggleWhilePlaying:
    def test_stops_playback_and_announces(self) -> None:
        controller, session, _prefs, _db, url_provider, notify = _make_controller(playing=True)

        controller.toggle()

        session.stop.assert_called_once_with()
        url_provider.get_stream_urls.assert_not_called()
        assert "stopped" in notify.call_args[0][0].lower()

    def test_cancels_pending_alert_auto_tune(self) -> None:
        auto_tuner = MagicMock()
        controller, session, *_ = _make_controller(playing=True, auto_tuner=auto_tuner)

        controller.toggle()

        auto_tuner.stop.assert_called_once_with()
        session.stop.assert_called_once_with()

    def test_stops_even_when_no_auto_tuner_exists(self) -> None:
        controller, session, *_ = _make_controller(playing=True, auto_tuner=None)

        controller.toggle()

        session.stop.assert_called_once_with()

    def test_stops_even_when_auto_tuner_raises(self) -> None:
        auto_tuner = MagicMock()
        auto_tuner.stop.side_effect = RuntimeError("boom")
        controller, session, *_ = _make_controller(playing=True, auto_tuner=auto_tuner)

        controller.toggle()

        session.stop.assert_called_once_with()


class TestToggleWhileStopped:
    def test_plays_last_station(self) -> None:
        controller, session, _prefs, station_database, url_provider, notify = _make_controller()

        controller.toggle()

        station_database.get_stations_by_call_signs.assert_called_once_with(["WXK27"])
        url_provider.get_stream_urls.assert_called_once_with("WXK27")
        session.player.play.assert_called_once_with("http://a")
        assert session.playing_station is WXK27
        assert session.current_urls == ["http://a", "http://b"]
        assert session.current_url_index == 0
        # The station name already carries the state, so it must not be repeated.
        assert notify.call_args[0][0] == "Playing WXK27, Austin."

    def test_falls_back_to_first_favorite_without_history(self) -> None:
        controller, _session, _prefs, station_database, url_provider, _notify = _make_controller(
            last_station=None,
            favorites=["WXL58", "WXK27"],
            stations=[WXL58],
        )

        controller.toggle()

        station_database.get_stations_by_call_signs.assert_called_once_with(["WXL58"])
        url_provider.get_stream_urls.assert_called_once_with("WXL58")

    def test_announces_when_no_station_is_known(self) -> None:
        controller, session, _prefs, _db, url_provider, notify = _make_controller(
            last_station=None, favorites=[]
        )

        controller.toggle()

        url_provider.get_stream_urls.assert_not_called()
        session.player.play.assert_not_called()
        assert "no station" in notify.call_args[0][0].lower()

    def test_announces_when_saved_station_is_unknown(self) -> None:
        controller, session, *_rest, notify = _make_controller(stations=[])

        controller.toggle()

        session.player.play.assert_not_called()
        assert "WXK27" in notify.call_args[0][0]

    def test_announces_when_no_streams_are_available(self) -> None:
        controller, session, *_rest, notify = _make_controller(urls=[])

        controller.toggle()

        session.player.play.assert_not_called()
        assert session.playing_station is None
        assert "WXK27" in notify.call_args[0][0]

    def test_falls_through_to_next_url_when_first_stream_fails(self) -> None:
        controller, session, *_rest, notify = _make_controller(play_results=[False, True])

        controller.toggle()

        assert [call.args[0] for call in session.player.play.call_args_list] == [
            "http://a",
            "http://b",
        ]
        assert session.current_url_index == 1
        assert "WXK27" in notify.call_args[0][0]

    def test_clears_station_when_every_stream_fails(self) -> None:
        controller, session, *_rest, notify = _make_controller(play_results=[False, False])

        controller.toggle()

        assert session.playing_station is None
        assert "could not" in notify.call_args[0][0].lower()

    def test_honors_preferred_stream_ordering(self) -> None:
        controller, session, preferences, *_rest = _make_controller()
        preferences.reorder_urls.side_effect = lambda _call_sign, values: list(reversed(values))

        controller.toggle()

        session.player.play.assert_called_once_with("http://b")

    def test_reports_lookup_failures_instead_of_raising(self) -> None:
        controller, session, _prefs, _db, url_provider, notify = _make_controller()
        url_provider.get_stream_urls.side_effect = RuntimeError("network down")

        controller.toggle()

        session.player.play.assert_not_called()
        assert notify.called

    def test_runs_playback_off_the_ui_thread(self) -> None:
        controller = RadioToggleController(
            session=MagicMock(is_playing=MagicMock(return_value=False)),
            preferences=MagicMock(),
            station_database=MagicMock(),
            url_provider=MagicMock(),
            notify=MagicMock(),
        )

        thread = controller._make_thread(lambda: None)

        assert thread.daemon is True
