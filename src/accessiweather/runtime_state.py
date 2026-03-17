"""Lean runtime-state scaffolding for migration-sensitive app state."""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_RUNTIME_STATE: dict[str, Any] = {
    "schema_version": 1,
    "alerts": {
        "schema_version": 1,
        "last_global_notification": None,
        "alert_states": [],
    },
    "notification_events": {
        "schema_version": 1,
        "discussion": {
            "last_issuance_time": None,
            "last_text": None,
            "last_check_time": None,
        },
        "severe_risk": {
            "last_value": None,
            "last_check_time": None,
        },
    },
    "meta": {
        "migrated_from": [],
        "migrated_at": None,
    },
}

_SECTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "alerts": _DEFAULT_RUNTIME_STATE["alerts"],
    "notification_events": _DEFAULT_RUNTIME_STATE["notification_events"],
}


def _merge_nested(defaults: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    """Overlay loaded state onto the default schema without dropping new keys."""
    merged = deepcopy(defaults)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_nested(merged[key], value)
        else:
            merged[key] = value
    return merged


class RuntimeStateManager:
    """Manage the future unified runtime-state file under a canonical state root."""

    def __init__(self, config_root: Path | str):
        """Initialize the manager for a given config-root directory."""
        self.config_root = Path(config_root)
        self.state_dir = self.config_root / "state"
        self.state_file = self.state_dir / "runtime_state.json"
        self.legacy_alert_state_file = self.config_root / "alert_state.json"
        self.legacy_notification_event_state_file = (
            self.config_root / "notification_event_state.json"
        )
        # In-memory cache to avoid redundant disk reads on the notification hot path.
        self._cache: dict[str, Any] | None = None

    def _get_cached_state(self) -> dict[str, Any]:
        """Return the in-memory state, loading from disk once if needed."""
        if self._cache is None:
            loaded = self._load_raw_state()
            if loaded is None:
                self._cache = deepcopy(_DEFAULT_RUNTIME_STATE)
            else:
                self._cache = _merge_nested(_DEFAULT_RUNTIME_STATE, loaded)
        return self._cache

    def _invalidate_cache(self) -> None:
        """Discard the in-memory cache so the next read re-loads from disk."""
        self._cache = None

    def load_state(self) -> dict[str, Any]:
        """Load runtime state from cache (or disk on first call), returning a copy."""
        return deepcopy(self._get_cached_state())

    def _section_is_populated(self, section: str, state: dict[str, Any]) -> bool:
        """Return True when the runtime-state file had real data for this section."""
        # The unified file exists and has this section only if it was previously written.
        # A freshly-loaded default does NOT count as populated.
        return self.state_file.exists() and isinstance(state.get(section), dict)

    def load_section(self, section: str) -> dict[str, Any]:
        """Load a runtime-state section, hydrating from legacy state if needed."""
        if section not in _SECTION_DEFAULTS:
            raise KeyError(f"Unknown runtime-state section: {section}")

        cached = self._get_cached_state()
        if self._section_is_populated(section, cached):
            return deepcopy(cached[section])

        legacy_section = self._load_legacy_section(section)
        if legacy_section is None:
            return deepcopy(_SECTION_DEFAULTS[section])

        self.save_section(
            section, legacy_section, migrated_from=self._legacy_name_for_section(section)
        )
        return legacy_section

    def save_section(
        self,
        section: str,
        section_state: dict[str, Any],
        *,
        migrated_from: str | None = None,
    ) -> bool:
        """Persist a single runtime-state section while preserving other sections."""
        if section not in _SECTION_DEFAULTS:
            raise KeyError(f"Unknown runtime-state section: {section}")

        # Update in-memory cache directly — avoids a disk read for each save.
        cached = self._get_cached_state()
        cached[section] = _merge_nested(_SECTION_DEFAULTS[section], section_state)

        if migrated_from:
            migrated = list(cached["meta"].get("migrated_from", []))
            if migrated_from not in migrated:
                migrated.append(migrated_from)
            cached["meta"]["migrated_from"] = migrated
            if cached["meta"].get("migrated_at") is None:
                from datetime import UTC, datetime

                cached["meta"]["migrated_at"] = datetime.now(UTC).isoformat()

        return self.save_state(cached)

    def save_state(self, state: dict[str, Any]) -> bool:
        """Save runtime state atomically and update the in-memory cache."""
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            tmp_file = self.state_file.with_suffix(".json.tmp")
            payload = json.dumps(state, indent=2, ensure_ascii=False)

            with open(tmp_file, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                # fsync only on platforms where it is meaningful; skip on Windows
                # (os.replace is atomic enough for state files there).
                if os.name != "nt":
                    os.fsync(handle.fileno())

            os.replace(tmp_file, self.state_file)
            # Keep the cache warm so the next read avoids a disk round-trip.
            self._cache = state
            return True
        except Exception as exc:
            logger.warning("Failed to save runtime state to %s: %s", self.state_file, exc)
            try:
                tmp_file = self.state_file.with_suffix(".json.tmp")
                if tmp_file.exists():
                    tmp_file.unlink()
            except Exception:
                logger.debug("Failed to remove runtime-state temp file", exc_info=True)
            return False

    def _load_raw_state(self) -> dict[str, Any] | None:
        """Return the raw runtime-state payload when available and valid."""
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, encoding="utf-8") as handle:
                loaded = json.load(handle)
        except Exception as exc:
            logger.warning("Failed to load runtime state from %s: %s", self.state_file, exc)
            return None

        if not isinstance(loaded, dict):
            logger.warning("Runtime state file did not contain a JSON object: %s", self.state_file)
            return None

        return loaded

    def _load_legacy_section(self, section: str) -> dict[str, Any] | None:
        """Load and normalize a legacy section payload for migration."""
        if section == "alerts":
            return self._load_legacy_alerts_section()
        if section == "notification_events":
            return self._load_legacy_notification_events_section()
        raise KeyError(f"Unknown runtime-state section: {section}")

    def _load_legacy_alerts_section(self) -> dict[str, Any] | None:
        data = self._load_legacy_json(self.legacy_alert_state_file)
        if data is None:
            return None
        return _merge_nested(
            _SECTION_DEFAULTS["alerts"],
            {
                "alert_states": data.get("alert_states", []),
                "last_global_notification": data.get("last_global_notification"),
            },
        )

    def _load_legacy_notification_events_section(self) -> dict[str, Any] | None:
        data = self._load_legacy_json(self.legacy_notification_event_state_file)
        if data is None:
            return None
        last_check_time = data.get("last_check_time")
        return _merge_nested(
            _SECTION_DEFAULTS["notification_events"],
            {
                "discussion": {
                    "last_issuance_time": data.get("last_discussion_issuance_time"),
                    "last_text": data.get("last_discussion_text"),
                    "last_check_time": last_check_time,
                },
                "severe_risk": {
                    "last_value": data.get("last_severe_risk"),
                    "last_check_time": last_check_time,
                },
            },
        )

    def _load_legacy_json(self, path: Path) -> dict[str, Any] | None:
        """Load a legacy JSON payload without raising on corruption."""
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            logger.warning("Failed to load legacy runtime state from %s: %s", path, exc)
            return None
        if not isinstance(data, dict):
            logger.warning("Legacy runtime state file did not contain a JSON object: %s", path)
            return None
        return data

    def _legacy_name_for_section(self, section: str) -> str:
        if section == "alerts":
            return self.legacy_alert_state_file.name
        if section == "notification_events":
            return self.legacy_notification_event_state_file.name
        raise KeyError(f"Unknown runtime-state section: {section}")
