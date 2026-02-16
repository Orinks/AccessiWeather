"""Sanitize user input for safe logging."""

import re

# Match control characters (except space), including newlines, tabs, carriage returns
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def sanitize_log(value: str) -> str:
    r"""
    Replace control characters in a string to prevent log injection.

    Newlines, carriage returns, tabs, and other control characters are
    replaced with their repr-style escape sequences (e.g. ``\n``).

    Args:
        value: The raw user input string.

    Returns:
        A sanitized string safe for log interpolation.

    """
    return _CONTROL_CHARS.sub(lambda m: repr(m.group())[1:-1], value)
