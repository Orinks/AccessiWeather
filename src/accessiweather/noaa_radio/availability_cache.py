"""Persistent station-level availability suppression for NOAA radio."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from accessiweather.paths import RuntimeStoragePaths, resolve_default_runtime_storage

logger = logging.getLogger(__name__)


class StationAvailabilityCache:
    """Track temporarily suppressed stations in a small JSON file."""

    def __init__(
        self,
        *,
        path: Path | str | None = None,
        runtime_paths: RuntimeStoragePaths | None = None,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        """Initialize the cache with an optional persistence path and clock."""
        resolved_path = path
        if resolved_path is None:
            resolved_path = (
                runtime_paths or resolve_default_runtime_storage()
            ).noaa_radio_availability_file
        self._path = Path(resolved_path)
        self._time_fn = time_fn or time.time
        self._records: dict[str, dict[str, Any]] = {}
        self._load()

    def suppress(self, call_sign: str, ttl_seconds: int, reason: str) -> None:
        """Mark a station as suppressed until the TTL expires."""
        normalized = self._normalize(call_sign)
        if not normalized:
            return
        self._records[normalized] = {
            "reason": reason,
            "expires_at": self._time_fn() + ttl_seconds,
        }
        self._save()

    def clear(self, call_sign: str) -> None:
        """Remove an active suppression entry."""
        normalized = self._normalize(call_sign)
        if not normalized:
            return
        if self._records.pop(normalized, None) is not None:
            self._save()

    def is_suppressed(self, call_sign: str) -> bool:
        """Return True when the station is currently suppressed."""
        return self.get_record(call_sign) is not None

    def get_record(self, call_sign: str) -> dict[str, Any] | None:
        """Return the current suppression record for a station, if any."""
        self._prune_expired()
        normalized = self._normalize(call_sign)
        record = self._records.get(normalized)
        return dict(record) if record is not None else None

    def get_suppressed_call_signs(self) -> list[str]:
        """Return currently suppressed call signs."""
        self._prune_expired()
        return sorted(self._records)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load NOAA radio availability cache: %s", exc)
            return

        if not isinstance(payload, dict):
            return

        records: dict[str, dict[str, Any]] = {}
        for call_sign, record in payload.items():
            if not isinstance(call_sign, str) or not isinstance(record, dict):
                continue
            expires_at = record.get("expires_at")
            reason = record.get("reason")
            if not isinstance(expires_at, int | float) or not isinstance(reason, str):
                continue
            normalized = self._normalize(call_sign)
            if normalized:
                records[normalized] = {
                    "reason": reason,
                    "expires_at": float(expires_at),
                }

        self._records = records
        self._prune_expired()

    def _save(self) -> None:
        self._prune_expired()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._records, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to save NOAA radio availability cache: %s", exc)

    def _prune_expired(self) -> None:
        now = self._time_fn()
        expired = [
            call_sign
            for call_sign, record in self._records.items()
            if float(record.get("expires_at", 0)) <= now
        ]
        if not expired:
            return
        for call_sign in expired:
            self._records.pop(call_sign, None)
        if self._path.exists():
            self._save()

    @staticmethod
    def _normalize(call_sign: str) -> str:
        return call_sign.upper().strip()
