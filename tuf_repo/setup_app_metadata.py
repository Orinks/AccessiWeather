"""Setup script to integrate TUF root metadata into AccessiWeather app.

This script copies the TUF root.json file to the appropriate location
so it gets included in the Briefcase build.
"""

import shutil
import sys
from pathlib import Path

# Add the repo directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from repo_settings import METADATA_DIR, REPO_DIR
except ImportError as e:
    print(f"Error importing repo settings: {e}")
    sys.exit(1)


def main():
    """Copy root.json to app resources."""
    print("Setting up TUF metadata for AccessiWeather...")

    # Source: TUF repository root metadata
    root_json_source = METADATA_DIR / "root.json"

    # Destination: App resources directory
    app_src_dir = Path(__file__).parent.parent / "src" / "accessiweather"
    resources_dir = app_src_dir / "resources"

    # Create resources directory if it doesn't exist
    resources_dir.mkdir(exist_ok=True)

    root_json_dest = resources_dir / "root.json"

    try:
        if not root_json_source.exists():
            print(f"❌ Root metadata not found: {root_json_source}")
            print("Run 'python repo_init.py' first to initialize the TUF repository.")
            return 1

        # Copy root.json to resources
        shutil.copy2(root_json_source, root_json_dest)

        print(f"✅ Root metadata copied successfully!")
        print(f"📁 Source: {root_json_source}")
        print(f"📁 Destination: {root_json_dest}")

        # Verify the copy
        if root_json_dest.exists():
            size = root_json_dest.stat().st_size
            print(f"📊 File size: {size} bytes")

        print("\n📋 Next steps:")
        print("1. Build your app: briefcase package")
        print("2. The root.json will be automatically included in the build")
        print("3. Add your first version: python repo_add_bundle.py 0.9.4")

        return 0

    except Exception as e:
        print(f"❌ Failed to copy root metadata: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
