"""Tests for Open-Meteo weather model switching functionality."""

from unittest.mock import patch

import pytest

from accessiweather.openmeteo_client import OpenMeteoApiClient


class TestOpenMeteoModelSwitching:
    """Test suite for Open-Meteo weather model switching."""

    @pytest.fixture
    def client(self):
        """Create an OpenMeteoApiClient instance for testing."""
        return OpenMeteoApiClient(
            user_agent="TestClient",
            timeout=30.0,
            max_retries=0,
            retry_delay=0.0,
        )

    @pytest.fixture
    def mock_response(self):
        """Create a mock response for API calls."""
        return {
            "latitude": 40.0,
            "longitude": -75.0,
            "current": {
                "temperature_2m": 72.5,
                "weather_code": 1,
            },
            "daily": {
                "time": ["2024-01-01"],
                "temperature_2m_max": [75.0],
            },
            "hourly": {
                "time": ["2024-01-01T12:00"],
                "temperature_2m": [72.0],
            },
        }

    def test_get_current_weather_default_model(self, client, mock_response):
        """Test that default model (best_match) doesn't add models param."""
        with patch.object(client, "_make_request", return_value=mock_response) as mock_request:
            client.get_current_weather(40.0, -75.0)

            call_args = mock_request.call_args
            params = call_args[0][1]  # Second positional arg is params

            # Default model should not add 'models' parameter
            assert "models" not in params

    def test_get_current_weather_with_specific_model(self, client, mock_response):
        """Test that specifying a model adds the models param."""
        with patch.object(client, "_make_request", return_value=mock_response) as mock_request:
            client.get_current_weather(40.0, -75.0, model="icon_seamless")

            call_args = mock_request.call_args
            params = call_args[0][1]

            assert "models" in params
            assert params["models"] == "icon_seamless"

    def test_get_current_weather_best_match_explicit(self, client, mock_response):
        """Test that explicit best_match doesn't add models param."""
        with patch.object(client, "_make_request", return_value=mock_response) as mock_request:
            client.get_current_weather(40.0, -75.0, model="best_match")

            call_args = mock_request.call_args
            params = call_args[0][1]

            # best_match should not add 'models' parameter (it's the default)
            assert "models" not in params

    def test_get_forecast_default_model(self, client, mock_response):
        """Test forecast with default model."""
        with patch.object(client, "_make_request", return_value=mock_response) as mock_request:
            client.get_forecast(40.0, -75.0)

            call_args = mock_request.call_args
            params = call_args[0][1]

            assert "models" not in params

    def test_get_forecast_with_specific_model(self, client, mock_response):
        """Test forecast with specific model."""
        with patch.object(client, "_make_request", return_value=mock_response) as mock_request:
            client.get_forecast(40.0, -75.0, model="gfs_seamless")

            call_args = mock_request.call_args
            params = call_args[0][1]

            assert "models" in params
            assert params["models"] == "gfs_seamless"

    def test_get_hourly_forecast_default_model(self, client, mock_response):
        """Test hourly forecast with default model."""
        with patch.object(client, "_make_request", return_value=mock_response) as mock_request:
            client.get_hourly_forecast(40.0, -75.0)

            call_args = mock_request.call_args
            params = call_args[0][1]

            assert "models" not in params

    def test_get_hourly_forecast_with_specific_model(self, client, mock_response):
        """Test hourly forecast with specific model."""
        with patch.object(client, "_make_request", return_value=mock_response) as mock_request:
            client.get_hourly_forecast(40.0, -75.0, model="ecmwf_ifs04")

            call_args = mock_request.call_args
            params = call_args[0][1]

            assert "models" in params
            assert params["models"] == "ecmwf_ifs04"

    @pytest.mark.parametrize(
        "model",
        [
            "icon_seamless",
            "icon_global",
            "icon_eu",
            "icon_d2",
            "gfs_seamless",
            "gfs_global",
            "ecmwf_ifs04",
            "meteofrance_seamless",
            "gem_seamless",
            "jma_seamless",
        ],
    )
    def test_all_supported_models(self, client, mock_response, model):
        """Test that all supported models can be passed to API."""
        with patch.object(client, "_make_request", return_value=mock_response) as mock_request:
            client.get_current_weather(40.0, -75.0, model=model)

            call_args = mock_request.call_args
            params = call_args[0][1]

            assert "models" in params
            assert params["models"] == model


class TestOpenMeteoModelSettingsValidation:
    """Test model settings validation in AppSettings."""

    def test_valid_model_setting(self):
        """Test that valid models are accepted."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings(openmeteo_weather_model="icon_seamless")
        assert settings.openmeteo_weather_model == "icon_seamless"

    def test_default_model_setting(self):
        """Test that default model is best_match."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings()
        assert settings.openmeteo_weather_model == "best_match"

    def test_invalid_model_corrected_on_validation(self):
        """Test that invalid model is corrected to default on validation."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings(openmeteo_weather_model="invalid_model")
        settings.validate_on_access("openmeteo_weather_model")
        assert settings.openmeteo_weather_model == "best_match"

    def test_model_setting_serialization(self):
        """Test that model setting is properly serialized to dict."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings(openmeteo_weather_model="gfs_seamless")
        settings_dict = settings.to_dict()

        assert "openmeteo_weather_model" in settings_dict
        assert settings_dict["openmeteo_weather_model"] == "gfs_seamless"

    def test_model_setting_deserialization(self):
        """Test that model setting is properly deserialized from dict."""
        from accessiweather.models.config import AppSettings

        data = {"openmeteo_weather_model": "ecmwf_ifs04"}
        settings = AppSettings.from_dict(data)

        assert settings.openmeteo_weather_model == "ecmwf_ifs04"

    def test_model_setting_missing_uses_default(self):
        """Test that missing model setting uses default value."""
        from accessiweather.models.config import AppSettings

        data = {}  # No openmeteo_weather_model key
        settings = AppSettings.from_dict(data)

        assert settings.openmeteo_weather_model == "best_match"
