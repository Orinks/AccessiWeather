"""Add a new application bundle to the TUF repository.

This script adds a new version of AccessiWeather to the TUF repository,
creating archives and patches as needed.
"""

import argparse
import sys
from pathlib import Path

# Add the repo directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from repo_settings import APP_NAME, BUILD_DIR, KEYS_DIR, REPO_DIR, TARGETS_DIR
    from tufup.repo import Repository
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure tufup is installed: pip install tufup")
    sys.exit(1)


def find_briefcase_build(version: str) -> Path:
    """Find the Briefcase build directory for the given version.

    Args:
        version: Version string to look for

    Returns:
        Path to the build directory

    """
    # Common Briefcase build paths
    possible_paths = [
        BUILD_DIR / "accessiweather" / "windows" / "app",
        BUILD_DIR / "accessiweather" / "linux" / "appimage" / "AccessiWeather.AppImage",
        BUILD_DIR / "accessiweather" / "macOS" / "app",
        # Fallback to any directory in build/
        BUILD_DIR / "accessiweather",
    ]

    for path in possible_paths:
        if path.exists():
            print(f"Found build directory: {path}")
            return path

    # If not found, list available directories
    print(f"Build directory not found. Available directories in {BUILD_DIR}:")
    if BUILD_DIR.exists():
        for item in BUILD_DIR.iterdir():
            if item.is_dir():
                print(f"  - {item}")
    else:
        print(f"  Build directory {BUILD_DIR} does not exist")

    raise FileNotFoundError(f"Could not find Briefcase build directory for version {version}")


def main():
    """Add a bundle to the TUF repository."""
    parser = argparse.ArgumentParser(description="Add AccessiWeather bundle to TUF repository")
    parser.add_argument("version", help="Version string (e.g., 0.9.5)")
    parser.add_argument(
        "--bundle-dir", help="Path to bundle directory (auto-detected if not provided)"
    )
    parser.add_argument("--skip-patch", "-s", action="store_true", help="Skip patch creation")
    parser.add_argument("--custom-metadata", help="Custom metadata JSON string")

    args = parser.parse_args()

    print(f"Adding AccessiWeather v{args.version} to TUF repository...")

    try:
        # Find bundle directory
        if args.bundle_dir:
            bundle_dir = Path(args.bundle_dir)
        else:
            bundle_dir = find_briefcase_build(args.version)

        if not bundle_dir.exists():
            print(f"❌ Bundle directory not found: {bundle_dir}")
            return 1

        print(f"📁 Bundle directory: {bundle_dir}")

        # Create repository instance
        repo = Repository(
            app_name=APP_NAME,
            app_version_attr="__version__",
            repo_dir=REPO_DIR,
            keys_dir=KEYS_DIR,
        )

        # Parse custom metadata if provided
        custom_metadata = None
        if args.custom_metadata:
            import json

            try:
                custom_metadata = json.loads(args.custom_metadata)
            except json.JSONDecodeError as e:
                print(f"❌ Invalid custom metadata JSON: {e}")
                return 1

        # Add bundle to repository
        print(f"📦 Adding bundle version {args.version}...")
        repo.add_bundle(
            new_version=args.version,
            new_bundle_dir=bundle_dir,
            skip_patch=args.skip_patch,
            custom_metadata=custom_metadata,
        )

        print("✅ Bundle added successfully!")

        # Show repository contents
        print(f"\n📋 Repository contents in {TARGETS_DIR}:")
        for item in sorted(TARGETS_DIR.glob("*")):
            size_mb = item.stat().st_size / (1024 * 1024)
            print(f"   - {item.name} ({size_mb:.1f} MB)")

        print(f"\n🚀 Next steps:")
        print("1. Upload the repository/ directory to orinks.net/updates/")
        print("2. Test the update in your application")
        print("3. Announce the new version to users")

        print(f"\n📤 Upload command example:")
        print(f"   rsync -av {REPO_DIR}/ user@orinks.net:/path/to/updates/")

    except Exception as e:
        print(f"❌ Failed to add bundle: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
