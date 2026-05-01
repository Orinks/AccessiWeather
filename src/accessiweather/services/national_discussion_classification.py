"""Classification helpers for national discussion products."""

from __future__ import annotations


def classify_pmd_discussion(text: str | None) -> str | None:
    """Classify a WPC PMD product as short, medium, or extended range."""
    text_upper = text.upper() if text else ""
    if "PMDSPD" in text_upper:
        return "short_range"
    if "PMDEPD" in text_upper:
        return "medium_range"
    if "PMDET" in text_upper:
        return "extended"

    text_lower = text.lower() if text else ""
    if "short range" in text_lower:
        return "short_range"
    if "medium range" in text_lower or "3-7 day" in text_lower:
        return "medium_range"
    if "extended" in text_lower and ("8-10" in text_lower or "day 8" in text_lower):
        return "extended"
    return None


def classify_swo_outlook(text: str | None) -> str | None:
    """Classify an SPC SWO product as day 1, day 2, or day 3."""
    text_upper = text.upper() if text else ""
    if "SWODY1" in text_upper:
        return "day1"
    if "SWODY2" in text_upper:
        return "day2"
    if "SWODY3" in text_upper:
        return "day3"

    text_lower = text.lower() if text else ""
    if "day 1" in text_lower:
        return "day1"
    if "day 2" in text_lower:
        return "day2"
    if "day 3" in text_lower:
        return "day3"
    return None
