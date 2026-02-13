"""Tests for NOAA Weather Radio audio player service."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.noaa_radio.player import RadioPlayer


@pytest.fixture
def mock_sound_lib():
    """Fixture that patches sound_lib availability and URLStream."""
    mock_stream_instance = MagicMock()
    mock_stream_instance.is_playing = True
    mock_stream_instance.volume = 1.0

    with (
        patch("accessiweather.noaa_radio.player._sound_lib_available", True),
        patch("accessiweather.noaa_radio.player._sound_lib_initialized", True),
        patch("accessiweather.noaa_radio.player.URLStream", create=True),
    ):
        # Patch the import inside play()
        mock_url_stream_cls = MagicMock(return_value=mock_stream_instance)
        with patch.dict(
            "sys.modules",
            {
                "sound_lib": MagicMock(),
                "sound_lib.stream": MagicMock(URLStream=mock_url_stream_cls),
            },
        ):
            yield mock_url_stream_cls, mock_stream_instance


@pytest.fixture
def no_sound_lib():
    """Fixture that patches sound_lib as unavailable."""
    with (
        patch("accessiweather.noaa_radio.player._sound_lib_available", False),
        patch("accessiweather.noaa_radio.player._sound_lib_initialized", True),
    ):
        yield


class TestRadioPlayerInit:
    """Tests for RadioPlayer initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        player = RadioPlayer()
        assert player.get_volume() == 1.0
        assert player.is_playing() is False

    def test_init_with_callbacks(self):
        """Test initialization with callbacks."""
        on_playing = MagicMock()
        on_stopped = MagicMock()
        on_error = MagicMock()
        player = RadioPlayer(on_playing=on_playing, on_stopped=on_stopped, on_error=on_error)
        assert player._on_playing is on_playing
        assert player._on_stopped is on_stopped
        assert player._on_error is on_error


class TestRadioPlayerPlay:
    """Tests for RadioPlayer.play()."""

    def test_play_success(self, mock_sound_lib):
        """Test successful play starts stream."""
        mock_cls, mock_stream = mock_sound_lib
        on_playing = MagicMock()
        player = RadioPlayer(on_playing=on_playing)
        result = player.play("http://example.com/stream")
        assert result is True
        mock_cls.assert_called_once_with(url="http://example.com/stream")
        mock_stream.play.assert_called_once()
        on_playing.assert_called_once()

    def test_play_no_sound_lib(self, no_sound_lib):
        """Test play returns False when sound_lib unavailable."""
        on_error = MagicMock()
        player = RadioPlayer(on_error=on_error)
        result = player.play("http://example.com/stream")
        assert result is False
        on_error.assert_called_once()
        assert "not available" in on_error.call_args[0][0]

    def test_play_stream_error(self, mock_sound_lib):
        """Test play handles stream errors gracefully."""
        mock_cls, _ = mock_sound_lib
        mock_cls.side_effect = Exception("Connection failed")
        on_error = MagicMock()
        player = RadioPlayer(on_error=on_error)
        result = player.play("http://example.com/stream")
        assert result is False
        on_error.assert_called_once()
        assert "Connection failed" in on_error.call_args[0][0]

    def test_play_sets_volume(self, mock_sound_lib):
        """Test play sets volume on the stream."""
        _, mock_stream = mock_sound_lib
        player = RadioPlayer()
        player.set_volume(0.5)
        player.play("http://example.com/stream")
        assert mock_stream.volume == 0.5

    def test_play_stops_previous_stream(self, mock_sound_lib):
        """Test play stops previous stream before starting new one."""
        mock_cls, mock_stream = mock_sound_lib
        player = RadioPlayer()
        player.play("http://example.com/stream1")
        # Play again - should stop the first
        mock_stream.is_playing = True
        player.play("http://example.com/stream2")
        mock_stream.stop.assert_called()


