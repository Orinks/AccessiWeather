"""
Tests for utility modules.

Tests various utility functions used throughout the application.
"""

from __future__ import annotations

import pytest


class TestRetryUtils:
    """Tests for retry utilities."""

    def test_retry_decorator_exists(self):
        """Verify retry decorator can be imported."""
        from accessiweather.utils.retry import retry_with_backoff

        assert callable(retry_with_backoff)

    def test_api_timeout_error(self):
        """Test APITimeoutError exception."""
        from accessiweather.utils.retry import APITimeoutError

        with pytest.raises(APITimeoutError):
            raise APITimeoutError("Test timeout")


class TestTemperatureUtils:
    """Tests for temperature utilities."""

    def test_calculate_dewpoint(self):
        """Test dewpoint calculation."""
        from accessiweather.utils.temperature_utils import (
            TemperatureUnit,
            calculate_dewpoint,
        )

        # At 72°F and 65% humidity, dewpoint is approximately 58-60°F
        dewpoint = calculate_dewpoint(72.0, 65, unit=TemperatureUnit.FAHRENHEIT)
        assert dewpoint is not None
        assert 55 < dewpoint < 65

    def test_calculate_dewpoint_celsius(self):
        """Test dewpoint calculation in Celsius."""
        from accessiweather.utils.temperature_utils import (
            TemperatureUnit,
            calculate_dewpoint,
        )

        # At 22°C and 65% humidity
        dewpoint = calculate_dewpoint(22.0, 65, unit=TemperatureUnit.CELSIUS)
        assert dewpoint is not None
        assert 12 < dewpoint < 18

    def test_calculate_dewpoint_invalid(self):
        """Test dewpoint with invalid inputs."""
        from accessiweather.utils.temperature_utils import (
            TemperatureUnit,
            calculate_dewpoint,
        )

        assert calculate_dewpoint(None, 65, unit=TemperatureUnit.FAHRENHEIT) is None
        assert calculate_dewpoint(72.0, None, unit=TemperatureUnit.FAHRENHEIT) is None


class TestFormatStringParser:
    """Tests for format string parsing."""

    def test_parser_import(self):
        """Verify format string parser can be imported."""
        from accessiweather.format_string_parser import FormatStringParser

        assert FormatStringParser is not None

    def test_basic_parsing(self):
        """Test basic format string parsing."""
        from accessiweather.format_string_parser import FormatStringParser

        parser = FormatStringParser()
        # Test format_string method with placeholder substitution
        result = parser.format_string("Temperature: {temp}°F", {"temp": "72"})
        assert result == "Temperature: 72°F"


class TestConstants:
    """Tests for application constants."""

    def test_severity_priority_map(self):
        """Test severity priority mapping."""
        from accessiweather.constants import SEVERITY_PRIORITY_MAP

        assert SEVERITY_PRIORITY_MAP["extreme"] == 5
        assert SEVERITY_PRIORITY_MAP["severe"] == 4
        assert SEVERITY_PRIORITY_MAP["moderate"] == 3
        assert SEVERITY_PRIORITY_MAP["minor"] == 2
        assert SEVERITY_PRIORITY_MAP["unknown"] == 1

    def test_alert_constants(self):
        """Test alert-related constants."""
        from accessiweather.constants import (
            ALERT_HISTORY_MAX_LENGTH,
            DEFAULT_GLOBAL_COOLDOWN_MINUTES,
            DEFAULT_MAX_NOTIFICATIONS_PER_HOUR,
        )

        assert ALERT_HISTORY_MAX_LENGTH > 0
        assert DEFAULT_GLOBAL_COOLDOWN_MINUTES >= 0
        assert DEFAULT_MAX_NOTIFICATIONS_PER_HOUR > 0
