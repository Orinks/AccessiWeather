"""Tests for file-based portable passphrase helpers."""

from __future__ import annotations

from accessiweather.config.import_export import (
    generate_portable_passphrase,
    load_portable_passphrase,
    save_portable_passphrase,
)


def test_generate_portable_passphrase_is_random():
    p1 = generate_portable_passphrase()
    p2 = generate_portable_passphrase()
    assert p1 != p2
    assert len(p1) > 20


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "api-keys.pass"
    passphrase = "test-secret-value"
    assert save_portable_passphrase(path, passphrase) is True
    assert path.exists()
    loaded = load_portable_passphrase(path)
    assert loaded == passphrase


def test_load_returns_none_when_missing(tmp_path):
    path = tmp_path / "nonexistent.pass"
    assert load_portable_passphrase(path) is None


def test_load_returns_none_for_empty_file(tmp_path):
    path = tmp_path / "empty.pass"
    path.write_text("   ", encoding="utf-8")
    assert load_portable_passphrase(path) is None


def test_save_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "dir" / "api-keys.pass"
    assert save_portable_passphrase(path, "secret") is True
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "secret"


def test_get_portable_passphrase_path():
    """ConfigManager.get_portable_passphrase_path returns correct path."""
    from pathlib import Path

    from accessiweather.config.config_manager import ConfigManager

    cm = ConfigManager.__new__(ConfigManager)
    cm.config_dir = Path("/fake/config")
    assert cm.get_portable_passphrase_path() == Path("/fake/config/api-keys.pass")
