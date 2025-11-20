#!/usr/bin/env python3
"""
A make-like utility for AccessiWeather using BeeWare Briefcase.

This replaces the legacy PyInstaller/Inno Setup scripts and includes workarounds
for Windows build issues to ensure a working CI/CD process for GitHub Pages deployment.

Usage examples:
  python installer/make.py create          # First-time platform scaffold
  python installer/make.py build           # Build app bundle
  python installer/make.py package         # Create installer (e.g., MSI on Windows)
  python installer/make.py dev             # Run app in development mode
  python installer/make.py test            # Run test suite in a Briefcase dev app
  python installer/make.py zip             # Create a temporary portable ZIP from the build
  python installer/make.py verify          # Verify soundpack cleanup in built ZIP
  python installer/make.py status          # Show detected settings and versions
  python installer/make.py clean           # Clean Briefcase build artifacts (best-effort)

Options:
  --platform windows|macOS|linux (default: windows)
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

TRY_BREF_CLEAN = True  # call `briefcase clean` if available
ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"$ {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False)
        return res.returncode
    except FileNotFoundError:
        print(f"Error: command not found: {cmd[0]}")
        return 127


def _briefcase_exists() -> bool:
    # Use version check; some CLIs return non-zero for --help
    code = _run([sys.executable, "-m", "briefcase", "-V"], cwd=ROOT)
    return code == 0


def _briefcase(*args: str) -> int:
    return _run([sys.executable, "-m", "briefcase", *args], cwd=ROOT)


def _read_version() -> str:
    """Read version from pyproject.toml (project.version)."""
    pyproject = ROOT / "pyproject.toml"
    try:
        # Prefer tomllib on Python 3.11+; fall back to naive parsing without external deps
        try:
            import tomllib  # Python 3.11+

            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            return data.get("project", {}).get("version", "0.0.0")
        except Exception:
            text = pyproject.read_text(encoding="utf-8")
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("version") and '"' in s:
                    return s.split('"', 2)[1]
            return "0.0.0"
    except Exception:
        return "0.0.0"


def _detect_default_platform() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "macOS"
    return "linux"


# ---------------- Headless/autonomous helpers ----------------


def _detect_python_env() -> tuple[Path, Path | None, bool]:
    """
    Detect a suitable Python for building and whether a venv needs creation.

    Returns a tuple: (python_exe, venv_dir_or_None, created_new_env)
    - If the current interpreter is already a virtual environment, returns that
      interpreter and (None, False) so we won't create/manage a new venv.
    - Otherwise, prefers an existing .venv, then venv directory; if neither
      exists, instructs to create venv at ./venv and returns (its python, Path, True).
    """
    in_venv = (hasattr(sys, "base_prefix") and sys.prefix != sys.base_prefix) or getattr(
        sys, "real_prefix", None
    )
    if in_venv:
        return Path(sys.executable), None, False

    candidates = [ROOT / ".venv", ROOT / "venv"]
    for vdir in candidates:
        if vdir.exists():
            py = _venv_python(vdir)
            if py.exists():
                return py, vdir, False
    # None found: propose creating ./venv
    vdir = ROOT / "venv"
    return _venv_python(vdir), vdir, True


def _venv_python(venv_dir: Path) -> Path:
    """Return the path to the venv's Python executable."""
    if platform.system().lower().startswith("win"):
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _ensure_venv(venv_dir: Path) -> int:
    """Create a virtual environment at venv_dir if it doesn't exist."""
    if venv_dir.exists():
        return 0
    print(f"Creating virtual environment at {venv_dir} ...")
    return _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=ROOT)


def _pip(venv_py: Path, *args: str) -> int:
    return _run([str(venv_py), "-m", "pip", *args], cwd=ROOT)


def _briefcase_with(venv_py: Path, *args: str) -> int:
    return _run([str(venv_py), "-m", "briefcase", *args], cwd=ROOT)


