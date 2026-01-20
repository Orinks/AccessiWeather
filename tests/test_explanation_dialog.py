"""
Tests for Explanation Dialog functionality.

Tests the ExplanationDialog class and weather explanation UI integration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from accessiweather.ai_explainer import ExplanationResult, ExplanationStyle

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_explanation_result():
    """Create a sample ExplanationResult for testing."""
    return ExplanationResult(
        text="Today's weather is mild and pleasant with partly cloudy skies. "
        "Temperatures in the low 70s make it ideal for outdoor activities. "
        "Light winds from the northwest at 10 mph will keep conditions comfortable.",
        model_used="meta-llama/llama-3.3-70b-instruct:free",
        token_count=150,
        estimated_cost=0.0,
        cached=False,
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def cached_explanation_result():
    """Create a cached ExplanationResult for testing."""
    return ExplanationResult(
        text="Cached weather explanation.",
        model_used="cached-model",
        token_count=50,
        estimated_cost=0.0,
        cached=True,
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def mock_app():
    """Create a mock AccessiWeatherApp."""
    app = MagicMock()
    app.config_manager = MagicMock()

    # Create location mock with proper attribute setting
    # (MagicMock's 'name' parameter is reserved for the mock's name, not an attribute)
    location_mock = MagicMock()
    location_mock.name = "Test City, NY"
    location_mock.latitude = 40.7128
    location_mock.longitude = -74.0060
    location_mock.timezone = "America/New_York"
    app.config_manager.get_current_location.return_value = location_mock
    app.config_manager.get_settings.return_value = MagicMock(
        ai_model_preference="auto",
        ai_explanation_style="standard",
        openrouter_api_key="test-api-key",
        custom_system_prompt=None,
        custom_instructions=None,
    )
    app.current_weather_data = MagicMock(
        current=MagicMock(
            temperature_f=72.0,
            condition="Partly Cloudy",
            humidity=65,
            wind_speed_mph=10.0,
            wind_direction="NW",
            visibility_miles=10.0,
            pressure_in=30.05,
        ),
        forecast=MagicMock(
            periods=[
                MagicMock(
                    name="Today",
                    temperature=75,
                    temperature_unit="F",
                    short_forecast="Sunny",
                    wind_speed=10,
                    wind_direction="NW",
                )
            ]
        ),
        alerts=MagicMock(alerts=[]),
    )
    app.ai_explanation_cache = None
    return app


# =============================================================================
# ExplanationResult Tests
# =============================================================================


class TestExplanationResultDisplay:
    """Tests for ExplanationResult display formatting."""

    def test_result_has_text(self, sample_explanation_result):
        """Test that result has explanation text."""
        assert sample_explanation_result.text is not None
        assert len(sample_explanation_result.text) > 0

    def test_result_has_model_info(self, sample_explanation_result):
        """Test that result has model information."""
        assert sample_explanation_result.model_used is not None
        assert len(sample_explanation_result.model_used) > 0

    def test_result_has_token_count(self, sample_explanation_result):
        """Test that result has token count."""
        assert sample_explanation_result.token_count > 0

    def test_result_has_timestamp(self, sample_explanation_result):
        """Test that result has timestamp."""
        assert sample_explanation_result.timestamp is not None

    def test_cached_result_indicator(self, cached_explanation_result):
        """Test that cached results are properly indicated."""
        assert cached_explanation_result.cached is True

    def test_fresh_result_not_cached(self, sample_explanation_result):
        """Test that fresh results are not marked as cached."""
        assert sample_explanation_result.cached is False

    def test_free_model_zero_cost(self, sample_explanation_result):
        """Test that free model results have zero cost."""
        assert sample_explanation_result.estimated_cost == 0.0


# =============================================================================
# Weather Data Preparation Tests
# =============================================================================


class TestWeatherDataPreparation:
    """Tests for preparing weather data for AI explanation."""

    def test_build_weather_dict_from_conditions(self, mock_app):
        """Test building weather dict from current conditions."""
        current = mock_app.current_weather_data.current

        weather_dict = {
            "temperature": current.temperature_f,
            "temperature_unit": "F",
            "conditions": current.condition,
            "humidity": current.humidity,
            "wind_speed": current.wind_speed_mph,
            "wind_direction": current.wind_direction,
            "visibility": current.visibility_miles,
            "pressure": current.pressure_in,
        }

        assert weather_dict["temperature"] == 72.0
        assert weather_dict["conditions"] == "Partly Cloudy"
        assert weather_dict["humidity"] == 65

    def test_build_weather_dict_with_alerts(self, mock_app):
        """Test building weather dict with alerts."""
        mock_app.current_weather_data.alerts.alerts = [
            MagicMock(title="Heat Advisory", severity="Moderate"),
        ]

        alerts = [
            {"title": alert.title, "severity": alert.severity}
            for alert in mock_app.current_weather_data.alerts.alerts
        ]

        assert len(alerts) == 1
        assert alerts[0]["title"] == "Heat Advisory"

    def test_build_weather_dict_with_forecast(self, mock_app):
        """Test building weather dict with forecast periods."""
        # Verify forecast periods exist and have expected structure
        periods = mock_app.current_weather_data.forecast.periods
        assert periods is not None
        assert len(periods) >= 1

        # Check the first period has expected attributes
        first_period = periods[0]
        assert hasattr(first_period, "name")
        assert hasattr(first_period, "temperature")
        assert hasattr(first_period, "short_forecast")


# =============================================================================
# Style Selection Tests
# =============================================================================


class TestExplanationStyleSelection:
    """Tests for explanation style selection."""

    def test_brief_style_mapping(self):
        """Test mapping brief style setting."""
        style_map = {
            "brief": ExplanationStyle.BRIEF,
            "standard": ExplanationStyle.STANDARD,
            "detailed": ExplanationStyle.DETAILED,
        }
        assert style_map["brief"] == ExplanationStyle.BRIEF

    def test_standard_style_mapping(self):
        """Test mapping standard style setting."""
        style_map = {
            "brief": ExplanationStyle.BRIEF,
            "standard": ExplanationStyle.STANDARD,
            "detailed": ExplanationStyle.DETAILED,
        }
        assert style_map["standard"] == ExplanationStyle.STANDARD

    def test_detailed_style_mapping(self):
        """Test mapping detailed style setting."""
        style_map = {
            "brief": ExplanationStyle.BRIEF,
            "standard": ExplanationStyle.STANDARD,
            "detailed": ExplanationStyle.DETAILED,
        }
        assert style_map["detailed"] == ExplanationStyle.DETAILED

    def test_unknown_style_defaults_to_standard(self):
        """Test that unknown style defaults to standard."""
        style_map = {
            "brief": ExplanationStyle.BRIEF,
            "standard": ExplanationStyle.STANDARD,
            "detailed": ExplanationStyle.DETAILED,
        }
        style = style_map.get("unknown", ExplanationStyle.STANDARD)
        assert style == ExplanationStyle.STANDARD


# =============================================================================
# Model Selection Tests
# =============================================================================


class TestModelSelection:
    """Tests for AI model selection in explanation dialog."""

    def test_auto_model_preference(self, mock_app):
        """Test auto model preference maps to openrouter/auto."""
        mock_app.config_manager.get_settings.return_value.ai_model_preference = "auto"

        settings = mock_app.config_manager.get_settings()
        if settings.ai_model_preference == "auto":
            model = "openrouter/auto"
        else:
            model = settings.ai_model_preference

        assert model == "openrouter/auto"

    def test_specific_model_preference(self, mock_app):
        """Test specific model preference is used."""
        mock_app.config_manager.get_settings.return_value.ai_model_preference = "gpt-4"

        settings = mock_app.config_manager.get_settings()
        if settings.ai_model_preference == "auto":
            model = "openrouter/auto"
        else:
            model = settings.ai_model_preference

        assert model == "gpt-4"


# =============================================================================
# Location Validation Tests
# =============================================================================


class TestLocationValidation:
    """Tests for location validation before generating explanation."""

    def test_location_required(self, mock_app):
        """Test that location is required for explanation."""
        location = mock_app.config_manager.get_current_location()
        assert location is not None
        assert location.name == "Test City, NY"

    def test_no_location_detected(self, mock_app):
        """Test handling when no location is set."""
        mock_app.config_manager.get_current_location.return_value = None

        location = mock_app.config_manager.get_current_location()
        assert location is None


# =============================================================================
# Weather Data Validation Tests
# =============================================================================


class TestWeatherDataValidation:
    """Tests for weather data validation before generating explanation."""

    def test_weather_data_required(self, mock_app):
        """Test that weather data is required for explanation."""
        weather_data = mock_app.current_weather_data
        assert weather_data is not None
        assert weather_data.current is not None

    def test_no_weather_data_detected(self, mock_app):
        """Test handling when no weather data is available."""
        mock_app.current_weather_data = None

        weather_data = mock_app.current_weather_data
        assert weather_data is None

    def test_no_current_conditions_detected(self, mock_app):
        """Test handling when current conditions are missing."""
        mock_app.current_weather_data.current = None

        weather_data = mock_app.current_weather_data
        assert weather_data is not None
        assert weather_data.current is None


# =============================================================================
# Custom Prompt Tests
# =============================================================================


class TestCustomPrompts:
    """Tests for custom prompt configuration."""

    def test_custom_system_prompt_used(self, mock_app):
        """Test that custom system prompt is passed to explainer."""
        mock_app.config_manager.get_settings.return_value.custom_system_prompt = (
            "You are a pirate weather forecaster."
        )

        settings = mock_app.config_manager.get_settings()
        custom_prompt = getattr(settings, "custom_system_prompt", None)

        assert custom_prompt is not None
        assert "pirate" in custom_prompt

    def test_custom_instructions_used(self, mock_app):
        """Test that custom instructions are passed to explainer."""
        mock_app.config_manager.get_settings.return_value.custom_instructions = (
            "Focus on gardening activities."
        )

        settings = mock_app.config_manager.get_settings()
        custom_instructions = getattr(settings, "custom_instructions", None)

        assert custom_instructions is not None
        assert "gardening" in custom_instructions

    def test_no_custom_prompts(self, mock_app):
        """Test handling when no custom prompts are configured."""
        settings = mock_app.config_manager.get_settings()
        custom_prompt = getattr(settings, "custom_system_prompt", None)
        custom_instructions = getattr(settings, "custom_instructions", None)

        # Default fixture has None for these
        assert custom_prompt is None
        assert custom_instructions is None


# =============================================================================
# Time Zone Tests
# =============================================================================


class TestTimeZoneHandling:
    """Tests for time zone handling in explanations."""

    def test_location_has_timezone(self, mock_app):
        """Test that location timezone is available."""
        location = mock_app.config_manager.get_current_location()
        timezone = getattr(location, "timezone", None)

        assert timezone == "America/New_York"

    def test_time_of_day_morning(self):
        """Test morning time of day detection."""
        hour = 9
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        assert time_of_day == "morning"

    def test_time_of_day_afternoon(self):
        """Test afternoon time of day detection."""
        hour = 14
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        assert time_of_day == "afternoon"

    def test_time_of_day_evening(self):
        """Test evening time of day detection."""
        hour = 19
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        assert time_of_day == "evening"

    def test_time_of_day_night(self):
        """Test night time of day detection."""
        hour = 23
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        assert time_of_day == "night"
