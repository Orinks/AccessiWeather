import httpx
import pytest

from accessiweather.location_manager import LocationManager
from accessiweather.models import Location


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


def patch_async_client(monkeypatch: pytest.MonkeyPatch, attempts: dict, payload):
    request = httpx.Request("GET", "https://example.com")

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            attempts["count"] += 1
            if attempts["count"] < attempts["failures_before_success"]:
                raise httpx.ConnectError("network", request=request)
            return DummyResponse(payload)

    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: DummyClient())


@pytest.mark.asyncio
async def test_search_locations_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0, "failures_before_success": 3}
    payload = [
        {
            "lat": "40.0",
            "lon": "-75.0",
            "address": {"city": "Testville", "state": "TS", "country": "United States"},
            "display_name": "Testville, TS",
        }
    ]

    patch_async_client(monkeypatch, attempts, payload)
    monkeypatch.setattr(
        "accessiweather.utils.retry_utils.asyncio.sleep",
        lambda *_: DummySleepAwaitable(),
    )

    manager = LocationManager()
    results = await manager.search_locations("Testville")

    assert attempts["count"] == 3
    assert results
    assert isinstance(results[0], Location)
    assert results[0].name.startswith("Testville")


@pytest.mark.asyncio
async def test_reverse_geocode_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0, "failures_before_success": 3}
    payload = {
        "lat": "40.0",
        "lon": "-75.0",
        "address": {"city": "Testville", "state": "TS", "country": "United States"},
        "display_name": "Testville, TS",
    }

    patch_async_client(monkeypatch, attempts, payload)
    monkeypatch.setattr(
        "accessiweather.utils.retry_utils.asyncio.sleep",
        lambda *_: DummySleepAwaitable(),
    )

    manager = LocationManager()
    result = await manager.reverse_geocode(40.0, -75.0)

    assert attempts["count"] == 3
    assert isinstance(result, Location)
    assert result.name.startswith("Testville")


@pytest.mark.asyncio
async def test_get_current_location_from_ip_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0, "failures_before_success": 2}
    payload = {
        "status": "success",
        "city": "Sample City",
        "regionName": "Sample Region",
        "country": "United States",
        "lat": 10.0,
        "lon": 20.0,
        "countryCode": "US",
    }

    patch_async_client(monkeypatch, attempts, payload)
    monkeypatch.setattr(
        "accessiweather.utils.retry_utils.asyncio.sleep",
        lambda *_: DummySleepAwaitable(),
    )

    manager = LocationManager()
    result = await manager.get_current_location_from_ip()

    assert attempts["count"] == 2
    assert isinstance(result, Location)
    assert result.name.startswith("Sample City")


class DummySleepAwaitable:
    def __await__(self):
        yield
