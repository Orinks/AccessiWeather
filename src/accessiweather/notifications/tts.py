"""Simple text-to-speech helper used for alert summaries."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

try:
    import pyttsx3  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001
    pyttsx3 = None
    logger.debug("pyttsx3 not available; TTS disabled")


def speak_async(text: str, *, voice: str | None = None, rate: int | None = None) -> bool:
    """Speak the provided text using a background thread.

    Returns True if speech was started successfully.
    """
    if not text:
        return False

    if pyttsx3 is None:
        logger.debug("TTS backend not available")
        return False

    def _run() -> None:
        try:
            engine = pyttsx3.init()
            if voice:
                try:
                    engine.setProperty("voice", voice)
                except Exception:  # noqa: BLE001
                    logger.debug("Requested TTS voice '%s' unavailable", voice)
            if rate:
                try:
                    engine.setProperty("rate", rate)
                except Exception:  # noqa: BLE001
                    logger.debug("Could not set TTS rate to %s", rate)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"TTS playback error: {exc}")

    thread = threading.Thread(target=_run, name="AccessiWeatherTTS", daemon=True)
    thread.start()
    return True
