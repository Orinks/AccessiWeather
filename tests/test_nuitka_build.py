from __future__ import annotations

import os
from pathlib import Path

import pytest

from installer import build_nuitka


def test_get_version_reads_pyproject() -> None:
    assert build_nuitka.get_version() == "0.6.1.dev0"


def test_write_inno_version_file_uses_pyproject_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(build_nuitka, "DIST_DIR", tmp_path)

    version_file = build_nuitka.write_inno_version_file()

    assert version_file == tmp_path / "version.txt"
    assert version_file.read_text(encoding="utf-8") == "[version]\nvalue=0.6.1.dev0\n"


def test_windows_nuitka_command_uses_standalone_dir_and_pyproject_version() -> None:
    command = build_nuitka.build_nuitka_command(
        output_dir=Path("dist"),
        build_tag="nightly-20260427",
        assume_platform="Windows",
    )

    assert command[:3] == [build_nuitka.sys.executable, "-m", "nuitka"]
    assert "--mode=standalone" in command
    assert "--windows-console-mode=disable" in command
    assert "--output-filename=AccessiWeather" in command
    assert "--report=dist/compilation-report.xml" in command
    assert "--product-version=0.6.1.0" in command
    assert "--file-version=0.6.1.0" in command
    assert "--include-data-dir=src/accessiweather/resources=accessiweather/resources" in command
    assert "--include-data-dir=soundpacks/default=soundpacks/default" in command
    assert "--python-flag=-m" not in command
    assert "--noinclude-unittest-mode=nofollow" not in command
    assert "--include-package-data=tzdata" in command
    assert "--include-package-data=prism:_native/*" in command
    assert "--include-package=accessiweather" not in command
    assert "--deployment" not in command
    assert "--enable-plugin=anti-bloat" not in command
    assert "installer/nuitka_entry.py" in command
    assert "src/accessiweather" not in command
    assert "src/accessiweather/__main__.py" not in command
    assert "--mode=onefile" not in command


def test_macos_nuitka_command_uses_app_mode() -> None:
    command = build_nuitka.build_nuitka_command(
        output_dir=Path("dist"),
        build_tag=None,
        assume_platform="Darwin",
    )

    assert "--mode=app" in command
    assert "--macos-create-app-bundle" not in command
    assert "--macos-app-name=AccessiWeather" in command
    assert "--include-data-dir=src/accessiweather/resources=accessiweather/resources" not in command


def test_nuitka_is_available_as_build_extra() -> None:
    pyproject = (build_nuitka.ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"nuitka' in pyproject


def test_production_build_workflow_uses_nuitka() -> None:
    workflow = (build_nuitka.ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )

    assert "NUITKA_CACHE_DIR:" in workflow
    assert "actions/cache/restore@v4" in workflow
    assert "actions/cache/save@v4" in workflow
    assert "brew install ccache" in workflow
    assert "choco install innosetup" in workflow
    assert "--only-binary wxPython" in workflow
    assert "dist/AccessiWeather_Setup_*.exe" in workflow
    assert "dist/AccessiWeather_macOS_*.zip" in workflow
    assert "python installer/build_nuitka.py" in workflow
    assert "scripts/generate_build_meta.py" in workflow


def test_stage_nuitka_distribution_copies_output_to_dist_shape(tmp_path, monkeypatch) -> None:
    build_dir = tmp_path / "build" / "nuitka"
    nuitka_dist = build_dir / "__main__.dist"
    nuitka_dist.mkdir(parents=True)
    (nuitka_dist / "AccessiWeather.exe").write_bytes(b"fake-exe")
    (nuitka_dist / "wx").mkdir()

    dist_dir = tmp_path / "dist"
    monkeypatch.setattr(build_nuitka, "BUILD_DIR", build_dir)
    monkeypatch.setattr(build_nuitka, "DIST_DIR", dist_dir)

    staged = build_nuitka.stage_nuitka_distribution()

    assert staged == dist_dir / "AccessiWeather_dir"
    assert (staged / "AccessiWeather.exe").read_bytes() == b"fake-exe"
    assert (staged / "wx").is_dir()


def test_stage_nuitka_distribution_prefers_newest_output(tmp_path, monkeypatch) -> None:
    build_dir = tmp_path / "build" / "nuitka"
    stale_dist = build_dir / "accessiweather.dist"
    fresh_dist = build_dir / "nuitka_entry.dist"
    stale_dist.mkdir(parents=True)
    fresh_dist.mkdir(parents=True)
    (stale_dist / "AccessiWeather.exe").write_bytes(b"stale-exe")
    (fresh_dist / "AccessiWeather.exe").write_bytes(b"fresh-exe")

    stale_time = 1_700_000_000
    fresh_time = stale_time + 60
    monkeypatch.setattr(build_nuitka, "BUILD_DIR", build_dir)
    monkeypatch.setattr(build_nuitka, "DIST_DIR", tmp_path / "dist")
    os.utime(stale_dist, (stale_time, stale_time))
    os.utime(fresh_dist, (fresh_time, fresh_time))

    staged = build_nuitka.stage_nuitka_distribution()

    assert (staged / "AccessiWeather.exe").read_bytes() == b"fresh-exe"


def test_stage_nuitka_distribution_copies_macos_app_to_dist_shape(tmp_path, monkeypatch) -> None:
    build_dir = tmp_path / "build" / "nuitka"
    nuitka_app = build_dir / "__main__.app"
    executable = nuitka_app / "Contents" / "MacOS" / "AccessiWeather"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"fake-app")

    dist_dir = tmp_path / "dist"
    monkeypatch.setattr(build_nuitka, "BUILD_DIR", build_dir)
    monkeypatch.setattr(build_nuitka, "DIST_DIR", dist_dir)

    staged = build_nuitka.stage_nuitka_distribution()

    assert staged == dist_dir / "AccessiWeather.app"
    assert (staged / "Contents" / "MacOS" / "AccessiWeather").read_bytes() == b"fake-app"


def test_stage_nuitka_distribution_fails_when_output_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(build_nuitka, "BUILD_DIR", tmp_path / "build" / "nuitka")

    with pytest.raises(FileNotFoundError, match="Nuitka standalone/app output"):
        build_nuitka.stage_nuitka_distribution()


def test_create_windows_installer_delegates_to_shared_installer_builder(
    tmp_path, monkeypatch
) -> None:
    from installer import build

    called = False
    original_dist_dir = build.DIST_DIR

    def fake_create_windows_installer() -> bool:
        nonlocal called
        called = True
        assert tmp_path == build.DIST_DIR
        return True

    monkeypatch.setattr(build_nuitka, "DIST_DIR", tmp_path)
    monkeypatch.setattr(build, "create_windows_installer", fake_create_windows_installer)

    assert build_nuitka.create_windows_installer() is True
    assert called is True
    assert original_dist_dir == build.DIST_DIR
