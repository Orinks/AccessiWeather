"""
Tests for sound_player module.

Tests the PreviewPlayer class and sound playback functionality,
including sound_lib integration and unavailable-backend handling.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.notifications.sound_player import SOUND_LIB_AVAILABLE


class TestPreviewPlayerInit:
    """Test PreviewPlayer initialization."""

    def test_init_creates_instance(self):
        """PreviewPlayer should initialize with default state."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()
        assert player._current_stream is None
        assert player._is_playing is False

    def test_is_playing_initially_false(self):
        """is_playing should return False initially."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()
        assert player.is_playing() is False


class TestPreviewPlayerWithSoundLib:
    """Test PreviewPlayer with sound_lib backend."""

    def test_play_with_sound_lib_creates_stream(self):
        """Playing with sound_lib should create a FileStream."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()

        # Create a mock stream module
        mock_stream_module = MagicMock()
        mock_file_stream = MagicMock()
        mock_stream_module.FileStream.return_value = mock_file_stream

        # Create temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            import sound_lib as _sl

            with (
                patch.dict("sys.modules", {"sound_lib.stream": mock_stream_module}),
                patch.object(_sl, "stream", mock_stream_module, create=True),
                patch(
                    "accessiweather.notifications.sound_player.stream",
                    mock_stream_module,
                    create=True,
                ),
            ):
                # Manually call the internal method
                player._play_with_sound_lib(temp_path)

            # Verify play was called on the stream
            mock_file_stream.play.assert_called_once()
            assert player._is_playing is True
        finally:
            temp_path.unlink(missing_ok=True)

    def test_play_with_sound_lib_sets_current_stream(self):
        """Playing should set _current_stream."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()

        mock_stream_module = MagicMock()
        mock_file_stream = MagicMock()
        mock_stream_module.FileStream.return_value = mock_file_stream

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            import sound_lib as _sl

            with (
                patch.dict("sys.modules", {"sound_lib.stream": mock_stream_module}),
                patch.object(_sl, "stream", mock_stream_module, create=True),
                patch(
                    "accessiweather.notifications.sound_player.stream",
                    mock_stream_module,
                    create=True,
                ),
            ):
                player._play_with_sound_lib(temp_path)

            assert player._current_stream is not None
        finally:
            temp_path.unlink(missing_ok=True)

    def test_stop_stops_and_frees_stream(self):
        """stop() should stop and free the current stream."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()

        # Set up a mock stream
        mock_stream = MagicMock()
        player._current_stream = mock_stream
        player._is_playing = True

        player.stop()

        mock_stream.stop.assert_called_once()
        mock_stream.free.assert_called_once()
        assert player._current_stream is None
        assert player._is_playing is False

    def test_stop_handles_exception_gracefully(self):
        """stop() should handle exceptions without crashing."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()

        mock_stream = MagicMock()
        mock_stream.stop.side_effect = Exception("Stop failed")
        player._current_stream = mock_stream
        player._is_playing = True

        # Should not raise
        player.stop()

        assert player._current_stream is None
        assert player._is_playing is False

    def test_is_playing_checks_stream_property(self):
        """is_playing should check the stream's is_playing property."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()

        mock_stream = MagicMock()
        mock_stream.is_playing = True
        player._current_stream = mock_stream

        assert player.is_playing() is True

        mock_stream.is_playing = False
        assert player.is_playing() is False


