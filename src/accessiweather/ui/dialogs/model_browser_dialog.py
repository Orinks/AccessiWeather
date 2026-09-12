"""Model browser dialog for selecting OpenRouter or Venice AI models."""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import suppress
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from ...api.openrouter_models import OpenRouterModel
    from ...api.venice_models import VeniceModel

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
    Dialog for browsing and selecting OpenRouter or Venice AI models.

    Provides search, filtering by free models, and displays model details.
    """

    def __init__(self, parent, api_key: str | None = None, provider: str = "openrouter"):
        """
        Initialize the model browser dialog.

        Args:
            parent: Parent window
            api_key: Optional key for the selected catalog service.
            provider: Catalog service, openrouter or venice.

        """
        super().__init__(
            parent,
            title="Browse Venice Models" if provider == "venice" else "Browse AI Models",
            size=(650, 550),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.api_key = api_key
        self.provider = provider
        self._closed = False
        self._load_generation = 0
        from ...screen_reader import ScreenReaderAnnouncer

        self._announcer = ScreenReaderAnnouncer()
        self._all_models: list[OpenRouterModel | VeniceModel] = []
        self._filtered_models: list[OpenRouterModel | VeniceModel] = []
        self._selected_model_id: str | None = None
        self._providers: list[str] = []

        self._create_ui()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
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
        if self.provider == "venice":
            self.free_only_checkbox.Hide()
            filter_sizer.Add(wx.StaticText(self, label="Price:"), 0, wx.ALIGN_CENTER_VERTICAL)
            self.price_choice = wx.Choice(self, choices=["All prices", "Free", "Paid"])
            self.price_choice.SetSelection(0)
            self.price_choice.SetName("Model price filter")
            self.price_choice.Bind(wx.EVT_CHOICE, self._on_filter_changed)
            filter_sizer.Add(self.price_choice, 0, wx.RIGHT, 10)
            self.function_checkbox = wx.CheckBox(self, label="Weather assistant compatible")
            self.function_checkbox.SetName("Weather assistant compatible models only")
            self.function_checkbox.Bind(wx.EVT_CHECKBOX, self._on_filter_changed)
            filter_sizer.Add(self.function_checkbox, 0, wx.RIGHT, 10)

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
        if self.provider == "venice":
            self.balance_label = wx.StaticText(self, label="Checking Venice account credit status…")
            self.balance_label.SetName("Venice account credit status")
            main_sizer.Add(self.balance_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Model list
        list_label = wx.StaticText(self, label="Available models:")
        main_sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.model_list = wx.ListBox(self, style=wx.LB_SINGLE, size=(-1, 200))
        self.model_list.Bind(wx.EVT_LISTBOX, self._on_model_selected)
        self.model_list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_model_double_click)
        self.model_list.Bind(wx.EVT_CHAR_HOOK, self._on_list_key)
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

        self.cancel_btn = wx.Button(self, wx.ID_CANCEL, "&Cancel")
        self.cancel_btn.Bind(wx.EVT_BUTTON, self._on_close)
        btn_sizer.Add(self.cancel_btn, 0)

        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)
        for control, name in (
            (self.search_box, "Search models"),
            (self.provider_choice, "Model provider filter"),
            (self.model_list, "Available models"),
            (self.description_text, "Model description"),
        ):
            control.SetName(name)

        if hasattr(self, "search_box"):
            self.search_box.SetFocus()

    def _on_search_changed(self, event):
        """Handle search text changed."""
        self._apply_filters()

    def _on_filter_changed(self, event):
        """Handle filter checkbox or provider selection changed."""
        # If the free-only checkbox changed, update the provider list
        if event.GetEventObject() == self.free_only_checkbox or self.provider == "venice":
            self._update_provider_list()
        self._apply_filters()
        self._announcer.announce(self.status_label.GetLabel())

    def _on_model_selected(self, event):
        """Handle model selection in list."""
        index = self.model_list.GetSelection()
        if index != wx.NOT_FOUND and 0 <= index < len(self._filtered_models):
            model = self._filtered_models[index]
            offline = getattr(model, "offline", False)
            self._selected_model_id = None if offline else model.id
            self.select_btn.Enable(not offline)

            # Show description
            desc = model.description or "No description available."
            if self.provider == "venice":
                if offline:
                    desc += "\nThis model is offline and unavailable for selection."
                desc += "\n" + self._model_pricing(model)
                desc += (
                    "\nSupports weather assistant function calling."
                    if model.supports_function_calling
                    else "\nDoes not support weather assistant function calling; use for explanations only."
                )
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
            if getattr(model, "offline", False):
                self._on_model_selected(event)
                self._announcer.announce("This model is offline and unavailable for selection.")
                return
            self._selected_model_id = model.id
            self._shutdown()
            self.EndModal(wx.ID_OK)

    def _on_list_key(self, event: wx.KeyEvent) -> None:
        """Handle key events on the model list — Enter selects the highlighted item."""
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_select(event)
        else:
            event.Skip()

    def _on_refresh(self, event):
        """Refresh the model list."""
        self._load_models()

    def _on_select(self, event):
        """Handle select button - close with OK."""
        if self._selected_model_id:
            self._shutdown()
            self.EndModal(wx.ID_OK)
        else:
            index = self.model_list.GetSelection()
            if 0 <= index < len(self._filtered_models) and getattr(
                self._filtered_models[index], "offline", False
            ):
                self._announcer.announce("This model is offline and unavailable for selection.")

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        """Handle keyboard shortcuts for the dialog."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._on_close(event)
            return
        event.Skip()

    def _on_close(self, event) -> None:
        """Close the dialog as cancelled."""
        self._shutdown()
        self.EndModal(wx.ID_CANCEL)

    def _shutdown(self):
        """Stop callbacks and release the announcement backend once."""
        if not self._closed:
            self._closed = True
            self._announcer.shutdown()

    def _load_models(self):
        """Load the selected provider's catalog without stale callbacks changing the UI."""
        self._load_generation += 1
        generation = self._load_generation
        self.status_label.SetLabel("Loading models...")
        self._all_models = []
        self._filtered_models = []
        self.model_list.Clear()
        self.select_btn.Enable(False)
        self._selected_model_id = None
        self.description_text.SetValue("")
        self.refresh_btn.Enable(False)
        self.search_box.SetFocus()
        self._announcer.announce("Loading models…")
        if self.provider == "venice":
            self.balance_label.SetLabel(
                "Checking Venice account credit status…"
                if self.api_key
                else "Add a Venice API key to check account credits. The public model catalog is available without a key."
            )

        def do_load():
            """Fetch models in background thread."""
            try:
                if self.provider == "venice":
                    from ...api.venice_models import VeniceModelsClient

                    client = VeniceModelsClient(api_key=self.api_key)
                else:
                    from ...api.openrouter_models import OpenRouterModelsClient

                    client = OpenRouterModelsClient(api_key=self.api_key)

                async def fetch():
                    models = await client.get_text_models(force_refresh=True)
                    balance = None
                    if self.provider == "venice":
                        with suppress(Exception):
                            balance = await client.fetch_balance()
                    return models, balance

                models, balance = asyncio.run(fetch())
                wx.CallAfter(self._finish_load, generation, models, None, balance)
            except Exception as error:
                message = "Unable to load models. Check your connection and API key, then refresh."
                if self.provider == "venice":
                    from ...api.venice_models import VeniceModelsError

                    if isinstance(error, VeniceModelsError):
                        message = str(error)
                wx.CallAfter(
                    self._finish_load,
                    generation,
                    [],
                    message,
                    None,
                )

        thread = threading.Thread(target=do_load, daemon=True)
        thread.start()

    def _finish_load(self, generation, models, error, balance):
        """Ignore completion after closure, destruction, or a newer refresh."""
        if self._closed or generation != self._load_generation or not self or self.IsBeingDeleted():
            return
        self.refresh_btn.Enable(True)
        if self.provider == "venice":
            self.balance_label.SetLabel(
                self._balance_status(balance)
                if self.api_key
                else "Add a Venice API key to check account credits. The public model catalog is available without a key."
            )
            self.balance_label.Wrap(610)
            self.Layout()
        self._on_models_loaded(models, error)
        announcement = self.status_label.GetLabel()
        if self.provider == "venice":
            announcement += ". " + self.balance_label.GetLabel()
        self._announcer.announce(announcement)

    @staticmethod
    def _balance_status(balance):
        """Describe account permission without implying a model is affordable or free."""
        amounts = []
        if balance is not None:
            if balance.usd is not None:
                amounts.append(f"USD: ${balance.usd:g}")
            if balance.diem is not None:
                amounts.append(f"DIEM: {balance.diem:g}")
            if balance.consumption_currency:
                amounts.append(f"Consumption currency: {balance.consumption_currency}")
        prefix = "; ".join(amounts) + ". " if amounts else ""
        if balance is None or balance.can_consume is None:
            return (
                prefix
                + "Credit status unknown. Paid models remain selectable; check your Venice API account before use."
            )
        if not balance.can_consume:
            if balance.usd == 0 and balance.diem == 0:
                return (
                    prefix
                    + "No API credits available. Paid models remain selectable but need credits before use."
                )
            return (
                prefix
                + "Account cannot currently consume API credits. Paid models remain selectable but require usable credits before use."
            )
        return (
            prefix
            + "Account can consume API credits. Paid model charges still apply; this does not guarantee enough credit for a request."
        )

    def _matches_price_and_capability(self, model):
        """Filter only explicitly known pricing and capability metadata."""
        if self.provider != "venice":
            return not self.free_only_checkbox.GetValue() or model.is_free
        price = self.price_choice.GetSelection()
        if price == 1 and not model.is_free:
            return False
        if price == 2 and not (
            (model.pricing_prompt is not None and model.pricing_prompt > 0)
            or (model.pricing_completion is not None and model.pricing_completion > 0)
        ):
            return False
        return not self.function_checkbox.GetValue() or model.supports_function_calling

    @staticmethod
    def _model_pricing(model):
        """Show both directions of token pricing with unknown values explicit."""
        if model.is_free:
            return "Free"

        def price(value):
            return "unknown" if value is None else f"${value:g}"

        return f"Input: {price(model.pricing_prompt)}; output: {price(model.pricing_completion)} per million tokens"

    def _on_models_loaded(self, models: list, error: str | None):
        """
        Handle models loaded from API.

        Args:
            models: List of models from the selected catalog service.
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
        models_for_providers = [
            m for m in self._all_models if self._matches_price_and_capability(m)
        ]

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
        selected_provider = self._get_selected_provider()

        self._filtered_models = []
        for model in self._all_models:
            # Apply free filter
            if not self._matches_price_and_capability(model):
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
            if self.provider == "venice":
                pricing = self._model_pricing(model)
            elif model.is_free:
                pricing = "Free"
            else:
                # Pricing is per 1M tokens, show per 1K for readability
                prompt_cost = model.pricing_prompt / 1000
                pricing = f"${prompt_cost:.6f} per 1K tokens"

            # Create descriptive item string for screen readers
            item = f"{model.display_name} - Context: {model.context_display} - {pricing}"
            if self.provider == "venice":
                item += (
                    " - Weather assistant compatible"
                    if model.supports_function_calling
                    else " - Explanations only"
                )
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
            The selected OpenRouterModel or VeniceModel, or None if no selection

        """
        if not self._selected_model_id:
            return None

        for model in self._filtered_models:
            if model.id == self._selected_model_id:
                return model
        return None


def show_model_browser_dialog(
    parent, api_key: str | None = None, provider: str = "openrouter"
) -> str | None:
    """
    Show the model browser dialog and return the selected model ID.

    Args:
        parent: Parent window
        api_key: Optional key for the selected catalog service.
        provider: Catalog service, openrouter or venice.

    Returns:
        The selected model ID, or None if cancelled

    """
    dlg = None
    try:
        dlg = ModelBrowserDialog(parent, api_key=api_key, provider=provider)
        result = dlg.ShowModal()
        return dlg.get_selected_model_id() if result == wx.ID_OK else None

    except Exception:
        logger.error("Failed to show model browser dialog")
        wx.MessageBox(
            "Failed to open model browser. Please try again.",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return None
    finally:
        if dlg is not None:
            dlg._shutdown()
            dlg.Destroy()
