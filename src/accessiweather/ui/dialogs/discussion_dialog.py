"""NWS Area Forecast Discussion dialog using plain wxPython."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class DiscussionDialog(wx.Dialog):
    """Dialog for displaying NWS Area Forecast Discussion."""

    def __init__(
        self, parent: wx.Window, app: AccessiWeatherApp, title: str = "Area Forecast Discussion"
    ):
        """
        Initialize the discussion dialog.

        Args:
            parent: Parent window
            app: Application instance
            title: Dialog title

        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.app = app
        self._is_loading = False
        self._is_explaining = False
        self._current_discussion: str | None = None

        self._create_widgets()
        self._bind_events()
        self._setup_initial_state()

        # Set a reasonable size
        self.SetSize((700, 600))
        self.CenterOnParent()

        # Load the discussion
        self._load_discussion()

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        self.header_label = wx.StaticText(
            panel, label="NWS Area Forecast Discussion provides detailed meteorologist analysis."
        )
        main_sizer.Add(self.header_label, 0, wx.ALL | wx.EXPAND, 10)

        # Status
        self.status_label = wx.StaticText(panel, label="Loading discussion...")
        main_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        # Discussion section
        discussion_header = wx.StaticText(panel, label="Forecast Discussion:")
        main_sizer.Add(discussion_header, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.discussion_display = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="Forecast discussion text",
        )
        main_sizer.Add(self.discussion_display, 1, wx.ALL | wx.EXPAND, 10)

        # AI Explanation section
        explanation_header = wx.StaticText(panel, label="Plain Language Summary:")
        main_sizer.Add(explanation_header, 0, wx.LEFT | wx.RIGHT, 10)

        self.explanation_display = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="AI-generated plain language summary",
        )
        main_sizer.Add(self.explanation_display, 1, wx.ALL | wx.EXPAND, 10)

        # Button sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.refresh_button = wx.Button(panel, label="&Refresh")
        button_sizer.Add(self.refresh_button, 0, wx.RIGHT, 5)

        self.explain_button = wx.Button(panel, label="&Explain with AI")
        button_sizer.Add(self.explain_button, 0, wx.RIGHT, 5)

        self.close_button = wx.Button(panel, wx.ID_CLOSE, label="&Close")
        button_sizer.Add(self.close_button, 0)

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        panel.SetSizer(main_sizer)

        # Dialog sizer to contain the panel
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

    def _bind_events(self) -> None:
        """Bind event handlers."""
        self.refresh_button.Bind(wx.EVT_BUTTON, self._on_refresh)
        self.explain_button.Bind(wx.EVT_BUTTON, self._on_explain)
        self.close_button.Bind(wx.EVT_BUTTON, self._on_close)

    def _setup_initial_state(self) -> None:
        """Set up initial state."""
        self.discussion_display.SetValue("Loading...")
        self.explanation_display.SetValue(
            "Click 'Explain with AI' to generate a plain language summary.\n\n"
            "Note: Requires an OpenRouter API key configured in Settings."
        )
        self.explain_button.Disable()

    def _set_status(self, message: str) -> None:
        """Update the status label."""
        self.status_label.SetLabel(message)

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
            self.discussion_display.SetValue(
                "Please select a location to view the forecast discussion."
            )
            return

        if not getattr(self.app, "weather_client", None):
            self._set_status("Weather client is not ready.")
            return

        self._is_loading = True
        self.refresh_button.Disable()
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
        self.refresh_button.Enable()

        if discussion:
            self._on_discussion_loaded(discussion, location_name)
        else:
            self._set_status("No discussion available for this location.")
            self.discussion_display.SetValue(
                "Forecast discussion not available.\n\n"
                "This may occur if:\n"
                "- The location is outside NWS coverage (US only)\n"
                "- The NWS service is temporarily unavailable\n"
                "- No recent discussion has been issued"
            )
            self.explain_button.Disable()

    def _on_fetch_error(self, error: str) -> None:
        """Handle fetch error."""
        self._is_loading = False
        self.refresh_button.Enable()
        self._set_status(f"Error: {error}")
        self.discussion_display.SetValue(f"Failed to load discussion: {error}")

    def _on_discussion_loaded(self, discussion: str, location_name: str | None = None) -> None:
        """Handle discussion data loaded."""
        self._current_discussion = discussion

        # Check if it's an error message
        if discussion.startswith("Forecast discussion not available"):
            self._set_status("Discussion not available.")
            self.discussion_display.SetValue(discussion)
            self.explain_button.Disable()
            return

        if location_name:
            self._set_status(f"Discussion loaded for {location_name}.")
        else:
            location = self.app.config_manager.get_current_location()
            loc_name = location.name if location else "current location"
            self._set_status(f"Discussion loaded for {loc_name}.")

        self.discussion_display.SetValue(discussion)

        # Enable explain button if AI is available
        self._update_explain_button_state()

    def _update_explain_button_state(self) -> None:
        """Enable or disable the explain button based on AI availability."""
        # Check if OpenRouter API key is configured
        try:
            from ...config.secure_storage import SecureStorage

            api_key = SecureStorage.get_password("openrouter_api_key")
            if api_key and self._current_discussion:
                self.explain_button.Enable()
            else:
                self.explain_button.Disable()
        except Exception:
            self.explain_button.Disable()

    def _on_refresh(self, event) -> None:
        """Handle refresh button press."""
        self._fetch_discussion()

    def _on_explain(self, event) -> None:
        """Handle explain button press - use AI to explain the discussion."""
        if not self._current_discussion or self._is_explaining:
            return

        self._is_explaining = True
        self.explain_button.Disable()
        self.explanation_display.SetValue("Generating plain language summary...")
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
            model_pref = getattr(settings, "ai_model_preference", None)
            # Convert "auto" to OpenRouter's auto-router model ID
            model = "openrouter/auto" if model_pref == "auto" else model_pref

            explainer = AIExplainer(
                api_key=api_key,
                model=model if model else None,
                custom_system_prompt=getattr(settings, "custom_system_prompt", None),
                custom_instructions=getattr(settings, "custom_instructions", None),
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
        self.explain_button.Enable()
        self.explanation_display.SetValue(explanation)
        self._set_status(f"Explanation generated using {model_used}.")

    def _on_explain_error(self, error: str) -> None:
        """Handle explanation error."""
        self._is_explaining = False
        self.explain_button.Enable()
        self.explanation_display.SetValue(
            f"Failed to generate explanation: {error}\n\n"
            "Please check your OpenRouter API key in Settings."
        )
        self._set_status("Explanation failed.")

    def _on_close(self, event) -> None:
        """Handle close button press."""
        self.EndModal(wx.ID_CLOSE)


def show_discussion_dialog(parent, app: AccessiWeatherApp) -> None:
    """
    Show the Area Forecast Discussion dialog.

    Args:
        parent: Parent window (wx.Window or has .control attribute)
        app: Application instance

    """
    try:
        # Get the underlying wx control if parent has a control attribute
        parent_ctrl = getattr(parent, "control", parent)

        dlg = DiscussionDialog(parent_ctrl, app)
        dlg.ShowModal()
        dlg.Destroy()

    except Exception as e:
        logger.error(f"Failed to show discussion dialog: {e}")
        wx.MessageBox(
            f"Failed to open forecast discussion: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
