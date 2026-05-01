"""Special Weather Statement matching and message helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..models import TextProduct, WeatherAlert


_SPS_MAX_BODY_CHARS = 160


def normalize_for_match(text: str | None) -> str:
    """Return a casefolded, whitespace-collapsed version of ``text`` for matching."""
    if not text:
        return ""
    return " ".join(text.split()).casefold()


def first_nonempty_line(text: str | None) -> str | None:
    """Return the first non-empty, non-whitespace line of ``text``."""
    if not text:
        return None
    for raw in text.splitlines():
        line = raw.strip()
        if line:
            return line
    return None


def truncate(text: str, limit: int) -> str:
    """Truncate ``text`` to ``limit`` chars, appending an ellipsis if cut."""
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."


def sps_alert_signatures(alerts: Sequence[WeatherAlert]) -> list[str]:
    """Collect normalized signatures for active SPS alerts."""
    signatures: list[str] = []
    for alert in alerts:
        event = (alert.event or "").strip().casefold()
        if event != "special weather statement":
            continue
        for candidate in (alert.headline, first_nonempty_line(alert.description)):
            sig = normalize_for_match(candidate)
            if sig:
                signatures.append(sig)
    return signatures


def sps_is_case_a(product: TextProduct, alert_signatures: Sequence[str]) -> bool:
    """Return True when ``product`` looks like the event-style SPS an alert covers."""
    if not alert_signatures:
        return False
    product_haystack_parts = [product.headline or "", product.product_text or ""]
    product_norm = normalize_for_match(" ".join(product_haystack_parts))
    if not product_norm:
        return False
    return any(sig in product_norm or product_norm in sig for sig in alert_signatures)


def format_sps_body(product: TextProduct) -> str:
    """Build the toast body from headline plus CWA office, with text fallback."""
    headline = (product.headline or "").strip()
    if headline:
        body = f"{headline} - {product.cwa_office}"
        return truncate(body, _SPS_MAX_BODY_CHARS)
    fallback = first_nonempty_line(product.product_text) or ""
    return truncate(fallback.strip(), _SPS_MAX_BODY_CHARS)
