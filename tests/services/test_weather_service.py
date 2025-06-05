"""Tests for the WeatherService class."""

import time
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.services.weather_service import WeatherService

# Sample test data
SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "temperature": 75,
                "temperatureUnit": "F",
                "shortForecast": "Sunny",
                "detailedForecast": "Sunny with a high near 75.",
            }
        ]
    }
}

SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "properties": {
                "headline": "Test Alert",
                "description": "Test Description",
                "instruction": "Test Instruction",
                "severity": "Moderate",
                "event": "Test Event",
            }
        }
    ]
}

SAMPLE_DISCUSSION_TEXT = """
This is a sample forecast discussion.
Multiple lines of text.
With weather information.
"""

SAMPLE_NATIONAL_DISCUSSION_DATA = {
    "wpc": {
        "short_range_summary": "WPC Short Range Summary",
        "short_range_full": "WPC Full Discussion",
    },
    "spc": {"day1_summary": "SPC Day 1 Summary", "day1_full": "SPC Full Discussion"},
    "attribution": "Data from NOAA/NWS",
}


# Fixture to create a mocked NoaaApiClient
@pytest.fixture
def mock_api_client():
    client = MagicMock(spec=NoaaApiClient)
    # Set default return values
    client.get_forecast.return_value = SAMPLE_FORECAST_DATA
    client.get_alerts.return_value = SAMPLE_ALERTS_DATA
    client.get_discussion.return_value = SAMPLE_DISCUSSION_TEXT
    client.get_national_discussion_summary.return_value = {
        "wpc": {"short_range_summary": "WPC Summary"},
        "spc": {"day1_summary": "SPC Summary"},
    }
    return client


# Fixture to create a WeatherService instance with the mocked client
@pytest.fixture
def weather_service(mock_api_client):
    return WeatherService(mock_api_client)


def test_get_forecast_success(weather_service, mock_api_client):
    """Test getting forecast data successfully."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_forecast(lat, lon)

    assert result == SAMPLE_FORECAST_DATA
    mock_api_client.get_forecast.assert_called_once_with(lat, lon, force_refresh=False)


def test_get_forecast_with_force_refresh(weather_service, mock_api_client):
    """Test getting forecast data with force_refresh=True."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_forecast(lat, lon, force_refresh=True)

    assert result == SAMPLE_FORECAST_DATA
    mock_api_client.get_forecast.assert_called_once_with(lat, lon, force_refresh=True)


def test_get_forecast_error(weather_service, mock_api_client):
    """Test getting forecast data when API client raises an error."""
    lat, lon = 40.0, -75.0
    mock_api_client.get_forecast.side_effect = Exception("API Error")

    # Also mock the OpenMeteo client to fail so fallback doesn't work
    with patch.object(weather_service.openmeteo_client, "get_forecast") as mock_openmeteo:
        mock_openmeteo.side_effect = Exception("OpenMeteo Error")

        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_forecast(lat, lon)

        assert "NWS failed and Open-Meteo fallback failed" in str(exc_info.value)
        mock_api_client.get_forecast.assert_called_once_with(lat, lon, force_refresh=False)


def test_get_alerts_success(weather_service, mock_api_client):
    """Test getting alerts data successfully."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_alerts(lat, lon)

    assert result == SAMPLE_ALERTS_DATA
    mock_api_client.get_alerts.assert_called_once_with(
        lat, lon, radius=50, precise_location=True, force_refresh=False
    )


def test_get_alerts_with_force_refresh(weather_service, mock_api_client):
    """Test getting alerts data with force_refresh=True."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_alerts(lat, lon, force_refresh=True)

    assert result == SAMPLE_ALERTS_DATA
    mock_api_client.get_alerts.assert_called_once_with(
        lat, lon, radius=50, precise_location=True, force_refresh=True
    )


def test_get_alerts_error(weather_service, mock_api_client):
    """Test getting alerts data when API client raises an error."""
    lat, lon = 40.0, -75.0
    mock_api_client.get_alerts.side_effect = Exception("API Error")

    with pytest.raises(ApiClientError) as exc_info:
        weather_service.get_alerts(lat, lon)

    assert "Unable to retrieve alerts data" in str(exc_info.value)
    mock_api_client.get_alerts.assert_called_once()


