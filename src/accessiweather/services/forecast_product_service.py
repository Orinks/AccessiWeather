"""
Forecast product service — caches NWS text products (AFD / HWO / SPS).

Wraps :func:`accessiweather.weather_client_nws.get_nws_text_product` with a
per-key TTL cache driven by :class:`accessiweather.cache.Cache`. TTLs differ by
product type:

- AFD: 3600 s  (discussions update every ~6 h)
- HWO: 7200 s  (hazardous-weather outlooks update once daily)
- SPS:  900 s  (special statements are time-sensitive)

Failed fetches (:class:`TextProductFetchError`) are NOT cached — the caller
sees the exception and the next call retries.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Literal

from ..cache import Cache
from ..iem_client import (
    fetch_iem_afos_text,
    fetch_iem_spc_mcds,
    fetch_iem_spc_outlook,
    fetch_iem_spc_watches,
    fetch_iem_wpc_mpds,
    fetch_iem_wpc_outlook,
)
from ..models import TextProduct
from ..weather_client_nws import (
    TextProductFetchError,
    get_nws_text_product,
    get_nws_text_product_history,
)

logger = logging.getLogger(__name__)

ProductType = Literal["AFD", "HWO", "SPS"]

# Per-type cache TTLs in seconds. Keyed by product_type; see module docstring
# for rationale.
_PRODUCT_TTLS: dict[str, int] = {
    "AFD": 3600,
    "HWO": 7200,
    "SPS": 900,
}

FetcherResult = TextProduct | list[TextProduct] | None
Fetcher = Callable[..., Awaitable[FetcherResult]]
HistoryFetcher = Callable[..., Awaitable[list[TextProduct]]]


class ForecastProductService:
    """Cache-fronted service for NWS text products."""

    _TTLS = _PRODUCT_TTLS

    def __init__(
        self,
        cache: Cache,
        *,
        fetcher: Fetcher | None = None,
        history_fetcher: HistoryFetcher | None = None,
    ) -> None:
        """
        Initialize the service.

        Args:
            cache: Shared ``Cache`` instance. The service stores entries keyed by
                ``nws_text_product:{product_type}:{cwa_office}``.
            fetcher: Optional async callable with the same signature as
                :func:`get_nws_text_product`. Defaults to the real module-level
                function. Injected primarily for unit tests.
            history_fetcher: Optional async callable with the same signature as
                :func:`get_nws_text_product_history`.

        """
        self._cache = cache
        self._fetcher: Fetcher = fetcher or get_nws_text_product
        self._history_fetcher: HistoryFetcher = history_fetcher or get_nws_text_product_history

    @staticmethod
    def _cache_key(product_type: str, cwa_office: str) -> str:
        return f"nws_text_product:{product_type}:{cwa_office}"

    @staticmethod
    def _history_cache_key(
        product_type: str,
        cwa_office: str,
        limit: int,
        start: datetime | None,
        end: datetime | None,
    ) -> str:
        start_key = start.isoformat() if start is not None else ""
        end_key = end.isoformat() if end is not None else ""
        return f"nws_text_product_history:{product_type}:{cwa_office}:{limit}:{start_key}:{end_key}"

    @staticmethod
    def _iem_cache_key(product_type: str, *parts: object) -> str:
        joined = ":".join(str(part) for part in parts)
        return f"iem_text_product:{product_type}:{joined}"

    async def get(
        self,
        product_type: ProductType,
        cwa_office: str,
        **fetcher_kwargs: Any,
    ) -> FetcherResult:
        """
        Return a cached or freshly-fetched text product.

        On cache hit the stored value is returned directly. On miss the fetcher
        is invoked and the result is cached with the per-type TTL before being
        returned. :class:`TextProductFetchError` from the fetcher propagates
        unchanged and is NOT cached.
        """
        key = self._cache_key(product_type, cwa_office)

        # has_key() distinguishes "cached value that happens to be None/[]"
        # from "cache miss". Call it first, then fetch the value.
        if self._cache.has_key(key):
            return self._cache.get(key)

        try:
            result = await self._fetcher(product_type, cwa_office, **fetcher_kwargs)
        except TextProductFetchError:
            # Do not cache failures — let the next call retry.
            raise

        ttl = self._TTLS.get(product_type, self._cache.default_ttl)
        self._cache.set(key, result, ttl=ttl)
        return result

    async def get_history(
        self,
        product_type: str,
        cwa_office: str,
        *,
        limit: int = 10,
        start: datetime | None = None,
        end: datetime | None = None,
        **fetcher_kwargs: Any,
    ) -> list[TextProduct]:
        """
        Return cached or freshly-fetched NWS text-product history.

        History uses a separate cache namespace from the current-product path so
        current AFD/HWO/SPS fetches never collide with historical listings.
        """
        key = self._history_cache_key(product_type, cwa_office, limit, start, end)

        if self._cache.has_key(key):
            cached = self._cache.get(key)
            if isinstance(cached, list):
                return cached

        history_kwargs: dict[str, Any] = {"limit": limit, **fetcher_kwargs}
        if start is not None:
            history_kwargs["start"] = start
        if end is not None:
            history_kwargs["end"] = end

        try:
            result = await self._history_fetcher(product_type, cwa_office, **history_kwargs)
        except TextProductFetchError:
            raise

        ttl = self._TTLS.get(product_type, self._cache.default_ttl)
        self._cache.set(key, result, ttl=ttl)
        return result

    async def get_iem_afos(self, product_id: str, **kwargs: Any) -> TextProduct:
        """Fetch raw IEM AFOS text for advanced product lookup."""
        return await fetch_iem_afos_text(product_id, **kwargs)

    async def get_iem_spc_outlook(
        self,
        latitude: float,
        longitude: float,
        *,
        day: int = 1,
        current: bool = True,
        valid_at: datetime | None = None,
        max_items: int | None = 5,
        timeout: float = 10.0,
    ) -> TextProduct:
        """Fetch a structured IEM SPC convective outlook summary."""
        valid_key = valid_at.isoformat() if valid_at is not None else ""
        key = self._iem_cache_key(
            "SPC_OUTLOOK", latitude, longitude, day, current, valid_key, max_items
        )
        cached = self._cache.get(key)
        if isinstance(cached, TextProduct):
            return cached
        result = await fetch_iem_spc_outlook(
            latitude,
            longitude,
            day=day,
            current=current,
            valid_at=valid_at,
            max_items=max_items,
            timeout=timeout,
        )
        self._cache.set(key, result, ttl=self._TTLS.get("SPS", 900))
        return result

    async def get_iem_spc_mcds(
        self,
        latitude: float,
        longitude: float,
        *,
        active_only: bool = True,
        start: datetime | None = None,
        end: datetime | None = None,
        max_items: int | None = 5,
        timeout: float = 10.0,
    ) -> TextProduct:
        """Fetch structured IEM SPC mesoscale discussion summaries."""
        start_key = start.isoformat() if start is not None else ""
        end_key = end.isoformat() if end is not None else ""
        key = self._iem_cache_key(
            "SPC_MCD", latitude, longitude, active_only, start_key, end_key, max_items
        )
        cached = self._cache.get(key)
        if isinstance(cached, TextProduct):
            return cached
        result = await fetch_iem_spc_mcds(
            latitude,
            longitude,
            active_only=active_only,
            start=start,
            end=end,
            max_items=max_items,
            timeout=timeout,
        )
        self._cache.set(key, result, ttl=self._TTLS.get("SPS", 900))
        return result

    async def get_iem_spc_watches(
        self,
        latitude: float,
        longitude: float,
        *,
        valid_at: datetime | None = None,
        max_items: int | None = 5,
        timeout: float = 10.0,
    ) -> TextProduct:
        """Fetch structured IEM SPC watch summaries."""
        valid_key = valid_at.isoformat() if valid_at is not None else "latest"
        key = self._iem_cache_key("SPC_WATCHES", latitude, longitude, valid_key, max_items)
        cached = self._cache.get(key)
        if isinstance(cached, TextProduct):
            return cached
        result = await fetch_iem_spc_watches(
            latitude,
            longitude,
            valid_at=valid_at,
            max_items=max_items,
            timeout=timeout,
        )
        self._cache.set(key, result, ttl=self._TTLS.get("SPS", 900))
        return result

    async def get_iem_wpc_outlook(
        self,
        latitude: float,
        longitude: float,
        *,
        day: int = 1,
        valid_at: datetime | None = None,
        limit: int = 1,
        max_items: int | None = 5,
        timeout: float = 10.0,
    ) -> TextProduct:
        """Fetch a structured IEM WPC excessive rainfall outlook summary."""
        valid_key = valid_at.isoformat() if valid_at is not None else "latest"
        key = self._iem_cache_key("WPC_ERO", latitude, longitude, day, valid_key, limit, max_items)
        cached = self._cache.get(key)
        if isinstance(cached, TextProduct):
            return cached
        result = await fetch_iem_wpc_outlook(
            latitude,
            longitude,
            day=day,
            valid_at=valid_at,
            limit=limit,
            max_items=max_items,
            timeout=timeout,
        )
        self._cache.set(key, result, ttl=self._TTLS.get("SPS", 900))
        return result

    async def get_iem_wpc_mpds(
        self,
        latitude: float,
        longitude: float,
        *,
        active_only: bool = True,
        start: datetime | None = None,
        end: datetime | None = None,
        max_items: int | None = 5,
        timeout: float = 10.0,
    ) -> TextProduct:
        """Fetch structured IEM WPC mesoscale precipitation discussion summaries."""
        start_key = start.isoformat() if start is not None else ""
        end_key = end.isoformat() if end is not None else ""
        key = self._iem_cache_key(
            "WPC_MPD", latitude, longitude, active_only, start_key, end_key, max_items
        )
        cached = self._cache.get(key)
        if isinstance(cached, TextProduct):
            return cached
        result = await fetch_iem_wpc_mpds(
            latitude,
            longitude,
            active_only=active_only,
            start=start,
            end=end,
            max_items=max_items,
            timeout=timeout,
        )
        self._cache.set(key, result, ttl=self._TTLS.get("SPS", 900))
        return result
