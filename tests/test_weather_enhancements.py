from unittest.mock import AsyncMock, patch

import pytest

from accessiweather.models import (
    CurrentConditions,
    Forecast,
    HourlyForecast,
    HydrologicalData,
    Location,
    MarineForecast,
    SolarData,
    WeatherAlerts,
    WeatherData,
)
from accessiweather.weather_client import WeatherClient


@pytest.mark.asyncio
async def test_weather_client_full_data_structure():
    """Test that WeatherClient correctly assembles all new data types when using 'auto' source."""
    client = WeatherClient(data_source="auto")
    location = Location(
        name="Test Loc", latitude=30, longitude=-90, country_code="US"
    )  # US location

    # Mock data objects
    mock_hydrological = HydrologicalData(
        river_discharge=100.0, river_stage=5.0, flood_category="Minor"
    )
    mock_marine = MarineForecast(
        wave_height_ft=3.5, water_temperature_f=65.0, small_craft_advisory=True
    )
    mock_solar = SolarData(solar_radiation=800.0, solar_energy=25.0)

    mock_current = CurrentConditions(temperature_f=70)
    mock_forecast = Forecast(periods=[])
    mock_hourly = HourlyForecast(periods=[])
    mock_alerts = WeatherAlerts(alerts=[])
    mock_discussion = "Test discussion"

    # We mock the internal _fetch_* methods that _fetch_smart_auto_source calls.
    # Note: _fetch_smart_auto_source defines internal coroutines like fetch_nws, fetch_openmeteo
    # which call self._fetch_nws_data, self._fetch_openmeteo_data.

    # Mock return value for _fetch_nws_data (triggers on US location)
    # Returns (current, forecast, discussion, alerts, hourly, marine)
    nws_return = (
        mock_current,
        mock_forecast,
        mock_discussion,
        mock_alerts,
        mock_hourly,
        mock_marine,
    )

    # Mock return value for _fetch_openmeteo_data (always called in auto mode)
    # Returns (current, forecast, hourly, hydrological)
    # Note: fusion engine will merge/prioritize, but we just want to ensure fields are present.
    om_return = (mock_current, mock_forecast, mock_hourly, mock_hydrological)

    # Mock Visual Crossing data
    # client.visual_crossing_client is initialized in __init__. We need to mock it.
    mock_vc_client = AsyncMock()
    mock_vc_client.get_current_conditions.return_value = mock_current
    mock_vc_client.get_forecast.return_value = mock_forecast
    mock_vc_client.get_hourly_forecast.return_value = mock_hourly
    mock_vc_client.get_alerts.return_value = mock_alerts
    mock_vc_client.get_solar_data.return_value = mock_solar

    client.visual_crossing_client = mock_vc_client

    with (
        patch.object(client, "_fetch_nws_data", return_value=nws_return),
        patch.object(client, "_fetch_openmeteo_data", return_value=om_return),
        patch.object(client, "_is_us_location", return_value=True),
    ):
        # force is_us_location to True so NWS is used
        data = await client.get_weather_data(location)

    # Verify that the returned WeatherData object has the new fields populated
    assert isinstance(data, WeatherData)

    # NWS provides Marine
    assert data.marine == mock_marine
    assert data.marine.has_data()

    # Open-Meteo provides Hydrological
    assert data.hydrological == mock_hydrological
    assert data.hydrological.has_data()

    # Visual Crossing provides Solar
    assert data.solar == mock_solar
    assert data.solar.has_data()

    # Verify basic data
    assert data.current.temperature_f == mock_current.temperature_f


@pytest.mark.asyncio
async def test_hydrological_data_model():
    data = HydrologicalData(river_discharge=100)
    assert data.has_data()

    data_empty = HydrologicalData()
    assert not data_empty.has_data()


@pytest.mark.asyncio
async def test_marine_data_model():
    data = MarineForecast(wave_height_ft=2.0)
    assert data.has_data()

    data_warning = MarineForecast(small_craft_advisory=True)
    assert data_warning.has_data()

    data_empty = MarineForecast()
    assert not data_empty.has_data()


@pytest.mark.asyncio
async def test_solar_data_model():
    data = SolarData(solar_radiation=500)
    assert data.has_data()

    data_empty = SolarData()
    assert not data_empty.has_data()
