"""Model browser dialog for selecting OpenRouter AI models."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from ...api.openrouter_models import OpenRouterModel

logger = logging.getLogger(__name__)


class ModelBrowserDialog(wx.Dialog):
    """Dialog for browsing and selecting OpenRouter AI models."""

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
            size=(700, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.api_key = api_key
        self._all_models: list[OpenRouterModel] = []
        self._filtered_models: list[OpenRouterModel] = []
        self._selected_model_id: str | None = None

        self._create_ui()
        self._setup_accessibility()
        self._load_models()

    def _create_ui(self):
        """Create the dialog UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Search and filter row
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Search box
        filter_sizer.Add(
            wx.StaticText(self, label="Search:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self._search_box = wx.TextCtrl(self, size=(200, -1))
        self._search_box.Bind(wx.EVT_TEXT, self._on_search_changed)
        filter_sizer.Add(self._search_box, 1, wx.RIGHT, 10)

        # Free only checkbox
        self._free_only_checkbox = wx.CheckBox(self, label="Free models only")
        self._free_only_checkbox.Bind(wx.EVT_CHECKBOX, self._on_filter_changed)
        filter_sizer.Add(self._free_only_checkbox, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Status label
        self._status_label = wx.StaticText(self, label="Loading models...")
        main_sizer.Add(self._status_label, 0, wx.LEFT | wx.BOTTOM, 10)

        # Model list
        self._model_list = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self._model_list.InsertColumn(0, "Model Name", width=280)
        self._model_list.InsertColumn(1, "Context", width=80)
        self._model_list.InsertColumn(2, "Pricing", width=120)
        self._model_list.InsertColumn(3, "Type", width=60)
        self._model_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_model_selected)
        self._model_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_model_activated)
        main_sizer.Add(self._model_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Model description
        main_sizer.Add(
            wx.StaticText(self, label="Description:"),
            0,
            wx.LEFT | wx.TOP,
            10,
        )
        self._description_text = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            size=(-1, 60),
        )
        main_sizer.Add(self._description_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        refresh_btn = wx.Button(self, label="Refresh")
        refresh_btn.Bind(wx.EVT_BUTTON, self._on_refresh)
        button_sizer.Add(refresh_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)

        self._ok_btn = wx.Button(self, wx.ID_OK, "Select")
        self._ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)
        self._ok_btn.Enable(False)
        button_sizer.Add(self._ok_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)

    def _setup_accessibility(self):
        """Set up accessibility labels."""
        self._search_box.SetName("Search models")
        self._model_list.SetName("Available AI models")
        self._description_text.SetName("Model description")

    def _load_models(self):
        """Load models from OpenRouter in a background thread."""
        self._status_label.SetLabel("Loading models...")
        self._model_list.DeleteAllItems()
        self._ok_btn.Enable(False)

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

    def _on_models_loaded(self, models: list, error: str | None):
        """
        Handle models loaded from API.

        Args:
            models: List of OpenRouterModel objects
            error: Error message if loading failed

        """
        if error:
            self._status_label.SetLabel(f"Error: {error}")
            return

        self._all_models = models
        self._apply_filters()

    def _apply_filters(self):
        """Apply search and filter criteria to the model list."""
        search_text = self._search_box.GetValue().lower().strip()
        free_only = self._free_only_checkbox.GetValue()

        self._filtered_models = []
        for model in self._all_models:
            # Apply free filter
            if free_only and not model.is_free:
                continue

            # Apply search filter
            if search_text and (
                search_text not in model.name.lower()
                and search_text not in model.id.lower()
                and search_text not in model.description.lower()
            ):
                continue

            self._filtered_models.append(model)

        self._populate_list()

    def _populate_list(self):
        """Populate the list control with filtered models."""
        self._model_list.DeleteAllItems()

        for i, model in enumerate(self._filtered_models):
            # Format pricing
            if model.is_free:
                pricing = "Free"
            else:
                # Pricing is per 1M tokens, show per 1K for readability
                prompt_cost = model.pricing_prompt / 1000  # Convert to per 1K
                pricing = f"${prompt_cost:.6f}/1K tokens"

            # Model type
            model_type = "Free" if model.is_free else "Paid"

            index = self._model_list.InsertItem(i, model.display_name)
            self._model_list.SetItem(index, 1, model.context_display)
            self._model_list.SetItem(index, 2, pricing)
            self._model_list.SetItem(index, 3, model_type)

        # Update status
        total = len(self._all_models)
        showing = len(self._filtered_models)
        if showing == total:
            self._status_label.SetLabel(f"{total} models available")
        else:
            self._status_label.SetLabel(f"Showing {showing} of {total} models")

        # Clear selection
        self._selected_model_id = None
        self._ok_btn.Enable(False)
        self._description_text.SetValue("")

    def _on_search_changed(self, event):
        """Handle search text changed."""
        self._apply_filters()

    def _on_filter_changed(self, event):
        """Handle filter checkbox changed."""
        self._apply_filters()

    def _on_model_selected(self, event):
        """Handle model selection in list."""
        index = event.GetIndex()
        if 0 <= index < len(self._filtered_models):
            model = self._filtered_models[index]
            self._selected_model_id = model.id
            self._ok_btn.Enable(True)

            # Show description
            desc = model.description or "No description available."
            self._description_text.SetValue(desc)

    def _on_model_activated(self, event):
        """Handle double-click on model (select and close)."""
        index = event.GetIndex()
        if 0 <= index < len(self._filtered_models):
            model = self._filtered_models[index]
            self._selected_model_id = model.id
            self.EndModal(wx.ID_OK)

    def _on_refresh(self, event):
        """Refresh the model list."""
        self._load_models()

    def _on_ok(self, event):
        """Handle OK button."""
        if self._selected_model_id:
            self.EndModal(wx.ID_OK)

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

        dlg = ModelBrowserDialog(parent_ctrl, api_key=api_key)
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
