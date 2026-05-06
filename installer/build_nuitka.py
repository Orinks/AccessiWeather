#!/usr/bin/env python3
"""Experimental Nuitka build path for AccessiWeather."""

from __future__ import annotations

import argparse
import importlib.util
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build" / "nuitka"
RESOURCES_DIR = SRC_DIR / "accessiweather" / "resources"
SOUNDPACKS_DIR = ROOT / "soundpacks"
APP_NAME = "AccessiWeather"
LINUX_SYSTEM_DLL_EXCLUDES = (
    "libgio-2.0.so*",
    "libglib-2.0.so*",
    "libgmodule-2.0.so*",
    "libgobject-2.0.so*",
    "libgthread-2.0.so*",
)
SOUND_LIB_NATIVE_EXTS = {".dll", ".dylib", ".so"}


def _sound_lib_lib_dir() -> Path:
    """Locate sound_lib's native BASS library directory in the build environment."""
    spec = importlib.util.find_spec("sound_lib")
    if not spec or not spec.submodule_search_locations:
        raise RuntimeError("sound_lib is not installed; cannot build packaged audio support")

    package_dir = Path(next(iter(spec.submodule_search_locations)))
    lib_dir = package_dir / "lib"
    if lib_dir.exists():
        return lib_dir
    raise RuntimeError(f"sound_lib native library directory was not found: {lib_dir}")


def _sound_lib_target_dir(staged_dir: Path) -> Path:
    """Return the frozen path where sound_lib looks for native libraries."""
    if staged_dir.suffix == ".app":
        return staged_dir / "Contents" / "Resources" / "sound_lib" / "lib"
    return staged_dir / "sound_lib" / "lib"


def _stage_sound_lib_runtime_files(staged_dir: Path) -> Path:
    """Copy sound_lib native libraries into the frozen runtime data layout."""
    source_dir = _sound_lib_lib_dir()
    target_dir = _sound_lib_target_dir(staged_dir)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)

    native_files = [
        path
        for path in target_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SOUND_LIB_NATIVE_EXTS
    ]
    if not native_files:
        raise RuntimeError(f"No sound_lib native libraries were staged under {target_dir}")
    return target_dir


def _repo_path(path: Path) -> str:
    """Return a POSIX-style path relative to the repository root."""
    return path.relative_to(ROOT).as_posix()


def get_version() -> str:
    """Read the package version from pyproject.toml."""
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def _nuitka_version(version: str) -> str:
    """Convert a PEP 440-ish version into Nuitka's numeric Windows version format."""
    base = version.split("+", 1)[0].split(".dev", 1)[0].split("a", 1)[0].split("b", 1)[0]
    parts = [part for part in base.split(".") if part.isdigit()]
    return ".".join((parts + ["0", "0", "0", "0"])[:4])


def write_inno_version_file() -> Path:
    """Write the version handoff consumed by Inno Setup."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    version_file = DIST_DIR / "version.txt"
    version_file.write_text(f"[version]\nvalue={get_version()}\n", encoding="utf-8")
    return version_file


def _find_nuitka_output_dir() -> tuple[Path, str]:
    """Find the folder produced by Nuitka and return its packaging kind."""
    candidates = sorted(
        BUILD_DIR.glob("*.dist"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    for candidate in candidates:
        if (candidate / f"{APP_NAME}.exe").exists() or (candidate / APP_NAME).exists():
            return candidate, "dist"

    app_candidates = sorted(
        BUILD_DIR.glob("*.app"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    for candidate in app_candidates:
        if (candidate / "Contents" / "MacOS" / APP_NAME).exists():
            return candidate, "app"

    raise FileNotFoundError(f"Nuitka standalone/app output was not found under {BUILD_DIR}")


def stage_nuitka_distribution() -> Path:
    """Copy Nuitka standalone output into the layout expected by Inno and ZIP code."""
    source_dir, output_kind = _find_nuitka_output_dir()
    if output_kind == "app":
        target_name = "AccessiWeather.app"
    elif platform.system() == "Linux":
        target_name = "AccessiWeather"
    else:
        target_name = "AccessiWeather_dir"
    target_dir = DIST_DIR / target_name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)
    _stage_sound_lib_runtime_files(target_dir)
    return target_dir


def create_portable_zip() -> bool:
    """Create a portable ZIP from the staged Nuitka standalone folder."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from installer import build

    original_dist_dir = build.DIST_DIR
    try:
        build.DIST_DIR = DIST_DIR
        return build.create_portable_zip()
    finally:
        build.DIST_DIR = original_dist_dir


