"""Tests for source priority combo box persistence in settings dialog."""

from __future__ import annotations

from collections import defaultdict
import sys
import types
from unittest.mock import MagicMock

# Some dialog package imports require this optional wx module.
if "wx.lib.scrolledpanel" not in sys.modules:
    _scrolled = types.ModuleType("wx.lib.scrolledpanel")
    _scrolled.ScrolledPanel = object
    sys.modules["wx.lib.scrolledpanel"] = _scrolled

from accessiweather.models import AppSettings
from accessiweather.ui.dialogs.settings_dialog import (
    INTL_PRIORITY_OPTIONS,
    US_PRIORITY_OPTIONS,
    SettingsDialogSimple,
    _priority_selection_from_value,
)


class _DummyControl:
    def __init__(self):
        self._selection = 0
        self._value = False
        self._items: list[str] = []

    def SetSelection(self, value: int):
        self._selection = value

    def GetSelection(self) -> int:
        return self._selection

    def SetValue(self, value):
        self._value = value

    def GetValue(self):
        return self._value

    def Append(self, item: str):
        self._items.append(item)

    def GetCount(self) -> int:
        return len(self._items)

    def SetString(self, index: int, value: str):
        if index < len(self._items):
            self._items[index] = value

    def Clear(self):
        self._items = []
        self._selection = 0

    def Enable(self, _enabled: bool):
        return None

    def SetName(self, _name: str):
        return None


def _build_dialog(settings: AppSettings) -> SettingsDialogSimple:
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog.config_manager = MagicMock()
    dialog.config_manager.get_settings.return_value = settings
    dialog.config_manager.update_settings.return_value = True
    dialog._controls = defaultdict(_DummyControl)
    dialog._sound_pack_ids = ["default"]
    dialog._selected_specific_model = None
    dialog._update_minimize_on_startup_state = lambda _enabled: None
    return dialog


def test_load_settings_initializes_source_priority_combo_boxes_from_saved_values():
    settings = AppSettings(
        source_priority_us=["openmeteo", "nws", "visualcrossing"],
        source_priority_international=["visualcrossing", "openmeteo"],
    )
    dialog = _build_dialog(settings)

    dialog._load_settings()

    assert dialog._controls["us_priority"].GetSelection() == 2
    assert dialog._controls["intl_priority"].GetSelection() == 1


def test_save_settings_persists_selected_source_priority_values():
    dialog = _build_dialog(AppSettings())
    dialog._controls["us_priority"].SetSelection(1)
    dialog._controls["intl_priority"].SetSelection(1)

    assert dialog._save_settings() is True

    call = dialog.config_manager.update_settings.call_args
    assert call is not None
    kwargs = call.kwargs
    assert kwargs["source_priority_us"] == US_PRIORITY_OPTIONS[1]
    assert kwargs["source_priority_international"] == INTL_PRIORITY_OPTIONS[1]


def test_invalid_saved_priority_defaults_to_first_option():
    assert _priority_selection_from_value(["bad", "order"], US_PRIORITY_OPTIONS) == 0
