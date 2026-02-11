"""Regression tests for Zip Slip (path traversal) vulnerability."""

import io
import zipfile
from pathlib import Path

import pytest

from accessiweather.notifications.sound_pack_installer import safe_extractall


class TestSafeExtractall:
    """Tests that safe_extractall rejects path traversal attempts."""

    def test_should_reject_zip_with_path_traversal_entry(self, tmp_path: Path) -> None:
        """A ZIP containing '../escape.txt' must be rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../escape.txt", "pwned")
        buf.seek(0)

        with zipfile.ZipFile(buf, "r") as zf, pytest.raises(ValueError, match="Zip Slip detected"):
            safe_extractall(zf, tmp_path)

        # Confirm nothing was written outside target
        assert not (tmp_path.parent / "escape.txt").exists()

    def test_should_reject_zip_with_deep_path_traversal(self, tmp_path: Path) -> None:
        """A ZIP containing '../../etc/passwd' must be rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../etc/passwd", "root:x:0:0")
        buf.seek(0)

        with zipfile.ZipFile(buf, "r") as zf, pytest.raises(ValueError, match="Zip Slip detected"):
            safe_extractall(zf, tmp_path)

    def test_should_allow_safe_zip_entries(self, tmp_path: Path) -> None:
        """A ZIP with normal entries should extract fine."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("sounds/alert.wav", "data")
            zf.writestr("pack.json", "{}")
        buf.seek(0)

        with zipfile.ZipFile(buf, "r") as zf:
            safe_extractall(zf, tmp_path)

        assert (tmp_path / "sounds" / "alert.wav").exists()
        assert (tmp_path / "pack.json").exists()

    def test_should_reject_absolute_path_in_zip(self, tmp_path: Path) -> None:
        """A ZIP with an absolute path entry must be rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("/tmp/evil.txt", "pwned")
        buf.seek(0)

        with zipfile.ZipFile(buf, "r") as zf, pytest.raises(ValueError, match="Zip Slip detected"):
            safe_extractall(zf, tmp_path)