def run_headless() -> int:
    """
    Headless build: ensure deps, then package MSI and ZIP with Briefcase.

    Behavior:
    - Ensures ./venv exists and installs/updates build tools and Briefcase
    - On Windows hosts: update+build windows, cleanup soundpacks, then package
      MSI and ZIP: `briefcase package windows -p msi` and `-p zip`
    - On non-Windows hosts: prints a note and exits (Windows packages require
      Windows). CI should run this on a Windows runner.
    """
    host = platform.system().lower()
    vpy, venv_dir, created = _detect_python_env()

    # Ensure venv only if we decided to manage one
    if venv_dir is not None:
        if created:
            print(f"Creating virtual environment at {venv_dir} ...")
            code = _ensure_venv(venv_dir)
            if code != 0:
                return code
        else:
            print(f"Using existing virtual environment at {venv_dir}")
    else:
        print(f"Using active Python environment: {vpy}")

    # Ensure packaging toolchain in the chosen environment
    print("Upgrading pip/setuptools/wheel/build ...")
    if _pip(vpy, "install", "-U", "pip", "setuptools", "wheel", "build") != 0:
        return 1
    print("Installing/Upgrading Briefcase ...")
    if _pip(vpy, "install", "-U", "briefcase") != 0:
        return 1

    if host.startswith("win"):
        # Prepare windows app build
        print("Running Briefcase update/build for Windows ...")
        _briefcase_with(vpy, "update", "windows")  # best-effort
        build_code = _briefcase_with(vpy, "build", "windows", "--no-update")
        if build_code != 0:
            print("Build failed; attempting to re-create app template and rebuild ...")
            # Some template versions require a re-create with current Briefcase
            if _briefcase_with(vpy, "create", "windows", "app") != 0:
                return 1
            if _briefcase_with(vpy, "build", "windows", "--no-update") != 0:
                return 1

        # Clean up soundpacks and weather cache in build tree prior to packaging
        _cleanup_soundpacks(argparse.Namespace(platform="windows"))
        _cleanup_weather_cache(argparse.Namespace(platform="windows"))

        print("Packaging Windows MSI ...")
        if _briefcase_with(vpy, "package", "windows", "--adhoc-sign", "-p", "msi") != 0:
            return 1

        print("Packaging Windows ZIP ...")
        if _briefcase_with(vpy, "package", "windows", "--adhoc-sign", "-p", "zip") != 0:
            return 1

        print("Headless packaging complete. Artifacts are in ./dist")
        return 0

    print(
        "Non-Windows host detected; MSI/ZIP Windows packages are skipped.\n"
        "Run this script on a Windows host (e.g., GitHub Actions windows-latest) to build installers."
    )
    return 0


def _cleanup_soundpacks(args: argparse.Namespace) -> None:
    """Remove non-default soundpacks from build directory to keep only default soundpack."""
    build_base = ROOT / "build" / "accessiweather" / args.platform / "app"
    soundpacks_path = build_base / "src" / "app" / "accessiweather" / "soundpacks"

    if not soundpacks_path.exists():
        return

    # Keep only the default soundpack
    default_soundpacks = {"default", ".gitkeep"}

    print("Cleaning up soundpacks (keeping only default)...")
    removed_count = 0

    for item in soundpacks_path.iterdir():
        if item.name not in default_soundpacks:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
            print(f"  Removed: {item.name}")
            removed_count += 1

    if removed_count > 0:
        print(f"  Cleaned up {removed_count} non-default soundpack(s)")
    else:
        print("  No non-default soundpacks found to clean")


def _cleanup_weather_cache(args: argparse.Namespace) -> None:
    """Remove weather cache from build directory to avoid shipping stale data."""
    build_base = ROOT / "build" / "accessiweather" / args.platform / "app"

    # Find all possible weather cache locations in the build
    cache_patterns = [
        build_base / "src" / "app_packages" / "accessiweather" / "cache",
        build_base / "src" / "app" / "accessiweather" / "cache",
        build_base / "cache",
    ]

    print("Cleaning up weather cache...")
    removed_any = False

    for cache_path in cache_patterns:
        if cache_path.exists() and cache_path.is_dir():
            print(f"  Removing cache directory: {cache_path}")
            shutil.rmtree(cache_path, ignore_errors=True)
            removed_any = True

    if removed_any:
        print("  Weather cache cleaned up successfully")
    else:
        print("  No weather cache found to clean")


