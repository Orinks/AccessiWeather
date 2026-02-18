"""Debug notification test helpers."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from ..alert_manager import AlertManager
from ..alert_notification_system import AlertNotificationSystem
from ..models import AppSettings, Location, WeatherAlert, WeatherAlerts, WeatherData
from .notification_event_manager import NotificationEventManager
from .toast_notifier import SafeDesktopNotifier

logger = logging.getLogger(__name__)


def _store_result(results: dict[str, dict], key: str, passed: bool, message: str) -> None:
    """Store a single test result and log outcome."""
    results[key] = {"passed": passed, "message": message}
    if passed:
        logger.info("Notification test passed: %s (%s)", key, message)
    else:
        logger.error("Notification test failed: %s (%s)", key, message)


def _run_async(coro):
    """Run a coroutine from synchronous debug test code."""
    return asyncio.run(coro)


def run_notification_test(app) -> dict[str, dict | bool | int]:
    """
    Run end-to-end notification debug tests.

    Returns a dictionary with per-test pass/fail status and summary counters.
    """
    results: dict[str, dict] = {}
    settings = AppSettings()
    try:
        settings = app.config_manager.get_settings()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Using default settings for notification test: %s", exc)

    # 1) Test SafeDesktopNotifier.send_notification() directly
    try:
        notifier = SafeDesktopNotifier(
            app_name="AccessiWeather Debug Test",
            sound_enabled=bool(getattr(settings, "sound_enabled", True)),
            soundpack=getattr(settings, "sound_pack", "default"),
        )
        sent = notifier.send_notification(
            title="AccessiWeather Notification Test",
            message="Direct SafeDesktopNotifier test",
            timeout=5,
            play_sound=False,
        )
        _store_result(
            results,
            "safe_desktop_notifier",
            bool(sent),
            "SafeDesktopNotifier.send_notification returned success"
            if sent
            else "SafeDesktopNotifier.send_notification returned False",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("SafeDesktopNotifier test raised an exception")
        _store_result(results, "safe_desktop_notifier", False, f"Exception: {exc}")

    # 2) Test AlertNotificationSystem with a mock WeatherAlert
    try:
        with tempfile.TemporaryDirectory(prefix="accessiweather-alert-test-") as tmpdir:
            alert_manager = AlertManager(tmpdir)
            mock_notifier = MagicMock()
            mock_notifier.send_notification = MagicMock(return_value=True)
            notification_system = AlertNotificationSystem(
                alert_manager=alert_manager,
                notifier=mock_notifier,
                settings=settings,
            )
            alert = WeatherAlert(
                id="debug-alert-test",
                title="Debug Test Alert",
                description="Alert notification system debug test.",
                severity="Moderate",
                urgency="Expected",
                certainty="Likely",
                event="Debug Notification Test",
                expires=datetime.now(UTC) + timedelta(hours=1),
            )
            sent_count = _run_async(
                notification_system.process_and_notify(WeatherAlerts(alerts=[alert]))
            )
            called = bool(mock_notifier.send_notification.called)
            passed = sent_count >= 1 and called
            _store_result(
                results,
                "alert_notification_system",
                passed,
                f"process_and_notify sent {sent_count} notifications; notifier_called={called}",
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("AlertNotificationSystem test raised an exception")
        _store_result(results, "alert_notification_system", False, f"Exception: {exc}")

    # 3) Test discussion update notification path
    try:
        location_name = "Debug Test Location"
        try:
            current_location = app.config_manager.get_current_location()
            if current_location and current_location.name:
                location_name = current_location.name
        except Exception:  # pragma: no cover - defensive
            pass

        event_manager = NotificationEventManager(state_file=None)
        event_settings = AppSettings()
        event_settings.notify_discussion_update = True
        event_settings.notify_severe_risk_change = False
        event_settings.sound_enabled = bool(getattr(settings, "sound_enabled", True))

        location = Location(name=location_name, latitude=0.0, longitude=0.0)
        first_time = datetime.now(UTC).replace(microsecond=0)
        first_data = WeatherData(
            location=location,
            discussion="Initial forecast discussion",
            discussion_issuance_time=first_time,
        )
        initial_events = event_manager.check_for_events(first_data, event_settings, location_name)

        updated_data = WeatherData(
            location=location,
            discussion="Updated forecast discussion",
            discussion_issuance_time=first_time + timedelta(hours=1),
        )
        update_events = event_manager.check_for_events(updated_data, event_settings, location_name)

        mock_notifier = MagicMock()
        mock_notifier.send_notification = MagicMock(return_value=True)
        sent_success = False
        if update_events:
            event = update_events[0]
            sent_success = bool(
                mock_notifier.send_notification(
                    title=event.title,
                    message=event.message,
                    timeout=10,
                    sound_event=event.sound_event,
                    play_sound=event_settings.sound_enabled,
                )
            )

        passed = len(initial_events) == 0 and len(update_events) >= 1 and sent_success
        _store_result(
            results,
            "discussion_update_path",
            passed,
            "initial_events=0, update_events>=1, notifier_send=True"
            if passed
            else (
                f"initial_events={len(initial_events)}, "
                f"update_events={len(update_events)}, notifier_send={sent_success}"
            ),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Discussion update path test raised an exception")
        _store_result(results, "discussion_update_path", False, f"Exception: {exc}")

    passed_count = sum(1 for item in results.values() if item.get("passed"))
    total_count = len(results)
    all_passed = passed_count == total_count

    summary: dict[str, dict | bool | int] = dict(results)
    summary["passed_count"] = passed_count
    summary["total_count"] = total_count
    summary["all_passed"] = all_passed
    logger.info(
        "Notification tests complete: %d/%d passed (all_passed=%s)",
        passed_count,
        total_count,
        all_passed,
    )
    return summary
