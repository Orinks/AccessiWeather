"""Tests for LocationService."""

from unittest.mock import MagicMock

from accessiweather.services.location_service import LocationService


def _make_service():
    """Create a LocationService with a mock LocationManager."""
    mgr = MagicMock()
    mgr.saved_locations = {
        "New York": {"lat": 40.7, "lon": -74.0},
        "Chicago": {"lat": 41.9, "lon": -87.6},
    }
    return LocationService(mgr), mgr


class TestLocationService:
    def test_update_data_source(self):
        svc, mgr = _make_service()
        svc.update_data_source("weatherapi")
        mgr.update_data_source.assert_called_once_with("weatherapi")

    def test_get_current_location(self):
        svc, mgr = _make_service()
        mgr.get_current_location.return_value = ("New York", 40.7, -74.0)
        assert svc.get_current_location() == ("New York", 40.7, -74.0)

    def test_get_current_location_none(self):
        svc, mgr = _make_service()
        mgr.get_current_location.return_value = None
        assert svc.get_current_location() is None

    def test_get_current_location_name(self):
        svc, mgr = _make_service()
        mgr.get_current_location_name.return_value = "Chicago"
        assert svc.get_current_location_name() == "Chicago"

    def test_get_current_location_name_none(self):
        svc, mgr = _make_service()
        mgr.get_current_location_name.return_value = None
        assert svc.get_current_location_name() is None

    def test_get_all_locations(self):
        svc, mgr = _make_service()
        mgr.get_all_locations.return_value = ["New York", "Chicago"]
        assert svc.get_all_locations() == ["New York", "Chicago"]

    def test_add_location_success(self):
        svc, mgr = _make_service()
        mgr.add_location.return_value = True
        assert svc.add_location("Boston", 42.4, -71.1) is True
        mgr.add_location.assert_called_once_with("Boston", 42.4, -71.1)

    def test_add_location_failure(self):
        svc, mgr = _make_service()
        mgr.add_location.return_value = False
        assert svc.add_location("London", 51.5, -0.1) is False

    def test_remove_location_success(self):
        svc, mgr = _make_service()
        mgr.remove_location.return_value = True
        assert svc.remove_location("New York") is True
        mgr.remove_location.assert_called_once_with("New York")

    def test_remove_location_failure(self):
        svc, mgr = _make_service()
        mgr.remove_location.return_value = False
        assert svc.remove_location("Unknown") is False

    def test_set_current_location(self):
        svc, mgr = _make_service()
        svc.set_current_location("Chicago")
        mgr.set_current_location.assert_called_once_with("Chicago")

    def test_get_location_coordinates_found(self):
        svc, mgr = _make_service()
        assert svc.get_location_coordinates("New York") == (40.7, -74.0)

    def test_get_location_coordinates_not_found(self):
        svc, mgr = _make_service()
        assert svc.get_location_coordinates("Unknown") is None

    def test_get_nationwide_location(self):
        svc, mgr = _make_service()
        result = svc.get_nationwide_location()
        assert len(result) == 3
        assert isinstance(result[0], str)
        assert isinstance(result[1], (int, float))
        assert isinstance(result[2], (int, float))

    def test_is_nationwide_location(self):
        svc, mgr = _make_service()
        mgr.is_nationwide_location.return_value = True
        assert svc.is_nationwide_location("Nationwide") is True
        mgr.is_nationwide_location.assert_called_once_with("Nationwide")

    def test_is_nationwide_location_false(self):
        svc, mgr = _make_service()
        mgr.is_nationwide_location.return_value = False
        assert svc.is_nationwide_location("New York") is False
