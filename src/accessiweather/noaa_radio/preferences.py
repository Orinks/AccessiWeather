"""User preferences for NOAA Weather Radio stream selection and station limits."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
DEFAULT_STATION_LIMIT = 10


class RadioPreferences:
    """Stores NOAA radio stream preferences and nearby-station limits in a JSON file."""

    def __init__(
        self,
        config_dir: Path | str | None = None,
        path: Path | str | None = None,
    ) -> None:
        """Initialize with an optional canonical preferences file path."""
        self._prefs: dict[str, str] = {}
        self._station_limit: int | None = DEFAULT_STATION_LIMIT
        if path is not None:
            self._path = Path(path)
        elif config_dir is not None:
            self._path = Path(config_dir) / "noaa_radio_prefs.json"
        else:
            self._path: Path | None = None
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                logger.warning("Failed to load radio preferences: expected JSON object")
                return

            if "preferred_streams" in data or "station_limit" in data:
                preferred_streams = data.get("preferred_streams", {})
                if isinstance(preferred_streams, dict):
                    self._prefs = {
                        str(call_sign).upper(): url
                        for call_sign, url in preferred_streams.items()
                        if isinstance(url, str)
                    }
                station_limit = data.get("station_limit", DEFAULT_STATION_LIMIT)
                self._station_limit = self._normalize_station_limit(station_limit)
            else:
                self._prefs = {
                    str(call_sign).upper(): url
                    for call_sign, url in data.items()
                    if isinstance(url, str)
                }
                self._station_limit = DEFAULT_STATION_LIMIT
        except Exception as e:
            logger.warning(f"Failed to load radio preferences: {e}")

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "preferred_streams": self._prefs,
                "station_limit": self._station_limit,
            }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save radio preferences: {e}")

    def _normalize_station_limit(self, value: object) -> int | None:
        """Return a validated station limit, defaulting invalid values to 10."""
        if value is None:
            return None
        if isinstance(value, str) and value.lower() == "all":
            return None
        if isinstance(value, int) and value > 0:
            return value
        return DEFAULT_STATION_LIMIT

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

    def get_station_limit(self) -> int | None:
        """Return the preferred nearby-station limit, or None for all stations."""
        return self._station_limit

    def set_station_limit(self, limit: int | None) -> None:
        """Set the preferred nearby-station limit."""
        self._station_limit = self._normalize_station_limit(limit)
        self._save()
