"""Tests for source-labelled surf and beach condition summaries."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from accessiweather import surf_conditions
from accessiweather.models import Location, TextProduct
from accessiweather.surf_conditions import (
    fetch_openmeteo_marine_surf_conditions,
    fetch_pirate_weather_beach_conditions,
    format_openmeteo_marine_report,
)


def _location(name: str = "Porto") -> Location:
    return Location(name=name, latitude=41.15, longitude=-8.63, country_code="PT")


def _resp(json_data, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


class _AsyncClientContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, *_exc_info):
        return False


def test_openmeteo_marine_report_labels_derived_conditions():
    report = format_openmeteo_marine_report(
        {
            "current": {
                "time": "2026-06-07T12:00",
                "wave_height": 1.4,
                "wave_direction": 270,
                "wave_period": 8,
                "swell_wave_height": 0.9,
                "swell_wave_direction": 250,
                "swell_wave_period": 11,
                "sea_surface_temperature": 18.5,
            },
            "current_units": {
                "wave_height": "m",
                "wave_period": "s",
                "swell_wave_height": "m",
                "swell_wave_period": "s",
                "sea_surface_temperature": "°C",
            },
        },
        _location(),
    )

    assert report is not None
    product = report.to_text_product()
    assert product.product_type == "SURF_CONDITIONS"
    assert "Surf conditions from Open-Meteo Marine for Porto." in product.product_text
    assert "not an official NWS Surf Zone Forecast" in product.product_text
    assert "Wave height: 1.4 m." in product.product_text
    assert "Wave direction: W (270 degrees)." in product.product_text


@pytest.mark.asyncio
async def test_client_get_accepts_synchronous_test_double():
    client = MagicMock(spec=httpx.AsyncClient)
    response = _resp({"ok": True})
    client.get.return_value = response

    result = await surf_conditions._client_get(client, "https://example.test")

    assert result is response


def test_openmeteo_format_helpers_ignore_empty_values():
    assert surf_conditions._first_present({"wave_height": []}, "wave_height") is None
    assert surf_conditions._format_value("   ", "m") is None
    assert surf_conditions._format_direction("offshore") == "offshore"


def test_openmeteo_marine_report_requires_current_marine_values():
    assert format_openmeteo_marine_report({"current": {}}, _location()) is None
    assert (
        format_openmeteo_marine_report({"current": {"time": "2026-06-07T12:00"}}, _location())
        is None
    )


def test_openmeteo_marine_report_tolerates_invalid_time():
    report = format_openmeteo_marine_report(
        {"current": {"time": "not-a-time", "wave_height": 1.2}},
        _location(),
    )

    assert report is not None
    assert report.issued_at is not None


@pytest.mark.asyncio
async def test_fetch_openmeteo_marine_surf_conditions_uses_marine_endpoint():
    client = MagicMock(spec=httpx.AsyncClient)
    client.get.return_value = _resp(
        {
            "current": {"time": "2026-06-07T12:00", "wave_height": 2.0},
            "current_units": {"wave_height": "m"},
        }
    )

    result = await fetch_openmeteo_marine_surf_conditions(
        _location(),
        marine_base_url="https://example.test/v1",
        client=client,
    )

    assert isinstance(result, TextProduct)
    assert result.product_type == "SURF_CONDITIONS"
    assert result.cwa_office == "Open-Meteo Marine"
    assert "not an official NWS Surf Zone Forecast" in result.product_text
    client.get.assert_called_once()
    assert client.get.call_args.args[0] == "https://example.test/v1/marine"
    assert "wave_height" in client.get.call_args.kwargs["params"]["current"]


@pytest.mark.asyncio
async def test_fetch_openmeteo_marine_surf_conditions_requires_coordinates():
    location = type("Location", (), {"name": "Unknown", "latitude": None, "longitude": -8.63})()

    result = await fetch_openmeteo_marine_surf_conditions(location)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_openmeteo_marine_surf_conditions_handles_unavailable_response():
    client = MagicMock(spec=httpx.AsyncClient)
    client.get.return_value = _resp({}, status_code=500)

    result = await fetch_openmeteo_marine_surf_conditions(_location(), client=client)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_openmeteo_marine_surf_conditions_handles_transport_errors():
    client = MagicMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.TransportError("offline")

    result = await fetch_openmeteo_marine_surf_conditions(_location(), client=client)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_openmeteo_marine_surf_conditions_creates_client(monkeypatch):
    client = MagicMock(spec=httpx.AsyncClient)
    client.get.return_value = _resp(
        {
            "current": {"time": "2026-06-07T12:00", "wave_height": 1.0},
            "current_units": {"wave_height": "m"},
        }
    )

    def fake_async_client(**kwargs):
        assert kwargs == {"timeout": 3.0, "follow_redirects": True}
        return _AsyncClientContext(client)

    monkeypatch.setattr(surf_conditions.httpx, "AsyncClient", fake_async_client)

    result = await fetch_openmeteo_marine_surf_conditions(_location(), timeout=3.0)

    assert isinstance(result, TextProduct)
    client.get.assert_called_once()


@pytest.mark.asyncio
async def test_pirate_weather_beach_conditions_use_only_available_weather_context():
    pirate_client = MagicMock()
    pirate_client.get_forecast_data = AsyncMock(
        return_value={
            "currently": {
                "summary": "Breezy",
                "temperature": 70,
                "apparentTemperature": 68,
                "windSpeed": 14,
                "windGust": 24,
                "windBearing": 180,
                "uvIndex": 6,
                "visibility": 9,
                "precipProbability": 0.2,
            }
        }
    )
    weather_client = MagicMock()
    weather_client._pirate_weather_client_for_location.return_value = pirate_client

    result = await fetch_pirate_weather_beach_conditions(_location("Brighton"), weather_client)

    assert isinstance(result, TextProduct)
    assert result.product_type == "SURF_CONDITIONS"
    assert "Surf conditions from Pirate Weather for Brighton." in result.product_text
    assert "not an official NWS Surf Zone Forecast" in result.product_text
    assert "wave data is not available from this source" in result.product_text
    assert "Wind direction: S (180 degrees)." in result.product_text


@pytest.mark.asyncio
async def test_pirate_weather_beach_conditions_require_available_client():
    assert await fetch_pirate_weather_beach_conditions(_location()) is None
    assert await fetch_pirate_weather_beach_conditions(_location(), MagicMock()) is None


@pytest.mark.asyncio
async def test_pirate_weather_beach_conditions_use_fallback_client_attribute():
    pirate_client = MagicMock()
    pirate_client.get_forecast_data = AsyncMock(
        return_value={"currently": {"summary": "Clear", "windSpeed": 8}}
    )
    weather_client = MagicMock()
    weather_client._pirate_weather_client_for_location.return_value = None
    weather_client.pirate_weather_client = pirate_client

    result = await fetch_pirate_weather_beach_conditions(_location(), weather_client)

    assert isinstance(result, TextProduct)
    assert "Conditions: Clear." in result.product_text
    assert "Wind speed: 8 mph." in result.product_text


@pytest.mark.asyncio
async def test_pirate_weather_beach_conditions_handles_unavailable_payloads():
    pirate_client = MagicMock()
    weather_client = MagicMock()
    weather_client._pirate_weather_client_for_location.return_value = pirate_client

    pirate_client.get_forecast_data = AsyncMock(side_effect=RuntimeError("offline"))
    assert await fetch_pirate_weather_beach_conditions(_location(), weather_client) is None

    pirate_client.get_forecast_data = AsyncMock(return_value=["not", "a", "dict"])
    assert await fetch_pirate_weather_beach_conditions(_location(), weather_client) is None

    pirate_client.get_forecast_data = AsyncMock(return_value={"currently": []})
    assert await fetch_pirate_weather_beach_conditions(_location(), weather_client) is None

    pirate_client.get_forecast_data = AsyncMock(return_value={"currently": {}})
    assert await fetch_pirate_weather_beach_conditions(_location(), weather_client) is None
