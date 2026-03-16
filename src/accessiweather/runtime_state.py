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

    def load_state(self) -> dict[str, Any]:
        """Load runtime state, falling back to the default schema on error."""
        loaded = self._load_raw_state()
        if loaded is None:
            return deepcopy(_DEFAULT_RUNTIME_STATE)

        return _merge_nested(_DEFAULT_RUNTIME_STATE, loaded)

    def load_section(self, section: str) -> dict[str, Any]:
        """Load a runtime-state section, hydrating from legacy state if needed."""
        if section not in _SECTION_DEFAULTS:
            raise KeyError(f"Unknown runtime-state section: {section}")

        raw_state = self._load_raw_state()
        if isinstance(raw_state, dict) and section in raw_state and isinstance(raw_state[section], dict):
            return deepcopy(self.load_state()[section])

        legacy_section = self._load_legacy_section(section)
        if legacy_section is None:
            return deepcopy(_SECTION_DEFAULTS[section])

        self.save_section(section, legacy_section, migrated_from=self._legacy_name_for_section(section))
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

        state = self.load_state()
        state[section] = _merge_nested(_SECTION_DEFAULTS[section], section_state)

        if migrated_from:
            migrated = list(state["meta"].get("migrated_from", []))
            if migrated_from not in migrated:
                migrated.append(migrated_from)
            state["meta"]["migrated_from"] = migrated
            if state["meta"].get("migrated_at") is None:
                from datetime import UTC, datetime

                state["meta"]["migrated_at"] = datetime.now(UTC).isoformat()

        return self.save_state(state)

    def save_state(self, state: dict[str, Any]) -> bool:
        """Save runtime state atomically."""
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            tmp_file = self.state_file.with_suffix(".json.tmp")
            payload = json.dumps(state, indent=2, ensure_ascii=False)

            with open(tmp_file, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(tmp_file, self.state_file)
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
