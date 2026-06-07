"""Tests for alert-triggered NOAA Weather Radio auto-tuning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from accessiweather.models import AppSettings, Location, WeatherAlert
from accessiweather.noaa_radio.alert_auto_tune import (
    AlertRadioAutoTuner,
    WeatherIndexAlertStationResolver,
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
    def play(self, _url: str) -> bool:
        return True


class _FakeSession:
    def __init__(self, *, playing: bool = False, station: Station | None = None) -> None:
        self.playing_station = station
        self.current_urls = []
        self.current_url_index = 0
        self.player = _FakePlayer()
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


def test_auto_tune_schedules_worker_for_resolved_alert_station():
    tuner, _session, started, _url_provider, resolver = _make_tuner()

    tuner.tune_for_alerts([_alert()])

    assert len(started) == 1
    assert resolver.calls == []
    _url_provider.get_stream_urls.return_value = []
    started[0]()
    assert resolver.calls[0][0][0].event == "Tornado Warning"
    assert resolver.calls[0][1].name == "Austin"


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