def test_get_discussion_success(weather_service, mock_api_client):
    """Test getting discussion data successfully."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_discussion(lat, lon)

    assert result == SAMPLE_DISCUSSION_TEXT
    mock_api_client.get_discussion.assert_called_once_with(lat, lon, force_refresh=False)


def test_get_discussion_with_force_refresh(weather_service, mock_api_client):
    """Test getting discussion data with force_refresh=True."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_discussion(lat, lon, force_refresh=True)

    assert result == SAMPLE_DISCUSSION_TEXT
    mock_api_client.get_discussion.assert_called_once_with(lat, lon, force_refresh=True)


def test_get_discussion_error(weather_service, mock_api_client):
    """Test getting discussion data when API client raises an error."""
    lat, lon = 40.0, -75.0
    mock_api_client.get_discussion.side_effect = Exception("API Error")

    with pytest.raises(ApiClientError) as exc_info:
        weather_service.get_discussion(lat, lon)

    assert "Unable to retrieve forecast discussion data" in str(exc_info.value)
    mock_api_client.get_discussion.assert_called_once()


def test_get_national_forecast_data_success(weather_service):
    """Test getting national forecast data successfully."""
    # Mock the NationalDiscussionScraper.fetch_all_discussions method
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.return_value = SAMPLE_NATIONAL_DISCUSSION_DATA

        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()

        # Verify cache was updated
        assert weather_service.national_data_cache == SAMPLE_NATIONAL_DISCUSSION_DATA
        assert weather_service.national_data_timestamp > 0


def test_get_national_forecast_data_with_cache(weather_service):
    """Test getting national forecast data from cache."""
    # Set up cache
    weather_service.national_data_cache = SAMPLE_NATIONAL_DISCUSSION_DATA
    weather_service.national_data_timestamp = time.time()

    # Mock the scraper to verify it's not called
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_not_called()


def test_get_national_forecast_data_with_force_refresh(weather_service):
    """Test getting national forecast data with force_refresh=True."""
    # Set up cache
    weather_service.national_data_cache = {"old": "data"}
    weather_service.national_data_timestamp = time.time()

    # Mock the scraper
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.return_value = SAMPLE_NATIONAL_DISCUSSION_DATA

        result = weather_service.get_national_forecast_data(force_refresh=True)

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()

        # Verify cache was updated
        assert weather_service.national_data_cache == SAMPLE_NATIONAL_DISCUSSION_DATA


def test_get_national_forecast_data_with_expired_cache(weather_service):
    """Test getting national forecast data with expired cache."""
    # Set up expired cache (timestamp from 2 hours ago)
    weather_service.national_data_cache = {"old": "data"}
    weather_service.national_data_timestamp = time.time() - 7200  # 2 hours ago

    # Mock the scraper
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.return_value = SAMPLE_NATIONAL_DISCUSSION_DATA

        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()

        # Verify cache was updated
        assert weather_service.national_data_cache == SAMPLE_NATIONAL_DISCUSSION_DATA


def test_get_national_forecast_data_error_no_cache(weather_service):
    """Test getting national forecast data when scraper raises an error and no cache exists."""
    # Ensure no cache
    weather_service.national_data_cache = None

    # Mock the scraper to raise an exception
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.side_effect = Exception("Scraper Error")

        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_national_forecast_data()

        assert "Unable to retrieve nationwide forecast data" in str(exc_info.value)
        mock_fetch.assert_called_once()


def test_get_national_forecast_data_error_with_cache(weather_service):
    """Test getting national forecast data when scraper raises an error but cache exists."""
    # Set up cache
    weather_service.national_data_cache = SAMPLE_NATIONAL_DISCUSSION_DATA
    weather_service.national_data_timestamp = time.time() - 7200  # Expired cache (2 hours ago)

    # Mock the scraper to raise an exception
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.side_effect = Exception("Scraper Error")

        # Should return cached data even though it's expired
        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()


