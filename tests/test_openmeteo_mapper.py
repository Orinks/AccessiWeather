"""Tests for Open-Meteo forecast mapping behavior."""

from accessiweather.openmeteo_mapper import OpenMeteoMapper


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
