"""Tests for portable ZIP staging in installer.build."""

from __future__ import annotations

import zipfile

from installer import build


def test_create_portable_zip_from_single_exe_includes_default_soundpack(
    tmp_path, monkeypatch
) -> None:
    """Portable ZIPs staged from a single exe must include the default soundpack."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "AccessiWeather.exe").write_bytes(b"fake-exe")

    soundpacks_dir = tmp_path / "soundpacks"
    default_soundpack_dir = soundpacks_dir / "default"
    default_soundpack_dir.mkdir(parents=True)
    (default_soundpack_dir / "pack.json").write_text('{"name":"Default"}', encoding="utf-8")
    (default_soundpack_dir / "startup.wav").write_bytes(b"fake-wav")

    monkeypatch.setattr(build, "IS_WINDOWS", True)
    monkeypatch.setattr(build, "IS_MACOS", False)
    monkeypatch.setattr(build, "IS_LINUX", False)
    monkeypatch.setattr(build, "DIST_DIR", dist_dir)
    monkeypatch.setattr(build, "SOUNDPACKS_DIR", soundpacks_dir)
    monkeypatch.setattr(build, "get_version", lambda: "9.9.9")

    assert build.create_portable_zip() is True

    zip_path = dist_dir / "AccessiWeather_Portable_v9.9.9.zip"
    assert zip_path.exists()

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())

    assert "AccessiWeather_portable/AccessiWeather.exe" in names
    assert "AccessiWeather_portable/.portable" in names
    assert "AccessiWeather_portable/data/soundpacks/default/pack.json" in names
    assert "AccessiWeather_portable/data/soundpacks/default/startup.wav" in names


def test_create_portable_zip_from_dir_distribution_uses_staged_bundled_soundpack(
    tmp_path, monkeypatch
) -> None:
    """Portable ZIPs should reuse the sound pack already staged by the app builder."""
    dist_dir = tmp_path / "dist"
    source_dir = dist_dir / "AccessiWeather_dir"
    bundled_default = source_dir / "soundpacks" / "default"
    bundled_default.mkdir(parents=True)
    (bundled_default / "pack.json").write_text('{"name":"Default"}', encoding="utf-8")
    (bundled_default / "startup.wav").write_bytes(b"fake-wav")
    (source_dir / "AccessiWeather.exe").write_bytes(b"fake-exe")

    monkeypatch.setattr(build, "IS_WINDOWS", True)
    monkeypatch.setattr(build, "IS_MACOS", False)
    monkeypatch.setattr(build, "IS_LINUX", False)
    monkeypatch.setattr(build, "DIST_DIR", dist_dir)
    monkeypatch.setattr(build, "SOUNDPACKS_DIR", tmp_path / "missing-soundpacks")
    monkeypatch.setattr(build, "get_version", lambda: "9.9.9")

    assert build.create_portable_zip() is True
    assert (source_dir / "data" / "soundpacks" / "default" / "pack.json").exists()

    zip_path = dist_dir / "AccessiWeather_Portable_v9.9.9.zip"
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())

    assert "AccessiWeather_dir/data/soundpacks/default/pack.json" in names
    assert "AccessiWeather_dir/data/soundpacks/default/startup.wav" in names
    assert "AccessiWeather_dir/.portable" in names


def test_create_portable_zip_fails_when_default_soundpack_manifest_missing(
    tmp_path, monkeypatch
) -> None:
    """Portable ZIP creation must fail loudly if no default pack manifest can be staged."""
    dist_dir = tmp_path / "dist"
    source_dir = dist_dir / "AccessiWeather_dir"
    source_dir.mkdir(parents=True)
    (source_dir / "AccessiWeather.exe").write_bytes(b"fake-exe")

    monkeypatch.setattr(build, "IS_WINDOWS", True)
    monkeypatch.setattr(build, "IS_MACOS", False)
    monkeypatch.setattr(build, "IS_LINUX", False)
    monkeypatch.setattr(build, "DIST_DIR", dist_dir)
    monkeypatch.setattr(build, "SOUNDPACKS_DIR", tmp_path / "missing-soundpacks")
    monkeypatch.setattr(build, "get_version", lambda: "9.9.9")

    assert build.create_portable_zip() is False
    assert not (dist_dir / "AccessiWeather_Portable_v9.9.9.zip").exists()
