"""Tests for NOAA Weather Radio modules."""

from unittest.mock import MagicMock, patch

from accessiweather.noaa_radio import Station, StationDatabase, StreamURLProvider
from accessiweather.noaa_radio.player import RadioPlayer
from accessiweather.noaa_radio.preferences import RadioPreferences

# ---------------------------------------------------------------------------
# Station / StationDatabase tests
# ---------------------------------------------------------------------------


class TestStation:
    def test_station_fields(self):
        s = Station("KEC49", 162.550, "Test City", 40.0, -74.0, "NY")
        assert s.call_sign == "KEC49"
        assert s.frequency == 162.550
        assert s.name == "Test City"
        assert s.state == "NY"


class TestStationDatabase:
    def test_find_nearest_returns_sorted(self):
        stations = [
            Station("A", 162.4, "Far", 50.0, -100.0, "XX"),
            Station("B", 162.4, "Near", 40.1, -74.1, "NY"),
            Station("C", 162.4, "Mid", 42.0, -80.0, "PA"),
        ]
        db = StationDatabase(stations)
        results = db.find_nearest(40.0, -74.0, limit=3)
        assert results[0].station.call_sign == "B"
        assert results[0].distance_km < results[1].distance_km

    def test_find_nearest_limit(self):
        db = StationDatabase()
        results = db.find_nearest(40.0, -74.0, limit=3)
        assert len(results) == 3

    def test_get_stations_by_state(self):
        stations = [
            Station("A", 162.4, "NYC", 40.0, -74.0, "NY"),
            Station("B", 162.4, "LA", 34.0, -118.0, "CA"),
        ]
        db = StationDatabase(stations)
        ny = db.get_stations_by_state("ny")
        assert len(ny) == 1
        assert ny[0].call_sign == "A"

    def test_get_all_stations(self):
        stations = [Station("A", 162.4, "Test", 40.0, -74.0, "NY")]
        db = StationDatabase(stations)
        assert len(db.get_all_stations()) == 1

    def test_default_stations_not_empty(self):
        db = StationDatabase()
        assert len(db.get_all_stations()) > 0

    def test_empty_state_returns_empty(self):
        db = StationDatabase()
        assert db.get_stations_by_state("ZZ") == []


# ---------------------------------------------------------------------------
# StreamURLProvider tests
# ---------------------------------------------------------------------------


class TestStreamURLProvider:
    def test_get_stream_url_known(self):
        provider = StreamURLProvider(custom_urls={"TEST1": ["http://example.com/stream"]})
        assert provider.get_stream_url("TEST1") == "http://example.com/stream"

    def test_get_stream_url_fallback(self):
        provider = StreamURLProvider(use_fallback=True)
        url = provider.get_stream_url("UNKNOWN1")
        assert url is not None
        assert "UNKNOWN1" in url

    def test_get_stream_url_no_fallback(self):
        provider = StreamURLProvider(use_fallback=False)
        assert provider.get_stream_url("UNKNOWN1") is None

    def test_get_stream_urls_multiple(self):
        provider = StreamURLProvider(custom_urls={"TEST1": ["http://a.com", "http://b.com"]})
        urls = provider.get_stream_urls("TEST1")
        assert len(urls) == 2

    def test_has_known_url(self):
        provider = StreamURLProvider(custom_urls={"TEST1": ["http://a.com"]})
        assert provider.has_known_url("TEST1") is True
        assert provider.has_known_url("NOPE") is False

    def test_case_insensitive(self):
        provider = StreamURLProvider(custom_urls={"TEST1": ["http://a.com"]})
        assert provider.get_stream_url("test1") == "http://a.com"

    def test_empty_call_sign(self):
        provider = StreamURLProvider()
        assert provider.get_stream_urls("") == []
        assert provider.get_stream_urls("  ") == []


# ---------------------------------------------------------------------------
# RadioPlayer tests
# ---------------------------------------------------------------------------


