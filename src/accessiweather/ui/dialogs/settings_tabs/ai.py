"""AI settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)

_STYLE_VALUES = ["brief", "standard", "detailed"]
_STYLE_MAP = {"brief": 0, "standard": 1, "detailed": 2}


class AITab:
    """AI provider access, model preferences, and shared custom prompts."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    def create(self, page_label: str = "AI"):
        """Build the AI tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        self.dialog.add_help_text(
            panel,
            sizer,
            "Choose the provider used for AI weather explanations and the weather assistant. Each provider keeps its own key and model.",
            left=5,
        )

        controls["ai_provider"] = self.dialog.add_labeled_control_row(
            panel,
            sizer,
            "AI provider:",
            lambda parent: wx.Choice(parent, choices=["OpenRouter", "Venice AI"]),
        )
        controls["ai_provider"].SetSelection(0)
        controls["ai_provider"].Bind(wx.EVT_CHOICE, self._on_provider_changed)
        self._panel = panel
        self._provider_panels = {}

        openrouter_panel = wx.Panel(panel)
        openrouter_sizer = wx.BoxSizer(wx.VERTICAL)
        key_section = self.dialog.create_section(
            openrouter_panel,
            openrouter_sizer,
            "OpenRouter access",
            "Add and validate your OpenRouter API key before choosing a model.",
        )
        controls["openrouter_key"] = self.dialog.add_labeled_control_row(
            openrouter_panel,
            key_section,
            "OpenRouter API key:",
            lambda parent: wx.TextCtrl(parent, style=wx.TE_PASSWORD, size=(320, -1)),
            expand_control=True,
        )
        validate_btn = wx.Button(openrouter_panel, label="Validate OpenRouter key")
        validate_btn.Bind(wx.EVT_BUTTON, self.dialog._on_validate_openrouter_key)
        key_section.Add(validate_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        model_section = self.dialog.create_section(
            openrouter_panel,
            openrouter_sizer,
            "OpenRouter model",
            "Free options are easiest to start with. Paid routing can unlock more model choices.",
        )
        controls["ai_model"] = self.dialog.add_labeled_control_row(
            openrouter_panel,
            model_section,
            "OpenRouter model preference:",
            lambda parent: wx.Choice(
                parent,
                choices=[
                    "Free router (automatic, free)",
                    "Auto router (paid)",
                ],
            ),
        )
        browse_btn = wx.Button(openrouter_panel, label="Browse OpenRouter models...")
        browse_btn.Bind(wx.EVT_BUTTON, self.dialog._on_browse_models)
        model_section.Add(browse_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        openrouter_panel.SetSizer(openrouter_sizer)
        sizer.Add(openrouter_panel, 0, wx.EXPAND)
        self._provider_panels["openrouter"] = openrouter_panel

        venice_panel = wx.Panel(panel)
        venice_sizer = wx.BoxSizer(wx.VERTICAL)
        venice_section = self.dialog.create_section(
            venice_panel,
            venice_sizer,
            "Venice AI access",
            "Use your own Venice API key. API requests can use prepaid USD, DIEM, or bundled API credits available to your account.",
        )
        controls["venice_key"] = self.dialog.add_labeled_control_row(
            venice_panel,
            venice_section,
            "Venice API key:",
            lambda parent: wx.TextCtrl(parent, style=wx.TE_PASSWORD, size=(320, -1)),
            expand_control=True,
        )
        controls["validate_venice_key"] = wx.Button(venice_panel, label="Validate Venice key")
        controls["validate_venice_key"].Bind(wx.EVT_BUTTON, self.dialog._on_validate_venice_key)
        venice_section.Add(controls["validate_venice_key"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["get_venice_key"] = wx.Button(venice_panel, label="Get Venice API key...")
        controls["get_venice_key"].Bind(wx.EVT_BUTTON, self._on_get_venice_key)
        venice_section.Add(controls["get_venice_key"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["venice_model"] = self.dialog.add_labeled_control_row(
            venice_panel,
            venice_section,
            "Venice model ID:",
            lambda parent: wx.TextCtrl(parent, size=(320, -1)),
            expand_control=True,
        )
        venice_browse = wx.Button(venice_panel, label="Browse Venice models...")
        venice_browse.Bind(wx.EVT_BUTTON, self._on_browse_venice_models)
        venice_section.Add(venice_browse, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.dialog.add_help_text(
            venice_panel,
            venice_section,
            "Default: venice-uncensored-1-2. Choose a text model with function calling for the weather assistant. Manage keys and API credits at venice.ai/settings/api.",
        )
        venice_panel.SetSizer(venice_sizer)
        sizer.Add(venice_panel, 0, wx.EXPAND)
        self._provider_panels["venice"] = venice_panel
        self._apply_provider_visibility()

        controls["ai_style"] = self.dialog.add_labeled_control_row(
            panel,
            sizer,
            "Explanation style:",
            lambda parent: wx.Choice(
                parent,
                choices=[
                    "Brief (1-2 sentences)",
                    "Standard (3-4 sentences)",
                    "Detailed (full paragraph)",
                ],
            ),
        )

        prompt_section = self.dialog.create_section(
            panel,
            sizer,
            "Custom prompts",
            "Leave these blank to use the default behavior. Add text only if you want more control over tone or focus.",
        )
        prompt_section.Add(
            wx.StaticText(panel, label="Custom system prompt (optional):"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        controls["custom_prompt"] = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(420, 70))
        prompt_section.Add(
            controls["custom_prompt"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        reset_prompt_btn = wx.Button(panel, label="Reset prompt to default")
        reset_prompt_btn.Bind(wx.EVT_BUTTON, self.dialog._on_reset_prompt)
        prompt_section.Add(reset_prompt_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        prompt_section.Add(
            wx.StaticText(panel, label="Custom instructions (optional):"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        controls["custom_instructions"] = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE,
            size=(420, 50),
        )
        controls["custom_instructions"].SetHint(
            "For example: focus on outdoor activities, keep responses under 50 words"
        )
        prompt_section.Add(
            controls["custom_instructions"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        cost_section = self.dialog.create_section(
            panel,
            sizer,
            "Cost notes",
            None,
        )
        self.dialog.add_help_text(
            panel,
            cost_section,
            "OpenRouter offers free models that may be rate limited. Paid models charge according to usage and model pricing. Venice can use prepaid USD, DIEM, or bundled API credits; having credits does not make a paid model free.",
        )

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, page_label)
        return panel

    def _on_provider_changed(self, event):
        """Show only the settings for the provider the user picked."""
        self._apply_provider_visibility()

    def _apply_provider_visibility(self):
        """Hide the sections for providers that are not selected."""
        panels = getattr(self, "_provider_panels", None)
        if not panels:
            return
        selected = (
            "venice" if self.dialog._controls["ai_provider"].GetSelection() == 1 else "openrouter"
        )
        for name, provider_panel in panels.items():
            provider_panel.Show(name == selected)
        page = getattr(self, "_panel", None)
        if page is not None:
            page.Layout()
            if hasattr(page, "FitInside"):
                page.FitInside()

    def _on_get_venice_key(self, event):
        """Open account setup without collecting credentials in the application."""
        if not wx.LaunchDefaultBrowser("https://venice.ai/settings/api"):
            wx.MessageBox(
                "Could not open your browser. Visit https://venice.ai/settings/api "
                "to sign up or manage your Venice API keys.",
                "Open Venice API settings",
                wx.OK | wx.ICON_ERROR,
                parent=self.dialog,
            )

    def load(self, settings):
        """Populate AI tab controls from settings."""
        controls = self.dialog._controls

        controls["ai_provider"].SetSelection(
            1 if getattr(settings, "ai_provider", "openrouter") == "venice" else 0
        )
        self._apply_provider_visibility()
        venice_key = str(getattr(settings, "venice_api_key", "") or "")
        controls["venice_key"].SetValue(venice_key)
        self.dialog._original_venice_key = venice_key
        self.dialog._venice_key_cleared = False
        if hasattr(wx, "EVT_TEXT"):
            controls["venice_key"].Bind(
                wx.EVT_TEXT,
                lambda _event: setattr(self.dialog, "_venice_key_cleared", True),
            )
        controls["venice_model"].SetValue(
            getattr(settings, "venice_model", "venice-uncensored-1-2") or "venice-uncensored-1-2"
        )

        openrouter_key = getattr(settings, "openrouter_api_key", "") or ""
        controls["openrouter_key"].SetValue(str(openrouter_key))
        self.dialog._original_openrouter_key = str(openrouter_key)
        self.dialog._openrouter_key_cleared = False
        if hasattr(wx, "EVT_TEXT"):
            controls["openrouter_key"].Bind(
                wx.EVT_TEXT,
                lambda _event: setattr(self.dialog, "_openrouter_key_cleared", True),
            )

        ai_model = getattr(settings, "ai_model_preference", "openrouter/free")
        if ai_model == "openrouter/free":
            controls["ai_model"].SetSelection(0)
        elif ai_model in ("auto", "openrouter/auto"):
            controls["ai_model"].SetSelection(1)
        else:
            model_display = f"Selected: {ai_model.split('/')[-1]}"
            controls["ai_model"].Append(model_display)
            controls["ai_model"].SetSelection(2)
            self.dialog._selected_specific_model = ai_model

        ai_style = getattr(settings, "ai_explanation_style", "standard")
        controls["ai_style"].SetSelection(_STYLE_MAP.get(ai_style, 1))

        custom_prompt = getattr(settings, "custom_system_prompt", "") or ""
        controls["custom_prompt"].SetValue(custom_prompt)

        custom_instructions = getattr(settings, "custom_instructions", "") or ""
        controls["custom_instructions"].SetValue(custom_instructions)

    def _on_browse_venice_models(self, event):
        """Keep Venice model browsing separate from OpenRouter credentials and selection."""
        from ..model_browser_dialog import show_model_browser_dialog

        controls = self.dialog._controls
        selected = show_model_browser_dialog(
            self.dialog,
            api_key=controls["venice_key"].GetValue().strip() or None,
            provider="venice",
        )
        if selected:
            controls["venice_model"].SetValue(selected)

    def save(self) -> dict:
        """Return AI tab settings as a dict."""
        controls = self.dialog._controls
        return {
            "ai_provider": "venice"
            if controls["ai_provider"].GetSelection() == 1
            else "openrouter",
            "venice_api_key": controls["venice_key"].GetValue().strip(),
            "venice_model": controls["venice_model"].GetValue().strip() or "venice-uncensored-1-2",
            "openrouter_api_key": controls["openrouter_key"].GetValue(),
            "ai_model_preference": self.dialog._get_ai_model_preference(),
            "ai_explanation_style": _STYLE_VALUES[controls["ai_style"].GetSelection()],
            "custom_system_prompt": controls["custom_prompt"].GetValue() or None,
            "custom_instructions": controls["custom_instructions"].GetValue() or None,
        }

    def setup_accessibility(self):
        """Set accessibility names for AI tab controls."""
        controls = self.dialog._controls
        names = {
            "ai_provider": "AI provider",
            "venice_key": "Venice API key",
            "venice_model": "Venice model ID",
            "validate_venice_key": "Validate Venice key",
            "get_venice_key": "Get Venice API key (opens browser)",
            "openrouter_key": "OpenRouter API key",
            "ai_model": "AI model preference",
            "ai_style": "AI explanation style",
            "custom_prompt": "Custom system prompt",
            "custom_instructions": "Custom instructions",
        }
        for key, name in names.items():
            controls[key].SetName(name)
