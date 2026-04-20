"""
Tests for zone-reuse optimization in the NWS alert-fetch path.

Unit 4 of the Forecast Products PR 1 plan (A-R6): when a ``Location`` has
a stored ``county_zone_id`` (or ``forecast_zone_id`` for the zone radius
type), ``get_nws_alerts`` should use it directly and skip the per-refresh
``/points`` call. When the stored field is absent, the existing ``/points``
resolution path is used.

Tests mock ``httpx`` so no network calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from accessiweather.models import Location
from accessiweather.weather_client_nws import get_nws_alerts

BASE_URL = "https://api.weather.gov"
USER_AGENT = "Test/1.0"


def _make_response(payload: dict, status_code: int = 200) -> MagicMock:
    """Build a mock httpx response object."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        # Simulate httpx raising for error responses.
        def _raise() -> None:
            request = httpx.Request("GET", BASE_URL)
            raise httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=request,
                response=httpx.Response(status_code, request=request),
            )

        response.raise_for_status.side_effect = _raise
    return response


def _classify_call(call) -> str:
    """Classify a mock httpx GET call as points/alerts/other."""
    # httpx.AsyncClient.get(url, headers=..., params=...) — url is positional arg 0.
    url = call.args[0] if call.args else call.kwargs.get("url", "")
    if "/points/" in url:
        return "points"
    if "/alerts/active" in url:
        return "alerts"
    return "other"


def _count_calls(mock_client: AsyncMock) -> dict[str, int]:
    counts = {"points": 0, "alerts": 0, "other": 0}
    for call in mock_client.get.call_args_list:
        counts[_classify_call(call)] += 1
    return counts


@pytest.fixture
def stored_location() -> Location:
    """Return a US location with zone metadata already populated."""
    return Location(
        name="Stored City",
        latitude=40.7128,
        longitude=-74.0060,
        county_zone_id="NYC061",
        forecast_zone_id="NYZ072",
    )


@pytest.fixture
def unstored_location() -> Location:
    """Return a US location without zone metadata — should fall back to /points."""
    return Location(
        name="Unstored City",
        latitude=40.7128,
        longitude=-74.0060,
    )


@pytest.fixture
def empty_alerts_payload() -> dict:
    return {"features": []}


@pytest.fixture
def points_payload() -> dict:
    """Minimal /points payload with county + forecastZone URLs."""
    return {
        "properties": {
            "county": "https://api.weather.gov/zones/county/NYC061",
            "forecastZone": "https://api.weather.gov/zones/forecast/NYZ072",
        }
    }


@pytest.mark.asyncio
async def test_county_happy_path_uses_stored_zone(stored_location, empty_alerts_payload):
    """County radius + stored county_zone_id → zone param used, no /points call."""
    alerts_response = _make_response(empty_alerts_payload)

    with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = alerts_response

        result = await get_nws_alerts(
            location=stored_location,
            nws_base_url=BASE_URL,
            user_agent=USER_AGENT,
            timeout=10.0,
            alert_radius_type="county",
        )

    assert result is not None
    counts = _count_calls(mock_client)
    assert counts["points"] == 0, "Stored county_zone_id must skip /points"
    assert counts["alerts"] == 1

    # Inspect the alert call's params.
    alert_call = next(c for c in mock_client.get.call_args_list if _classify_call(c) == "alerts")
    params = alert_call.kwargs.get("params", {})
    assert params.get("zone") == "NYC061"
    assert params.get("status") == "actual"
    assert "point" not in params


@pytest.mark.asyncio
async def test_zone_happy_path_uses_stored_forecast_zone(stored_location, empty_alerts_payload):
    """Zone radius + stored forecast_zone_id → zone param used, no /points call."""
    alerts_response = _make_response(empty_alerts_payload)

    with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = alerts_response

        result = await get_nws_alerts(
            location=stored_location,
            nws_base_url=BASE_URL,
            user_agent=USER_AGENT,
            timeout=10.0,
            alert_radius_type="zone",
        )

    assert result is not None
    counts = _count_calls(mock_client)
    assert counts["points"] == 0, "Stored forecast_zone_id must skip /points"
    assert counts["alerts"] == 1

    alert_call = next(c for c in mock_client.get.call_args_list if _classify_call(c) == "alerts")
    params = alert_call.kwargs.get("params", {})
    assert params.get("zone") == "NYZ072"
    assert params.get("status") == "actual"