class TestPreviewPlayerPlay:
    """Test PreviewPlayer.play() method."""

    def test_play_stops_current_playback_first(self):
        """play() should stop current playback before starting new."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()
        player.stop = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with (
                patch("accessiweather.notifications.sound_player.SOUND_LIB_AVAILABLE", False),
            ):
                player.play(temp_path)

            player.stop.assert_called_once()
        finally:
            temp_path.unlink(missing_ok=True)

    def test_play_returns_false_for_nonexistent_file(self):
        """play() should return False for non-existent files."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()
        result = player.play(Path("/nonexistent/file.wav"))
        assert result is False

    def test_play_prefers_sound_lib(self):
        """play() should prefer sound_lib when available."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()
        player._play_with_sound_lib = MagicMock(return_value=True)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with patch("accessiweather.notifications.sound_player.SOUND_LIB_AVAILABLE", True):
                player.play(temp_path)

            player._play_with_sound_lib.assert_called_once()
        finally:
            temp_path.unlink(missing_ok=True)

    def test_play_returns_false_when_sound_lib_unavailable(self):
        """play() should fail cleanly when sound_lib is unavailable."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()
        player._play_with_sound_lib = MagicMock(return_value=True)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with patch("accessiweather.notifications.sound_player.SOUND_LIB_AVAILABLE", False):
                result = player.play(temp_path)

            player._play_with_sound_lib.assert_not_called()
            assert result is False
        finally:
            temp_path.unlink(missing_ok=True)


class TestPreviewPlayerToggle:
    """Test PreviewPlayer.toggle() method."""

    def test_toggle_starts_playback_when_stopped(self):
        """toggle() should start playback when not playing."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()
        player.is_playing = MagicMock(return_value=False)
        player.play = MagicMock(return_value=True)
        player.stop = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            result = player.toggle(temp_path)

            player.play.assert_called_once_with(temp_path)
            player.stop.assert_not_called()
            assert result is True
        finally:
            temp_path.unlink(missing_ok=True)

    def test_toggle_stops_playback_when_playing(self):
        """toggle() should stop playback when already playing."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()
        player.is_playing = MagicMock(return_value=True)
        player.play = MagicMock()
        player.stop = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            result = player.toggle(temp_path)

            player.stop.assert_called_once()
            player.play.assert_not_called()
            assert result is False
        finally:
            temp_path.unlink(missing_ok=True)


class TestGetPreviewPlayer:
    """Test get_preview_player() function."""

    def test_returns_singleton(self):
        """get_preview_player() should return the same instance."""
        import accessiweather.notifications.sound_player as sp

        # Reset global
        sp._preview_player = None

        player1 = sp.get_preview_player()
        player2 = sp.get_preview_player()

        assert player1 is player2

    def test_creates_preview_player(self):
        """get_preview_player() should create a PreviewPlayer instance."""
        import accessiweather.notifications.sound_player as sp

        sp._preview_player = None

        player = sp.get_preview_player()

        assert isinstance(player, sp.PreviewPlayer)


class TestSoundPackFunctions:
    """Test sound pack related functions."""

    def test_validate_sound_pack_missing_directory(self):
        """validate_sound_pack should fail for missing directory."""
        from accessiweather.notifications.sound_player import validate_sound_pack

        is_valid, msg = validate_sound_pack(Path("/nonexistent/pack"))

        assert is_valid is False
        assert "does not exist" in msg

    def test_validate_sound_pack_missing_pack_json(self):
        """validate_sound_pack should fail for missing pack.json."""
        from accessiweather.notifications.sound_player import validate_sound_pack

        with tempfile.TemporaryDirectory() as tmpdir:
            pack_path = Path(tmpdir)
            is_valid, msg = validate_sound_pack(pack_path)

        assert is_valid is False
        assert "pack.json" in msg

    def test_validate_sound_pack_valid(self):
        """validate_sound_pack should pass for valid pack."""
        from accessiweather.notifications.sound_player import validate_sound_pack

        with tempfile.TemporaryDirectory() as tmpdir:
            pack_path = Path(tmpdir)

            # Create pack.json
            pack_data = {"name": "Test Pack", "sounds": {"alert": "alert.wav"}}
            (pack_path / "pack.json").write_text(json.dumps(pack_data))

            # Create sound file
            (pack_path / "alert.wav").touch()

            is_valid, msg = validate_sound_pack(pack_path)

        assert is_valid is True
        assert "valid" in msg.lower()

    def test_validate_sound_pack_missing_sound_file(self):
        """validate_sound_pack should fail for missing sound files."""
        from accessiweather.notifications.sound_player import validate_sound_pack

        with tempfile.TemporaryDirectory() as tmpdir:
            pack_path = Path(tmpdir)

            # Create pack.json with missing sound
            pack_data = {"name": "Test Pack", "sounds": {"alert": "missing.wav"}}
            (pack_path / "pack.json").write_text(json.dumps(pack_data))

            is_valid, msg = validate_sound_pack(pack_path)

        assert is_valid is False
        assert "missing" in msg.lower()


