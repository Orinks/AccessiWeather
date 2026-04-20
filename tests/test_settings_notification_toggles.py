"""
Tests for Unit 12 — new notification toggles + intro copy rewrite.

Covers:
1. `AppSettings.notify_hwo_update` / `notify_sps_issued` defaults ON.
2. Round-trip via `to_dict` / `from_dict` preserving non-default values.
3. Legacy config (no new keys) loads with both defaults ON.
4. Settings notifications tab load/save wires both toggles.
5. Checkbox labels describe intent without relying on nearby context.
6. Section intro StaticText reflects the two defaults-ON behavior.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from accessiweather.models.config import AppSettings

# ---------------------------------------------------------------------------
# Dataclass round-trip tests
# ---------------------------------------------------------------------------


def test_new_toggles_default_true_on_fresh_settings():
    settings = AppSettings()
    assert settings.notify_hwo_update is True
    assert settings.notify_sps_issued is True


def test_new_toggles_round_trip_defaults_through_dict():
    original = AppSettings()
    restored = AppSettings.from_dict(original.to_dict())
    assert restored.notify_hwo_update is True
    assert restored.notify_sps_issued is True


def test_new_toggles_round_trip_non_default_values():
    original = AppSettings()
    original.notify_hwo_update = False
    original.notify_sps_issued = False

    payload = original.to_dict()
    assert payload["notify_hwo_update"] is False
    assert payload["notify_sps_issued"] is False

    restored = AppSettings.from_dict(payload)
    assert restored.notify_hwo_update is False
    assert restored.notify_sps_issued is False


def test_legacy_config_without_new_keys_loads_both_defaults_on():
    # Simulate a legacy config dict: anything the user had before, WITHOUT
    # notify_hwo_update / notify_sps_issued keys.
    legacy_payload = {
        "temperature_unit": "both",
        "notify_discussion_update": True,
    }
    restored = AppSettings.from_dict(legacy_payload)
    assert restored.notify_hwo_update is True
    assert restored.notify_sps_issued is True


def test_new_toggle_keys_are_always_emitted_in_to_dict():
    # Mirror the notify_discussion_update pattern: always-emit (no conditional).
    settings = AppSettings()
    payload = settings.to_dict()
    assert "notify_hwo_update" in payload
    assert "notify_sps_issued" in payload


def test_new_toggle_deserialization_normalizes_stringy_booleans():
    # _as_bool should cover legacy/stringy representations.
    restored = AppSettings.from_dict({"notify_hwo_update": "false", "notify_sps_issued": "0"})
    assert restored.notify_hwo_update is False
    assert restored.notify_sps_issued is False


# ---------------------------------------------------------------------------
# Settings notifications tab UI tests (stub-wx based)
# ---------------------------------------------------------------------------


class _DummyControl:
    def __init__(self) -> None:
        self._value: bool | int | float = False
        self._selection = 0
        self._label = ""
        self._name = ""

    def SetValue(self, value) -> None:
        self._value = value

    def GetValue(self):
        return self._value

    def SetSelection(self, value: int) -> None:
        self._selection = value

    def GetSelection(self) -> int:
        return self._selection

    def SetLabel(self, value: str) -> None:
        self._label = value

    def GetLabel(self) -> str:
        return self._label

    def SetName(self, value: str) -> None:
        self._name = value

    def __getattr__(self, _name: str):
        return lambda *args, **kwargs: None


class _Controls(dict):
    def __missing__(self, key: str) -> _DummyControl:
        value = _DummyControl()
        self[key] = value
        return value


class _RecordedCheckBox:
    """Captures the label= kwarg so tests can assert accessibility naming."""

    instances: list[_RecordedCheckBox] = []

    def __init__(self, _parent, label: str = "", **_kwargs):
        self.label = label
        self._value = False
        self.__class__.instances.append(self)

    def SetValue(self, value) -> None:
        self._value = bool(value)

    def GetValue(self) -> bool:
        return self._value

    def SetName(self, _value: str) -> None:
        return None

    def __getattr__(self, _name: str):
        return lambda *args, **kwargs: None


class _RecordedStaticText:
    """Captures label= kwarg so tests can assert intro-copy substrings."""

    instances: list[_RecordedStaticText] = []

    def __init__(self, _parent, label: str = "", **_kwargs):
        self.label = label
        self.__class__.instances.append(self)

    def __getattr__(self, _name: str):
        return lambda *args, **kwargs: None


class _FakeSizer:
    def __init__(self) -> None:
        self.children: list = []

    def Add(self, item, *args, **kwargs) -> None:
        self.children.append(item)


class _FakeDialog:
    """Minimal stand-in for the parent settings dialog."""

    def __init__(self) -> None:
        self._controls: dict = _Controls()
        self.notebook = MagicMock()
        self.sections: list[tuple[str, str | None]] = []

    def add_help_text(self, _parent, parent_sizer, text, **_kwargs):
        st = _RecordedStaticText(_parent, label=text)
        parent_sizer.Add(st)
        return st

    def create_section(self, _parent, _parent_sizer, title, description=None):
        # Mirror real behavior: description is not rendered automatically.
        self.sections.append((title, description))
        return _FakeSizer()

    def add_labeled_control_row(self, parent, parent_sizer, _label, control_factory, **_kwargs):
        ctrl = control_factory(parent)
        parent_sizer.Add(ctrl)
        return ctrl

    def _on_alert_advanced(self, *_a, **_kw):
        return None


@pytest.fixture
def notifications_tab_panel(monkeypatch):
    """Render the Notifications tab with recorded wx widgets."""
    # Reset per-test capture lists.
    _RecordedCheckBox.instances = []
    _RecordedStaticText.instances = []

    import wx as _wx

    from accessiweather.ui.dialogs.settings_tabs import notifications as notif_mod

    # Patch the wx symbols the module uses via attribute access.
    monkeypatch.setattr(notif_mod.wx, "CheckBox", _RecordedCheckBox, raising=False)
    monkeypatch.setattr(notif_mod.wx, "StaticText", _RecordedStaticText, raising=False)
    monkeypatch.setattr(notif_mod.wx, "BoxSizer", lambda *_a, **_kw: _FakeSizer(), raising=False)
    monkeypatch.setattr(notif_mod.wx, "ScrolledWindow", MagicMock(), raising=False)
    monkeypatch.setattr(notif_mod.wx, "SpinCtrl", MagicMock(), raising=False)
    monkeypatch.setattr(notif_mod.wx, "Choice", MagicMock(), raising=False)
    monkeypatch.setattr(notif_mod.wx, "Button", MagicMock(), raising=False)

    # wx constants referenced as flags — harmless integers suffice.
    for const in (
        "LEFT",
        "RIGHT",
        "TOP",
        "BOTTOM",
        "ALL",
        "EXPAND",
        "HORIZONTAL",
        "VERTICAL",
        "ALIGN_CENTER_VERTICAL",
        "EVT_BUTTON",
    ):
        if not hasattr(notif_mod.wx, const):
            setattr(notif_mod.wx, const, 0)

    _ = _wx  # keep import for side effects (conftest wx stub setup)

    dialog = _FakeDialog()
    tab = notif_mod.NotificationsTab(dialog)
    tab.create()
    return tab, dialog


def test_tab_creates_hwo_and_sps_checkboxes_with_descriptive_labels(
    notifications_tab_panel,
):
    tab, dialog = notifications_tab_panel
    controls = dialog._controls

    assert "notify_hwo_update" in controls
    assert "notify_sps_issued" in controls

    hwo_ctrl = controls["notify_hwo_update"]
    sps_ctrl = controls["notify_sps_issued"]

    # Accessibility: labels describe intent standalone (screen readers read
    # these directly). Match the exact copy from the plan.
    assert hwo_ctrl.label == "Notify on Hazardous Weather Outlook updates"
    assert sps_ctrl.label == "Notify on Special Weather Statement (informational)"


def test_tab_intro_copy_reflects_defaults_on_behavior(notifications_tab_panel):
    _tab, _dialog = notifications_tab_panel

    intro_labels = [st.label for st in _RecordedStaticText.instances]
    joined = "\n".join(intro_labels)

    # The rewritten intro must explicitly name HWO + SPS and say they default ON.
    assert "Hazardous Weather Outlook" in joined
    assert "Special Weather Statement" in joined
    assert "on by default" in joined
    # And preserve the old "others are off unless you turn them on" nuance.
    assert "off unless you turn them on" in joined


def test_load_populates_new_toggles_from_settings(notifications_tab_panel):
    tab, dialog = notifications_tab_panel

    settings = AppSettings()
    settings.notify_hwo_update = True
    settings.notify_sps_issued = False

    tab.load(settings)

    assert dialog._controls["notify_hwo_update"].GetValue() is True
    assert dialog._controls["notify_sps_issued"].GetValue() is False


def test_save_round_trips_new_toggle_state(notifications_tab_panel):
    tab, dialog = notifications_tab_panel

    dialog._controls["notify_hwo_update"].SetValue(False)
    dialog._controls["notify_sps_issued"].SetValue(True)

    payload = tab.save()

    assert payload["notify_hwo_update"] is False
    assert payload["notify_sps_issued"] is True