def test_process_alerts(weather_service):
    """Test processing alerts data."""
    alerts_data = {
        "features": [
            {
                "id": "alert1",
                "properties": {
                    "headline": "Test Alert 1",
                    "description": "Description 1",
                    "instruction": "Instruction 1",
                    "severity": "Moderate",
                    "event": "Test Event 1",
                    "effective": "2024-01-01T00:00:00Z",
                    "expires": "2024-01-02T00:00:00Z",
                    "status": "Actual",
                    "messageType": "Alert",
                    "areaDesc": "Test Area 1",
                },
            },
            {
                "id": "alert2",
                "properties": {
                    "headline": "Test Alert 2",
                    "description": "Description 2",
                    "instruction": "Instruction 2",
                    "severity": "Severe",
                    "event": "Test Event 2",
                    "effective": "2024-01-01T00:00:00Z",
                    "expires": "2024-01-02T00:00:00Z",
                    "status": "Actual",
                    "messageType": "Alert",
                    "areaDesc": "Test Area 2",
                },
            },
        ]
    }

    processed_alerts, new_count, updated_count = weather_service.process_alerts(alerts_data)

    assert len(processed_alerts) == 2
    assert new_count == 2  # Both alerts are new
    assert updated_count == 0  # No alerts were updated
    assert processed_alerts[0]["headline"] == "Test Alert 1"
    assert processed_alerts[0]["severity"] == "Moderate"
    assert processed_alerts[1]["headline"] == "Test Alert 2"
    assert processed_alerts[1]["severity"] == "Severe"


def test_process_alerts_empty(weather_service):
    """Test processing empty alerts data."""
    alerts_data: dict = {"features": []}

    processed_alerts, new_count, updated_count = weather_service.process_alerts(alerts_data)

    assert len(processed_alerts) == 0
    assert new_count == 0
    assert updated_count == 0


def test_process_alerts_missing_properties(weather_service):
    """Test processing alerts data with missing properties."""
    alerts_data = {
        "features": [
            {
                "id": "alert1",
                "properties": {
                    # Missing most properties
                    "headline": "Test Alert"
                },
            }
        ]
    }

    processed_alerts, new_count, updated_count = weather_service.process_alerts(alerts_data)

    assert len(processed_alerts) == 1
    assert new_count == 1
    assert updated_count == 0
    assert processed_alerts[0]["headline"] == "Test Alert"
    # Check default values for missing properties
    assert processed_alerts[0]["description"] == "No description available"
    assert processed_alerts[0]["instruction"] == ""
    assert processed_alerts[0]["severity"] == "Unknown"
    assert processed_alerts[0]["event"] == "Unknown Event"


@pytest.mark.unit
def test_weather_service_initialization_with_config():
    """Test WeatherService initialization with different configurations."""
    config = {
        "settings": {"data_source": "nws"},
        "api_settings": {"api_contact": "test@example.com"},
    }

    mock_nws_client = MagicMock()
    service = WeatherService(nws_client=mock_nws_client, config=config)

    assert service.config == config
    assert service.nws_client == mock_nws_client
    assert service.openmeteo_client is not None


@pytest.mark.unit
def test_weather_service_initialization_with_clients():
    """Test WeatherService initialization with provided clients."""
    mock_nws_client = MagicMock()
    mock_openmeteo_client = MagicMock()

    service = WeatherService(nws_client=mock_nws_client, openmeteo_client=mock_openmeteo_client)

    assert service.nws_client == mock_nws_client
    assert service.openmeteo_client == mock_openmeteo_client


@pytest.mark.unit
def test_should_use_openmeteo_us_location(weather_service):
    """Test that NWS is preferred for US locations."""
    # Set the data source to auto for this test
    weather_service.config = {"settings": {"data_source": "auto"}}

    # US coordinates (New York)
    lat, lon = 40.7128, -74.0060

    # Mock the geocoding service to return True for US location
    with patch("accessiweather.geocoding.GeocodingService") as mock_geocoding_class:
        mock_geocoding_instance = mock_geocoding_class.return_value
        mock_geocoding_instance.validate_coordinates.return_value = True

        result = weather_service._should_use_openmeteo(lat, lon)

    assert result is False


