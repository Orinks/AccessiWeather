"""Tests for debug notification test helpers."""

from __future__ import annotations

from types import SimpleNamespace

from accessiweather.models import AppSettings, Location
from accessiweather.notifications import notification_test


class _FakeConfigManager:
    def __init__(self) -> None:
        self._settings = AppSettings()
        self._location = Location(name="Test City", latitude=40.0, longitude=-74.0)

    def get_settings(self) -> AppSettings:
        return self._settings

    def get_current_location(self) -> Location:
        return self._location


class _FakeAlertManager:
    def __init__(self, _state_dir: str) -> None:
        self._state_dir = _state_dir


class _FakeAlertNotificationSystem:
    def __init__(self, alert_manager, notifier, settings) -> None:
        self.alert_manager = alert_manager
        self.notifier = notifier
        self.settings = settings

    async def process_and_notify(self, _alerts) -> int:
        self.notifier.send_notification(title="x", message="y", timeout=5, play_sound=False)
        return 1


def _build_fake_app() -> SimpleNamespace:
    return SimpleNamespace(
        config_manager=_FakeConfigManager(),
        paths=SimpleNamespace(config="/tmp"),
    )


def test_run_notification_test_all_pass(monkeypatch):
    class _FakeNotifier:
        def __init__(self, **_kwargs) -> None:
            pass

        def send_notification(self, **_kwargs) -> bool:
            return True

    monkeypatch.setattr(notification_test, "SafeDesktopNotifier", _FakeNotifier)
    monkeypatch.setattr(notification_test, "AlertManager", _FakeAlertManager)
    monkeypatch.setattr(notification_test, "AlertNotificationSystem", _FakeAlertNotificationSystem)

    results = notification_test.run_notification_test(_build_fake_app())

    assert results["all_passed"] is True
    assert results["passed_count"] == 3
    assert results["total_count"] == 3
    assert results["safe_desktop_notifier"]["passed"] is True
    assert results["alert_notification_system"]["passed"] is True
    assert results["discussion_update_path"]["passed"] is True


def test_run_notification_test_records_failure(monkeypatch):
    class _FailingNotifier:
        def __init__(self, **_kwargs) -> None:
            pass

        def send_notification(self, **_kwargs) -> bool:
            return False

    monkeypatch.setattr(notification_test, "SafeDesktopNotifier", _FailingNotifier)
    monkeypatch.setattr(notification_test, "AlertManager", _FakeAlertManager)
    monkeypatch.setattr(notification_test, "AlertNotificationSystem", _FakeAlertNotificationSystem)

    results = notification_test.run_notification_test(_build_fake_app())

    assert results["all_passed"] is False
    assert results["passed_count"] == 2
    assert results["total_count"] == 3
    assert results["safe_desktop_notifier"]["passed"] is False
    assert results["alert_notification_system"]["passed"] is True
    assert results["discussion_update_path"]["passed"] is True
