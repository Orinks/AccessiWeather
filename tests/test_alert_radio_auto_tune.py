"""Tests for alert-triggered NOAA Weather Radio auto-tuning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from accessiweather.models import AppSettings, Location, WeatherAlert
from accessiweather.noaa_radio.alert_auto_tune import (
    AlertRadioAutoTuner,
    NoReliableAlertStationResolver,
    WeatherIndexAlertStationResolver,
    county_zone_to_same_code,
    is_nwr_same_weather_event,
)
from accessiweather.noaa_radio.station_db import StationDatabase
from accessiweather.noaa_radio.stations import Station
from accessiweather.noaa_radio.weatherindex_client import (
    WeatherIndexServedCounty,
    WeatherIndexStationMetadata,
)


class _FakeThread:
    def __init__(self, target, started):
        self._target = target
        self._started = started

    def start(self):
        self._started.append(self._target)


class _FakePlayer:
    def __init__(self, session=None, results: list[bool] | None = None) -> None:
        self._session = session
        self._results = list(results) if results is not None else None
        self.played_urls = []

    def play(self, _url: str) -> bool:
        self.played_urls.append(_url)
        result = self._results.pop(0) if self._results else True
        if result and self._session is not None:
            self._session._playing = True
        return result


class _FakeSession:
    def __init__(self, *, playing: bool = False, station: Station | None = None) -> None:
        self.playing_station = station
        self.current_urls = []
        self.current_url_index = 0
        self.player = _FakePlayer(self)
        self._playing = playing
        self.stop = MagicMock(side_effect=self._stop)

    def is_playing(self) -> bool:
        return self._playing

    def _stop(self, *, notify: bool = True) -> None:
        del notify
        self._playing = False
        self.playing_station = None


class _FakePreferences:
    def reorder_urls(self, _call_sign: str, urls: list[str]) -> list[str]:
        return list(urls)


class _NoMatchResolver:
    def resolve_station(self, alerts, location):
        del alerts, location


class _RaisingResolver:
    def resolve_station(self, alerts, location):
        del alerts, location
        raise RuntimeError("metadata unavailable")


class _MappedResolver:
    def __init__(self, station: Station) -> None:
        self.station = station
        self.calls = []

    def resolve_station(self, alerts, location):
        self.calls.append((alerts, location))
        return self.station


class _FakeWeatherIndexClient:
    def __init__(self, metadata_by_call_sign: dict[str, WeatherIndexStationMetadata | None]):
        self.metadata_by_call_sign = metadata_by_call_sign
        self.calls = []

    def get_station_metadata(self, call_sign: str):
        normalized = call_sign.upper()
        self.calls.append(normalized)
        return self.metadata_by_call_sign.get(normalized)


def _alert() -> WeatherAlert:
    now = datetime.now(UTC)
    return WeatherAlert(
        id="alert-1",
        title="Tornado Warning",
        description="Take shelter now.",
        severity="Extreme",
        urgency="Immediate",
        certainty="Observed",
        event="Tornado Warning",
        expires=now + timedelta(hours=1),
        affected_zones=["TXC453"],
    )


def _forecast_zone_alert() -> WeatherAlert:
    alert = _alert()
    alert.affected_zones = ["TXZ192"]
    alert.same_codes = []
    return alert


def _air_quality_alert() -> WeatherAlert:
    alert = _alert()
    alert.title = "Air Quality Alert"
    alert.event = "Air Quality Alert"
    alert.severity = "Moderate"
    return alert


def _settings(**kwargs) -> AppSettings:
    return AppSettings(auto_tune_weather_radio_alerts=True, **kwargs)


def _location() -> Location:
    return Location(name="Austin", latitude=30.2672, longitude=-97.7431)


def _make_tuner(
    *,
    settings: AppSettings | None = None,
    session: _FakeSession | None = None,
    resolver=None,
    started: list | None = None,
):
    started = started if started is not None else []
    session = session or _FakeSession()
    station = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
    resolver = resolver or _MappedResolver(station)
    url_provider = MagicMock()
    url_provider.get_stream_urls.return_value = ["https://example.test/wxk27"]
    tuner = AlertRadioAutoTuner(
        settings_provider=lambda: settings or _settings(),
        location_provider=_location,
        preferences=_FakePreferences(),
        session=session,
        station_resolver=resolver,
        url_provider=url_provider,
        thread_factory=lambda target: _FakeThread(target, started),
    )
    return tuner, session, started, url_provider, resolver


def _metadata(call_sign: str, same_codes: list[str]) -> WeatherIndexStationMetadata:
    return WeatherIndexStationMetadata(
        call_sign=call_sign,
        wfo="Austin/San Antonio TX",
        latitude=30.3219,
        longitude=-97.8033,
        served_counties=tuple(
            WeatherIndexServedCounty(
                county=f"County {index}",
                same_code=same_code,
                state="TX",
                area="All",
            )
            for index, same_code in enumerate(same_codes)
        ),
    )


def test_auto_tune_disabled_does_not_schedule_worker():
    tuner, _session, started, _url_provider, _resolver = _make_tuner(
        settings=AppSettings(auto_tune_weather_radio_alerts=False)
    )

    tuner.tune_for_alerts([_alert()])

    assert started == []


def test_auto_tune_without_reliable_station_match_does_not_play_station():
    tuner, _session, started, _url_provider, _resolver = _make_tuner(resolver=_NoMatchResolver())

    tuner.tune_for_alerts([_alert()])
    assert len(started) == 1
    started[0]()

    _url_provider.get_stream_urls.assert_not_called()


def test_auto_tune_skips_non_nwr_same_event_without_worker():
    tuner, _session, started, _url_provider, resolver = _make_tuner()

    tuner.tune_for_alerts([_air_quality_alert()])

    assert started == []
    assert resolver.calls == []
    _url_provider.get_stream_urls.assert_not_called()


def test_auto_tune_filters_mixed_batch_to_nwr_same_events_only():
    tuner, _session, started, _url_provider, resolver = _make_tuner()

    tuner.tune_for_alerts([_air_quality_alert(), _alert()])
    assert len(started) == 1
    _url_provider.get_stream_urls.return_value = []
    started[0]()

    resolved_alerts = resolver.calls[0][0]
    assert [alert.event for alert in resolved_alerts] == ["Tornado Warning"]


def test_nwr_same_weather_event_eligibility_includes_operational_weather_events():
    assert is_nwr_same_weather_event(WeatherAlert("Tornado", "body", event="Tornado Warning"))
    assert is_nwr_same_weather_event(
        WeatherAlert("Special Weather", "body", event="Special Weather Statement")
    )
    assert is_nwr_same_weather_event(
        WeatherAlert("Snow Squall", "body", event="Snow Squall Warning")
    )


def test_nwr_same_weather_event_eligibility_excludes_advisory_only_events():
    assert not is_nwr_same_weather_event(
        WeatherAlert("Air Quality", "body", event="Air Quality Alert")
    )
    assert not is_nwr_same_weather_event(WeatherAlert("Heat", "body", event="Heat Advisory"))
    assert not is_nwr_same_weather_event(
        WeatherAlert("Small Craft", "body", event="Small Craft Advisory")
    )


def test_nwr_same_weather_event_eligibility_rejects_missing_event_name():
    assert not is_nwr_same_weather_event(WeatherAlert("Unknown", "body", event=None))


def test_county_zone_conversion_rejects_unknown_state_prefix():
    assert county_zone_to_same_code("XXC001") is None


def test_no_reliable_resolver_never_selects_unrelated_station():
    assert NoReliableAlertStationResolver().resolve_station([_alert()], _location()) is None


def test_empty_alert_batch_does_not_schedule_worker():
    tuner, _session, started, _url_provider, resolver = _make_tuner()

    tuner.tune_for_alerts([])

    assert started == []
    assert resolver.calls == []


def test_settings_provider_failure_disables_auto_tune_safely():
    tuner, _session, started, _url_provider, resolver = _make_tuner()
    tuner._settings_provider = MagicMock(side_effect=RuntimeError("settings unavailable"))

    tuner.tune_for_alerts([_alert()])

    assert started == []
    assert resolver.calls == []


def test_default_resolver_skips_in_worker_when_alert_has_no_reliable_coverage_metadata():
    started = []
    session = _FakeSession()
    url_provider = MagicMock()
    tuner = AlertRadioAutoTuner(
        settings_provider=lambda: _settings(),
        location_provider=_location,
        preferences=_FakePreferences(),
        session=session,
        url_provider=url_provider,
        thread_factory=lambda target: _FakeThread(target, started),
    )

    tuner.tune_for_alerts([_forecast_zone_alert()])
    assert len(started) == 1
    started[0]()

    url_provider.get_stream_urls.assert_not_called()


def test_station_resolution_failure_does_not_fetch_or_play_streams():
    tuner, _session, started, url_provider, _resolver = _make_tuner(resolver=_RaisingResolver())

    tuner.tune_for_alerts([_alert()])
    assert len(started) == 1
    started[0]()

    url_provider.get_stream_urls.assert_not_called()


def test_location_provider_failure_still_allows_resolver_without_location():
    station = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
    resolver = _MappedResolver(station)
    started = []
    tuner, _session, _started, url_provider, _resolver = _make_tuner(
        resolver=resolver,
        started=started,
    )
    tuner._location_provider = MagicMock(side_effect=RuntimeError("location unavailable"))
    url_provider.get_stream_urls.return_value = []

    tuner.tune_for_alerts([_alert()])
    started[0]()

    assert resolver.calls[0][1] is None


def test_weatherindex_resolver_matches_alert_same_code_to_station_coverage():
    austin = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
    station_db = StationDatabase([austin])
    weatherindex = _FakeWeatherIndexClient({"WXK27": _metadata("WXK27", ["048453"])})
    resolver = WeatherIndexAlertStationResolver(
        station_database=station_db,
        weatherindex_client=weatherindex,
    )
    alert = _alert()
    alert.same_codes = ["048453"]
    alert.affected_zones = []

    station = resolver.resolve_station([alert], _location())

    assert station == austin
    assert weatherindex.calls == ["WXK27"]


def test_weatherindex_resolver_converts_county_zone_to_same_code():
    austin = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
    station_db = StationDatabase([austin])
    weatherindex = _FakeWeatherIndexClient({"WXK27": _metadata("WXK27", ["048453"])})
    resolver = WeatherIndexAlertStationResolver(
        station_database=station_db,
        weatherindex_client=weatherindex,
    )

    station = resolver.resolve_station([_alert()], _location())

    assert station == austin


def test_weatherindex_resolver_skips_forecast_zone_without_same_metadata():
    austin = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
    station_db = StationDatabase([austin])
    weatherindex = _FakeWeatherIndexClient({"WXK27": _metadata("WXK27", ["048453"])})
    resolver = WeatherIndexAlertStationResolver(
        station_database=station_db,
        weatherindex_client=weatherindex,
    )

    station = resolver.resolve_station([_forecast_zone_alert()], _location())

    assert station is None
    assert weatherindex.calls == []


def test_weatherindex_resolver_skips_station_without_coverage_metadata():
    austin = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
    station_db = StationDatabase([austin])
    weatherindex = _FakeWeatherIndexClient({"WXK27": _metadata("WXK27", [])})
    resolver = WeatherIndexAlertStationResolver(
        station_database=station_db,
        weatherindex_client=weatherindex,
    )

    station = resolver.resolve_station([_alert()], _location())

    assert station is None
    assert weatherindex.calls == ["WXK27"]


def test_weatherindex_resolver_uses_nearest_matching_station_for_tie_breaker():
    far_station = Station("AAAAA", 162.4, "Far, TX", 35.0, -101.0, "TX")
    near_station = Station("ZZZZZ", 162.4, "Near, TX", 30.3, -97.8, "TX")
    station_db = StationDatabase([far_station, near_station])
    weatherindex = _FakeWeatherIndexClient(
        {
            "AAAAA": _metadata("AAAAA", ["048453"]),
            "ZZZZZ": _metadata("ZZZZZ", ["048453"]),
        }
    )
    resolver = WeatherIndexAlertStationResolver(
        station_database=station_db,
        weatherindex_client=weatherindex,
    )

    station = resolver.resolve_station([_alert()], _location())

    assert station == near_station
    assert weatherindex.calls == ["ZZZZZ"]


def test_weatherindex_resolver_uses_call_sign_order_without_location():
    later_station = Station("ZZZZZ", 162.4, "Later, TX", 30.3, -97.8, "TX")
    earlier_station = Station("AAAAA", 162.4, "Earlier, TX", 35.0, -101.0, "TX")
    station_db = StationDatabase([later_station, earlier_station])
    weatherindex = _FakeWeatherIndexClient(
        {
            "AAAAA": _metadata("AAAAA", ["048453"]),
            "ZZZZZ": _metadata("ZZZZZ", ["048453"]),
        }
    )
    resolver = WeatherIndexAlertStationResolver(
        station_database=station_db,
        weatherindex_client=weatherindex,
    )

    station = resolver.resolve_station([_alert()], None)

    assert station == earlier_station
    assert weatherindex.calls == ["AAAAA"]


def test_weatherindex_resolver_uses_alert_same_code_state_for_no_location_tie_breaker():
    texas_station = Station("ZZZZZ", 162.4, "Texas, TX", 30.3, -97.8, "TX")
    kansas_station = Station("AAAAA", 162.4, "Kansas, KS", 39.0, -96.0, "KS")
    station_db = StationDatabase([kansas_station, texas_station])
    weatherindex = _FakeWeatherIndexClient(
        {
            "AAAAA": _metadata("AAAAA", ["048453"]),
            "ZZZZZ": _metadata("ZZZZZ", ["048453"]),
        }
    )
    resolver = WeatherIndexAlertStationResolver(
        station_database=station_db,
        weatherindex_client=weatherindex,
    )
    alert = _alert()
    alert.affected_zones = []
    alert.same_codes = ["048453"]

    station = resolver.resolve_station([alert], None)

    assert station == texas_station
    assert weatherindex.calls == ["ZZZZZ"]


def test_weatherindex_resolver_ignores_malformed_same_codes_and_unknown_states():
    station_db = StationDatabase([Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")])
    weatherindex = _FakeWeatherIndexClient({"WXK27": _metadata("WXK27", ["048453"])})
    resolver = WeatherIndexAlertStationResolver(
        station_database=station_db,
        weatherindex_client=weatherindex,
    )
    alert = _alert()
    alert.affected_zones = ["XXC001"]
    alert.same_codes = ["abc", object()]

    station = resolver.resolve_station([alert], None)

    assert station is None
    assert weatherindex.calls == []


def test_auto_tune_schedules_worker_for_resolved_alert_station():
    tuner, _session, started, _url_provider, resolver = _make_tuner()

    tuner.tune_for_alerts([_alert()])

    assert len(started) == 1
    assert resolver.calls == []
    _url_provider.get_stream_urls.return_value = []
    started[0]()
    assert resolver.calls[0][0][0].event == "Tornado Warning"
    assert resolver.calls[0][1].name == "Austin"


def test_auto_tune_invalid_duration_defaults_to_five_minutes_and_stops_playback():
    times = iter([100.0, 401.0])
    tuner, session, started, _url_provider, _resolver = _make_tuner(
        settings=_settings(auto_tune_weather_radio_duration_minutes=0),
    )
    tuner._monotonic = lambda: next(times)

    tuner.tune_for_alerts([_alert()])
    started[0]()

    session.stop.assert_called_once_with()
    assert session.is_playing() is False


def test_stop_cancels_pending_auto_tune_before_stream_starts():
    tuner, session, started, url_provider, _resolver = _make_tuner()

    tuner.tune_for_alerts([_alert()])
    tuner.stop()
    started[0]()

    url_provider.get_stream_urls.assert_not_called()
    assert session.playing_station is None


def test_manual_playback_starting_during_resolution_prevents_auto_tune():
    manual_station = Station("KHB40", 162.55, "Manual, TX", 30.0, -97.0, "TX")
    tuner, session, started, url_provider, _resolver = _make_tuner()

    tuner.tune_for_alerts([_alert()])
    session._playing = True
    session.playing_station = manual_station
    started[0]()

    url_provider.get_stream_urls.assert_not_called()
    assert session.playing_station == manual_station


def test_auto_tune_clears_station_when_all_stream_urls_fail():
    tuner, session, started, url_provider, _resolver = _make_tuner()
    url_provider.get_stream_urls.return_value = [
        "https://example.test/primary",
        "https://example.test/backup",
    ]
    session.player = _FakePlayer(session, results=[False, False])

    tuner.tune_for_alerts([_alert()])
    started[0]()

    assert session.player.played_urls == [
        "https://example.test/primary",
        "https://example.test/backup",
    ]
    assert session.playing_station is None


def test_duplicate_alert_batch_extends_existing_auto_tune_without_overlap():
    tuner, _session, started, _url_provider, _resolver = _make_tuner()

    tuner.tune_for_alerts([_alert()])
    tuner.tune_for_alerts([_alert()])

    assert len(started) == 1


def test_manual_playback_is_respected_and_not_interrupted():
    manual_station = Station("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
    session = _FakeSession(playing=True, station=manual_station)
    tuner, _session, started, _url_provider, _resolver = _make_tuner(session=session)

    tuner.tune_for_alerts([_alert()])

    assert started == []
    session.stop.assert_not_called()