def create_windows_installer() -> bool:
    """Create the Windows Inno Setup installer from the staged Nuitka folder."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from installer import build

    original_dist_dir = build.DIST_DIR
    try:
        build.DIST_DIR = DIST_DIR
        return build.create_windows_installer()
    finally:
        build.DIST_DIR = original_dist_dir


def build_nuitka_command(
    *,
    output_dir: Path,
    build_tag: str | None,
    assume_platform: str | None = None,
) -> list[str]:
    """Build the Nuitka command for the current platform."""
    system = assume_platform or platform.system()
    version = get_version()
    numeric_version = _nuitka_version(version)

    mode = "--mode=app" if system == "Darwin" else "--mode=standalone"
    command = [
        sys.executable,
        "-m",
        "nuitka",
        mode,
        "--assume-yes-for-downloads",
        "--noinclude-pytest-mode=nofollow",
        "--include-package-data=desktop_notifier",
        "--include-package-data=prism:_native/*",
        "--include-package-data=sound_lib",
        "--include-package-data=tzdata",
        "--include-package-data=toasted",
        f"--output-dir={output_dir.as_posix()}",
        f"--output-filename={APP_NAME}",
        f"--report={(output_dir / 'compilation-report.xml').as_posix()}",
        f"--product-name={APP_NAME}",
        f"--file-description={APP_NAME}",
        f"--product-version={numeric_version}",
        f"--file-version={numeric_version}",
        _repo_path(ROOT / "installer" / "nuitka_entry.py"),
    ]

    if (SOUNDPACKS_DIR / "default").exists():
        command.insert(
            -1,
            f"--include-data-dir={_repo_path(SOUNDPACKS_DIR / 'default')}=soundpacks/default",
        )

    if system != "Darwin":
        command.insert(
            -1,
            f"--include-data-dir={_repo_path(RESOURCES_DIR)}=accessiweather/resources",
        )

    if build_tag:
        command.insert(-1, f"--company-name=Orinks ({build_tag})")
    else:
        command.insert(-1, "--company-name=Orinks")

    if system == "Windows":
        icon = RESOURCES_DIR / "app.ico"
        command.extend(
            [
                "--windows-console-mode=disable",
                f"--windows-icon-from-ico={_repo_path(icon)}",
            ]
        )
    elif system == "Darwin":
        icon = RESOURCES_DIR / "app.icns"
        command.extend(
            [
                f"--macos-app-name={APP_NAME}",
                f"--macos-app-icon={_repo_path(icon)}",
            ]
        )
    elif system == "Linux":
        # GTK loads the host GLib/GIO stack. Shipping another copy can trigger
        # duplicate GType registration crashes such as "cannot register existing
        # type 'GTask'" when wx/GTK and other GLib consumers initialize.
        command.extend(f"--noinclude-dlls={pattern}" for pattern in LINUX_SYSTEM_DLL_EXCLUDES)

    return command


def run_command(command: list[str]) -> None:
    """Run a command from the project root."""
    print("Running:", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def ensure_nuitka_available() -> None:
    """Fail early with a useful message if Nuitka is not installed."""
    if shutil.which("nuitka") is None:
        try:
            subprocess.run(
                [sys.executable, "-m", "nuitka", "--version"],
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError("Nuitka is not installed. Run: pip install nuitka") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AccessiWeather with Nuitka.")
    parser.add_argument("--tag", default=None, help="Build tag, e.g. nightly-20260427.")
    parser.add_argument("--skip-compile", action="store_true", help="Only write version metadata.")
    parser.add_argument(
        "--skip-installer",
        action="store_true",
        help="Skip creating the Windows Inno Setup installer.",
    )
    args = parser.parse_args()

    print(f"AccessiWeather Nuitka build, version {get_version()}")
    write_inno_version_file()

    if args.skip_compile:
        return 0

    ensure_nuitka_available()
    run_command(build_nuitka_command(output_dir=BUILD_DIR, build_tag=args.tag))
    stage_nuitka_distribution()
    if (
        platform.system() == "Windows"
        and not args.skip_installer
        and not create_windows_installer()
    ):
        return 1
    if not create_portable_zip():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
