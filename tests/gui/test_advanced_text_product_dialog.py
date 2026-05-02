from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.skipif(
    hasattr(sys.modules.get("wx"), "_core"),
    reason="Real wxPython detected; this module patches wx globals for stub-only dialog tests.",
)

_wx = sys.modules["wx"]

for _attr, _val in {
    "DEFAULT_DIALOG_STYLE": 0,
    "RESIZE_BORDER": 0x40,
    "TE_MULTILINE": 0x0020,
    "TE_READONLY": 0x0010,
    "HSCROLL": 0x8000,
    "WXK_ESCAPE": 27,
    "ID_CLOSE": 5107,
    "ID_OK": 5100,
}.items():
    if not hasattr(_wx, _attr):
        setattr(_wx, _attr, _val)


@pytest.fixture(autouse=True)
def _neutralize_wx():
    saved: dict = {"Dialog.__init__": _wx.Dialog.__init__}

    def _noop(self, *a, **kw):
        return None

    _wx.Dialog.__init__ = _noop
    for name in ("StaticText", "TextCtrl", "Button", "Choice", "CheckBox"):
        saved[name] = getattr(_wx, name)
        setattr(
            _wx,
            name,
            MagicMock(
                name=name,
                side_effect=lambda *a, _name=name, **kw: MagicMock(name=kw.get("label", _name)),
            ),
        )

    saved["CallAfter"] = _wx.CallAfter
    _wx.CallAfter = MagicMock(name="CallAfter", side_effect=lambda func, *a, **kw: func(*a, **kw))

    for meth in ("SetSize", "SetSizer", "Bind", "EndModal", "Close", "CenterOnParent"):
        if not hasattr(_wx.Dialog, meth):
            setattr(_wx.Dialog, meth, _noop)

    yield

    _wx.Dialog.__init__ = saved["Dialog.__init__"]
    for name in ("StaticText", "TextCtrl", "Button", "Choice", "CheckBox"):
        setattr(_wx, name, saved[name])
    _wx.CallAfter = saved["CallAfter"]


from accessiweather.models import Location, TextProduct  # noqa: E402
from accessiweather.ui.dialogs.advanced_text_product_dialog import (  # noqa: E402
    AdvancedTextProductDialog,
)


def _location() -> Location:
    return Location(
        name="Raleigh, NC",
        latitude=35.78,
        longitude=-78.64,
        country_code="US",
        cwa_office="RAH",
    )


def _product(product_type: str = "AFD") -> TextProduct:
    return TextProduct(
        product_type=product_type,  # type: ignore[arg-type]
        product_id="p1",
        cwa_office="RAH",
        issuance_time=None,
        product_text="official text",
        headline="Official product",
    )


def test_lookup_prefers_nws_history_for_supported_local_products():
    service = MagicMock()
    service.get_history = AsyncMock(return_value=[_product("AFD")])
    service.get_iem_afos = AsyncMock(return_value=_product("SWODY1"))

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )

    dlg.product_input.GetValue.return_value = "AFD"
    dlg.location_input.GetValue.return_value = "RAH"
    dlg.limit_input.GetValue.return_value = "5"
    dlg.start_input.GetValue.return_value = "2026-05-01"
    dlg.end_input.GetValue.return_value = "2026-05-02T12:00:00Z"
    dlg.source_choice.GetStringSelection.return_value = "Prefer NWS when available"
    dlg._run_lookup_sync()

    call_kwargs = service.get_history.await_args.kwargs
    assert service.get_history.await_args.args == ("AFD", "RAH")
    assert call_kwargs["limit"] == 5
    assert call_kwargs["start"].isoformat() == "2026-05-01T00:00:00+00:00"
    assert call_kwargs["end"].isoformat() == "2026-05-02T12:00:00+00:00"
    service.get_iem_afos.assert_not_called()
    dlg.result_text.SetValue.assert_called()
    assert "official text" in dlg.result_text.SetValue.call_args.args[0]


