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
from datetime import datetime
from typing import TYPE_CHECKING, Literal, cast

import wx

if TYPE_CHECKING:
    from ...ai_explainer import AIExplainer
    from ...models import TextProduct

logger = logging.getLogger(__name__)

ProductType = Literal["AFD", "HWO", "SPS"]

_PRODUCT_FULL_NAMES: dict[str, str] = {
    "AFD": "Area Forecast Discussion",
    "HWO": "Hazardous Weather Outlook",
    "SPS": "Special Weather Statement",
}

# Empty-state copy per product type.
_EMPTY_COPY: dict[str, str] = {
    "AFD": "Area Forecast Discussion not currently available for {cwa_office}.",
    "HWO": "Hazardous Weather Outlook not currently available for {cwa_office}.",
    "SPS": "No recent Special Weather Statements for {cwa_office}.",
}

_NO_CWA_COPY = "NWS text products will populate after the next weather refresh."

ProductLoader = Callable[[], Awaitable["TextProduct | list[TextProduct] | None"]]


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

        """
        super().__init__(parent)
        self.product_type = product_type
        self._product_loader = product_loader
        self._ai_explainer = ai_explainer
        self._cwa_office = cwa_office
        self._location_name = location_name
        self._app = app

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
        self._layout()

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
            return

        if self.product_type == "SPS":
            self._render_sps_products(products)
        else:
            self._render_single_product(products[0])

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

    def _update_explain_button_state(self) -> None:
        """Enable Explain only when AI + loaded text are available."""
        if self._ai_explainer is not None and self._current_text:
            self.explain_button.Enable()
        else:
            self.explain_button.Disable()

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
        if not self._current_text or self._is_explaining or self._ai_explainer is None:
            return
        self._is_explaining = True
        self._show_ai_summary_section()
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
        if self._ai_explainer is None:
            return
        runner = getattr(self._app, "run_async", None) if self._app is not None else None
        if runner is not None:
            runner(self._run_explain(text))
            return

        import asyncio

        try:
            asyncio.ensure_future(self._run_explain(text))
        except RuntimeError:
            logger.warning("No running event loop for ForecastProductPanel explain")

    async def _run_explain(self, text: str) -> None:
        """Invoke ``AIExplainer.explain_text_product`` for this tab's product."""
        try:
            assert self._ai_explainer is not None
            # product_type is narrowed by construction — cast for pyright.
            result = await self._ai_explainer.explain_text_product(
                text,
                cast(ProductType, self.product_type),
                self._location_name,
            )
            wx.CallAfter(self._on_explain_complete, result.text)
        except Exception as exc:  # noqa: BLE001
            wx.CallAfter(self._on_explain_error, str(exc))

    def _on_explain_complete(self, summary: str) -> None:
        """Fill in the AI summary TextCtrl on success."""
        self._is_explaining = False
        self._show_ai_summary_section()
        self._set_post_explain_buttons(has_attempted=True)
        self.ai_summary_display.SetValue(summary)

    def _on_explain_error(self, message: str) -> None:
        """Populate the AI summary TextCtrl with an error message."""
        self._is_explaining = False
        self._show_ai_summary_section()
        self._set_post_explain_buttons(has_attempted=True)
        self.ai_summary_display.SetValue(
            f"Failed to generate summary: {message}\n\nCheck your OpenRouter API key in Settings."
        )


# ----------------------------------------------------------------------
# Formatting helpers
# ----------------------------------------------------------------------
def _format_issuance(issuance_time: datetime | None) -> str:
    """Return the "Issued: ..." line in the user's OS local timezone."""
    if issuance_time is None:
        return "Issued: unknown"
    try:
        local = issuance_time.astimezone()
    except (ValueError, OSError):
        local = issuance_time
    return f"Issued: {local.strftime('%Y-%m-%d %H:%M %Z').strip()}"


def _format_sps_choice_entry(product: TextProduct) -> str:
    """Build a wx.Choice entry for an SPS product."""
    if product.issuance_time is not None:
        try:
            local = product.issuance_time.astimezone()
        except (ValueError, OSError):
            local = product.issuance_time
        when = local.strftime("%Y-%m-%d %H:%M")
    else:
        when = "unknown"
    headline = product.headline
    if not headline:
        # Fall back to the first non-empty line of the product text.
        for line in (product.product_text or "").splitlines():
            stripped = line.strip()
            if stripped:
                headline = stripped
                break
    if not headline:
        headline = "Special Weather Statement"
    return f"Issued {when} \u2014 {headline}"
