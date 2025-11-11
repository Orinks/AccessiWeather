"""Tests for Open-Meteo data mapper with timezone handling."""

from __future__ import annotations

from datetime import datetime

import pytest

from accessiweather.openmeteo_mapper import OpenMeteoMapper, _parse_openmeteo_datetime


class TestParseOpenMeteoDatetime:
    """Test the datetime parser for Open-Meteo responses."""

    def test_parse_with_utc_offset(self):
        """Test parsing naive datetime string with UTC offset."""
        # Open-Meteo with timezone="auto" returns naive strings in local time
        datetime_str = "2025-11-11T06:40:00"
        utc_offset_seconds = -18000  # EST is UTC-5 hours

        result = _parse_openmeteo_datetime(datetime_str, utc_offset_seconds)

        # Should convert to UTC and return ISO string
        assert result is not None
        assert "+" in result or "Z" in result  # Has timezone info

        # Parse back to verify correct conversion
        dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert dt.tzinfo is not None
        assert dt.hour == 11  # 6:40 AM EST = 11:40 AM UTC
        assert dt.minute == 40

    def test_parse_none_datetime(self):
        """Test parsing None datetime."""
        result = _parse_openmeteo_datetime(None, -18000)
        assert result is None

    def test_parse_none_offset(self):
        """Test parsing with None offset returns original string."""
        datetime_str = "2025-11-11T06:40:00"
        result = _parse_openmeteo_datetime(datetime_str, None)
        assert result == datetime_str

    def test_parse_already_utc(self):
        """Test parsing datetime with Z suffix (already UTC)."""
        datetime_str = "2025-11-11T11:40:00Z"
        utc_offset_seconds = -18000

        result = _parse_openmeteo_datetime(datetime_str, utc_offset_seconds)

        # Should handle Z suffix and convert properly
        assert result is not None

    def test_parse_invalid_datetime_returns_original(self):
        """Test parsing invalid datetime string returns original."""
        invalid_str = "not-a-datetime"
        result = _parse_openmeteo_datetime(invalid_str, -18000)
        assert result == invalid_str


class TestOpenMeteoMapperCurrentConditions:
    """Test mapping Open-Meteo current conditions responses."""

    @pytest.fixture
    def mapper(self):
        """Create mapper instance."""
        return OpenMeteoMapper()

    @pytest.fixture
    def sample_openmeteo_response(self):
        """Sample Open-Meteo API response."""
        return {
            "latitude": 39.9663,
            "longitude": -74.8103,
            "generationtime_ms": 0.123,
            "utc_offset_seconds": -18000,  # EST
            "timezone": "America/New_York",
            "timezone_abbreviation": "EST",
            "elevation": 50.0,
            "current_units": {
                "time": "iso8601",
                "temperature_2m": "°F",
                "relative_humidity_2m": "%",
                "apparent_temperature": "°F",
                "weather_code": "wmo code",
                "wind_speed_10m": "mph",
                "wind_direction_10m": "°",
                "pressure_msl": "hPa",
            },
            "current": {
                "time": "2025-11-11T09:25",  # Naive local time
                "temperature_2m": 55.4,
                "relative_humidity_2m": 72,
                "apparent_temperature": 52.1,
                "weather_code": 2,
                "wind_speed_10m": 8.5,
                "wind_direction_10m": 225,
                "pressure_msl": 1015.2,
            },
            "daily": {
                "time": ["2025-11-11"],
                "sunrise": ["2025-11-11T06:40"],  # Naive local time
                "sunset": ["2025-11-11T16:46"],  # Naive local time
                "uv_index_max": [3.2],
            },
        }

    def test_map_current_conditions_basic(self, mapper, sample_openmeteo_response):
        """Test basic current conditions mapping."""
        result = mapper.map_current_conditions(sample_openmeteo_response)

        assert result is not None
        assert "properties" in result
        props = result["properties"]

        # Check basic fields
        assert props["temperature"]["value"] == 55.4
        assert props["relativeHumidity"]["value"] == 72
        assert props["windSpeed"]["value"] == 8.5
        assert props["windDirection"]["value"] == 225

    def test_map_sunrise_sunset_not_converted_to_utc(self, mapper, sample_openmeteo_response):
        """Test that sunrise/sunset times are NOT converted to UTC."""
        result = mapper.map_current_conditions(sample_openmeteo_response)

        props = result["properties"]
        sunrise = props["sunrise"]
        sunset = props["sunset"]

        # Should be the original naive datetime strings (not converted to UTC)
        assert sunrise == "2025-11-11T06:40"
        assert sunset == "2025-11-11T16:46"

        # Should NOT have timezone info
        assert "+" not in sunrise
        assert "Z" not in sunrise
        assert "+" not in sunset
        assert "Z" not in sunset

    def test_map_timestamp_converted_to_utc(self, mapper, sample_openmeteo_response):
        """Test that current timestamp IS converted to UTC."""
        result = mapper.map_current_conditions(sample_openmeteo_response)

        props = result["properties"]
        timestamp = props["timestamp"]

        # Should be converted to UTC
        assert timestamp is not None
        assert "+" in timestamp or "Z" in timestamp

        # Parse and verify it's in UTC
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert dt.tzinfo is not None
        # 9:25 AM EST = 14:25 UTC (2:25 PM)
        assert dt.hour == 14

    def test_map_missing_sunrise_sunset(self, mapper):
        """Test handling response without sunrise/sunset."""
        response = {
            "latitude": 39.9663,
            "longitude": -74.8103,
            "utc_offset_seconds": -18000,
            "current_units": {"temperature_2m": "°F"},
            "current": {"time": "2025-11-11T09:25", "temperature_2m": 55.4},
            # No daily data
        }

        result = mapper.map_current_conditions(response)

        props = result["properties"]
        assert props["sunrise"] is None
        assert props["sunset"] is None

    def test_map_empty_daily_sunrise_sunset(self, mapper):
        """Test handling empty sunrise/sunset arrays."""
        response = {
            "latitude": 39.9663,
            "longitude": -74.8103,
            "utc_offset_seconds": -18000,
            "current_units": {"temperature_2m": "°F"},
            "current": {"time": "2025-11-11T09:25", "temperature_2m": 55.4},
            "daily": {
                "time": [],
                "sunrise": [],
                "sunset": [],
            },
        }

        result = mapper.map_current_conditions(response)

        props = result["properties"]
        assert props["sunrise"] is None
        assert props["sunset"] is None


