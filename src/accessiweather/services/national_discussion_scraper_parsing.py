"""HTML parsing helpers for national discussion scraper pages."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_discussion_text(html_content: str, source: str) -> dict[str, Any]:
    """Extract WPC or SPC discussion text from an HTML page."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        discussion_element = soup.find("pre")

        if not discussion_element:
            discussion_element = soup.find("div", class_=lambda c: c and "discussion" in c.lower())

        if not discussion_element:
            discussion_element = soup.find("div", id=lambda i: i and "discussion" in i.lower())

        if not discussion_element:
            discussion_element = _find_discussion_paragraph(soup, source)

        if not discussion_element:
            logger.error(f"Could not find {source.upper()} discussion text using any selector")
            return {"success": False, "error": f"{source.upper()} discussion unavailable"}

        full_text = discussion_element.get_text()
        if not full_text:
            logger.error(f"Empty {source.upper()} discussion text")
            return {"success": False, "error": f"Empty {source.upper()} discussion"}

        full_text = full_text.strip()
        if source == "spc" and "...SUMMARY..." in full_text:
            full_text = _extract_spc_summary(full_text)

        return {"success": True, "full_text": full_text}

    except Exception as e:
        logger.error(f"Error parsing {source.upper()} discussion HTML: {str(e)}")
        return {
            "success": False,
            "error": f"Error parsing {source.upper()} discussion: {str(e)}",
        }


def extract_cpc_outlook_text(html_content: str, label: str) -> str | None:
    """Extract outlook text from a CPC outlook HTML page."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        pre = soup.find("pre")
        if pre:
            text = pre.get_text().strip()
            if text:
                return text

        for selector in [{"class_": "contentArea"}, {"class_": "mainContent"}, {"id": "content"}]:
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

        logger.error(f"Could not extract CPC {label} outlook text")
        return None

    except Exception as e:
        logger.error(f"Error parsing CPC {label} outlook HTML: {e}")
        return None


def _find_discussion_paragraph(soup: BeautifulSoup, source: str) -> Any | None:
    if source == "wpc":
        phrases = ["Short-Range Forecast Discussion", "Weather Prediction Center"]
    elif source == "spc":
        phrases = ["Convective Outlook", "Storm Prediction Center"]
    else:
        return None

    for paragraph in soup.find_all("p"):
        if paragraph.text and any(phrase in paragraph.text for phrase in phrases):
            return paragraph
    return None


def _extract_spc_summary(full_text: str) -> str:
    try:
        return full_text.split("...SUMMARY...", 1)[1].strip()
    except Exception as e:
        logger.warning(f"Error extracting SPC summary section: {e}")
        return full_text
