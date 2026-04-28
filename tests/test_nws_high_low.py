"""Tests for NWS high/low temperature pairing and hourly pressure parsing."""

import httpx
import pytest

from accessiweather.models import Location
from accessiweather.weather_client_nws import (
    _fetch_nws_gridpoint_pressure,
    apply_nws_gridpoint_pressure,
    get_nws_hourly_forecast,
    parse_nws_forecast,
    parse_nws_gridpoint_pressure,
    parse_nws_hourly_forecast,
)


def _make_period(name, temp, unit="F", is_daytime=True):
    return {
        "name": name,
        "temperature": temp,
        "temperatureUnit": unit,
        "isDaytime": is_daytime,
        "shortForecast": "Sunny",
        "detailedForecast": "",
        "windSpeed": "10 mph",
        "windDirection": "N",
        "icon": "",
        "startTime": "2026-02-12T06:00:00-05:00",
        "endTime": "2026-02-12T18:00:00-05:00",
    }


def _wrap(periods):
    return {"properties": {"periods": periods}}


class TestNwsHighLowPairing:
    def test_daytime_gets_nighttime_low(self):
        data = _wrap(
            [
                _make_period("Today", 34, is_daytime=True),
                _make_period("Tonight", 16, is_daytime=False),
            ]
        )
        forecast = parse_nws_forecast(data)
        assert forecast.periods[0].temperature == 34
        assert forecast.periods[0].temperature_low == 16
        assert forecast.periods[1].temperature == 16
        assert forecast.periods[1].temperature_low is None

    def test_multiple_day_night_pairs(self):
        data = _wrap(
            [
                _make_period("Today", 34, is_daytime=True),
                _make_period("Tonight", 16, is_daytime=False),
                _make_period("Friday", 36, is_daytime=True),
                _make_period("Friday Night", 20, is_daytime=False),
            ]
        )
        forecast = parse_nws_forecast(data)
        assert forecast.periods[0].temperature_low == 16
        assert forecast.periods[2].temperature_low == 20

    def test_nighttime_first_no_crash(self):
        """When forecast starts at night (evening request), no pairing for first period."""
        data = _wrap(
            [
                _make_period("Tonight", 16, is_daytime=False),
                _make_period("Friday", 36, is_daytime=True),
                _make_period("Friday Night", 20, is_daytime=False),
            ]
        )
        forecast = parse_nws_forecast(data)
        assert forecast.periods[0].temperature_low is None
        assert forecast.periods[1].temperature_low == 20

    def test_single_daytime_period_no_crash(self):
        data = _wrap([_make_period("Today", 34, is_daytime=True)])
        forecast = parse_nws_forecast(data)
        assert forecast.periods[0].temperature_low is None

    def test_detailed_forecast_preserved(self):
        """detailed_forecast is mapped from NWS detailedForecast field."""
        data = _wrap(
            [
                {
                    **_make_period("Today", 34, is_daytime=True),
                    "detailedForecast": "Sunny, with a high near 34. Northwest wind 10 mph.",
                    "shortForecast": "Sunny",
                }
            ]
        )
        forecast = parse_nws_forecast(data)
        assert (
            forecast.periods[0].detailed_forecast
            == "Sunny, with a high near 34. Northwest wind 10 mph."
        )

    def test_probability_of_precipitation_preserved(self):
        """NWS probabilityOfPrecipitation.value is mapped to the forecast period."""
        data = _wrap(
            [
                {
                    **_make_period("Today", 34, is_daytime=True),
                    "probabilityOfPrecipitation": {
                        "unitCode": "wmoUnit:percent",
                        "value": 52,
                    },
                }
            ]
        )
        forecast = parse_nws_forecast(data)
        assert forecast.periods[0].precipitation_probability == 52

    def test_empty_periods(self):
        forecast = parse_nws_forecast({"properties": {"periods": []}})
        assert len(forecast.periods) == 0

    def test_consecutive_daytime_no_pairing(self):
        """Two daytime periods in a row shouldn't pair."""
        data = _wrap(
            [
                _make_period("Today", 34, is_daytime=True),
                _make_period("Tomorrow", 36, is_daytime=True),
            ]
        )
        forecast = parse_nws_forecast(data)
        assert forecast.periods[0].temperature_low is None
        assert forecast.periods[1].temperature_low is None


def _hourly_payload(start_time: str = "2026-04-26T10:00:00-04:00"):
    return {
        "properties": {
            "periods": [
                {
                    "startTime": start_time,
                    "endTime": "2026-04-26T11:00:00-04:00",
                    "temperature": 60,
                    "temperatureUnit": "F",
                    "shortForecast": "Cloudy",
                    "windSpeed": "5 mph",
                    "windDirection": "N",
                    "probabilityOfPrecipitation": {
                        "unitCode": "wmoUnit:percent",
                        "value": 14,
                    },
                }
            ]
        }
    }