def test_lookup_uses_iem_for_national_pil_without_nws_location():
    service = MagicMock()
    service.get_history = AsyncMock(return_value=[])
    service.get_iem_afos = AsyncMock(return_value=_product("SWODY1"))

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="SWODY1",
    )
    dlg.product_input.GetValue.return_value = "SWODY1"
    dlg.location_input.GetValue.return_value = ""
    dlg.limit_input.GetValue.return_value = "1"
    dlg.start_input.GetValue.return_value = ""
    dlg.end_input.GetValue.return_value = ""
    dlg.source_choice.GetStringSelection.return_value = "Prefer NWS when available"

    dlg._run_lookup_sync()

    service.get_history.assert_not_called()
    service.get_iem_afos.assert_awaited_once()
    assert "Source: IEM" in dlg.result_text.SetValue.call_args.args[0]


def test_lookup_can_fetch_spc_outlook_summary():
    service = MagicMock()
    service.get_iem_spc_outlook = AsyncMock(return_value=_product("SPC_OUTLOOK_DAY1"))

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="SPC Day 1 Outlook",
    )
    dlg.product_input.GetValue.return_value = "SPC Day 1 Outlook"
    dlg.limit_input.GetValue.return_value = "1"
    dlg.start_input.GetValue.return_value = ""
    dlg.end_input.GetValue.return_value = ""
    dlg.source_choice.GetStringSelection.return_value = "Prefer NWS when available"

    dlg._run_lookup_sync()

    service.get_iem_spc_outlook.assert_awaited_once_with(35.78, -78.64, day=1, current=True)


def test_product_preset_updates_product_input():
    service = MagicMock()
    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    dlg.product_preset_choice.GetStringSelection.return_value = "WPC MPD near location"

    dlg._on_product_preset(MagicMock())

    dlg.product_input.SetValue.assert_called_once_with("WPC MPD")


def test_lookup_can_fetch_wpc_outlook_summary():
    service = MagicMock()
    service.get_iem_wpc_outlook = AsyncMock(return_value=_product("WPC_ERO_DAY1"))

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="WPC Day 1 Excessive Rainfall Outlook",
    )
    dlg.product_input.GetValue.return_value = "WPC Day 1 Excessive Rainfall Outlook"
    dlg.limit_input.GetValue.return_value = "1"
    dlg.start_input.GetValue.return_value = "2026-05-01T12:00:00Z"
    dlg.end_input.GetValue.return_value = ""
    dlg.source_choice.GetStringSelection.return_value = "Prefer NWS when available"

    dlg._run_lookup_sync()

    service.get_iem_wpc_outlook.assert_awaited_once()
    assert service.get_iem_wpc_outlook.await_args.kwargs["day"] == 1
    assert service.get_iem_wpc_outlook.await_args.kwargs["valid_at"].isoformat() == (
        "2026-05-01T12:00:00+00:00"
    )


def test_lookup_can_fetch_wpc_mpd_summary():
    service = MagicMock()
    service.get_iem_wpc_mpds = AsyncMock(return_value=_product("WPC_MPD"))

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="WPC MPD",
    )
    dlg.product_input.GetValue.return_value = "WPC MPD"
    dlg.limit_input.GetValue.return_value = "1"
    dlg.start_input.GetValue.return_value = ""
    dlg.end_input.GetValue.return_value = ""
    dlg.source_choice.GetStringSelection.return_value = "Prefer NWS when available"

    dlg._run_lookup_sync()

    service.get_iem_wpc_mpds.assert_awaited_once_with(35.78, -78.64)


def test_lookup_can_fetch_spc_watch_summary():
    service = MagicMock()
    service.get_iem_spc_watches = AsyncMock(return_value=_product("SPC_WATCHES"))

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="SPC Watches",
    )
    dlg.product_input.GetValue.return_value = "SPC Watches"
    dlg.limit_input.GetValue.return_value = "1"
    dlg.start_input.GetValue.return_value = "2026-03-16T15:00:00Z"
    dlg.end_input.GetValue.return_value = ""
    dlg.source_choice.GetStringSelection.return_value = "Prefer NWS when available"

    dlg._run_lookup_sync()

    service.get_iem_spc_watches.assert_awaited_once()
    assert service.get_iem_spc_watches.await_args.kwargs["valid_at"].isoformat() == (
        "2026-03-16T15:00:00+00:00"
    )
