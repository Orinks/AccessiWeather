"""
Tests for ``MainWindow._pre_warm_products_for_location``.

Unit 9 adds a background pre-warm step that fetches AFD/HWO/SPS/SRF for every
saved US location with a populated ``cwa_office`` whenever the active
location's weather refresh succeeds (and symmetrically for non-active
locations inside ``_pre_warm_other_locations``).

The tests exercise the helper directly rather than driving the full
``_fetch_weather_data`` path — the helper is where the official NWS text-product
policy lives (US-only, cwa gating, per-product failure isolation) and driving it
directly keeps the test surface narrow.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models.weather import Location
from accessiweather.weather_client_nws import TextProductFetchError


def _make_window(service: MagicMock):
    """Build a MainWindow stub with just enough to drive the pre-warm helper."""
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
        win = MainWindow.__new__(MainWindow)

    # _pre_warm_products_for_location calls through ``_get_forecast_product_service``;
    # pre-populate the cached instance so we don't need the full service graph.
    win._forecast_product_service = service
    return win


def _us_location(name: str, cwa: str | None = "PHI") -> Location:
    return Location(
        name=name,
        latitude=39.95,
        longitude=-75.16,
        country_code="US",
        cwa_office=cwa,
    )


def _non_us_location(name: str = "London") -> Location:
    return Location(
        name=name,
        latitude=51.5,
        longitude=-0.12,
        country_code="GB",
        cwa_office=None,
    )


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_pre_warm_fetches_text_products_and_daily_climate_for_us_location():
    """Happy path: a single US location triggers text products and CLI fetches."""
    service = MagicMock()
    service.get = AsyncMock(return_value=None)
    service.get_daily_climate_report_for_location = AsyncMock(return_value=None)

    win = _make_window(service)
    asyncio.run(win._pre_warm_products_for_location(_us_location("Philadelphia")))

    assert service.get.await_count == 4
    fetched_types = {call.args[0] for call in service.get.await_args_list}
    assert fetched_types == {"AFD", "HWO", "SPS", "SRF"}
    service.get_daily_climate_report_for_location.assert_awaited_once()


def test_pre_warm_starts_daily_climate_without_waiting_for_other_products():
    """CLI pre-warm should begin beside AFD/HWO/SPS/SRF so the tab opens warm."""
    started: list[str] = []
    release_products = asyncio.Event()

    async def _get(product_type: str, _cwa: str, **_kw):
        started.append(product_type)
        await release_products.wait()

    async def _get_daily_climate(_location):
        started.append("CLI")

    service = MagicMock()
    service.get = AsyncMock(side_effect=_get)
    service.get_daily_climate_report_for_location = AsyncMock(side_effect=_get_daily_climate)

    async def _run_prewarm():
        win = _make_window(service)
        task = asyncio.create_task(
            win._pre_warm_products_for_location(_us_location("Philadelphia"))
        )
        for _ in range(5):
            await asyncio.sleep(0)
            if "CLI" in started:
                break
        assert "CLI" in started
        release_products.set()
        await task

    asyncio.run(_run_prewarm())


def test_pre_warm_skips_non_us_location():
    """Non-US locations never hit the service."""
    service = MagicMock()
    service.get = AsyncMock(return_value=None)
    service.get_daily_climate_report_for_location = AsyncMock(return_value=None)

    win = _make_window(service)
    asyncio.run(win._pre_warm_products_for_location(_non_us_location()))

    service.get.assert_not_awaited()
    service.get_daily_climate_report_for_location.assert_not_awaited()


def test_pre_warm_skips_us_location_without_cwa_office():
    """US location with ``cwa_office=None`` yields zero fetches."""
    service = MagicMock()
    service.get = AsyncMock(return_value=None)
    service.get_daily_climate_report_for_location = AsyncMock(return_value=None)

    win = _make_window(service)
    asyncio.run(win._pre_warm_products_for_location(_us_location("Nowhere", cwa=None)))

    service.get.assert_not_awaited()
    service.get_daily_climate_report_for_location.assert_not_awaited()


def test_pre_warm_fetch_error_isolated_to_single_product():
    """A ``TextProductFetchError`` on HWO doesn't block other NWS products."""
    service = MagicMock()

    async def _get(product_type: str, _cwa: str, **_kw):
        if product_type == "HWO":
            raise TextProductFetchError("404 for HWO")
        return

    service.get = AsyncMock(side_effect=_get)

    win = _make_window(service)
    # Should NOT raise — failure isolation is the whole point.
    asyncio.run(win._pre_warm_products_for_location(_us_location("Philadelphia")))

    assert service.get.await_count == 4
    fetched_types = [call.args[0] for call in service.get.await_args_list]
    assert fetched_types == ["AFD", "HWO", "SPS", "SRF"]


