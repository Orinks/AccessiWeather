"""
Toga dialog for displaying forecast discussion text.

This dialog displays the National Weather Service Area Forecast Discussion (AFD)
with enhanced accessibility features and user experience improvements.
"""

import asyncio
import logging

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

logger = logging.getLogger(__name__)


class ForecastDiscussionDialog:
    """Dialog for displaying NWS Area Forecast Discussion with accessibility features."""

    def __init__(self, app, discussion_text: str, location_name: str = None):
        """
        Initialize the forecast discussion dialog.

        Args:
        ----
            app: The main application instance
            discussion_text: The AFD text to display
            location_name: The name of the location for the AFD

        """
        self.app = app
        self.discussion_text = discussion_text or "No forecast discussion available."
        self.location_name = location_name or "Unknown Location"
        self.window = None  # Will be created when dialog is shown

        # UI components
        self.text_display = None
        self.close_button = None
        self.explain_button = None

    def _create_ui(self):
        """Create the dialog user interface."""
        # Create a new window for the dialog with descriptive title including location
        title = f"Area Forecast Discussion - {self.location_name}"
        self.window = toga.Window(title=title, size=(800, 600))

        main_box = toga.Box(style=Pack(direction=COLUMN, margin=15))

        # Simple header without unnecessary descriptive text
        header_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))

        title_label = toga.Label(
            "Area Forecast Discussion",
            style=Pack(font_size=16, font_weight="bold", margin_bottom=10),
        )

        header_box.add(title_label)
        main_box.add(header_box)

        # Main text display with better styling and accessibility
        self.text_display = toga.MultilineTextInput(
            value=self.discussion_text,
            readonly=True,
            style=Pack(
                flex=1,
                margin=5,
                font_family="monospace",  # Monospace for better AFD formatting
            ),
        )
        main_box.add(self.text_display)

        # Button box for better layout
        button_box = toga.Box(style=Pack(direction=ROW, margin_top=15))

        # Add Explain button if API key is configured
        if self._has_api_key():
            self.explain_button = toga.Button(
                "Explain in Plain Language",
                on_press=lambda w: asyncio.create_task(self._on_explain(w)),
                style=Pack(width=180),
            )
            try:
                self.explain_button.aria_label = "Explain forecast discussion"
                self.explain_button.aria_description = (
                    "Get an AI-generated plain language summary of this technical forecast"
                )
            except AttributeError:
                pass
            button_box.add(self.explain_button)

        # Add some spacing
        spacer = toga.Box(style=Pack(flex=1))
        button_box.add(spacer)

        self.close_button = toga.Button(
            "Close", on_press=self._on_close, style=Pack(width=100, margin_left=10)
        )
        button_box.add(self.close_button)

        main_box.add(button_box)
        self.window.content = main_box

    def _has_api_key(self) -> bool:
        """Check if OpenRouter API key is configured."""
        try:
            settings = self.app.config_manager.get_config().settings
            api_key = getattr(settings, "openrouter_api_key", "")
            return bool(api_key and api_key.strip())
        except Exception:
            return False

    def _setup_accessibility(self):
        """Set up accessibility features for screen readers."""
        try:
            # The main accessibility feature is ensuring the text content
            # is immediately accessible when the dialog opens
            # The window title and focus management handle the rest
            logger.debug("Accessibility setup completed for forecast discussion dialog")

        except Exception as e:
            logger.warning(f"Could not set up accessibility features: {e}")

    async def show_and_focus(self):
        """Show the dialog and set proper focus for accessibility."""
        try:
            # Create the UI if not already created
            if self.window is None:
                self._create_ui()
                self._setup_accessibility()

            # Show the window
            self.window.show()

            # Set focus to the text display for immediate screen reader access
            await asyncio.sleep(0.1)  # Small delay to ensure dialog is fully rendered

            if self.text_display:
                try:
                    self.text_display.focus()
                    logger.info("Set focus to discussion text for accessibility")
                except Exception as e:
                    logger.warning(f"Could not set focus to text display: {e}")
                    # Fallback to close button
                    if self.close_button:
                        try:
                            self.close_button.focus()
                            logger.info("Set focus to close button as fallback")
                        except Exception as e2:
                            logger.warning(f"Could not set focus to any widget: {e2}")

        except Exception as e:
            logger.error(f"Failed to show and focus discussion dialog: {e}")
            raise

    def _on_close(self, widget):
        """Handle close button press."""
        logger.info("Forecast discussion dialog closed")
        if self.window:
            self.window.close()

    async def _on_explain(self, widget):
        """Handle explain button press - generate AI summary of the AFD."""
        from ..handlers.ai_handlers import generate_ai_explanation

        # Use generic explanation function with AFD text
        await generate_ai_explanation(
            self.app,
            self.discussion_text,
            self.location_name,
            is_weather=False,
        )
