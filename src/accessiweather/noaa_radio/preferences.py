"""User preferences for NOAA Weather Radio stream selection."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RadioPreferences:
    """Stores per-station preferred stream URLs in a JSON file."""

    def __init__(self, config_dir: Path | str | None = None) -> None:
        """Initialize with optional config directory for persistence."""
        self._prefs: dict[str, str] = {}
        if config_dir is not None:
            self._path = Path(config_dir) / "noaa_radio_prefs.json"
        else:
            self._path: Path | None = None
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            self._prefs = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load radio preferences: {e}")

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._prefs, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save radio preferences: {e}")

    def get_preferred_url(self, call_sign: str) -> str | None:
        """Get the preferred stream URL for a station, or None."""
        return self._prefs.get(call_sign.upper())

    def set_preferred_url(self, call_sign: str, url: str) -> None:
        """Set the preferred stream URL for a station."""
        self._prefs[call_sign.upper()] = url
        self._save()

    def clear_preferred_url(self, call_sign: str) -> None:
        """Remove the preferred stream URL for a station."""
        if call_sign.upper() in self._prefs:
            del self._prefs[call_sign.upper()]
            self._save()

    def reorder_urls(self, call_sign: str, urls: list[str]) -> list[str]:
        """Reorder URLs so the preferred one is first, if set."""
        preferred = self.get_preferred_url(call_sign)
        if preferred and preferred in urls:
            return [preferred] + [u for u in urls if u != preferred]
        return list(urls)
