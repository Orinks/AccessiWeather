"""Notification event data helpers for WeatherClient."""

from __future__ import annotations

import asyncio
import inspect
import logging

from .alert_lifecycle import diff_alerts
from .models import (
    Location,
    MinutelyPrecipitationForecast,
    WeatherAlerts,
    WeatherData,
)
from .notifications.minutely_precipitation import parse_pirate_weather_minutely_block
from .weather_client_alerts import AlertAggregator

logger = logging.getLogger(__name__)


class WeatherClientNotificationMixin:
    async def get_notification_event_data(self, location: Location) -> WeatherData:
        """Fetch only lightweight data needed for alert/discussion/risk notifications."""
        logger.info("Fetching notification event data for %s", location.name)
        weather_data = WeatherData(location=location)

        try:
            if self.data_source in ("auto", "nws") and self._is_us_location(location):
                # Use discussion-only fetch so a forecast API failure can never
                # silently suppress AFD update notifications.
                discussion_task = asyncio.create_task(self._get_nws_discussion_only(location))
                alerts_task = asyncio.create_task(self._get_nws_alerts(location))
                discussion_result, alerts_result = await asyncio.gather(
                    discussion_task, alerts_task, return_exceptions=True
                )
                if isinstance(discussion_result, Exception):
                    raise discussion_result
                if isinstance(alerts_result, Exception):
                    raise alerts_result
                discussion, discussion_issuance_time = discussion_result
                alerts = alerts_result
                logger.debug(
                    "get_notification_event_data: discussion=%s issuance=%s alerts=%s",
                    "ok" if discussion else "None",
                    discussion_issuance_time,
                    len(alerts.alerts) if alerts and alerts.alerts else 0,
                )
                weather_data.discussion = discussion
                weather_data.discussion_issuance_time = discussion_issuance_time
                weather_data.alerts = alerts or WeatherAlerts(alerts=[])
            elif self.data_source in ("auto", "pirateweather") and (
                pirate_weather_client := self._pirate_weather_client_for_location(location)
            ):
                current_task = asyncio.create_task(
                    pirate_weather_client.get_current_conditions(location)
                )
                alerts_task = asyncio.create_task(pirate_weather_client.get_alerts(location))
                current_result, alerts_result = await asyncio.gather(
                    current_task, alerts_task, return_exceptions=True
                )
                if isinstance(current_result, Exception):
                    raise current_result
                if isinstance(alerts_result, Exception):
                    raise alerts_result
                weather_data.current = current_result
                weather_data.alerts = alerts_result or WeatherAlerts(alerts=[])
            else:
                # openmeteo provides no alerts; also handles misconfigured clients
                weather_data.alerts = WeatherAlerts(alerts=[])

            # Only fetch PW minutely in the lightweight poll if the user actually
            # wants precipitation start/stop notifications AND PW is the active source.
            # This avoids an extra API call every 60s for users who don't use it.
            if (
                self.data_source in ("auto", "pirateweather")
                and self.pirate_weather_client
                and self.settings
            ):
                _want_start = getattr(self.settings, "notify_minutely_precipitation_start", False)
                _want_stop = getattr(self.settings, "notify_minutely_precipitation_stop", False)
                _want_likelihood = getattr(self.settings, "notify_precipitation_likelihood", False)
                if (_want_start or _want_stop or _want_likelihood) and (
                    self._should_fetch_minutely_precipitation(location)
                ):
                    weather_data.minutely_precipitation = await self._get_pirate_weather_minutely(
                        location
                    )
                    self._last_minutely_poll_by_location[self._location_key(location)] = (
                        self._utcnow()
                    )

            # In auto mode the full refresh stores AlertAggregator.aggregate_alerts(...)
            # output in _previous_alerts. The lightweight poll must produce the same
            # canonical shape or the two paths will alternate and diff_alerts will fire
            # phantom "new"/"updated" notifications every refresh cycle.
            if self.data_source == "auto" and weather_data.alerts is not None:
                weather_data.alerts = AlertAggregator().aggregate_alerts(weather_data.alerts, None)

            loc_key = self._location_key(location)
            previous_alerts = self._previous_alerts.get(loc_key)
            if self.data_source in ("auto", "nws"):
                _cancel_refs = await self._fetch_nws_cancel_references()
            else:
                _cancel_refs = set()
            weather_data.alert_lifecycle_diff = diff_alerts(
                previous_alerts, weather_data.alerts, confirmed_cancel_ids=_cancel_refs
            )
            if weather_data.alerts is not None:
                self._previous_alerts[loc_key] = weather_data.alerts
        except Exception as exc:
            logger.error("Failed to fetch notification event data for %s: %s", location.name, exc)
            weather_data.alerts = weather_data.alerts or WeatherAlerts(alerts=[])

        return weather_data

    async def _get_pirate_weather_minutely(
        self, location: Location
    ) -> MinutelyPrecipitationForecast | None:
        """Fetch Pirate Weather minutely precipitation when a client is configured."""
        client = getattr(self, "pirate_weather_client", None)
        if client is None:
            return None

        for method_name in ("get_minutely_forecast", "get_forecast"):
            method = getattr(client, method_name, None)
            if not callable(method):
                continue
            try:
                result = method(location)
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, dict):
                    units = getattr(client, "units", "si")
                    if not isinstance(units, str):
                        units = "si"
                    return parse_pirate_weather_minutely_block(result, units=units)
            except TypeError:
                logger.debug(
                    "Pirate Weather client method %s has an unsupported signature", method_name
                )
            except Exception as exc:
                logger.debug("Pirate Weather minutely fetch via %s failed: %s", method_name, exc)
                return None

        return None