class TestRadioPlayer:
    def test_play_without_sound_lib(self):
        on_error = MagicMock()
        player = RadioPlayer(on_error=on_error)
        with patch("accessiweather.noaa_radio.player._ensure_sound_lib", return_value=False):
            result = player.play("http://example.com/stream")
        assert result is False
        on_error.assert_called_once()

    def test_initial_volume(self):
        player = RadioPlayer()
        assert player.get_volume() == 1.0

    def test_set_volume_clamps(self):
        player = RadioPlayer()
        player.set_volume(1.5)
        assert player.get_volume() == 1.0
        player.set_volume(-0.5)
        assert player.get_volume() == 0.0

    def test_is_playing_no_stream(self):
        player = RadioPlayer()
        assert player.is_playing() is False

    def test_is_stalled_no_stream(self):
        player = RadioPlayer()
        assert player.is_stalled() is False

    def test_stop_when_not_playing(self):
        on_stopped = MagicMock()
        player = RadioPlayer(on_stopped=on_stopped)
        player.stop()  # Should not crash or call on_stopped
        on_stopped.assert_not_called()

    def test_retry_without_url(self):
        player = RadioPlayer()
        assert player.retry() is False

    def test_retry_exhaustion(self):
        on_error = MagicMock()
        player = RadioPlayer(on_error=on_error)
        player._current_url = "http://example.com/stream"
        player._retry_count = RadioPlayer.MAX_RETRIES
        result = player.retry()
        assert result is False
        on_error.assert_called_once()
        assert "multiple attempts" in on_error.call_args[0][0]

    def test_check_health_no_stream(self):
        player = RadioPlayer()
        player.check_health()  # Should not crash


# ---------------------------------------------------------------------------
# RadioPreferences tests
# ---------------------------------------------------------------------------


class TestRadioPreferences:
    def test_no_preferred_by_default(self, tmp_path):
        prefs = RadioPreferences(config_dir=tmp_path)
        assert prefs.get_preferred_url("TEST1") is None

    def test_set_and_get_preferred(self, tmp_path):
        prefs = RadioPreferences(config_dir=tmp_path)
        prefs.set_preferred_url("TEST1", "http://stream2.com")
        assert prefs.get_preferred_url("TEST1") == "http://stream2.com"

    def test_persistence(self, tmp_path):
        prefs1 = RadioPreferences(config_dir=tmp_path)
        prefs1.set_preferred_url("TEST1", "http://stream2.com")
        prefs2 = RadioPreferences(config_dir=tmp_path)
        assert prefs2.get_preferred_url("TEST1") == "http://stream2.com"

    def test_clear_preferred(self, tmp_path):
        prefs = RadioPreferences(config_dir=tmp_path)
        prefs.set_preferred_url("TEST1", "http://stream2.com")
        prefs.clear_preferred_url("TEST1")
        assert prefs.get_preferred_url("TEST1") is None

    def test_reorder_urls_with_preferred(self, tmp_path):
        prefs = RadioPreferences(config_dir=tmp_path)
        prefs.set_preferred_url("TEST1", "http://b.com")
        urls = ["http://a.com", "http://b.com", "http://c.com"]
        reordered = prefs.reorder_urls("TEST1", urls)
        assert reordered[0] == "http://b.com"
        assert len(reordered) == 3

    def test_reorder_urls_no_preferred(self, tmp_path):
        prefs = RadioPreferences(config_dir=tmp_path)
        urls = ["http://a.com", "http://b.com"]
        reordered = prefs.reorder_urls("TEST1", urls)
        assert reordered == urls

    def test_reorder_urls_preferred_not_in_list(self, tmp_path):
        prefs = RadioPreferences(config_dir=tmp_path)
        prefs.set_preferred_url("TEST1", "http://gone.com")
        urls = ["http://a.com", "http://b.com"]
        reordered = prefs.reorder_urls("TEST1", urls)
        assert reordered == urls

    def test_case_insensitive(self, tmp_path):
        prefs = RadioPreferences(config_dir=tmp_path)
        prefs.set_preferred_url("test1", "http://stream.com")
        assert prefs.get_preferred_url("TEST1") == "http://stream.com"
