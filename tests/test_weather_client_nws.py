import httpx
import pytest

from accessiweather import weather_client_nws


class DummyResponse:
    """Minimal httpx-style response stub for testing."""

    def __init__(self, payload):
        """Persist the payload so callers can retrieve it via json()."""
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_get_nws_tafs_prefers_nws_payload(monkeypatch):
    async def fake_client_get(client, url, headers=None, params=None):
        return DummyResponse({"features": [{"properties": {"rawMessage": "TAF KAAA TEST"}}]})

    monkeypatch.setattr(weather_client_nws, "_client_get", fake_client_get)

    client = httpx.AsyncClient()
    try:
        taf = await weather_client_nws.get_nws_tafs(
            "KAAA", "https://api.weather.gov", "AccessiWeather/Tests", 10, client
        )
    finally:
        await client.aclose()

    assert taf == "TAF KAAA TEST"


@pytest.mark.asyncio
async def test_get_nws_tafs_falls_back_to_aviationweather(monkeypatch):
    async def fake_client_get(client, url, headers=None, params=None):
        if "aviationweather.gov" in url:
            return DummyResponse([{"rawTAF": "TAF KBBB Fallback"}])
        return DummyResponse({"features": []})

    monkeypatch.setattr(weather_client_nws, "_client_get", fake_client_get)

    client = httpx.AsyncClient()
    try:
        taf = await weather_client_nws.get_nws_tafs(
            "KBBB", "https://api.weather.gov", "AccessiWeather/Tests", 10, client
        )
    finally:
        await client.aclose()

    assert taf == "TAF KBBB Fallback"
