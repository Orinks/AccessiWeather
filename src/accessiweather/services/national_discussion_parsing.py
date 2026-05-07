"""HTML parsing helpers for national discussion products."""

from __future__ import annotations

import logging
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


class _TextCollector(HTMLParser):
    """Small HTML text collector for legacy parser tests."""

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[tuple[str, dict[str, str], str]] = []
        self._active: list[tuple[str, dict[str, str], list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"pre", "div", "p", "body"}:
            self._active.append((tag, {key: value or "" for key, value in attrs}, []))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._active) - 1, -1, -1):
            active_tag, attrs, buffer = self._active[index]
            if active_tag == tag:
                self.blocks.append((active_tag, attrs, "".join(buffer)))
                del self._active[index]
                break

    def handle_data(self, data: str) -> None:
        for _tag, _attrs, buffer in self._active:
            buffer.append(data)


def _collect_blocks(html: str) -> list[tuple[str, dict[str, str], str]]:
    if html is None:
        raise TypeError("html must be a string")
    parser = _TextCollector()
    parser.feed(html)
    for tag, attrs, buffer in parser._active:
        parser.blocks.append((tag, attrs, "".join(buffer)))
    return parser.blocks


def extract_nhc_outlook_text(html: str) -> str:
    """Extract tropical weather outlook text from an NHC HTML page."""
    try:
        blocks = _collect_blocks(html)
        for tag, _attrs, text in blocks:
            if tag == "pre" and text.strip():
                return text.strip()
        for _tag, attrs, text in blocks:
            attrs_text = " ".join(attrs.values()).lower()
            if "outlook" in attrs_text and text.strip():
                return text.strip()

        return "Unable to parse NHC outlook text from page"
    except Exception as e:
        return f"Error parsing NHC outlook: {e}"


def extract_cpc_outlook_text(html: str, label: str) -> str | None:
    """Extract outlook text from a CPC outlook HTML page."""
    try:
        blocks = _collect_blocks(html)
        for tag, _attrs, text in blocks:
            if tag == "pre" and text.strip():
                return text.strip()
        for _tag, attrs, text in blocks:
            attrs_text = " ".join(attrs.values()).lower()
            if (
                any(
                    selector in attrs_text for selector in ("contentarea", "maincontent", "content")
                )
                and text.strip()
            ):
                return text.strip()
        texts = [text.strip() for tag, _attrs, text in blocks if tag != "body" and text.strip()]
        if texts:
            longest = max(texts, key=len)
            if len(longest) > 100:
                return longest

        logger.error("Could not extract CPC %s outlook text", label)
        return None
    except Exception as e:
        logger.error("Error parsing CPC %s outlook HTML: %s", label, e)
        return None