class TestRadioPlayerStop:
    """Tests for RadioPlayer.stop()."""

    def test_stop_cleans_up_stream(self, mock_sound_lib):
        """Test stop cleans up stream reference."""
        _, mock_stream = mock_sound_lib
        on_stopped = MagicMock()
        player = RadioPlayer(on_stopped=on_stopped)
        player.play("http://example.com/stream")
        player.stop()
        mock_stream.stop.assert_called()
        mock_stream.free.assert_called()
        assert player._stream is None
        on_stopped.assert_called()

    def test_stop_when_not_playing(self):
        """Test stop when nothing is playing does not error."""
        on_stopped = MagicMock()
        player = RadioPlayer(on_stopped=on_stopped)
        player.stop()  # Should not raise
        on_stopped.assert_not_called()

    def test_stop_handles_exception(self, mock_sound_lib):
        """Test stop handles cleanup exceptions gracefully."""
        _, mock_stream = mock_sound_lib
        mock_stream.stop.side_effect = Exception("cleanup error")
        player = RadioPlayer()
        player.play("http://example.com/stream")
        player.stop()  # Should not raise
        assert player._stream is None


class TestRadioPlayerVolume:
    """Tests for volume control."""

    def test_set_volume_normal(self):
        """Test setting volume within range."""
        player = RadioPlayer()
        player.set_volume(0.5)
        assert player.get_volume() == 0.5

    def test_set_volume_clamp_high(self):
        """Test volume is clamped to 1.0 max."""
        player = RadioPlayer()
        player.set_volume(1.5)
        assert player.get_volume() == 1.0

    def test_set_volume_clamp_low(self):
        """Test volume is clamped to 0.0 min."""
        player = RadioPlayer()
        player.set_volume(-0.5)
        assert player.get_volume() == 0.0

    def test_set_volume_updates_active_stream(self, mock_sound_lib):
        """Test setting volume updates active stream."""
        _, mock_stream = mock_sound_lib
        player = RadioPlayer()
        player.play("http://example.com/stream")
        player.set_volume(0.7)
        assert mock_stream.volume == 0.7

    def test_get_volume_default(self):
        """Test default volume is 1.0."""
        player = RadioPlayer()
        assert player.get_volume() == 1.0


class TestRadioPlayerIsPlaying:
    """Tests for is_playing()."""

    def test_is_playing_no_stream(self):
        """Test is_playing returns False when no stream."""
        player = RadioPlayer()
        assert player.is_playing() is False

    def test_is_playing_active_stream(self, mock_sound_lib):
        """Test is_playing returns True when stream is active."""
        _, mock_stream = mock_sound_lib
        mock_stream.is_playing = True
        player = RadioPlayer()
        player.play("http://example.com/stream")
        assert player.is_playing() is True

    def test_is_playing_handles_exception(self, mock_sound_lib):
        """Test is_playing handles exception from stream."""
        _, mock_stream = mock_sound_lib
        type(mock_stream).is_playing = property(
            lambda self: (_ for _ in ()).throw(Exception("err"))
        )
        player = RadioPlayer()
        player._stream = mock_stream
        assert player.is_playing() is False


