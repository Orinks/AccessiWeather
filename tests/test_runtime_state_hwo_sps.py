"""
Tests for the HWO/SPS runtime-state sub-sections added in Unit 9.

Three coupled changes live in two files:

- ``runtime_state._DEFAULT_RUNTIME_STATE`` gains ``hwo`` and ``sps`` defaults
  under ``notification_events``.
- ``NotificationEventManager._runtime_section_to_legacy_shape`` and
  ``_legacy_shape_to_runtime_section`` translate the new sub-sections to and
  from the flat ``NotificationState`` field names.

These tests exercise the converters directly (no runtime-state file) and via
the manager's cache-backed round-trip, covering legacy payloads, populated
payloads, and round-trip stability for the new HWO/SPS fields.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from accessiweather.notifications.notification_event_manager import (
    NotificationEventManager,
    NotificationState,
)
from accessiweather.runtime_state import RuntimeStateManager


def test_default_runtime_state_has_hwo_sps_sections(tmp_path) -> None:
    """Fresh runtime-state load exposes the new sub-sections with defaults."""
    manager = RuntimeStateManager(tmp_path / "config")
    state = manager.load_state()

    notif = state["notification_events"]
    assert notif["hwo"] == {
        "last_issuance_time": None,
        "last_text": None,
        "last_summary_signature": None,
        "last_check_time": None,
    }
    assert notif["sps"] == {
        "last_product_ids": [],
        "last_check_time": None,
    }


def test_legacy_runtime_state_loads_without_hwo_sps(tmp_path) -> None:
    """An on-disk runtime-state file missing HWO/SPS loads with defaults."""
    config_root = tmp_path / "config"
    state_dir = config_root / "state"
    state_dir.mkdir(parents=True)
    # Write a runtime-state file in the shape that existed before Unit 9.
    legacy_payload = {
        "schema_version": 1,
        "alerts": {"schema_version": 1, "alert_states": [], "last_global_notification": None},
        "notification_events": {
            "schema_version": 1,
            "discussion": {
                "last_issuance_time": "2026-04-20T00:00:00+00:00",
                "last_text": "legacy AFD",
                "last_check_time": None,
            },
            "severe_risk": {"last_value": 30, "last_check_time": None},
        },
        "meta": {"migrated_from": [], "migrated_at": None},
    }
    (state_dir / "runtime_state.json").write_text(json.dumps(legacy_payload), encoding="utf-8")

    manager = RuntimeStateManager(config_root)
    section = manager.load_section("notification_events")

    # Legacy data preserved.
    assert section["discussion"]["last_text"] == "legacy AFD"
    assert section["severe_risk"]["last_value"] == 30
    # New sub-sections filled in from defaults — no KeyError / crash.
    assert section["hwo"]["last_issuance_time"] is None
    assert section["sps"]["last_product_ids"] == []


def test_legacy_shape_to_runtime_section_emits_hwo_sps() -> None:
    """Translating a populated legacy dict produces the new sub-sections."""
    issuance_iso = "2026-04-20T14:00:00+00:00"
    legacy = {
        "last_discussion_issuance_time": None,
        "last_discussion_text": None,
        "last_severe_risk": None,
        "last_minutely_transition_signature": None,
        "last_minutely_likelihood_signature": None,
        "last_check_time": "2026-04-20T14:30:00+00:00",
        "last_hwo_issuance_time": issuance_iso,
        "last_hwo_text": "HWO body",
        "last_hwo_summary_signature": "sig-1",
        "last_sps_product_ids": ["sps-b", "sps-a"],
    }

    section = NotificationEventManager._legacy_shape_to_runtime_section(legacy)

    assert section["hwo"]["last_issuance_time"] == issuance_iso
    assert section["hwo"]["last_text"] == "HWO body"
    assert section["hwo"]["last_summary_signature"] == "sig-1"
    assert section["hwo"]["last_check_time"] == "2026-04-20T14:30:00+00:00"
    # Product ids are sorted so the on-disk representation is stable.
    assert section["sps"]["last_product_ids"] == ["sps-a", "sps-b"]


def test_runtime_section_to_legacy_shape_extracts_hwo_sps() -> None:
    """Translating a populated runtime-state section produces legacy-shape keys."""
    section = {
        "discussion": {"last_issuance_time": None, "last_text": None, "last_check_time": None},
        "severe_risk": {"last_value": None, "last_check_time": None},
        "minutely_precipitation": {
            "last_transition_signature": None,
            "last_likelihood_signature": None,
            "last_check_time": None,
        },
        "hwo": {
            "last_issuance_time": "2026-04-20T09:00:00+00:00",
            "last_text": "HWO text",
            "last_summary_signature": "sig-xyz",
            "last_check_time": None,
        },
        "sps": {"last_product_ids": ["sps-1", "sps-2"], "last_check_time": None},
    }

    legacy = NotificationEventManager._runtime_section_to_legacy_shape(section)

    assert legacy["last_hwo_issuance_time"] == "2026-04-20T09:00:00+00:00"
    assert legacy["last_hwo_text"] == "HWO text"
    assert legacy["last_hwo_summary_signature"] == "sig-xyz"
    assert legacy["last_sps_product_ids"] == ["sps-1", "sps-2"]


def test_notification_state_hwo_sps_round_trip_through_converters() -> None:
    """
    Full converter chain reconstructs the original HWO/SPS fields.

    NotificationState -> legacy dict -> runtime section -> legacy dict
    -> NotificationState should be an identity for HWO/SPS data.
    """
    issuance = datetime(2026, 4, 20, 15, 0, 0, tzinfo=timezone.utc)
    original = NotificationState(
        last_hwo_issuance_time=issuance,
        last_hwo_text="HWO body",
        last_hwo_summary_signature="sig-123",
        last_sps_product_ids={"sps-a", "sps-b"},
    )

    legacy_dict = original.to_dict()
    section = NotificationEventManager._legacy_shape_to_runtime_section(legacy_dict)
    # Simulate a disk round-trip — the runtime-state file is JSON.
    section = json.loads(json.dumps(section))
    legacy_again = NotificationEventManager._runtime_section_to_legacy_shape(section)
    restored = NotificationState.from_dict(legacy_again)

    assert restored.last_hwo_issuance_time == issuance
    assert restored.last_hwo_text == "HWO body"
    assert restored.last_hwo_summary_signature == "sig-123"
    assert restored.last_sps_product_ids == {"sps-a", "sps-b"}


def test_manager_persists_hwo_sps_through_runtime_state(tmp_path) -> None:
    """End-to-end: manager saves HWO/SPS via runtime-state and reloads them."""
    runtime_manager = RuntimeStateManager(tmp_path / "config")
    manager = NotificationEventManager(runtime_state_manager=runtime_manager)

    manager.state.last_hwo_issuance_time = datetime(2026, 4, 20, 16, 0, 0, tzinfo=timezone.utc)
    manager.state.last_hwo_text = "outlook body"
    manager.state.last_hwo_summary_signature = "sig-persist"
    manager.state.last_sps_product_ids = {"sps-p-1", "sps-p-2"}
    manager._save_state()

    # New manager, same state dir — forces a disk read.
    reloaded_runtime = RuntimeStateManager(tmp_path / "config")
    reloaded = NotificationEventManager(runtime_state_manager=reloaded_runtime)

    assert reloaded.state.last_hwo_issuance_time == manager.state.last_hwo_issuance_time
    assert reloaded.state.last_hwo_text == "outlook body"
    assert reloaded.state.last_hwo_summary_signature == "sig-persist"
    assert reloaded.state.last_sps_product_ids == {"sps-p-1", "sps-p-2"}
