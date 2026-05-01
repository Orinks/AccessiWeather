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
import webbrowser  # noqa: F401 - compatibility for tests and downstream monkeypatches
from typing import TYPE_CHECKING

import wx

from .app_activation import AppActivationMixin
from .app_lifecycle import AppLifecycleMixin
from .app_shortcuts import AppShortcutsMixin
from .app_startup_guidance import AppStartupGuidanceMixin
from .models import WeatherData
from .notification_activation import NotificationActivationRequest
from .paths import Paths, RuntimeStoragePaths, detect_portable_mode, resolve_runtime_storage
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


def show_alert_dialog(parent, alert, settings=None) -> None:
    """Lazy wrapper for the single-alert details dialog."""
    from .ui.dialogs import show_alert_dialog as _show_alert_dialog

    _show_alert_dialog(parent, alert, settings)


def show_alerts_summary_dialog(parent, alerts) -> None:
    """Lazy wrapper for the combined multi-alert dialog."""
    from .ui.dialogs import show_alerts_summary_dialog as _show_alerts_summary_dialog

    _show_alerts_summary_dialog(parent, alerts)


class AccessiWeatherApp(
    AppLifecycleMixin, AppShortcutsMixin, AppStartupGuidanceMixin, AppActivationMixin, wx.App
):
    """AccessiWeather application using wxPython."""

    def __init__(
        self,
        config_dir: str | None = None,
        portable_mode: bool = False,
        debug: bool = False,
        force_wizard: bool = False,
        updated: bool = False,
        activation_request: NotificationActivationRequest | None = None,
    ):
        """
        Initialize the AccessiWeather application.

        Args:
            config_dir: Optional custom configuration directory path
            portable_mode: If True, use portable mode (config in app directory)
            debug: If True, enable debug mode (enables debug logging and extra UI tools)
            force_wizard: If True, force the onboarding wizard even if already shown
            updated: If True, skip lock-file prompt (app was restarted after an update)
            activation_request: Optional toast activation request passed from Windows

        """
        self._updated = updated
        self._activation_request = activation_request
        self._config_dir = config_dir

        # Auto-detect portable mode for frozen builds unless explicitly overridden
        # via --portable or --config-dir.
        if not portable_mode and config_dir is None:
            try:
                portable_mode = detect_portable_mode()
            except Exception:
                portable_mode = False

        self._portable_mode = portable_mode
        self.debug_mode = bool(debug)
        self._force_wizard = bool(force_wizard)
        self._portable_keys_imported_this_session: bool = False

        # App version and build info (import locally to avoid circular import)
        from . import __version__

        self.version = __version__

        # Build tag for nightly builds (from generated _build_meta.py or legacy _build_info.py)
        try:
            from ._build_meta import BUILD_TAG  # pragma: no cover — build only

            self.build_tag: str | None = BUILD_TAG  # pragma: no cover
        except ImportError:
            try:
                from ._build_info import BUILD_TAG

                self.build_tag = BUILD_TAG
            except ImportError:
                self.build_tag = None

        # Set up paths (similar to Toga's paths API)
        self.paths = Paths()
        self.runtime_paths: RuntimeStoragePaths = resolve_runtime_storage(
            self.paths,
            config_dir=self._config_dir,
            portable_mode=self._portable_mode,
        )

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
        self._auto_update_check_timer: wx.Timer | None = None
        self._auto_update_interval_seconds: int = 24 * 3600
        self._last_update_check_at: float | None = None
        self._activation_handoff_timer: wx.Timer | None = None
        self._startup_update_check_deferred: bool = False
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

    @property
    def notifier(self):
        """Public accessor for the app-level notifier (used by notification subsystems)."""
        return self._notifier

    @notifier.setter
    def notifier(self, value) -> None:
        self._notifier = value

    def OnInit(self) -> bool:
        """Initialize the application (wxPython entry point)."""
        logger.info("Starting AccessiWeather application (wxPython)")

        # Ensure Start Menu shortcut has the correct AUMID for Action Center clicks.
        # Uses pure Python ctypes COM — no subprocess, no visible terminal window.
        from .windows_toast_identity import ensure_windows_toast_identity

        ensure_windows_toast_identity()

        try:
            # Check for single instance
            self.single_instance_manager = SingleInstanceManager(
                self, runtime_paths=self.runtime_paths
            )
            if not self.single_instance_manager.try_acquire_lock():
                if self._activation_request is not None:
                    logger.info("Forwarding notification activation to running instance")
                    self.single_instance_manager.write_activation_handoff(self._activation_request)
                    return False
                if self._updated:
                    # After an update restart the old lock file is stale; force-acquire it
                    logger.info("Post-update restart: forcing lock acquisition")
                    self.single_instance_manager.force_remove_lock()
                    self.single_instance_manager.try_acquire_lock()
                else:
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
            self._start_activation_handoff_polling()

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
            self._schedule_startup_activation_request()

            # Show one-time startup guidance prompts (non-blocking).
            self._schedule_startup_guidance_prompts()

            # Start periodic automatic update checks
            self._start_auto_update_checks()

            # Check for updates on startup, after onboarding completes when shown.
            self._check_for_updates_after_startup_guidance()

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
            future = asyncio.run_coroutine_threadsafe(coro, self._async_loop)
            logger.debug("[async] scheduled coroutine: %r", coro)

            def _log_future_result(done_future) -> None:
                try:
                    result = done_future.result()
                    logger.debug("[async] coroutine completed: %r -> %r", coro, result)
                except Exception as exc:
                    logger.error("[async] coroutine failed: %r (%s)", coro, exc, exc_info=True)

            future.add_done_callback(_log_future_result)

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


def main(
    config_dir: str | None = None,
    portable_mode: bool = False,
    debug: bool = False,
    fake_version: str | None = None,
    fake_nightly: str | None = None,
    force_wizard: bool = False,
    updated: bool = False,
    activation_request: NotificationActivationRequest | None = None,
):
    """
    Run AccessiWeather application.

    Args:
        config_dir: Custom configuration directory path.
        portable_mode: Run in portable mode.
        debug: Enable debug mode.
        fake_version: Fake version for testing updates (e.g., '0.1.0').
        fake_nightly: Fake nightly tag for testing updates (e.g., 'nightly-20250101').
        force_wizard: Force the onboarding wizard even if already shown.
        updated: Skip lock-file prompt (app was restarted after an update).
        activation_request: Optional toast activation request passed from Windows.

    """
    app = AccessiWeatherApp(
        config_dir=config_dir,
        portable_mode=portable_mode,
        debug=debug,
        force_wizard=force_wizard,
        updated=updated,
        activation_request=activation_request,
    )

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