class TestOpenMeteoMapperForecast:
    """Test mapping Open-Meteo forecast responses."""

    @pytest.fixture
    def mapper(self):
        """Create mapper instance."""
        return OpenMeteoMapper()

    @pytest.fixture
    def sample_forecast_response(self):
        """Sample Open-Meteo forecast API response."""
        return {
            "latitude": 39.9663,
            "longitude": -74.8103,
            "utc_offset_seconds": -18000,
            "timezone": "America/New_York",
            "daily_units": {
                "time": "iso8601",
                "weather_code": "wmo code",
                "temperature_2m_max": "°F",
                "temperature_2m_min": "°F",
            },
            "daily": {
                "time": ["2025-11-11", "2025-11-12", "2025-11-13"],
                "weather_code": [2, 3, 1],
                "temperature_2m_max": [62.0, 58.0, 65.0],
                "temperature_2m_min": [45.0, 42.0, 48.0],
            },
        }

    def test_map_forecast_basic(self, mapper, sample_forecast_response):
        """Test basic forecast mapping."""
        result = mapper.map_forecast(sample_forecast_response)

        assert result is not None
        assert "properties" in result
        props = result["properties"]

        assert "periods" in props
        periods = props["periods"]
        # Each day creates 2 periods (day + night), but some may be missing data
        assert len(periods) >= 2
        assert len(periods) <= 6  # 3 days * 2 periods max

    def test_map_forecast_period_times_converted(self, mapper, sample_forecast_response):
        """Test that forecast period start/end times are converted to UTC."""
        result = mapper.map_forecast(sample_forecast_response)

        periods = result["properties"]["periods"]
        first_period = periods[0]

        # Start and end times should be converted to UTC
        assert "startTime" in first_period
        assert "endTime" in first_period

        # Should have timezone info
        start = first_period["startTime"]
        assert start is not None
        assert "+" in start or "Z" in start


