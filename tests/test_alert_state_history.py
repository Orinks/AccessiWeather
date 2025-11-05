"""Tests for AlertState with bounded history tracking."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from accessiweather.alert_manager import AlertState
from accessiweather.constants import ALERT_HISTORY_MAX_LENGTH


@pytest.mark.unit
class TestAlertStateInitialization:
    """Test AlertState initialization and basic properties."""

    def test_init_creates_state_with_history(self):
        """AlertState should initialize with history containing initial entry."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="abc123",
            first_seen=datetime.now(UTC),
            severity_priority=3,
        )

        assert state.alert_id == "test-alert"
        assert len(state.hash_history) == 1
        assert state.content_hash == "abc123"

    def test_init_with_all_parameters(self):
        """AlertState should accept all optional parameters."""
        first_seen = datetime.now(UTC)
        last_notified = datetime.now(UTC)

        state = AlertState(
            alert_id="test-alert",
            content_hash="abc123",
            first_seen=first_seen,
            last_notified=last_notified,
            notification_count=5,
            severity_priority=4,
        )

        assert state.last_notified == last_notified
        assert state.notification_count == 5
        assert state.hash_history[-1][1] == 4  # severity priority

    def test_content_hash_property_returns_most_recent(self):
        """content_hash property should return most recent hash from history."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )

        state.add_hash("updated", 3)
        assert state.content_hash == "updated"

        state.add_hash("latest", 4)
        assert state.content_hash == "latest"

    def test_empty_history_content_hash(self):
        """content_hash property should handle empty history gracefully."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )
        state.hash_history.clear()

        assert state.content_hash == ""


@pytest.mark.unit
class TestAlertStateHistoryManagement:
    """Test history addition and bounded deque behavior."""

    def test_add_hash_appends_to_history(self):
        """add_hash should append new entry to history."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=1,
        )

        initial_count = len(state.hash_history)
        state.add_hash("new_hash", 2)

        assert len(state.hash_history) == initial_count + 1
        assert state.hash_history[-1][0] == "new_hash"
        assert state.hash_history[-1][1] == 2

    def test_add_hash_with_custom_timestamp(self):
        """add_hash should accept custom timestamps."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=1,
        )

        custom_timestamp = 1699200000.0
        state.add_hash("custom", 3, timestamp=custom_timestamp)

        assert state.hash_history[-1][2] == custom_timestamp

    def test_add_hash_uses_current_time_by_default(self):
        """add_hash should use current time when timestamp not provided."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=1,
        )

        before = time.time()
        state.add_hash("new", 2)
        after = time.time()

        timestamp = state.hash_history[-1][2]
        assert before <= timestamp <= after

    def test_history_respects_max_length(self):
        """History should not exceed ALERT_HISTORY_MAX_LENGTH."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=1,
        )

        # Add more entries than max length
        for i in range(ALERT_HISTORY_MAX_LENGTH + 5):
            state.add_hash(f"hash_{i}", i % 5 + 1)

        # Should be bounded to max length
        assert len(state.hash_history) == ALERT_HISTORY_MAX_LENGTH

        # Should have most recent entries
        assert state.hash_history[-1][0].startswith("hash_")

    def test_history_maintains_chronological_order(self):
        """History should maintain chronological order (oldest to newest)."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=1,
        )

        timestamps = []
        for i in range(5):
            ts = time.time() + i * 0.01  # Small increments
            state.add_hash(f"hash_{i}", 2, timestamp=ts)
            timestamps.append(ts)

        # Verify chronological order
        history_timestamps = [entry[2] for entry in state.hash_history]
        assert history_timestamps == sorted(history_timestamps)


@pytest.mark.unit
class TestAlertStateChangeDetection:
    """Test change detection methods."""

    def test_has_changed_detects_different_hash(self):
        """has_changed should return True for different hash."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="original",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )

        assert state.has_changed("different")

    def test_has_changed_same_hash(self):
        """has_changed should return False for same hash."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="original",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )

        assert not state.has_changed("original")

    def test_has_changed_empty_history(self):
        """has_changed should return True when history is empty."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="original",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )
        state.hash_history.clear()

        assert state.has_changed("anything")

    def test_has_changed_detects_flip_flop(self):
        """has_changed should detect A→B→A pattern."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="A",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )

        # Change to B
        state.add_hash("B", 2)
        assert state.has_changed("A")  # A is different from current (B)

        # Change back to A
        state.add_hash("A", 2)
        assert not state.has_changed("A")  # A is same as current


@pytest.mark.unit
class TestAlertStateEscalationDetection:
    """Test escalation detection logic."""

    def test_is_escalated_higher_priority(self):
        """is_escalated should return True when priority increases."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=2,  # Minor
        )

        # Escalate to Severe (4)
        assert state.is_escalated(4)

    def test_is_escalated_same_priority(self):
        """is_escalated should return False for same priority."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=3,
        )

        assert not state.is_escalated(3)

    def test_is_escalated_lower_priority(self):
        """is_escalated should return False when priority decreases."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=4,  # Severe
        )

        # Downgrade to Moderate (3)
        assert not state.is_escalated(3)

    def test_is_escalated_compares_against_max_history(self):
        """is_escalated should compare against highest priority in history."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=2,  # Minor
        )

        # Add Moderate, then back to Minor
        state.add_hash("hash2", 3)  # Moderate
        state.add_hash("hash3", 2)  # Back to Minor

        # Current is Minor, but history has Moderate
        # Severe (4) is still an escalation
        assert state.is_escalated(4)

        # Moderate (3) is not an escalation (matches max in history)
        assert not state.is_escalated(3)

    def test_is_escalated_empty_history(self):
        """is_escalated should return False for empty history."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )
        state.hash_history.clear()

        assert not state.is_escalated(5)


