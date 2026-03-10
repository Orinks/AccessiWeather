from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from accessiweather.api.nws.weather_data import NwsWeatherData


def _station(station_id: str, name: str, lat: float, lon: float) -> dict:
    return {
        "type": "Feature",
        "properties": {"stationIdentifier": station_id, "name": name},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def _obs(minutes_old: int, *, has_data: bool = True) -> dict:
    value = 12.3 if has_data else None
    return {
        "properties": {
            "timestamp": (datetime.now(UTC) - timedelta(minutes=minutes_old)).isoformat(),
            "temperature": {"value": value},
        }
    }


class _FakeWrapper:
    def __init__(self, stations: list[dict], observations: dict[str, dict]):
        self._stations = stations
        self._observations = observations
        self.core_client = SimpleNamespace(BASE_URL="https://api.weather.gov")

        def _make_api_request(_func, station_id: str):
            return self._observations[station_id]

        self.core_client.make_api_request = _make_api_request
        self.point_location = SimpleNamespace(
            get_point_data=lambda lat, lon, force_refresh=False: {
                "properties": {"observationStations": "https://example.test/stations"}
            }
        )

    def _rate_limit(self):
        return None

    def _generate_cache_key(self, endpoint: str, params: dict):
        return f"{endpoint}:{sorted(params.items())}"

    def _get_cached_or_fetch(self, cache_key: str, fetch_data, force_refresh: bool):
        return fetch_data()

    def _fetch_url(self, url: str):
        return {"features": self._stations}


def test_major_airport_preferred_selects_major_station_over_nearest_small_field():
    stations = [
        _station("K8A0", "Small Municipal Airport", 40.000, -86.000),
        _station("KIND", "Indianapolis International Airport", 40.020, -86.010),
    ]
    observations = {"K8A0": _obs(5), "KIND": _obs(8)}
    data = NwsWeatherData(_FakeWrapper(stations, observations))

    current = data.get_current_conditions(
        40.001,
        -86.000,
        station_selection_strategy="major_airport_preferred",
    )

    assert current == observations["KIND"]


def test_freshest_observation_prefers_more_recent_station_within_nearest_group():
    stations = [
        _station("KAAA", "Small Airport", 40.000, -86.000),
        _station("KBBB", "Regional Airport", 40.005, -86.005),
        _station("KCCC", "County Airport", 40.008, -86.009),
    ]
    observations = {
        "KAAA": _obs(95),
        "KBBB": _obs(12),
        "KCCC": _obs(60),
    }
    data = NwsWeatherData(_FakeWrapper(stations, observations))

    current = data.get_current_conditions(
        40.000,
        -86.000,
        station_selection_strategy="freshest_observation",
    )

    assert current == observations["KBBB"]


def test_hybrid_default_falls_back_when_preferred_station_has_missing_data():
    stations = [
        _station("KSM1", "Small Field", 41.000, -87.000),
        _station("KORD", "Chicago O'Hare International Airport", 41.020, -87.010),
    ]
    observations = {
        "KSM1": _obs(25, has_data=True),
        "KORD": _obs(5, has_data=False),
    }
    data = NwsWeatherData(_FakeWrapper(stations, observations))

    current = data.get_current_conditions(
        41.000,
        -87.000,
        station_selection_strategy="hybrid_default",
    )

    assert current == observations["KSM1"]
