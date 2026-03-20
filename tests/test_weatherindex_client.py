"""Tests for WeatherIndex NOAA radio stream resolution."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import requests

from accessiweather.noaa_radio.weatherindex_client import WeatherIndexClient


class TestWeatherIndexClient:
    """Tests for the WeatherIndex client."""

    def _make_client(self, json_data: dict, **kwargs) -> WeatherIndexClient:
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
