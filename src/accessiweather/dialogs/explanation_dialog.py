"""Dialog for displaying AI-generated weather explanations."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import toga
from toga.style import Pack
from travertino.constants import COLUMN

if TYPE_CHECKING:
    from ..ai_explainer import ExplanationResult

logger = logging.getLogger(__name__)


class ExplanationDialog:
    """Dialog for displaying AI-generated weather explanations."""

    def __init__(
        self,
        app: toga.App,
        explanation: ExplanationResult,
        location: str,
    ):
        """
        Create explanation dialog with result.

        Args:
            app: The Toga application instance
            explanation: The AI-generated explanation result
            location: The location name for the weather data

        """
        self.app = app
        self.explanation = explanation
        self.location = location
        self.window: toga.Window | None = None

    def show(self) -> None:
        """Display the dialog."""
        content = self._build_content()

        self.window = toga.Window(
            title=f"Weather Explanation - {self.location}",
            size=(500, 400),
            resizable=True,
        )
        self.window.content = content

        # Set up close handler
        self.window.on_close = self._on_close

        self.window.show()

        # Set focus to explanation text for screen readers
        self._set_initial_focus()

    def _build_content(self) -> toga.Box:
        """Build dialog content with explanation text and metadata."""
        main_box = toga.Box(style=Pack(direction=COLUMN, padding=15))

        # Header with location and timestamp
        header_label = toga.Label(
            f"Weather explanation for {self.location}",
            style=Pack(font_weight="bold", font_size=14, padding_bottom=10),
        )
        with contextlib.suppress(AttributeError):
            header_label.aria_role = "heading"
            header_label.aria_level = 1
        main_box.add(header_label)

        # Timestamp
        timestamp_text = self.explanation.timestamp.strftime("%B %d, %Y at %I:%M %p")
        timestamp_label = toga.Label(
            f"Generated: {timestamp_text}",
            style=Pack(font_style="italic", padding_bottom=15),
        )
        main_box.add(timestamp_label)

        # Explanation text (main content)
        # Note: Set value after creation to ensure it displays correctly on all platforms
        self.explanation_text = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, padding_bottom=15),
        )
        # Set value after widget creation
        self.explanation_text.value = self.explanation.text or "(No explanation text received)"
        with contextlib.suppress(AttributeError):
            self.explanation_text.aria_label = "Weather explanation"
            self.explanation_text.aria_description = (
                "AI-generated explanation of current weather conditions"
            )
        main_box.add(self.explanation_text)

        # Log for debugging
        logger.debug(
            f"Explanation text set to: {self.explanation.text[:100] if self.explanation.text else 'EMPTY'}..."
        )

        # Metadata section
        metadata_box = toga.Box(style=Pack(direction=COLUMN, padding_top=10))

        # Model used
        model_label = toga.Label(
            f"Model: {self.explanation.model_used}",
            style=Pack(font_size=11),
        )
        metadata_box.add(model_label)

        # Token count and cost
        cost_text = (
            "No cost"
            if self.explanation.estimated_cost == 0
            else f"~${self.explanation.estimated_cost:.6f}"
        )
        usage_label = toga.Label(
            f"Tokens: {self.explanation.token_count} | Cost: {cost_text}",
            style=Pack(font_size=11),
        )
        metadata_box.add(usage_label)

        # Cached indicator
        if self.explanation.cached:
            cached_label = toga.Label(
                "(Cached result)",
                style=Pack(font_size=11, font_style="italic"),
            )
            metadata_box.add(cached_label)

        main_box.add(metadata_box)

        # Close button
        close_button = toga.Button(
            "Close",
            on_press=self._on_close_pressed,
            style=Pack(padding_top=15),
        )
        with contextlib.suppress(AttributeError):
            close_button.aria_label = "Close dialog"
        main_box.add(close_button)

        return main_box

    def _set_initial_focus(self) -> None:
        """Set focus to explanation text for accessibility."""
        try:
            if hasattr(self, "explanation_text") and self.explanation_text:
                self.explanation_text.focus()
        except Exception as e:
            logger.debug(f"Could not set initial focus: {e}")

    def _on_close_pressed(self, widget) -> None:
        """Handle close button press."""
        self.close()

    def _on_close(self, widget) -> bool:
        """Handle window close event."""
        self.window = None
        return True

    def close(self) -> None:
        """Close the dialog."""
        if self.window:
            self.window.close()
            self.window = None


class LoadingDialog:
    """Dialog showing loading state while generating explanation."""

    def __init__(self, app: toga.App, location: str):
        """
        Create loading dialog.

        Args:
            app: The Toga application instance
            location: The location being explained

        """
        self.app = app
        self.location = location
        self.window: toga.Window | None = None
        self.activity_indicator: toga.ActivityIndicator | None = None

    def show(self) -> None:
        """Display the loading dialog."""
        main_box = toga.Box(style=Pack(direction=COLUMN, padding=20, alignment="center"))

        # Loading message
        loading_label = toga.Label(
            f"Generating explanation for {self.location}...",
            style=Pack(padding_bottom=15, text_align="center"),
        )
        with contextlib.suppress(AttributeError):
            loading_label.aria_live = "polite"
            loading_label.aria_label = "Loading, generating weather explanation"
        main_box.add(loading_label)

        # Activity indicator (spinning animation)
        self.activity_indicator = toga.ActivityIndicator(style=Pack(padding_bottom=10))
        main_box.add(self.activity_indicator)

        # Status label
        self.status_label = toga.Label(
            "Please wait...",
            style=Pack(font_style="italic", text_align="center"),
        )
        main_box.add(self.status_label)

        self.window = toga.Window(
            title="Generating Explanation",
            size=(350, 150),
            resizable=False,
            closable=False,  # Prevent closing via X button during loading
        )
        self.window.content = main_box
        self.window.show()

        # Start the activity indicator
        if self.activity_indicator:
            self.activity_indicator.start()

    def close(self) -> None:
        """Close the loading dialog."""
        # Stop the activity indicator
        if self.activity_indicator:
            with contextlib.suppress(Exception):
                self.activity_indicator.stop()

        if self.window:
            self.window.close()
            self.window = None


class ErrorDialog:
    """Dialog for displaying AI explanation errors."""

    def __init__(self, app: toga.App, error_message: str):
        """
        Create error dialog.

        Args:
            app: The Toga application instance
            error_message: User-friendly error message

        """
        self.app = app
        self.error_message = error_message
        self.window: toga.Window | None = None

    def show(self) -> None:
        """Display the error dialog."""
        main_box = toga.Box(style=Pack(direction=COLUMN, padding=20))

        # Error heading
        error_heading = toga.Label(
            "Unable to Generate Explanation",
            style=Pack(font_weight="bold", padding_bottom=10),
        )
        with contextlib.suppress(AttributeError):
            error_heading.aria_role = "heading"
            error_heading.aria_level = 1
        main_box.add(error_heading)

        # Error message
        error_label = toga.Label(
            self.error_message,
            style=Pack(padding_bottom=15),
        )
        with contextlib.suppress(AttributeError):
            error_label.aria_live = "assertive"
            error_label.aria_label = f"Error: {self.error_message}"
        main_box.add(error_label)

        # Close button
        close_button = toga.Button(
            "OK",
            on_press=self._on_close_pressed,
        )
        main_box.add(close_button)

        self.window = toga.Window(
            title="Error",
            size=(400, 180),
            resizable=False,
        )
        self.window.content = main_box
        self.window.show()

    def _on_close_pressed(self, widget) -> None:
        """Handle close button press."""
        self.close()

    def close(self) -> None:
        """Close the error dialog."""
        if self.window:
            self.window.close()
            self.window = None
