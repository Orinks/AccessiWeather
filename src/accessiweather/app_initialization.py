"""Initialization helpers for the AccessiWeather application."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import toga

from . import background_tasks, event_handlers, ui_builder
from .alert_manager import AlertManager
from .alert_notification_system import AlertNotificationSystem
from .cache import WeatherDataCache
from .config import ConfigManager
from .display import WeatherPresenter
from .location_manager import LocationManager
from .weather_client import WeatherClient
from .weather_history import WeatherHistoryService

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .app import AccessiWeatherApp


logger = logging.getLogger(__name__)


def initialize_components(app: AccessiWeatherApp) -> None:
    """Initialize core application components for the given app instance."""
    logger.info("Initializing application components")

    app.config_manager = ConfigManager(app)
    config = app.config_manager.load_config()

    try:
        from .services import GitHubUpdateService

        app.update_service = GitHubUpdateService(
            app_name="AccessiWeather",
            config_dir=app.config_manager.config_dir if app.config_manager else None,
        )
        logger.info("Update service initialized")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to initialize update service: %s", exc)
        app.update_service = None

    data_source = config.settings.data_source if config.settings else "auto"
    visual_crossing_api_key = config.settings.visual_crossing_api_key if config.settings else ""
    config_dir_value = getattr(app.config_manager, "config_dir", None)
    cache_root: Path | None = None
    if config_dir_value is not None:
        try:
            cache_root = Path(config_dir_value)
        except (TypeError, ValueError):  # pragma: no cover - defensive logging
            cache_root = None
    if cache_root is None:
        fallback_dir = getattr(app.paths, "config", None)
        try:
            cache_root = Path(fallback_dir) if fallback_dir is not None else Path.cwd()
        except (TypeError, ValueError):  # pragma: no cover - defensive logging
            cache_root = Path.cwd()
    cache_dir = cache_root / "weather_cache"
    offline_cache = WeatherDataCache(cache_dir)
    app.weather_client = WeatherClient(
        user_agent="AccessiWeather/2.0",
        data_source=data_source,
        visual_crossing_api_key=visual_crossing_api_key,
        settings=config.settings,
        offline_cache=offline_cache,
    )

    app.location_manager = LocationManager()

    config = app.config_manager.get_config()
    app.presenter = WeatherPresenter(config.settings)

    from .notifications.toast_notifier import SafeDesktopNotifier

    app._notifier = SafeDesktopNotifier(
        sound_enabled=bool(getattr(config.settings, "sound_enabled", True)),
        soundpack=getattr(config.settings, "sound_pack", "default"),
    )

    config_dir = str(app.paths.config)
    alert_settings = config.settings.to_alert_settings()
    app.alert_manager = AlertManager(config_dir, alert_settings)
    app.alert_notification_system = AlertNotificationSystem(app.alert_manager, app._notifier)

    # Initialize weather history service
    if config.settings.weather_history_enabled:
        app.weather_history_service = WeatherHistoryService()
        logger.info("Weather history service initialized")
    else:
        app.weather_history_service = None

    try:
        if bool(getattr(config.settings, "minimize_to_tray", False)):
            ui_builder.initialize_system_tray(app)
        else:
            app.status_icon = None
    except Exception:  # pragma: no cover - defensive logging
        app.status_icon = None

    logger.info("Application components initialized")

    if config.settings.debug_mode:
        test_alert_command = toga.Command(
            lambda widget: asyncio.create_task(event_handlers.test_alert_notification(app, widget)),
            text="Test Alert Notification",
            tooltip="Send a test alert notification",
            group=toga.Group.COMMANDS,
        )
        app.commands.add(test_alert_command)


def load_initial_data(app: AccessiWeatherApp) -> None:
    """Load persisted configuration and kick off initial data fetches."""
    logger.info("Loading initial data")

    try:
        config = app.config_manager.get_config()

        if not config.locations:
            logger.info("No locations found, adding default locations")
            task = asyncio.create_task(background_tasks.add_initial_locations(app))
            task.add_done_callback(background_tasks.task_done_callback)
        else:
            if config.current_location:
                task = asyncio.create_task(event_handlers.refresh_weather_data(app))
                task.add_done_callback(background_tasks.task_done_callback)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to load initial data: %s", exc)
