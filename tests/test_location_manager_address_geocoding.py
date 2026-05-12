"""Tests for street-address geocoding in LocationManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.location_manager import LocationManager


def _make_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def census_payload() -> dict:
    return {
        "result": {
            "addressMatches": [
                {
                    "coordinates": {
                        "x": -76.928365658124,
                        "y": 38.845053106269,
                    },
                    "matchedAddress": "4600 SILVER HILL RD, WASHINGTON, DC, 20233",
                }
            ]
        }
    }


def test_street_address_detection_keeps_city_and_zip_queries_on_existing_path() -> None:
    manager = LocationManager()

    assert manager._looks_like_street_address("4600 Silver Hill Rd, Washington, DC")
    assert manager._looks_like_street_address("123 Main Street, Carrollton, TX")
    assert manager._looks_like_street_address("1234 Elm, Carrollton, TX")
    assert not manager._looks_like_street_address("Carrollton, TX")
    assert not manager._looks_like_street_address("75007")


def test_parse_census_address_match_returns_us_location(census_payload: dict) -> None:
    manager = LocationManager()

    location = manager._parse_census_address_match(census_payload["result"]["addressMatches"][0])

    assert location is not None
    assert location.name == "4600 SILVER HILL RD, WASHINGTON, DC, 20233"
    assert location.latitude == pytest.approx(38.845053106269)
    assert location.longitude == pytest.approx(-76.928365658124)
    assert location.country_code == "US"


@pytest.mark.asyncio
async def test_search_locations_uses_census_for_street_address(census_payload: dict) -> None:
    manager = LocationManager()

    with patch("accessiweather.location_manager.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = _make_response(census_payload)

        locations = await manager.search_locations(
            "4600 Silver Hill Rd, Washington, DC 20233",
            limit=5,
        )

    assert len(locations) == 1
    assert locations[0].name == "4600 SILVER HILL RD, WASHINGTON, DC, 20233"
    assert locations[0].country_code == "US"

    mock_client.get.assert_called_once()
    call = mock_client.get.call_args
    assert call.args == ("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",)
    assert call.kwargs["params"] == {
        "address": "4600 Silver Hill Rd, Washington, DC 20233",
        "benchmark": "Public_AR_Current",
        "format": "json",
    }


@pytest.mark.asyncio
async def test_search_locations_falls_back_to_openmeteo_when_address_has_no_match(
    census_payload: dict,
) -> None:
    manager = LocationManager()
    census_payload["result"]["addressMatches"] = []

    with patch("accessiweather.location_manager.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = [
            _make_response(census_payload),
            _make_response(
                {
                    "results": [
                        {
                            "name": "Carrollton",
                            "latitude": 32.95373,
                            "longitude": -96.89028,
                            "admin1": "Texas",
                            "country": "United States",
                            "country_code": "US",
                        }
                    ]
                }
            ),
        ]

        locations = await manager.search_locations(
            "123 Unknown Street, Carrollton, TX",
            limit=5,
        )

    assert len(locations) == 1
    assert locations[0].name == "Carrollton, Texas"
    assert locations[0].latitude == pytest.approx(32.95373)
    assert locations[0].longitude == pytest.approx(-96.89028)
    assert mock_client.get.call_count == 2
