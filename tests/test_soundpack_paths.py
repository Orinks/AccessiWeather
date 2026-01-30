"""Tests for soundpack path resolution."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock


class TestFindProjectRoot:
    """Tests for _find_project_root helper."""

    def test_finds_project_root_from_module(self):
        """Should find project root containing pyproject.toml."""
        from accessiweather.soundpack_paths import _find_project_root

        # Start from this test file
        start = Path(__file__).resolve()
        root = _find_project_root(start)

        assert root is not None
        assert (root / "pyproject.toml").exists()

    def test_returns_none_when_no_pyproject(self, tmp_path: Path):
        """Should return None when no pyproject.toml in any parent."""
        from accessiweather.soundpack_paths import _find_project_root

        # Create a deep nested path with no pyproject.toml
        deep_path = tmp_path / "a" / "b" / "c"
        deep_path.mkdir(parents=True)

        result = _find_project_root(deep_path)
        assert result is None


class TestGetSoundpacksDir:
    """Tests for get_soundpacks_dir function."""

    def test_returns_path_in_dev_mode(self):
        """Should return soundpacks dir relative to project root in dev."""
        from accessiweather.soundpack_paths import get_soundpacks_dir

        soundpacks_dir = get_soundpacks_dir()

        assert soundpacks_dir.name == "soundpacks"
        # Should be at project root level
        assert (soundpacks_dir.parent / "pyproject.toml").exists()

    def test_frozen_mode_with_meipass(self):
        """Should use _MEIPASS in PyInstaller frozen mode."""
        from accessiweather import soundpack_paths

        fake_meipass = Path("/fake/meipass")

        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "_MEIPASS", str(fake_meipass), create=True),
        ):
            result = soundpack_paths.get_soundpacks_dir()

        assert result == fake_meipass / "soundpacks"

    def test_frozen_mode_without_meipass(self):
        """Should fall back to executable parent when no _MEIPASS."""
        from accessiweather import soundpack_paths

        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", "/fake/dir/app.exe"),
        ):
            # Ensure _MEIPASS doesn't exist
            if hasattr(sys, "_MEIPASS"):
                delattr(sys, "_MEIPASS")
            result = soundpack_paths.get_soundpacks_dir()

        assert result == Path("/fake/dir/soundpacks")

    def test_fallback_when_no_project_root(self):
        """Should use fallback path when project root not found."""
        from accessiweather import soundpack_paths

        with mock.patch.object(
            soundpack_paths, "_find_project_root", return_value=None
        ):
            result = soundpack_paths.get_soundpacks_dir()

        # Should fall back to parents[2] of the module file
        expected_fallback = Path(soundpack_paths.__file__).resolve().parents[2]
        assert result == expected_fallback / "soundpacks"
