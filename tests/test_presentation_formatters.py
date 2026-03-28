from __future__ import annotations

from datetime import UTC, datetime

import pytest

from accessiweather.display.presentation.formatters import format_display_time, format_hourly_wind
from accessiweather.models.weather import HourlyForecastPeriod
from accessiweather.utils import TemperatureUnit


def test_format_display_time_local_mode_utc_timestamp_omits_utc_suffix() -> None:
    start_time = datetime(2026, 1, 20, 18, 0, tzinfo=UTC)

    rendered = format_display_time(
        start_time,
        time_display_mode="local",
        use_12hour=False,
        show_timezone=True,
    )

    assert rendered == "18:00"


def test_format_display_time_local_mode_naive_timestamp_stays_as_is() -> None:
    start_time = datetime(2026, 1, 20, 9, 30)

    rendered = format_display_time(
        start_time,
        time_display_mode="local",
        use_12hour=False,
        show_timezone=True,
    )

    assert rendered == "09:30"


# ---------------------------------------------------------------------------
# Regression tests – format_hourly_wind unit consistency (PW non-US bug)
# ---------------------------------------------------------------------------


def _make_period(
    *,
    wind_direction: str | None = "SW",
    wind_speed: str | None = None,
    wind_speed_mph: float | None = None,
) -> HourlyForecastPeriod:
    return HourlyForecastPeriod(
        start_time=datetime(2026, 3, 27, 12, 0, tzinfo=UTC),
        wind_direction=wind_direction,
        wind_speed=wind_speed,
        wind_speed_mph=wind_speed_mph,
    )


class TestFormatHourlyWindUnitConsistency:
    """format_hourly_wind must render speed and gust in the same unit."""

    def test_celsius_unit_pref_uses_kmh_for_numeric_wind_speed(self) -> None:
        """When wind_speed_mph is set and unit_pref is Celsius, output is in km/h."""
        # format_wind_speed maps CELSIUS → km/h
        period = _make_period(wind_speed_mph=10.0)
        result = format_hourly_wind(period, TemperatureUnit.CELSIUS)
        assert result is not None
        assert "km/h" in result
        assert "mph" not in result

    def test_us_unit_pref_uses_mph_for_numeric_wind_speed(self) -> None:
        """When wind_speed_mph is set and unit_pref is Fahrenheit, output is in mph."""
        period = _make_period(wind_speed_mph=14.0)
        result = format_hourly_wind(period, TemperatureUnit.FAHRENHEIT)
        assert result is not None
        assert "mph" in result

    def test_fallback_to_wind_speed_string_when_no_numeric(self) -> None:
        """Periods without wind_speed_mph (NWS/VC) use the pre-formatted string."""
        period = _make_period(wind_speed="12 mph")
        result = format_hourly_wind(period, TemperatureUnit.CELSIUS)
        assert result == "SW at 12 mph"

    def test_returns_none_when_no_wind_data(self) -> None:
        period = _make_period(wind_speed=None, wind_speed_mph=None)
        assert format_hourly_wind(period, TemperatureUnit.FAHRENHEIT) is None

    def test_returns_none_when_no_direction(self) -> None:
        period = _make_period(wind_direction=None, wind_speed_mph=10.0)
        assert format_hourly_wind(period, TemperatureUnit.FAHRENHEIT) is None

    @pytest.mark.parametrize(
        "units,wind_raw,expected_unit_substr",
        [
            # CA: 14 km/h → ~8.7 mph → displayed in km/h for Celsius user pref
            ("ca", 14.0, "km/h"),
            # SI: 5 m/s → ~11.2 mph → displayed in km/h for Celsius user pref
            # (CELSIUS maps to km/h in format_wind_speed, not m/s)
            ("si", 5.0, "km/h"),
        ],
    )
    def test_non_us_pirate_weather_speed_matches_gust_unit(
        self, units: str, wind_raw: float, expected_unit_substr: str
    ) -> None:
        """Regression: non-US PW wind speed and gust must use the same unit."""
        from accessiweather.pirate_weather_client import PirateWeatherClient

        pw_client = PirateWeatherClient(api_key="test", units=units)
        payload = {
            "offset": 0,
            "hourly": {
                "data": [
                    {
                        "time": 1700000000,
                        "temperature": 20.0,
                        "humidity": 0.60,
                        "windSpeed": wind_raw,
                        "windGust": wind_raw * 1.5,
                        "windBearing": 225,
                        "pressure": 1010.0,
                        "precipProbability": 0.0,
                        "precipIntensity": 0.0,
                        "cloudCover": 0.3,
                        "uvIndex": 2,
                        "visibility": 10.0,
                    }
                ]
            },
        }
        hourly = pw_client._parse_hourly_forecast(payload)
        period = hourly.periods[0]

        # Both speed and gust must carry numeric mph values
        assert period.wind_speed_mph is not None
        assert period.wind_gust_mph is not None

        # When formatted with Celsius preference the displayed unit must match
        speed_str = format_hourly_wind(period, TemperatureUnit.CELSIUS)
        assert speed_str is not None
        assert expected_unit_substr in speed_str, (
            f"Expected '{expected_unit_substr}' in speed '{speed_str}'"
        )
