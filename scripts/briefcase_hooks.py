"""Briefcase build hooks for AccessiWeather.

These hooks automatically embed GitHub App credentials during the build process
and restore the original files afterward, ensuring users get a fully configured
app without needing to set up environment variables.
"""

import subprocess
import sys
from pathlib import Path


def pre_build_hook(command, **kwargs):
    """Pre-build hook: Embed GitHub App credentials before building."""
    print("🔧 Pre-build: Embedding GitHub App credentials...")

    # Run the embed credentials script
    script_path = Path("scripts/embed_credentials.py")
    if not script_path.exists():
        print("⚠️  Warning: Embed credentials script not found, skipping credential embedding")
        return

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)], check=True, capture_output=True, text=True
        )

        print("✅ Credentials embedded successfully")
        if result.stdout:
            print(result.stdout)

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to embed credentials: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        # Don't fail the build - just warn
        print("⚠️  Continuing build without embedded credentials")


def post_build_hook(command, **kwargs):
    """Post-build hook: Restore original credentials file after building."""
    print("🔄 Post-build: Restoring original credentials file...")

    # Run the restore credentials script
    script_path = Path("scripts/embed_credentials.py")
    if not script_path.exists():
        print("⚠️  Warning: Embed credentials script not found, skipping restore")
        return

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "restore"],
            check=True,
            capture_output=True,
            text=True,
        )

        print("✅ Original credentials file restored")
        if result.stdout:
            print(result.stdout)

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to restore credentials: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        # Don't fail the build - just warn
        print("⚠️  Original file may not be restored")
