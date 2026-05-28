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


def _make_nws_response(payload: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
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


@pytest.mark.asyncio
async def test_reverse_geocode_coordinates_uses_nws_relative_location() -> None:
    manager = LocationManager()

    with patch("accessiweather.location_manager.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = _make_nws_response(
            {
                "properties": {
                    "relativeLocation": {
                        "properties": {
                            "city": "Mount Holly",
                            "state": "NJ",
                        }
                    },
                    "timeZone": "America/New_York",
                }
            }
        )

        location = await manager.reverse_geocode_coordinates(39.9571, -74.8069)

    assert location is not None
    assert location.name == "Mount Holly, NJ"
    assert location.latitude == pytest.approx(39.9571)
    assert location.longitude == pytest.approx(-74.8069)
    assert location.country_code == "US"
    assert location.timezone == "America/New_York"


@pytest.mark.asyncio
async def test_reverse_geocode_coordinates_returns_none_when_nws_cannot_name_point() -> None:
    manager = LocationManager()

    with patch("accessiweather.location_manager.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = _make_nws_response({"properties": {}}, status_code=404)

        location = await manager.reverse_geocode_coordinates(51.5074, -0.1278)

    assert location is None


@pytest.mark.asyncio
async def test_reverse_geocode_coordinates_uses_nominatim_for_international_point() -> None:
    manager = LocationManager()

    with patch("accessiweather.location_manager.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = [
            _make_nws_response({"properties": {}}, status_code=404),
            _make_nws_response(
                {
                    "display_name": "London, Greater London, England, United Kingdom",
                    "address": {
                        "city": "London",
                        "state": "England",
                        "country": "United Kingdom",
                        "country_code": "gb",
                    },
                }
            ),
        ]

        location = await manager.reverse_geocode_coordinates(51.5074, -0.1278)

    assert location is not None
    assert location.name == "London, England, United Kingdom"
    assert location.latitude == pytest.approx(51.5074)
    assert location.longitude == pytest.approx(-0.1278)
    assert location.country_code == "GB"
    assert mock_client.get.call_count == 2
    assert mock_client.get.call_args_list[1].args == (
        "https://nominatim.openstreetmap.org/reverse",
    )
    assert mock_client.get.call_args_list[1].kwargs["params"] == {
        "format": "jsonv2",
        "lat": 51.5074,
        "lon": -0.1278,
        "zoom": 10,
        "addressdetails": 1,
        "accept-language": "en",
    }


@pytest.mark.asyncio
async def test_reverse_geocode_coordinates_uses_country_when_no_city_available() -> None:
    manager = LocationManager()

    with patch("accessiweather.location_manager.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = [
            _make_nws_response({"properties": {}}, status_code=404),
            _make_nws_response(
                {
                    "display_name": "Iceland",
                    "address": {
                        "country": "Iceland",
                        "country_code": "is",
                    },
                }
            ),
        ]

        location = await manager.reverse_geocode_coordinates(64.9631, -19.0208)

    assert location is not None
    assert location.name == "Iceland"
    assert location.country_code == "IS"


@pytest.mark.asyncio
async def test_reverse_geocode_coordinates_returns_none_when_nominatim_times_out() -> None:
    manager = LocationManager()

    with patch("accessiweather.location_manager.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = [
            _make_nws_response({"properties": {}}, status_code=404),
            TimeoutError("timed out"),
        ]

        location = await manager.reverse_geocode_coordinates(51.5074, -0.1278)

    assert location is None


@pytest.mark.asyncio
async def test_reverse_geocode_coordinates_returns_none_for_bad_nominatim_payload() -> None:
    manager = LocationManager()

    invalid_json_response = _make_nws_response({}, status_code=200)
    invalid_json_response.json.side_effect = ValueError("not json")
    non_object_response = _make_nws_response(["not", "an", "object"], status_code=200)
    empty_name_response = _make_nws_response({"address": {}}, status_code=200)

    for response in (invalid_json_response, non_object_response, empty_name_response):
        with patch("accessiweather.location_manager.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                _make_nws_response({"properties": {}}, status_code=404),
                response,
            ]

            location = await manager.reverse_geocode_coordinates(51.5074, -0.1278)

        assert location is None


def test_format_nominatim_location_name_falls_back_to_display_name() -> None:
    manager = LocationManager()

    name = manager._format_nominatim_location_name(
        {
            "display_name": "Coordinates near Antarctica",
            "address": None,
        }
    )

    assert name == "Coordinates near Antarctica"
