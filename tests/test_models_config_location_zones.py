"""
Tests for Location zone-metadata fields and their JSON round-trip.

Covers Unit 1 of the Forecast Products PR 1 plan: zone fields on `Location`,
round-trip through `AppConfig.to_dict`/`from_dict`, and the
`_transform_point_data` passthrough of cwa/forecastZone/gridId.
"""

from __future__ import annotations

from accessiweather.api.nws.point_location import NwsPointLocation
from accessiweather.models import AppConfig, AppSettings, Location


def _make_config_with(location: Location) -> AppConfig:
    return AppConfig(
        settings=AppSettings(),
        locations=[location],
        current_location=location,
    )


class TestLocationZoneFieldsRoundTrip:
    """Round-trip scenarios for the six zone-metadata fields on Location."""

    def test_all_zone_fields_populated_round_trip(self):
        """All six zone fields round-trip identically through to_dict/from_dict."""
        loc = Location(
            name="Philadelphia",
            latitude=39.9526,
            longitude=-75.1652,
            timezone="America/New_York",
            country_code="US",
            forecast_zone_id="PAZ106",
            cwa_office="PHI",
            county_zone_id="PAC101",
            fire_zone_id="PAZ106",
            radar_station="KDIX",
        )

        data = _make_config_with(loc).to_dict()
        restored = AppConfig.from_dict(data)

        assert restored.current_location is not None
        restored_loc = restored.current_location
        assert restored_loc.forecast_zone_id == "PAZ106"
        assert restored_loc.cwa_office == "PHI"
        assert restored_loc.county_zone_id == "PAC101"
        assert restored_loc.fire_zone_id == "PAZ106"
        assert restored_loc.radar_station == "KDIX"
        assert restored_loc.timezone == "America/New_York"

        # And the same via the locations list
        assert len(restored.locations) == 1
        assert restored.locations[0].cwa_office == "PHI"

    def test_all_zone_fields_null_no_null_keys_emitted(self):
        """When zone fields are None, keys must not appear in serialized JSON."""
        loc = Location(name="Test", latitude=40.0, longitude=-74.0)

        data = _make_config_with(loc).to_dict()

        loc_json = data["locations"][0]
        current_json = data["current_location"]

        for zone_key in (
            "forecast_zone_id",
            "cwa_office",
            "county_zone_id",
            "fire_zone_id",
            "radar_station",
            "timezone",
        ):
            assert zone_key not in loc_json, f"{zone_key} should not be emitted when null"
            assert zone_key not in current_json, (
                f"{zone_key} should not be emitted when null on current_location"
            )

        # And round-trip still produces None
        restored = AppConfig.from_dict(data)
        assert restored.current_location is not None
        assert restored.current_location.forecast_zone_id is None
        assert restored.current_location.cwa_office is None
        assert restored.current_location.county_zone_id is None
        assert restored.current_location.fire_zone_id is None
        assert restored.current_location.radar_station is None
        assert restored.current_location.timezone is None

    def test_legacy_json_without_zone_fields_deserializes_cleanly(self):
        """Legacy JSON missing zone keys yields a Location with all-null zone fields."""
        legacy_data = {
            "settings": {},
            "locations": [
                {
                    "name": "Legacy City",
                    "latitude": 40.0,
                    "longitude": -74.0,
                }
            ],
            "current_location": {
                "name": "Legacy City",
                "latitude": 40.0,
                "longitude": -74.0,
            },
        }

        config = AppConfig.from_dict(legacy_data)

        assert len(config.locations) == 1
        legacy_loc = config.locations[0]
        assert legacy_loc.name == "Legacy City"
        assert legacy_loc.forecast_zone_id is None
        assert legacy_loc.cwa_office is None
        assert legacy_loc.county_zone_id is None
        assert legacy_loc.fire_zone_id is None
        assert legacy_loc.radar_station is None
        assert legacy_loc.timezone is None
        assert legacy_loc.country_code is None
        assert legacy_loc.marine_mode is False

        assert config.current_location is not None
        assert config.current_location.cwa_office is None

    def test_partial_population_only_cwa_office_round_trips(self):
        """Only cwa_office populated: other zone keys must not appear in JSON."""
        loc = Location(
            name="Partial",
            latitude=41.0,
            longitude=-75.0,
            cwa_office="PHI",
        )

        data = _make_config_with(loc).to_dict()
        loc_json = data["locations"][0]

        assert loc_json["cwa_office"] == "PHI"
        for zone_key in (
            "forecast_zone_id",
            "county_zone_id",
            "fire_zone_id",
            "radar_station",
            "timezone",
        ):
            assert zone_key not in loc_json

        restored = AppConfig.from_dict(data)
        restored_loc = restored.locations[0]
        assert restored_loc.cwa_office == "PHI"
        assert restored_loc.forecast_zone_id is None
        assert restored_loc.county_zone_id is None
        assert restored_loc.fire_zone_id is None
        assert restored_loc.radar_station is None
        assert restored_loc.timezone is None


class TestTransformPointDataZonePassthrough:
    """_transform_point_data must expose cwa, forecastZone, gridId."""

    def test_transform_point_data_includes_zone_passthroughs(self):
        """Realistic /points response: cwa, forecastZone, gridId pass through unchanged."""
        # Minimal-but-realistic NWS /points response fixture.
        raw_point_response = {
            "properties": {
                "forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast",
                "forecastHourly": ("https://api.weather.gov/gridpoints/PHI/50,75/forecast/hourly"),
                "forecastGridData": "https://api.weather.gov/gridpoints/PHI/50,75",
                "observationStations": ("https://api.weather.gov/gridpoints/PHI/50,75/stations"),
                "county": "https://api.weather.gov/zones/county/PAC101",
                "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ106",
                "timeZone": "America/New_York",
                "radarStation": "KDIX",
                "cwa": "PHI",
                "forecastZone": "https://api.weather.gov/zones/forecast/PAZ106",
                "gridId": "PHI",
            }
        }

        # _transform_point_data doesn't rely on wrapper internals.
        transformer = NwsPointLocation(wrapper_instance=None)
        transformed = transformer._transform_point_data(raw_point_response)

        props = transformed["properties"]
        # New passthroughs
        assert props["cwa"] == "PHI"
        assert props["forecastZone"] == "https://api.weather.gov/zones/forecast/PAZ106"
        assert props["gridId"] == "PHI"

        # Existing passthroughs remain intact (regression guard)
        assert props["county"] == "https://api.weather.gov/zones/county/PAC101"
        assert props["fireWeatherZone"] == "https://api.weather.gov/zones/fire/PAZ106"
        assert props["timeZone"] == "America/New_York"
        assert props["radarStation"] == "KDIX"
        assert props["forecast"] == ("https://api.weather.gov/gridpoints/PHI/50,75/forecast")
