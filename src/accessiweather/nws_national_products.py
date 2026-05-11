"""Helpers for legacy national NWS product aliases."""

from __future__ import annotations

import logging

from accessiweather.iem_client import IemProductFetchError, fetch_iem_afos_text_sync

logger = logging.getLogger(__name__)

NATIONAL_PRODUCT_AFOS_IDS: dict[tuple[str, str], str] = {
    ("FXUS01", "KWNH"): "PMDSPD",
    ("FXUS06", "KWNH"): "PMDEPD",
    ("FXUS07", "KWNH"): "PMDET4",
    ("FXUS02", "KWNH"): "QPFPFD",
    ("ACUS01", "KWNS"): "SWODY1",
    ("ACUS02", "KWNS"): "SWODY2",
    ("ACUS03", "KWNS"): "SWODY3",
    ("MIATWOAT", "KNHC"): "TWOAT",
    ("MIATWOEP", "KNHC"): "TWOEP",
    ("FXUS05", "KWNC"): "PMDMRD",
    ("FXUS07", "KWNC"): "PMDMRD",
}


def national_product_afos_id(product_type: str, location: str) -> str | None:
    """Return the IEM AFOS product ID for a legacy national product alias."""
    return NATIONAL_PRODUCT_AFOS_IDS.get((product_type.upper(), location.upper()))


def fetch_iem_national_product(
    product_type: str,
    location: str,
    *,
    timeout: int = 10,
    user_agent: str = "AccessiWeather/1.0 (AccessiWeather)",
) -> str | None:
    """Fetch a national product through IEM when weather.gov lacks that product type."""
    afos_id = national_product_afos_id(product_type, location)
    if afos_id is None:
        return None

    try:
        product = fetch_iem_afos_text_sync(afos_id, timeout=timeout, user_agent=user_agent)
    except IemProductFetchError as exc:
        logger.warning("IEM AFOS lookup failed for %s/%s: %s", product_type, location, exc)
        return None
    return product.product_text
