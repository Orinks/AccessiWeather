from __future__ import annotations

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
