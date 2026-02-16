"""
Thin wrapper around prismatoid for screen reader announcements.

Provides graceful fallback when prismatoid is not installed or crashes on import.
"""

import logging

logger = logging.getLogger(__name__)


def _try_import_prism():
    """Lazily import prism, returning the module or None."""
    try:
        import prism

        return prism
    except Exception:
        logger.debug("prismatoid not available", exc_info=True)
        return None


try:
    # Module-level flag for tests to check
    PRISM_AVAILABLE = _try_import_prism() is not None
except Exception:
    PRISM_AVAILABLE = False


class ScreenReaderAnnouncer:
    """Announces text via screen reader using prismatoid, with graceful fallback."""

    def __init__(self) -> None:
        """Initialize the announcer, acquiring a screen reader backend if possible."""
        self._backend = None
        self._runtime_available = False
        prism = _try_import_prism()
        if prism is not None:
            try:
                ctx = prism.Context()
                backend = ctx.acquire_best()
                features = backend.features
                if features.is_supported_at_runtime:
                    self._backend = backend
                    self._runtime_available = True
                    logger.info("Screen reader backend active: %s", backend.name)
                else:
                    logger.debug(
                        "Screen reader backend found (%s) but not running at runtime",
                        backend.name,
                    )
            except Exception:
                logger.warning("Failed to acquire screen reader backend", exc_info=True)
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
        """Return whether a screen reader is actively running."""
        return self._runtime_available

    def shutdown(self) -> None:
        """Clean up resources."""
        self._backend = None
        self._runtime_available = False