@pytest.mark.unit
def test_should_use_openmeteo_non_us_location(weather_service):
    """Test that Open-Meteo is used for non-US locations."""
    # Set the data source to auto for this test
    weather_service.config = {"settings": {"data_source": "auto"}}

    # London coordinates
    lat, lon = 51.5074, -0.1278

    # Mock the geocoding service to return False for non-US location
    with patch("accessiweather.geocoding.GeocodingService") as mock_geocoding_class:
        mock_geocoding_instance = mock_geocoding_class.return_value
        mock_geocoding_instance.validate_coordinates.return_value = False

        result = weather_service._should_use_openmeteo(lat, lon)

    assert result is True


@pytest.mark.unit
def test_should_use_openmeteo_edge_cases(weather_service):
    """Test edge cases for location detection."""
    # Set the data source to auto for this test
    weather_service.config = {"settings": {"data_source": "auto"}}

    # Test coordinates at US borders
    test_cases = [
        (49.0, -125.0, True),  # Canada (north of US)
        (25.0, -80.0, False),  # Florida (US)
        (32.0, -117.0, False),  # California (US)
        (19.0, -155.0, False),  # Hawaii (US)
        (64.0, -153.0, False),  # Alaska (US)
    ]

    # Mock the geocoding service to return appropriate values
    with patch("accessiweather.geocoding.GeocodingService") as mock_geocoding_class:
        mock_geocoding_instance = mock_geocoding_class.return_value

        for lat, lon, expected in test_cases:
            # Set the mock to return False for non-US (expected=True) and True for US (expected=False)
            mock_geocoding_instance.validate_coordinates.return_value = not expected

            result = weather_service._should_use_openmeteo(lat, lon)
            assert result == expected, f"Failed for coordinates ({lat}, {lon})"


@pytest.mark.unit
def test_get_forecast_nws_success(weather_service):
    """Test successful forecast retrieval using NWS."""
    lat, lon = 40.0, -75.0

    with patch.object(weather_service, "_should_use_openmeteo", return_value=False):
        with patch.object(
            weather_service.nws_client, "get_forecast", return_value=SAMPLE_FORECAST_DATA
        ):
            result = weather_service.get_forecast(lat, lon)

            assert result == SAMPLE_FORECAST_DATA
            weather_service.nws_client.get_forecast.assert_called_once_with(
                lat, lon, force_refresh=False
            )


@pytest.mark.unit
def test_get_forecast_openmeteo_success(weather_service):
    """Test successful forecast retrieval using Open-Meteo."""
    lat, lon = 51.5074, -0.1278  # London

    with patch.object(weather_service, "_should_use_openmeteo", return_value=True):
        with patch.object(
            weather_service.openmeteo_client, "get_forecast", return_value={"test": "data"}
        ):
            with patch.object(
                weather_service.openmeteo_mapper, "map_forecast", return_value=SAMPLE_FORECAST_DATA
            ):
                result = weather_service.get_forecast(lat, lon)

                assert result == SAMPLE_FORECAST_DATA
                weather_service.openmeteo_client.get_forecast.assert_called_once()
                weather_service.openmeteo_mapper.map_forecast.assert_called_once()


@pytest.mark.unit
def test_get_hourly_forecast_nws_success(weather_service):
    """Test successful hourly forecast retrieval using NWS."""
    lat, lon = 40.0, -75.0

    with patch.object(weather_service, "_should_use_openmeteo", return_value=False):
        with patch.object(
            weather_service.nws_client, "get_hourly_forecast", return_value=SAMPLE_FORECAST_DATA
        ):
            result = weather_service.get_hourly_forecast(lat, lon)

            assert result == SAMPLE_FORECAST_DATA
            weather_service.nws_client.get_hourly_forecast.assert_called_once_with(
                lat, lon, force_refresh=False
            )


