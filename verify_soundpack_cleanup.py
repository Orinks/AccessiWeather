#!/usr/bin/env python3
"""Verify that built applications only contain the default soundpack."""

import sys
import zipfile
from pathlib import Path


def verify_zip_soundpacks(zip_path: Path) -> bool:
    """Verify that a ZIP file only contains the default soundpack."""
    if not zip_path.exists():
        print(f"❌ ZIP file not found: {zip_path}")
        return False

    print(f"🔍 Checking soundpacks in: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Find all soundpack directories
        soundpack_dirs = set()
        for file_info in zf.filelist:
            path_parts = file_info.filename.split("/")
            # Look for paths like: app/accessiweather/soundpacks/NAME/
            if len(path_parts) >= 4 and path_parts[-3] == "soundpacks" and path_parts[-2] != "":
                soundpack_name = path_parts[-2]
                if soundpack_name not in [".gitkeep", "__pycache__"]:
                    soundpack_dirs.add(soundpack_name)

        if not soundpack_dirs:
            print("❌ No soundpacks found in ZIP")
            return False

        expected_soundpacks = {"default"}

        if soundpack_dirs == expected_soundpacks:
            print(f"✅ Only default soundpack found: {sorted(soundpack_dirs)}")
            return True
        print(f"❌ Unexpected soundpacks found: {sorted(soundpack_dirs)}")
        print(f"   Expected: {sorted(expected_soundpacks)}")
        return False


def main():
    """Verify soundpack cleanup in built artifacts."""
    dist_dir = Path(__file__).parent / "dist"

    # Find the latest ZIP file
    zip_files = list(dist_dir.glob("AccessiWeather_Portable_v*.zip"))

    if not zip_files:
        print("❌ No portable ZIP files found in dist/")
        return 1

    # Use the most recent ZIP file
    latest_zip = max(zip_files, key=lambda p: p.stat().st_mtime)

    success = verify_zip_soundpacks(latest_zip)

    if success:
        print("🎉 Soundpack verification passed!")
        return 0
    print("💥 Soundpack verification failed!")
    return 1


if __name__ == "__main__":
    sys.exit(main())
