"""Pure unit tests for ForecastProductPanel availability notifications."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.models import TextProduct
from accessiweather.ui.dialogs.forecast_product_panel import ForecastProductPanel


def _panel_stub(product_type: str = "HWO"):
    calls: list[bool] = []
    panel = SimpleNamespace(
        product_type=product_type,
        _availability_callback=lambda _panel, has_product: calls.append(has_product),
        _is_loading=True,
        _show_retry=MagicMock(),
        _render_empty_state=MagicMock(),
        _render_sps_products=MagicMock(),
        _render_single_product=MagicMock(),
    )
    panel._notify_availability = lambda has_product: ForecastProductPanel._notify_availability(
        panel, has_product
    )
    return panel, calls


def _product(product_type: str = "HWO") -> TextProduct:
    return TextProduct(
        product_type=product_type,  # type: ignore[arg-type]
        product_id="product-1",
        cwa_office="FWD",
        issuance_time=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
        product_text="Product text",
        headline=None,
    )


def test_empty_result_reports_unavailable_after_rendering_empty_state():
    panel, calls = _panel_stub()

    ForecastProductPanel._on_load_complete(panel, None)

    panel._render_empty_state.assert_called_once()
    assert calls == [False]


def test_single_product_reports_available_after_rendering_product():
    panel, calls = _panel_stub()

    ForecastProductPanel._on_load_complete(panel, _product())

    panel._render_single_product.assert_called_once()
    assert calls == [True]


def test_load_error_reports_available_to_keep_retry_tab_visible():
    calls: list[bool] = []
    panel = SimpleNamespace(
        product_type="HWO",
        _availability_callback=lambda _panel, has_product: calls.append(has_product),
        _is_loading=True,
        _show_retry=MagicMock(),
        _show_sps_chooser=MagicMock(),
        _hide_ai_summary_section=MagicMock(),
        product_textctrl=MagicMock(),
        issuance_label=MagicMock(),
        explain_button=MagicMock(),
        _current_text="old text",
    )
    panel._notify_availability = lambda has_product: ForecastProductPanel._notify_availability(
        panel, has_product
    )

    ForecastProductPanel._on_load_error(panel, RuntimeError("boom"))

    panel._show_retry.assert_called_once_with(True)
    assert calls == [True]
