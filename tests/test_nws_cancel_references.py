"""Tests for fetch_nws_cancel_references."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.weather_client_nws import fetch_nws_cancel_references


@pytest.mark.asyncio
async def test_returns_referenced_ids():
    """Returns set of IDs from Cancel messages references array."""
    mock_data = {
        "features": [
            {
                "properties": {
                    "messageType": "Cancel",
                    "references": [
                        {"identifier": "NWS-IDP-1", "sent": "2024-01-01T00:00:00Z"},
                        {"identifier": "NWS-IDP-2", "sent": "2024-01-01T00:00:00Z"},
                    ],
                }
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_data)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    result = await fetch_nws_cancel_references(
        "https://api.weather.gov",
        "TestAgent/1.0",
        10.0,
        lookback_minutes=15,
        client=mock_client,
    )
    assert "NWS-IDP-1" in result
    assert "NWS-IDP-2" in result


@pytest.mark.asyncio
async def test_returns_empty_set_on_error():
    """Returns empty set on HTTP error (safe default)."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Network error"))
    result = await fetch_nws_cancel_references(
        "https://api.weather.gov",
        "TestAgent/1.0",
        10.0,
        lookback_minutes=15,
        client=mock_client,
    )
    assert result == set()


@pytest.mark.asyncio
async def test_empty_features_returns_empty_set():
    """Empty features array returns empty set."""
    mock_data = {"features": []}
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_data)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    result = await fetch_nws_cancel_references(
        "https://api.weather.gov", "TestAgent/1.0", 10.0, client=mock_client
    )
    assert result == set()


@pytest.mark.asyncio
async def test_creates_http_client_when_none_provided():
    """When client is None, the helper owns the temporary HTTP client."""
    cancel_data = {
        "features": [
            {
                "properties": {
                    "references": [
                        {"identifier": "cancel-ref-1"},
                        {"@id": "cancel-ref-2"},
                    ],
                }
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=cancel_data)
    mock_new_client = AsyncMock()
    mock_new_client.get = AsyncMock(return_value=mock_response)

    with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_new_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await fetch_nws_cancel_references(
            nws_base_url="https://api.weather.gov",
            user_agent="TestAgent/1.0",
            timeout=10.0,
            client=None,
        )

    assert "cancel-ref-1" in result
    assert "cancel-ref-2" in result
