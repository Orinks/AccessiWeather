"""Initialization helpers for the AccessiWeather application (wxPython version)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import wx

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

    # Defer update service initialization to background (using wx.CallLater)
    app.update_service = None
    wx.CallLater(100, _initialize_update_service_deferred, app)

    # Initialize weather client with lazy imports
    data_source = config.settings.data_source if config.settings else "auto"
    # Note: visual_crossing_api_key is now a LazySecureStorage object that defers
    # keyring access until first use. We pass it directly to WeatherClient which
    # will access the value lazily when the VisualCrossing client is needed.
    lazy_api_key = config.settings.visual_crossing_api_key if config.settings else ""
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
        visual_crossing_api_key=lazy_api_key,
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

    config_dir_str = str(app.paths.config)
    alert_settings = config.settings.to_alert_settings()
    app.alert_manager = AlertManager(config_dir_str, alert_settings)
    app.alert_notification_system = AlertNotificationSystem(
        app.alert_manager, app._notifier, config.settings
    )

    # Defer weather history service initialization
    app.weather_history_service = None
    if config.settings.weather_history_enabled:
        wx.CallLater(200, _initialize_weather_history_deferred, app)

    # System tray is handled differently in wxPython - skip for now
    # TODO: Implement wx.adv.TaskBarIcon for system tray support
    app.status_icon = None

    logger.info("Application components initialized")


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
    """Load persisted configuration and kick off initial data fetches."""
    logger.info("Loading initial data")

    try:
        config = app.config_manager.get_config()

        if not config.locations:
            logger.info("No locations configured; waiting for user to add one")
            if app.main_window:
                app.main_window.set_status("Add a location to get started.")
        elif config.current_location:
            # Start initial data fetch for current location
            if app.main_window:
                app.main_window.refresh_weather_async()

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to load initial data: %s", exc)
