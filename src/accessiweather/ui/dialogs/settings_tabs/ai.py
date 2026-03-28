"""AI settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)

_STYLE_VALUES = ["brief", "standard", "detailed"]
_STYLE_MAP = {"brief": 0, "standard": 1, "detailed": 2}


class AITab:
    """AI tab: OpenRouter API key, model preferences, explanation style, custom prompts."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    def create(self):
        """Build the AI tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        sizer.Add(wx.StaticText(panel, label="AI Weather Explanations"), 0, wx.ALL, 5)
        sizer.Add(
            wx.StaticText(
                panel,
                label="Get natural language explanations of weather conditions using AI.",
            ),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        sizer.Add(wx.StaticText(panel, label="OpenRouter API Key:"), 0, wx.ALL, 5)
        controls["openrouter_key"] = wx.TextCtrl(panel, style=wx.TE_PASSWORD, size=(300, -1))
        sizer.Add(controls["openrouter_key"], 0, wx.LEFT, 10)

        validate_btn = wx.Button(panel, label="Validate API Key")
        validate_btn.Bind(wx.EVT_BUTTON, self.dialog._on_validate_openrouter_key)
        sizer.Add(validate_btn, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        row_model = wx.BoxSizer(wx.HORIZONTAL)
        row_model.Add(
            wx.StaticText(panel, label="Model Preference:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["ai_model"] = wx.Choice(
            panel,
            choices=[
                "Free Router (Auto, Free)",
                "Llama 3.3 70B (Free)",
                "Auto Router (Paid)",
            ],
        )
        row_model.Add(controls["ai_model"], 0)
        sizer.Add(row_model, 0, wx.LEFT, 10)

        browse_btn = wx.Button(panel, label="Browse Models...")
        browse_btn.Bind(wx.EVT_BUTTON, self.dialog._on_browse_models)
        sizer.Add(browse_btn, 0, wx.LEFT | wx.TOP, 10)

        row_style = wx.BoxSizer(wx.HORIZONTAL)
        row_style.Add(
            wx.StaticText(panel, label="Explanation Style:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["ai_style"] = wx.Choice(
            panel,
            choices=[
                "Brief (1-2 sentences)",
                "Standard (3-4 sentences)",
                "Detailed (full paragraph)",
            ],
        )
        row_style.Add(controls["ai_style"], 0)
        sizer.Add(row_style, 0, wx.LEFT | wx.TOP, 10)

        sizer.Add(
            wx.StaticText(panel, label="Custom System Prompt (optional):"),
            0,
            wx.LEFT | wx.TOP,
            10,
        )
        controls["custom_prompt"] = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(400, 60))
        sizer.Add(controls["custom_prompt"], 0, wx.LEFT | wx.EXPAND, 10)

        reset_prompt_btn = wx.Button(panel, label="Reset to Default")
        reset_prompt_btn.Bind(wx.EVT_BUTTON, self.dialog._on_reset_prompt)
        sizer.Add(reset_prompt_btn, 0, wx.LEFT | wx.TOP, 10)

        sizer.Add(
            wx.StaticText(panel, label="Custom Instructions (optional):"),
            0,
            wx.LEFT | wx.TOP,
            10,
        )
        controls["custom_instructions"] = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(400, 40))
        controls["custom_instructions"].SetHint(
            "e.g., Focus on outdoor activities, Keep responses under 50 words"
        )
        sizer.Add(controls["custom_instructions"], 0, wx.LEFT | wx.EXPAND, 10)

        sizer.Add(wx.StaticText(panel, label="Cost Information:"), 0, wx.LEFT | wx.TOP, 10)
        sizer.Add(
            wx.StaticText(panel, label="Free models: No cost, may have rate limits"),
            0,
            wx.LEFT,
            15,
        )
        sizer.Add(
            wx.StaticText(panel, label="Paid models: ~$0.001 per explanation (varies by model)"),
            0,
            wx.LEFT,
            15,
        )

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, "AI")
        return panel

    def load(self, settings):
        """Populate AI tab controls from settings."""
        controls = self.dialog._controls

        openrouter_key = getattr(settings, "openrouter_api_key", "") or ""
        controls["openrouter_key"].SetValue(str(openrouter_key))
        self.dialog._original_openrouter_key = str(openrouter_key)
        self.dialog._openrouter_key_cleared = False
        if hasattr(wx, "EVT_TEXT"):
            controls["openrouter_key"].Bind(
                wx.EVT_TEXT,
                lambda e: setattr(self.dialog, "_openrouter_key_cleared", True),
            )

        ai_model = getattr(settings, "ai_model_preference", "openrouter/free")
        if ai_model == "openrouter/free":
            controls["ai_model"].SetSelection(0)
        elif ai_model == "meta-llama/llama-3.3-70b-instruct:free":
            controls["ai_model"].SetSelection(1)
        elif ai_model == "auto":
            controls["ai_model"].SetSelection(2)
        else:
            model_display = f"Selected: {ai_model.split('/')[-1]}"
            controls["ai_model"].Append(model_display)
            controls["ai_model"].SetSelection(3)
            self.dialog._selected_specific_model = ai_model

        ai_style = getattr(settings, "ai_explanation_style", "standard")
        controls["ai_style"].SetSelection(_STYLE_MAP.get(ai_style, 1))

        custom_prompt = getattr(settings, "custom_system_prompt", "") or ""
        controls["custom_prompt"].SetValue(custom_prompt)

        custom_instructions = getattr(settings, "custom_instructions", "") or ""
        controls["custom_instructions"].SetValue(custom_instructions)

    def save(self) -> dict:
        """Return AI tab settings as a dict."""
        controls = self.dialog._controls
        return {
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
            "openrouter_key": "OpenRouter API Key",
            "ai_model": "Model Preference",
            "ai_style": "Explanation Style",
            "custom_prompt": "Custom System Prompt (optional)",
            "custom_instructions": "Custom Instructions (optional)",
        }
        for key, name in names.items():
            controls[key].SetName(name)
