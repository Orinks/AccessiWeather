from __future__ import annotations

import sys
from datetime import UTC, datetime
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
    "CB_READONLY": 16,
}.items():
    if not hasattr(_wx, _attr):
        setattr(_wx, _attr, _val)


@pytest.fixture(autouse=True)
def _neutralize_wx():
    saved: dict = {"Dialog.__init__": _wx.Dialog.__init__}

    def _noop(self, *a, **kw):
        return None

    _wx.Dialog.__init__ = _noop
    for name in ("StaticText", "TextCtrl", "Button", "Choice", "ComboBox", "CheckBox"):
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
    for name in ("StaticText", "TextCtrl", "Button", "Choice", "ComboBox", "CheckBox"):
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

    service.get_iem_spc_outlook.assert_awaited_once_with(
        35.78,
        -78.64,
        day=1,
        current=True,
        valid_at=None,
    )


def test_lookup_can_fetch_spc_outlook_for_valid_time():
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
    dlg.start_input.GetValue.return_value = "2026-03-06T20:00:00Z"
    dlg.end_input.GetValue.return_value = ""
    dlg.source_choice.GetStringSelection.return_value = "Prefer NWS when available"

    dlg._run_lookup_sync()

    service.get_iem_spc_outlook.assert_awaited_once()
    assert service.get_iem_spc_outlook.await_args.kwargs["current"] is False
    assert service.get_iem_spc_outlook.await_args.kwargs["valid_at"].isoformat() == (
        "2026-03-06T20:00:00+00:00"
    )


def test_product_preset_updates_product_input():
    service = MagicMock()
    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    dlg.product_preset_choice.GetStringSelection.return_value = (
        "WPC MPD (Mesoscale Precipitation Discussion) near location"
    )

    dlg._on_product_preset(MagicMock())

    dlg.product_input.SetValue.assert_called_once_with("WPC MPD")


def test_national_product_presets_use_iem_afos():
    service = MagicMock()
    service.get_iem_afos = AsyncMock(return_value=_product("PMDMRD"))

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    dlg.product_preset_choice.GetStringSelection.return_value = (
        "CPC 6-10 and 8-14 Day Outlook (Climate Prediction Center)"
    )
    dlg._on_product_preset(MagicMock())

    dlg.product_input.GetValue.return_value = "PMDMRD"
    dlg.location_input.GetValue.return_value = ""
    dlg.limit_input.GetValue.return_value = "1"
    dlg.start_input.GetValue.return_value = ""
    dlg.end_input.GetValue.return_value = ""
    dlg.source_choice.GetStringSelection.return_value = "IEM AFOS only"
    dlg._run_lookup_sync()

    dlg.product_input.SetValue.assert_called_with("PMDMRD")
    service.get_iem_afos.assert_awaited_once()


def test_local_product_preset_selects_location_office_choice():
    service = MagicMock()
    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    dlg.product_preset_choice.GetStringSelection.return_value = "Local Area Forecast Discussion"
    dlg.office_choice.GetCount.return_value = 3
    dlg.office_choice.GetString.side_effect = [
        "Selected location office (RAH)",
        "No office or national product",
        "Custom office below",
    ]

    dlg._on_product_preset(MagicMock())

    dlg.product_input.SetValue.assert_called_with("AFD")
    dlg.office_choice.SetSelection.assert_called_with(0)


def test_iem_lookup_passes_order_center_wmo_and_aviation_choices():
    service = MagicMock()
    service.get_iem_afos = AsyncMock(return_value=_product("AFDRAH"))

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    dlg.product_input.GetValue.return_value = "AFD"
    dlg.office_choice.GetStringSelection.return_value = "Selected location office (RAH)"
    dlg.limit_input.GetValue.return_value = "5"
    dlg.start_input.GetValue.return_value = ""
    dlg.end_input.GetValue.return_value = ""
    dlg.source_choice.GetStringSelection.return_value = "IEM AFOS only"
    dlg.order_choice.GetStringSelection.return_value = "Oldest first"
    dlg.afd_aviation_only.GetValue.return_value = True
    dlg.center_input.GetValue.return_value = "KRAH"
    dlg.wmo_input.GetValue.return_value = "FXUS62"

    dlg._run_lookup_sync()

    service.get_iem_afos.assert_awaited_once_with(
        "AFDRAH",
        limit=1,
        start=None,
        end=None,
        order="asc",
        aviation_afd=True,
        center="KRAH",
        wmo_id="FXUS62",
    )


