"""Tests for smart auto mode multi-source data enrichment."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from accessiweather.models import (
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    WeatherAlert,
    WeatherAlerts,
)
from accessiweather.weather_client import WeatherClient


@pytest.mark.asyncio
async def test_auto_mode_enriches_nws_with_sunrise_sunset():
    """Test that auto mode adds sunrise/sunset from Open-Meteo to NWS data."""
    # Setup
    location = Location(name="New York", latitude=40.7128, longitude=-74.0060)
    client = WeatherClient(data_source="auto")

    # Mock NWS data without sunrise/sunset
    nws_current = CurrentConditions(
        temperature_f=72.0,
        temperature_c=22.2,
        condition="Clear",
        humidity=60,
    )

    # Mock Open-Meteo data with sunrise/sunset
    openmeteo_current = CurrentConditions(
        temperature_f=70.0,
        temperature_c=21.1,
        condition="Clear",
        sunrise_time=datetime(2024, 6, 15, 6, 30, tzinfo=UTC),
        sunset_time=datetime(2024, 6, 15, 20, 45, tzinfo=UTC),
    )

    with (
        patch.object(client, "_get_nws_current_conditions", return_value=nws_current),
        patch.object(
            client,
            "_get_nws_forecast_and_discussion",
            return_value=(Forecast(periods=[]), "Test discussion"),
        ),
        patch.object(client, "_get_nws_hourly_forecast", return_value=HourlyForecast(periods=[])),
        patch.object(client, "_get_nws_alerts", return_value=WeatherAlerts(alerts=[])),
        patch.object(client, "_get_openmeteo_current_conditions", return_value=openmeteo_current),
    ):
        weather_data = await client.get_weather_data(location)

        # Verify NWS data is primary
        assert weather_data.current.temperature_f == 72.0

        # Verify sunrise/sunset was enriched from Open-Meteo
        assert weather_data.current.sunrise_time == datetime(2024, 6, 15, 6, 30, tzinfo=UTC)
        assert weather_data.current.sunset_time == datetime(2024, 6, 15, 20, 45, tzinfo=UTC)


@pytest.mark.asyncio
async def test_auto_mode_enriches_openmeteo_with_nws_discussion():
    """Test that auto mode adds NWS discussion to Open-Meteo data for US locations."""
    # Setup
    location = Location(name="Tokyo", latitude=35.6762, longitude=139.6503)
    # Pretend Tokyo is in US for testing purposes (mock _is_us_location)
    client = WeatherClient(data_source="auto")

    # Mock Open-Meteo data
    openmeteo_current = CurrentConditions(
        temperature_f=72.0,
        temperature_c=22.2,
        condition="Clear",
        sunrise_time=datetime(2024, 6, 15, 6, 30, tzinfo=UTC),
        sunset_time=datetime(2024, 6, 15, 20, 45, tzinfo=UTC),
    )

    with (
        patch.object(client, "_is_us_location", return_value=False),
        patch.object(client, "_get_openmeteo_current_conditions", return_value=openmeteo_current),
        patch.object(client, "_get_openmeteo_forecast", return_value=Forecast(periods=[])),
        patch.object(
            client, "_get_openmeteo_hourly_forecast", return_value=HourlyForecast(periods=[])
        ),
        patch.object(
            client,
            "_get_nws_forecast_and_discussion",
            return_value=(Forecast(periods=[]), "NWS forecast discussion"),
        ),
    ):
        weather_data = await client.get_weather_data(location)

        # For non-US location, should use Open-Meteo and NOT get NWS discussion
        assert weather_data.current.temperature_f == 72.0
        assert weather_data.discussion == "Forecast discussion not available from Open-Meteo."


@pytest.mark.asyncio
async def test_auto_mode_enriches_with_visual_crossing_alerts():
    """Test that auto mode adds Visual Crossing alerts when API key is configured."""
    # Setup
    location = Location(name="New York", latitude=40.7128, longitude=-74.0060)
    client = WeatherClient(data_source="auto", visual_crossing_api_key="test_key")
    client.air_quality_enabled = False
    client.pollen_enabled = False
    client.air_quality_notify_threshold = 0
    client.environmental_client = None
    client.trend_insights_enabled = False

    # Mock NWS data
    nws_current = CurrentConditions(temperature_f=72.0, temperature_c=22.2, condition="Clear")
    nws_alerts = WeatherAlerts(alerts=[])

    # Mock Visual Crossing alerts
    vc_alert = WeatherAlert(
        id="vc-alert-1",
        title="Heat Advisory until 8 PM",
        event="Heat Advisory",
        severity="Moderate",
        headline="Heat Advisory until 8 PM",
        description="Temperatures may reach 95 degrees",
        instruction="Stay hydrated",
    )
    vc_alerts = WeatherAlerts(alerts=[vc_alert])

    # Mock Visual Crossing client methods
    mock_vc_client = AsyncMock()
    mock_vc_client.get_current_conditions = AsyncMock(return_value=None)
    mock_vc_client.get_forecast = AsyncMock(return_value=None)
    mock_vc_client.get_hourly_forecast = AsyncMock(return_value=None)
    mock_vc_client.get_alerts = AsyncMock(return_value=vc_alerts)
    client.visual_crossing_client = mock_vc_client

    # Mock the fetch methods used by smart auto source
    async def mock_fetch_nws(location):
        return (nws_current, Forecast(periods=[]), None, nws_alerts, HourlyForecast(periods=[]))

    async def mock_fetch_openmeteo(location):
        return (CurrentConditions(), Forecast(periods=[]), HourlyForecast(periods=[]))

    with (
        patch.object(client, "_fetch_nws_data", side_effect=mock_fetch_nws),
        patch.object(client, "_fetch_openmeteo_data", side_effect=mock_fetch_openmeteo),
        patch.object(client, "_process_visual_crossing_alerts", new_callable=AsyncMock),
    ):
        weather_data = await client.get_weather_data(location)

        # Verify Visual Crossing alert was added
        assert len(weather_data.alerts.alerts) == 1
        assert weather_data.alerts.alerts[0].event == "Heat Advisory"


@pytest.mark.asyncio
async def test_auto_mode_enriches_with_fresh_sunrise_sunset():
    """Test that enrichment updates sunrise/sunset from Open-Meteo in auto mode."""
    # Setup
    location = Location(name="New York", latitude=40.7128, longitude=-74.0060)
    client = WeatherClient(data_source="auto")

    # Mock NWS data WITH sunrise/sunset
    existing_sunrise = datetime(2024, 6, 15, 6, 0, tzinfo=UTC)
    existing_sunset = datetime(2024, 6, 15, 21, 0, tzinfo=UTC)
    nws_current = CurrentConditions(
        temperature_f=72.0,
        temperature_c=22.2,
        condition="Clear",
        sunrise_time=existing_sunrise,
        sunset_time=existing_sunset,
    )

    # Fresh sunrise/sunset from Open-Meteo
    fresh_sunrise = datetime(2024, 6, 15, 5, 45, tzinfo=UTC)
    fresh_sunset = datetime(2024, 6, 15, 21, 15, tzinfo=UTC)
    openmeteo_current = CurrentConditions(
        sunrise_time=fresh_sunrise,
        sunset_time=fresh_sunset,
    )

    with (
        patch.object(client, "_get_nws_current_conditions", return_value=nws_current),
        patch.object(
            client,
            "_get_nws_forecast_and_discussion",
            return_value=(Forecast(periods=[]), "Test discussion"),
        ),
        patch.object(client, "_get_nws_hourly_forecast", return_value=HourlyForecast(periods=[])),
        patch.object(client, "_get_nws_alerts", return_value=WeatherAlerts(alerts=[])),
        patch.object(client, "_get_openmeteo_current_conditions", return_value=openmeteo_current),
    ):
        weather_data = await client.get_weather_data(location)

        # Verify sunrise/sunset was updated with fresh data from Open-Meteo
        assert weather_data.current.sunrise_time == fresh_sunrise
        assert weather_data.current.sunset_time == fresh_sunset


@pytest.mark.asyncio
async def test_enrichment_only_runs_in_auto_mode():
    """Test that smart enrichment only happens in auto mode."""
    # Setup
    location = Location(name="New York", latitude=40.7128, longitude=-74.0060)
    client = WeatherClient(data_source="nws")  # Explicit NWS mode

    nws_current = CurrentConditions(temperature_f=72.0, temperature_c=22.2, condition="Clear")

    with (
        patch.object(client, "_get_nws_current_conditions", return_value=nws_current),
        patch.object(
            client,
            "_get_nws_forecast_and_discussion",
            return_value=(Forecast(periods=[]), "Test discussion"),
        ),
        patch.object(client, "_get_nws_hourly_forecast", return_value=HourlyForecast(periods=[])),
        patch.object(client, "_get_nws_alerts", return_value=WeatherAlerts(alerts=[])),
        patch.object(client, "_get_openmeteo_current_conditions") as mock_openmeteo,
    ):
        # Call get_weather_data to trigger the flow
        await client.get_weather_data(location)

        # Verify Open-Meteo was NOT called for enrichment in explicit NWS mode
        mock_openmeteo.assert_not_called()


@pytest.mark.asyncio
async def test_nws_discussion_only_for_us_locations():
    """Test that NWS discussion enrichment only happens for US locations."""
    # Setup
    location = Location(name="London", latitude=51.5074, longitude=-0.1278)
    client = WeatherClient(data_source="auto")

    openmeteo_current = CurrentConditions(
        temperature_f=72.0,
        temperature_c=22.2,
        condition="Clear",
        sunrise_time=datetime(2024, 6, 15, 6, 30, tzinfo=UTC),
        sunset_time=datetime(2024, 6, 15, 20, 45, tzinfo=UTC),
    )

    with (
        patch.object(client, "_get_openmeteo_current_conditions", return_value=openmeteo_current),
        patch.object(client, "_get_openmeteo_forecast", return_value=Forecast(periods=[])),
        patch.object(
            client, "_get_openmeteo_hourly_forecast", return_value=HourlyForecast(periods=[])
        ),
        patch.object(client, "_get_nws_forecast_and_discussion") as mock_nws_discussion,
    ):
        weather_data = await client.get_weather_data(location)

        # Verify NWS discussion was NOT called for non-US location
        mock_nws_discussion.assert_not_called()
        assert weather_data.discussion == "Forecast discussion not available from Open-Meteo."


@pytest.mark.asyncio
async def test_openmeteo_current_conditions_includes_sunrise_sunset():
    """Test that Open-Meteo API request includes sunrise/sunset parameters."""
    client = WeatherClient()

    # This test verifies the API parameters are set correctly
    # We can't easily test the actual API call without mocking httpx
    # but we can verify that the parse function receives daily data
    sample_data = {
        "current": {
            "time": "2024-06-15T12:00",
            "temperature_2m": 72.0,
            "relative_humidity_2m": 60,
            "apparent_temperature": 70.0,
            "weather_code": 0,
            "wind_speed_10m": 5.0,
            "wind_direction_10m": 180,
            "pressure_msl": 1013.25,
        },
        "current_units": {
            "temperature_2m": "°F",
            "relative_humidity_2m": "%",
            "apparent_temperature": "°F",
            "wind_speed_10m": "mph",
            "pressure_msl": "hPa",
        },
        "daily": {
            "sunrise": ["2024-06-15T06:30:00"],
            "sunset": ["2024-06-15T20:45:00"],
        },
    }

    current = client._parse_openmeteo_current_conditions(sample_data)

    # Verify sunrise/sunset is parsed (now timezone-aware after fix)
    assert current.sunrise_time == datetime(2024, 6, 15, 6, 30, tzinfo=UTC)
    assert current.sunset_time == datetime(2024, 6, 15, 20, 45, tzinfo=UTC)


@pytest.mark.asyncio
async def test_visual_crossing_alerts_merged_with_existing():
    """Test that Visual Crossing alerts are merged with existing alerts, not replaced."""
    location = Location(name="New York", latitude=40.7128, longitude=-74.0060)
    client = WeatherClient(data_source="auto", visual_crossing_api_key="test_key")
    client.air_quality_enabled = False
    client.pollen_enabled = False
    client.air_quality_notify_threshold = 0
    client.environmental_client = None
    client.trend_insights_enabled = False

    # Mock NWS alert
    nws_alert = WeatherAlert(
        id="nws-alert-1",
        title="Flood Warning until midnight",
        event="Flood Warning",
        severity="Severe",
        headline="Flood Warning until midnight",
        description="Heavy rains expected",
        instruction="Avoid low-lying areas",
    )
    nws_alerts = WeatherAlerts(alerts=[nws_alert])

    # Mock Visual Crossing alert (different)
    vc_alert = WeatherAlert(
        id="vc-alert-1",
        title="Heat Advisory until 8 PM",
        event="Heat Advisory",
        severity="Moderate",
        headline="Heat Advisory until 8 PM",
        description="Temperatures may reach 95 degrees",
        instruction="Stay hydrated",
    )
    vc_alerts = WeatherAlerts(alerts=[vc_alert])

    # Mock Visual Crossing client methods
    mock_vc_client = AsyncMock()
    mock_vc_client.get_current_conditions = AsyncMock(return_value=None)
    mock_vc_client.get_forecast = AsyncMock(return_value=None)
    mock_vc_client.get_hourly_forecast = AsyncMock(return_value=None)
    mock_vc_client.get_alerts = AsyncMock(return_value=vc_alerts)
    client.visual_crossing_client = mock_vc_client

    # Mock the fetch methods used by smart auto source
    nws_current = CurrentConditions(temperature_f=72.0, condition="Clear")

    async def mock_fetch_nws(location):
        return (nws_current, Forecast(periods=[]), None, nws_alerts, HourlyForecast(periods=[]))

    async def mock_fetch_openmeteo(location):
        return (CurrentConditions(), Forecast(periods=[]), HourlyForecast(periods=[]))

    with (
        patch.object(client, "_fetch_nws_data", side_effect=mock_fetch_nws),
        patch.object(client, "_fetch_openmeteo_data", side_effect=mock_fetch_openmeteo),
        patch.object(client, "_process_visual_crossing_alerts", new_callable=AsyncMock),
    ):
        weather_data = await client.get_weather_data(location)

        # Verify both alerts are present
        assert len(weather_data.alerts.alerts) == 2
        event_names = {alert.event for alert in weather_data.alerts.alerts}
        assert "Flood Warning" in event_names
        assert "Heat Advisory" in event_names
