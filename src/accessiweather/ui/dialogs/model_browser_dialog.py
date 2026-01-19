"""Model browser dialog for selecting OpenRouter AI models using gui_builder."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    from ...api.openrouter_models import OpenRouterModel

logger = logging.getLogger(__name__)


class ModelBrowserDialog(forms.Dialog):
    """
    Dialog for browsing and selecting OpenRouter AI models.

    Uses gui_builder for accessible, screen-reader-friendly UI.
    """

    # Search section
    search_label = fields.StaticText(label="Search models:")
    search_box = fields.Text(label="Search models by name or description")

    # Filter checkbox
    free_only_checkbox = fields.CheckBox(label="Show free models only")

    # Status display
    status_label = fields.StaticText(label="Loading models...")

    # Model list
    model_list_label = fields.StaticText(label="Available models:")
    model_list = fields.ListBox(label="Select an AI model")

    # Description display
    description_label = fields.StaticText(label="Model description:")
    description_text = fields.Text(
        label="Selected model description",
        multiline=True,
        readonly=True,
    )

    # Buttons
    refresh_button = fields.Button(label="&Refresh")
    select_button = fields.Button(label="&Select")
    cancel_button = fields.Button(label="&Cancel")

    def __init__(self, api_key: str | None = None, **kwargs):
        """
        Initialize the model browser dialog.

        Args:
            api_key: Optional OpenRouter API key
            **kwargs: Additional keyword arguments passed to Dialog

        """
        self.api_key = api_key
        self._all_models: list[OpenRouterModel] = []
        self._filtered_models: list[OpenRouterModel] = []
        self._selected_model_id: str | None = None

        kwargs.setdefault("title", "Browse AI Models")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and set up post-render components."""
        super().render(**kwargs)
        self._setup_accessibility()
        self._setup_initial_state()
        self._load_models()

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels for screen readers."""
        self.search_box.set_accessible_label("Search for AI models by name or description")
        self.model_list.set_accessible_label("Available AI models list")
        self.description_text.set_accessible_label("Description of selected model")

    def _setup_initial_state(self) -> None:
        """Set up initial button states."""
        self.select_button.disable()

    # Event handlers using gui_builder decorators
    @search_box.add_callback
    def on_search_changed(self):
        """Handle search text changed."""
        self._apply_filters()

    @free_only_checkbox.add_callback
    def on_filter_changed(self):
        """Handle filter checkbox changed."""
        self._apply_filters()

    @model_list.add_callback
    def on_model_selected(self):
        """Handle model selection in list."""
        index = self.model_list.get_index()
        if index is not None and 0 <= index < len(self._filtered_models):
            model = self._filtered_models[index]
            self._selected_model_id = model.id
            self.select_button.enable()

            # Show description
            desc = model.description or "No description available."
            self.description_text.set_value(desc)
        else:
            self._selected_model_id = None
            self.select_button.disable()
            self.description_text.set_value("")

    @refresh_button.add_callback
    def on_refresh(self):
        """Refresh the model list."""
        self._load_models()

    @select_button.add_callback
    def on_select(self):
        """Handle select button - close with OK."""
        if self._selected_model_id:
            self.widget.control.EndModal(wx.ID_OK)

    @cancel_button.add_callback
    def on_cancel(self):
        """Handle cancel button."""
        self.widget.control.EndModal(wx.ID_CANCEL)

    def _load_models(self) -> None:
        """Load models from OpenRouter in a background thread."""
        self.status_label.set_label("Loading models...")
        self.model_list.set_items([])
        self.select_button.disable()
        self._selected_model_id = None

        def do_load():
            """Fetch models in background thread."""
            import asyncio

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

    def _on_models_loaded(self, models: list, error: str | None) -> None:
        """
        Handle models loaded from API.

        Args:
            models: List of OpenRouterModel objects
            error: Error message if loading failed

        """
        if error:
            self.status_label.set_label(f"Error: {error}")
            return

        self._all_models = models
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply search and filter criteria to the model list."""
        search_text = self.search_box.get_value().lower().strip()
        free_only = self.free_only_checkbox.get_value()

        self._filtered_models = []
        for model in self._all_models:
            # Apply free filter
            if free_only and not model.is_free:
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

    def _populate_list(self) -> None:
        """Populate the list with filtered models."""
        items = []
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
            items.append(item)

        self.model_list.set_items(items)

        # Update status
        total = len(self._all_models)
        showing = len(self._filtered_models)
        if showing == total:
            self.status_label.set_label(f"{total} models available")
        else:
            self.status_label.set_label(f"Showing {showing} of {total} models")

        # Clear selection
        self._selected_model_id = None
        self.select_button.disable()
        self.description_text.set_value("")

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
        # Get the underlying wx control if parent is a gui_builder widget
        parent_ctrl = getattr(parent, "control", parent)

        # Create and render the dialog
        dlg = ModelBrowserDialog(api_key=api_key, parent=parent_ctrl)
        dlg.render()

        # Show modal and get result
        result = dlg.widget.control.ShowModal()
        selected_id = dlg.get_selected_model_id() if result == wx.ID_OK else None

        # Destroy the dialog
        dlg.widget.control.Destroy()

        return selected_id

    except Exception as e:
        logger.error(f"Failed to show model browser dialog: {e}")
        wx.MessageBox(
            f"Failed to open model browser: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return None
