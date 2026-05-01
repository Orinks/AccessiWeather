"""Formatting helpers for forecast text product panels."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import TextProduct

PRODUCT_FULL_NAMES: dict[str, str] = {
    "AFD": "Area Forecast Discussion",
    "HWO": "Hazardous Weather Outlook",
    "SPS": "Special Weather Statement",
}

EMPTY_COPY: dict[str, str] = {
    "AFD": "Area Forecast Discussion not currently available for {cwa_office}.",
    "HWO": "Hazardous Weather Outlook not currently available for {cwa_office}.",
    "SPS": "No recent Special Weather Statements for {cwa_office}.",
}

NO_CWA_COPY = "NWS text products will populate after the next weather refresh."


def format_issuance(issuance_time: datetime | None) -> str:
    """Return the ``Issued: ...`` line in the user's OS local timezone."""
    if issuance_time is None:
        return "Issued: unknown"
    try:
        local = issuance_time.astimezone()
    except (ValueError, OSError):
        local = issuance_time
    return f"Issued: {local.strftime('%Y-%m-%d %H:%M %Z').strip()}"


def format_sps_choice_entry(product: TextProduct) -> str:
    """Build a wx.Choice entry for an SPS product."""
    if product.issuance_time is not None:
        try:
            local = product.issuance_time.astimezone()
        except (ValueError, OSError):
            local = product.issuance_time
        when = local.strftime("%Y-%m-%d %H:%M")
    else:
        when = "unknown"
    headline = product.headline
    if not headline:
        for line in (product.product_text or "").splitlines():
            stripped = line.strip()
            if stripped:
                headline = stripped
                break
    if not headline:
        headline = "Special Weather Statement"
    return f"Issued {when} \u2014 {headline}"