class TestEnsureSoundLib:
    """Tests for _ensure_sound_lib() function."""

    def test_ensure_sound_lib_success(self):
        """Test _ensure_sound_lib when import succeeds."""
        import accessiweather.noaa_radio.player as mod

        old_init, old_avail = mod._sound_lib_initialized, mod._sound_lib_available
        try:
            mod._sound_lib_initialized = False
            mod._sound_lib_available = False
            with patch.dict(
                "sys.modules",
                {
                    "sound_lib": MagicMock(),
                    "sound_lib.stream": MagicMock(),
                },
            ):
                result = mod._ensure_sound_lib()
            assert result is True
            assert mod._sound_lib_available is True
        finally:
            mod._sound_lib_initialized, mod._sound_lib_available = old_init, old_avail

    def test_ensure_sound_lib_import_error(self):
        """Test _ensure_sound_lib when ImportError raised."""
        import accessiweather.noaa_radio.player as mod

        old_init, old_avail = mod._sound_lib_initialized, mod._sound_lib_available
        try:
            mod._sound_lib_initialized = False
            mod._sound_lib_available = False
            with patch.dict("sys.modules", {"sound_lib": MagicMock()}):
                # Remove sound_lib.stream so import fails
                import sys

                sys.modules.pop("sound_lib.stream", None)
                with patch("builtins.__import__", side_effect=ImportError("no sound_lib")):
                    result = mod._ensure_sound_lib()
            assert result is False
            assert mod._sound_lib_available is False
        finally:
            mod._sound_lib_initialized, mod._sound_lib_available = old_init, old_avail

    def test_ensure_sound_lib_other_exception(self):
        """Test _ensure_sound_lib when non-ImportError raised."""
        import accessiweather.noaa_radio.player as mod

        old_init, old_avail = mod._sound_lib_initialized, mod._sound_lib_available
        try:
            mod._sound_lib_initialized = False
            mod._sound_lib_available = False
            with patch("builtins.__import__", side_effect=RuntimeError("bass error")):
                result = mod._ensure_sound_lib()
            assert result is False
            assert mod._sound_lib_available is False
        finally:
            mod._sound_lib_initialized, mod._sound_lib_available = old_init, old_avail

    def test_ensure_sound_lib_cached(self):
        """Test _ensure_sound_lib returns cached result."""
        import accessiweather.noaa_radio.player as mod

        old_init, old_avail = mod._sound_lib_initialized, mod._sound_lib_available
        try:
            mod._sound_lib_initialized = True
            mod._sound_lib_available = True
            result = mod._ensure_sound_lib()
            assert result is True
        finally:
            mod._sound_lib_initialized, mod._sound_lib_available = old_init, old_avail


class TestRetry:
    """Tests for RadioPlayer.retry()."""

    def test_retry_success(self, mock_sound_lib):
        """Test successful retry reconnects."""
        mock_cls, mock_stream = mock_sound_lib
        on_reconnecting = MagicMock()
        player = RadioPlayer(on_reconnecting=on_reconnecting)
        player.play("http://example.com/stream")
        mock_cls.reset_mock()
        result = player.retry()
        assert result is True
        on_reconnecting.assert_called_once_with(1)
        mock_cls.assert_called_once_with(url="http://example.com/stream")

    def test_retry_cleans_old_stream(self, mock_sound_lib):
        """Test retry cleans up the old stream."""
        _, mock_stream = mock_sound_lib
        player = RadioPlayer()
        player.play("http://example.com/stream")
        old_stop_count = mock_stream.stop.call_count
        player.retry()
        assert mock_stream.stop.call_count > old_stop_count
        assert mock_stream.free.call_count > 0

    def test_retry_old_stream_cleanup_exception(self, mock_sound_lib):
        """Test retry handles exception during old stream cleanup."""
        _, mock_stream = mock_sound_lib
        player = RadioPlayer()
        player.play("http://example.com/stream")
        mock_stream.stop.side_effect = Exception("cleanup fail")
        result = player.retry()
        assert result is True  # Should still attempt reconnect


class TestSetVolumeException:
    """Tests for set_volume exception handling."""

    def test_set_volume_stream_exception(self, mock_sound_lib):
        """Test set_volume handles stream exception."""
        _, mock_stream = mock_sound_lib
        player = RadioPlayer()
        player.play("http://example.com/stream")
        type(mock_stream).volume = property(
            lambda s: 1.0, lambda s, v: (_ for _ in ()).throw(Exception("vol err"))
        )
        player.set_volume(0.5)  # Should not raise
        assert player.get_volume() == 0.5