class TestNwsHourlyPressure:
    def test_probability_of_precipitation_preserved(self):
        """NWS hourly probabilityOfPrecipitation.value is mapped to the hourly period."""
        hourly = parse_nws_hourly_forecast(_hourly_payload())
        assert hourly.periods[0].precipitation_probability == 14

    @pytest.mark.asyncio
    async def test_get_nws_hourly_forecast_applies_gridpoint_pressure(self):
        location = Location(name="Test", latitude=40.0, longitude=-74.0)
        grid_data = {
            "properties": {
                "forecastHourly": "https://example.test/hourly",
                "forecastGridData": "https://example.test/grid",
            }
        }

        def handler(request):
            if str(request.url) == "https://example.test/hourly":
                return httpx.Response(200, json=_hourly_payload())
            if str(request.url) == "https://example.test/grid":
                return httpx.Response(
                    200,
                    json={
                        "properties": {
                            "pressure": {
                                "values": [
                                    {
                                        "validTime": "2026-04-26T10:00:00-04:00/PT1H",
                                        "value": 101325,
                                    }
                                ]
                            }
                        }
                    },
                )
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await get_nws_hourly_forecast(
                location,
                "https://api.weather.gov",
                "AccessiWeather tests",
                10,
                client,
                grid_data,
            )

        assert result is not None
        assert result.periods[0].pressure_mb == 1013.25

    @pytest.mark.asyncio
    async def test_fetch_gridpoint_pressure_returns_empty_when_url_missing(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: None)) as client:
            result = await _fetch_nws_gridpoint_pressure({"properties": {}}, client, {})

        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_gridpoint_pressure_ignores_nonretryable_errors(self):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(404))
        ) as client:
            result = await _fetch_nws_gridpoint_pressure(
                {"properties": {"forecastGridData": "https://example.test/grid"}},
                client,
                {},
            )

        assert result == {}

    def test_gridpoint_pressure_applies_to_hourly_periods(self):
        hourly = parse_nws_hourly_forecast(_hourly_payload())
        pressure = parse_nws_gridpoint_pressure(
            {
                "properties": {
                    "pressure": {
                        "uom": "wmoUnit:Pa",
                        "values": [
                            {
                                "validTime": "2026-04-26T10:00:00-04:00/PT1H",
                                "value": 101325,
                            }
                        ],
                    }
                }
            }
        )

        result = apply_nws_gridpoint_pressure(hourly, pressure)

        assert result.periods[0].pressure_mb == 1013.25
        assert result.periods[0].pressure_in is not None

    def test_gridpoint_pressure_ignores_far_valid_times(self):
        hourly = parse_nws_hourly_forecast(_hourly_payload())
        pressure = parse_nws_gridpoint_pressure(
            {
                "properties": {
                    "pressure": {
                        "values": [
                            {
                                "validTime": "2026-04-26T15:00:00-04:00/PT1H",
                                "value": 101325,
                            }
                        ]
                    }
                }
            }
        )

        result = apply_nws_gridpoint_pressure(hourly, pressure)

        assert result.periods[0].pressure_mb is None
        assert result.periods[0].pressure_in is None

    def test_gridpoint_pressure_parser_skips_invalid_values(self):
        pressure = parse_nws_gridpoint_pressure(
            {
                "properties": {
                    "pressure": {
                        "values": [
                            None,
                            {"validTime": None, "value": 101325},
                            {"validTime": "not-a-time/PT1H", "value": 101325},
                            {"validTime": "2026-04-26T10:00:00-04:00/PT1H", "value": None},
                        ]
                    }
                }
            }
        )

        assert pressure == {}

    def test_gridpoint_pressure_keeps_existing_hourly_pressure(self):
        hourly = parse_nws_hourly_forecast(_hourly_payload())
        hourly.periods[0].pressure_mb = 1000.0
        pressure = parse_nws_gridpoint_pressure(
            {
                "properties": {
                    "pressure": {
                        "values": [
                            {
                                "validTime": "2026-04-26T10:00:00-04:00/PT1H",
                                "value": 101325,
                            }
                        ]
                    }
                }
            }
        )

        result = apply_nws_gridpoint_pressure(hourly, pressure)

        assert result is hourly
        assert result.periods[0].pressure_mb == 1000.0

    def test_gridpoint_pressure_returns_original_when_no_pressure_available(self):
        hourly = parse_nws_hourly_forecast(_hourly_payload())

        result = apply_nws_gridpoint_pressure(hourly, {})

        assert result is hourly
