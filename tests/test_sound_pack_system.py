"""Unit tests for the sound pack system."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import toga

from accessiweather.notifications.sound_player import (
    get_available_sound_packs,
    get_sound_file,
    play_notification_sound,
)


class TestSoundPackSystem:
    """Test cases for the sound pack system."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary directory for test sound packs
        self.temp_dir = tempfile.mkdtemp()
        self.soundpacks_dir = Path(self.temp_dir)

        # Create test sound packs
        self._create_test_sound_packs()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_sound_packs(self):
        """Create test sound pack directories and files."""
        # Default pack
        default_pack = self.soundpacks_dir / "default"
        default_pack.mkdir(parents=True, exist_ok=True)

        default_pack_json = {
            "name": "Default",
            "author": "Test Author",
            "description": "Default test sound pack",
            "sounds": {"alert": "alert.wav", "notify": "notify.wav"},
        }

        with open(default_pack / "pack.json", "w", encoding="utf-8") as f:
            json.dump(default_pack_json, f)

        # Create dummy sound files
        (default_pack / "alert.wav").touch()
        (default_pack / "notify.wav").touch()

        # Custom pack
        custom_pack = self.soundpacks_dir / "nature"
        custom_pack.mkdir(parents=True, exist_ok=True)

        custom_pack_json = {
            "name": "Nature Sounds",
            "author": "Nature Author",
            "description": "Relaxing nature sounds",
            "sounds": {"alert": "bird_chirp.wav", "notify": "water_drop.wav"},
        }

        with open(custom_pack / "pack.json", "w", encoding="utf-8") as f:
            json.dump(custom_pack_json, f)

        # Create dummy sound files
        (custom_pack / "bird_chirp.wav").touch()
        (custom_pack / "water_drop.wav").touch()

        # Broken pack (missing sound file)
        broken_pack = self.soundpacks_dir / "broken"
        broken_pack.mkdir(parents=True, exist_ok=True)

        broken_pack_json = {
            "name": "Broken Pack",
            "author": "Test Author",
            "description": "Pack with missing sound file",
            "sounds": {"alert": "missing.wav", "notify": "notify.wav"},
        }

        with open(broken_pack / "pack.json", "w", encoding="utf-8") as f:
            json.dump(broken_pack_json, f)

        # Only create one of the sound files
        (broken_pack / "notify.wav").touch()

    @patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR")
    def test_get_sound_file_default_pack(self, mock_soundpacks_dir):
        """Test getting sound file from default pack."""
        mock_soundpacks_dir.__truediv__ = lambda self, other: self.soundpacks_dir / other
        mock_soundpacks_dir.return_value = self.soundpacks_dir

        # Mock the SOUNDPACKS_DIR to use our test directory
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            sound_file = get_sound_file("alert", "default")

            assert sound_file is not None
            assert sound_file.name == "alert.wav"
            assert sound_file.exists()

    @patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR")
    def test_get_sound_file_custom_pack(self, mock_soundpacks_dir):
        """Test getting sound file from custom pack."""
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            sound_file = get_sound_file("alert", "nature")

            assert sound_file is not None
            assert sound_file.name == "bird_chirp.wav"
            assert sound_file.exists()

    @patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR")
    def test_get_sound_file_fallback_to_default(self, mock_soundpacks_dir):
        """Test fallback to default pack when sound file is missing."""
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            # Try to get missing sound from broken pack
            sound_file = get_sound_file("alert", "broken")

            # Should fallback to default pack
            assert sound_file is not None
            assert sound_file.name == "alert.wav"
            assert "default" in str(sound_file.parent)

    @patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR")
    def test_get_sound_file_nonexistent_pack(self, mock_soundpacks_dir):
        """Test getting sound file from non-existent pack."""
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            sound_file = get_sound_file("alert", "nonexistent")

            # Should fallback to default pack
            assert sound_file is not None
            assert sound_file.name == "alert.wav"
            assert "default" in str(sound_file.parent)

    @patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR")
    def test_get_sound_file_nonexistent_event(self, mock_soundpacks_dir):
        """Test getting sound file for non-existent event."""
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            sound_file = get_sound_file("nonexistent_event", "default")

            # Should return None since the event doesn't exist and no fallback file
            assert sound_file is None

    @patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR")
    def test_get_sound_packs(self, mock_soundpacks_dir):
        """Test getting list of available sound packs."""
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            sound_packs = get_available_sound_packs()

            assert isinstance(sound_packs, dict)
            assert "default" in sound_packs
            assert "nature" in sound_packs
            assert "broken" in sound_packs

            # Check pack metadata
            assert sound_packs["default"]["name"] == "Default"
            assert sound_packs["nature"]["name"] == "Nature Sounds"
            assert sound_packs["default"]["author"] == "Test Author"

    @patch("accessiweather.notifications.sound_player.winsound")
    @patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR")
    def test_play_notification_sound_success(self, mock_soundpacks_dir, mock_winsound):
        """Test successful sound playback using winsound on Windows."""
        with (
            patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir),
            patch(
                "accessiweather.notifications.sound_player.platform.system", return_value="Windows"
            ),
        ):
            play_notification_sound("alert", "default")

            # Verify winsound.PlaySound was called (primary method on Windows)
            mock_winsound.PlaySound.assert_called_once()
            args, kwargs = mock_winsound.PlaySound.call_args
            assert str(args[0]).endswith("alert.wav")
            assert args[1] == mock_winsound.SND_FILENAME | mock_winsound.SND_ASYNC

    @patch("accessiweather.notifications.sound_player.playsound")
    @patch("accessiweather.notifications.sound_player.winsound")
    @patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR")
    def test_play_notification_sound_fallback_to_playsound(
        self, mock_soundpacks_dir, mock_winsound, mock_playsound
    ):
        """Test fallback to playsound when winsound fails."""
        with (
            patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir),
            patch(
                "accessiweather.notifications.sound_player.platform.system", return_value="Windows"
            ),
        ):
            # Make winsound.PlaySound raise an exception to trigger fallback
            mock_winsound.PlaySound.side_effect = Exception("Winsound failed")

            play_notification_sound("alert", "default")

            # Verify winsound was tried first
            mock_winsound.PlaySound.assert_called_once()

            # Verify playsound was called as fallback
            mock_playsound.assert_called_once()
            args, kwargs = mock_playsound.call_args
            assert str(args[0]).endswith("alert.wav")
            assert kwargs.get("block") is False

    @patch("accessiweather.notifications.sound_player.playsound")
    @patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR")
    def test_play_notification_sound_no_playsound(self, mock_soundpacks_dir, mock_playsound):
        """Test sound playback when playsound is not available."""
        with patch("accessiweather.notifications.sound_player.playsound", None):
            # Should not raise an exception
            play_notification_sound("alert", "default")

    @patch("accessiweather.notifications.sound_player.playsound")
    @patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR")
    def test_play_notification_sound_exception(self, mock_soundpacks_dir, mock_playsound):
        """Test sound playback when playsound raises an exception."""
        mock_playsound.side_effect = Exception("Playback failed")

        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            # Should not raise an exception, just log the error
            play_notification_sound("alert", "default")

    def test_sound_pack_json_validation(self):
        """Test validation of sound pack JSON files."""
        # Test with invalid JSON
        invalid_pack = self.soundpacks_dir / "invalid"
        invalid_pack.mkdir(parents=True, exist_ok=True)

        with open(invalid_pack / "pack.json", "w", encoding="utf-8") as f:
            f.write("invalid json content")

        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            sound_file = get_sound_file("alert", "invalid")

            # Should fallback to default pack when JSON is invalid
            # The function returns None when it can't read the pack and there's no default fallback
            # This is expected behavior for invalid JSON
            assert sound_file is not None
            assert "default" in str(sound_file.parent)

    def test_sound_pack_metadata_extraction(self):
        """Test extraction of sound pack metadata."""
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            sound_packs = get_available_sound_packs()

            nature_pack = sound_packs.get("nature")
            assert nature_pack is not None
            assert nature_pack["name"] == "Nature Sounds"
            assert nature_pack["author"] == "Nature Author"
            assert nature_pack["description"] == "Relaxing nature sounds"
            assert "alert" in nature_pack["sounds"]
            assert "notify" in nature_pack["sounds"]


