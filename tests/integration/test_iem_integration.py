"""Integration tests for IEM-backed NWS text products."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from accessiweather.iem_client import (
    fetch_iem_afos_text,
    fetch_iem_spc_outlook,
    fetch_iem_wpc_outlook,
)
from tests.integration.conftest import integration_vcr


@pytest.mark.integration
class TestIemTextProducts:
    """Test IEM product endpoints used by Forecaster Notes."""

    @integration_vcr.use_cassette("iem/afos_swody1.yaml")
    @pytest.mark.asyncio
    async def test_fetch_afos_text_product(self):
        """Test fetching a national AFOS text product from IEM."""
        product = await fetch_iem_afos_text("SWODY1", limit=1)

        assert product.product_id == "SWODY1"
        assert product.product_type == "SWODY1"
        assert product.cwa_office == "IEM"
        assert "SWODY1" in product.headline
        assert len(product.product_text) > 100

    @integration_vcr.use_cassette("iem/spc_outlook_day1.yaml")
    @pytest.mark.asyncio
    async def test_fetch_spc_outlook_summary(self):
        """Test fetching a point-based SPC outlook summary from IEM."""
        product = await fetch_iem_spc_outlook(
            35.7796,
            -78.6382,
            day=1,
            current=False,
            valid_at=datetime(2026, 5, 7, 12, tzinfo=UTC),
            max_items=2,
            timeout=30.0,
        )

        assert product.product_id == "SPC_OUTLOOK_DAY1"
        assert product.product_type == "SPC_OUTLOOK"
        assert product.cwa_office == "SPC"
        assert "SPC Day 1 Convective Outlook" in product.product_text

    @integration_vcr.use_cassette("iem/wpc_outlook_day1.yaml")
    @pytest.mark.asyncio
    async def test_fetch_wpc_excessive_rainfall_summary(self):
        """Test fetching a point-based WPC excessive rainfall summary from IEM."""
        product = await fetch_iem_wpc_outlook(
            35.7796,
            -78.6382,
            day=1,
            valid_at=datetime(2026, 5, 7, 12, tzinfo=UTC),
            max_items=2,
            timeout=30.0,
        )

        assert product.product_id == "WPC_ERO_DAY1"
        assert product.product_type == "WPC_ERO"
        assert product.cwa_office == "WPC"
        assert "WPC Day 1 Excessive Rainfall Outlook" in product.product_text
