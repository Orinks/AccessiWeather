"""Tests for Open-Meteo forecast mapping behavior."""

from accessiweather.openmeteo_mapper import OpenMeteoMapper


class TestOpenMeteoMapperCurrentFields:
    def test_current_pressure_hpa_is_mapped_to_pascals(self):
        mapped = OpenMeteoMapper().map_current_conditions(
            {
                "current": {
                    "temperature_2m": 72.0,
                    "relative_humidity_2m": 55,
                    "apparent_temperature": 72.0,
                    "wind_direction_10m": 180,
                    "wind_speed_10m": 8.0,
                    "pressure_msl": 1015.0,
                    "weather_code": 1,
                },
                "current_units": {"temperature_2m": "°F", "pressure_msl": "hPa"},
            }
        )

        pressure = mapped["properties"]["barometricPressure"]

        assert pressure["value"] == 101500.0
        assert pressure["unitCode"] == "wmoUnit:Pa"

    def test_current_pressure_pascal_unit_is_not_scaled_twice(self):
        mapped = OpenMeteoMapper().map_current_conditions(
            {
                "current": {
                    "temperature_2m": 72.0,
                    "relative_humidity_2m": 55,
                    "apparent_temperature": 72.0,
                    "wind_direction_10m": 180,
                    "wind_speed_10m": 8.0,
                    "pressure_msl": 101500.0,
                    "weather_code": 1,
                },
                "current_units": {"temperature_2m": "°F", "pressure_msl": "Pa"},
            }
        )

        assert mapped["properties"]["barometricPressure"]["value"] == 101500.0


def _make_daily_payload(
    dates: list[str],
    highs: list[float | None],
    lows: list[float | None],
) -> dict:
    return {
        "utc_offset_seconds": 0,
        "daily": {
            "time": dates,
            "weather_code": [1] * len(dates),
            "temperature_2m_max": highs,
            "temperature_2m_min": lows,
            "wind_speed_10m_max": [10] * len(dates),
            "wind_direction_10m_dominant": [180] * len(dates),
        },
        "daily_units": {
            "temperature_2m_max": "°F",
            "temperature_2m_min": "°F",
            "wind_speed_10m_max": "mph",
        },
    }


class TestOpenMeteoMapperForecastPairing:
    def test_daytime_period_gets_following_night_low(self):
        mapped = OpenMeteoMapper().map_forecast(_make_daily_payload(["2026-03-19"], [54.0], [39.0]))

        periods = mapped["properties"]["periods"]

        assert periods[0]["isDaytime"] is True
        assert periods[0]["temperature"] == 54
        assert periods[0]["temperature_low"] == 39
        assert periods[1]["isDaytime"] is False
        assert periods[1]["temperature"] == 39
        assert "temperature_low" not in periods[1]

    def test_multiple_day_night_pairs_each_get_low(self):
        mapped = OpenMeteoMapper().map_forecast(
            _make_daily_payload(
                ["2026-03-19", "2026-03-20"],
                [54.0, 58.0],
                [39.0, 42.0],
            )
        )

        periods = mapped["properties"]["periods"]

        assert periods[0]["temperature_low"] == 39
        assert periods[2]["temperature_low"] == 42

    def test_missing_night_temperature_leaves_day_low_unset(self):
        mapped = OpenMeteoMapper().map_forecast(_make_daily_payload(["2026-03-19"], [54.0], [None]))

        periods = mapped["properties"]["periods"]

        assert "temperature_low" not in periods[0]

    def test_daily_weekday_uses_local_date_for_eastern_hemisphere(self):
        # 2026-03-19 is a Thursday. With a +10h offset (e.g. Australia), naive
        # local midnight converts to the previous day in UTC; the period name
        # must still reflect the local calendar day, not the UTC-shifted one.
        payload = _make_daily_payload(["2026-03-19"], [54.0], [39.0])
        payload["utc_offset_seconds"] = 10 * 3600

        periods = OpenMeteoMapper().map_forecast(payload)["properties"]["periods"]

        assert periods[0]["name"] == "Thursday"
        assert periods[1]["name"] == "Thursday Night"
        # Day period should start at 6am local (not in UTC).
        assert periods[0]["startTime"].startswith("2026-03-19T06:00:00")

    def test_daily_date_with_z_suffix_uses_value_error_fallback(self):
        payload = _make_daily_payload(["2026-03-19Z"], [54.0], [39.0])

        periods = OpenMeteoMapper().map_forecast(payload)["properties"]["periods"]

        assert periods[0]["name"] == "Thursday"


class TestOpenMeteoMapperHourlyFields:
    def test_hourly_mapping_includes_humidity_and_dewpoint(self):
        mapped = OpenMeteoMapper().map_hourly_forecast(
            {
                "utc_offset_seconds": 0,
                "hourly": {
                    "time": ["2026-03-19T12:00"],
                    "temperature_2m": [72.0],
                    "relative_humidity_2m": [55],
                    "dew_point_2m": [54.0],
                    "weather_code": [1],
                    "wind_speed_10m": [8.0],
                    "wind_direction_10m": [180],
                    "is_day": [1],
                },
                "hourly_units": {
                    "temperature_2m": "°F",
                    "wind_speed_10m": "mph",
                },
            }
        )

        period = mapped["properties"]["periods"][0]

        assert period["relativeHumidity"]["value"] == 55
        assert period["dewpoint"]["value"] == 54.0

    def test_hourly_mapping_calculates_dewpoint_when_missing(self):
        mapped = OpenMeteoMapper().map_hourly_forecast(
            {
                "utc_offset_seconds": 0,
                "hourly": {
                    "time": ["2026-03-19T12:00"],
                    "temperature_2m": [72.0],
                    "relative_humidity_2m": [55],
                    "weather_code": [1],
                    "wind_speed_10m": [8.0],
                    "wind_direction_10m": [180],
                    "is_day": [1],
                },
                "hourly_units": {
                    "temperature_2m": "°F",
                    "wind_speed_10m": "mph",
                },
            }
        )

        period = mapped["properties"]["periods"][0]

        assert period["relativeHumidity"]["value"] == 55
        assert period["dewpoint"]["value"] is not None
