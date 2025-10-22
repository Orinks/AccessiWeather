from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from accessiweather.models import Location
from accessiweather.visual_crossing_api_client.visual_crossing_timeline_api_accessi_weather_sketch_client.models.current_conditions import (
    CurrentConditions,
)
from accessiweather.visual_crossing_api_client.visual_crossing_timeline_api_accessi_weather_sketch_client.models.day_forecast import (
    DayForecast,
)
from accessiweather.visual_crossing_api_client.visual_crossing_timeline_api_accessi_weather_sketch_client.models.timeline_response import (
    TimelineResponse,
)
from accessiweather.visual_crossing_api_client.visual_crossing_timeline_api_accessi_weather_sketch_client.models.weather_alert import (
    WeatherAlert,
)
from accessiweather.visual_crossing_client import VisualCrossingClient


@pytest.fixture
def timeline_payload() -> dict:
    return {
        "resolvedAddress": "Testville",
        "timezone": "UTC",
        "currentConditions": {
            "datetimeEpoch": 1_700_000_000,
            "datetime": "2024-05-01T12:00:00",
            "temp": 70.0,
            "feelslike": 68.0,
            "humidity": 55.0,
            "windspeed": 5.0,
            "winddir": 180.0,
            "pressure": 30.12,
            "visibility": 9.8,
            "dew": 50.0,
            "conditions": "Clear",
        },
        "days": [
            {
                "datetime": "2024-05-01",
                "tempmax": 75.0,
                "tempmin": 55.0,
                "temp": 65.0,
                "conditions": "Partly cloudy",
                "description": "Pleasant day with clouds in the afternoon.",
                "windspeed": 12.0,
                "winddir": 200.0,
                "icon": "partly-cloudy-day",
                "hours": [
                    {
                        "datetime": "10:00:00",
                        "temp": 68.0,
                        "conditions": "Sunny",
                        "windspeed": 10.0,
                        "winddir": 190.0,
                        "icon": "sunny",
                        "pressure": 1015.0,
                        "precipprob": 10.0,
                        "humidity": 50.0,
                    }
                ],
            }
        ],
        "alerts": [
            {
                "event": "Test Advisory",
                "headline": "Test Advisory in effect",
                "severity": "moderate",
                "description": "Remain cautious during the afternoon.",
                "onset": "2024-05-01T09:00:00Z",
                "ends": "2024-05-01T18:00:00Z",
                "id": "alert-123",
                "effective": "2024-05-01T08:30:00Z",
            }
        ],
    }


@pytest.fixture
def timeline_response(timeline_payload: dict) -> TimelineResponse:
    # Build via the generated models so additional properties flow through.
    current = CurrentConditions.from_dict(timeline_payload["currentConditions"])
    day = DayForecast.from_dict(timeline_payload["days"][0])
    alert = WeatherAlert.from_dict(timeline_payload["alerts"][0])
    return TimelineResponse(
        resolved_address=timeline_payload["resolvedAddress"],
        timezone=timeline_payload["timezone"],
        current_conditions=current,
        days=[day],
        alerts=[alert],
    )


@pytest.fixture
def location() -> Location:
    return Location(name="Testville", latitude=40.0, longitude=-74.0)


@pytest.fixture
def visual_client_with_timeline(mocker, timeline_response: TimelineResponse):
    client = VisualCrossingClient(api_key="test-key", use_timeline_api=True)
    fetch_mock = AsyncMock(return_value=timeline_response)

    client._timeline_client = SimpleNamespace(fetch=fetch_mock)

    async_client_factory = mocker.patch("accessiweather.visual_crossing_client.httpx.AsyncClient")

    return client, fetch_mock, async_client_factory


@pytest.mark.asyncio
async def test_current_conditions_from_timeline(
    visual_client_with_timeline, location: Location
) -> None:
    client, fetch_mock, async_client_factory = visual_client_with_timeline

    result = await client.get_current_conditions(location)

    fetch_mock.assert_awaited_once()
    request = fetch_mock.await_args[0][0]
    assert request.include == "current"
    assert result is not None
    assert result.temperature_f == pytest.approx(70.0)
    assert result.dewpoint_f == pytest.approx(50.0)
    assert result.visibility_miles == pytest.approx(9.8)
    assert result.last_updated is not None
    async_client_factory.assert_not_called()


@pytest.mark.asyncio
async def test_daily_forecast_from_timeline(
    visual_client_with_timeline, location: Location
) -> None:
    client, fetch_mock, async_client_factory = visual_client_with_timeline
    # Configure fetch to return data when include="days"
    fetch_mock.return_value = fetch_mock.return_value

    forecast = await client.get_forecast(location)

    request = fetch_mock.await_args_list[-1][0][0]
    assert request.include == "days"
    assert forecast is not None
    assert len(forecast.periods) == 1
    first_period = forecast.periods[0]
    assert first_period.temperature == pytest.approx(75.0)
    assert first_period.wind_direction == "SSW"
    async_client_factory.assert_not_called()


@pytest.mark.asyncio
async def test_hourly_forecast_from_timeline(
    visual_client_with_timeline, location: Location
) -> None:
    client, fetch_mock, async_client_factory = visual_client_with_timeline

    hourly = await client.get_hourly_forecast(location)

    request = fetch_mock.await_args_list[-1][0][0]
    assert "hours" in (request.include or "")
    assert hourly is not None
    assert len(hourly.periods) == 1
    first_hour = hourly.periods[0]
    assert first_hour.temperature == pytest.approx(68.0)
    assert first_hour.short_forecast == "Sunny"
    async_client_factory.assert_not_called()


@pytest.mark.asyncio
async def test_alerts_from_timeline(visual_client_with_timeline, location: Location) -> None:
    client, fetch_mock, async_client_factory = visual_client_with_timeline

    alerts = await client.get_alerts(location)

    request = fetch_mock.await_args_list[-1][0][0]
    assert request.include == "alerts"
    assert alerts.alerts
    alert = alerts.alerts[0]
    assert alert.event == "Test Advisory"
    assert alert.severity == "Moderate"
    assert alert.id == "alert-123"
    async_client_factory.assert_not_called()
