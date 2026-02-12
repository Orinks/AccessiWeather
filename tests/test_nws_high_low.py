"""Tests for NWS high/low temperature pairing in parse_nws_forecast."""

from accessiweather.weather_client_nws import parse_nws_forecast


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
