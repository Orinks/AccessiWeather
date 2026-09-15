from __future__ import annotations

from types import SimpleNamespace

import pytest

from accessiweather.shortcut_preferences import WINDOW_TRAY_SHORTCUTS
from accessiweather.ui.dialogs.settings_dialog_handlers import SettingsDialogHandlersMixin
from accessiweather.ui.dialogs.settings_tabs.advanced import AdvancedTab


class _DummyControl:
    def __init__(self) -> None:
        self._value = ""
        self._name = ""

        self.focused = False
        self.selected_all = False

    def SetValue(self, value):
        self._value = value

    def SetFocus(self) -> None:
        self.focused = True

    def SelectAll(self) -> None:
        self.selected_all = True

    def GetValue(self):
        return self._value

    def SetName(self, value: str) -> None:
        self._name = value

    def Enable(self, _value: bool) -> None:
        return None


class _Controls(dict):
    def __missing__(self, key: str) -> _DummyControl:
        control = _DummyControl()
        self[key] = control
        return control


class _DialogStub(SettingsDialogHandlersMixin):
    def __init__(self) -> None:
        self._controls = _Controls()


def test_advanced_tab_load_and_save_include_window_tray_shortcuts():
    dialog = SimpleNamespace(
        _controls=_Controls(), _update_minimize_on_startup_state=lambda _v: None
    )
    tab = AdvancedTab(dialog)
    settings = SimpleNamespace(
        minimize_to_tray=True,
        minimize_on_startup=False,
        shortcut_show_main_window="Ctrl+Alt+W",
        shortcut_hide_main_window="Ctrl+Alt+M",
        shortcut_read_tray_info="Ctrl+Alt+I",
        startup_enabled=True,
        weather_history_enabled=False,
    )

    tab.load(settings)
    saved = tab.save()

    assert saved["shortcut_show_main_window"] == "Ctrl+Alt+W"
    assert saved["shortcut_hide_main_window"] == "Ctrl+Alt+M"
    assert saved["shortcut_read_tray_info"] == "Ctrl+Alt+I"


def test_validate_window_tray_shortcuts_rejects_reserved_shortcut():
    dialog = _DialogStub()
    dialog._controls["shortcut_show_main_window"].SetValue("Ctrl+R")
    dialog._controls["shortcut_hide_main_window"].SetValue("Ctrl+Shift+M")
    dialog._controls["shortcut_read_tray_info"].SetValue("Ctrl+Shift+I")

    error = dialog._validate_window_tray_shortcuts()

    assert error == (
        "shortcut_show_main_window",
        "Show main window shortcut cannot use Ctrl+R because that shortcut already "
        "refresh the weather.",
    )


def test_on_ok_focuses_the_rejected_shortcut_field(monkeypatch):
    from accessiweather.ui.dialogs import settings_dialog_handlers

    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        settings_dialog_handlers.wx,
        "MessageBox",
        lambda message, caption, *_args, **_kwargs: shown.append((caption, message)),
    )
    dialog = _DialogStub()
    dialog._save_settings = lambda: pytest.fail("settings must not save with a bad shortcut")
    dialog._controls["shortcut_show_main_window"].SetValue("Ctrl+Alt+Shift+W")
    dialog._controls["shortcut_hide_main_window"].SetValue("Ctrl+Weather")
    dialog._controls["shortcut_read_tray_info"].SetValue("")

    dialog._on_ok(None)

    assert shown and shown[0][0] == "Shortcut Problem"
    assert dialog._controls["shortcut_hide_main_window"].focused
    assert dialog._controls["shortcut_hide_main_window"].selected_all
    assert not dialog._controls["shortcut_show_main_window"].focused


def test_validate_window_tray_shortcuts_normalizes_values_and_allows_blank():
    dialog = _DialogStub()
    dialog._controls["shortcut_show_main_window"].SetValue(" control + alt + shift + w ")
    dialog._controls["shortcut_hide_main_window"].SetValue("")
    dialog._controls["shortcut_read_tray_info"].SetValue("ctrl+alt+i")

    error = dialog._validate_window_tray_shortcuts()

    assert error is None
    assert dialog._controls["shortcut_show_main_window"].GetValue() == "Ctrl+Alt+Shift+W"
    assert dialog._controls["shortcut_hide_main_window"].GetValue() == ""
    assert dialog._controls["shortcut_read_tray_info"].GetValue() == "Ctrl+Alt+I"
    assert {preference.setting_name for preference in WINDOW_TRAY_SHORTCUTS} == {
        "shortcut_show_main_window",
        "shortcut_hide_main_window",
        "shortcut_read_tray_info",
    }