def test_pre_warm_unexpected_exception_is_swallowed():
    """A generic ``Exception`` from one fetch is swallowed; iteration continues."""
    service = MagicMock()

    async def _get(product_type: str, _cwa: str, **_kw):
        if product_type == "AFD":
            raise RuntimeError("unexpected")
        return

    service.get = AsyncMock(side_effect=_get)

    win = _make_window(service)
    asyncio.run(win._pre_warm_products_for_location(_us_location("Philadelphia")))

    assert service.get.await_count == 4


class _FakeWeatherClient:
    """Minimal stand-in for ``AccessiWeatherApp.weather_client``."""

    def __init__(self) -> None:
        self.pre_warm_batch = AsyncMock()

    def get_cached_weather(self, _location):  # pragma: no cover - exercised indirectly
        return None


class _FakeConfigManager:
    def __init__(self, locations: list[Location]) -> None:
        self._locations = locations

    def get_all_locations(self) -> list[Location]:
        return list(self._locations)


def _window_with_app(service: MagicMock, locations: list[Location]):
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
        win = MainWindow.__new__(MainWindow)

    win._forecast_product_service = service
    win.app = MagicMock()
    win.app.config_manager = _FakeConfigManager(locations)
    win.app.weather_client = _FakeWeatherClient()
    return win


@pytest.mark.asyncio
async def test_fetch_weather_data_warms_active_products_before_ui_delivery():
    """HWO/SPS notification checks need active text products cached before UI processing."""
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
        win = MainWindow.__new__(MainWindow)

    location = _us_location("Philadelphia")
    weather_data = MagicMock()
    order: list[str] = []

    win.app = MagicMock()
    win.app.config_manager.get_current_location.return_value = location
    win.app.weather_client.get_weather_data = AsyncMock(return_value=weather_data)
    win._fetch_generation = 1
    win._pre_warm_products_for_location = AsyncMock(side_effect=lambda _loc: order.append("warm"))
    win._pre_warm_other_locations = AsyncMock(side_effect=lambda _loc: order.append("others"))
    win._on_weather_data_received = MagicMock()
    win._on_weather_error = MagicMock()

    def _call_after(callback, *args):
        order.append("ui")
        callback(*args)

    with patch("accessiweather.ui.main_window_refresh.wx.CallAfter", side_effect=_call_after):
        await win._fetch_weather_data(force_refresh=False, generation=1)

    assert order == ["warm", "ui", "others"]
    win._pre_warm_products_for_location.assert_awaited_once_with(location)
    win._on_weather_data_received.assert_called_once_with(weather_data)


@pytest.mark.asyncio
async def test_pre_warm_other_locations_iterates_saved_us_locations():
    """With three saved US locations, the non-active two each get four fetches."""
    service = MagicMock()
    service.get = AsyncMock(return_value=None)

    active = _us_location("Philadelphia")
    other_us_1 = _us_location("New York")
    other_us_1.cwa_office = "OKX"
    other_us_2 = _us_location("Boston")
    other_us_2.cwa_office = "BOX"

    win = _window_with_app(service, [active, other_us_1, other_us_2])

    await win._pre_warm_other_locations(active)

    # Two non-active US locations * 4 product types = 8 fetches.
    assert service.get.await_count == 8
    cwas_by_product = {call.args[0]: set() for call in service.get.await_args_list}
    for call in service.get.await_args_list:
        cwas_by_product[call.args[0]].add(call.args[1])
    assert cwas_by_product == {
        "AFD": {"OKX", "BOX"},
        "HWO": {"OKX", "BOX"},
        "SPS": {"OKX", "BOX"},
        "SRF": {"OKX", "BOX"},
    }


@pytest.mark.asyncio
async def test_pre_warm_other_locations_skips_non_us_peers():
    """Mixed US + non-US list: only US peers drive product fetches."""
    service = MagicMock()
    service.get = AsyncMock(return_value=None)

    active = _us_location("Philadelphia")
    us_peer = _us_location("New York", cwa="OKX")
    non_us_peer = _non_us_location("Paris")

    win = _window_with_app(service, [active, us_peer, non_us_peer])

    await win._pre_warm_other_locations(active)

    # Only the US peer contributes fetches (4), the non-US one is skipped.
    assert service.get.await_count == 4
    fetched_cwas = {call.args[1] for call in service.get.await_args_list}
    assert fetched_cwas == {"OKX"}
