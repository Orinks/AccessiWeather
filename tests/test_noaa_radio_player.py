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
