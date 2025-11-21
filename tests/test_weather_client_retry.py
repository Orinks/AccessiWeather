import httpx
import pytest

from accessiweather.models import Location, WeatherAlerts
from accessiweather.visual_crossing_client import VisualCrossingClient
from accessiweather.weather_client_nws import get_nws_alerts
from accessiweather.weather_client_openmeteo import get_openmeteo_forecast


class DummySleepAwaitable:
    def __await__(self):
        yield


class DummyResponse:
    """Mock response for testing."""

    def __init__(self, payload, status_code: int = 200) -> None:
        """Initialize mock response."""
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if not (200 <= self.status_code < 300):
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_get_nws_alerts_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0, "failures_before_success": 3}

    async def fake_client_get(client, url, *, headers=None, params=None):
        attempts["count"] += 1
        if attempts["count"] < attempts["failures_before_success"]:
            raise httpx.ConnectError("failed", request=httpx.Request("GET", url))
        return DummyResponse({"features": []})

    monkeypatch.setattr("accessiweather.weather_client_nws._client_get", fake_client_get)
    monkeypatch.setattr(
        "accessiweather.weather_client_nws.parse_nws_alerts",
        lambda data: WeatherAlerts(alerts=[]),
    )
    monkeypatch.setattr(
        "accessiweather.utils.retry_utils.asyncio.sleep",
        lambda *_: DummySleepAwaitable(),
    )

    location = Location(name="Test", latitude=0.0, longitude=0.0)
    result = await get_nws_alerts(
        location,
        "https://api.weather.gov",
        "TestAgent/1.0",
        timeout=5.0,
        client=object(),
    )

    assert attempts["count"] == 3
    assert isinstance(result, WeatherAlerts)


@pytest.mark.asyncio
async def test_get_openmeteo_forecast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0, "failures_before_success": 3}

    async def fake_client_get(client, url, *, params=None):
        attempts["count"] += 1
        if attempts["count"] < attempts["failures_before_success"]:
            raise httpx.ReadTimeout("timeout", request=httpx.Request("GET", url))
        return DummyResponse({"daily": {}})

    monkeypatch.setattr("accessiweather.weather_client_openmeteo._client_get", fake_client_get)
    monkeypatch.setattr(
        "accessiweather.weather_client_openmeteo.parse_openmeteo_forecast",
        lambda data: "parsed",
    )
    monkeypatch.setattr(
        "accessiweather.utils.retry_utils.asyncio.sleep",
        lambda *_: DummySleepAwaitable(),
    )

    location = Location(name="Test", latitude=0.0, longitude=0.0)
    result = await get_openmeteo_forecast(
        location,
        "https://api.open-meteo.com/v1",
        timeout=5.0,
        client=object(),
    )

    assert attempts["count"] == 3
    assert result == "parsed"


@pytest.mark.asyncio
async def test_visual_crossing_retries_on_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0, "failures_before_success": 3}
    request = httpx.Request("GET", "https://weather.visualcrossing.com")

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None, headers=None):
            attempts["count"] += 1
            if attempts["count"] < attempts["failures_before_success"]:
                raise httpx.ConnectError("down", request=request)
            return DummyResponse({"currentConditions": {"temp": 70, "humidity": 50}, "days": []})

    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: DummyClient())
    monkeypatch.setattr(
        "accessiweather.visual_crossing_client.VisualCrossingClient._parse_current_conditions",
        lambda self, data, location=None: "ok",
    )
    monkeypatch.setattr(
        "accessiweather.utils.retry_utils.asyncio.sleep",
        lambda *_: DummySleepAwaitable(),
    )

    client = VisualCrossingClient(api_key="test-key")
    location = Location(name="Test", latitude=0.0, longitude=0.0)

    result = await client.get_current_conditions(location)

    assert attempts["count"] == 3
    assert result == "ok"
