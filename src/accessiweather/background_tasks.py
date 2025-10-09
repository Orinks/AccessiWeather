"""Background task helpers for AccessiWeather."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from . import event_handlers

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from .app import AccessiWeatherApp


logger = logging.getLogger(__name__)


async def start_background_updates(app: AccessiWeatherApp) -> None:
    """Start periodic background weather updates."""
    try:
        if not app.config_manager:
            logger.warning("Config manager not available, skipping background updates")
            return

        config = app.config_manager.get_config()
        update_interval = config.settings.update_interval_minutes * 60

        logger.info(
            "Starting background updates every %s minutes",
            config.settings.update_interval_minutes,
        )

        while True:
            logger.debug("Background update loop: sleeping for %s seconds", update_interval)
            await asyncio.sleep(update_interval)

            if (
                not app.is_updating
                and app.config_manager
                and app.config_manager.get_current_location()
            ):
                logger.info("Performing background weather update")
                try:
                    await asyncio.wait_for(event_handlers.refresh_weather_data(app), timeout=60.0)
                    logger.info("Background weather update completed successfully")
                except TimeoutError:
                    logger.error("Background weather update timed out after 60 seconds")
                    app.is_updating = False
                    if app.refresh_button:
                        app.refresh_button.enabled = True
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.error("Background weather update failed: %s", exc)
                    app.is_updating = False
                    if app.refresh_button:
                        app.refresh_button.enabled = True
            else:
                logger.debug(
                    "Skipping background update - is_updating: %s, has_location: %s",
                    app.is_updating,
                    bool(app.config_manager and app.config_manager.get_current_location()),
                )

    except asyncio.CancelledError:
        logger.info("Background updates cancelled")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Background update error: %s", exc)


def task_done_callback(task: asyncio.Task) -> None:
    """Consume exceptions from background tasks to avoid warnings."""
    try:
        _ = task.result()
    except asyncio.CancelledError:
        logger.debug("Async task cancelled")
    except Exception as exc:  # noqa: BLE001
        logger.error("Async task failed: %s", exc)


async def add_initial_locations(app: AccessiWeatherApp) -> None:
    """Add initial locations for first-time users."""
    try:
        location = await app.location_manager.get_current_location_from_ip()

        if location:
            app.config_manager.add_location(location.name, location.latitude, location.longitude)
            logger.info("Added current location from IP: %s", location.name)

        test_locations = [
            ("New York, NY", 40.7128, -74.0060),
            ("Los Angeles, CA", 34.0522, -118.2437),
            ("Tokyo, Japan", 35.6762, 139.6503),
            ("London, UK", 51.5074, -0.1278),
            ("Sydney, Australia", -33.8688, 151.2093),
            ("Paris, France", 48.8566, 2.3522),
        ]

        for name, lat, lon in test_locations:
            app.config_manager.add_location(name, lat, lon)
            logger.info("Added test location: %s", name)

        if location:
            app.config_manager.set_current_location(location.name)
        else:
            app.config_manager.set_current_location("Tokyo, Japan")

        app._update_location_selection()
        await event_handlers.refresh_weather_data(app)

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to add initial locations: %s", exc)