def test_iem_lookup_uses_custom_date_choices_before_raw_text_fields():
    service = MagicMock()
    service.get_iem_afos = AsyncMock(return_value=_product("SWODY1"))

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="SWODY1",
    )
    dlg.product_input.GetValue.return_value = "SWODY1"
    dlg.office_choice.GetStringSelection.return_value = "No office or national product"
    dlg.limit_input.GetValue.return_value = "3"
    dlg.source_choice.GetStringSelection.return_value = "IEM AFOS only"
    dlg.order_choice.GetStringSelection.return_value = "Newest first"
    dlg.afd_aviation_only.GetValue.return_value = False
    dlg.center_input.GetValue.return_value = ""
    dlg.wmo_input.GetValue.return_value = ""
    dlg.start_year_choice.GetStringSelection.return_value = "2024"
    dlg.start_month_choice.GetStringSelection.return_value = "01 - January"
    dlg.start_day_choice.GetStringSelection.return_value = "15"
    dlg.end_year_choice.GetStringSelection.return_value = "2024"
    dlg.end_month_choice.GetStringSelection.return_value = "01 - January"
    dlg.end_day_choice.GetStringSelection.return_value = "16"
    dlg.start_input.GetValue.return_value = "2020-01-01"
    dlg.end_input.GetValue.return_value = "2020-01-02"

    dlg._run_lookup_sync()

    kwargs = service.get_iem_afos.await_args.kwargs
    assert kwargs["start"].isoformat() == "2024-01-15T00:00:00+00:00"
    assert kwargs["end"].isoformat() == "2024-01-16T00:00:00+00:00"


def test_custom_date_choice_requires_complete_calendar_date():
    service = MagicMock()

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    dlg.start_year_choice.GetStringSelection.return_value = "2024"
    dlg.start_month_choice.GetStringSelection.return_value = ""
    dlg.start_day_choice.GetStringSelection.return_value = "15"

    with pytest.raises(ValueError, match="year, month, and day"):
        dlg._date_from_choice_parts("start")


def test_custom_date_preset_prefills_valid_date_choices(monkeypatch):
    service = MagicMock()
    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    dlg.date_preset_choice.GetStringSelection.return_value = "Choose start and end dates"
    monkeypatch.setattr(
        AdvancedTextProductDialog,
        "_date_range_for_preset",
        staticmethod(
            lambda _preset: (
                datetime(2026, 7, 4, 12, 0, tzinfo=UTC),
                datetime(2026, 7, 5, 12, 0, tzinfo=UTC),
            )
        ),
    )

    dlg._on_date_preset(MagicMock())

    dlg.start_input.SetValue.assert_called_once_with("2026-07-04T12:00:00Z")
    dlg.end_input.SetValue.assert_called_once_with("2026-07-05T12:00:00Z")
    dlg.start_year_choice.SetSelection.assert_called()
    dlg.start_month_choice.SetSelection.assert_called()
    dlg.start_day_choice.SetSelection.assert_called()


def test_escape_key_ends_dialog_with_close_id():
    service = MagicMock()
    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    dlg.EndModal = MagicMock()
    event = MagicMock()
    event.GetKeyCode.return_value = _wx.WXK_ESCAPE

    dlg._on_key(event)

    dlg.EndModal.assert_called_once_with(_wx.ID_CLOSE)
    event.Skip.assert_not_called()


def test_non_escape_key_continues_event_processing():
    service = MagicMock()
    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    event = MagicMock()
    event.GetKeyCode.return_value = ord("A")

    dlg._on_key(event)

    event.Skip.assert_called_once()


def test_focusable_controls_have_accessibility_metadata():
    service = MagicMock()
    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )

    for control in dlg._focusable_controls():
        control.SetName.assert_called()
        control.SetToolTip.assert_called()


def test_iem_lookup_rejects_invalid_custom_product_id():
    service = MagicMock()
    service.get_iem_afos = AsyncMock(return_value=_product("BAD"))

    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    dlg.product_input.GetValue.return_value = "TOO-LONG"
    dlg.office_choice.GetStringSelection.return_value = "No office or national product"
    dlg.limit_input.GetValue.return_value = "1"
    dlg.start_input.GetValue.return_value = ""
    dlg.end_input.GetValue.return_value = ""
    dlg.source_choice.GetStringSelection.return_value = "IEM AFOS only"
    dlg.order_choice.GetStringSelection.return_value = "Newest first"
    dlg.afd_aviation_only.GetValue.return_value = False
    dlg.center_input.GetValue.return_value = ""
    dlg.wmo_input.GetValue.return_value = ""

    dlg._run_lookup_sync()

    service.get_iem_afos.assert_not_called()
    assert "3-to-6 character" in dlg.result_text.SetValue.call_args.args[0]


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

    service.get_iem_wpc_mpds.assert_awaited_once_with(
        35.78,
        -78.64,
        active_only=False,
        start=None,
        end=None,
        max_items=1,
    )


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


def test_date_preset_populates_start_and_end_inputs(monkeypatch):
    service = MagicMock()
    dlg = AdvancedTextProductDialog(
        parent=MagicMock(),
        location=_location(),
        forecast_product_service=service,
        initial_product_type="AFD",
    )
    dlg.date_preset_choice.GetStringSelection.return_value = "Past 7 days"
    monkeypatch.setattr(
        AdvancedTextProductDialog,
        "_date_range_for_preset",
        staticmethod(
            lambda _preset: (
                datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
                datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
            )
        ),
    )

    dlg._on_date_preset(MagicMock())

    dlg.start_input.SetValue.assert_called_once_with("2026-04-27T12:00:00Z")
    dlg.end_input.SetValue.assert_called_once_with("2026-05-04T12:00:00Z")
