"""Stream URL provider for NOAA Weather Radio stations."""

from __future__ import annotations


class StreamURLProvider:
    """
    Provides streaming URLs for NOAA Weather Radio stations.

    Maps station call signs to audio stream URLs from various aggregator
    services. Supports multiple URL sources per station for fallback.
    """

    # Known stream URLs for NOAA Weather Radio stations.
    # These are sourced from public aggregators like Broadcastify.
    _STREAM_URLS: dict[str, list[str]] = {
        "WXJ76": [
            "https://broadcastify.cdnstream1.com/33873",
            "https://relay.broadcastify.com/33873",
        ],
        "WXK48": [
            "https://broadcastify.cdnstream1.com/33874",
        ],
        "KWO39": [
            "https://broadcastify.cdnstream1.com/33875",
            "https://relay.broadcastify.com/33875",
        ],
        "WXL58": [
            "https://broadcastify.cdnstream1.com/33876",
        ],
        "WNG634": [
            "https://broadcastify.cdnstream1.com/33877",
        ],
        "KHB60": [
            "https://broadcastify.cdnstream1.com/33878",
        ],
        "WXJ39": [
            "https://broadcastify.cdnstream1.com/33879",
        ],
        "KEC73": [
            "https://broadcastify.cdnstream1.com/33880",
        ],
    }

    # Default URL pattern template using Broadcastify CDN.
    _DEFAULT_PATTERN = "https://broadcastify.cdnstream1.com/noaa/{call_sign}"

    def __init__(
        self,
        custom_urls: dict[str, list[str]] | None = None,
        use_fallback: bool = True,
    ) -> None:
        """
        Initialize the stream URL provider.

        Args:
            custom_urls: Optional dictionary of call_sign -> list of URLs
                to override or supplement the built-in database.
            use_fallback: Whether to generate a fallback URL from the default
                pattern when no known URL exists for a station.

        """
        self._urls: dict[str, list[str]] = dict(self._STREAM_URLS)
        if custom_urls:
            for call_sign, urls in custom_urls.items():
                self._urls[call_sign.upper()] = urls
        self._use_fallback = use_fallback

    def get_stream_url(self, call_sign: str) -> str | None:
        """
        Get the primary stream URL for a station.

        Args:
            call_sign: The station call sign (case-insensitive).

        Returns:
            The primary stream URL string, or None if no URL is available.

        """
        urls = self.get_stream_urls(call_sign)
        return urls[0] if urls else None

    def get_stream_urls(self, call_sign: str) -> list[str]:
        """
        Get all available stream URLs for a station.

        Returns multiple URLs for fallback purposes. The first URL in the
        list is considered the primary/preferred source.

        Args:
            call_sign: The station call sign (case-insensitive).

        Returns:
            A list of stream URL strings. Empty list if no URLs are available.

        """
        normalized = call_sign.upper().strip()
        if not normalized:
            return []

        urls = self._urls.get(normalized)
        if urls:
            return list(urls)

        if self._use_fallback:
            return [self._DEFAULT_PATTERN.format(call_sign=normalized)]

        return []

    def has_known_url(self, call_sign: str) -> bool:
        """
        Check if a station has a known (non-fallback) stream URL.

        Args:
            call_sign: The station call sign (case-insensitive).

        Returns:
            True if the station has known stream URLs in the database.

        """
        return call_sign.upper().strip() in self._urls
