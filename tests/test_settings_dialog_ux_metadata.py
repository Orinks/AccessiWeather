from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import accessiweather.ui.dialogs.settings_dialog as settings_module
from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple
from accessiweather.ui.dialogs.settings_tabs.audio import AudioTab
from accessiweather.ui.dialogs.settings_tabs.data_sources import DataSourcesTab


def test_dialog_tab_definitions_follow_user_focused_order_and_labels():
    assert SettingsDialogSimple.get_tab_definitions() == [
        ("general", "General"),
        ("display", "Display"),
        ("notifications", "Alerts"),
        ("audio", "Audio"),
        ("data_sources", "Data Sources"),
        ("ai", "AI"),
        ("updates", "Updates"),
        ("advanced", "Advanced"),
    ]


def test_audio_event_sound_summary_mentions_sound_choices_clearly():
    enabled = AudioTab._build_default_event_sound_states()
    total = len(enabled)
    assert AudioTab.build_event_sound_summary_text(enabled) == (
        f"Sounds will play for all {total} selectable event types."
    )

    some_disabled = dict(enabled)
    some_disabled["data_updated"] = False
    some_disabled["fetch_error"] = False
    assert AudioTab.build_event_sound_summary_text(some_disabled) == (
        f"Sounds will play for {total - 2} of {total} selectable event types."
    )

    all_disabled = dict.fromkeys(enabled, False)
    assert (
        AudioTab.build_event_sound_summary_text(all_disabled)
        == "Sounds are turned off for every selectable event type."
    )


def test_source_settings_summary_uses_plain_language():
    state = {
        "auto_mode_api_budget": 2,
        "auto_sources_us": ["nws", "openmeteo", "pirateweather"],
        "auto_sources_international": ["openmeteo", "pirateweather"],
        "station_selection_strategy": 2,
    }

    assert DataSourcesTab.build_source_settings_summary_text(state) == (
        "Automatic mode budget: Max coverage. "
        "US automatic sources: NWS, Open-Meteo, Pirate Weather. "
        "International automatic sources: Open-Meteo, Pirate Weather. "
        "NWS station strategy: Major airport preferred."
    )


def test_create_section_uses_heading_and_plain_sizer_for_accessibility(monkeypatch):
    fake_section = MagicMock()
    fake_heading = MagicMock()
    monkeypatch.setattr(
        settings_module.wx,
        "BoxSizer",
        MagicMock(return_value=fake_section),
        raising=False,
    )
    monkeypatch.setattr(
        settings_module.wx,
        "StaticText",
        MagicMock(return_value=fake_heading),
        raising=False,
    )
    monkeypatch.setattr(settings_module.wx, "VERTICAL", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "EXPAND", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "LEFT", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "RIGHT", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "TOP", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "BOTTOM", 0, raising=False)

    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog.add_help_text = MagicMock()
    dialog._wrap_static_text = MagicMock()
    parent_sizer = MagicMock()
    parent = MagicMock()

    section = dialog.create_section(
        parent=parent,
        parent_sizer=parent_sizer,
        title="Weather refresh",
        description="This should not be injected before the first control.",
    )

    assert section is fake_section
    settings_module.wx.StaticText.assert_called_once_with(parent, label="Weather refresh")
    dialog._wrap_static_text.assert_called_once_with(fake_heading)
    dialog.add_help_text.assert_not_called()
    assert parent_sizer.Add.call_count == 2


def test_add_labeled_control_row_creates_label_before_control(monkeypatch):
    creation_order: list[str] = []
    fake_row = MagicMock()
    fake_label = MagicMock()
    fake_control = MagicMock()

    monkeypatch.setattr(
        settings_module.wx,
        "BoxSizer",
        MagicMock(return_value=fake_row),
        raising=False,
    )
    monkeypatch.setattr(settings_module.wx, "HORIZONTAL", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "ALIGN_CENTER_VERTICAL", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "RIGHT", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "LEFT", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "BOTTOM", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "EXPAND", 0, raising=False)

    def fake_static_text(parent, label):
        creation_order.append(f"label:{label}")
        return fake_label

    monkeypatch.setattr(settings_module.wx, "StaticText", fake_static_text, raising=False)

    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    parent_sizer = MagicMock()
    parent = MagicMock()

    control = dialog.add_labeled_control_row(
        parent,
        parent_sizer,
        "Weather source:",
        lambda _parent: creation_order.append("control") or fake_control,
    )

    assert control is fake_control
    assert creation_order == ["label:Weather source:", "control"]
    assert fake_row.Add.call_count == 2
    parent_sizer.Add.assert_called_once()


def test_data_sources_tab_provider_groups_avoid_static_box_sizers(monkeypatch):
    class FakeControl:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.bound = []
            self.sizer = None

        def Bind(self, *args, **kwargs):
            self.bound.append((args, kwargs))

        def SetScrollRate(self, *args):
            return None

        def SetSizer(self, sizer):
            self.sizer = sizer

    class FakeSizer:
        def __init__(self, *args, **kwargs):
            self.children = []

        def Add(self, *args, **kwargs):
            self.children.append((args, kwargs))

        def ShowItems(self, _show):
            return None

    class FakeNotebook(FakeControl):
        def __init__(self):
            super().__init__()
            self.pages = []

        def AddPage(self, panel, label):
            self.pages.append((panel, label))

    monkeypatch.setattr(
        settings_module.wx,
        "StaticBoxSizer",
        MagicMock(side_effect=AssertionError("StaticBoxSizer should not be used")),
        raising=False,
    )
    monkeypatch.setattr(settings_module.wx, "ScrolledWindow", FakeControl, raising=False)
    monkeypatch.setattr(settings_module.wx, "BoxSizer", FakeSizer, raising=False)
    monkeypatch.setattr(settings_module.wx, "Choice", FakeControl, raising=False)
    monkeypatch.setattr(settings_module.wx, "TextCtrl", FakeControl, raising=False)
    monkeypatch.setattr(settings_module.wx, "Button", FakeControl, raising=False)
    monkeypatch.setattr(settings_module.wx, "StaticText", FakeControl, raising=False)
    monkeypatch.setattr(settings_module.wx, "TE_MULTILINE", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "TE_NO_VSCROLL", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "TE_READONLY", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "TE_PASSWORD", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "VERTICAL", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "LEFT", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "RIGHT", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "BOTTOM", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "EXPAND", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "EVT_CHOICE", object(), raising=False)
    monkeypatch.setattr(settings_module.wx, "EVT_BUTTON", object(), raising=False)

    dialog = SimpleNamespace(
        notebook=FakeNotebook(),
        _controls={},
        add_help_text=MagicMock(),
        create_section=MagicMock(side_effect=lambda *args, **kwargs: FakeSizer()),
        add_labeled_row=MagicMock(),
        add_labeled_control_row=MagicMock(
            side_effect=lambda _p, _s, _l, factory, **_k: factory(_p)
        ),
        _wrap_static_text=MagicMock(),
        _on_data_source_changed=MagicMock(),
        _on_configure_source_settings=MagicMock(),
        _on_get_pw_api_key=MagicMock(),
        _on_validate_pw_api_key=MagicMock(),
    )

    tab = DataSourcesTab(dialog)
    panel = tab.create()

    assert panel is dialog.notebook.pages[0][0]
    assert dialog.create_section.call_count >= 3
