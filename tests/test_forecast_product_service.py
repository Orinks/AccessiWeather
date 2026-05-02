"""
Tests for :class:`ForecastProductService`.

Covers:
- Caching behaviour with per-type TTLs (AFD 3600s, HWO 7200s, SPS 900s)
- Cache-key uniqueness across ``product_type`` and ``cwa_office``
- Empty SPS returns ``[]`` (not ``None``)
- ``TextProductFetchError`` propagates and is NOT cached
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from accessiweather.cache import Cache
from accessiweather.iem_client import IemProductFetchError
from accessiweather.models import TextProduct
from accessiweather.services.forecast_product_service import ForecastProductService
from accessiweather.weather_client_nws import TextProductFetchError


def _afd(office: str = "PHI", product_id: str = "afd-1") -> TextProduct:
    return TextProduct(
        product_type="AFD",
        product_id=product_id,
        cwa_office=office,
        issuance_time=datetime(2026, 4, 16, 14, 32, 0, tzinfo=UTC),
        product_text="AFD TEXT",
        headline=None,
    )


def _sps(office: str = "PHI", product_id: str = "sps-1") -> TextProduct:
    return TextProduct(
        product_type="SPS",
        product_id=product_id,
        cwa_office=office,
        issuance_time=datetime(2026, 4, 16, 14, 32, 0, tzinfo=UTC),
        product_text="SPS TEXT",
        headline="Special Weather Statement",
    )


class TestForecastProductServiceCaching:
    @pytest.mark.asyncio
    async def test_repeat_calls_within_ttl_hit_cache(self):
        cache = Cache()
        fetcher = AsyncMock(return_value=_afd())
        service = ForecastProductService(cache, fetcher=fetcher)

        r1 = await service.get("AFD", "PHI")
        r2 = await service.get("AFD", "PHI")

        assert r1 is r2
        fetcher.assert_called_once()

    @pytest.mark.asyncio
    async def test_per_type_ttl_afd_cached_sps_refetched(self, monkeypatch):
        """At t+1000s: AFD (TTL 3600) stays cached; SPS (TTL 900) refetches."""
        cache = Cache()
        fetcher = AsyncMock(
            side_effect=lambda pt, office, **kw: _afd() if pt == "AFD" else [_sps()]
        )
        service = ForecastProductService(cache, fetcher=fetcher)

        # t=0
        fake_time = [1_000_000.0]
        monkeypatch.setattr("accessiweather.cache.time.time", lambda: fake_time[0])

        await service.get("AFD", "PHI")
        await service.get("SPS", "PHI")
        assert fetcher.call_count == 2

        # Advance 1000 seconds: AFD still alive (3600s), SPS expired (900s).
        fake_time[0] += 1000

        await service.get("AFD", "PHI")  # cache hit -> no new call
        await service.get("SPS", "PHI")  # cache miss -> one new call

        assert fetcher.call_count == 3  # one extra call for SPS refetch


class TestForecastProductServiceCacheKeys:
    @pytest.mark.asyncio
    async def test_different_offices_do_not_collide(self):
        cache = Cache()

        def side_effect(product_type, office, **_kw):
            return _afd(office=office, product_id=f"afd-{office}")

        fetcher = AsyncMock(side_effect=side_effect)
        service = ForecastProductService(cache, fetcher=fetcher)

        r_phi = await service.get("AFD", "PHI")
        r_okx = await service.get("AFD", "OKX")

        assert isinstance(r_phi, TextProduct)
        assert isinstance(r_okx, TextProduct)
        assert r_phi.cwa_office == "PHI"
        assert r_okx.cwa_office == "OKX"
        assert fetcher.call_count == 2

    @pytest.mark.asyncio
    async def test_different_product_types_do_not_collide(self):
        cache = Cache()

        def side_effect(product_type, office, **_kw):
            if product_type == "SPS":
                return [_sps(office=office)]
            return TextProduct(
                product_type=product_type,
                product_id=f"{product_type}-1",
                cwa_office=office,
                issuance_time=datetime(2026, 4, 16, 14, 32, 0, tzinfo=UTC),
                product_text=f"{product_type} TEXT",
                headline=None,
            )

        fetcher = AsyncMock(side_effect=side_effect)
        service = ForecastProductService(cache, fetcher=fetcher)

        afd = await service.get("AFD", "PHI")
        hwo = await service.get("HWO", "PHI")
        sps = await service.get("SPS", "PHI")

        assert isinstance(afd, TextProduct) and afd.product_type == "AFD"
        assert isinstance(hwo, TextProduct) and hwo.product_type == "HWO"
        assert isinstance(sps, list)
        assert fetcher.call_count == 3


class TestForecastProductServiceEmpty:
    @pytest.mark.asyncio
    async def test_empty_sps_returns_list_not_none(self):
        cache = Cache()
        fetcher = AsyncMock(return_value=[])
        service = ForecastProductService(cache, fetcher=fetcher)

        result = await service.get("SPS", "PHI")

        assert result == []
        assert isinstance(result, list)
        # Cached properly — second call still returns [] without refetching.
        result2 = await service.get("SPS", "PHI")
        assert result2 == []
        fetcher.assert_called_once()


class TestForecastProductServiceErrorPropagation:
    @pytest.mark.asyncio
    async def test_fetch_error_propagates_and_is_not_cached(self):
        cache = Cache()
        fetcher = AsyncMock(side_effect=TextProductFetchError("boom"))
        service = ForecastProductService(cache, fetcher=fetcher)

        with pytest.raises(TextProductFetchError):
            await service.get("AFD", "PHI")

        # The failure must NOT have been cached: a second call re-invokes the fetcher.
        with pytest.raises(TextProductFetchError):
            await service.get("AFD", "PHI")

        assert fetcher.call_count == 2


class TestForecastProductServiceHistory:
    @pytest.mark.asyncio
    async def test_history_uses_separate_cache_key(self):
        cache = Cache()
        fetcher = AsyncMock(return_value=_afd(product_id="current"))
        history_fetcher = AsyncMock(return_value=[_afd(product_id="old")])
        service = ForecastProductService(
            cache,
            fetcher=fetcher,
            history_fetcher=history_fetcher,
        )

        current = await service.get("AFD", "PHI")
        history = await service.get_history("AFD", "PHI", limit=10)

        assert isinstance(current, TextProduct)
        assert current.product_id == "current"
        assert [p.product_id for p in history] == ["old"]
        fetcher.assert_called_once()
        history_fetcher.assert_called_once_with("AFD", "PHI", limit=10)

        cached_history = await service.get_history("AFD", "PHI", limit=10)
        assert cached_history is history
        history_fetcher.assert_called_once()


class TestForecastProductServiceIemStructuredProducts:
    @pytest.mark.asyncio
    async def test_iem_structured_wrappers_delegate(self, monkeypatch):
        cache = Cache(default_ttl=60)
        service = ForecastProductService(cache)
        product = TextProduct(
            product_type="SPC_WATCHES",
            product_id="structured",
            cwa_office="SPC",
            issuance_time=None,
            product_text="structured text",
            headline=None,
        )

        async def fake_spc_watches(lat, lon, **kwargs):
            assert lat == 35.78
            assert lon == -78.64
            assert kwargs["valid_at"] is None
            assert kwargs["max_items"] == 5
            assert kwargs["timeout"] == 10.0
            return product

        async def fake_wpc_outlook(lat, lon, **kwargs):
            assert lat == 35.78
            assert lon == -78.64
            assert kwargs["day"] == 2
            assert kwargs["limit"] == 3
            assert kwargs["max_items"] == 5
            assert kwargs["timeout"] == 10.0
            return product

        async def fake_wpc_mpds(lat, lon, **kwargs):
            assert lat == 35.78
            assert lon == -78.64
            assert kwargs == {"max_items": 5, "timeout": 10.0}
            return product

        monkeypatch.setattr(
            "accessiweather.services.forecast_product_service.fetch_iem_spc_watches",
            fake_spc_watches,
        )
        monkeypatch.setattr(
            "accessiweather.services.forecast_product_service.fetch_iem_wpc_outlook",
            fake_wpc_outlook,
        )
        monkeypatch.setattr(
            "accessiweather.services.forecast_product_service.fetch_iem_wpc_mpds",
            fake_wpc_mpds,
        )

        assert await service.get_iem_spc_watches(35.78, -78.64) is product
        assert await service.get_iem_wpc_outlook(35.78, -78.64, day=2, limit=3) is product
        assert await service.get_iem_wpc_mpds(35.78, -78.64) is product

    @pytest.mark.asyncio
    async def test_iem_structured_wrappers_cache_results(self, monkeypatch):
        cache = Cache(default_ttl=60)
        service = ForecastProductService(cache)
        product = TextProduct(
            product_type="SPC_MCD",
            product_id="structured",
            cwa_office="SPC",
            issuance_time=None,
            product_text="structured text",
            headline=None,
        )
        calls = 0

        async def fake_spc_mcds(lat, lon, **kwargs):
            nonlocal calls
            calls += 1
            return product

        monkeypatch.setattr(
            "accessiweather.services.forecast_product_service.fetch_iem_spc_mcds",
            fake_spc_mcds,
        )

        assert await service.get_iem_spc_mcds(35.78, -78.64, max_items=3) is product
        assert await service.get_iem_spc_mcds(35.78, -78.64, max_items=3) is product
        assert calls == 1

    @pytest.mark.asyncio
    async def test_spc_outlook_does_not_fall_back_to_national_afos(self, monkeypatch):
        cache = Cache(default_ttl=60)
        service = ForecastProductService(cache)

        async def failing_spc_outlook(*_args, **_kwargs):
            raise IemProductFetchError("slow")

        async def fake_afos(product_id, **kwargs):
            raise AssertionError("SPC point outlooks must not fall back to national AFOS text")

        monkeypatch.setattr(
            "accessiweather.services.forecast_product_service.fetch_iem_spc_outlook",
            failing_spc_outlook,
        )
        monkeypatch.setattr(
            "accessiweather.services.forecast_product_service.fetch_iem_afos_text",
            fake_afos,
        )

        with pytest.raises(IemProductFetchError, match="slow"):
            await service.get_iem_spc_outlook(
                35.78,
                -78.64,
                day=1,
                current=True,
                timeout=4.0,
            )
