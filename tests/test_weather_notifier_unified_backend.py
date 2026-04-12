from __future__ import annotations

from unittest.mock import patch


class TestWeatherNotifierUsesSafeDesktopNotifier:
    def test_notify_alerts_uses_send_notification(self):
        with patch(
            "accessiweather.notifications.weather_notifier.SafeDesktopNotifier"
        ) as notifier_cls:
            notifier = notifier_cls.return_value
            from accessiweather.notifications.weather_notifier import WeatherNotifier

            weather_notifier = WeatherNotifier(enable_persistence=False)
            weather_notifier.notify_alerts(alert_count=2, new_count=1, updated_count=1)

        notifier.send_notification.assert_called_once_with(
            title="Weather Alerts",
            message="1 new alert, 1 updated alert in your area",
            timeout=10,
        )

    def test_show_notification_uses_send_notification(self):
        alert = {
            "event": "Tornado Warning",
            "headline": "Tornado warning in your area",
        }

        with patch(
            "accessiweather.notifications.weather_notifier.SafeDesktopNotifier"
        ) as notifier_cls:
            notifier = notifier_cls.return_value
            from accessiweather.notifications.weather_notifier import WeatherNotifier

            weather_notifier = WeatherNotifier(enable_persistence=False)
            weather_notifier.show_notification(alert, is_update=False)

        notifier.send_notification.assert_called_once_with(
            title="Weather Tornado Warning",
            message="Tornado warning in your area",
            timeout=10,
        )
