"""
AccessiWeather wxPython application.

This module provides the main wxPython application class with excellent
screen reader accessibility.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from typing import TYPE_CHECKING

import wx

from .models import WeatherData
from .paths import Paths
from .single_instance import SingleInstanceManager

if TYPE_CHECKING:
    from .alert_manager import AlertManager
    from .alert_notification_system import AlertNotificationSystem
    from .config import ConfigManager
    from .display import WeatherPresenter
    from .location_manager import LocationManager
    from .ui.main_window import MainWindow
    from .weather_client import WeatherClient

# Configure logging
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

logger = logging.getLogger(__name__)


class AccessiWeatherApp(wx.App):
    """AccessiWeather application using wxPython."""

    def __init__(self, config_dir: str | None = None, portable_mode: bool = False):
        """
        Initialize the AccessiWeather application.

        Args:
            config_dir: Optional custom configuration directory path
            portable_mode: If True, use portable mode (config in app directory)

        """
        self._config_dir = config_dir
        self._portable_mode = portable_mode

        # App version from package (import locally to avoid circular import)
        from . import __version__

        self.version = __version__
        self.build_tag: str | None = None  # Set by nightly builds or --fake-nightly

        # Set up paths (similar to Toga's paths API)
        self.paths = Paths()

        # Core components (initialized in OnInit)
        self.config_manager: ConfigManager | None = None
        self.weather_client: WeatherClient | None = None
        self.location_manager: LocationManager | None = None
        self.presenter: WeatherPresenter | None = None
        self.update_service = None
        self.single_instance_manager: SingleInstanceManager | None = None
        self.weather_history_service = None

        # UI components
        self.main_window: MainWindow | None = None

        # Background update
        self._update_timer: wx.Timer | None = None
        self.is_updating: bool = False

        # Weather data storage
        self.current_weather_data: WeatherData | None = None

        # Alert management
        self.alert_manager: AlertManager | None = None
        self.alert_notification_system: AlertNotificationSystem | None = None

        # Notification system
        self._notifier = None

        # System tray icon (initialized after main window)
        self.tray_icon = None

        # Taskbar icon text updater for dynamic tooltips
        self.taskbar_icon_updater = None

        # Async event loop for background tasks
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: threading.Thread | None = None

        super().__init__()

    def OnInit(self) -> bool:
        """Initialize the application (wxPython entry point)."""
        logger.info("Starting AccessiWeather application (wxPython)")

        try:
            # Check for single instance
            self.single_instance_manager = SingleInstanceManager(self)
            if not self.single_instance_manager.try_acquire_lock():
                logger.info("Another instance is already running, showing force start dialog")
                if not self._show_force_start_dialog():
                    return False

            # Start async event loop in background thread
            self._start_async_loop()

            # Initialize core components
            self._initialize_components()

            # Create main window
            from .ui.main_window import MainWindow

            self.main_window = MainWindow(app=self)

            # Set up keyboard accelerators (shortcuts)
            self._setup_accelerators()

            # Initialize system tray icon
            self._initialize_tray_icon()

            # Load initial data
            self._load_initial_data()

            # Start background update timer
            self._start_background_updates()

            # Play startup sound
            self._play_startup_sound()

            # Initialize taskbar icon updater for dynamic tooltips
            self._initialize_taskbar_updater()

            # Show window (or minimize to tray if setting enabled)
            self._show_or_minimize_window()

            # Check for updates on startup (if enabled)
            self._check_for_updates_on_startup()

            logger.info("AccessiWeather application started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start application: {e}", exc_info=True)
            wx.MessageBox(
                f"Failed to start application: {e}",
                "Startup Error",
                wx.OK | wx.ICON_ERROR,
            )
            return False

    def _show_force_start_dialog(self) -> bool:
        """
        Show a dialog offering to force start when another instance appears to be running.

        Returns
        -------
            bool: True if user chose to force start and lock was acquired, False to exit

        """
        dialog = wx.MessageDialog(
            None,
            "AccessiWeather appears to be already running, or a previous session "
            "didn't close properly.\n\n"
            "Would you like to force start? This will close any existing instance.",
            "AccessiWeather - Already Running",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        dialog.SetYesNoLabels("Force Start", "Cancel")

        result = dialog.ShowModal()
        dialog.Destroy()

        if result == wx.ID_YES:
            logger.info("User chose to force start")
            if self.single_instance_manager.force_remove_lock():
                if self.single_instance_manager.try_acquire_lock():
                    logger.info("Successfully acquired lock after force removal")
                    return True
                logger.error("Failed to acquire lock even after force removal")
                wx.MessageBox(
                    "Failed to start AccessiWeather.\n\n"
                    "Please try closing any running instances and try again.",
                    "Startup Error",
                    wx.OK | wx.ICON_ERROR,
                )
            else:
                wx.MessageBox(
                    "Failed to remove the lock file.\n\n"
                    "Please try manually deleting the lock file or restarting your computer.",
                    "Startup Error",
                    wx.OK | wx.ICON_ERROR,
                )
            return False
        logger.info("User cancelled force start")
        return False

    def _start_async_loop(self) -> None:
        """Start asyncio event loop in a background thread."""

        def run_loop():
            self._async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._async_loop)
            self._async_loop.run_forever()

        self._async_thread = threading.Thread(target=run_loop, daemon=True)
        self._async_thread.start()

    def run_async(self, coro) -> None:
        """Run a coroutine in the background async loop."""
        if self._async_loop:
            asyncio.run_coroutine_threadsafe(coro, self._async_loop)

    def call_after_async(self, callback, *args) -> None:
        """Call a function on the main thread after async operation."""
        wx.CallAfter(callback, *args)

    def _initialize_components(self) -> None:
        """Initialize core application components."""
        from .app_initialization import initialize_components

        initialize_components(self)

    def _load_initial_data(self) -> None:
        """Load initial configuration and data."""
        from .app_initialization import load_initial_data

        load_initial_data(self)

    def _setup_accelerators(self) -> None:
        """Set up keyboard accelerators (shortcuts)."""
        if not self.main_window:
            return

        # Define keyboard shortcuts
        accelerators = [
            (wx.ACCEL_CTRL, ord("R"), self._on_refresh_shortcut),
            (wx.ACCEL_CTRL, ord("L"), self._on_add_location_shortcut),
            (wx.ACCEL_CTRL, ord("D"), self._on_remove_location_shortcut),
            (wx.ACCEL_CTRL, ord("H"), self._on_history_shortcut),
            (wx.ACCEL_CTRL, ord("S"), self._on_settings_shortcut),
            (wx.ACCEL_CTRL, ord("Q"), self._on_exit_shortcut),
            (wx.ACCEL_NORMAL, wx.WXK_F5, self._on_refresh_shortcut),
        ]

        # Create accelerator table
        # Access the frame directly (MainWindow is now a SizedFrame)
        frame = self.main_window
        accel_entries = []
        for flags, key, handler in accelerators:
            cmd_id = wx.NewIdRef()
            frame.Bind(wx.EVT_MENU, handler, id=cmd_id)
            accel_entries.append(wx.AcceleratorEntry(flags, key, cmd_id))

        accel_table = wx.AcceleratorTable(accel_entries)
        frame.SetAcceleratorTable(accel_table)
        logger.info("Keyboard accelerators set up successfully")

    def _on_refresh_shortcut(self, event) -> None:
        """Handle Ctrl+R / F5 shortcut."""
        if self.main_window:
            self.main_window.on_refresh()

    def _on_add_location_shortcut(self, event) -> None:
        """Handle Ctrl+L shortcut."""
        if self.main_window:
            self.main_window.on_add_location()

    def _on_remove_location_shortcut(self, event) -> None:
        """Handle Ctrl+D shortcut."""
        if self.main_window:
            self.main_window.on_remove_location()

    def _on_history_shortcut(self, event) -> None:
        """Handle Ctrl+H shortcut."""
        if self.main_window:
            self.main_window.on_view_history()

    def _on_settings_shortcut(self, event) -> None:
        """Handle Ctrl+S shortcut."""
        if self.main_window:
            self.main_window.on_settings()

    def _on_exit_shortcut(self, event) -> None:
        """Handle Ctrl+Q shortcut."""
        self.request_exit()

    def _initialize_tray_icon(self) -> None:
        """Initialize the system tray icon."""
        try:
            from .ui.system_tray import SystemTrayIcon

            self.tray_icon = SystemTrayIcon(self)
            logger.info("System tray icon initialized")
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

    def _check_for_updates_on_startup(self) -> None:
        """Check for updates on startup if enabled in settings."""
        try:
            settings = self.config_manager.get_settings()
            if not getattr(settings, "auto_update_enabled", True):
                logger.debug("Automatic update check disabled")
                return

            channel = getattr(settings, "update_channel", "stable")

            def do_check():
                import asyncio

                from .services.simple_update import UpdateService, parse_nightly_date

                try:
                    current_version = getattr(self, "version", "0.0.0")
                    build_tag = getattr(self, "build_tag", None)
                    current_nightly_date = parse_nightly_date(build_tag) if build_tag else None

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

                    if update_info:
                        # Show notification about available update
                        channel_label = "nightly" if update_info.is_nightly else "stable"
                        logger.info(f"Update available: {update_info.version} ({channel_label})")

                        def show_update_notification():
                            result = wx.MessageBox(
                                f"A new {channel_label} update is available!\n\n"
                                f"Current: {current_version}\n"
                                f"Latest: {update_info.version}\n\n"
                                "Download now?",
                                "Update Available",
                                wx.YES_NO | wx.ICON_INFORMATION,
                            )
                            if result == wx.YES:
                                self._download_and_apply_update(update_info)

                        wx.CallAfter(show_update_notification)
                    else:
                        logger.debug("No updates available")

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

        from .config_utils import is_portable_mode
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
                        portable = is_portable_mode()
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

    def _start_background_updates(self) -> None:
        """Start periodic background weather updates."""
        try:
            settings = self.config_manager.get_settings()
            interval_minutes = getattr(settings, "update_interval_minutes", 10)
            interval_ms = interval_minutes * 60 * 1000

            self._update_timer = wx.Timer()
            self._update_timer.Bind(wx.EVT_TIMER, self._on_background_update)
            self._update_timer.Start(interval_ms)
            logger.info(f"Background updates started (every {interval_minutes} minutes)")
        except Exception as e:
            logger.error(f"Failed to start background updates: {e}")

    def _on_background_update(self, event) -> None:
        """Handle background update timer event."""
        if self.main_window and not self.is_updating:
            self.main_window.refresh_weather_async()

    def _play_startup_sound(self) -> None:
        """Play startup sound if enabled."""
        try:
            settings = self.config_manager.get_settings()
            if getattr(settings, "sound_enabled", True):
                from .notifications.sound_player import play_startup_sound

                sound_pack = getattr(settings, "sound_pack", "default")
                play_startup_sound(sound_pack)
        except Exception as e:
            logger.debug(f"Could not play startup sound: {e}")

    def request_exit(self) -> None:
        """Request application exit with cleanup."""
        logger.info("Application exit requested")

        # Stop background updates
        if self._update_timer:
            self._update_timer.Stop()

        # Play exit sound (non-blocking, app exits immediately)
        try:
            settings = self.config_manager.get_settings()
            if getattr(settings, "sound_enabled", True):
                from .notifications.sound_player import play_exit_sound

                sound_pack = getattr(settings, "sound_pack", "default")
                play_exit_sound(sound_pack)
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

            if self.presenter:
                self.presenter.settings = settings

            if self._notifier:
                self._notifier.sound_enabled = bool(getattr(settings, "sound_enabled", True))
                self._notifier.soundpack = getattr(settings, "sound_pack", "default")

            if self.alert_notification_system:
                self.alert_notification_system.settings = settings

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

            logger.info("Runtime settings refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh runtime settings: {e}")


def main(
    config_dir: str | None = None,
    portable_mode: bool = False,
    fake_version: str | None = None,
    fake_nightly: str | None = None,
):
    """
    Run AccessiWeather application.

    Args:
        config_dir: Custom configuration directory path.
        portable_mode: Run in portable mode.
        fake_version: Fake version for testing updates (e.g., '0.1.0').
        fake_nightly: Fake nightly tag for testing updates (e.g., 'nightly-20250101').

    """
    app = AccessiWeatherApp(config_dir=config_dir, portable_mode=portable_mode)

    # Override version/build_tag for update testing
    if fake_version:
        app.version = fake_version
        logger.info(f"Using fake version for testing: {fake_version}")
    if fake_nightly:
        app.build_tag = fake_nightly
        logger.info(f"Using fake nightly tag for testing: {fake_nightly}")

    app.MainLoop()
    return app


if __name__ == "__main__":
    main()
