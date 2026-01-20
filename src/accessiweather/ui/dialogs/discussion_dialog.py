"""NWS Area Forecast Discussion dialog using gui_builder."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class DiscussionDialog(forms.Dialog):
    """Dialog for displaying NWS Area Forecast Discussion using gui_builder."""

    # Header
    header_label = fields.StaticText(
        label="NWS Area Forecast Discussion provides detailed meteorologist analysis."
    )

    # Status
    status_label = fields.StaticText(label="Loading discussion...")

    # Discussion section
    discussion_header = fields.StaticText(label="Forecast Discussion")
    discussion_display = fields.Text(
        label="Forecast discussion text",
        multiline=True,
        readonly=True,
    )

    # AI Explanation section
    explanation_header = fields.StaticText(label="Plain Language Summary")
    explanation_display = fields.Text(
        label="AI-generated plain language summary",
        multiline=True,
        readonly=True,
    )

    # Buttons
    refresh_button = fields.Button(label="&Refresh")
    explain_button = fields.Button(label="&Explain with AI")
    close_button = fields.Button(label="&Close")

    def __init__(self, app: AccessiWeatherApp, **kwargs):
        """
        Initialize the discussion dialog.

        Args:
            app: Application instance
            **kwargs: Additional keyword arguments passed to Dialog

        """
        self.app = app
        self._is_loading = False
        self._is_explaining = False
        self._current_discussion: str | None = None

        kwargs.setdefault("title", "Area Forecast Discussion")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and set up components."""
        super().render(**kwargs)
        self._setup_initial_state()
        self._setup_accessibility()
        self._load_discussion()

    def _setup_initial_state(self) -> None:
        """Set up initial state."""
        self.discussion_display.set_value("Loading...")
        self.explanation_display.set_value(
            "Click 'Explain with AI' to generate a plain language summary.\n\n"
            "Note: Requires an OpenRouter API key configured in Settings."
        )
        self.explain_button.disable()

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels for screen readers."""
        self.discussion_display.set_accessible_label("Forecast discussion text")
        self.explanation_display.set_accessible_label("AI-generated plain language summary")

    def _set_status(self, message: str) -> None:
        """Update the status label."""
        self.status_label.set_label(message)

    def _load_discussion(self) -> None:
        """Load the discussion from current weather data or fetch fresh."""
        # Try to get discussion from current weather data first
        weather_data = getattr(self.app, "current_weather_data", None)
        if weather_data and weather_data.discussion:
            self._on_discussion_loaded(weather_data.discussion)
        else:
            # Fetch fresh data
            self._fetch_discussion()

    def _fetch_discussion(self) -> None:
        """Fetch fresh discussion data."""
        if self._is_loading:
            return

        location = self.app.config_manager.get_current_location()
        if not location:
            self._set_status("No location selected.")
            self.discussion_display.set_value(
                "Please select a location to view the forecast discussion."
            )
            return

        if not getattr(self.app, "weather_client", None):
            self._set_status("Weather client is not ready.")
            return

        self._is_loading = True
        self.refresh_button.disable()
        self._set_status(f"Fetching discussion for {location.name}...")

        # Run async fetch
        self.app.run_async(self._do_fetch(location))

    async def _do_fetch(self, location):
        """Perform the discussion fetch."""
        try:
            # Fetch weather data which includes discussion
            weather_data = await self.app.weather_client.get_weather_data(location)
            discussion = weather_data.discussion if weather_data else None
            wx.CallAfter(self._on_fetch_complete, location.name, discussion)
        except Exception as e:
            logger.error(f"Discussion fetch failed: {e}")
            wx.CallAfter(self._on_fetch_error, str(e))

    def _on_fetch_complete(self, location_name: str, discussion: str | None) -> None:
        """Handle fetch completion."""
        self._is_loading = False
        self.refresh_button.enable()

        if discussion:
            self._on_discussion_loaded(discussion, location_name)
        else:
            self._set_status("No discussion available for this location.")
            self.discussion_display.set_value(
                "Forecast discussion not available.\n\n"
                "This may occur if:\n"
                "- The location is outside NWS coverage (US only)\n"
                "- The NWS service is temporarily unavailable\n"
                "- No recent discussion has been issued"
            )
            self.explain_button.disable()

    def _on_fetch_error(self, error: str) -> None:
        """Handle fetch error."""
        self._is_loading = False
        self.refresh_button.enable()
        self._set_status(f"Error: {error}")
        self.discussion_display.set_value(f"Failed to load discussion: {error}")

    def _on_discussion_loaded(self, discussion: str, location_name: str | None = None) -> None:
        """Handle discussion data loaded."""
        self._current_discussion = discussion

        # Check if it's an error message
        if discussion.startswith("Forecast discussion not available"):
            self._set_status("Discussion not available.")
            self.discussion_display.set_value(discussion)
            self.explain_button.disable()
            return

        if location_name:
            self._set_status(f"Discussion loaded for {location_name}.")
        else:
            location = self.app.config_manager.get_current_location()
            loc_name = location.name if location else "current location"
            self._set_status(f"Discussion loaded for {loc_name}.")

        self.discussion_display.set_value(discussion)

        # Enable explain button if AI is available
        self._update_explain_button_state()

    def _update_explain_button_state(self) -> None:
        """Enable or disable the explain button based on AI availability."""
        # Check if OpenRouter API key is configured
        try:
            from ..config.secure_storage import SecureStorage

            api_key = SecureStorage.get_password("openrouter_api_key")
            if api_key and self._current_discussion:
                self.explain_button.enable()
            else:
                self.explain_button.disable()
        except Exception:
            self.explain_button.disable()

    @refresh_button.add_callback
    def on_refresh(self):
        """Handle refresh button press."""
        self._fetch_discussion()

    @explain_button.add_callback
    def on_explain(self):
        """Handle explain button press - use AI to explain the discussion."""
        if not self._current_discussion or self._is_explaining:
            return

        self._is_explaining = True
        self.explain_button.disable()
        self.explanation_display.set_value("Generating plain language summary...")
        self._set_status("Generating AI explanation...")

        # Run async explanation
        self.app.run_async(self._do_explain())

    async def _do_explain(self):
        """Perform the AI explanation."""
        try:
            from ...ai_explainer import AIExplainer, ExplanationStyle
            from ...config.secure_storage import SecureStorage

            api_key = SecureStorage.get_password("openrouter_api_key")
            if not api_key:
                wx.CallAfter(
                    self._on_explain_error,
                    "OpenRouter API key not configured. Set it in Settings > AI.",
                )
                return

            # Get configured model or use default
            settings = self.app.config_manager.get_settings()
            model = getattr(settings, "ai_model", None)

            explainer = (
                AIExplainer(api_key=api_key, model=model) if model else AIExplainer(api_key=api_key)
            )

            location = self.app.config_manager.get_current_location()
            location_name = location.name if location else "your area"

            # Ensure we have a valid discussion string
            discussion_text = self._current_discussion or ""
            result = await explainer.explain_afd(
                discussion_text,
                location_name,
                style=ExplanationStyle.DETAILED,
            )

            wx.CallAfter(self._on_explain_complete, result.text, result.model_used)

        except Exception as e:
            logger.error(f"AI explanation failed: {e}")
            wx.CallAfter(self._on_explain_error, str(e))

    def _on_explain_complete(self, explanation: str, model_used: str) -> None:
        """Handle explanation completion."""
        self._is_explaining = False
        self.explain_button.enable()
        self.explanation_display.set_value(explanation)
        self._set_status(f"Explanation generated using {model_used}.")

    def _on_explain_error(self, error: str) -> None:
        """Handle explanation error."""
        self._is_explaining = False
        self.explain_button.enable()
        self.explanation_display.set_value(
            f"Failed to generate explanation: {error}\n\n"
            "Please check your OpenRouter API key in Settings."
        )
        self._set_status("Explanation failed.")

    @close_button.add_callback
    def on_close(self):
        """Handle close button press."""
        self.widget.control.EndModal(wx.ID_CLOSE)


def show_discussion_dialog(parent, app: AccessiWeatherApp) -> None:
    """
    Show the Area Forecast Discussion dialog.

    Args:
        parent: Parent window (gui_builder widget)
        app: Application instance

    """
    try:
        # Get the underlying wx control if parent is a gui_builder widget
        parent_ctrl = getattr(parent, "control", parent)

        dlg = DiscussionDialog(app, parent=parent_ctrl)
        dlg.render()
        dlg.widget.control.ShowModal()
        dlg.widget.control.Destroy()

    except Exception as e:
        logger.error(f"Failed to show discussion dialog: {e}")
        wx.MessageBox(
            f"Failed to open forecast discussion: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
