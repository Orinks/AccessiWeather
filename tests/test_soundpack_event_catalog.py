from __future__ import annotations

import json
from pathlib import Path

from accessiweather.sound_events import FRIENDLY_SOUND_EVENT_CHOICES, USER_MUTABLE_SOUND_EVENT_KEYS
from accessiweather.ui.dialogs.soundpack_manager_models import FRIENDLY_ALERT_CATEGORIES
from accessiweather.ui.dialogs.soundpack_wizard_dialog import SoundPackWizardDialog


class _DummyCheckBox:
    def __init__(self) -> None:
        self.value = False

    def SetValue(self, value: bool) -> None:
        self.value = value


def test_soundpack_manager_uses_simplified_user_event_catalog():
    assert list(FRIENDLY_SOUND_EVENT_CHOICES) == FRIENDLY_ALERT_CATEGORIES

    category_keys = {key for _label, key in FRIENDLY_ALERT_CATEGORIES}
    assert category_keys == USER_MUTABLE_SOUND_EVENT_KEYS
    assert "tornado_warning" not in category_keys
    assert "warning" not in category_keys


def test_soundpack_wizard_common_selection_uses_simplified_events():
    wizard = SoundPackWizardDialog.__new__(SoundPackWizardDialog)
    keys = sorted(USER_MUTABLE_SOUND_EVENT_KEYS | {"tornado_warning", "warning"})
    checks = {key: _DummyCheckBox() for key in keys}
    wizard.category_checks = list(checks.items())

    SoundPackWizardDialog._select_common_alerts(wizard, event=None)

    for key in USER_MUTABLE_SOUND_EVENT_KEYS:
        assert checks[key].value is True
    assert checks["tornado_warning"].value is False
    assert checks["warning"].value is False


def test_default_pack_supports_all_visible_events_and_legacy_keys():
    pack_json = Path(__file__).parents[1] / "soundpacks" / "default" / "pack.json"
    pack_data = json.loads(pack_json.read_text(encoding="utf-8"))
    sounds = pack_data["sounds"]

    assert set(sounds) >= USER_MUTABLE_SOUND_EVENT_KEYS
    for key in ("warning", "watch", "advisory", "statement", "tornado_warning"):
        assert key in sounds

    for key, filename in sounds.items():
        sound_path = pack_json.parent / filename
        assert sound_path.exists(), f"{key} maps to missing file {filename}"