@pytest.mark.unit
def test_get_hourly_forecast_openmeteo_success(weather_service):
    """Test successful hourly forecast retrieval using Open-Meteo."""
    lat, lon = 51.5074, -0.1278  # London

    with patch.object(weather_service, "_should_use_openmeteo", return_value=True):
        with patch.object(
            weather_service.openmeteo_client, "get_hourly_forecast", return_value={"test": "data"}
        ):
            with patch.object(
                weather_service.openmeteo_mapper,
                "map_hourly_forecast",
                return_value=SAMPLE_FORECAST_DATA,
            ):
                result = weather_service.get_hourly_forecast(lat, lon)

                assert result == SAMPLE_FORECAST_DATA
                weather_service.openmeteo_client.get_hourly_forecast.assert_called_once()
                weather_service.openmeteo_mapper.map_hourly_forecast.assert_called_once()


@pytest.mark.unit
def test_get_current_conditions_nws_success(weather_service):
    """Test successful current conditions retrieval using NWS."""
    lat, lon = 40.0, -75.0

    with patch.object(weather_service, "_should_use_openmeteo", return_value=False):
        with patch.object(
            weather_service.nws_client, "get_current_conditions", return_value=SAMPLE_FORECAST_DATA
        ):
            result = weather_service.get_current_conditions(lat, lon)

            assert result == SAMPLE_FORECAST_DATA
            weather_service.nws_client.get_current_conditions.assert_called_once_with(
                lat, lon, force_refresh=False
            )


@pytest.mark.unit
def test_get_current_conditions_openmeteo_success(weather_service):
    """Test successful current conditions retrieval using Open-Meteo."""
    lat, lon = 51.5074, -0.1278  # London

    with patch.object(weather_service, "_should_use_openmeteo", return_value=True):
        with patch.object(
            weather_service.openmeteo_client, "get_current_weather", return_value={"test": "data"}
        ):
            with patch.object(
                weather_service.openmeteo_mapper,
                "map_current_conditions",
                return_value=SAMPLE_FORECAST_DATA,
            ):
                result = weather_service.get_current_conditions(lat, lon)

                assert result == SAMPLE_FORECAST_DATA
                weather_service.openmeteo_client.get_current_weather.assert_called_once()
                weather_service.openmeteo_mapper.map_current_conditions.assert_called_once()


@pytest.mark.unit
def test_get_temperature_unit_preference_celsius(weather_service):
    """Test getting temperature unit preference for Celsius."""
    weather_service.config = {"settings": {"temperature_unit": "celsius"}}

    result = weather_service._get_temperature_unit_preference()
    assert result == "celsius"


@pytest.mark.unit
def test_get_temperature_unit_preference_fahrenheit(weather_service):
    """Test getting temperature unit preference for Fahrenheit."""
    weather_service.config = {"settings": {"temperature_unit": "fahrenheit"}}

    result = weather_service._get_temperature_unit_preference()
    assert result == "fahrenheit"


@pytest.mark.unit
def test_get_temperature_unit_preference_both(weather_service):
    """Test getting temperature unit preference for both (defaults to fahrenheit)."""
    weather_service.config = {"settings": {"temperature_unit": "both"}}

    result = weather_service._get_temperature_unit_preference()
    assert result == "fahrenheit"


@pytest.mark.unit
def test_get_data_source_nws(weather_service):
    """Test getting data source configuration for NWS."""
    weather_service.config = {"settings": {"data_source": "nws"}}

    result = weather_service._get_data_source()
    assert result == "nws"


@pytest.mark.unit
def test_get_data_source_auto(weather_service):
    """Test getting data source configuration for auto."""
    weather_service.config = {"settings": {"data_source": "auto"}}

    result = weather_service._get_data_source()
    assert result == "auto"


@pytest.mark.unit
def test_get_data_source_default(weather_service):
    """Test getting data source configuration with default."""
    weather_service.config = {"settings": {}}

    result = weather_service._get_data_source()
    assert result == "nws"
