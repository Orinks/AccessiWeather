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
    "LSR": "Local Storm Report",
    "PNS": "Public Information Statement",
    "CLI": "Daily Climate Report",
    "SPC_OUTLOOK": "SPC Day 1 Convective Outlook (Storm Prediction Center)",
    "SPC_MCD": "SPC Mesoscale Discussions (Storm Prediction Center)",
    "SPC_WATCHES": "SPC Watches (Storm Prediction Center)",
    "WPC_ERO": "WPC Day 1 Excessive Rainfall Outlook (Weather Prediction Center)",
    "WPC_MPD": "WPC Mesoscale Precipitation Discussions (Weather Prediction Center)",
    "PMDSPD": "WPC Short Range Discussion (Weather Prediction Center)",
    "PMDEPD": "WPC Medium Range Discussion (Weather Prediction Center)",
    "PMDET4": "WPC Extended Discussion (Weather Prediction Center)",
    "QPFPFD": "WPC Quantitative Precipitation Discussion (Weather Prediction Center)",
    "PMDMRD": "CPC 6-10 and 8-14 Day Outlook (Climate Prediction Center)",
    "TWOAT": "NHC Atlantic Tropical Weather Outlook (National Hurricane Center)",
    "TWOEP": "NHC East Pacific Tropical Weather Outlook (National Hurricane Center)",
    "SWODY1": "SPC Day 1 Convective Outlook (Storm Prediction Center)",
    "SWODY2": "SPC Day 2 Convective Outlook (Storm Prediction Center)",
    "SWODY3": "SPC Day 3 Convective Outlook (Storm Prediction Center)",
}

EMPTY_COPY: dict[str, str] = {
    "AFD": "Area Forecast Discussion not currently available for {cwa_office}.",
    "HWO": "Hazardous Weather Outlook not currently available for {cwa_office}.",
    "SPS": "No recent Special Weather Statements for {cwa_office}.",
    "LSR": "No recent Local Storm Reports for {cwa_office}.",
    "PNS": "No recent Public Information Statements for {cwa_office}.",
    "CLI": "Daily Climate Report not currently available for {cwa_office}.",
    "SPC_OUTLOOK": (
        "No matching SPC (Storm Prediction Center) Day 1 Convective Outlook for this location."
    ),
    "SPC_MCD": (
        "No matching SPC (Storm Prediction Center) Mesoscale Discussions for this location."
    ),
    "SPC_WATCHES": "No matching SPC (Storm Prediction Center) Watches for this location.",
    "WPC_ERO": (
        "No matching WPC (Weather Prediction Center) Excessive Rainfall Outlook for this location."
    ),
    "WPC_MPD": (
        "No matching WPC (Weather Prediction Center) Mesoscale Precipitation Discussions "
        "for this location."
    ),
    "PMDSPD": "WPC Short Range Discussion is not currently available.",
    "PMDEPD": "WPC Medium Range Discussion is not currently available.",
    "PMDET4": "WPC Extended Discussion is not currently available.",
    "QPFPFD": "WPC Quantitative Precipitation Discussion is not currently available.",
    "PMDMRD": "CPC 6-10 and 8-14 Day Outlook is not currently available.",
    "TWOAT": "NHC Atlantic Tropical Weather Outlook is not currently available.",
    "TWOEP": "NHC East Pacific Tropical Weather Outlook is not currently available.",
    "SWODY1": "SPC Day 1 Convective Outlook is not currently available.",
    "SWODY2": "SPC Day 2 Convective Outlook is not currently available.",
    "SWODY3": "SPC Day 3 Convective Outlook is not currently available.",
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
