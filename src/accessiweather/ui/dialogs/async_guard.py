"""
Guard helpers for wx.CallAfter completion handlers.

Background work in the dialogs marshals its result back onto the main thread
via ``wx.CallAfter``. If the user closes the dialog before that callback runs,
the queued handler touches widgets whose underlying C++ objects have already
been destroyed, which raises ``RuntimeError: wrapped C/C++ object of type ...
has been deleted``. The :func:`guard_destroyed` decorator swallows exactly that
case so a closed dialog can never crash the app, while re-raising any other
``RuntimeError`` so genuine bugs stay visible.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def guard_destroyed(method: F) -> F:
    """Skip a wx completion handler if its dialog/widgets were already destroyed."""

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return method(self, *args, **kwargs)
        except RuntimeError as exc:
            if "has been deleted" in str(exc):
                logger.debug("Skipping %s: window destroyed before callback ran", method.__name__)
                return None
            raise

    return wrapper  # type: ignore[return-value]