class TestOpenMeteoMapperHourlyForecast:
    """Test mapping Open-Meteo hourly forecast responses."""

    @pytest.fixture
    def mapper(self):
        """Create mapper instance."""
        return OpenMeteoMapper()

    @pytest.fixture
    def sample_hourly_response(self):
        """Sample Open-Meteo hourly forecast API response."""
        return {
            "latitude": 39.9663,
            "longitude": -74.8103,
            "utc_offset_seconds": -18000,
            "timezone": "America/New_York",
            "hourly_units": {
                "time": "iso8601",
                "temperature_2m": "°F",
                "weather_code": "wmo code",
                "wind_speed_10m": "mph",
            },
            "hourly": {
                "time": [
                    "2025-11-11T10:00",
                    "2025-11-11T11:00",
                    "2025-11-11T12:00",
                ],
                "temperature_2m": [55.0, 57.0, 59.0],
                "weather_code": [2, 2, 1],
                "wind_speed_10m": [8.5, 9.0, 7.5],
            },
        }

    def test_map_hourly_forecast_basic(self, mapper, sample_hourly_response):
        """Test basic hourly forecast mapping."""
        result = mapper.map_hourly_forecast(sample_hourly_response)

        assert result is not None
        assert "properties" in result
        props = result["properties"]

        assert "periods" in props
        periods = props["periods"]
        assert len(periods) == 3

    def test_map_hourly_period_times_converted(self, mapper, sample_hourly_response):
        """Test that hourly period times are converted to UTC."""
        result = mapper.map_hourly_forecast(sample_hourly_response)

        periods = result["properties"]["periods"]
        first_period = periods[0]

        # Start time should be converted to UTC
        assert "startTime" in first_period
        start = first_period["startTime"]

        assert start is not None
        assert "+" in start or "Z" in start

        # Parse and verify conversion
        # 10:00 AM EST = 15:00 UTC (3:00 PM)
        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        assert dt.hour == 15


class TestTimezoneHandlingIntegration:
    """Integration tests for timezone handling across the mapper."""

    @pytest.fixture
    def mapper(self):
        """Create mapper instance."""
        return OpenMeteoMapper()

    def test_sunrise_sunset_stay_local_time(self, mapper):
        """Test that sunrise/sunset times remain in local time, not UTC."""
        response = {
            "latitude": 39.9663,
            "longitude": -74.8103,
            "utc_offset_seconds": -18000,  # EST = UTC-5
            "timezone": "America/New_York",
            "current_units": {"temperature_2m": "°F"},
            "current": {"time": "2025-11-11T09:25", "temperature_2m": 55.0},
            "daily": {
                "time": ["2025-11-11"],
                "sunrise": ["2025-11-11T06:40"],  # 6:40 AM local
                "sunset": ["2025-11-11T16:46"],  # 4:46 PM local
                "uv_index_max": [3.0],
            },
        }

        result = mapper.map_current_conditions(response)
        props = result["properties"]

        # Sunrise/sunset should be in local time (not converted)
        assert props["sunrise"] == "2025-11-11T06:40"
        assert props["sunset"] == "2025-11-11T16:46"

        # These should display as 6:40 AM and 4:46 PM, not 1:40 AM and 11:46 AM

    def test_timestamp_converts_to_utc(self, mapper):
        """Test that current timestamp converts from local to UTC."""
        response = {
            "latitude": 39.9663,
            "longitude": -74.8103,
            "utc_offset_seconds": -18000,  # EST = UTC-5
            "timezone": "America/New_York",
            "current_units": {"temperature_2m": "°F"},
            "current": {
                "time": "2025-11-11T09:25",  # 9:25 AM local
                "temperature_2m": 55.0,
            },
        }

        result = mapper.map_current_conditions(response)
        props = result["properties"]

        timestamp = props["timestamp"]

        # Should be converted to UTC
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert dt.tzinfo is not None

        # 9:25 AM EST should become 14:25 UTC
        assert dt.hour == 14
        assert dt.minute == 25

    def test_different_timezone_offsets(self, mapper):
        """Test handling different timezone offsets."""
        # Test with PST (UTC-8)
        response = {
            "latitude": 37.7749,
            "longitude": -122.4194,
            "utc_offset_seconds": -28800,  # PST = UTC-8
            "timezone": "America/Los_Angeles",
            "current_units": {"temperature_2m": "°F"},
            "current": {
                "time": "2025-11-11T06:00",  # 6:00 AM PST
                "temperature_2m": 52.0,
            },
            "daily": {
                "time": ["2025-11-11"],
                "sunrise": ["2025-11-11T06:30"],  # Local time
                "sunset": ["2025-11-11T17:00"],  # Local time
            },
        }

        result = mapper.map_current_conditions(response)
        props = result["properties"]

        # Sunrise/sunset stay in local time
        assert props["sunrise"] == "2025-11-11T06:30"
        assert props["sunset"] == "2025-11-11T17:00"

        # Timestamp converts to UTC
        timestamp = props["timestamp"]
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        # 6:00 AM PST = 14:00 UTC (2:00 PM)
        assert dt.hour == 14
