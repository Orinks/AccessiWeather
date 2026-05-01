"""Tray, update-check, background update, and shutdown helpers."""

from __future__ import annotations

import contextlib
import logging

import wx

from . import app_timer_manager
from .runtime_env import is_compiled_runtime

logger = logging.getLogger(__name__)


class AppLifecycleMixin:
    def _initialize_tray_icon(self) -> None:
        """Initialize the system tray icon."""
        try:
            from .ui.system_tray import SystemTrayIcon

            self.tray_icon = SystemTrayIcon(self)
            logger.info("System tray icon initialized")

            self._wire_notifier_activation_callback()
        except Exception as e:
            logger.warning(f"Failed to initialize system tray icon: {e}")
            self.tray_icon = None

    def _initialize_taskbar_updater(self) -> None:
        """Initialize the taskbar icon updater for dynamic tooltips."""
        try:
            from .taskbar_icon_updater import TaskbarIconUpdater

            settings = self.config_manager.get_settings()
            self.taskbar_icon_updater = TaskbarIconUpdater(
                text_enabled=getattr(settings, "taskbar_icon_text_enabled", False),
                dynamic_enabled=getattr(settings, "taskbar_icon_dynamic_enabled", True),
                format_string=getattr(settings, "taskbar_icon_text_format", "{temp} {condition}"),
                temperature_unit=getattr(settings, "temperature_unit", "both"),
                verbosity_level=getattr(settings, "verbosity_level", "standard"),
                round_values=getattr(settings, "round_values", False),
            )
            logger.debug("Taskbar icon updater initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize taskbar icon updater: {e}")
            self.taskbar_icon_updater = None

    def _show_or_minimize_window(self) -> None:
        """Show the main window or minimize to tray based on settings."""
        if not self.main_window:
            return

        try:
            settings = self.config_manager.get_settings()
            # Only minimize to tray if setting is enabled AND tray icon is available
            if getattr(settings, "minimize_on_startup", False) and self.tray_icon:
                # Don't show the window - keep it hidden (starts minimized to tray)
                logger.info("Window minimized to tray on startup")
            else:
                # Show the window normally
                self.main_window.Show()
                if getattr(settings, "minimize_on_startup", False) and not self.tray_icon:
                    logger.warning("minimize_on_startup enabled but tray icon unavailable")
        except Exception as e:
            # On error, show the window to avoid invisible app
            logger.warning(f"Failed to check minimize setting, showing window: {e}")
            self.main_window.Show()

    def _stop_auto_update_checks(self) -> None:
        """Stop and detach the automatic update-check timer, if present."""
        app_timer_manager.stop_auto_update_checks(self)

    def _start_auto_update_checks(self) -> None:
        """Start periodic automatic update checks based on user settings."""
        app_timer_manager.start_auto_update_checks(self)

    def _on_auto_update_check_timer(self, event) -> None:
        """Run an automatic update check on timer ticks."""
        app_timer_manager.on_auto_update_check_timer(self, event)

    def _check_for_updates_on_startup(self) -> None:
        """Check for updates on startup if enabled in settings."""
        try:
            # Skip update checks when running from source.
            if not is_compiled_runtime():
                logger.debug("Running from source, skipping update check")
                return

            settings = self.config_manager.get_settings()
            if not getattr(settings, "auto_update_enabled", True):
                logger.debug("Automatic update check disabled")
                return

            channel = getattr(settings, "update_channel", "stable")

            # Mark that a check was initiated now so the periodic scheduler
            # doesn't also fire during/right after this one. Use wall-clock-
            # inclusive monotonic time so sleep/wake cycles are accounted for.
            import time as _time

            self._last_update_check_at = _time.monotonic()
            logger.info("Auto-update check starting (channel=%s)", channel)

            def do_check():
                import asyncio

                from .services.simple_update import UpdateService, parse_nightly_date

                try:
                    current_version = getattr(self, "version", "0.0.0")
                    build_tag = getattr(self, "build_tag", None)
                    current_nightly_date = parse_nightly_date(build_tag) if build_tag else None
                    display_version = (
                        current_nightly_date if current_nightly_date else current_version
                    )

                    # Safety: if frozen but no build_tag and checking nightly channel,
                    # skip auto-prompt to avoid infinite update loops
                    if not build_tag and channel == "nightly":
                        logger.warning(
                            "Skipping startup nightly update check: no build_tag available. "
                            "Use Help > Check for Updates to check manually."
                        )
                        return

                    async def check():
                        service = UpdateService("AccessiWeather")
                        try:
                            return await service.check_for_updates(
                                current_version=current_version,
                                current_nightly_date=current_nightly_date,
                                channel=channel,
                            )
                        finally:
                            await service.close()

                    update_info = asyncio.run(check())

                    if update_info:  # pragma: no cover — UI prompt
                        # Show changelog dialog for available update
                        channel_label = "Nightly" if update_info.is_nightly else "Stable"
                        logger.info(f"Update available: {update_info.version} ({channel_label})")

                        def show_update_notification():
                            from .ui.dialogs.update_dialog import UpdateAvailableDialog

                            main_window = self.GetTopWindow()
                            dlg = UpdateAvailableDialog(
                                parent=main_window,
                                current_version=display_version,
                                new_version=update_info.version,
                                channel_label=channel_label,
                                release_notes=update_info.release_notes,
                            )
                            result = dlg.ShowModal()
                            dlg.Destroy()
                            if result == wx.ID_OK:
                                self._download_and_apply_update(update_info)

                        wx.CallAfter(show_update_notification)
                    else:
                        logger.info("Auto-update check: no updates available")

                except Exception as e:
                    logger.warning(f"Startup update check failed: {e}")

            # Run in background thread to not block startup
            import threading

            thread = threading.Thread(target=do_check, daemon=True)
            thread.start()

        except Exception as e:
            logger.warning(f"Failed to initiate startup update check: {e}")

    def _download_and_apply_update(self, update_info) -> None:
        """
        Download and apply an update.

        Args:
            update_info: UpdateInfo object from the update service.

        """
        import asyncio
        import tempfile
        from pathlib import Path

        from .services.simple_update import UpdateService, apply_update

        # Create progress dialog
        parent = self.main_window if self.main_window else None
        progress_dlg = wx.ProgressDialog(
            "Downloading Update",
            f"Downloading {update_info.artifact_name}...",
            maximum=100,
            parent=parent,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
        )

        def do_download():
            try:
                dest_dir = Path(tempfile.gettempdir())

                def progress_callback(downloaded, total):
                    if total > 0:
                        percent = int((downloaded / total) * 100)
                        wx.CallAfter(
                            progress_dlg.Update,
                            percent,
                            f"Downloading... {downloaded // 1024} / {total // 1024} KB",
                        )

                async def download():
                    service = UpdateService("AccessiWeather")
                    try:
                        return await service.download_update(
                            update_info, dest_dir, progress_callback
                        )
                    finally:
                        await service.close()

                update_path = asyncio.run(download())

                wx.CallAfter(progress_dlg.Destroy)

                # Ask for confirmation before applying
                def confirm_apply():
                    result = wx.MessageBox(
                        "Download complete. The application will now restart "
                        "to apply the update.\n\n"
                        "Continue?",
                        "Apply Update",
                        wx.YES_NO | wx.ICON_QUESTION,
                    )
                    if result == wx.YES:
                        portable = self._portable_mode
                        # Destroy all wx windows so file handles are released before exit
                        for win in wx.GetTopLevelWindows():
                            with contextlib.suppress(Exception):
                                win.Destroy()
                        wx.SafeYield()
                        apply_update(update_path, portable=portable)

                wx.CallAfter(confirm_apply)

            except Exception as e:
                logger.error(f"Error downloading update: {e}")
                wx.CallAfter(progress_dlg.Destroy)
                wx.CallAfter(
                    wx.MessageBox,
                    f"Failed to download update:\n{e}",
                    "Download Error",
                    wx.OK | wx.ICON_ERROR,
                )

        # Run download in background thread
        import threading

        thread = threading.Thread(target=do_download, daemon=True)
        thread.start()

    def update_tray_tooltip(self, weather_data=None, location_name: str | None = None) -> None:
        """
        Update the system tray icon tooltip with current weather.

        Args:
            weather_data: Current weather data
            location_name: Name of the current location

        """
        if not self.tray_icon or not self.taskbar_icon_updater:
            return

        try:
            tooltip = self.taskbar_icon_updater.format_tooltip(weather_data, location_name)
            self.tray_icon.update_tooltip(tooltip)
        except Exception as e:
            logger.debug(f"Failed to update tray tooltip: {e}")

    def _stop_background_updates(self) -> None:
        """Stop any running background timers."""
        app_timer_manager.stop_background_updates(self)

    def _start_background_updates(self) -> None:
        """Start split background timers for full refreshes and lightweight event checks."""
        app_timer_manager.start_background_updates(self)

    def _on_background_update(self, event) -> None:
        """Handle slower full weather refresh timer event."""
        app_timer_manager.on_background_update(self, event)

    def _on_event_check_update(self, event) -> None:
        """Handle fast lightweight event-check timer event."""
        app_timer_manager.on_event_check_update(self, event)

    def _play_startup_sound(self) -> None:
        """Play startup sound if enabled."""
        try:
            settings = self.config_manager.get_settings()
            if getattr(settings, "sound_enabled", True):
                from .notifications.sound_player import play_startup_sound

                sound_pack = getattr(settings, "sound_pack", "default")
                muted_events = getattr(settings, "muted_sound_events", [])
                play_startup_sound(sound_pack, muted_events=muted_events)
        except Exception as e:
            logger.debug(f"Could not play startup sound: {e}")

    def request_exit(self) -> None:
        """Request application exit with cleanup."""
        logger.info("Application exit requested")

        # Stop background updates
        self._stop_background_updates()

        self._stop_auto_update_checks()
        activation_handoff_timer = getattr(self, "_activation_handoff_timer", None)
        if activation_handoff_timer:
            activation_handoff_timer.Stop()

        # Play exit sound without blocking shutdown.
        try:
            settings = self.config_manager.get_settings()
            if getattr(settings, "sound_enabled", True):
                from .notifications.sound_player import (
                    PLAYSOUND_AVAILABLE,
                    SOUND_LIB_AVAILABLE,
                    play_exit_sound,
                )

                sound_pack = getattr(settings, "sound_pack", "default")
                muted_events = getattr(settings, "muted_sound_events", [])
                logger.debug(
                    "[packaging-diag] exit sound: compiled=%s sound_pack=%s sound_lib=%s playsound3=%s",
                    is_compiled_runtime(),
                    sound_pack,
                    SOUND_LIB_AVAILABLE,
                    PLAYSOUND_AVAILABLE,
                )

                play_exit_sound(sound_pack, muted_events=muted_events)
        except Exception:
            pass

        # Clean up system tray icon
        if self.tray_icon:
            self.tray_icon.RemoveIcon()
            self.tray_icon.Destroy()
            self.tray_icon = None

        # Release single instance lock
        if self.single_instance_manager:
            self.single_instance_manager.release_lock()

        # Stop async loop
        if self._async_loop:
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)

        # Close main window and exit
        if self.main_window:
            self.main_window.Destroy()

        self.ExitMainLoop()

    def refresh_runtime_settings(self) -> None:
        """Refresh runtime components with current settings."""
        try:
            settings = self.config_manager.get_settings()
            logger.info("Refreshing runtime settings")

            if self.weather_client:
                self.weather_client.settings = settings
                self.weather_client.data_source = settings.data_source
                self.weather_client.alerts_enabled = bool(settings.enable_alerts)
                # Reset cached API clients so new keys take effect immediately
                self.weather_client._pirate_weather_api_key = getattr(  # pragma: no cover
                    settings, "pirate_weather_api_key", ""
                )
                self.weather_client._pirate_weather_client = None  # pragma: no cover
                self.weather_client._avwx_api_key = getattr(  # pragma: no cover
                    settings, "avwx_api_key", ""
                )

            if self.presenter:
                self.presenter.settings = settings

            if self._notifier:
                self._notifier.sound_enabled = bool(getattr(settings, "sound_enabled", True))
                self._notifier.soundpack = getattr(settings, "sound_pack", "default")
                self._notifier.muted_sound_events = list(
                    getattr(settings, "muted_sound_events", [])
                )

            if self.alert_notification_system:
                logger.debug(
                    "[notify] refresh_runtime_settings: applying alert settings "
                    "(app_enabled=%s, sound_enabled=%s, threshold_flags={extreme:%s,severe:%s,"
                    "moderate:%s,minor:%s,unknown:%s})",
                    getattr(settings, "alert_notifications_enabled", None),
                    getattr(settings, "sound_enabled", None),
                    getattr(settings, "alert_notify_extreme", None),
                    getattr(settings, "alert_notify_severe", None),
                    getattr(settings, "alert_notify_moderate", None),
                    getattr(settings, "alert_notify_minor", None),
                    getattr(settings, "alert_notify_unknown", None),
                )
                self.alert_notification_system.settings = settings
                self.alert_notification_system.update_settings(settings.to_alert_settings())

            # Update taskbar icon updater settings
            if self.taskbar_icon_updater:
                self.taskbar_icon_updater.update_settings(
                    text_enabled=getattr(settings, "taskbar_icon_text_enabled", False),
                    dynamic_enabled=getattr(settings, "taskbar_icon_dynamic_enabled", True),
                    format_string=getattr(
                        settings, "taskbar_icon_text_format", "{temp} {condition}"
                    ),
                    temperature_unit=getattr(settings, "temperature_unit", "both"),
                    verbosity_level=getattr(settings, "verbosity_level", "standard"),
                )

            self._start_auto_update_checks()
            self._start_background_updates()

            logger.info("Runtime settings refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh runtime settings: {e}")
