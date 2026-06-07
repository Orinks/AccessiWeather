"""
TextProduct dataclass for NWS text-based products and source-labelled summaries.

AFD = Area Forecast Discussion
HWO = Hazardous Weather Outlook
SPS = Special Weather Statement
SRF = Surf Zone Forecast

These are fetched from ``/products/types/{TYPE}/locations/{cwa_office}`` and
``/products/{id}`` on the NWS API. Derived source summaries can also use this
shape when they are clearly labelled as non-NWS products.
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