@pytest.mark.asyncio
async def test_county_fallback_when_stored_fields_absent(
    unstored_location, empty_alerts_payload, points_payload
):
    """County radius + no stored zone → /points runs + alerts request works."""
    points_response = _make_response(points_payload)
    alerts_response = _make_response(empty_alerts_payload)

    with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        def _dispatch(url: str, *_args: object, **_kwargs: object):  # noqa: ARG001
            del _args, _kwargs
            if "/points/" in url:
                return points_response
            return alerts_response

        mock_client.get.side_effect = _dispatch

        result = await get_nws_alerts(
            location=unstored_location,
            nws_base_url=BASE_URL,
            user_agent=USER_AGENT,
            timeout=10.0,
            alert_radius_type="county",
        )

    assert result is not None
    counts = _count_calls(mock_client)
    assert counts["points"] == 1, "Without stored fields, /points resolution must run"
    assert counts["alerts"] == 1

    alert_call = next(c for c in mock_client.get.call_args_list if _classify_call(c) == "alerts")
    params = alert_call.kwargs.get("params", {})
    assert params.get("zone") == "NYC061"


@pytest.mark.asyncio
async def test_stored_zone_404_surfaces_as_error(stored_location):
    """
    Stale stored zone + NWS 404 on zone-alerts → returns safe empty alerts.

    Mirrors the pre-existing behavior of get_nws_alerts: non-retryable
    errors are swallowed and an empty WeatherAlerts is returned. The
    important assertion is that the error surfaces normally (no silent
    downgrade to point query) — i.e. only the zone-alert call is made,
    and no /points call happens to "rescue" the request.
    """
    # 404 from NWS on the zone-alerts fetch.
    bad_response = _make_response({}, status_code=404)

    with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = bad_response

        result = await get_nws_alerts(
            location=stored_location,
            nws_base_url=BASE_URL,
            user_agent=USER_AGENT,
            timeout=10.0,
            alert_radius_type="county",
        )

    # Pre-existing behavior: non-retryable error → empty WeatherAlerts.
    assert result is not None
    assert result.alerts == []

    counts = _count_calls(mock_client)
    # No silent /points downgrade — just the one failed zone-alert call.
    assert counts["points"] == 0
    assert counts["alerts"] == 1

    alert_call = next(c for c in mock_client.get.call_args_list if _classify_call(c) == "alerts")
    params = alert_call.kwargs.get("params", {})
    assert params.get("zone") == "NYC061"


@pytest.mark.asyncio
async def test_integration_second_refresh_has_one_fewer_http_call(
    empty_alerts_payload, points_payload
):
    """
    Before-stored vs after-stored: second refresh makes exactly one fewer HTTP call.

    Simulates the real-world flow: first refresh with no stored zones must
    call /points + /alerts (2 calls). After zone enrichment populates
    county_zone_id, the second refresh calls only /alerts (1 call).
    """
    first_location = Location(name="City", latitude=40.7128, longitude=-74.0060)
    second_location = Location(
        name="City",
        latitude=40.7128,
        longitude=-74.0060,
        county_zone_id="NYC061",
    )

    # --- First refresh: no stored fields, /points + /alerts ---
    with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as mock_client_class:
        mock_client_first = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client_first

        def _first_dispatch(url: str, *_args: object, **_kwargs: object):  # noqa: ARG001
            del _args, _kwargs
            if "/points/" in url:
                return _make_response(points_payload)
            return _make_response(empty_alerts_payload)

        mock_client_first.get.side_effect = _first_dispatch

        await get_nws_alerts(
            location=first_location,
            nws_base_url=BASE_URL,
            user_agent=USER_AGENT,
            timeout=10.0,
            alert_radius_type="county",
        )

    first_counts = _count_calls(mock_client_first)
    first_total = sum(first_counts.values())

    # --- Second refresh: stored county_zone_id, just /alerts ---
    with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as mock_client_class:
        mock_client_second = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client_second
        mock_client_second.get.return_value = _make_response(empty_alerts_payload)

        await get_nws_alerts(
            location=second_location,
            nws_base_url=BASE_URL,
            user_agent=USER_AGENT,
            timeout=10.0,
            alert_radius_type="county",
        )

    second_counts = _count_calls(mock_client_second)
    second_total = sum(second_counts.values())

    assert first_counts == {"points": 1, "alerts": 1, "other": 0}
    assert second_counts == {"points": 0, "alerts": 1, "other": 0}
    assert second_total == first_total - 1, (
        f"Expected one fewer HTTP call after zone metadata is stored; "
        f"first={first_total}, second={second_total}"
    )
