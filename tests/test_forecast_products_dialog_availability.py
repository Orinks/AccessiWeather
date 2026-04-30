"""Pure unit tests for ForecastProductsDialog tab availability handling."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.ui.dialogs.forecast_products_dialog import ForecastProductsDialog


def _dialog_stub(product_types: list[str]):
    panels = [SimpleNamespace(product_type=product_type) for product_type in product_types]
    return SimpleNamespace(notebook=MagicMock(name="Notebook"), panels=panels), panels


def test_empty_optional_product_removes_tab():
    dlg, panels = _dialog_stub(["AFD", "HWO", "SPS"])

    ForecastProductsDialog._on_panel_availability_resolved(dlg, panels[1], False)

    dlg.notebook.DeletePage.assert_called_once_with(1)
    assert [panel.product_type for panel in dlg.panels] == ["AFD", "SPS"]


def test_empty_afd_product_keeps_tab():
    dlg, panels = _dialog_stub(["AFD", "HWO", "SPS"])

    ForecastProductsDialog._on_panel_availability_resolved(dlg, panels[0], False)

    dlg.notebook.DeletePage.assert_not_called()
    assert [panel.product_type for panel in dlg.panels] == ["AFD", "HWO", "SPS"]


def test_available_optional_product_keeps_tab():
    dlg, panels = _dialog_stub(["AFD", "HWO", "SPS"])

    ForecastProductsDialog._on_panel_availability_resolved(dlg, panels[2], True)

    dlg.notebook.DeletePage.assert_not_called()
    assert [panel.product_type for panel in dlg.panels] == ["AFD", "HWO", "SPS"]
