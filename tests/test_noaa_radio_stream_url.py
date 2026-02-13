"""Tests for NOAA Weather Radio stream URL provider."""

from accessiweather.noaa_radio.stream_url import StreamURLProvider


class TestStreamURLProvider:
    """Tests for StreamURLProvider."""

    def test_get_stream_url_known_station(self) -> None:
        """Known station returns a URL string."""
        provider = StreamURLProvider()
        url = provider.get_stream_url("WXJ76")
        assert url is not None
        assert isinstance(url, str)
        assert url.startswith("https://")

    def test_get_stream_url_case_insensitive(self) -> None:
        """Call signs are case-insensitive."""
        provider = StreamURLProvider()
        assert provider.get_stream_url("wxj76") == provider.get_stream_url("WXJ76")

    def test_get_stream_url_unknown_with_fallback(self) -> None:
        """Unknown station with fallback enabled returns a generated URL."""
        provider = StreamURLProvider(use_fallback=True)
        url = provider.get_stream_url("UNKNOWN99")
        assert url is not None
        assert "UNKNOWN99" in url

    def test_get_stream_url_unknown_without_fallback(self) -> None:
        """Unknown station with fallback disabled returns None."""
        provider = StreamURLProvider(use_fallback=False)
        url = provider.get_stream_url("UNKNOWN99")
        assert url is None

    def test_get_stream_urls_known_station(self) -> None:
        """Known station with multiple URLs returns all of them."""
        provider = StreamURLProvider()
        urls = provider.get_stream_urls("WXJ76")
        assert isinstance(urls, list)
        assert len(urls) >= 1

    def test_get_stream_urls_unknown_without_fallback(self) -> None:
        """Unknown station without fallback returns empty list."""
        provider = StreamURLProvider(use_fallback=False)
        urls = provider.get_stream_urls("UNKNOWN99")
        assert urls == []

    def test_get_stream_urls_unknown_with_fallback(self) -> None:
        """Unknown station with fallback returns list with one fallback URL."""
        provider = StreamURLProvider(use_fallback=True)
        urls = provider.get_stream_urls("UNKNOWN99")
        assert len(urls) == 1

    def test_get_stream_urls_returns_copy(self) -> None:
        """Returned list is a copy, not a reference to internal data."""
        provider = StreamURLProvider()
        urls1 = provider.get_stream_urls("WXJ76")
        urls1.append("http://modified.example.com")
        urls2 = provider.get_stream_urls("WXJ76")
        assert "http://modified.example.com" not in urls2

    def test_custom_urls_override(self) -> None:
        """Custom URLs override built-in ones."""
        custom = {"WXJ76": ["https://custom.example.com/stream"]}
        provider = StreamURLProvider(custom_urls=custom)
        url = provider.get_stream_url("WXJ76")
        assert url == "https://custom.example.com/stream"

    def test_custom_urls_add_new_station(self) -> None:
        """Custom URLs can add stations not in the built-in database."""
        custom = {"NEWSTATION": ["https://new.example.com/stream"]}
        provider = StreamURLProvider(custom_urls=custom, use_fallback=False)
        url = provider.get_stream_url("NEWSTATION")
        assert url == "https://new.example.com/stream"

    def test_has_known_url_true(self) -> None:
        """has_known_url returns True for known stations."""
        provider = StreamURLProvider()
        assert provider.has_known_url("WXJ76") is True

    def test_has_known_url_false(self) -> None:
        """has_known_url returns False for unknown stations."""
        provider = StreamURLProvider()
        assert provider.has_known_url("UNKNOWN99") is False

    def test_empty_call_sign(self) -> None:
        """Empty call sign returns None/empty list."""
        provider = StreamURLProvider()
        assert provider.get_stream_url("") is None
        assert provider.get_stream_urls("") == []

    def test_whitespace_call_sign(self) -> None:
        """Whitespace-padded call sign is normalized."""
        provider = StreamURLProvider()
        assert provider.get_stream_url("  WXJ76  ") == provider.get_stream_url("WXJ76")