def cmd_status(args: argparse.Namespace) -> int:
    print("AccessiWeather make-like utility (Briefcase)")
    print(f"Root: {ROOT}")
    print(f"Platform: {args.platform}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Briefcase available: {'yes' if _briefcase_exists() else 'no'}")
    print(f"Version: {_read_version()}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    if not _briefcase_exists():
        print("Error: Briefcase is not installed. Install with: pip install briefcase")
        return 1
    return _briefcase("create", args.platform)


def cmd_build(args: argparse.Namespace) -> int:
    if not _briefcase_exists():
        print("Error: Briefcase is not installed. Install with: pip install briefcase")
        return 1
    # Use update+build for more robust builds, but ignore update failures
    _briefcase("update", args.platform)  # Don't fail if update fails
    result = _briefcase("build", args.platform, "--no-update")

    # Clean up soundpacks and weather cache after build (regardless of build success/failure)
    _cleanup_soundpacks(args)
    _cleanup_weather_cache(args)

    return result


def cmd_package(args: argparse.Namespace) -> int:
    if not _briefcase_exists():
        print("Error: Briefcase is not installed. Install with: pip install briefcase")
        return 1

    # Ensure soundpacks and weather cache are cleaned up before packaging
    _cleanup_soundpacks(args)
    _cleanup_weather_cache(args)

    return _briefcase("package", args.platform, "--adhoc-sign")


def cmd_dev(args: argparse.Namespace) -> int:
    if not _briefcase_exists():
        print("Error: Briefcase is not installed. Install with: pip install briefcase")
        return 1
    return _briefcase("dev")


def cmd_test(args: argparse.Namespace) -> int:
    if not _briefcase_exists():
        print("Error: Briefcase is not installed. Install with: pip install briefcase")
        return 1
    # Prefer Briefcase to run tests in the app context; fallback to pytest
    code = _briefcase("dev", "--test")
    if code != 0:
        print("briefcase dev --test failed; falling back to pytest")
        code = _run([sys.executable, "-m", "pytest"], cwd=ROOT)
    return code


def cmd_zip(args: argparse.Namespace) -> int:
    """Create a portable ZIP from the Briefcase build output (temporary)."""
    version = _read_version()
    if args.platform != "windows":
        print("Note: ZIP recipe is primarily intended for Windows.")

    # Find the built app directory more robustly
    build_base = ROOT / "build" / "accessiweather" / args.platform / "app"
    app_build_dir = build_base / "src"

    if not app_build_dir.exists():
        print(f"Error: build output not found at {app_build_dir}. Run build first.")
        return 1

    # Ensure soundpacks and weather cache are cleaned up before creating ZIP
    _cleanup_soundpacks(args)
    _cleanup_weather_cache(args)

    dist_dir = ROOT / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dist_dir / f"AccessiWeather_Portable_v{version}.zip"

    # Create zip
    print(f"Creating ZIP: {zip_path}")
    if zip_path.exists():
        zip_path.unlink()

    shutil.make_archive(zip_path.with_suffix(""), "zip", app_build_dir)
    print("ZIP created.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify that built ZIP contains only default soundpack."""
    dist_dir = ROOT / "dist"
    zip_files = list(dist_dir.glob("AccessiWeather_Portable_v*.zip"))

    if not zip_files:
        print("Error: No portable ZIP files found in dist/")
        return 1

    # Use verification script
    verify_script = ROOT / "verify_soundpack_cleanup.py"
    if verify_script.exists():
        return _run([sys.executable, str(verify_script)], cwd=ROOT)
    print("Warning: verify_soundpack_cleanup.py not found")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Clean Briefcase artifacts (best-effort)."""
    # Try Briefcase clean first if available (newer versions)
    if TRY_BREF_CLEAN and _briefcase_exists():
        code = _run([sys.executable, "-m", "briefcase", "clean", args.platform], cwd=ROOT)
        if code == 0:
            return 0

    # Fallback: remove known build trees (non-destructive to sources)
    patterns = [
        ROOT / "build",
        ROOT / "dist",
    ]
    for p in patterns:
        if p.exists():
            print(f"Removing {p}")
            shutil.rmtree(p, ignore_errors=True)
    print("Clean complete.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AccessiWeather Briefcase make-like tool")
    sub = parser.add_subparsers(dest="cmd")

    def add_common(sp):
        sp.add_argument(
            "--platform",
            default=_detect_default_platform(),
            choices=["windows", "macOS", "linux"],
            help="Target platform (default: auto-detected)",
        )

    p_status = sub.add_parser("status", help="Show environment and settings")
    add_common(p_status)
    p_status.set_defaults(func=cmd_status)

    p_create = sub.add_parser("create", help="Create platform scaffold")
    add_common(p_create)
    p_create.set_defaults(func=cmd_create)

    p_build = sub.add_parser("build", help="Build app bundle")
    add_common(p_build)
    p_build.set_defaults(func=cmd_build)

    p_package = sub.add_parser("package", help="Create installer (MSI on Windows)")
    add_common(p_package)
    p_package.set_defaults(func=cmd_package)

    p_dev = sub.add_parser("dev", help="Run app in dev mode")
    p_dev.set_defaults(func=cmd_dev)

    p_test = sub.add_parser("test", help="Run tests via Briefcase (fallback to pytest)")
    p_test.set_defaults(func=cmd_test)

    p_zip = sub.add_parser("zip", help="Create a portable ZIP from build output")
    add_common(p_zip)
    p_zip.set_defaults(func=cmd_zip)

    p_verify = sub.add_parser("verify", help="Verify soundpack cleanup in built ZIP")
    p_verify.set_defaults(func=cmd_verify)

    p_clean = sub.add_parser("clean", help="Clean Briefcase artifacts")
    add_common(p_clean)
    p_clean.set_defaults(func=cmd_clean)

    args = parser.parse_args()
    if not getattr(args, "cmd", None):
        # Default headless behavior: show status (no UI), exit 0
        default_args = argparse.Namespace(platform=_detect_default_platform())
        return cmd_status(default_args)
    return args.func(args)


if __name__ == "__main__":
    # Headless/autonomous default: when run without arguments, perform full build
    # and package steps non-interactively for CI/CD and local use.
    if len(sys.argv) == 1:
        raise SystemExit(run_headless())
    raise SystemExit(main())
