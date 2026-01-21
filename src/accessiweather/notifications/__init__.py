"""
Notifications package for AccessiWeather.

This package provides notification functionality including:
- Alert-based notifications (weather alerts from NWS, Visual Crossing)
- Event-based notifications (AFD updates, severe risk level changes)
- Sound playback for notifications
- Desktop toast notifications
"""

# Sound and alert mapper - always available
from .alert_sound_mapper import choose_sound_event, get_candidate_sound_events

# Event-based notifications
from .notification_event_manager import (
    NotificationEvent,
    NotificationEventManager,
    NotificationState,
)
from .sound_player import (
    get_available_sound_packs,
    get_sound_file,
    play_error_sound,
    play_exit_sound,
    play_exit_sound_blocking,
    play_notification_sound,
    play_sample_sound,
    play_startup_sound,
    play_success_sound,
)

# Desktop notifications
from .toast_notifier import SafeDesktopNotifier
from .weather_notifier import WeatherNotifier

__all__ = [
    # Alert sound mapping
    "choose_sound_event",
    "get_candidate_sound_events",
    # Sound player
    "get_available_sound_packs",
    "get_sound_file",
    "play_error_sound",
    "play_exit_sound",
    "play_exit_sound_blocking",
    "play_notification_sound",
    "play_sample_sound",
    "play_startup_sound",
    "play_success_sound",
    # Event notifications
    "NotificationEvent",
    "NotificationEventManager",
    "NotificationState",
    # Desktop notifications
    "SafeDesktopNotifier",
    "WeatherNotifier",
]
