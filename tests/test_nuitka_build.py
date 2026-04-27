from __future__ import annotations

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
    assert "--include-package-data=tzdata" in command
    assert "--include-package=accessiweather" in command
    assert "src/accessiweather/__main__.py" in command
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


def test_experimental_nuitka_workflow_uses_binary_wxpython_install() -> None:
    workflow = (build_nuitka.ROOT / ".github" / "workflows" / "nuitka-build.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "NUITKA_CACHE_DIR:" in workflow
    assert "actions/cache/restore@v4" in workflow
    assert "actions/cache/save@v4" in workflow
    assert "brew install ccache" in workflow
    assert "--only-binary wxPython" in workflow
    assert "build/nuitka/compilation-report.xml" in workflow
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
