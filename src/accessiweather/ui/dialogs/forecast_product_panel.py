"""
Reusable per-tab panel for the Forecast Products dialog.

Each :class:`ForecastProductPanel` renders one NWS text product type (AFD, HWO,
or SPS) with a shared shape: header, optional SPS-multi chooser, raw-product
TextCtrl, issuance timestamp StaticText, "Plain Language Summary" AI button
(hidden until clicked), and a retry button shown only in the fetch-failed
state.

The panel owns its own content-state machine — AFD/HWO have a single product,
SPS can have multiple. All empty/error states render inside the content area
because ``wx.Notebook`` doesn't support per-tab disable on Windows.

Accessibility note: screen readers announce adjacent ``wx.StaticText``, NOT
``SetName()`` or tooltips (project convention). Descriptive ``label=``
strings are used throughout.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Literal, cast

import wx

from .forecast_product_ai import (
    build_explainer,
    has_openrouter_key,
)
from .forecast_product_formatting import (
    EMPTY_COPY as _EMPTY_COPY,
    NO_CWA_COPY as _NO_CWA_COPY,
    PRODUCT_FULL_NAMES as _PRODUCT_FULL_NAMES,
    format_issuance as _format_issuance,
    format_sps_choice_entry as _format_sps_choice_entry,
)

if TYPE_CHECKING:
    from ...ai_explainer import AIExplainer
    from ...models import TextProduct

logger = logging.getLogger(__name__)

ProductType = Literal["AFD", "HWO", "SPS"]

ProductLoader = Callable[[], Awaitable["TextProduct | list[TextProduct] | None"]]
AvailabilityCallback = Callable[["ForecastProductPanel", bool], None]


class ForecastProductPanel(wx.Panel):
    """One tab's worth of content inside the Forecast Products dialog."""

    def __init__(
        self,
        parent: wx.Window,
        product_type: ProductType,
        product_loader: ProductLoader,
        ai_explainer: AIExplainer | None,
        cwa_office: str | None,
        location_name: str,
        app: object | None = None,
        availability_callback: AvailabilityCallback | None = None,
    ) -> None:
        """
        Build the panel widgets.

        Args:
            parent: Parent window (the ``wx.Notebook``).
            product_type: One of ``"AFD"``, ``"HWO"``, ``"SPS"``.
            product_loader: Zero-arg async callable that returns the fetched
                product(s). May raise ``TextProductFetchError``.
            ai_explainer: Optional explainer; when ``None`` the AI summary
                button stays disabled.
            cwa_office: CWA office code (e.g. ``"RAH"``). When ``None`` the
                panel shows a fallback message covering all three product
                types.
            location_name: Human-readable location name (used for AI prompts).
            app: Optional AccessiWeather app instance. When provided, async
                loaders dispatch via ``app.run_async`` (the background asyncio
                loop). Falls back to ``asyncio.ensure_future`` when absent.
            availability_callback: Optional callback invoked after load
                completes. ``False`` means the product fetch succeeded but
                returned no products; errors are reported as available so the
                dialog keeps the retry surface visible.

        """
        super().__init__(parent)
        self.product_type = product_type
        self._product_loader = product_loader
        self._ai_explainer = ai_explainer
        self._cwa_office = cwa_office
        self._location_name = location_name
        self._app = app
        self._availability_callback = availability_callback

        # State
        self._current_text: str | None = None
        # For SPS multi-product: the list of products currently available.
        self._sps_products: list[TextProduct] = []
        self._is_loading = False
        self._is_explaining = False

        self._create_widgets()
        self._bind_events()

        # Kick off initial load.
        self._trigger_load()

    # ------------------------------------------------------------------
    # Widget creation
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        """Construct the per-tab widget tree."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        full_name = _PRODUCT_FULL_NAMES[self.product_type]
        self.header_label = wx.StaticText(self, label=full_name)
        main_sizer.Add(self.header_label, 0, wx.ALL | wx.EXPAND, 8)

        # SPS multi-product chooser — ONLY created on the SPS tab. Creating it
        # on AFD/HWO and hiding it via Show(False) still leaks the label to
        # screen readers, which was reported as misleading. AFD and HWO never
        # have multiple concurrent products, so the chooser is SPS-only by
        # design.
        self.sps_choice_label: wx.StaticText | None = None
        self.sps_choice: wx.Choice | None = None
        if self.product_type == "SPS":
            self.sps_choice_label = wx.StaticText(self, label="Recent Special Weather Statements:")
            main_sizer.Add(self.sps_choice_label, 0, wx.LEFT | wx.RIGHT, 8)
            self.sps_choice = wx.Choice(self)
            main_sizer.Add(self.sps_choice, 0, wx.ALL | wx.EXPAND, 8)
            # Hidden until we actually have >1 SPS to switch between.
            main_sizer.Show(self.sps_choice_label, False)
            main_sizer.Show(self.sps_choice, False)

        # Raw product text — the primary content surface.
        self.product_textctrl = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL,
            value="Loading...",
        )
        main_sizer.Add(self.product_textctrl, 1, wx.ALL | wx.EXPAND, 8)

        # Issuance StaticText — adjacent StaticText is what screen readers pick up.
        self.issuance_label = wx.StaticText(self, label="")
        main_sizer.Add(self.issuance_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # AI summary header + display — hidden until user clicks "Plain Language Summary".
        self.ai_summary_header = wx.StaticText(self, label="Plain Language Summary:")
        main_sizer.Add(self.ai_summary_header, 0, wx.LEFT | wx.RIGHT, 8)
        self.ai_summary_display = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        main_sizer.Add(self.ai_summary_display, 0, wx.ALL | wx.EXPAND, 8)
        main_sizer.Show(self.ai_summary_header, False)
        main_sizer.Show(self.ai_summary_display, False)

        # Model information (shown alongside the AI summary). Mirrors
        # DiscussionDialog's Model / Tokens / Cost / Cached block so users
        # see the same provenance info they already expect from AFD.
        self.model_info_label = wx.StaticText(self, label="Model Information:")
        main_sizer.Add(self.model_info_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self.model_info = wx.TextCtrl(
            self,
            value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=wx.Size(-1, 80),
        )
        main_sizer.Add(self.model_info, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 8)
        main_sizer.Show(self.model_info_label, False)
        main_sizer.Show(self.model_info, False)

        # Buttons row
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.explain_button = wx.Button(self, label="Plain Language Summary")
        self.regenerate_button = wx.Button(self, label="Regenerate Summary")
        self.retry_button = wx.Button(self, label="Try again")
        button_sizer.Add(self.explain_button, 0, wx.RIGHT, 5)
        button_sizer.Add(self.regenerate_button, 0, wx.RIGHT, 5)
        button_sizer.Add(self.retry_button, 0)
        main_sizer.Add(button_sizer, 0, wx.ALL, 8)

        # Regenerate + retry hidden initially.
        self.regenerate_button.Hide()
        self.retry_button.Hide()
        # Explain button disabled until we have loaded text + explainer is available.
        self.explain_button.Disable()

        self.SetSizer(main_sizer)
        self._main_sizer = main_sizer

    def _bind_events(self) -> None:
        """Wire up button and SPS-choice events."""
        self.explain_button.Bind(wx.EVT_BUTTON, self._on_explain)
        self.regenerate_button.Bind(wx.EVT_BUTTON, self._on_regenerate)
        self.retry_button.Bind(wx.EVT_BUTTON, self._on_retry)
        if self.sps_choice is not None:
            self.sps_choice.Bind(wx.EVT_CHOICE, self._on_sps_choice_changed)

    # ------------------------------------------------------------------
    # Layout helpers (mirror DiscussionDialog's AI visibility design)
    # ------------------------------------------------------------------
    def _layout(self) -> None:
        sizer = self.GetSizer()
        if sizer:
            sizer.Layout()

    def _show_ai_summary_section(self) -> None:
        self._main_sizer.Show(self.ai_summary_header, True)
        self._main_sizer.Show(self.ai_summary_display, True)
        self._layout()

    def _hide_ai_summary_section(self) -> None:
        self._main_sizer.Show(self.ai_summary_header, False)
        self._main_sizer.Show(self.ai_summary_display, False)
        self._hide_model_info()
        self._layout()

    def _show_model_info(self) -> None:
        self._main_sizer.Show(self.model_info_label, True)
        self._main_sizer.Show(self.model_info, True)
        self._layout()

    def _hide_model_info(self) -> None:
        self.model_info.SetValue("")
        self._main_sizer.Show(self.model_info_label, False)
        self._main_sizer.Show(self.model_info, False)

    def _set_post_explain_buttons(self, has_attempted: bool) -> None:
        """Explain and Regenerate are mutually exclusive."""
        if has_attempted:
            self.explain_button.Hide()
            self.regenerate_button.Show()
        else:
            self.explain_button.Show()
            self.regenerate_button.Hide()
        self._layout()

    def _show_sps_chooser(self, visible: bool) -> None:
        label = self.sps_choice_label
        choice = self.sps_choice
        if label is None or choice is None:
            return
        self._main_sizer.Show(label, visible)
        self._main_sizer.Show(choice, visible)
        self._layout()

    def _show_retry(self, visible: bool) -> None:
        if visible:
            self.retry_button.Show()
        else:
            self.retry_button.Hide()
        self._layout()

    # ------------------------------------------------------------------
    # Load flow
    # ------------------------------------------------------------------
    def _trigger_load(self) -> None:
        """Enter the loading state and dispatch the async loader."""
        if self._cwa_office is None:
            # Nothing we can do — surface the pre-refresh message.
            self._render_no_cwa_state()
            return

        self._is_loading = True
        self._show_retry(False)
        self.product_textctrl.SetValue("Loading...")
        self.issuance_label.SetLabel("")
        self._hide_ai_summary_section()
        self._set_post_explain_buttons(has_attempted=False)
        self.explain_button.Disable()

        # Schedule the coroutine. Tests may stub _schedule_load; production
        # uses asyncio.ensure_future on the app's event loop.
        self._schedule_load(self._product_loader())

    def _schedule_load(self, coro) -> None:
        """
        Dispatch a loader coroutine. Separated for test override.

        Uses the app's run_async (background asyncio loop) when available —
        that's the only dispatch path that actually runs in production,
        because the wx main thread has no running asyncio loop of its own.
        """
        runner = getattr(self._app, "run_async", None) if self._app is not None else None
        if runner is not None:
            runner(self._run_loader(coro))
            return

        import asyncio

        try:
            asyncio.ensure_future(self._run_loader(coro))
        except RuntimeError:
            # No running loop — coroutine never runs. Surface as a load error
            # rather than leaving the panel stuck in Loading...
            logger.warning("No running event loop for ForecastProductPanel loader")
            wx.CallAfter(
                self._on_load_error,
                RuntimeError("No running event loop; cannot load product"),
            )
            coro.close()

    async def _run_loader(self, coro) -> None:
        """Await the loader coroutine and marshal result/error to main thread."""
        try:
            result = await coro
            wx.CallAfter(self._on_load_complete, result)
        except Exception as exc:  # noqa: BLE001 — surface any error as fetch failure
            logger.warning(f"ForecastProductPanel({self.product_type}) load failed: {exc}")
            wx.CallAfter(self._on_load_error, exc)

    # ------------------------------------------------------------------
    # Render paths — exercised directly by tests
    # ------------------------------------------------------------------
    def _render_no_cwa_state(self) -> None:
        """Render the 'cwa_office is null' fallback message."""
        self._current_text = None
        self.product_textctrl.SetValue(_NO_CWA_COPY)
        self.issuance_label.SetLabel("")
        self._show_sps_chooser(False)
        self._show_retry(False)
        self._hide_ai_summary_section()
        self.explain_button.Disable()

    def _on_load_complete(
        self,
        result: TextProduct | list[TextProduct] | None,
    ) -> None:
        """Handle successful fetch — may be None / empty / single / multi."""
        self._is_loading = False
        self._show_retry(False)

        # Normalise to list.
        if result is None:
            products: list[TextProduct] = []
        elif isinstance(result, list):
            products = list(result)
        else:
            products = [result]

        if not products:
            self._render_empty_state()
            self._notify_availability(False)
            return

        if self.product_type == "SPS":
            self._render_sps_products(products)
        else:
            self._render_single_product(products[0])
        self._notify_availability(True)

    def _render_empty_state(self) -> None:
        """Render the 'no product available' state."""
        template = _EMPTY_COPY[self.product_type]
        self.product_textctrl.SetValue(template.format(cwa_office=self._cwa_office))
        self.issuance_label.SetLabel("")
        self._show_sps_chooser(False)
        self._hide_ai_summary_section()
        self.explain_button.Disable()
        self._current_text = None

    def _render_single_product(self, product: TextProduct) -> None:
        """Render a single product (AFD / HWO / single SPS)."""
        self._current_text = product.product_text
        self.product_textctrl.SetValue(product.product_text)
        self.issuance_label.SetLabel(_format_issuance(product.issuance_time))
        self._show_sps_chooser(False)
        self._update_explain_button_state()

    def _render_sps_products(self, products: list[TextProduct]) -> None:
        """Render one or more SPS products with the multi-choice picker."""
        self._sps_products = products
        choice = self.sps_choice
        if choice is None:  # non-SPS panels shouldn't reach this path
            return
        entries = [_format_sps_choice_entry(p) for p in products]
        # Repopulate the choice widget. MagicMock in tests tolerates both.
        choice.Clear()
        for entry in entries:
            choice.Append(entry)
        choice.SetSelection(0)
        self._show_sps_chooser(len(products) > 1)
        self._render_single_product(products[0])
        # _render_single_product hides the chooser — re-show if multi.
        self._show_sps_chooser(len(products) > 1)

    def _on_sps_choice_changed(self, event) -> None:
        """Swap the TextCtrl content when the user picks a different SPS."""
        del event
        choice = self.sps_choice
        if choice is None:
            return
        idx = choice.GetSelection()
        if idx < 0 or idx >= len(self._sps_products):
            return
        product = self._sps_products[idx]
        self._current_text = product.product_text
        self.product_textctrl.SetValue(product.product_text)
        self.issuance_label.SetLabel(_format_issuance(product.issuance_time))
        self._update_explain_button_state()
        # Hide stale AI summary when switching products.
        self._hide_ai_summary_section()
        self._set_post_explain_buttons(has_attempted=False)

    def _on_load_error(self, exc: Exception) -> None:
        """Render the fetch-failed state."""
        del exc
        self._is_loading = False
        full_name = _PRODUCT_FULL_NAMES[self.product_type]
        self.product_textctrl.SetValue(f"Failed to fetch {full_name} — try again.")
        self.issuance_label.SetLabel("")
        self._show_sps_chooser(False)
        self._hide_ai_summary_section()
        self.explain_button.Disable()
        self._show_retry(True)
        self._current_text = None
        self._notify_availability(True)

    def _notify_availability(self, has_product: bool) -> None:
        """Tell the parent dialog whether this product has confirmed content."""
        if self._availability_callback is None:
            return
        self._availability_callback(self, has_product)

    def _update_explain_button_state(self) -> None:
        """
        Enable Explain only when we have loaded text + an OpenRouter key.

        The explainer itself is built on-demand at click time (mirrors
        ``DiscussionDialog._do_explain``). An injected ``self._ai_explainer``
        takes priority when set, which is how tests inject mocks.
        """
        if not self._current_text:
            self.explain_button.Disable()
            return
        if self._ai_explainer is not None:
            self.explain_button.Enable()
            return
        if self._has_openrouter_key():
            self.explain_button.Enable()
        else:
            self.explain_button.Disable()

    @staticmethod
    def _has_openrouter_key() -> bool:
        """Return True when the OpenRouter API key is available in SecureStorage."""
        return has_openrouter_key()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_retry(self, event) -> None:
        """Retry button click — re-invoke the loader."""
        del event
        self._trigger_load()

    def _on_explain(self, event) -> None:
        """Plain Language Summary button click."""
        del event
        if not self._current_text or self._is_explaining:
            return
        self._is_explaining = True
        self._show_ai_summary_section()
        self._hide_model_info()
        self._set_post_explain_buttons(has_attempted=False)
        self.explain_button.Disable()
        self.ai_summary_display.SetValue("Generating plain language summary...")
        self._schedule_explain(self._current_text)

    def _on_regenerate(self, event) -> None:
        """Regenerate summary — clear the explainer cache and re-invoke."""
        cache = getattr(self._ai_explainer, "cache", None)
        if cache is not None:
            try:
                cache.clear()
            except Exception:  # noqa: BLE001
                logger.debug("Failed to clear explainer cache", exc_info=True)
        self._on_explain(event)

    def _schedule_explain(self, text: str) -> None:
        """Dispatch the AI explain coroutine. Separated for test override."""
        runner = getattr(self._app, "run_async", None) if self._app is not None else None
        if runner is not None:
            runner(self._run_explain(text))
            return

        import asyncio

        try:
            asyncio.ensure_future(self._run_explain(text))
        except RuntimeError:
            logger.warning("No running event loop for ForecastProductPanel explain")

    def _build_explainer(self):
        """
        Build (or return the injected) AIExplainer for this click.

        Mirrors ``DiscussionDialog._do_explain``: reads the API key from
        SecureStorage and model + custom-prompt settings from AppConfig.
        Returns ``None`` when no API key is available, which surfaces as a
        user-facing error via the existing ``_on_explain_error`` path.
        """
        return build_explainer(self._ai_explainer, self._app)

    async def _run_explain(self, text: str) -> None:
        """Invoke ``AIExplainer.explain_text_product`` for this tab's product."""
        try:
            explainer = self._build_explainer()
            if explainer is None:
                wx.CallAfter(
                    self._on_explain_error,
                    "OpenRouter API key not configured. Set it in Settings > AI.",
                )
                return
            result = await explainer.explain_text_product(
                text,
                cast(ProductType, self.product_type),
                self._location_name,
            )
            wx.CallAfter(
                self._on_explain_complete,
                result.text,
                getattr(result, "model_used", ""),
                getattr(result, "token_count", 0),
                getattr(result, "estimated_cost", 0.0),
                getattr(result, "cached", False),
            )
        except Exception as exc:  # noqa: BLE001
            wx.CallAfter(self._on_explain_error, str(exc))

    def _on_explain_complete(
        self,
        summary: str,
        model_used: str = "",
        token_count: int = 0,
        estimated_cost: float = 0.0,
        cached: bool = False,
    ) -> None:
        """Fill in the AI summary TextCtrl + Model Information on success."""
        self._is_explaining = False
        self._show_ai_summary_section()
        self._set_post_explain_buttons(has_attempted=True)
        self.ai_summary_display.SetValue(summary)
        cost_text = "No cost" if estimated_cost == 0 else f"~${estimated_cost:.6f}"
        info = f"Model: {model_used}\nTokens: {token_count}\nCost: {cost_text}"
        if cached:
            info += "\nCached: Yes"
        self.model_info.SetValue(info)
        self._show_model_info()

    def _on_explain_error(self, message: str) -> None:
        """Populate the AI summary TextCtrl with an error message."""
        self._is_explaining = False
        self._show_ai_summary_section()
        self._set_post_explain_buttons(has_attempted=True)
        self.ai_summary_display.SetValue(
            f"Failed to generate summary: {message}\n\nCheck your OpenRouter API key in Settings."
        )
