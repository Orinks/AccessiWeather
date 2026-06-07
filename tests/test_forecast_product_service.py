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


def _srf(office: str = "PHI", product_id: str = "srf-1") -> TextProduct:
    return TextProduct(
        product_type="SRF",
        product_id=product_id,
        cwa_office=office,
        issuance_time=datetime(2026, 4, 16, 14, 32, 0, tzinfo=UTC),
        product_text="SURF ZONE FORECAST\nNew Jersey beaches...",
        headline="Surf Zone Forecast",
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
        srf = await service.get("SRF", "PHI")

        assert isinstance(afd, TextProduct) and afd.product_type == "AFD"
        assert isinstance(hwo, TextProduct) and hwo.product_type == "HWO"
        assert isinstance(sps, list)
        assert isinstance(srf, TextProduct) and srf.product_type == "SRF"
        assert fetcher.call_count == 4


class TestForecastProductServiceSurfConditions:
    @pytest.mark.asyncio
    async def test_official_srf_preferred_over_derived_conditions(self):
        cache = Cache()
        fetcher = AsyncMock(return_value=_srf())
        openmeteo = AsyncMock(
            return_value=TextProduct(
                product_type="SURF_CONDITIONS",
                product_id="openmeteo",
                cwa_office="Open-Meteo Marine",
                issuance_time=None,
                product_text="derived",
                headline="Surf conditions from Open-Meteo Marine",
            )
        )
        pirate = AsyncMock(return_value=None)
        service = ForecastProductService(
            cache,
            fetcher=fetcher,
            openmeteo_marine_fetcher=openmeteo,
            pirate_beach_fetcher=pirate,
        )
        location = type("Location", (), {"name": "Lumberton", "cwa_office": "PHI"})()

        result = await service.get_surf_conditions_for_location(location)

        assert isinstance(result, TextProduct)
        assert result.product_type == "SRF"
        assert "SURF ZONE FORECAST" in result.product_text
        fetcher.assert_awaited_once_with("SRF", "PHI")
        openmeteo.assert_not_awaited()
        pirate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_openmeteo_marine_used_when_official_srf_missing(self):
        cache = Cache()
        fetcher = AsyncMock(return_value=None)
        openmeteo_product = TextProduct(
            product_type="SURF_CONDITIONS",
            product_id="openmeteo",
            cwa_office="Open-Meteo Marine",
            issuance_time=None,
            product_text=(
                "Surf conditions from Open-Meteo Marine for Porto.\n"
                "Marine/surf conditions from Open-Meteo Marine; not an official NWS "
                "Surf Zone Forecast."
            ),
            headline="Surf conditions from Open-Meteo Marine",
        )
        openmeteo = AsyncMock(return_value=openmeteo_product)
        pirate = AsyncMock(return_value=None)
        service = ForecastProductService(
            cache,
            fetcher=fetcher,
            openmeteo_marine_fetcher=openmeteo,
            pirate_beach_fetcher=pirate,
        )
        location = type("Location", (), {"name": "Porto", "cwa_office": ""})()

        result = await service.get_surf_conditions_for_location(location)

        assert result is openmeteo_product
        assert result.product_type == "SURF_CONDITIONS"
        assert "not an official NWS Surf Zone Forecast" in result.product_text
        fetcher.assert_not_awaited()
        openmeteo.assert_awaited_once_with(location)
        pirate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pirate_weather_used_when_openmeteo_marine_unavailable(self):
        cache = Cache()
        fetcher = AsyncMock(return_value=None)
        openmeteo = AsyncMock(return_value=None)
        pirate_product = TextProduct(
            product_type="SURF_CONDITIONS",
            product_id="pirate",
            cwa_office="Pirate Weather",
            issuance_time=None,
            product_text=(
                "Surf conditions from Pirate Weather for London.\n"
                "Beach-weather context from Pirate Weather; not an official NWS Surf "
                "Zone Forecast."
            ),
            headline="Surf conditions from Pirate Weather",
        )
        pirate = AsyncMock(return_value=pirate_product)
        service = ForecastProductService(
            cache,
            fetcher=fetcher,
            openmeteo_marine_fetcher=openmeteo,
            pirate_beach_fetcher=pirate,
        )
        location = type("Location", (), {"name": "London", "cwa_office": ""})()
        weather_client = object()

        result = await service.get_surf_conditions_for_location(
            location,
            weather_client=weather_client,
        )

        assert result is pirate_product
        assert result.product_type == "SURF_CONDITIONS"
        assert "Beach-weather context from Pirate Weather" in result.product_text
        pirate.assert_awaited_once_with(location, weather_client=weather_client)


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
    async def test_iem_afos_cache_key_includes_lookup_filters(self, monkeypatch):
        cache = Cache(default_ttl=60)
        service = ForecastProductService(cache)
        calls: list[dict] = []

        async def fake_afos(product_id, **kwargs):
            calls.append({"product_id": product_id, **kwargs})
            return TextProduct(
                product_type=product_id,
                product_id=product_id,
                cwa_office=kwargs.get("center") or "IEM",
                issuance_time=None,
                product_text=f"text {len(calls)}",
                headline=None,
            )

        monkeypatch.setattr(
            "accessiweather.services.forecast_product_service.fetch_iem_afos_text",
            fake_afos,
        )

        first = await service.get_iem_afos("AFDRAH", limit=1, order="desc")
        cached = await service.get_iem_afos("AFDRAH", limit=1, order="desc")
        filtered = await service.get_iem_afos(
            "AFDRAH",
            limit=1,
            order="desc",
            center="KRAH",
            wmo_id="FXUS62",
            aviation_afd=True,
        )

        assert cached is first
        assert filtered is not first
        assert len(calls) == 2
        assert calls[1]["center"] == "KRAH"
        assert calls[1]["wmo_id"] == "FXUS62"
        assert calls[1]["aviation_afd"] is True

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
            assert kwargs == {
                "active_only": True,
                "start": None,
                "end": None,
                "max_items": 5,
                "timeout": 10.0,
            }
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
