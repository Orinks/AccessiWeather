"""Initialization helpers for the AccessiWeather application."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import toga

from . import app_helpers, background_tasks, event_handlers, ui_builder
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

    app.config_manager = ConfigManager(
        app,
        config_dir=getattr(app, "_config_dir", None),
        portable_mode=getattr(app, "_portable_mode", False),
    )
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
    debug_enabled = bool(getattr(config.settings, "debug_mode", False))
    log_level = logging.DEBUG if debug_enabled else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers:
        handler.setLevel(log_level)
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
            logger.info("No locations configured; waiting for user to add one")
            app_helpers.update_status(app, "Add a location to get started.")
        elif config.current_location:
            # Start initial data fetch for current location
            task = asyncio.create_task(event_handlers.refresh_weather_data(app))
            task.add_done_callback(background_tasks.task_done_callback)

            # Kick off a background pre-warm for all other locations
            # This ensures that switching locations later will be fast
            if len(config.locations) > 1:
                asyncio.create_task(_pre_warm_other_locations(app))

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to load initial data: %s", exc)


async def _pre_warm_other_locations(app: AccessiWeatherApp) -> None:
    """Background task to pre-warm cache for non-active locations on startup."""
    try:
        # Wait a bit to let the app settle and primary location load first
        await asyncio.sleep(5.0)

        if not app.config_manager or not app.weather_client:
            return

        current_location = app.config_manager.get_current_location()
        all_locations = app.config_manager.get_all_locations()

        other_locations = [
            loc
            for loc in all_locations
            if not current_location or loc.name != current_location.name
        ]

        if not other_locations:
            return

        logger.info(f"Startup: Pre-warming cache for {len(other_locations)} other locations")

        for loc in other_locations:
            try:
                # Be gentle with APIs
                await asyncio.sleep(2.0)
                if app.weather_client:
                    await app.weather_client.pre_warm_cache(loc)
            except Exception as e:
                logger.debug(f"Startup pre-warm failed for {loc.name}: {e}")

        logger.info("Startup: Cache pre-warming completed")

    except Exception as exc:
        logger.error(f"Error in startup cache pre-warming: {exc}")