class TestSoundPackManagerDialog:
    """Test cases for the sound pack manager dialog."""

    def setup_method(self):
        """Set up test fixtures with Toga dummy backend."""
        # Set up the dummy backend for Toga
        import os

        os.environ["TOGA_BACKEND"] = "toga_dummy"

        toga.App.app = None
        self.app = toga.App("Test App", "org.example.test")

    def teardown_method(self):
        """Clean up test fixtures."""
        toga.App.app = None

    def test_dialog_initialization(self):
        """Test sound pack manager dialog initialization."""
        # Import here to avoid import issues during test collection
        from accessiweather.dialogs.soundpack_manager_dialog import SoundPackManagerDialog

        # Mock the _create_dialog method to avoid complex UI setup
        with patch.object(SoundPackManagerDialog, "_create_dialog"):
            dialog = SoundPackManagerDialog(self.app, "default")
            assert dialog.app == self.app
            assert dialog.current_pack == "default"

    def test_sound_pack_loading(self):
        """Test loading of sound packs in the dialog."""
        # Create temporary sound packs
        temp_dir = tempfile.mkdtemp()
        soundpacks_dir = Path(temp_dir)

        # Create a test pack
        test_pack = soundpacks_dir / "test"
        test_pack.mkdir(parents=True, exist_ok=True)

        pack_json = {
            "name": "Test Pack",
            "author": "Test Author",
            "description": "Test description",
            "sounds": {"alert": "test_alert.wav"},
        }

        with open(test_pack / "pack.json", "w", encoding="utf-8") as f:
            json.dump(pack_json, f)

        (test_pack / "test_alert.wav").touch()

        from accessiweather.dialogs.soundpack_manager_dialog import SoundPackManagerDialog

        # Mock the _create_dialog method and patch the soundpacks directory
        with patch.object(SoundPackManagerDialog, "_create_dialog"):
            # Create dialog instance
            dialog = SoundPackManagerDialog(self.app, "default")

            # Override the soundpacks directory after initialization
            dialog.soundpacks_dir = soundpacks_dir

            # Reload sound packs with the new directory
            dialog._load_sound_packs()

            # Should have loaded the test pack
            assert "test" in dialog.sound_packs
            assert dialog.sound_packs["test"]["name"] == "Test Pack"

        # Clean up
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


