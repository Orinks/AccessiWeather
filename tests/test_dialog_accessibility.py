from __future__ import annotations

from unittest.mock import MagicMock

import accessiweather.ui.dialogs.settings_dialog as settings_module
from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple


def test_configure_modal_dialog_buttons_sets_standard_wx_semantics():
    dialog = MagicMock()
    ok_btn = MagicMock()
    cancel_btn = MagicMock()
    focus_target = MagicMock()

    dlg = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dlg._configure_modal_dialog_buttons(dialog, ok_btn, cancel_btn, focus_target=focus_target)

    dialog.SetAffirmativeId.assert_called_once_with(settings_module.wx.ID_OK)
    dialog.SetEscapeId.assert_called_once_with(settings_module.wx.ID_CANCEL)
    ok_btn.SetDefault.assert_called_once()
    focus_target.SetFocus.assert_called_once()


def test_run_event_sounds_dialog_configures_default_button_and_focus(monkeypatch):
    class FakeWindow:
        def __init__(self, *args, **kwargs):
            self.focused = False

        def SetFocus(self):
            self.focused = True

    class FakeDialog(FakeWindow):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.affirmative = None
            self.escape = None
            self.destroyed = False
            self.sizer = None

        def SetSizer(self, sizer):
            self.sizer = sizer

        def SetAffirmativeId(self, value):
            self.affirmative = value

        def SetEscapeId(self, value):
            self.escape = value

        def ShowModal(self):
            return settings_module.wx.ID_CANCEL

        def Destroy(self):
            self.destroyed = True

    class FakeButton(FakeWindow):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.default = False

        def SetDefault(self):
            self.default = True

    class FakeCheckBox(FakeWindow):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.value = False

        def SetValue(self, value):
            self.value = value

        def GetValue(self):
            return self.value

    class FakeScrolledWindow(FakeWindow):
        def SetScrollRate(self, *args):
            return None

        def SetSizer(self, sizer):
            self.sizer = sizer

    class FakeSizer:
        def __init__(self, *args, **kwargs):
            self.children = []

        def Add(self, *args, **kwargs):
            self.children.append((args, kwargs))

        def AddStretchSpacer(self):
            return None

    monkeypatch.setattr(settings_module.wx, "Dialog", FakeDialog, raising=False)
    monkeypatch.setattr(settings_module.wx, "StaticText", FakeWindow, raising=False)
    monkeypatch.setattr(settings_module.wx, "BoxSizer", FakeSizer, raising=False)
    monkeypatch.setattr(settings_module.wx, "ScrolledWindow", FakeScrolledWindow, raising=False)
    monkeypatch.setattr(
        settings_module.wx,
        "StaticBoxSizer",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("StaticBoxSizer should not be used in the event sounds dialog")
        ),
        raising=False,
    )
    monkeypatch.setattr(settings_module.wx, "CheckBox", FakeCheckBox, raising=False)
    monkeypatch.setattr(settings_module.wx, "Button", FakeButton, raising=False)
    for name in [
        "DEFAULT_DIALOG_STYLE",
        "RESIZE_BORDER",
        "VERTICAL",
        "HORIZONTAL",
        "ALL",
        "EXPAND",
        "LEFT",
        "RIGHT",
        "BOTTOM",
    ]:
        monkeypatch.setattr(settings_module.wx, name, 0, raising=False)

    dlg = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dlg._event_sound_states = {"alerts": True}
    dlg._build_default_event_sound_states = MagicMock(return_value={"alerts": True})
    dlg._get_mutable_sound_events = MagicMock(return_value=[("alerts", "Alerts")])
    dlg._get_event_sound_sections = MagicMock(
        return_value=[("General", "Choose events", ["alerts"])]
    )

    result = dlg._run_event_sounds_dialog()

    assert result is None
