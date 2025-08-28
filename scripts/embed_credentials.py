#!/usr/bin/env python3
"""Build script to embed GitHub App credentials for distribution.

This script is used during the build process to embed GitHub App credentials
into the distributed application, so end users don't need to configure anything.

Usage:
    python scripts/embed_credentials.py

The script:
1. Reads credentials from AccessiBotApp Configuration.txt
2. Replaces placeholders in src/accessiweather/github_credentials.py
3. Creates a backup of the original file for restoration

Security:
- Only runs during build process
- Original file is restored after build
- Credentials are never committed to source control
"""

import shutil
import sys
from pathlib import Path


def read_github_app_config():
    """Read GitHub App configuration from the text file."""
    config_file = Path("AccessiBotApp Configuration.txt")

    if not config_file.exists():
        print(f"Error: Configuration file not found: {config_file}")
        print("Make sure AccessiBotApp Configuration.txt exists in the project root.")
        return None

    try:
        with open(config_file, encoding="utf-8") as f:
            content = f.read()

        # Extract App ID
        app_id = None
        for line in content.split("\n"):
            if line.startswith("App ID:"):
                app_id = line.split(":", 1)[1].strip()
                break

        # Extract Installation ID
        installation_id = None
        for line in content.split("\n"):
            if line.startswith("Installation ID:"):
                installation_id = line.split(":", 1)[1].strip()
                break

        # Extract Private Key
        private_key = None
        if "-----BEGIN RSA PRIVATE KEY-----" in content:
            start = content.find("-----BEGIN RSA PRIVATE KEY-----")
            end = content.find("-----END RSA PRIVATE KEY-----") + len(
                "-----END RSA PRIVATE KEY-----"
            )
            private_key = content[start:end].strip()

        if not all([app_id, installation_id, private_key]):
            print("Error: Could not extract all required credentials from configuration file.")
            print(f"Found - App ID: {'✓' if app_id else '✗'}")
            print(f"Found - Installation ID: {'✓' if installation_id else '✗'}")
            print(f"Found - Private Key: {'✓' if private_key else '✗'}")
            return None

        return {"app_id": app_id, "installation_id": installation_id, "private_key": private_key}

    except Exception as e:
        print(f"Error reading configuration file: {e}")
        return None


def embed_credentials():
    """Embed credentials into the github_credentials.py file."""
    credentials_file = Path("src/accessiweather/github_credentials.py")
    backup_file = Path("src/accessiweather/github_credentials.py.backup")

    if not credentials_file.exists():
        print(f"Error: Credentials file not found: {credentials_file}")
        return False

    # Read credentials
    config = read_github_app_config()
    if not config:
        return False

    print("📋 Embedding GitHub App credentials for distribution...")

    # Create backup
    shutil.copy2(credentials_file, backup_file)
    print(f"✅ Created backup: {backup_file}")

    # Read the original file
    with open(credentials_file, encoding="utf-8") as f:
        content = f.read()

    # Replace placeholders with actual credentials
    # Escape quotes and newlines in the private key for Python string literal
    private_key_escaped = (
        config["private_key"].replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    )

    content = content.replace("BUILD_PLACEHOLDER_APP_ID", config["app_id"])
    content = content.replace("BUILD_PLACEHOLDER_INSTALLATION_ID", config["installation_id"])
    content = content.replace("BUILD_PLACEHOLDER_PRIVATE_KEY", private_key_escaped)

    # Write the modified file
    with open(credentials_file, "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ Credentials embedded successfully")
    print(f"   App ID: {config['app_id']}")
    print(f"   Installation ID: {config['installation_id']}")
    print(f"   Private Key: ***REDACTED*** ({len(config['private_key'])} chars)")

    return True


def restore_credentials():
    """Restore the original credentials file from backup."""
    credentials_file = Path("src/accessiweather/github_credentials.py")
    backup_file = Path("src/accessiweather/github_credentials.py.backup")

    if backup_file.exists():
        shutil.copy2(backup_file, credentials_file)
        backup_file.unlink()  # Remove backup
        print("✅ Restored original credentials file")
        return True
    print("⚠️  No backup file found to restore")
    return False


def main():
    """Execute the credential embedding process."""
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        print("🔄 Restoring original credentials file...")
        success = restore_credentials()
        sys.exit(0 if success else 1)

    print("🔧 AccessiWeather Build: Embedding GitHub App Credentials")
    print("=" * 55)

    success = embed_credentials()

    if success:
        print("\n✅ Credentials embedding complete!")
        print("\n⚠️  IMPORTANT:")
        print("   - The credentials are now embedded in the source code")
        print("   - Run 'python scripts/embed_credentials.py restore' after build")
        print("   - Do not commit the modified github_credentials.py file")
    else:
        print("\n❌ Failed to embed credentials")
        sys.exit(1)


if __name__ == "__main__":
    main()
