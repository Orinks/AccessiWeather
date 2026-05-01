"""Text parsing and summarization helpers for notification events."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import TextProduct


_HWO_SUMMARY_MIN_CHARS = 20


def extract_discussion_issued_time_label(discussion_text: str | None) -> str | None:
    """Extract the station-local issued time label from AFD text when present."""
    if not discussion_text:
        return None

    patterns = (
        r"\bISSUED\s+(\d{1,2})(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\b",
        r"\bISSUED\s+(\d{1,2}):(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\b",
        r"(?:^|\n)\s*(\d{1,2})(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b",
        r"(?:^|\n)\s*(\d{1,2}):(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b",
    )

    for pattern in patterns:
        match = re.search(pattern, discussion_text, re.IGNORECASE)
        if match:
            hour, minute, meridiem, tz_name = match.groups()
            return f"{int(hour)}:{minute} {meridiem.upper()} {tz_name.upper()}"

    return None


def format_issuance_time_label(issuance_time: datetime) -> str:
    """Format issuance time using the datetime's own timezone context."""
    time_str = issuance_time.strftime("%I:%M %p").lstrip("0")
    tz_name = issuance_time.tzname() or ""
    return f"{time_str} {tz_name}".strip()


def get_risk_category(risk: int) -> str:
    """Categorize severe weather risk level."""
    if risk >= 80:
        return "extreme"
    if risk >= 60:
        return "high"
    if risk >= 40:
        return "moderate"
    if risk >= 20:
        return "low"
    return "minimal"


def extract_section(text: str, start_marker: str, end_markers: tuple[str, ...]) -> str | None:
    """Extract the content of a named section from AFD text."""
    lines = text.splitlines()
    in_section = False
    body_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not in_section:
            if stripped.upper().startswith(start_marker.upper()):
                in_section = True
            continue
        if any(stripped.startswith(m) for m in end_markers) or any(
            stripped.upper().startswith(m.upper()) for m in end_markers
        ):
            break
        body_lines.append(stripped)
    if not in_section:
        return None
    content = " ".join(part for part in body_lines if part)
    return content if content else None


def normalize_discussion_summary(text: str | None) -> str:
    """Normalize extracted AFD summary text for comparison."""
    if not text:
        return ""
    return " ".join(text.split()).casefold().strip(" .")


def is_no_change_summary(text: str | None) -> bool:
    """Return True when a WHAT HAS CHANGED section explicitly says nothing changed."""
    normalized = normalize_discussion_summary(text)
    if not normalized:
        return False
    return normalized in {
        "no change",
        "no changes",
        "no significant change",
        "no significant changes",
        "no significant changes made to forecast",
        "no significant changes made to the forecast",
    }


def summarize_discussion_change(previous_text: str | None, current_text: str | None) -> str | None:
    """Return a short human-friendly summary of what changed in discussion text."""
    if not current_text:
        return None

    what_changed_section = extract_section(
        current_text,
        start_marker=".WHAT HAS CHANGED",
        end_markers=(".", "&&"),
    )
    current_declares_no_changes = is_no_change_summary(what_changed_section)
    if what_changed_section and not current_declares_no_changes:
        return what_changed_section[:300]

    section = extract_section(
        current_text,
        start_marker=".KEY MESSAGES",
        end_markers=(".", "&&"),
    )
    if section:
        previous_section = extract_section(
            previous_text or "",
            start_marker=".KEY MESSAGES",
            end_markers=(".", "&&"),
        )
        if not previous_section or normalize_discussion_summary(
            section
        ) != normalize_discussion_summary(previous_section):
            return section[:300]
        if current_declares_no_changes:
            return None

    if current_declares_no_changes:
        return None

    previous_lines = {
        line.strip()
        for line in (previous_text or "").splitlines()
        if line.strip() and not line.strip().startswith("$")
    }
    for raw_line in current_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("$"):
            continue
        if line not in previous_lines:
            return line[:300]
    return None


def hash_product_text(text: str) -> str:
    """Return a stable signature for a text product."""
    normalized = (text or "").strip()
    return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()


def format_hwo_body(stored_text: str | None, new_product: TextProduct) -> str:
    """Produce the HWO notification body."""
    summary = summarize_discussion_change(stored_text, new_product.product_text)
    if summary and len(summary.strip()) > _HWO_SUMMARY_MIN_CHARS:
        return summary.strip()
    return f"Hazardous Weather Outlook updated for {new_product.cwa_office} - tap to view."
