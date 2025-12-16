"""
Model Selection Dialog for OpenRouter AI models.

This dialog allows users to browse, search, and select AI models
from OpenRouter, with filtering for free vs paid models.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

if TYPE_CHECKING:
    from accessiweather.api.openrouter_models import OpenRouterModel

logger = logging.getLogger(__name__)

# Popular/recommended models to show at top (in order of preference)
RECOMMENDED_MODELS = [
    # Free models
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-235b-a22b:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "deepseek/deepseek-chat-v3-0324:free",
    # Paid auto-router
    "openrouter/auto",
    # Popular paid models
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "google/gemini-2.0-flash-001",
    # Popular unmoderated models
    "x-ai/grok-3-fast",
    "x-ai/grok-3",
    "x-ai/grok-2-1212",
    "cognitivecomputations/dolphin3.0-r1-mistral-24b:free",
    "cognitivecomputations/dolphin3.0-mistral-24b:free",
]

# Known providers for filtering
PROVIDERS = [
    "All Providers",
    "Meta (Llama)",
    "Google (Gemini/Gemma)",
    "OpenAI (GPT)",
    "Anthropic (Claude)",
    "Mistral",
    "DeepSeek",
    "Qwen",
    "Other",
]

PROVIDER_PREFIXES = {
    "Meta (Llama)": ["meta-llama/", "llama"],
    "Google (Gemini/Gemma)": ["google/", "gemini", "gemma"],
    "OpenAI (GPT)": ["openai/", "gpt-"],
    "Anthropic (Claude)": ["anthropic/", "claude"],
    "Mistral": ["mistralai/", "mistral"],
    "DeepSeek": ["deepseek/"],
    "Qwen": ["qwen/"],
}


class ModelSelectionDialog:
    """Dialog for selecting an OpenRouter AI model."""

    def __init__(
        self,
        app: toga.App,
        current_model: str,
        free_only: bool = True,
        on_model_selected: Callable[[str], None] | None = None,
    ):
        """
        Initialize the model selection dialog.

        Args:
            app: The Toga application instance
            current_model: Currently selected model ID
            free_only: If True, only show free models initially
            on_model_selected: Callback when a model is selected

        """
        self.app = app
        self.current_model = current_model
        self.free_only = free_only
        self.on_model_selected = on_model_selected
        self.models: list[OpenRouterModel] = []
        self.filtered_models: list[OpenRouterModel] = []
        self.selected_model: OpenRouterModel | None = None
        self.window: toga.Window | None = None
        self.selected_provider = "All Providers"
        self.unmoderated_only = False

    def _create_ui(self) -> toga.Box:
        """Create the dialog UI."""
        main_box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        # Header
        header_label = toga.Label(
            "Select AI Model",
            style=Pack(margin_bottom=5, font_weight="bold", font_size=14),
        )
        header_label.aria_label = "Select AI Model dialog"
        main_box.add(header_label)

        # Help text
        help_label = toga.Label(
            "Browse available models from OpenRouter. Recommended models appear first.",
            style=Pack(margin_bottom=10, font_size=10),
        )
        help_label.aria_label = "Help text"
        main_box.add(help_label)

        # Filter controls row
        filter_row = toga.Box(style=Pack(direction=ROW, margin_bottom=10))

        # Free/All toggle
        self.free_only_switch = toga.Switch(
            "Free models only",
            value=self.free_only,
            on_change=self._on_filter_changed,
            style=Pack(margin_right=20),
        )
        self.free_only_switch.aria_label = "Free models only filter"
        self.free_only_switch.aria_description = (
            "When enabled, only shows free models that won't charge your account"
        )
        filter_row.add(self.free_only_switch)

        # Provider filter
        provider_label = toga.Label("Provider:", style=Pack(margin_right=5, padding_top=5))
        filter_row.add(provider_label)

        self.provider_selection = toga.Selection(
            items=PROVIDERS,
            on_change=self._on_provider_changed,
            style=Pack(width=180),
        )
        self.provider_selection.aria_label = "Filter by provider"
        self.provider_selection.aria_description = (
            "Filter models by provider like Meta, Google, OpenAI, etc."
        )
        filter_row.add(self.provider_selection)

        main_box.add(filter_row)

        # Second filter row for unmoderated toggle
        filter_row2 = toga.Box(style=Pack(direction=ROW, margin_bottom=10))

        # Unmoderated/uncensored toggle
        self.unmoderated_switch = toga.Switch(
            "Unmoderated only",
            value=self.unmoderated_only,
            on_change=self._on_unmoderated_changed,
            style=Pack(margin_right=20),
        )
        self.unmoderated_switch.aria_label = "Unmoderated models only filter"
        self.unmoderated_switch.aria_description = (
            "When enabled, only shows models without content moderation (uncensored). "
            "Examples include Grok, some Llama variants, and Dolphin models."
        )
        filter_row2.add(self.unmoderated_switch)

        main_box.add(filter_row2)

        # Search box
        search_row = toga.Box(style=Pack(direction=ROW, margin_bottom=10))

        search_label = toga.Label("Search:", style=Pack(margin_right=5, padding_top=5))
        search_row.add(search_label)

        self.search_input = toga.TextInput(
            placeholder="Filter by name or description...",
            style=Pack(flex=1),
            on_change=self._on_search_changed,
        )
        self.search_input.aria_label = "Search models"
        self.search_input.aria_description = "Type to filter models by name or description"
        search_row.add(self.search_input)

        main_box.add(search_row)

        # Model list
        self.model_table = toga.Table(
            headings=["Name", "Context", "Cost/1M tokens"],
            accessors=["display_name", "context_display", "cost_display"],
            style=Pack(flex=1, height=300),
            on_select=self._on_model_select,
        )
        self.model_table.aria_label = "Available AI models"
        self.model_table.aria_description = (
            "List of available AI models. Select one to use for weather explanations."
        )
        main_box.add(self.model_table)

        # Model details
        details_box = toga.Box(style=Pack(direction=COLUMN, margin_top=10, margin_bottom=10))

        self.model_name_label = toga.Label(
            "Select a model to see details",
            style=Pack(font_weight="bold", margin_bottom=5),
        )
        self.model_name_label.aria_label = "Selected model name"
        details_box.add(self.model_name_label)

        self.model_description_label = toga.Label(
            "",
            style=Pack(font_size=10, height=40),
        )
        self.model_description_label.aria_label = "Model description"
        self.model_description_label.aria_live = "polite"
        details_box.add(self.model_description_label)

        main_box.add(details_box)

        # Status label
        self.status_label = toga.Label(
            "Loading models...",
            style=Pack(margin_bottom=10, font_size=10),
        )
        self.status_label.aria_label = "Status"
        self.status_label.aria_live = "polite"
        main_box.add(self.status_label)

        # Button row
        button_row = toga.Box(style=Pack(direction=ROW, margin_top=10))

        self.refresh_button = toga.Button(
            "Refresh",
            on_press=self._on_refresh,
            style=Pack(margin_right=10, width=100),
        )
        self.refresh_button.aria_label = "Refresh model list"
        self.refresh_button.aria_description = "Fetch the latest models from OpenRouter"
        button_row.add(self.refresh_button)

        # Spacer
        button_row.add(toga.Box(style=Pack(flex=1)))

        self.cancel_button = toga.Button(
            "Cancel",
            on_press=self._on_cancel,
            style=Pack(margin_right=10, width=100),
        )
        self.cancel_button.aria_label = "Cancel"
        self.cancel_button.aria_description = "Close without selecting a model"
        button_row.add(self.cancel_button)

        self.select_button = toga.Button(
            "Select",
            on_press=self._on_select,
            style=Pack(width=100),
            enabled=False,
        )
        self.select_button.aria_label = "Select model"
        self.select_button.aria_description = "Use the selected model for AI explanations"
        button_row.add(self.select_button)

        main_box.add(button_row)

        return main_box

    async def show(self) -> None:
        """Show the model selection dialog."""
        content = self._create_ui()

        self.window = toga.Window(
            title="Select AI Model",
            size=(600, 500),
            resizable=True,
        )
        self.window.content = content

        # Ensure window is registered with app before showing
        if self.window not in self.app.windows:
            self.app.windows.add(self.window)

        self.window.show()

        # Load models
        await self._load_models()

        # Set focus to search input for better UX
        self._set_focus()

    def _set_focus(self) -> None:
        """Set focus to the search input field."""
        try:
            if hasattr(self.search_input, "focus"):
                self.search_input.focus()
        except Exception as e:
            logger.debug(f"Could not set focus to search input: {e}")

    def _on_filter_changed(self, widget: toga.Switch) -> None:
        """Handle free-only filter toggle."""
        self.free_only = widget.value
        self._apply_filters()

    def _on_provider_changed(self, widget: toga.Selection) -> None:
        """Handle provider filter change."""
        self.selected_provider = str(widget.value) if widget.value else "All Providers"
        self._apply_filters()

    def _on_search_changed(self, widget: toga.TextInput) -> None:
        """Handle search input change."""
        self._apply_filters()

    def _on_unmoderated_changed(self, widget: toga.Switch) -> None:
        """Handle unmoderated filter toggle."""
        self.unmoderated_only = widget.value
        self._apply_filters()

    def _matches_provider(self, model: OpenRouterModel) -> bool:
        """Check if model matches the selected provider filter."""
        if self.selected_provider == "All Providers":
            return True

        if self.selected_provider == "Other":
            # "Other" matches models that don't match any known provider
            model_id_lower = model.id.lower()
            for prefixes in PROVIDER_PREFIXES.values():
                for prefix in prefixes:
                    if prefix.lower() in model_id_lower:
                        return False
            return True

        # Check if model matches the selected provider's prefixes
        prefixes = PROVIDER_PREFIXES.get(self.selected_provider, [])
        model_id_lower = model.id.lower()
        return any(prefix.lower() in model_id_lower for prefix in prefixes)

    def _get_model_sort_key(self, model: OpenRouterModel) -> tuple[int, str]:
        """Get sort key for model - recommended models first, then alphabetical."""
        try:
            # Recommended models get low index (appear first)
            idx = RECOMMENDED_MODELS.index(model.id)
            return (0, f"{idx:03d}")
        except ValueError:
            # Non-recommended models sorted alphabetically after
            return (1, model.name.lower())

    def _apply_filters(self) -> None:
        """Apply current filters to the model list."""
        search_query = self.search_input.value.lower() if self.search_input.value else ""

        self.filtered_models = []
        for model in self.models:
            # Apply free filter
            if self.free_only and not model.is_free:
                continue

            # Apply provider filter
            if not self._matches_provider(model):
                continue

            # Apply unmoderated filter
            # is_moderated=False means no content moderation (uncensored)
            if self.unmoderated_only and model.is_moderated:
                continue

            # Apply search filter
            if search_query and (
                search_query not in model.name.lower()
                and search_query not in model.id.lower()
                and search_query not in model.description.lower()
            ):
                continue

            self.filtered_models.append(model)

        # Sort: recommended models first, then alphabetically
        self.filtered_models.sort(key=self._get_model_sort_key)

        self._update_table()

    def _update_table(self) -> None:
        """Update the table with filtered models."""
        # Create display data for table
        table_data = []
        for model in self.filtered_models:
            if model.is_free:
                cost_display = "Free"
            else:
                # Show cost per 1M tokens (prompt + completion average)
                avg_cost = (model.pricing_prompt + model.pricing_completion) / 2
                if avg_cost < 0.0001:
                    cost_display = f"${avg_cost:.2e}"  # Scientific notation for very small costs
                elif avg_cost < 0.01:
                    cost_display = f"${avg_cost:.6f}"  # 6 decimals for small costs
                else:
                    cost_display = f"${avg_cost:.2f}"

            table_data.append(
                {
                    "display_name": model.display_name,
                    "context_display": model.context_display,
                    "cost_display": cost_display,
                    "_model": model,
                }
            )

        self.model_table.data = table_data
        self.status_label.text = f"Showing {len(self.filtered_models)} models"

    def _on_model_select(self, widget: toga.Table) -> None:
        """Handle model selection in table."""
        if widget.selection:
            row = widget.selection
            # Find the model from filtered list by matching display name
            row_display_name = getattr(row, "display_name", None)
            for model in self.filtered_models:
                if model.display_name == row_display_name:
                    self.selected_model = model
                    break

            if self.selected_model:
                self.model_name_label.text = self.selected_model.name
                desc = self.selected_model.description
                if len(desc) > 200:
                    desc = desc[:197] + "..."
                self.model_description_label.text = desc
                self.select_button.enabled = True
        else:
            self.selected_model = None
            self.model_name_label.text = "Select a model to see details"
            self.model_description_label.text = ""
            self.select_button.enabled = False

    async def _load_models(self, force_refresh: bool = False) -> None:
        """Load models from OpenRouter API."""
        self.status_label.text = "Loading models..."
        self.refresh_button.enabled = False

        try:
            from accessiweather.api.openrouter_models import (
                OpenRouterModelsClient,
                OpenRouterModelsError,
            )

            client = OpenRouterModelsClient()
            self.models = await client.get_text_models(force_refresh=force_refresh)
            self._apply_filters()

            # Try to select current model if it exists
            if self.current_model:
                for i, model in enumerate(self.filtered_models):
                    if model.id == self.current_model:
                        # Note: Toga Table selection is read-only in some backends
                        # The user will need to manually select the model
                        logger.debug(f"Current model {self.current_model} found at index {i}")
                        break

        except OpenRouterModelsError as e:
            logger.error(f"Failed to load models: {e}")
            self.status_label.text = f"Error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error loading models: {e}")
            self.status_label.text = f"Error loading models: {e}"
        finally:
            self.refresh_button.enabled = True

    def _on_refresh(self, widget: toga.Button) -> None:
        """Handle refresh button press."""
        asyncio.create_task(self._load_models(force_refresh=True))

    def _on_cancel(self, widget: toga.Button) -> None:
        """Handle cancel button press."""
        if self.window:
            self.window.close()

    def _on_select(self, widget: toga.Button) -> None:
        """Handle select button press."""
        if self.selected_model and self.on_model_selected:
            self.on_model_selected(self.selected_model.id)

        if self.window:
            self.window.close()


async def show_model_selection_dialog(
    app: toga.App,
    current_model: str,
    free_only: bool = True,
    on_model_selected: Callable[[str], None] | None = None,
) -> None:
    """
    Show the model selection dialog.

    Args:
        app: The Toga application instance
        current_model: Currently selected model ID
        free_only: If True, only show free models initially
        on_model_selected: Callback when a model is selected

    """
    dialog = ModelSelectionDialog(
        app=app,
        current_model=current_model,
        free_only=free_only,
        on_model_selected=on_model_selected,
    )
    await dialog.show()
