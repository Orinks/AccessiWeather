"""
Tests for the generic NWS text-product fetcher.

Covers:
- ``get_nws_text_product`` for AFD / HWO / SPS
- ``TextProductFetchError`` signalling network / non-200 failures
- ``get_nws_discussion`` backward-compat wrapper preserves its tuple shape
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pytest

from accessiweather.models import TextProduct
from accessiweather.weather_client_nws import (
    TextProductFetchError,
    get_nws_discussion,
    get_nws_text_product,
)

NWS_BASE = "https://api.weather.gov"
OFFICE = "PHI"


def _resp(json_data, status_code: int = 200) -> MagicMock:
    """Build a synchronous mock httpx.Response with status_code + json()."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _resp_error(status_code: int = 500) -> MagicMock:
    """Mock response whose raise_for_status raises HTTPStatusError."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    err = httpx.HTTPStatusError(f"HTTP {status_code}", request=MagicMock(), response=resp)
    resp.raise_for_status.side_effect = err
    return resp


def _client_for(responses: dict) -> MagicMock:
    """Mock AsyncClient dispatching on URL."""

    def side_effect(url, **_kwargs):
        if url in responses:
            return responses[url]
        return _resp({}, status_code=404)

    client = MagicMock(spec=httpx.AsyncClient)
    client.get.side_effect = side_effect
    return client


# ---------------------------------------------------------------------------
# AFD happy path
# ---------------------------------------------------------------------------


class TestGetNwsTextProductAFD:
    @pytest.mark.asyncio
    async def test_afd_returns_single_text_product(self):
        graph = {
            "@graph": [
                {
                    "id": "afd-001",
                    "issuanceTime": "2026-04-16T14:32:00+00:00",
                }
            ]
        }
        product = {
            "productText": "AREA FORECAST DISCUSSION...\nSYNOPSIS...\n",
            "issuanceTime": "2026-04-16T14:32:00+00:00",
        }
        client = _client_for(
            {
                f"{NWS_BASE}/products/types/AFD/locations/{OFFICE}": _resp(graph),
                f"{NWS_BASE}/products/afd-001": _resp(product),
            }
        )

        result = await get_nws_text_product("AFD", OFFICE, nws_base_url=NWS_BASE, client=client)

        assert isinstance(result, TextProduct)
        assert result.product_type == "AFD"
        assert result.product_id == "afd-001"
        assert result.cwa_office == OFFICE
        assert "AREA FORECAST DISCUSSION" in result.product_text
        assert result.issuance_time == datetime(2026, 4, 16, 14, 32, 0, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_afd_empty_graph_returns_none(self):
        client = _client_for(
            {
                f"{NWS_BASE}/products/types/AFD/locations/{OFFICE}": _resp({"@graph": []}),
            }
        )

        result = await get_nws_text_product("AFD", OFFICE, nws_base_url=NWS_BASE, client=client)

        assert result is None


# ---------------------------------------------------------------------------
# HWO happy path
# ---------------------------------------------------------------------------


class TestGetNwsTextProductHWO:
    @pytest.mark.asyncio
    async def test_hwo_returns_single_text_product(self):
        graph = {
            "@graph": [
                {"id": "hwo-001", "issuanceTime": "2026-04-16T10:00:00+00:00"},
            ]
        }
        product = {
            "productText": "HAZARDOUS WEATHER OUTLOOK\n...\n",
            "issuanceTime": "2026-04-16T10:00:00+00:00",
        }
        client = _client_for(
            {
                f"{NWS_BASE}/products/types/HWO/locations/{OFFICE}": _resp(graph),
                f"{NWS_BASE}/products/hwo-001": _resp(product),
            }
        )

        result = await get_nws_text_product("HWO", OFFICE, nws_base_url=NWS_BASE, client=client)

        assert isinstance(result, TextProduct)
        assert result.product_type == "HWO"
        assert result.product_id == "hwo-001"
        assert result.cwa_office == OFFICE
        assert "HAZARDOUS WEATHER" in result.product_text


# ---------------------------------------------------------------------------
# SPS — always returns a list, possibly empty, sorted newest-first
# ---------------------------------------------------------------------------


class TestGetNwsTextProductSPS:
    @pytest.mark.asyncio
    async def test_sps_three_products_sorted_newest_first(self):
        # Intentionally out-of-order in the @graph so we can verify sorting.
        graph = {
            "@graph": [
                {"id": "sps-middle", "issuanceTime": "2026-04-16T12:00:00+00:00"},
                {"id": "sps-newest", "issuanceTime": "2026-04-16T14:00:00+00:00"},
                {"id": "sps-oldest", "issuanceTime": "2026-04-16T10:00:00+00:00"},
            ]
        }
        client = _client_for(
            {
                f"{NWS_BASE}/products/types/SPS/locations/{OFFICE}": _resp(graph),
                f"{NWS_BASE}/products/sps-middle": _resp(
                    {
                        "productText": "SPS middle",
                        "issuanceTime": "2026-04-16T12:00:00+00:00",
                    }
                ),
                f"{NWS_BASE}/products/sps-newest": _resp(
                    {
                        "productText": "SPS newest",
                        "issuanceTime": "2026-04-16T14:00:00+00:00",
                    }
                ),
                f"{NWS_BASE}/products/sps-oldest": _resp(
                    {
                        "productText": "SPS oldest",
                        "issuanceTime": "2026-04-16T10:00:00+00:00",
                    }
                ),
            }
        )

        result = await get_nws_text_product("SPS", OFFICE, nws_base_url=NWS_BASE, client=client)

        assert isinstance(result, list)
        assert len(result) == 3
        # Newest first.
        assert result[0].product_id == "sps-newest"
        assert result[1].product_id == "sps-middle"
        assert result[2].product_id == "sps-oldest"
        for tp in result:
            assert tp.product_type == "SPS"
            assert tp.cwa_office == OFFICE

    @pytest.mark.asyncio
    async def test_sps_empty_graph_returns_empty_list(self):
        client = _client_for(
            {
                f"{NWS_BASE}/products/types/SPS/locations/{OFFICE}": _resp({"@graph": []}),
            }
        )

        result = await get_nws_text_product("SPS", OFFICE, nws_base_url=NWS_BASE, client=client)

        assert result == []
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestGetNwsTextProductEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_office_returns_none_no_http(self):
        client = MagicMock(spec=httpx.AsyncClient)

        result = await get_nws_text_product("AFD", "", nws_base_url=NWS_BASE, client=client)

        assert result is None
        client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_office_returns_none_no_http(self):
        client = MagicMock(spec=httpx.AsyncClient)

        result = await get_nws_text_product("AFD", None, nws_base_url=NWS_BASE, client=client)

        assert result is None
        client.get.assert_not_called()


# ---------------------------------------------------------------------------
# Error paths — TextProductFetchError
# ---------------------------------------------------------------------------


class TestGetNwsTextProductErrors:
    @pytest.mark.asyncio
    async def test_http_500_raises_fetch_error(self):
        client = _client_for(
            {
                f"{NWS_BASE}/products/types/AFD/locations/{OFFICE}": _resp_error(500),
            }
        )

        with pytest.raises(TextProductFetchError):
            await get_nws_text_product("AFD", OFFICE, nws_base_url=NWS_BASE, client=client)

    @pytest.mark.asyncio
    async def test_timeout_raises_fetch_error(self):
        client = MagicMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(TextProductFetchError):
            await get_nws_text_product("AFD", OFFICE, nws_base_url=NWS_BASE, client=client)


# ---------------------------------------------------------------------------
# Regression: get_nws_discussion wrapper preserves old tuple shape
# ---------------------------------------------------------------------------


class TestGetNwsDiscussionBackwardCompat:
    @pytest.mark.asyncio
    async def test_get_nws_discussion_returns_tuple(self):
        """Wrapper must still return (text, issuance_time) tuple for existing callers."""
        graph = {
            "@graph": [
                {"id": "afd-back", "issuanceTime": "2026-04-16T14:32:00+00:00"},
            ]
        }
        product = {
            "productText": "WRAPPER TEST DISCUSSION TEXT",
            "issuanceTime": "2026-04-16T14:32:00+00:00",
        }
        grid_data = {
            "properties": {
                "forecast": f"{NWS_BASE}/gridpoints/{OFFICE}/36,38/forecast",
            }
        }
        client = _client_for(
            {
                f"{NWS_BASE}/products/types/AFD/locations/{OFFICE}": _resp(graph),
                f"{NWS_BASE}/products/afd-back": _resp(product),
            }
        )
        headers = {"User-Agent": "Test/1.0"}

        text, issuance_time = await get_nws_discussion(client, headers, grid_data, NWS_BASE)

        assert text == "WRAPPER TEST DISCUSSION TEXT"
        assert issuance_time == datetime(2026, 4, 16, 14, 32, 0, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_get_nws_discussion_empty_graph_returns_fallback_string(self):
        """When no AFD products exist, wrapper returns the legacy fallback string."""
        grid_data = {
            "properties": {
                "forecast": f"{NWS_BASE}/gridpoints/{OFFICE}/36,38/forecast",
            }
        }
        client = _client_for(
            {
                f"{NWS_BASE}/products/types/AFD/locations/{OFFICE}": _resp({"@graph": []}),
            }
        )
        headers = {"User-Agent": "Test/1.0"}

        text, issuance_time = await get_nws_discussion(client, headers, grid_data, NWS_BASE)

        # Previous behavior: returned a non-None fallback string and None issuance.
        assert isinstance(text, str)
        assert text != ""
        assert issuance_time is None