# --- New tests for alert sound mapping and candidate resolution ---
from accessiweather.models import WeatherAlert
from accessiweather.notifications.alert_sound_mapper import (
    get_candidate_sound_events,
)
from accessiweather.notifications.sound_player import (
    get_sound_file_for_candidates,
)


def test_alert_sound_mapper_candidates_warning_first():
    """Alert with 'Warning' in event should prefer type over severity."""
    alert = WeatherAlert(
        title="Tornado Warning",
        description="",
        severity="Severe",
        event="Tornado Warning",
    )
    candidates = get_candidate_sound_events(alert)
    # First candidate should be 'warning'
    assert candidates[0] == "warning"
    # Should include severity and generic fallbacks
    assert "severe" in candidates
    assert candidates[-2:] == ["alert", "notify"]


def test_alert_sound_mapper_candidates_watch():
    alert = WeatherAlert(
        title="Flood Watch",
        description="",
        severity="Moderate",
        event="Flood Watch",
    )
    candidates = get_candidate_sound_events(alert)
    assert candidates[0] == "watch"
    assert "moderate" in candidates


def test_get_sound_file_for_candidates_resolution(tmp_path):
    """Resolver should pick first available key in pack, falling back appropriately."""
    # Create a test pack
    pack_dir = tmp_path / "theme"
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack_json = {
        "name": "Theme",
        "sounds": {
            # Intentionally omit 'warning' to force fallback to 'severe'
            "severe": "sev.wav",
            "alert": "alert.wav",
        },
    }
    (pack_dir / "sev.wav").write_bytes(b"x")
    (pack_dir / "alert.wav").write_bytes(b"y")
    import json as _json

    with open(pack_dir / "pack.json", "w", encoding="utf-8") as f:
        _json.dump(pack_json, f)

    # Patch SOUNDPACKS_DIR to tmp dir containing our pack and a default
    default_dir = tmp_path / "default"
    default_dir.mkdir(exist_ok=True)
    with open(default_dir / "pack.json", "w", encoding="utf-8") as f:
        _json.dump({"name": "Default", "sounds": {"alert": "alert.wav"}}, f)
    (default_dir / "alert.wav").write_bytes(b"z")

    from unittest.mock import patch as _patch

    with _patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", tmp_path):
        # Prefer 'severe' since 'warning' missing in pack
        p = get_sound_file_for_candidates(["warning", "severe", "alert"], "theme")
        assert p is not None
        assert p.name == "sev.wav"

        # If candidate only 'warning', should fall back to 'alert' (present in pack)
        p2 = get_sound_file_for_candidates(["warning"], "theme")
        assert p2 is not None
        assert p2.name == "alert.wav"

        # If pack missing both, fall back to default's alert
        p3 = get_sound_file_for_candidates(["warning", "watch"], "theme")
        assert p3 is not None
        assert p3.parent.name == "default"
        assert p3.name == "alert.wav"


if __name__ == "__main__":
    pytest.main([__file__])
