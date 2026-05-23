from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, call

import pytest

from accessiweather.cache import Cache
from accessiweather.models import AppSettings, Location, TextProduct
from accessiweather.notifications.notification_event_manager import NotificationEventManager
from accessiweather.services.forecast_product_service import ForecastProductService


def _climate_product(product_id: str, text: str, issued: datetime) -> TextProduct:
    return TextProduct(
        product_type="CLI",
        product_id=product_id,
        cwa_office="RDU",
        issuance_time=issued,
        product_text=text,
        headline="Daily Climate Report",
    )


@pytest.mark.asyncio
async def test_forecast_product_service_caches_daily_climate_by_station():
    issued = datetime(2026, 5, 22, 20, 54, tzinfo=UTC)
    fetcher = AsyncMock(return_value=_climate_product("cli-rdu", "CLIMATE REPORT", issued))
    service = ForecastProductService(Cache(), daily_climate_fetcher=fetcher)

    first = await service.get_daily_climate_report("KRDU")
    second = await service.get_daily_climate_report("KRDU")

    assert first is second
    fetcher.assert_awaited_once_with("RDU")


@pytest.mark.asyncio
async def test_daily_climate_for_location_falls_back_to_observation_stations():
    issued = datetime(2026, 5, 23, 5, 53, tzinfo=UTC)
    product = _climate_product("cli-ttn", "CLIMATE REPORT FOR TRENTON", issued)
    fetcher = AsyncMock(side_effect=[None, None, None, product])
    station_fetcher = AsyncMock(return_value=["KVAY", "KTTN", "KPHL"])
    service = ForecastProductService(
        Cache(),
        daily_climate_fetcher=fetcher,
        observation_station_fetcher=station_fetcher,
        daily_climate_location_fetcher=AsyncMock(return_value=set()),
    )
    location = Location(
        name="Lumberton, NJ",
        latitude=39.965,
        longitude=-74.805,
        country_code="US",
        cwa_office="PHI",
        radar_station="KDIX",
    )

    result = await service.get_daily_climate_report_for_location(location)

    assert result is product
    assert fetcher.await_args_list == [call("DIX"), call("PHI"), call("VAY"), call("TTN")]
    station_fetcher.assert_awaited_once_with(39.965, -74.805)
    assert service._cache.get("iem_text_product:CLI:DIX:latest") is product


@pytest.mark.asyncio
async def test_daily_climate_for_location_uses_cli_location_index_to_skip_dead_candidates():
    issued = datetime(2026, 5, 23, 5, 53, tzinfo=UTC)
    product = _climate_product("cli-ttn", "CLIMATE REPORT FOR TRENTON", issued)
    fetcher = AsyncMock(return_value=product)
    station_fetcher = AsyncMock(return_value=["KVAY", "KWRI", "KPNE", "KTTN", "KPHL"])
    cli_location_fetcher = AsyncMock(return_value={"TTN", "PHL", "ACY"})
    service = ForecastProductService(
        Cache(),
        daily_climate_fetcher=fetcher,
        observation_station_fetcher=station_fetcher,
        daily_climate_location_fetcher=cli_location_fetcher,
    )
    location = Location(
        name="Lumberton, NJ",
        latitude=39.965,
        longitude=-74.805,
        country_code="US",
        cwa_office="PHI",
        radar_station="KDIX",
    )

    result = await service.get_daily_climate_report_for_location(location)

    assert result is product
    fetcher.assert_awaited_once_with("TTN")
    station_fetcher.assert_awaited_once_with(39.965, -74.805)
    cli_location_fetcher.assert_awaited_once()
    assert service._cache.get("iem_text_product:CLI:DIX:latest") is product


@pytest.mark.asyncio
async def test_daily_climate_for_location_caches_resolved_cli_station():
    issued = datetime(2026, 5, 23, 5, 53, tzinfo=UTC)
    product = _climate_product("cli-ttn", "CLIMATE REPORT FOR TRENTON", issued)
    fetcher = AsyncMock(return_value=product)
    station_fetcher = AsyncMock(return_value=["KTTN", "KPHL"])
    cli_location_fetcher = AsyncMock(return_value={"TTN", "PHL"})
    service = ForecastProductService(
        Cache(),
        daily_climate_fetcher=fetcher,
        observation_station_fetcher=station_fetcher,
        daily_climate_location_fetcher=cli_location_fetcher,
    )
    location = Location(
        name="Lumberton, NJ",
        latitude=39.965,
        longitude=-74.805,
        country_code="US",
        cwa_office="PHI",
        radar_station="KDIX",
    )

    first = await service.get_daily_climate_report_for_location(location)
    second = await service.get_daily_climate_report_for_location(location)

    assert first is product
    assert second is product
    fetcher.assert_awaited_once_with("TTN")
    station_fetcher.assert_awaited_once()
    cli_location_fetcher.assert_awaited_once()


def test_location_daily_climate_station_candidates_prefer_radar_then_office():
    location = Location(
        name="Raleigh",
        latitude=35.7796,
        longitude=-78.6382,
        country_code="US",
        cwa_office="RAH",
        radar_station="KRDU",
    )

    assert ForecastProductService.daily_climate_station_candidates(location) == ["RDU", "RAH"]


def test_daily_climate_update_notification_is_baselined_then_summarized():
    manager = NotificationEventManager(state_file=None)
    settings = AppSettings()
    settings.notify_daily_climate_report_update = True
    first_time = datetime(2026, 5, 22, 20, 54, tzinfo=UTC)

    first = _climate_product(
        "cli-rdu-1",
        "CLIMATE REPORT\nMAXIMUM         65\nPRECIPITATION   0.25",
        first_time,
    )
    second = _climate_product(
        "cli-rdu-2",
        "CLIMATE REPORT\nMAXIMUM         70\nPRECIPITATION   0.40",
        first_time + timedelta(hours=24),
    )

    assert manager.check_daily_climate_report(first, settings, "Raleigh") is None
    event = manager.check_daily_climate_report(second, settings, "Raleigh")

    assert event is not None
    assert event.event_type == "daily_climate_report_update"
    assert event.sound_event == "discussion_update"
    assert "Daily Climate Report" in event.title
    assert "MAXIMUM" in event.message
    assert "PRECIPITATION" in event.message