@pytest.mark.unit
class TestAlertStatePreviousPriority:
    """Test getting previous severity priority."""

    def test_get_previous_priority_with_history(self):
        """get_previous_priority should return previous entry's priority."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )

        state.add_hash("updated", 3)
        assert state.get_previous_priority() == 2

    def test_get_previous_priority_single_entry(self):
        """get_previous_priority should return 1 for single entry."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=4,
        )

        assert state.get_previous_priority() == 1

    def test_get_previous_priority_multiple_updates(self):
        """get_previous_priority should track through multiple updates."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=1,
        )

        state.add_hash("hash2", 2)
        state.add_hash("hash3", 3)
        state.add_hash("hash4", 4)

        # Should return priority of second-to-last entry
        assert state.get_previous_priority() == 3


@pytest.mark.unit
class TestAlertStateSerialization:
    """Test to_dict and from_dict methods."""

    def test_to_dict_includes_hash_history(self):
        """to_dict should serialize hash_history."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )

        state.add_hash("updated", 3)

        data = state.to_dict()

        assert "hash_history" in data
        assert isinstance(data["hash_history"], list)
        assert len(data["hash_history"]) == 2

    def test_to_dict_format(self):
        """to_dict should format history as list of [hash, priority, timestamp]."""
        state = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )

        data = state.to_dict()
        entry = data["hash_history"][0]

        assert len(entry) == 3
        assert isinstance(entry[0], str)  # hash
        assert isinstance(entry[1], int)  # priority
        assert isinstance(entry[2], float)  # timestamp

    def test_from_dict_with_hash_history(self):
        """from_dict should restore state from new format."""
        original = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=2,
        )
        original.add_hash("updated", 3)

        data = original.to_dict()
        restored = AlertState.from_dict(data)

        assert restored.alert_id == original.alert_id
        assert len(restored.hash_history) == len(original.hash_history)
        assert restored.content_hash == original.content_hash

    def test_from_dict_migration_old_format(self):
        """from_dict should migrate from old format (single content_hash)."""
        old_format_data = {
            "alert_id": "test-alert",
            "content_hash": "old_hash",
            "first_seen": datetime.now(UTC).isoformat(),
            "last_notified": None,
            "notification_count": 0,
        }

        state = AlertState.from_dict(old_format_data)

        assert state.alert_id == "test-alert"
        assert state.content_hash == "old_hash"
        assert len(state.hash_history) == 1
        assert state.hash_history[0][0] == "old_hash"

    def test_from_dict_round_trip(self):
        """State should survive round-trip serialization."""
        original = AlertState(
            alert_id="test-alert",
            content_hash="initial",
            first_seen=datetime.now(UTC),
            severity_priority=2,
            notification_count=5,
        )

        for i in range(3):
            original.add_hash(f"hash_{i}", i + 2)

        data = original.to_dict()
        restored = AlertState.from_dict(data)

        assert restored.alert_id == original.alert_id
        assert restored.notification_count == original.notification_count
        assert len(restored.hash_history) == len(original.hash_history)
        assert restored.content_hash == original.content_hash
