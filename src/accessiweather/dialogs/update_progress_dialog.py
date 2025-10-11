"""
Update progress dialog for AccessiWeather Toga application.

This module provides a progress dialog for displaying update download and
installation progress with accessibility features.
"""

import asyncio
import logging
import os

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

logger = logging.getLogger(__name__)
LOG_PREFIX = "UpdateProgressDialog"


class _SafeEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy that auto-creates loops when needed."""

    def get_event_loop(self):  # pragma: no cover - exercised in tests
        if self._local._loop is None:
            self.set_event_loop(self.new_event_loop())
        return self._local._loop


def _ensure_asyncio_loop():
    """Ensure an asyncio event loop exists for the current thread."""
    policy = asyncio.get_event_loop_policy()
    if os.environ.get("TOGA_BACKEND") == "toga_dummy" and not isinstance(
        policy, _SafeEventLoopPolicy
    ):
        asyncio.set_event_loop_policy(_SafeEventLoopPolicy())
        policy = asyncio.get_event_loop_policy()
    try:
        policy.get_event_loop()
    except RuntimeError:
        loop = policy.new_event_loop()
        policy.set_event_loop(loop)


_ensure_asyncio_loop()


class UpdateProgressDialog:
    """Dialog for displaying update progress with accessibility features."""

    def __init__(self, app, title: str = "Updating AccessiWeather"):
        """
        Initialize the update progress dialog.

        Args:
        ----
            app: The main application instance
            title: Dialog title

        """
        self.app = app
        self.title = title
        self.window = None
        self.future = None

        # UI components
        self.progress_bar = None
        self.status_label = None
        self.detail_label = None
        self.cancel_button = None

        # Progress state
        self.is_cancelled = False
        self.current_progress = 0
        self.total_size = 0
        self.downloaded_size = 0

    def __await__(self):
        """Make the dialog awaitable for modal behavior."""
        if self.future is None:
            raise RuntimeError("Dialog future not initialized. Call show_and_prepare() first.")
        return self.future.__await__()

    def show_and_prepare(self):
        """Prepare and show the progress dialog."""
        logger.info("Showing update progress dialog")

        try:
            # Create a fresh future for this dialog session
            self.future = self.app.loop.create_future()

            self._ensure_toga_app_context()

            # Create dialog window
            self.window = toga.Window(
                title=self.title,
                size=(500, 200),
                resizable=False,
                minimizable=False,
                closable=False,  # Prevent closing via X button
            )

            # Create dialog content
            self._create_dialog_content()

            # Show the dialog
            self.window.show()

            # Set initial focus for accessibility
            self._set_initial_focus()

        except Exception as e:
            logger.error(f"Failed to show progress dialog: {e}", exc_info=True)
            if self.future and not self.future.done():
                self.future.set_exception(e)

    def _ensure_toga_app_context(self):
        """Ensure a Toga application context exists for window creation."""
        if getattr(toga.App, "app", None) is not None:
            return

        os.environ.setdefault("TOGA_BACKEND", "toga_dummy")

        try:
            self._toga_app_guard = toga.App("AccessiWeather (Tests)", "com.accessiweather.tests")
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.debug("%s: Unable to create fallback Toga app: %s", LOG_PREFIX, exc)

    def _create_dialog_content(self):
        """Create the progress dialog content."""
        # Main container
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=20))

        # Status label
        self.status_label = toga.Label(
            "Preparing update...",
            style=Pack(font_size=14, font_weight="bold", margin_bottom=10),
        )
        main_box.add(self.status_label)

        # Progress bar (using ActivityIndicator for now, as Toga doesn't have ProgressBar)
        self.progress_indicator = toga.ActivityIndicator(style=Pack(margin_bottom=10))
        main_box.add(self.progress_indicator)

        # Detail label for progress information
        self.detail_label = toga.Label(
            "Initializing...",
            style=Pack(font_size=12, margin_bottom=15),
        )
        main_box.add(self.detail_label)

        # Button row
        button_box = toga.Box(style=Pack(direction=ROW))

        # Add flexible space to center the button
        button_box.add(toga.Box(style=Pack(flex=1)))

        # Cancel button
        self.cancel_button = toga.Button(
            "Cancel",
            on_press=self._on_cancel,
            style=Pack(width=100),
            id="cancel_button",
        )
        button_box.add(self.cancel_button)

        # Add flexible space
        button_box.add(toga.Box(style=Pack(flex=1)))

        main_box.add(button_box)

        # Set window content
        self.window.content = main_box

    def _set_initial_focus(self):
        """Set initial focus for accessibility."""
        try:
            # Focus on the cancel button for keyboard accessibility
            if self.cancel_button:
                self.cancel_button.focus()
        except Exception as e:
            logger.warning(f"Could not set initial focus: {e}")

    async def update_progress(self, progress: float, downloaded: int = 0, total: int = 0):
        """
        Update the progress display.

        Args:
        ----
            progress: Progress percentage (0-100)
            downloaded: Bytes downloaded
            total: Total bytes to download

        """
        try:
            self.current_progress = progress
            self.downloaded_size = downloaded
            self.total_size = total

            # Update status based on progress
            if progress < 1:
                status = "Preparing update..."
            elif progress >= 100:
                status = "Finalizing update..."
            else:
                status = f"Downloading update... {progress:.1f}%"

            # Update detail information
            if total > 0:
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                detail = f"{downloaded_mb:.1f} MB of {total_mb:.1f} MB"
            else:
                detail = "Preparing download..."

            # Update UI elements
            if self.status_label:
                self.status_label.text = status

            if self.detail_label:
                self.detail_label.text = detail

            # Start/stop activity indicator based on progress
            if self.progress_indicator:
                if 0 < progress < 100:
                    self.progress_indicator.start()
                else:
                    self.progress_indicator.stop()

        except Exception as e:
            logger.error(f"Failed to update progress: {e}")

    async def set_status(self, status: str, detail: str = ""):
        """
        Set the status and detail text.

        Args:
        ----
            status: Main status message
            detail: Optional detail message

        """
        try:
            if self.status_label:
                self.status_label.text = status

            if self.detail_label and detail:
                self.detail_label.text = detail

        except Exception as e:
            logger.error(f"Failed to set status: {e}")

    def _on_cancel(self, widget):
        """Handle cancel button press."""
        logger.info("Update cancelled by user")
        self.is_cancelled = True

        # Update UI to show cancellation
        if self.status_label:
            self.status_label.text = "Cancelling update..."

        if self.cancel_button:
            self.cancel_button.enabled = False

        if self.progress_indicator:
            self.progress_indicator.stop()

        # Complete the future with cancellation
        if self.future and not self.future.done():
            self.future.set_result("cancelled")

    async def complete_success(self, message: str = "Update completed successfully"):
        """
        Complete the dialog with success.

        Args:
        ----
            message: Success message to display

        """
        try:
            await self.set_status(message, "The application will restart shortly.")

            if self.progress_indicator:
                self.progress_indicator.stop()

            if self.cancel_button:
                self.cancel_button.text = "Close"
                self.cancel_button.enabled = True

            # Wait a moment for user to see the message
            await asyncio.sleep(2)

            # Complete the future
            if self.future and not self.future.done():
                self.future.set_result("success")

        except Exception as e:
            logger.error(f"Failed to complete success: {e}")

    async def complete_error(self, error_message: str):
        """
        Complete the dialog with an error.

        Args:
        ----
            error_message: Error message to display

        """
        try:
            await self.set_status("Update failed", error_message)

            if self.progress_indicator:
                self.progress_indicator.stop()

            if self.cancel_button:
                self.cancel_button.text = "Close"
                self.cancel_button.enabled = True

            # Complete the future
            if self.future and not self.future.done():
                self.future.set_result("error")

        except Exception as e:
            logger.error(f"Failed to complete error: {e}")

    def close(self):
        """Close the dialog."""
        try:
            if self.window:
                self.window.close()
                self.window = None

        except Exception as e:
            logger.error(f"Failed to close dialog: {e}")


class UpdateNotificationDialog:
    """Simple notification dialog for update availability."""

    def __init__(self, app, update_info, platform_info):
        """
        Initialize the notification dialog.

        Args:
        ----
            app: The main application instance
            update_info: Information about the available update
            platform_info: Platform information

        """
        self.app = app
        self.update_info = update_info
        self.platform_info = platform_info

    async def show(self) -> str:
        """
        Show the update notification dialog.

        Returns
        -------
            User's choice: 'download', 'later', or 'skip'

        """
        try:
            # Determine the appropriate message based on platform capabilities
            if self.platform_info.update_capable:
                message = (
                    f"AccessiWeather {self.update_info.version} is available.\n\n"
                    f"Would you like to download and install it now?\n\n"
                    f"Current version: {self._get_current_version()}\n"
                    f"New version: {self.update_info.version}"
                )

                # Show dialog with download option
                result = await self.app.main_window.question_dialog("Update Available", message)

                return "download" if result else "later"
            # For installed versions, show notification with manual download link
            message = (
                f"AccessiWeather {self.update_info.version} is available.\n\n"
                f"Please visit the AccessiWeather website to download the latest version.\n\n"
                f"Current version: {self._get_current_version()}\n"
                f"New version: {self.update_info.version}"
            )

            await self.app.main_window.info_dialog("Update Available", message)
            return "manual"

        except Exception as e:
            logger.error(f"Failed to show update notification: {e}")
            return "error"

    def _get_current_version(self) -> str:
        """Get the current application version."""
        try:
            from accessiweather import __version__  # import from package

            return __version__ or "Unknown"
        except Exception:
            return "Unknown"
