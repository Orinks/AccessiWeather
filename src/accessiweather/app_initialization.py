"""Initialization helpers for the AccessiWeather application."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import toga

from . import app_helpers, background_tasks, event_handlers, ui_builder
from .config import ConfigManager

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

    # Defer update service initialization to background
    app.update_service = None
    asyncio.get_event_loop().call_soon(_initialize_update_service_deferred, app)

    # Initialize weather client with lazy imports
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

    # Lazy import WeatherDataCache
    from .cache import WeatherDataCache

    offline_cache = WeatherDataCache(cache_dir)
    debug_enabled = bool(getattr(config.settings, "debug_mode", False))
    log_level = logging.DEBUG if debug_enabled else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers:
        handler.setLevel(log_level)

    # Lazy import WeatherClient
    from .weather_client import WeatherClient

    app.weather_client = WeatherClient(
        user_agent="AccessiWeather/2.0",
        data_source=data_source,
        visual_crossing_api_key=visual_crossing_api_key,
        settings=config.settings,
        offline_cache=offline_cache,
    )

    # Lazy import LocationManager
    from .location_manager import LocationManager

    app.location_manager = LocationManager()

    config = app.config_manager.get_config()

    # Lazy import WeatherPresenter
    from .display import WeatherPresenter

    app.presenter = WeatherPresenter(config.settings)

    # Lazy import notifier
    from .notifications.toast_notifier import SafeDesktopNotifier

    app._notifier = SafeDesktopNotifier(
        sound_enabled=bool(getattr(config.settings, "sound_enabled", True)),
        soundpack=getattr(config.settings, "sound_pack", "default"),
    )

    # Initialize AI explanation cache (lazy import)
    from .cache import Cache

    ai_cache_ttl = getattr(config.settings, "ai_cache_ttl", 300)  # 5 minutes default
    app.ai_explanation_cache = Cache(default_ttl=ai_cache_ttl)

    # Lazy import alert components
    from .alert_manager import AlertManager
    from .alert_notification_system import AlertNotificationSystem

    config_dir = str(app.paths.config)
    alert_settings = config.settings.to_alert_settings()
    app.alert_manager = AlertManager(config_dir, alert_settings)
    app.alert_notification_system = AlertNotificationSystem(
        app.alert_manager, app._notifier, config.settings
    )

    # Defer weather history service initialization
    app.weather_history_service = None
    if config.settings.weather_history_enabled:
        asyncio.get_event_loop().call_soon(_initialize_weather_history_deferred, app)

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


def _initialize_update_service_deferred(app: AccessiWeatherApp) -> None:
    """Initialize update service in a deferred manner to not block startup."""
    try:
        from .services import GitHubUpdateService, sync_update_channel_to_service

        app.update_service = GitHubUpdateService(
            app_name="AccessiWeather",
            config_dir=app.config_manager.config_dir if app.config_manager else None,
        )
        sync_update_channel_to_service(app.config_manager, app.update_service)
        logger.info("Update service initialized (deferred)")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to initialize update service: %s", exc)
        app.update_service = None


def _initialize_weather_history_deferred(app: AccessiWeatherApp) -> None:
    """Initialize weather history service in a deferred manner."""
    try:
        from .weather_history import WeatherHistoryService

        app.weather_history_service = WeatherHistoryService()
        logger.info("Weather history service initialized (deferred)")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to initialize weather history service: %s", exc)
        app.weather_history_service = None


def load_initial_data(app: AccessiWeatherApp) -> None:
    """Load persisted configuration and kick off initial data fetches.

    Implements cache-first startup: if cached weather data exists for the current
    location, it is displayed immediately (synchronously) before the async refresh
    begins. This provides instant perceived performance even on slow networks.
    """
    import time

    start_time = time.perf_counter()
    logger.info("Loading initial data (cache-first)")

    try:
        config = app.config_manager.get_config()

        if not config.locations:
            logger.info("No locations configured; waiting for user to add one")
            app_helpers.update_status(app, "Add a location to get started.")
            return

        if not config.current_location:
            logger.info("No current location set")
            return

        # CACHE-FIRST: Check for cached data synchronously for instant startup
        cached_data = None
        if app.weather_client:
            try:
                cached_data = app.weather_client.get_cached_weather(config.current_location)
            except Exception as cache_exc:  # pragma: no cover - defensive logging
                logger.debug("Cache lookup failed (non-fatal): %s", cache_exc)

        if cached_data:
            # Display cached data immediately (synchronously)
            app.current_weather_data = cached_data
            app_helpers.sync_update_weather_displays(app, cached_data)

            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Cached data displayed in %.1fms for %s",
                elapsed,
                config.current_location.name,
            )

            # Show status indicating background refresh is in progress
            app_helpers.update_status(
                app, f"Updating weather for {config.current_location.name}..."
            )
        else:
            logger.info("No cached data available for %s", config.current_location.name)
            app_helpers.update_status(
                app, f"Loading weather for {config.current_location.name}..."
            )

        # Start async refresh for fresh data (runs in background)
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