class TestAvailabilityChecks:
    """Test availability check functions."""

    def test_is_sound_lib_available(self):
        """is_sound_lib_available should report sound_lib backend availability."""
        from accessiweather.notifications.sound_player import (
            SOUND_LIB_AVAILABLE,
            is_sound_lib_available,
        )

        assert is_sound_lib_available() is SOUND_LIB_AVAILABLE


class TestParseSoundEntry:
    """Test _parse_sound_entry function for volume parsing."""

    def test_parse_string_entry_default_volume(self):
        """String entry should default to volume 1.0."""
        from accessiweather.notifications.sound_player import _parse_sound_entry

        filename, volume = _parse_sound_entry("alert.wav", "alert")
        assert filename == "alert.wav"
        assert volume == 1.0

    def test_parse_string_entry_with_volumes_dict(self):
        """String entry with volumes dict should use dict value."""
        from accessiweather.notifications.sound_player import _parse_sound_entry

        volumes = {"alert": 0.7}
        filename, volume = _parse_sound_entry("alert.wav", "alert", volumes)
        assert filename == "alert.wav"
        assert volume == 0.7

    def test_parse_inline_dict_entry(self):
        """Inline dict entry should parse file and volume."""
        from accessiweather.notifications.sound_player import _parse_sound_entry

        entry = {"file": "critical_alert.wav", "volume": 0.5}
        filename, volume = _parse_sound_entry(entry, "critical_alert")
        assert filename == "critical_alert.wav"
        assert volume == 0.5

    def test_parse_inline_dict_entry_missing_volume(self):
        """Inline dict without volume should default to 1.0."""
        from accessiweather.notifications.sound_player import _parse_sound_entry

        entry = {"file": "alert.wav"}
        filename, volume = _parse_sound_entry(entry, "alert")
        assert filename == "alert.wav"
        assert volume == 1.0

    def test_parse_inline_dict_entry_missing_file(self):
        """Inline dict without file should use event name as default."""
        from accessiweather.notifications.sound_player import _parse_sound_entry

        entry = {"volume": 0.8}
        filename, volume = _parse_sound_entry(entry, "warning")
        assert filename == "warning.ogg"
        assert volume == 0.8

    def test_parse_volume_clamped_above_one(self):
        """Volume above 1.0 should be clamped to 1.0."""
        from accessiweather.notifications.sound_player import _parse_sound_entry

        entry = {"file": "alert.wav", "volume": 1.5}
        filename, volume = _parse_sound_entry(entry, "alert")
        assert volume == 1.0

    def test_parse_volume_clamped_below_zero(self):
        """Volume below 0.0 should be clamped to 0.0."""
        from accessiweather.notifications.sound_player import _parse_sound_entry

        entry = {"file": "alert.wav", "volume": -0.5}
        filename, volume = _parse_sound_entry(entry, "alert")
        assert volume == 0.0

    def test_parse_invalid_volume_defaults_to_one(self):
        """Invalid volume type should default to 1.0."""
        from accessiweather.notifications.sound_player import _parse_sound_entry

        entry = {"file": "alert.wav", "volume": "loud"}
        filename, volume = _parse_sound_entry(entry, "alert")
        assert volume == 1.0

    def test_parse_empty_string_entry(self):
        """Empty string entry should use event name as default."""
        from accessiweather.notifications.sound_player import _parse_sound_entry

        filename, volume = _parse_sound_entry("", "alert")
        assert filename == "alert.ogg"
        assert volume == 1.0


