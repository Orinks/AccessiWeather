"""Tests for marine enrichment helpers and marine mode NWS enrichment."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import Location, WeatherAlert, WeatherAlerts, WeatherData
from accessiweather.weather_client_enrichment import (
    _build_marine_highlights,
    _parse_marine_issued_at,
    enrich_with_marine_data,
)


class _MockResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_build_marine_highlights_deduplicates_and_limits_results():
    periods = [
        {
            "shortForecast": "South winds 10 to 15 knots. Waves 1 to 2 feet.",
            "detailedForecast": "South winds 10 to 15 knots. Seas around 2 feet.",
        },
        {
            "shortForecast": "Gusts up to 20 knots. Swells 3 feet.",
            "detailedForecast": "Gusts up to 20 knots. Swells 3 feet.",
        },
        {"shortForecast": "North winds 5 knots.", "detailedForecast": ""},
    ]

    highlights = _build_marine_highlights(periods)

    assert highlights == [
        "South winds 10 to 15 knots",
        "Waves 1 to 2 feet",
        "Seas around 2 feet",
        "Gusts up to 20 knots",
    ]


@pytest.mark.parametrize(
    ("value", "expected_none"),
    [
        ("2026-03-27T15:00:00Z", False),
        ("not-a-date", True),
        (None, True),
    ],
)
def test_parse_marine_issued_at_handles_valid_and_invalid_values(value, expected_none):
    result = _parse_marine_issued_at(value)

    assert (result is None) is expected_none


@pytest.mark.asyncio
async def test_enrich_with_marine_data_noops_when_marine_mode_disabled():
    location = Location(name="Inland", latitude=39.0, longitude=-76.0, marine_mode=False)
    weather_data = WeatherData(location=location)
    client = MagicMock()
    client._is_us_location.return_value = True

    await enrich_with_marine_data(client, weather_data, location)

    client._get_http_client.assert_not_called()
    assert weather_data.marine is None


@pytest.mark.asyncio
async def test_enrich_with_marine_data_populates_forecast_and_merges_alerts():
    location = Location(name="Annapolis", latitude=38.9784, longitude=-76.4922, marine_mode=True)
    weather_data = WeatherData(
        location=location,
        alerts=WeatherAlerts(
            alerts=[
                WeatherAlert(
                    id="existing-alert",
                    title="Existing Advisory",
                    description="Existing advisory",
                )
            ]
        ),
    )

    client = MagicMock()
    client._is_us_location.return_value = True
    client._get_http_client.return_value = object()
    client.user_agent = "AccessiWeather Test"
    client.nws_base_url = "https://api.weather.gov"
    client.timeout = 30

    zone_response = _MockResponse(
        {
            "features": [
                {
                    "id": "ANZ530",
                    "properties": {
                        "id": "ANZ530",
                        "name": "Chesapeake Bay from Pooles Island to Sandy Point",
                    },
                }
            ]
        }
    )
    alerts_response = _MockResponse({"features": []})
    marine_forecast = {
        "properties": {
            "name": "Chesapeake Bay from Pooles Island to Sandy Point",
            "updateTime": "2026-03-27T15:00:00Z",
            "periods": [
                {
                    "name": "Tonight",
                    "shortForecast": "South winds 10 to 15 knots. Waves 1 to 2 feet.",
                    "detailedForecast": "South winds 10 to 15 knots. Waves 1 to 2 feet.",
                },
                {
                    "name": "Saturday",
                    "shortForecast": "Gusts up to 20 knots.",
                    "detailedForecast": "Gusts up to 20 knots. Seas around 2 feet.",
                },
            ],
        }
    }
    marine_alert = WeatherAlert(
        id="marine-alert",
        title="Small Craft Advisory",
        description="Hazardous conditions expected.",
        source="NWS",
    )

    with (
        patch(
            "accessiweather.weather_client_enrichment.nws_client._client_get",
            new=AsyncMock(side_effect=[zone_response, alerts_response]),
        ),
        patch(
            "accessiweather.weather_client_enrichment.nws_client.get_nws_marine_forecast",
            new=AsyncMock(return_value=marine_forecast),
        ),
        patch(
            "accessiweather.weather_client_enrichment.nws_client.parse_nws_alerts",
            return_value=WeatherAlerts(alerts=[marine_alert]),
        ),
    ):
        await enrich_with_marine_data(client, weather_data, location)

    assert weather_data.marine is not None
    assert weather_data.marine.zone_id == "ANZ530"
    assert weather_data.marine.zone_name == "Chesapeake Bay from Pooles Island to Sandy Point"
    assert weather_data.marine.forecast_summary == "South winds 10 to 15 knots. Waves 1 to 2 feet."
    assert weather_data.marine.issued_at is not None
    assert len(weather_data.marine.periods) == 2
    assert weather_data.marine.highlights == [
        "South winds 10 to 15 knots",
        "Waves 1 to 2 feet",
        "Gusts up to 20 knots",
        "Seas around 2 feet",
    ]
    assert weather_data.alerts is not None
    assert sorted(alert.id for alert in weather_data.alerts.alerts) == [
        "existing-alert",
        "marine-alert",
    ]
    merged_marine_alert = next(
        alert for alert in weather_data.alerts.alerts if alert.id == "marine-alert"
    )
    assert merged_marine_alert.source == "NWS Marine"


@pytest.mark.asyncio
async def test_enrich_with_marine_data_returns_cleanly_when_no_zone_found():
    location = Location(name="Annapolis", latitude=38.9784, longitude=-76.4922, marine_mode=True)
    weather_data = WeatherData(location=location)
    client = MagicMock()
    client._is_us_location.return_value = True
    client._get_http_client.return_value = object()
    client.user_agent = "AccessiWeather Test"
    client.nws_base_url = "https://api.weather.gov"

    with patch(
        "accessiweather.weather_client_enrichment.nws_client._client_get",
        new=AsyncMock(return_value=_MockResponse({"features": []})),
    ):
        await enrich_with_marine_data(client, weather_data, location)

    assert weather_data.marine is None
    assert weather_data.alerts is None
