"""
Thin wrapper around prismatoid for screen reader announcements.

Provides graceful fallback when prismatoid is not installed.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import prism

    PRISM_AVAILABLE = True
except ImportError:
    PRISM_AVAILABLE = False
    logger.debug("prismatoid not installed; screen reader support disabled")


class ScreenReaderAnnouncer:
    """Announces text via screen reader using prismatoid, with graceful fallback."""

    def __init__(self) -> None:
        """Initialize the announcer, acquiring a screen reader backend if possible."""
        self._backend = None
        if PRISM_AVAILABLE:
            try:
                ctx = prism.Context()
                self._backend = ctx.acquire_best()
                logger.info("Screen reader backend acquired: %s", self._backend)
            except Exception:
                logger.warning("Failed to acquire screen reader backend", exc_info=True)
                self._backend = None
        else:
            logger.debug("prismatoid not available; announcer will be a no-op")

    def announce(self, text: str) -> None:
        """Speak text via screen reader. No-op if unavailable."""
        if self._backend is not None:
            try:
                self._backend.speak(text, interrupt=False)
            except Exception:
                logger.warning("Failed to announce text", exc_info=True)

    def is_available(self) -> bool:
        """Return whether a screen reader backend was successfully acquired."""
        return self._backend is not None

    def shutdown(self) -> None:
        """Clean up resources."""
        self._backend = None
