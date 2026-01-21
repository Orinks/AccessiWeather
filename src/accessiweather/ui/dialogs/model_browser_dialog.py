"""Model browser dialog for selecting OpenRouter AI models."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from ...api.openrouter_models import OpenRouterModel

logger = logging.getLogger(__name__)

# Mapping of provider IDs to display names for common providers
PROVIDER_DISPLAY_NAMES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "meta-llama": "Meta",
    "mistralai": "Mistral AI",
    "cohere": "Cohere",
    "perplexity": "Perplexity",
    "deepseek": "DeepSeek",
    "microsoft": "Microsoft",
    "amazon": "Amazon",
    "nvidia": "NVIDIA",
    "qwen": "Qwen",
    "x-ai": "xAI",
    "ai21": "AI21 Labs",
    "databricks": "Databricks",
    "inflection": "Inflection",
    "cognitivecomputations": "Cognitive Computations",
    "nousresearch": "Nous Research",
    "openchat": "OpenChat",
    "openrouter": "OpenRouter",
    "neversleep": "NeverSleep",
    "gryphe": "Gryphe",
    "undi95": "Undi95",
    "huggingfaceh4": "Hugging Face",
    "pygmalionai": "Pygmalion AI",
    "mancer": "Mancer",
    "lynn": "Lynn",
    "thedrummer": "TheDrummer",
    "sao10k": "Sao10k",
    "eva-unit-01": "Eva Unit 01",
    "aetherwiing": "Aetherwiing",
    "sophosympatheia": "Sophosympatheia",
    "liquid": "Liquid",
    "01-ai": "01.AI",
}


def get_provider_display_name(provider: str) -> str:
    """Get the display name for a provider."""
    if provider in PROVIDER_DISPLAY_NAMES:
        return PROVIDER_DISPLAY_NAMES[provider]
    # Fallback: capitalize and replace hyphens with spaces
    return provider.replace("-", " ").title()


class ModelBrowserDialog(wx.Dialog):
    """
    Dialog for browsing and selecting OpenRouter AI models.

    Provides search, filtering by free models, and displays model details.
    """

    def __init__(self, parent, api_key: str | None = None):
        """
        Initialize the model browser dialog.

        Args:
            parent: Parent window
            api_key: Optional OpenRouter API key

        """
        super().__init__(
            parent,
            title="Browse AI Models",
            size=(650, 550),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.api_key = api_key
        self._all_models: list[OpenRouterModel] = []
        self._filtered_models: list[OpenRouterModel] = []
        self._selected_model_id: str | None = None
        self._providers: list[str] = []

        self._create_ui()
        self._setup_accessibility()
        self._load_models()

    def _create_ui(self):
        """Create the dialog UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Search section
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_label = wx.StaticText(self, label="Search models:")
        search_sizer.Add(search_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.search_box = wx.TextCtrl(self, size=(300, -1))
        self.search_box.Bind(wx.EVT_TEXT, self._on_search_changed)
        search_sizer.Add(self.search_box, 1, wx.EXPAND)
        main_sizer.Add(search_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Filter row
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Free only checkbox
        self.free_only_checkbox = wx.CheckBox(self, label="Free only")
        self.free_only_checkbox.Bind(wx.EVT_CHECKBOX, self._on_filter_changed)
        filter_sizer.Add(self.free_only_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        # Provider filter
        provider_label = wx.StaticText(self, label="Provider:")
        filter_sizer.Add(provider_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.provider_choice = wx.Choice(self, choices=["All Providers"])
        self.provider_choice.SetSelection(0)
        self.provider_choice.Bind(wx.EVT_CHOICE, self._on_filter_changed)
        filter_sizer.Add(self.provider_choice, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(filter_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Status display
        self.status_label = wx.StaticText(self, label="Loading models...")
        main_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT, 10)

        # Model list
        list_label = wx.StaticText(self, label="Available models:")
        main_sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.model_list = wx.ListBox(self, style=wx.LB_SINGLE, size=(-1, 200))
        self.model_list.Bind(wx.EVT_LISTBOX, self._on_model_selected)
        self.model_list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_model_double_click)
        main_sizer.Add(self.model_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Description display
        desc_label = wx.StaticText(self, label="Model description:")
        main_sizer.Add(desc_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.description_text = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            size=(-1, 80),
        )
        main_sizer.Add(self.description_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.refresh_btn = wx.Button(self, label="&Refresh")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self._on_refresh)
        btn_sizer.Add(self.refresh_btn, 0, wx.RIGHT, 10)

        btn_sizer.AddStretchSpacer()

        self.select_btn = wx.Button(self, wx.ID_OK, "&Select")
        self.select_btn.Bind(wx.EVT_BUTTON, self._on_select)
        self.select_btn.Enable(False)
        btn_sizer.Add(self.select_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "&Cancel")
        btn_sizer.Add(cancel_btn, 0)

        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)

    def _setup_accessibility(self):
        """Set up accessibility labels for screen readers."""
        self.search_box.SetName("Search for AI models by name or description")
        self.model_list.SetName("Available AI models list")
        self.description_text.SetName("Description of selected model")
        self.free_only_checkbox.SetName("Filter to show only free models")
        self.provider_choice.SetName("Filter by model provider")

    def _on_search_changed(self, event):
        """Handle search text changed."""
        self._apply_filters()

    def _on_filter_changed(self, event):
        """Handle filter checkbox or provider selection changed."""
        # If the free-only checkbox changed, update the provider list
        if event.GetEventObject() == self.free_only_checkbox:
            self._update_provider_list()
        self._apply_filters()

    def _on_model_selected(self, event):
        """Handle model selection in list."""
        index = self.model_list.GetSelection()
        if index != wx.NOT_FOUND and 0 <= index < len(self._filtered_models):
            model = self._filtered_models[index]
            self._selected_model_id = model.id
            self.select_btn.Enable(True)

            # Show description
            desc = model.description or "No description available."
            self.description_text.SetValue(desc)
        else:
            self._selected_model_id = None
            self.select_btn.Enable(False)
            self.description_text.SetValue("")

    def _on_model_double_click(self, event):
        """Handle double-click on model - select and close."""
        index = self.model_list.GetSelection()
        if index != wx.NOT_FOUND and 0 <= index < len(self._filtered_models):
            model = self._filtered_models[index]
            self._selected_model_id = model.id
            self.EndModal(wx.ID_OK)

    def _on_refresh(self, event):
        """Refresh the model list."""
        self._load_models()

    def _on_select(self, event):
        """Handle select button - close with OK."""
        if self._selected_model_id:
            self.EndModal(wx.ID_OK)

    def _load_models(self):
        """Load models from OpenRouter in a background thread."""
        self.status_label.SetLabel("Loading models...")
        self.model_list.Clear()
        self.select_btn.Enable(False)
        self._selected_model_id = None
        self.description_text.SetValue("")

        def do_load():
            """Fetch models in background thread."""
            from ...api.openrouter_models import OpenRouterModelsClient, OpenRouterModelsError

            try:
                client = OpenRouterModelsClient(api_key=self.api_key)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    models = loop.run_until_complete(client.get_text_models(force_refresh=True))
                finally:
                    loop.close()

                wx.CallAfter(self._on_models_loaded, models, None)

            except OpenRouterModelsError as e:
                logger.error(f"Failed to load models: {e}")
                wx.CallAfter(self._on_models_loaded, [], str(e))
            except Exception as e:
                logger.error(f"Unexpected error loading models: {e}")
                wx.CallAfter(self._on_models_loaded, [], str(e))

        thread = threading.Thread(target=do_load, daemon=True)
        thread.start()

    def _on_models_loaded(self, models: list, error: str | None):
        """
        Handle models loaded from API.

        Args:
            models: List of OpenRouterModel objects
            error: Error message if loading failed

        """
        if error:
            self.status_label.SetLabel(f"Error: {error}")
            return

        self._all_models = models
        self._update_provider_list()
        self._apply_filters()

    def _update_provider_list(self):
        """Update the provider dropdown with available providers."""
        # Determine which models to consider for provider list
        free_only = self.free_only_checkbox.GetValue()
        if free_only:
            # Only show providers that have free models
            models_for_providers = [m for m in self._all_models if m.is_free]
        else:
            models_for_providers = self._all_models

        # Extract unique providers from filtered models
        providers = sorted({model.provider for model in models_for_providers})
        self._providers = providers

        # Update dropdown, preserving selection if possible
        current_selection = self.provider_choice.GetStringSelection()
        self.provider_choice.Clear()
        self.provider_choice.Append("All Providers")
        for provider in providers:
            display_name = get_provider_display_name(provider)
            self.provider_choice.Append(display_name)

        # Restore selection or default to "All Providers"
        idx = self.provider_choice.FindString(current_selection)
        if idx != wx.NOT_FOUND:
            self.provider_choice.SetSelection(idx)
        else:
            self.provider_choice.SetSelection(0)

    def _get_selected_provider(self) -> str | None:
        """Get the currently selected provider filter, or None for all."""
        idx = self.provider_choice.GetSelection()
        if idx <= 0:  # "All Providers" or nothing selected
            return None
        # Map back to original provider name (index 0 is "All Providers")
        return self._providers[idx - 1] if idx - 1 < len(self._providers) else None

    def _apply_filters(self):
        """Apply search and filter criteria to the model list."""
        search_text = self.search_box.GetValue().lower().strip()
        free_only = self.free_only_checkbox.GetValue()
        selected_provider = self._get_selected_provider()

        self._filtered_models = []
        for model in self._all_models:
            # Apply free filter
            if free_only and not model.is_free:
                continue

            # Apply provider filter
            if selected_provider and model.provider != selected_provider:
                continue

            # Apply search filter
            if search_text and (
                search_text not in model.name.lower()
                and search_text not in model.id.lower()
                and search_text not in (model.description or "").lower()
            ):
                continue

            self._filtered_models.append(model)

        self._populate_list()

    def _populate_list(self):
        """Populate the list with filtered models."""
        self.model_list.Clear()

        for model in self._filtered_models:
            # Format as accessible string with all relevant info
            if model.is_free:
                pricing = "Free"
            else:
                # Pricing is per 1M tokens, show per 1K for readability
                prompt_cost = model.pricing_prompt / 1000
                pricing = f"${prompt_cost:.6f} per 1K tokens"

            # Create descriptive item string for screen readers
            item = f"{model.display_name} - Context: {model.context_display} - {pricing}"
            self.model_list.Append(item)

        # Update status
        total = len(self._all_models)
        showing = len(self._filtered_models)
        if showing == total:
            self.status_label.SetLabel(f"{total} models available")
        else:
            self.status_label.SetLabel(f"Showing {showing} of {total} models")

        # Clear selection
        self._selected_model_id = None
        self.select_btn.Enable(False)
        self.description_text.SetValue("")

    def get_selected_model_id(self) -> str | None:
        """
        Get the selected model ID.

        Returns:
            The selected model ID, or None if no selection

        """
        return self._selected_model_id

    def get_selected_model(self):
        """
        Get the selected model object.

        Returns:
            The selected OpenRouterModel, or None if no selection

        """
        if not self._selected_model_id:
            return None

        for model in self._filtered_models:
            if model.id == self._selected_model_id:
                return model
        return None


def show_model_browser_dialog(parent, api_key: str | None = None) -> str | None:
    """
    Show the model browser dialog and return the selected model ID.

    Args:
        parent: Parent window
        api_key: Optional OpenRouter API key

    Returns:
        The selected model ID, or None if cancelled

    """
    try:
        dlg = ModelBrowserDialog(parent, api_key=api_key)
        result = dlg.ShowModal()
        selected_id = dlg.get_selected_model_id() if result == wx.ID_OK else None
        dlg.Destroy()
        return selected_id

    except Exception as e:
        logger.error(f"Failed to show model browser dialog: {e}")
        wx.MessageBox(
            f"Failed to open model browser: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return None
