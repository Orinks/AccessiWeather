from __future__ import annotations

import json

from accessiweather.runtime_state import RuntimeStateManager


def test_uses_canonical_state_subdirectory(tmp_path):
    manager = RuntimeStateManager(tmp_path / "config")

    assert manager.state_dir == tmp_path / "config" / "state"
    assert manager.state_file == tmp_path / "config" / "state" / "runtime_state.json"
    assert manager.legacy_alert_state_file == tmp_path / "config" / "alert_state.json"
    assert (
        manager.legacy_notification_event_state_file
        == tmp_path / "config" / "notification_event_state.json"
    )


def test_load_returns_default_schema_when_file_missing(tmp_path):
    manager = RuntimeStateManager(tmp_path / "config")

    state = manager.load_state()

    assert state["schema_version"] == 1
    assert state["alerts"]["alert_states"] == []
    assert state["notification_events"]["discussion"]["last_issuance_time"] is None
    assert state["notification_events"]["severe_risk"]["last_value"] is None


def test_round_trip_preserves_phase1_runtime_sections(tmp_path):
    manager = RuntimeStateManager(tmp_path / "config")
    state = manager.load_state()
    state["alerts"]["last_global_notification"] = "2026-03-16T15:00:00+00:00"
    state["alerts"]["alert_states"] = [{"alert_id": "abc"}]
    state["notification_events"]["discussion"]["last_issuance_time"] = "2026-03-16T14:30:00+00:00"
    state["notification_events"]["discussion"]["last_text"] = "Discussion text"
    state["notification_events"]["severe_risk"]["last_value"] = 35
    state["meta"]["migrated_from"] = ["alert_state.json"]

    assert manager.save_state(state) is True

    reloaded = manager.load_state()

    assert reloaded == state
    assert not manager.state_file.with_suffix(".json.tmp").exists()


def test_corrupt_file_recovers_default_schema(tmp_path):
    manager = RuntimeStateManager(tmp_path / "config")
    manager.state_dir.mkdir(parents=True, exist_ok=True)
    manager.state_file.write_text("{not valid json", encoding="utf-8")

    state = manager.load_state()

    assert state["schema_version"] == 1
    assert state["alerts"]["alert_states"] == []


def test_load_section_prefers_unified_data_when_available(tmp_path):
    manager = RuntimeStateManager(tmp_path / "config")
    manager.state_dir.mkdir(parents=True, exist_ok=True)
    manager.state_file.write_text(
        json.dumps(
            {
                "alerts": {
                    "alert_states": [{"alert_id": "from-unified"}],
                    "last_global_notification": "2026-03-16T15:00:00+00:00",
                }
            }
        ),
        encoding="utf-8",
    )
    manager.legacy_alert_state_file.parent.mkdir(parents=True, exist_ok=True)
    manager.legacy_alert_state_file.write_text(
        json.dumps(
            {
                "alert_states": [{"alert_id": "from-legacy"}],
                "last_global_notification": "2026-03-16T14:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    section = manager.load_section("alerts")

    assert section["alert_states"] == [{"alert_id": "from-unified"}]
    assert section["last_global_notification"] == "2026-03-16T15:00:00+00:00"


def test_load_section_falls_back_to_valid_legacy_data_per_section(tmp_path):
    manager = RuntimeStateManager(tmp_path / "config")
    manager.legacy_notification_event_state_file.parent.mkdir(parents=True, exist_ok=True)
    manager.legacy_notification_event_state_file.write_text(
        json.dumps(
            {
                "last_discussion_issuance_time": "2026-03-16T14:30:00+00:00",
                "last_discussion_text": "Discussion text",
                "last_severe_risk": 35,
                "last_check_time": "2026-03-16T14:31:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    notification_section = manager.load_section("notification_events")
    alert_section = manager.load_section("alerts")

    assert notification_section["discussion"]["last_issuance_time"] == "2026-03-16T14:30:00+00:00"
    assert notification_section["discussion"]["last_text"] == "Discussion text"
    assert notification_section["discussion"]["last_check_time"] == "2026-03-16T14:31:00+00:00"
    assert notification_section["severe_risk"]["last_value"] == 35
    assert notification_section["severe_risk"]["last_check_time"] == "2026-03-16T14:31:00+00:00"
    assert alert_section["alert_states"] == []


def test_load_section_ignores_corrupt_legacy_file_without_breaking_other_section(tmp_path):
    manager = RuntimeStateManager(tmp_path / "config")
    manager.legacy_alert_state_file.parent.mkdir(parents=True, exist_ok=True)
    manager.legacy_alert_state_file.write_text("{bad json", encoding="utf-8")
    manager.legacy_notification_event_state_file.write_text(
        json.dumps(
            {
                "last_discussion_issuance_time": "2026-03-16T14:30:00+00:00",
                "last_discussion_text": "Discussion text",
                "last_severe_risk": 42,
            }
        ),
        encoding="utf-8",
    )

    alerts = manager.load_section("alerts")
    notification_events = manager.load_section("notification_events")

    assert alerts["alert_states"] == []
    assert notification_events["discussion"]["last_issuance_time"] == "2026-03-16T14:30:00+00:00"
    assert notification_events["severe_risk"]["last_value"] == 42
