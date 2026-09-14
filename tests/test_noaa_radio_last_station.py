"""Tests for remembering the last NOAA Weather Radio station that played."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from accessiweather.noaa_radio.preferences import RadioPreferences
from accessiweather.noaa_radio.stations import Station

WXK27 = Station("WXK27", 162.4, "Austin", 30.2672, -97.7431, "TX")


class TestPreferencesLastStation:
    def test_defaults_to_none(self, tmp_path: Path) -> None:
        prefs = RadioPreferences(path=tmp_path / "noaa_radio_prefs.json")

        assert prefs.get_last_station() is None

    def test_persists_across_instances(self, tmp_path: Path) -> None:
        path = tmp_path / "noaa_radio_prefs.json"
        RadioPreferences(path=path).set_last_station("wxk27")

        assert RadioPreferences(path=path).get_last_station() == "WXK27"

    def test_survives_alongside_existing_preferences(self, tmp_path: Path) -> None:
        path = tmp_path / "noaa_radio_prefs.json"
        prefs = RadioPreferences(path=path)
        prefs.set_preferred_url("WXK27", "http://a")
        prefs.add_favorite_station("WXL58")
        prefs.set_last_station("WXK27")

        reloaded = RadioPreferences(path=path)

        assert reloaded.get_last_station() == "WXK27"
        assert reloaded.get_preferred_url("WXK27") == "http://a"
        assert reloaded.get_favorite_stations() == ["WXL58"]
        assert json.loads(path.read_text(encoding="utf-8"))["last_station"] == "WXK27"

    def test_blank_value_clears_the_saved_station(self, tmp_path: Path) -> None:
        path = tmp_path / "noaa_radio_prefs.json"
        prefs = RadioPreferences(path=path)
        prefs.set_last_station("WXK27")

        prefs.set_last_station("  ")

        assert prefs.get_last_station() is None
        assert RadioPreferences(path=path).get_last_station() is None

    def test_ignores_non_string_values_on_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "noaa_radio_prefs.json"
        path.write_text(json.dumps({"preferred_streams": {}, "last_station": 42}), encoding="utf-8")

        assert RadioPreferences(path=path).get_last_station() is None


class TestSessionRecordsLastStation:
    def _session(self, preferences=None):
        callbacks: dict = {}

        def make_player(**kwargs):
            callbacks.update(kwargs)
            return MagicMock()

        with patch("accessiweather.noaa_radio.session.RadioPlayer", side_effect=make_player):
            from accessiweather.noaa_radio.session import RadioSession

            session = RadioSession(preferences=preferences)
        return session, callbacks

    def test_records_station_when_playback_starts(self) -> None:
        preferences = MagicMock()
        session, callbacks = self._session(preferences)
        session.playing_station = WXK27

        callbacks["on_playing"]()

        preferences.set_last_station.assert_called_once_with("WXK27")

    def test_records_nothing_without_a_station(self) -> None:
        preferences = MagicMock()
        session, callbacks = self._session(preferences)

        callbacks["on_playing"]()

        preferences.set_last_station.assert_not_called()

    def test_playback_continues_when_saving_fails(self) -> None:
        preferences = MagicMock()
        preferences.set_last_station.side_effect = OSError("read-only")
        session, callbacks = self._session(preferences)
        session.playing_station = WXK27
        on_playing = MagicMock()
        session.bind_callbacks(
            on_playing=on_playing,
            on_stopped=MagicMock(),
            on_error=MagicMock(),
            on_stalled=MagicMock(),
            on_reconnecting=MagicMock(),
        )

        callbacks["on_playing"]()

        on_playing.assert_called_once_with()

    def test_works_without_preferences_attached(self) -> None:
        session, callbacks = self._session(None)
        session.playing_station = WXK27

        callbacks["on_playing"]()

        assert session.playing_station is WXK27
