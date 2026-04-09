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

    def create(self, page_label: str = "AI"):
        """Build the AI tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        self.dialog.add_help_text(
            panel,
            sizer,
            "Use AI explanations if you want plain-language weather summaries powered by OpenRouter.",
            left=5,
        )

        key_section = self.dialog.create_section(
            panel,
            sizer,
            "OpenRouter access",
            "Add and validate your OpenRouter API key before choosing a model.",
        )
        controls["openrouter_key"] = self.dialog.add_labeled_control_row(
            panel,
            key_section,
            "OpenRouter API key:",
            lambda parent: wx.TextCtrl(parent, style=wx.TE_PASSWORD, size=(320, -1)),
            expand_control=True,
        )
        validate_btn = wx.Button(panel, label="Validate OpenRouter key")
        validate_btn.Bind(wx.EVT_BUTTON, self.dialog._on_validate_openrouter_key)
        key_section.Add(validate_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        model_section = self.dialog.create_section(
            panel,
            sizer,
            "Model and explanation style",
            "Free options are easiest to start with. Paid routing can unlock more model choices.",
        )
        controls["ai_model"] = self.dialog.add_labeled_control_row(
            panel,
            model_section,
            "Model preference:",
            lambda parent: wx.Choice(
                parent,
                choices=[
                    "Free router (automatic, free)",
                    "Llama 3.3 70B (free)",
                    "Auto router (paid)",
                ],
            ),
        )
        browse_btn = wx.Button(panel, label="Browse OpenRouter models...")
        browse_btn.Bind(wx.EVT_BUTTON, self.dialog._on_browse_models)
        model_section.Add(browse_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["ai_style"] = self.dialog.add_labeled_control_row(
            panel,
            model_section,
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
        controls["custom_prompt"] = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(420, 70))
        prompt_section.Add(
            wx.StaticText(panel, label="Custom system prompt (optional):"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        prompt_section.Add(
            controls["custom_prompt"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        reset_prompt_btn = wx.Button(panel, label="Reset prompt to default")
        reset_prompt_btn.Bind(wx.EVT_BUTTON, self.dialog._on_reset_prompt)
        prompt_section.Add(reset_prompt_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["custom_instructions"] = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE,
            size=(420, 50),
        )
        controls["custom_instructions"].SetHint(
            "For example: focus on outdoor activities, keep responses under 50 words"
        )
        prompt_section.Add(
            wx.StaticText(panel, label="Custom instructions (optional):"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
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
            "Free models do not cost money but may be rate limited. Paid models often cost around $0.001 per explanation, depending on the model.",
        )

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, page_label)
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
                lambda _event: setattr(self.dialog, "_openrouter_key_cleared", True),
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
            "openrouter_key": "OpenRouter API key",
            "ai_model": "AI model preference",
            "ai_style": "AI explanation style",
            "custom_prompt": "Custom system prompt",
            "custom_instructions": "Custom instructions",
        }
        for key, name in names.items():
            controls[key].SetName(name)
