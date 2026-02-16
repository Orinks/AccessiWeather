"""Tests for WxRadioClient and wxradio.org integration with StreamURLProvider."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import requests

from accessiweather.noaa_radio.stream_url import StreamURLProvider
from accessiweather.noaa_radio.wxradio_client import (
    WxRadioClient,
    _extract_call_sign,
)

# -- Call sign extraction tests --


class TestExtractCallSign:
    """Tests for the _extract_call_sign helper."""

    def test_standard_mount(self) -> None:
        assert _extract_call_sign("/FL-Tallahassee-KIH24") == "KIH24"

    def test_multi_word_city(self) -> None:
        assert _extract_call_sign("/MI-MountPleasant-KZZ33") == "KZZ33"

    def test_alt_suffix_ignored(self) -> None:
        assert _extract_call_sign("/MI-MountPleasant-KZZ33-alt2") == "KZZ33"

    def test_single_letter_suffix(self) -> None:
        assert _extract_call_sign("/NE-Omaha-KIH61-A") == "KIH61"

    def test_canadian_call_sign(self) -> None:
        assert _extract_call_sign("/AB-Calgary-XLF339") == "XLF339"

    def test_alt1_suffix(self) -> None:
        assert _extract_call_sign("/NY-Middleville-WXM45-alt1") == "WXM45"

    def test_no_leading_slash(self) -> None:
        assert _extract_call_sign("FL-Tallahassee-KIH24") == "KIH24"

    def test_too_few_parts(self) -> None:
        assert _extract_call_sign("/SomeMount") is None

    def test_empty_string(self) -> None:
        assert _extract_call_sign("") is None

    def test_no_call_sign_match(self) -> None:
        assert _extract_call_sign("/XX-City-nocallsign") is None

    def test_uppercase_normalization(self) -> None:
        assert _extract_call_sign("/fl-tallahassee-kih24") == "KIH24"

    def test_alt_suffix_with_ALT(self) -> None:
        assert _extract_call_sign("/GA-Atlanta-KEC80-ALT") == "KEC80"


# -- Sample Icecast JSON responses --

SAMPLE_ICECAST_RESPONSE = {
    "icestats": {
        "source": [
            {
                "listenurl": "http://wxradio.org:8000/FL-Tallahassee-KIH24",
                "server_name": "FL-Tallahassee-KIH24",
            },
            {
                "listenurl": "http://wxradio.org:8000/GA-Atlanta-KEC80",
                "server_name": "GA-Atlanta-KEC80",
            },
            {
                "listenurl": "http://wxradio.org:8000/AB-Calgary-XLF339",
                "server_name": "AB-Calgary-XLF339",
            },
        ]
    }
}

SINGLE_SOURCE_RESPONSE = {
    "icestats": {
        "source": {
            "listenurl": "http://wxradio.org:8000/FL-Tallahassee-KIH24",
            "server_name": "FL-Tallahassee-KIH24",
        }
    }
}

EMPTY_RESPONSE: dict = {"icestats": {"source": []}}

MALFORMED_RESPONSE: dict = {"unexpected": "data"}


# -- WxRadioClient tests --


class TestWxRadioClient:
    """Tests for the WxRadioClient class."""

    def _make_client(self, json_data: dict, **kwargs) -> WxRadioClient:
        session = MagicMock(spec=requests.Session)
        response = MagicMock()
        response.json.return_value = json_data
        response.raise_for_status.return_value = None
        session.get.return_value = response
        return WxRadioClient(session=session, **kwargs)

    def test_parse_multiple_sources(self) -> None:
        client = self._make_client(SAMPLE_ICECAST_RESPONSE)
        streams = client.get_streams()
        assert "KIH24" in streams
        assert "KEC80" in streams
        assert "XLF339" in streams
        assert streams["KIH24"] == ["https://wxradio.org/FL-Tallahassee-KIH24"]

    def test_parse_single_source(self) -> None:
        client = self._make_client(SINGLE_SOURCE_RESPONSE)
        streams = client.get_streams()
        assert "KIH24" in streams

    def test_empty_sources(self) -> None:
        client = self._make_client(EMPTY_RESPONSE)
        assert client.get_streams() == {}

    def test_malformed_response(self) -> None:
        client = self._make_client(MALFORMED_RESPONSE)
        assert client.get_streams() == {}

    def test_cache_returns_same_data(self) -> None:
        client = self._make_client(SAMPLE_ICECAST_RESPONSE)
        first = client.get_streams()
        second = client.get_streams()
        assert first == second
        # Session.get should only be called once due to caching
        client._session.get.assert_called_once()  # type: ignore[union-attr]

    def test_cache_expiry(self) -> None:
        client = self._make_client(SAMPLE_ICECAST_RESPONSE, cache_ttl=1)
        client.get_streams()
        # Manually expire the cache
        client._cache_time = time.monotonic() - 2
        client.get_streams()
        assert client._session.get.call_count == 2  # type: ignore[union-attr]

    def test_invalidate_cache(self) -> None:
        client = self._make_client(SAMPLE_ICECAST_RESPONSE)
        client.get_streams()
        client.invalidate_cache()
        assert client._cache is None

    def test_network_error_returns_empty(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.ConnectionError("fail")
        client = WxRadioClient(session=session)
        assert client.get_streams() == {}

    def test_network_error_returns_stale_cache(self) -> None:
        client = self._make_client(SAMPLE_ICECAST_RESPONSE, cache_ttl=0)
        first = client.get_streams()
        assert len(first) > 0

        # Now make it fail
        client._session.get.side_effect = requests.ConnectionError("fail")  # type: ignore[union-attr]
        client._cache_time = 0  # Force stale
        second = client.get_streams()
        assert second == first

    def test_timeout_error(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.Timeout("timeout")
        client = WxRadioClient(session=session)
        assert client.get_streams() == {}

    def test_duplicate_call_sign_deduplication(self) -> None:
        """Multiple mounts for same call sign should deduplicate URLs."""
        data = {
            "icestats": {
                "source": [
                    {
                        "listenurl": "http://wxradio.org:8000/FL-Tallahassee-KIH24",
                        "server_name": "FL-Tallahassee-KIH24",
                    },
                    {
                        "listenurl": "http://wxradio.org:8000/FL-Tallahassee-KIH24",
                        "server_name": "FL-Tallahassee-KIH24",
                    },
                ]
            }
        }
        client = self._make_client(data)
        streams = client.get_streams()
        assert len(streams["KIH24"]) == 1

    def test_source_without_listenurl_uses_server_name(self) -> None:
        data = {
            "icestats": {
                "source": [
                    {"server_name": "FL-Tallahassee-KIH24"},
                ]
            }
        }
        client = self._make_client(data)
        streams = client.get_streams()
        assert "KIH24" in streams

    def test_source_with_no_usable_fields_skipped(self) -> None:
        data = {"icestats": {"source": [{"bitrate": 128}]}}
        client = self._make_client(data)
        assert client.get_streams() == {}


# -- StreamURLProvider integration tests --


class TestStreamURLProviderWithWxRadio:
    """Tests for StreamURLProvider using WxRadioClient."""

    def _make_mock_client(self, streams: dict[str, list[str]]) -> WxRadioClient:
        client = MagicMock(spec=WxRadioClient)
        client.get_streams.return_value = streams
        return client

    def test_dynamic_urls_first(self) -> None:
        mock = self._make_mock_client({"KIH24": ["https://wxradio.org/FL-Tallahassee-KIH24"]})
        provider = StreamURLProvider(wxradio_client=mock)
        urls = provider.get_stream_urls("KIH24")
        assert urls[0] == "https://wxradio.org/FL-Tallahassee-KIH24"
        # Static URLs should follow
        assert len(urls) > 1

    def test_dynamic_dedup_with_static(self) -> None:
        """Dynamic URL that's also in static should not appear twice."""
        mock = self._make_mock_client({"KIH24": ["https://wxradio.org/FL-Tallahassee-KIH24"]})
        provider = StreamURLProvider(wxradio_client=mock)
        urls = provider.get_stream_urls("KIH24")
        assert urls.count("https://wxradio.org/FL-Tallahassee-KIH24") == 1

    def test_fallback_to_static_on_empty_dynamic(self) -> None:
        mock = self._make_mock_client({})
        provider = StreamURLProvider(wxradio_client=mock)
        urls = provider.get_stream_urls("KIH24")
        # Should return static URLs
        assert len(urls) > 0
        assert "wxradio.org/FL-Tallahassee-KIH24" in urls[0]

    def test_fallback_on_client_error(self) -> None:
        mock = MagicMock(spec=WxRadioClient)
        mock.get_streams.side_effect = Exception("boom")
        provider = StreamURLProvider(wxradio_client=mock)
        urls = provider.get_stream_urls("KIH24")
        assert len(urls) > 0

    def test_no_wxradio_client_works_as_before(self) -> None:
        provider = StreamURLProvider()
        urls = provider.get_stream_urls("KIH24")
        assert len(urls) > 0

    def test_dynamic_only_station(self) -> None:
        """Station only in dynamic data, not in static."""
        mock = self._make_mock_client({"ZZTEST": ["https://wxradio.org/XX-Test-ZZTEST"]})
        provider = StreamURLProvider(wxradio_client=mock, use_fallback=False)
        urls = provider.get_stream_urls("ZZTEST")
        assert urls == ["https://wxradio.org/XX-Test-ZZTEST"]

    def test_has_known_url_unchanged(self) -> None:
        provider = StreamURLProvider()
        assert provider.has_known_url("KIH24") is True
        assert provider.has_known_url("NONEXISTENT") is False
