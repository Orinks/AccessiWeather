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
    assert "AccessiWeather_portable/data/soundpacks/default/pack.json" in names
    assert "AccessiWeather_portable/data/soundpacks/default/startup.wav" in names
