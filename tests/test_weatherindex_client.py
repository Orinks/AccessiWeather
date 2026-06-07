"""Tests for WeatherIndex NOAA radio stream resolution."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import requests

from accessiweather.noaa_radio.weatherindex_client import WeatherIndexClient


class TestWeatherIndexClient:
    """Tests for the WeatherIndex client."""

    def _make_client(self, json_data: Any, **kwargs) -> WeatherIndexClient:
        session = MagicMock(spec=requests.Session)
        response = MagicMock()
        response.json.return_value = json_data
        response.raise_for_status.return_value = None
        session.get.return_value = response
        return WeatherIndexClient(session=session, **kwargs)

    def test_get_stream_urls_parses_feed_urls(self) -> None:
        client = self._make_client(
            {
                "station": {
                    "call_sign": "WXJ76",
                    "feeds": [
                        {"stream_url": "https://audio.example.com/live"},
                        {"stream_url": "https://audio.example.com/backup"},
                    ],
                }
            }
        )

        assert client.get_stream_urls("WXJ76") == [
            "https://audio.example.com/live",
            "https://audio.example.com/backup",
        ]

    def test_get_stream_urls_deduplicates_and_skips_empty_values(self) -> None:
        client = self._make_client(
            {
                "feeds": [
                    {"stream_url": "https://audio.example.com/live"},
                    {"stream_url": "  "},
                    {"stream_url": "https://audio.example.com/live"},
                    {},
                ]
            }
        )

        assert client.get_stream_urls("WXJ76") == ["https://audio.example.com/live"]

    def test_get_stream_urls_returns_empty_on_network_error(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.ConnectionError("fail")
        client = WeatherIndexClient(session=session)

        assert client.get_stream_urls("WXJ76") == []

    def test_get_stream_urls_returns_empty_on_malformed_payload(self) -> None:
        client = self._make_client({"feeds": "bad-data"})

        assert client.get_stream_urls("WXJ76") == []

    def test_get_stream_urls_uses_per_station_cache(self) -> None:
        client = self._make_client(
            {"feeds": [{"stream_url": "https://audio.example.com/live"}]},
            cache_ttl=60,
        )

        first = client.get_stream_urls("WXJ76")
        second = client.get_stream_urls("WXJ76")

        assert first == second
        client._session.get.assert_called_once()  # type: ignore[union-attr]

    def test_get_stream_urls_refetches_after_cache_expiry(self) -> None:
        client = self._make_client(
            {"feeds": [{"stream_url": "https://audio.example.com/live"}]},
            cache_ttl=1,
        )

        client.get_stream_urls("WXJ76")
        client._cache["WXJ76"] = (["https://audio.example.com/live"], time.monotonic() - 2)

        client.get_stream_urls("WXJ76")

        assert client._session.get.call_count == 2  # type: ignore[union-attr]

    def test_get_station_metadata_parses_coverage_fields(self) -> None:
        client = self._make_client(
            {
                "callsign": "WXK27",
                "wfo": "Austin/San Antonio TX",
                "latitude": 30.3219,
                "longitude": -97.8033,
                "served_counties": [
                    {
                        "county": "Travis",
                        "same_code": "048453",
                        "state": "TX",
                        "area": "All",
                    }
                ],
            }
        )

        metadata = client.get_station_metadata("wxk27")

        assert metadata is not None
        assert metadata.call_sign == "WXK27"
        assert metadata.wfo == "Austin/San Antonio TX"
        assert metadata.latitude == 30.3219
        assert metadata.longitude == -97.8033
        assert metadata.served_counties[0].same_code == "048453"

    def test_get_station_metadata_returns_none_for_blank_call_sign_without_network(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = WeatherIndexClient(session=session)

        assert client.get_station_metadata("   ") is None
        session.get.assert_not_called()

    def test_get_station_metadata_uses_per_station_cache(self) -> None:
        client = self._make_client(
            {
                "callsign": "WXK27",
                "served_counties": [
                    {"county": "Travis", "same_code": "048453", "state": "TX"},
                ],
            },
            cache_ttl=60,
        )

        first = client.get_station_metadata("WXK27")
        second = client.get_station_metadata("WXK27")

        assert first == second
        client._session.get.assert_called_once()  # type: ignore[union-attr]

    def test_get_station_metadata_refetches_after_cache_expiry(self) -> None:
        client = self._make_client(
            {
                "callsign": "WXK27",
                "served_counties": [
                    {"county": "Travis", "same_code": "048453", "state": "TX"},
                ],
            },
            cache_ttl=1,
        )

        client.get_station_metadata("WXK27")
        client._metadata_cache["WXK27"] = (None, time.monotonic() - 2)
        client.get_station_metadata("WXK27")

        assert client._session.get.call_count == 2  # type: ignore[union-attr]

    def test_get_station_metadata_returns_none_on_network_error(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.ConnectionError("fail")
        client = WeatherIndexClient(session=session)

        assert client.get_station_metadata("WXK27") is None

    def test_get_station_metadata_returns_none_on_malformed_payload(self) -> None:
        client = self._make_client(["not", "a", "station"])

        assert client.get_station_metadata("WXK27") is None

    def test_get_station_metadata_skips_incomplete_counties_and_normalizes_fields(self) -> None:
        client = self._make_client(
            {
                "station": {
                    "call_sign": " wxk27 ",
                    "wfo": "  Austin/San Antonio TX ",
                    "latitude": "bad-latitude",
                    "longitude": None,
                    "served_counties": [
                        "not-a-dict",
                        {"county": "Travis", "same_code": "abc", "state": "TX"},
                        {"county": "Travis", "same_code": "048453"},
                        {"county": " Travis ", "same_code": 48453, "state": " tx ", "area": " "},
                    ],
                }
            }
        )

        metadata = client.get_station_metadata("WXK27")

        assert metadata is not None
        assert metadata.call_sign == "WXK27"
        assert metadata.wfo == "Austin/San Antonio TX"
        assert metadata.latitude is None
        assert metadata.longitude is None
        assert len(metadata.served_counties) == 1
        county = metadata.served_counties[0]
        assert county.county == "Travis"
        assert county.same_code == "048453"
        assert county.state == "TX"
        assert county.area is None

    def test_get_station_metadata_allows_empty_coverage_payload(self) -> None:
        client = self._make_client({"feeds": []})

        metadata = client.get_station_metadata("WXJ76")

        assert metadata is not None
        assert metadata.served_counties == ()
