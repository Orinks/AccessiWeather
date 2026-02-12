"""Tests for NOAA Weather Radio station database module."""

from accessiweather.noaa_radio import Station, StationDatabase
from accessiweather.noaa_radio.station_db import StationResult, _haversine


class TestStation:
    """Tests for the Station dataclass."""

    def test_station_fields(self) -> None:
        s = Station("KEC49", 162.55, "Test", 40.0, -74.0, "NY")
        assert s.call_sign == "KEC49"
        assert s.frequency == 162.55
        assert s.name == "Test"
        assert s.lat == 40.0
        assert s.lon == -74.0
        assert s.state == "NY"


class TestHaversine:
    """Tests for haversine distance calculation."""

    def test_same_point(self) -> None:
        assert _haversine(40.0, -74.0, 40.0, -74.0) == 0.0

    def test_known_distance(self) -> None:
        # New York to Los Angeles ≈ 3944 km
        dist = _haversine(40.7128, -74.0060, 34.0522, -118.2437)
        assert 3930 < dist < 3960

    def test_short_distance(self) -> None:
        # NYC to Philadelphia ≈ 130 km
        dist = _haversine(40.7128, -74.0060, 39.9526, -75.1652)
        assert 120 < dist < 140


class TestStationDatabase:
    """Tests for StationDatabase."""

    def test_get_all_stations_default(self) -> None:
        db = StationDatabase()
        stations = db.get_all_stations()
        assert len(stations) >= 20

    def test_get_all_stations_returns_copies(self) -> None:
        db = StationDatabase()
        s1 = db.get_all_stations()
        s2 = db.get_all_stations()
        assert s1 is not s2

    def test_get_stations_by_state(self) -> None:
        db = StationDatabase()
        tx = db.get_stations_by_state("TX")
        assert len(tx) >= 2
        assert all(s.state == "TX" for s in tx)

    def test_get_stations_by_state_case_insensitive(self) -> None:
        db = StationDatabase()
        assert db.get_stations_by_state("tx") == db.get_stations_by_state("TX")

    def test_get_stations_by_state_empty(self) -> None:
        db = StationDatabase()
        assert db.get_stations_by_state("ZZ") == []

    def test_find_nearest_returns_sorted(self) -> None:
        db = StationDatabase()
        results = db.find_nearest(40.7128, -74.0060, limit=5)
        assert len(results) == 5
        distances = [r.distance_km for r in results]
        assert distances == sorted(distances)

    def test_find_nearest_closest_is_nyc(self) -> None:
        db = StationDatabase()
        results = db.find_nearest(40.7128, -74.0060, limit=1)
        assert results[0].station.call_sign == "KEC49"
        assert results[0].distance_km < 1.0  # same coords

    def test_find_nearest_limit(self) -> None:
        db = StationDatabase()
        assert len(db.find_nearest(40.0, -74.0, limit=3)) == 3

    def test_find_nearest_returns_station_result(self) -> None:
        db = StationDatabase()
        results = db.find_nearest(40.0, -74.0, limit=1)
        assert isinstance(results[0], StationResult)
        assert isinstance(results[0].station, Station)
        assert isinstance(results[0].distance_km, float)

    def test_custom_stations(self) -> None:
        custom = [Station("TEST1", 162.5, "Test", 0.0, 0.0, "XX")]
        db = StationDatabase(stations=custom)
        assert len(db.get_all_stations()) == 1

    def test_all_stations_are_us(self) -> None:
        db = StationDatabase()
        us_states = {
            "AL",
            "AK",
            "AZ",
            "AR",
            "CA",
            "CO",
            "CT",
            "DE",
            "FL",
            "GA",
            "HI",
            "ID",
            "IL",
            "IN",
            "IA",
            "KS",
            "KY",
            "LA",
            "ME",
            "MD",
            "MA",
            "MI",
            "MN",
            "MS",
            "MO",
            "MT",
            "NE",
            "NV",
            "NH",
            "NJ",
            "NM",
            "NY",
            "NC",
            "ND",
            "OH",
            "OK",
            "OR",
            "PA",
            "RI",
            "SC",
            "SD",
            "TN",
            "TX",
            "UT",
            "VT",
            "VA",
            "WA",
            "WV",
            "WI",
            "WY",
            "DC",
            "PR",
            "VI",
            "GU",
            "AS",
            "MP",
        }
        for s in db.get_all_stations():
            assert s.state in us_states, f"{s.call_sign} has invalid state {s.state}"