class TestGetSoundEntry:
    """Test get_sound_entry function."""

    def test_get_sound_entry_string_format(self):
        """get_sound_entry should handle string sound entries."""
        from accessiweather.notifications.sound_player import (
            get_sound_entry,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Temporarily override SOUNDPACKS_DIR
            import accessiweather.notifications.sound_player as sp

            original_dir = sp.SOUNDPACKS_DIR
            sp.SOUNDPACKS_DIR = Path(tmpdir)

            try:
                pack_path = Path(tmpdir) / "test_pack"
                pack_path.mkdir()

                pack_data = {"name": "Test", "sounds": {"alert": "alert.wav"}}
                (pack_path / "pack.json").write_text(json.dumps(pack_data))
                (pack_path / "alert.wav").touch()

                sound_file, volume = get_sound_entry("alert", "test_pack")

                assert sound_file is not None
                assert sound_file.name == "alert.wav"
                assert volume == 1.0
            finally:
                sp.SOUNDPACKS_DIR = original_dir

    def test_get_sound_entry_inline_volume_format(self):
        """get_sound_entry should handle inline volume format."""
        from accessiweather.notifications.sound_player import get_sound_entry

        with tempfile.TemporaryDirectory() as tmpdir:
            import accessiweather.notifications.sound_player as sp

            original_dir = sp.SOUNDPACKS_DIR
            sp.SOUNDPACKS_DIR = Path(tmpdir)

            try:
                pack_path = Path(tmpdir) / "test_pack"
                pack_path.mkdir()

                pack_data = {
                    "name": "Test",
                    "sounds": {"critical": {"file": "critical.wav", "volume": 0.7}},
                }
                (pack_path / "pack.json").write_text(json.dumps(pack_data))
                (pack_path / "critical.wav").touch()

                sound_file, volume = get_sound_entry("critical", "test_pack")

                assert sound_file is not None
                assert sound_file.name == "critical.wav"
                assert volume == 0.7
            finally:
                sp.SOUNDPACKS_DIR = original_dir

    def test_get_sound_entry_separate_volumes_format(self):
        """get_sound_entry should handle separate volumes section."""
        from accessiweather.notifications.sound_player import get_sound_entry

        with tempfile.TemporaryDirectory() as tmpdir:
            import accessiweather.notifications.sound_player as sp

            original_dir = sp.SOUNDPACKS_DIR
            sp.SOUNDPACKS_DIR = Path(tmpdir)

            try:
                pack_path = Path(tmpdir) / "test_pack"
                pack_path.mkdir()

                pack_data = {
                    "name": "Test",
                    "sounds": {"alert": "alert.wav"},
                    "volumes": {"alert": 0.6},
                }
                (pack_path / "pack.json").write_text(json.dumps(pack_data))
                (pack_path / "alert.wav").touch()

                sound_file, volume = get_sound_entry("alert", "test_pack")

                assert sound_file is not None
                assert sound_file.name == "alert.wav"
                assert volume == 0.6
            finally:
                sp.SOUNDPACKS_DIR = original_dir

    def test_get_sound_entry_missing_sound_returns_none(self):
        """get_sound_entry should return (None, 1.0) for missing sounds."""
        from accessiweather.notifications.sound_player import get_sound_entry

        with tempfile.TemporaryDirectory() as tmpdir:
            import accessiweather.notifications.sound_player as sp

            original_dir = sp.SOUNDPACKS_DIR
            sp.SOUNDPACKS_DIR = Path(tmpdir)

            try:
                # Create a pack without default pack for fallback
                pack_path = Path(tmpdir) / "default"
                pack_path.mkdir()

                pack_data = {"name": "Default", "sounds": {}}
                (pack_path / "pack.json").write_text(json.dumps(pack_data))

                sound_file, volume = get_sound_entry("nonexistent", "default")

                assert sound_file is None
                assert volume == 1.0
            finally:
                sp.SOUNDPACKS_DIR = original_dir

    def test_get_sound_entry_for_candidates_falls_back_within_pack(self):
        """Candidate lookup should use the next available event in the selected pack."""
        from accessiweather.notifications.sound_player import get_sound_entry_for_candidates

        with tempfile.TemporaryDirectory() as tmpdir:
            import accessiweather.notifications.sound_player as sp

            original_dir = sp.SOUNDPACKS_DIR
            sp.SOUNDPACKS_DIR = Path(tmpdir)

            try:
                pack_path = Path(tmpdir) / "test_pack"
                pack_path.mkdir()
                default_path = Path(tmpdir) / "default"
                default_path.mkdir()

                pack_data = {"name": "Test", "sounds": {"alert": "alert.wav"}}
                (pack_path / "pack.json").write_text(json.dumps(pack_data))
                (pack_path / "alert.wav").touch()

                default_data = {"name": "Default", "sounds": {"severe": "severe.wav"}}
                (default_path / "pack.json").write_text(json.dumps(default_data))
                (default_path / "severe.wav").touch()

                sound_file, volume = get_sound_entry_for_candidates(
                    ["severe", "alert", "notify"], "test_pack"
                )

                assert sound_file is not None
                assert sound_file.parent == pack_path
                assert sound_file.name == "alert.wav"
                assert volume == 1.0
            finally:
                sp.SOUNDPACKS_DIR = original_dir


class TestValidateSoundPackWithVolume:
    """Test validate_sound_pack with volume-related fields."""

    def test_validate_pack_with_inline_volume(self):
        """validate_sound_pack should accept inline volume format."""
        from accessiweather.notifications.sound_player import validate_sound_pack

        with tempfile.TemporaryDirectory() as tmpdir:
            pack_path = Path(tmpdir)

            pack_data = {
                "name": "Test Pack",
                "sounds": {"alert": {"file": "alert.wav", "volume": 0.8}},
            }
            (pack_path / "pack.json").write_text(json.dumps(pack_data))
            (pack_path / "alert.wav").touch()

            is_valid, msg = validate_sound_pack(pack_path)

        assert is_valid is True

    def test_validate_pack_with_separate_volumes(self):
        """validate_sound_pack should accept separate volumes section."""
        from accessiweather.notifications.sound_player import validate_sound_pack

        with tempfile.TemporaryDirectory() as tmpdir:
            pack_path = Path(tmpdir)

            pack_data = {
                "name": "Test Pack",
                "sounds": {"alert": "alert.wav"},
                "volumes": {"alert": 0.7},
            }
            (pack_path / "pack.json").write_text(json.dumps(pack_data))
            (pack_path / "alert.wav").touch()

            is_valid, msg = validate_sound_pack(pack_path)

        assert is_valid is True

    def test_validate_pack_with_invalid_volume_value(self):
        """validate_sound_pack should reject invalid volume values."""
        from accessiweather.notifications.sound_player import validate_sound_pack

        with tempfile.TemporaryDirectory() as tmpdir:
            pack_path = Path(tmpdir)

            pack_data = {
                "name": "Test Pack",
                "sounds": {"alert": "alert.wav"},
                "volumes": {"alert": 1.5},  # Invalid: > 1.0
            }
            (pack_path / "pack.json").write_text(json.dumps(pack_data))
            (pack_path / "alert.wav").touch()

            is_valid, msg = validate_sound_pack(pack_path)

        assert is_valid is False
        assert "0.0 and 1.0" in msg

    def test_validate_pack_with_invalid_volume_type(self):
        """validate_sound_pack should reject non-numeric volume values."""
        from accessiweather.notifications.sound_player import validate_sound_pack

        with tempfile.TemporaryDirectory() as tmpdir:
            pack_path = Path(tmpdir)

            pack_data = {
                "name": "Test Pack",
                "sounds": {"alert": "alert.wav"},
                "volumes": {"alert": "loud"},  # Invalid: not a number
            }
            (pack_path / "pack.json").write_text(json.dumps(pack_data))
            (pack_path / "alert.wav").touch()

            is_valid, msg = validate_sound_pack(pack_path)

        assert is_valid is False
        assert "Invalid volume" in msg


class TestGetSoundPackSoundsWithVolume:
    """Test get_sound_pack_sounds handles volume formats."""

    def test_get_sounds_normalizes_inline_format(self):
        """get_sound_pack_sounds should return just filenames for inline format."""
        from accessiweather.notifications.sound_player import get_sound_pack_sounds

        with tempfile.TemporaryDirectory() as tmpdir:
            import accessiweather.notifications.sound_player as sp

            original_dir = sp.SOUNDPACKS_DIR
            sp.SOUNDPACKS_DIR = Path(tmpdir)

            try:
                pack_path = Path(tmpdir) / "test_pack"
                pack_path.mkdir()

                pack_data = {
                    "name": "Test",
                    "sounds": {
                        "alert": {"file": "alert.wav", "volume": 0.8},
                        "warning": "warning.wav",
                    },
                }
                (pack_path / "pack.json").write_text(json.dumps(pack_data))

                sounds = get_sound_pack_sounds("test_pack")

                assert sounds["alert"] == "alert.wav"
                assert sounds["warning"] == "warning.wav"
            finally:
                sp.SOUNDPACKS_DIR = original_dir


class TestSoundPackSpecificAlertMode:
    """Test sound pack detection for specific alert sound mode."""

    def test_legacy_alert_keys_enable_specific_alert_sounds(self):
        from accessiweather.notifications.sound_player import (
            sound_pack_uses_specific_alert_sounds,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            import accessiweather.notifications.sound_player as sp

            original_dir = sp.SOUNDPACKS_DIR
            sp.SOUNDPACKS_DIR = Path(tmpdir)

            try:
                pack_path = Path(tmpdir) / "old_pack"
                pack_path.mkdir()
                pack_data = {
                    "name": "Old Pack",
                    "sounds": {
                        "alert": "alert.wav",
                        "tornado_warning": "tornado.wav",
                    },
                }
                (pack_path / "pack.json").write_text(json.dumps(pack_data))

                assert sound_pack_uses_specific_alert_sounds("old_pack") is True
            finally:
                sp.SOUNDPACKS_DIR = original_dir

    def test_severity_only_pack_does_not_enable_specific_alert_sounds(self):
        from accessiweather.notifications.sound_player import (
            sound_pack_uses_specific_alert_sounds,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            import accessiweather.notifications.sound_player as sp

            original_dir = sp.SOUNDPACKS_DIR
            sp.SOUNDPACKS_DIR = Path(tmpdir)

            try:
                pack_path = Path(tmpdir) / "new_pack"
                pack_path.mkdir()
                pack_data = {
                    "name": "New Pack",
                    "sounds": {
                        "alert": "alert.wav",
                        "severe": "severe.wav",
                    },
                }
                (pack_path / "pack.json").write_text(json.dumps(pack_data))

                assert sound_pack_uses_specific_alert_sounds("new_pack") is False
            finally:
                sp.SOUNDPACKS_DIR = original_dir

    def test_pack_manifest_can_explicitly_enable_specific_alert_sounds(self):
        from accessiweather.notifications.sound_player import (
            sound_pack_uses_specific_alert_sounds,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            import accessiweather.notifications.sound_player as sp

            original_dir = sp.SOUNDPACKS_DIR
            sp.SOUNDPACKS_DIR = Path(tmpdir)

            try:
                pack_path = Path(tmpdir) / "declared_pack"
                pack_path.mkdir()
                pack_data = {
                    "name": "Declared Pack",
                    "specific_alert_sounds": True,
                    "sounds": {
                        "alert": "alert.wav",
                        "severe": "severe.wav",
                    },
                }
                (pack_path / "pack.json").write_text(json.dumps(pack_data))

                assert sound_pack_uses_specific_alert_sounds("declared_pack") is True
            finally:
                sp.SOUNDPACKS_DIR = original_dir


class TestPlaySoundFileWithVolume:
    """Test _play_sound_file with volume parameter."""

    def test_play_sound_file_clamps_volume(self):
        """_play_sound_file should clamp volume to 0.0-1.0."""
        from accessiweather.notifications.sound_player import _play_sound_file

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_stream_module = MagicMock()
            mock_file_stream = MagicMock()
            mock_file_stream.is_playing = False
            mock_stream_module.FileStream.return_value = mock_file_stream
            with (
                patch("accessiweather.notifications.sound_player.SOUND_LIB_AVAILABLE", True),
                patch.dict("sys.modules", {"sound_lib.stream": mock_stream_module}),
            ):
                _play_sound_file(temp_path, volume=1.5)
                assert mock_file_stream.volume == 1.0
        finally:
            temp_path.unlink(missing_ok=True)

    def test_play_sound_file_reinitializes_sound_lib_after_first_stream_failure(self):
        """A stale post-resume sound_lib output should be reinitialized and retried once."""
        from accessiweather.notifications.sound_player import _play_sound_file

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            mock_stream_module = MagicMock()
            mock_file_stream = MagicMock()
            mock_file_stream.is_playing = False
            mock_stream_module.FileStream.side_effect = [
                RuntimeError("BASS device unavailable after resume"),
                mock_file_stream,
            ]
            mock_output_module = MagicMock()
            stale_output = MagicMock()
            fresh_output = MagicMock()
            mock_output_module.Output.return_value = fresh_output

            with (
                patch("accessiweather.notifications.sound_player.SOUND_LIB_AVAILABLE", True),
                patch("accessiweather.notifications.sound_player._sound_lib_output", stale_output),
                patch.dict(
                    "sys.modules",
                    {
                        "sound_lib.stream": mock_stream_module,
                        "sound_lib.output": mock_output_module,
                    },
                ),
            ):
                result = _play_sound_file(temp_path, volume=0.5)

            assert result is True
            assert mock_stream_module.FileStream.call_count == 2
            stale_output.free.assert_called_once()
            mock_output_module.Output.assert_called_once()
            mock_file_stream.play.assert_called_once()
            assert mock_file_stream.volume == 0.5
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.skipif(
        not SOUND_LIB_AVAILABLE,
        reason="sound_lib not available or working on this system",
    )
    def test_play_sound_file_uses_sound_lib_for_volume(self):
        """
        _play_sound_file should use sound_lib when volume < 1.0.

        NOTE: This test requires a working sound_lib installation with audio output.
        It's skipped on headless systems (CI) where sound_lib can't initialize properly.
        The volume parsing logic is tested separately in TestParseSoundEntry.
        """
        from accessiweather.notifications.sound_player import _play_sound_file

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # This is an integration test that requires working audio
            # Just verify no exception is raised
            result = _play_sound_file(temp_path, volume=0.5)
            # Result may be True or False depending on audio availability
            assert isinstance(result, bool)
        finally:
            temp_path.unlink(missing_ok=True)


class TestUserLevelMute:
    """Test user-level event muting in the sound player."""

    def test_play_notification_sound_skips_muted_event(self):
        """Muted events should never reach the playback backend."""
        from accessiweather.notifications.sound_player import play_notification_sound

        with patch("accessiweather.notifications.sound_player._play_sound_file") as mock_play:
            play_notification_sound("data_updated", "default", muted_events=["data_updated"])

        mock_play.assert_not_called()

    def test_play_notification_sound_candidates_skips_muted_logical_event(self):
        """Candidate playback should skip entirely when the logical event is muted."""
        from accessiweather.notifications.sound_player import play_notification_sound_candidates

        with patch("accessiweather.notifications.sound_player._play_sound_file") as mock_play:
            play_notification_sound_candidates(
                ["discussion_update", "notify"],
                "default",
                logical_event="discussion_update",
                muted_events=["discussion_update"],
            )

        mock_play.assert_not_called()


class TestSilentPlaybackBypassesBackend:
    """Test that silent events do not reach the playback backend."""

    def test_volume_zero_returns_without_sound_lib(self):
        """Volume zero should be treated as a silent no-op."""
        from accessiweather.notifications.sound_player import _play_sound_file

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with patch("accessiweather.notifications.sound_player.SOUND_LIB_AVAILABLE", False):
                result = _play_sound_file(temp_path, volume=0.0)

            assert result is True
        finally:
            temp_path.unlink(missing_ok=True)
