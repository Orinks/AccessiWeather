#!/usr/bin/env python3
"""
Package the staged Nuitka Linux build as a cross-distro AppImage.

Runs after ``installer/build_nuitka.py`` and expects ``dist/AccessiWeather``
to exist. linuxdeploy bundles the shared libraries the wxPython Ubuntu wheel
links against (Ubuntu-specific sonames such as libjpeg.so.8 do not exist on
Fedora/Arch/openSUSE), while the host-integration stacks below stay excluded
so the app keeps using the target system's GTK, GLib, D-Bus, and OpenSSL.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import time
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
STAGED_DIR = DIST_DIR / "AccessiWeather"
WORK_DIR = ROOT / "build" / "appimage"
TOOLS_DIR = WORK_DIR / "tools"
APPDIR = WORK_DIR / "AppDir"
APPIMAGE_ASSETS_DIR = ROOT / "installer" / "appimage"
ICON_SOURCE = ROOT / "src" / "accessiweather" / "resources" / "app_256.png"

LINUXDEPLOY_URL = (
    "https://github.com/linuxdeploy/linuxdeploy/releases/download/"
    "1-alpha-20251107-1/linuxdeploy-x86_64.AppImage"
)
APPIMAGE_RUNTIME_URL = (
    "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64"
)

# Libraries that must come from the target system, not the AppImage.
# Grouped by why bundling them would break users:
EXCLUDED_LIBRARY_GLOBS = (
    # GLib/GIO: host gio modules (GVFS, etc.) load into whichever GLib is in
    # the process; shipping our own triggers duplicate-GType registration
    # crashes ("cannot register existing type 'GTask'").
    "libglib-2.0*",
    "libgio-2.0*",
    "libgobject-2.0*",
    "libgmodule-2.0*",
    "libgthread-2.0*",
    # GTK/desktop + accessibility stack: must be the host's so AT-SPI (screen
    # readers), themes, and input methods work.
    "libgtk-3*",
    "libgdk-3*",
    "libgdk_pixbuf-2.0*",
    "libpango*",
    "libcairo*",
    "libpixman*",
    "libatk*",
    "libatspi*",
    "libnotify*",
    "libthai*",
    "libdatrie*",
    "libfribidi*",
    "libgraphite2*",
    "libharfbuzz*",
    # Host system plumbing tied to the running OS.
    "libdbus-1*",
    "libsystemd*",
    "libselinux*",
    "libcap*",
    "libmount*",
    "libblkid*",
    "liblz4*",
    "libgcrypt*",
    "libgpg-error*",
    # TLS/HTTP: use the distro's security-patched OpenSSL/curl stack.
    "libssl*",
    "libcrypto*",
    "libcurl*",
    "libgnutls*",
    "libnettle*",
    "libhogweed*",
    "libtasn1*",
    "libp11-kit*",
    "libidn2*",
    "libunistring*",
    "libpsl*",
    "libnghttp2*",
    "libssh*",
    "librtmp*",
    "liblber*",
    "libldap*",
    "libsasl2*",
    "libgssapi_krb5*",
    "libkrb5*",
    "libk5crypto*",
    "libkeyutils*",
    # Already shipped at the dist top level by Nuitka.
    "libpython*",
    "libreadline*",
    "libtinfo*",
)

# Sonames that must never appear in usr/lib (subset of the globs above that
# CI treats as hard failures — same philosophy as the tarball OpenSSL check).
FORBIDDEN_BUNDLED_PREFIXES = (
    "libssl",
    "libcrypto",
    "libglib-2.0",
    "libgio-2.0",
    "libgobject-2.0",
    "libgtk-3",
    "libgdk-3",
    "libatk",
    "libatspi",
)

# Sonames that must be present for non-Debian distros to work. These are the
# Ubuntu-soname dependencies of the wxPython wheel (and their non-universal
# transitive deps) that Fedora 43 was missing in the 0.9.0 tarball.
REQUIRED_BUNDLED_SONAMES = (
    "libjpeg.so.8",
    "libtiff.so.6",
    "libjbig.so.0",
    "libSDL2-2.0.so.0",
    "libsamplerate.so.0",
    "libpcre2-32.so.0",
    "libapparmor.so.1",
)


def get_version() -> str:
    """Read the package version from pyproject.toml."""
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def download(url: str, target: Path, attempts: int = 4) -> Path:
    """Download url to target with simple retries; keep an existing file."""
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            print(f"Downloading {url} (attempt {attempt})")
            with urllib.request.urlopen(url, timeout=120) as response:
                target.write_bytes(response.read())
            if target.stat().st_size == 0:
                raise OSError("downloaded file is empty")
            return target
        except OSError as exc:
            if attempt == attempts:
                raise RuntimeError(f"Failed to download {url}: {exc}") from exc
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def assemble_appdir() -> None:
    """Build the AppDir skeleton from the staged Nuitka distribution."""
    if APPDIR.exists():
        shutil.rmtree(APPDIR)
    (APPDIR / "opt").mkdir(parents=True)
    print(f"Copying {STAGED_DIR} into AppDir")
    shutil.copytree(STAGED_DIR, APPDIR / "opt" / "accessiweather")


def run_linuxdeploy(linuxdeploy: Path, runtime: Path, version: str) -> Path:
    """Run linuxdeploy and return the produced AppImage path."""
    command = [
        str(linuxdeploy),
        # Runner images ship without FUSE; run the AppImage tool extracted.
        "--appimage-extract-and-run",
        f"--appdir={APPDIR}",
        f"--deploy-deps-only={APPDIR / 'opt' / 'accessiweather'}",
        f"--desktop-file={APPIMAGE_ASSETS_DIR / 'accessiweather.desktop'}",
        f"--icon-file={WORK_DIR / 'accessiweather.png'}",
        f"--custom-apprun={APPIMAGE_ASSETS_DIR / 'AppRun'}",
        "--output=appimage",
    ]
    command.extend(f"--exclude-library={glob}" for glob in EXCLUDED_LIBRARY_GLOBS)

    env = os.environ.copy()
    env["LINUXDEPLOY_OUTPUT_VERSION"] = version
    env["LDAI_RUNTIME_FILE"] = str(runtime)

    shutil.copy2(ICON_SOURCE, WORK_DIR / "accessiweather.png")
    print("Running:", " ".join(command))
    subprocess.run(command, cwd=WORK_DIR, check=True, env=env)

    produced = sorted(WORK_DIR.glob("*.AppImage"), key=lambda p: p.stat().st_mtime)
    produced = [path for path in produced if path.name != linuxdeploy.name]
    if not produced:
        raise RuntimeError("linuxdeploy did not produce an AppImage")
    return produced[-1]


def verify_bundled_libraries() -> None:
    """Fail the build when usr/lib bundles host stacks or misses portability libs."""
    lib_dir = APPDIR / "usr" / "lib"
    bundled = {path.name for path in lib_dir.iterdir()} if lib_dir.exists() else set()

    forbidden = sorted(name for name in bundled if name.startswith(FORBIDDEN_BUNDLED_PREFIXES))
    if forbidden:
        raise RuntimeError(
            "AppImage must not bundle host-integration libraries "
            f"(GLib/GTK/OpenSSL stay on the target system): {forbidden}"
        )

    missing = sorted(set(REQUIRED_BUNDLED_SONAMES) - bundled)
    if missing:
        raise RuntimeError(f"AppImage is missing libraries needed on non-Debian distros: {missing}")
    print(f"Verified {len(bundled)} bundled libraries in usr/lib")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the AccessiWeather AppImage.")
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Keep build/appimage for debugging instead of reusing it clean.",
    )
    args = parser.parse_args()

    if platform.system() != "Linux":
        print("AppImage packaging only runs on Linux.")
        return 1
    if not (STAGED_DIR / "AccessiWeather").exists():
        print(f"Staged build not found at {STAGED_DIR}; run installer/build_nuitka.py first.")
        return 1

    version = get_version()
    print(f"AccessiWeather AppImage build, version {version}")

    if WORK_DIR.exists() and not args.keep_workdir:
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    linuxdeploy = download(LINUXDEPLOY_URL, TOOLS_DIR / "linuxdeploy-x86_64.AppImage")
    linuxdeploy.chmod(0o755)
    runtime = download(APPIMAGE_RUNTIME_URL, TOOLS_DIR / "runtime-x86_64")

    assemble_appdir()
    produced = run_linuxdeploy(linuxdeploy, runtime, version)
    verify_bundled_libraries()

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = DIST_DIR / f"AccessiWeather_Linux_v{version}_x86_64.AppImage"
    if target.exists():
        target.unlink()
    shutil.move(produced, target)
    target.chmod(0o755)
    print(f"Created {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