class TestIsStalled:
    """Tests for is_stalled()."""

    def test_is_stalled_true(self, mock_sound_lib):
        """Test is_stalled returns True when stream is stalled."""
        _, mock_stream = mock_sound_lib
        mock_stream.is_stalled = True
        player = RadioPlayer()
        player.play("http://example.com/stream")
        assert player.is_stalled() is True

    def test_is_stalled_false(self, mock_sound_lib):
        """Test is_stalled returns False when stream is not stalled."""
        _, mock_stream = mock_sound_lib
        mock_stream.is_stalled = False
        player = RadioPlayer()
        player.play("http://example.com/stream")
        assert player.is_stalled() is False

    def test_is_stalled_exception(self, mock_sound_lib):
        """Test is_stalled handles exception."""
        _, mock_stream = mock_sound_lib
        type(mock_stream).is_stalled = property(
            lambda self: (_ for _ in ()).throw(Exception("err"))
        )
        player = RadioPlayer()
        player._stream = mock_stream
        assert player.is_stalled() is False


class TestGetLevel:
    """Tests for get_level()."""

    def test_get_level_with_stream(self, mock_sound_lib):
        """Test get_level returns stream level."""
        _, mock_stream = mock_sound_lib
        mock_stream.get_level.return_value = 12345
        player = RadioPlayer()
        player.play("http://example.com/stream")
        assert player.get_level() == 12345

    def test_get_level_no_stream(self):
        """Test get_level returns 0 with no stream."""
        player = RadioPlayer()
        assert player.get_level() == 0

    def test_get_level_exception(self, mock_sound_lib):
        """Test get_level handles exception."""
        _, mock_stream = mock_sound_lib
        mock_stream.get_level.side_effect = Exception("level err")
        player = RadioPlayer()
        player._stream = mock_stream
        assert player.get_level() == 0


class TestCheckHealth:
    """Tests for check_health()."""

    def test_check_health_stalled_triggers_retry(self, mock_sound_lib):
        """Test check_health calls retry when stalled."""
        _, mock_stream = mock_sound_lib
        mock_stream.is_stalled = True
        on_stalled = MagicMock()
        player = RadioPlayer(on_stalled=on_stalled)
        player.play("http://example.com/stream")
        with patch.object(player, "retry") as mock_retry:
            player.check_health()
            mock_retry.assert_called_once()
        on_stalled.assert_called_once()

    def test_check_health_silence_counting(self, mock_sound_lib):
        """Test check_health counts silence and auto-advances."""
        _, mock_stream = mock_sound_lib
        mock_stream.is_stalled = False
        mock_stream.is_playing = True
        mock_stream.get_level.return_value = 0
        on_auto = MagicMock()
        player = RadioPlayer()
        player.play("http://example.com/stream")
        # Call check_health SILENCE_THRESHOLD times
        for _ in range(RadioPlayer.SILENCE_THRESHOLD):
            player.check_health(on_auto_advance=on_auto)
        on_auto.assert_called_once()
        assert player._silence_count == 0  # Reset after auto-advance

    def test_check_health_silence_reset_on_sound(self, mock_sound_lib):
        """Test silence counter resets when sound detected."""
        _, mock_stream = mock_sound_lib
        mock_stream.is_stalled = False
        mock_stream.is_playing = True
        mock_stream.get_level.return_value = 0
        player = RadioPlayer()
        player.play("http://example.com/stream")
        player.check_health()
        player.check_health()
        assert player._silence_count == 2
        # Now sound returns
        mock_stream.get_level.return_value = 100
        player.check_health()
        assert player._silence_count == 0

    def test_check_health_not_playing_resets_silence(self, mock_sound_lib):
        """Test silence counter resets when not playing."""
        _, mock_stream = mock_sound_lib
        mock_stream.is_stalled = False
        mock_stream.is_playing = False
        player = RadioPlayer()
        player.play("http://example.com/stream")
        player._silence_count = 2
        player.check_health()
        assert player._silence_count == 0
