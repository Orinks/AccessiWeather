from __future__ import annotations

import json
import logging
from pathlib import Path

from accessiweather.notifications.sound_pack_helpers import get_sound_entry
from accessiweather.sound_events import (
    FRIENDLY_SOUND_EVENT_CHOICES,
    KNOWN_SOUND_EVENT_KEYS,
    LEGACY_SOUND_EVENT_KEYS,
    USER_MUTABLE_SOUND_EVENT_KEYS,
)
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

    assert "unknown" in USER_MUTABLE_SOUND_EVENT_KEYS
    assert set(sounds) >= KNOWN_SOUND_EVENT_KEYS
    assert set(sounds) >= USER_MUTABLE_SOUND_EVENT_KEYS
    assert set(sounds) >= LEGACY_SOUND_EVENT_KEYS
    assert "severe_thunderstorm_watch" in sounds
    assert "thunderstorm_severe" in sounds
    assert "wind_watch" in sounds
    assert "wind_severe" in sounds

    for key, filename in sounds.items():
        sound_path = pack_json.parent / filename
        assert sound_path.exists(), f"{key} maps to missing file {filename}"


def test_missing_specific_event_uses_default_pack_event_before_selected_pack_notify(tmp_path):
    soundpacks_dir = tmp_path / "soundpacks"
    custom_pack = soundpacks_dir / "custom"
    default_pack = soundpacks_dir / "default"
    custom_pack.mkdir(parents=True)
    default_pack.mkdir(parents=True)
    (custom_pack / "notify.wav").write_bytes(b"custom notify")
    (default_pack / "notify.ogg").write_bytes(b"default notify")
    (custom_pack / "pack.json").write_text(
        json.dumps({"name": "Custom", "sounds": {"notify": "notify.wav"}}),
        encoding="utf-8",
    )
    (default_pack / "pack.json").write_text(
        json.dumps(
            {
                "name": "Default",
                "sounds": {"notify": "notify.ogg", "discussion_update": "notify.ogg"},
            }
        ),
        encoding="utf-8",
    )

    sound_file, _volume = get_sound_entry(
        "discussion_update",
        "custom",
        soundpacks_dir=soundpacks_dir,
        default_pack="default",
        logger=logging.getLogger(__name__),
    )

    assert sound_file == default_pack / "notify.ogg"
