"""HTML parsing helpers for national discussion products."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_nhc_outlook_text(html: str) -> str:
    """Extract tropical weather outlook text from an NHC HTML page."""
    try:
        soup = BeautifulSoup(html, "html.parser")

        pre = soup.find("pre")
        if pre:
            return pre.get_text().strip()

        div = soup.find("div", id=lambda i: i and "outlook" in i.lower())
        if div:
            return div.get_text().strip()

        el = soup.find(class_=lambda c: c and "outlook" in str(c).lower())
        if el:
            return el.get_text().strip()

        return "Unable to parse NHC outlook text from page"
    except Exception as e:
        return f"Error parsing NHC outlook: {e}"


def extract_cpc_outlook_text(html: str, label: str) -> str | None:
    """Extract outlook text from a CPC outlook HTML page."""
    try:
        soup = BeautifulSoup(html, "html.parser")

        pre = soup.find("pre")
        if pre:
            text = pre.get_text().strip()
            if text:
                return text

        for selector in [
            {"class_": "contentArea"},
            {"class_": "mainContent"},
            {"id": "content"},
        ]:
            div = soup.find("div", **selector)
            if div:
                text = div.get_text().strip()
                if text:
                    return text

        body = soup.find("body")
        if body:
            texts = [
                p.get_text().strip() for p in body.find_all(["p", "div"]) if p.get_text().strip()
            ]
            if texts:
                longest = max(texts, key=len)
                if len(longest) > 100:
                    return longest

        logger.error("Could not extract CPC %s outlook text", label)
        return None
    except Exception as e:
        logger.error("Error parsing CPC %s outlook HTML: %s", label, e)
        return None
