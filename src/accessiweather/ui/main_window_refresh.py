"""MainWindowRefreshMixin helpers for the main window."""
# ruff: noqa: F403, F405

from __future__ import annotations

from .main_window_shared import *  # noqa: F403


class MainWindowRefreshMixin:
    def _set_current_location(self, location_name: str) -> None:
        """Set the current location and persist to config."""
        try:
            # set_current_location expects a string (location name), not a Location object
            result = self.app.config_manager.set_current_location(location_name)
            if not result:
                logger.error(
                    f"Failed to set current location '{location_name}': "
                    "location not found or save failed"
                )
            else:
                logger.info(f"Current location set and saved: {location_name}")
        except Exception as e:
            logger.error(f"Failed to set current location: {e}")

    def refresh_weather_async(self, force_refresh: bool = False) -> None:
        """
        Refresh weather data asynchronously.

        When the All Locations view is active the summary is rebuilt from
        whatever is currently in the cache — no new network requests are made.
        """
        # All Locations view: fetch fresh data for all locations sequentially then re-render.
        if getattr(self, "_all_locations_active", False):
            self.refresh_button.Disable()
            self.app.run_async(self._fetch_all_locations_data())
            return

        if self.app.is_updating and not force_refresh:
            logger.debug("Already updating, skipping refresh")
            return

        # Increment generation to invalidate any in-flight fetches
        self._fetch_generation += 1
        self.app.is_updating = True
        self.refresh_button.Disable()

        # Run async weather fetch with current generation
        generation = self._fetch_generation
        self.app.run_async(
            self._fetch_weather_data(force_refresh=force_refresh, generation=generation)
        )

    def refresh_notification_events_async(self) -> None:
        """Run a lightweight event check without refreshing the full weather UI."""
        main_window_notification_events.refresh_notification_events_async(self)

    async def _fetch_notification_event_data(self) -> None:
        """Fetch only the lightweight data needed for notifications."""
        await main_window_notification_events.fetch_notification_event_data(self)

    async def _fetch_weather_data(self, force_refresh: bool = False, generation: int = 0) -> None:
        """Fetch weather data in background."""
        try:
            location = self.app.config_manager.get_current_location()
            if not location:
                wx.CallAfter(self._on_weather_error, "No location selected")
                return

            # For Nationwide location, fetch discussion summaries instead of weather
            if location.name == "Nationwide":
                wx.CallAfter(
                    self.current_conditions.SetValue,
                    "Fetching nationwide weather discussions from NWS, SPC, NHC, and CPC...\n"
                    "This may take a moment.",
                )
                wx.CallAfter(self._set_forecast_sections, "", "")
                await self._fetch_nationwide_discussions(generation)
                return

            # Fetch weather data - pass the Location object directly
            # force_refresh=True bypasses cache (used when switching locations)
            weather_data = await self.app.weather_client.get_weather_data(
                location, force_refresh=force_refresh
            )

            # Only update UI if this fetch is still current (not superseded by a newer one)
            if generation != self._fetch_generation:
                logger.debug(
                    f"Discarding stale fetch for {location.name} "
                    f"(gen {generation} < {self._fetch_generation})"
                )
                return

            # Update UI on main thread
            wx.CallAfter(self._on_weather_data_received, weather_data)

            # Pre-warm NWS text products (AFD/HWO/SPS) for the active location
            # so the Forecast Products dialog and Unit 10/11 notification
            # checks see fresh data without issuing an on-demand fetch.
            await self._pre_warm_products_for_location(location)

            # Pre-warm cache for other locations in background (non-blocking)
            if not force_refresh:
                await self._pre_warm_other_locations(location)

        except Exception as e:
            logger.error(f"Failed to fetch weather data: {e}")
            wx.CallAfter(self._on_weather_error, str(e))

    def _get_discussion_service(self):
        """Get or create the shared NationalDiscussionService instance."""
        if not hasattr(self, "_discussion_service") or self._discussion_service is None:
            from ..services.national_discussion_service import NationalDiscussionService

            self._discussion_service = NationalDiscussionService()
        return self._discussion_service

    async def _fetch_nationwide_discussions(self, generation: int) -> None:
        """Fetch nationwide discussion summaries and display in weather fields."""
        import asyncio

        try:
            service = self._get_discussion_service()
            # Run synchronous fetch in thread to avoid blocking
            discussions = await asyncio.to_thread(service.fetch_all_discussions)

            if generation != self._fetch_generation:
                return

            # Build current conditions text (short range + SPC day 1)
            current_parts = ["=== Nationwide Weather Summary ===\n"]
            wpc = discussions.get("wpc", {})
            if wpc.get("short_range", {}).get("text"):
                current_parts.append(
                    f"--- {wpc['short_range']['title']} ---\n{wpc['short_range']['text']}\n"
                )
            spc = discussions.get("spc", {})
            if spc.get("day1", {}).get("text"):
                current_parts.append(f"--- {spc['day1']['title']} ---\n{spc['day1']['text']}\n")
            current_text = "\n".join(current_parts)

            # Build forecast text (extended + CPC outlooks)
            forecast_parts = ["=== Extended Outlook ===\n"]
            if wpc.get("extended", {}).get("text"):
                forecast_parts.append(
                    f"--- {wpc['extended']['title']} ---\n{wpc['extended']['text']}\n"
                )
            cpc = discussions.get("cpc", {})
            if cpc.get("outlook", {}).get("text"):
                forecast_parts.append(
                    f"--- {cpc['outlook']['title']} ---\n{cpc['outlook']['text']}\n"
                )
            forecast_text = "\n".join(forecast_parts)

            wx.CallAfter(self._on_nationwide_data_received, current_text, forecast_text)

        except Exception as e:
            logger.error(f"Failed to fetch nationwide discussions: {e}")
            wx.CallAfter(self._on_weather_error, str(e))

    def _on_nationwide_data_received(self, current_text: str, forecast_text: str) -> None:
        """Handle received nationwide discussion data (called on main thread)."""
        try:
            self.current_conditions.SetValue(current_text)
            self._set_forecast_sections(forecast_text, "")
            self.stale_warning_label.SetLabel("")
        except Exception as e:
            logger.error(f"Error updating nationwide display: {e}")
        finally:
            self.app.is_updating = False
            self.refresh_button.Enable()

    async def _fetch_all_locations_data(self) -> None:
        """Fetch fresh weather data for all saved locations sequentially, then re-render summary."""
        try:
            all_locations = [
                loc
                for loc in self.app.config_manager.get_all_locations()
                if loc.name != "Nationwide"
            ]
            if all_locations and self.app.weather_client:
                await self.app.weather_client.pre_warm_batch(all_locations)
        except Exception as e:
            logger.error(f"Failed to refresh all locations: {e}")
        finally:
            wx.CallAfter(self._on_all_locations_refresh_complete)

    def _on_all_locations_refresh_complete(self) -> None:
        """Handle completion of all-locations background refresh on the main thread."""
        if getattr(self, "_all_locations_active", False):
            self._show_all_locations_summary()
        self.refresh_button.Enable()
        self.app.is_updating = False

    async def _pre_warm_other_locations(self, current_location: Location) -> None:
        """Pre-warm cache for non-current locations so switching is instant."""
        try:
            all_locations = self.app.config_manager.get_all_locations()
            uncached = [
                loc
                for loc in all_locations
                if loc.name != current_location.name
                and not (
                    self.app.weather_client.get_cached_weather(loc)
                    and self.app.weather_client.get_cached_weather(loc).has_any_data()
                )
            ]
            if uncached:
                logger.debug(f"Pre-warming cache for {len(uncached)} locations")
                await self.app.weather_client.pre_warm_batch(uncached)

            # Pre-warm NWS text products (AFD/HWO/SPS) for every non-active
            # saved US location. Failure isolation is per-(product, location):
            # one failure never cascades to other products or other locations.
            for loc in all_locations:
                if loc.name == current_location.name:
                    continue
                await self._pre_warm_products_for_location(loc)
        except Exception as e:
            logger.debug(f"Cache pre-warm failed (non-critical): {e}")

    async def _pre_warm_products_for_location(self, location: Location) -> None:
        """
        Pre-warm AFD/HWO/SPS caches for a single location.

        Non-US locations and US locations without a populated ``cwa_office``
        are skipped. Each product fetch is wrapped in its own try/except so
        one failure (e.g. an NWS 404 for HWO) never prevents the next product
        type or subsequent locations from being pre-warmed.
        """
        # Nationwide is a synthetic entry with no real CWA — skip it cheaply.
        if location.name == "Nationwide":
            return

        # Local import avoids a hard dependency on services at module-import
        # time for the stripped-down test fixtures that stub self.
        from ..services.zone_enrichment_service import _is_us_location
        from ..weather_client_nws import TextProductFetchError

        if not _is_us_location(location):
            return
        if not getattr(location, "cwa_office", None):
            return

        try:
            service = self._get_forecast_product_service()
        except Exception:  # noqa: BLE001
            logger.debug("ForecastProductService unavailable for pre-warm", exc_info=True)
            return

        for product_type in ("AFD", "HWO", "SPS"):
            try:
                await service.get(product_type, location.cwa_office)
            except TextProductFetchError:
                logger.debug(
                    "Pre-warm %s for %s (%s) failed",
                    product_type,
                    location.name,
                    location.cwa_office,
                )
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Unexpected pre-warm failure for %s at %s",
                    product_type,
                    location.name,
                    exc_info=True,
                )

    def _on_weather_data_received(self, weather_data) -> None:
        """Handle received weather data (called on main thread)."""
        # Guard: if we switched to All Locations view, ignore stale single-location data.
        if getattr(self, "_all_locations_active", False):
            logger.debug("Ignoring stale weather data received while All Locations view is active")
            return
        try:
            self.app.current_weather_data = weather_data
            self._update_precipitation_timeline_menu_state(weather_data)

            # Use presenter to create formatted presentation
            presentation = self.app.presenter.present(weather_data)

            # Update current conditions (with data source attribution appended)
            current_text = ""
            if presentation.current_conditions:
                current_text = presentation.current_conditions.fallback_text
            else:
                current_text = "No current conditions available."

            # Append data source attribution to current conditions for screen reader accessibility
            if presentation.source_attribution and presentation.source_attribution.summary_text:
                current_text += f"\n\n{presentation.source_attribution.summary_text}"

            self.current_conditions.SetValue(current_text)

            # Update stale/cached data warning
            if presentation.status_messages:
                warning_text = " ".join(presentation.status_messages)
                self.stale_warning_label.SetLabel(warning_text)
            else:
                self.stale_warning_label.SetLabel("")

            # Update forecast
            if presentation.forecast:
                daily_sections = [presentation.forecast.daily_section_text]
                if presentation.forecast.marine_section_text:
                    daily_sections.append(presentation.forecast.marine_section_text)
                daily_text = "\n\n".join(section for section in daily_sections if section).rstrip()
                daily_text = daily_text or "No daily forecast available."
                hourly_text = (
                    presentation.forecast.hourly_section_text or "No hourly forecast available."
                )
                self._set_forecast_sections(daily_text, hourly_text)
                if presentation.forecast.mobility_briefing:
                    self.append_event_center_entry(
                        presentation.forecast.mobility_briefing,
                        category="Briefing",
                    )
            else:
                self._set_forecast_sections(
                    "No daily forecast available.", "No hourly forecast available."
                )

            # Update lifecycle label map from the current active alerts, then refresh the alerts list.
            if weather_data.alerts is not None:
                from accessiweather.alert_lifecycle import compute_lifecycle_labels

                active_alerts = weather_data.alerts.get_active_alerts()
                self._alert_lifecycle_labels = compute_lifecycle_labels(active_alerts)

            # Update alerts
            self._update_alerts(weather_data.alerts, self._alert_lifecycle_labels)

            # Process alert notifications on full refresh too (AlertManager deduplicates
            # so the lightweight event poll won't re-notify for the same alerts).
            if (
                weather_data.alerts
                and weather_data.alerts.has_alerts()
                and self.app.alert_notification_system
            ):
                active_alerts = weather_data.alerts.get_active_alerts()
                logger.info(
                    "[notify-ui] full refresh scheduling alert processing for %d active alert(s): %s",
                    len(active_alerts),
                    [
                        {
                            "id": alert.get_unique_id(),
                            "event": alert.event,
                            "severity": alert.severity,
                        }
                        for alert in active_alerts
                    ],
                )
                self.app.run_async(
                    self.app.alert_notification_system.process_and_notify(weather_data.alerts)
                )

            location = self.app.config_manager.get_current_location()
            location_name = location.name if location else "Unknown"

            # Update system tray tooltip with current weather
            self.app.update_tray_tooltip(weather_data, location_name)

            # Process notification events (AFD updates, severe risk changes)
            self._process_notification_events(weather_data)

            # Surface the refresh time in the status bar so users have a
            # passive indicator of data freshness without needing to re-read
            # any panels.  Silent (no screen-reader announcement).
            self._set_last_updated_status()

            # Play the weather-updated sound on successful refresh.
            try:
                settings = self.app.config_manager.get_settings()
                if getattr(settings, "sound_enabled", True):
                    from accessiweather.notifications.sound_player import play_data_updated_sound

                    sound_pack = getattr(settings, "sound_pack", "default")
                    muted_events = getattr(settings, "muted_sound_events", [])
                    play_data_updated_sound(sound_pack, muted_events=muted_events)
            except Exception as sound_exc:
                logger.debug(f"Failed to play weather-updated sound: {sound_exc}")

        except Exception as e:
            logger.error(f"Failed to update weather display: {e}")
            self.set_status(f"Error updating display: {e}")

        finally:
            self.app.is_updating = False
            self.refresh_button.Enable()
