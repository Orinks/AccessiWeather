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
        self.config_root = Path(config_root)
        self.state_dir = self.config_root / "state"
        self.state_file = self.state_dir / "runtime_state.json"
        self.legacy_alert_state_file = self.config_root / "alert_state.json"
        self.legacy_notification_event_state_file = (
            self.config_root / "notification_event_state.json"
        )

    def load_state(self) -> dict[str, Any]:
        """Load runtime state, falling back to the default schema on error."""
        if not self.state_file.exists():
            return deepcopy(_DEFAULT_RUNTIME_STATE)

        try:
            with open(self.state_file, encoding="utf-8") as handle:
                loaded = json.load(handle)
        except Exception as exc:
            logger.warning("Failed to load runtime state from %s: %s", self.state_file, exc)
            return deepcopy(_DEFAULT_RUNTIME_STATE)

        if not isinstance(loaded, dict):
            logger.warning("Runtime state file did not contain a JSON object: %s", self.state_file)
            return deepcopy(_DEFAULT_RUNTIME_STATE)

        return _merge_nested(_DEFAULT_RUNTIME_STATE, loaded)

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
