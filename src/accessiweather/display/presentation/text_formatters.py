"""Text formatting helpers for weather presentation output."""

from __future__ import annotations

import textwrap


def wrap_text(text: str, width: int) -> str:
    """Wrap long text blocks to make fallback text easier to read."""
    return textwrap.fill(text, width=width, break_long_words=False)


def truncate(text: str, max_length: int) -> str:
    """Trim text to a maximum length using an ellipsis when needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
