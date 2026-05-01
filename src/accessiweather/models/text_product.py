"""
TextProduct dataclass for NWS text-based products (AFD, HWO, SPS).

AFD = Area Forecast Discussion
HWO = Hazardous Weather Outlook
SPS = Special Weather Statement

These are fetched from ``/products/types/{TYPE}/locations/{cwa_office}`` and
``/products/{id}`` on the NWS API. All three endpoints share the same response
shape, so a single dataclass is sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

ProductType = str


@dataclass(frozen=True)
class TextProduct:
    """A single NWS text product."""

    product_type: ProductType
    product_id: str
    cwa_office: str
    issuance_time: datetime | None
    product_text: str
    headline: str | None
