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

        logger.info("Starting background updates")

        while True:
            # Re-read config each loop to pick up user changes without restart
            config = app.config_manager.get_config()
            update_interval = max(1, int(config.settings.update_interval_minutes)) * 60

            logger.debug("Background update loop: sleeping for %s seconds", update_interval)
            await asyncio.sleep(update_interval)

            if not app.is_updating and app.config_manager and app.config_manager.has_locations():
                logger.info("Performing background weather update for all locations")
                try:
                    # Update all locations to keep cache fresh for instant switching
                    # We use a shorter timeout per location but allow the total process to take longer
                    all_locations = app.config_manager.get_all_locations()
                    current_location = app.config_manager.get_current_location()

                    # Prioritize current location
                    if current_location:
                        logger.info(
                            f"Background update: Prioritizing current location {current_location.name}"
                        )
                        await asyncio.wait_for(
                            event_handlers.refresh_weather_data(app), timeout=45.0
                        )

                    # Then update others in background
                    other_locations = [
                        loc
                        for loc in all_locations
                        if not current_location or loc.name != current_location.name
                    ]

                    if other_locations:
                        logger.info(
                            f"Background update: Refreshing {len(other_locations)} other locations"
                        )
                        for loc in other_locations:
                            if app.weather_client:
                                try:
                                    # Pre-warm cache without updating UI
                                    # Add a small delay to be nice to APIs
                                    await asyncio.sleep(2.0)
                                    await app.weather_client.pre_warm_cache(loc)
                                except Exception as loc_exc:
                                    logger.warning(
                                        f"Failed background update for {loc.name}: {loc_exc}"
                                    )

                    logger.info("Background weather update completed successfully")
                except TimeoutError:
                    logger.error("Background weather update timed out")
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
                    "Skipping background update - is_updating: %s, has_locations: %s",
                    app.is_updating,
                    bool(app.config_manager and app.config_manager.has_locations()),
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
