"""
Tests for sound_player module.

Tests the PreviewPlayer class and sound playback functionality,
including sound_lib integration and playsound3 fallback.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


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
            with (
                patch.dict("sys.modules", {"sound_lib.stream": mock_stream_module}),
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
            with (
                patch.dict("sys.modules", {"sound_lib.stream": mock_stream_module}),
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


class TestPreviewPlayerWithPlaysound:
    """Test PreviewPlayer with playsound3 fallback."""

    def test_play_with_playsound_calls_playsound(self):
        """Playing with playsound3 should call playsound function."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with patch(
                "accessiweather.notifications.sound_player.playsound"
            ) as mock_playsound:
                result = player._play_with_playsound(temp_path)

            mock_playsound.assert_called_once()
            assert result is True
            assert player._is_playing is True
        finally:
            temp_path.unlink(missing_ok=True)

    def test_play_with_playsound_handles_exception(self):
        """Playing with playsound3 should handle exceptions."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with patch(
                "accessiweather.notifications.sound_player.playsound",
                side_effect=Exception("Playback failed"),
            ):
                result = player._play_with_playsound(temp_path)

            assert result is False
            assert player._is_playing is False
        finally:
            temp_path.unlink(missing_ok=True)


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
            with patch(
                "accessiweather.notifications.sound_player.SOUND_LIB_AVAILABLE", False
            ), patch(
                "accessiweather.notifications.sound_player.PLAYSOUND_AVAILABLE",
                False,
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
        player._play_with_playsound = MagicMock(return_value=True)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with patch(
                "accessiweather.notifications.sound_player.SOUND_LIB_AVAILABLE", True
            ):
                player.play(temp_path)

            player._play_with_sound_lib.assert_called_once()
            player._play_with_playsound.assert_not_called()
        finally:
            temp_path.unlink(missing_ok=True)

    def test_play_falls_back_to_playsound(self):
        """play() should fall back to playsound3 when sound_lib unavailable."""
        from accessiweather.notifications.sound_player import PreviewPlayer

        player = PreviewPlayer()
        player._play_with_sound_lib = MagicMock(return_value=True)
        player._play_with_playsound = MagicMock(return_value=True)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with patch(
                "accessiweather.notifications.sound_player.SOUND_LIB_AVAILABLE", False
            ), patch(
                "accessiweather.notifications.sound_player.PLAYSOUND_AVAILABLE",
                True,
            ):
                player.play(temp_path)

            player._play_with_sound_lib.assert_not_called()
            player._play_with_playsound.assert_called_once()
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
        import json

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
        import json

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

    def test_is_playsound_available(self):
        """is_playsound_available should return boolean."""
        from accessiweather.notifications.sound_player import is_playsound_available

        result = is_playsound_available()
        assert isinstance(result, bool)

    def test_is_sound_lib_available_alias(self):
        """is_sound_lib_available should be an alias for is_playsound_available."""
        from accessiweather.notifications.sound_player import (
            is_playsound_available,
            is_sound_lib_available,
        )

        # They should be the same function
        assert is_sound_lib_available is is_playsound_available
