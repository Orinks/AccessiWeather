"""Initialize TUF repository for AccessiWeather.

This script initializes a new TUF repository with the necessary keys and metadata.
Run this once to set up the update repository.
"""

import sys
from pathlib import Path

# Add the repo directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from repo_settings import (
        APP_NAME,
        ENCRYPTED_KEYS,
        EXPIRATION_DAYS,
        KEY_MAP,
        KEYS_DIR,
        METADATA_DIR,
        REPO_DIR,
        TARGETS_DIR,
        THRESHOLDS,
    )
    from tufup.repo import Repository
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure tufup is installed: pip install tufup")
    sys.exit(1)


def main():
    """Initialize the TUF repository."""
    print("Initializing TUF repository for AccessiWeather...")

    try:
        # Create repository instance
        repo = Repository(
            app_name=APP_NAME,
            app_version_attr="__version__",
            repo_dir=REPO_DIR,
            keys_dir=KEYS_DIR,
            key_map=KEY_MAP,
            encrypted_keys=ENCRYPTED_KEYS,
            thresholds=THRESHOLDS,
            expiration_days=EXPIRATION_DAYS,
        )

        # Save configuration
        repo.save_config()

        # Initialize repository (creates keys and root metadata)
        repo.initialize()

        print("✅ TUF repository initialized successfully!")
        print(f"📁 Repository directory: {REPO_DIR}")
        print(f"🔑 Keystore directory: {KEYS_DIR}")
        print(f"📋 Metadata directory: {METADATA_DIR}")
        print(f"🎯 Targets directory: {TARGETS_DIR}")

        print("\n📋 Next steps:")
        print("1. Build your application with Briefcase: briefcase package")
        print("2. Add the first version: python repo_add_bundle.py")
        print("3. Upload the repository/ directory to orinks.net/updates/")
        print("4. Include root.json in your application bundle")

        # Show generated keys
        print(f"\n🔑 Generated keys in {KEYS_DIR}:")
        for key_file in KEYS_DIR.glob("*"):
            print(f"   - {key_file.name}")

        print("\n⚠️  IMPORTANT: Keep the keystore/ directory secure and backed up!")
        print("   Never upload keystore/ to your web server or version control.")

    except Exception as e:
        print(f"❌ Failed to initialize repository: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
