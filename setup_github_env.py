#!/usr/bin/env python3
"""Setup script to configure GitHub App environment variables for AccessiWeather.

This script reads the GitHub App credentials from AccessiBotApp Configuration.txt
and sets them as environment variables for secure access.

Usage:
    python setup_github_env.py

Environment variables set:
    ACCESSIWEATHER_GITHUB_APP_ID
    ACCESSIWEATHER_GITHUB_APP_PRIVATE_KEY
    ACCESSIWEATHER_GITHUB_APP_INSTALLATION_ID
"""

import os
import sys
from pathlib import Path


def read_github_app_config():
    """Read GitHub App configuration from the text file."""
    config_file = Path("AccessiBotApp Configuration.txt")

    if not config_file.exists():
        print(f"Error: Configuration file not found: {config_file}")
        print("Please ensure AccessiBotApp Configuration.txt exists in the current directory.")
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


def set_environment_variables(config):
    """Set environment variables for the current session."""
    env_vars = {
        "ACCESSIWEATHER_GITHUB_APP_ID": config["app_id"],
        "ACCESSIWEATHER_GITHUB_APP_INSTALLATION_ID": config["installation_id"],
        "ACCESSIWEATHER_GITHUB_APP_PRIVATE_KEY": config["private_key"],
    }

    for var_name, var_value in env_vars.items():
        os.environ[var_name] = var_value
        print(f"✓ Set {var_name}")

    return env_vars


def generate_batch_file(config):
    """Generate a Windows batch file to set environment variables."""
    # Escape the private key for batch file (replace newlines with ^)
    private_key_escaped = config["private_key"].replace("\n", "^")

    batch_content = f"""@echo off
REM AccessiWeather GitHub App Environment Variables
REM Generated automatically - do not commit this file to version control

set "ACCESSIWEATHER_GITHUB_APP_ID={config["app_id"]}"
set "ACCESSIWEATHER_GITHUB_APP_INSTALLATION_ID={config["installation_id"]}"
set "ACCESSIWEATHER_GITHUB_APP_PRIVATE_KEY={private_key_escaped}"

echo GitHub App environment variables set for AccessiWeather
echo You can now run AccessiWeather with GitHub App authentication enabled
"""

    batch_file = Path("set_github_env.bat")
    with open(batch_file, "w", encoding="utf-8") as f:
        f.write(batch_content)

    print(f"✓ Generated batch file: {batch_file}")
    return batch_file


def generate_shell_script(config):
    """Generate a shell script to set environment variables."""
    shell_content = f"""#!/bin/bash
# AccessiWeather GitHub App Environment Variables
# Generated automatically - do not commit this file to version control

export ACCESSIWEATHER_GITHUB_APP_ID="{config["app_id"]}"
export ACCESSIWEATHER_GITHUB_APP_INSTALLATION_ID="{config["installation_id"]}"
export ACCESSIWEATHER_GITHUB_APP_PRIVATE_KEY="{config["private_key"]}"

echo "GitHub App environment variables set for AccessiWeather"
echo "You can now run AccessiWeather with GitHub App authentication enabled"
"""

    shell_file = Path("set_github_env.sh")
    with open(shell_file, "w", encoding="utf-8") as f:
        f.write(shell_content)

    # Make executable on Unix-like systems
    if hasattr(os, "chmod"):
        os.chmod(shell_file, 0o755)

    print(f"✓ Generated shell script: {shell_file}")
    return shell_file


def main():
    """Set up GitHub App environment variables."""
    print("AccessiWeather GitHub App Environment Setup")
    print("=" * 45)

    # Read configuration
    config = read_github_app_config()
    if not config:
        sys.exit(1)

    print("✓ Successfully read GitHub App configuration")

    # Set environment variables for current session
    set_environment_variables(config)

    # Generate platform-specific scripts
    if os.name == "nt":  # Windows
        generate_batch_file(config)
        print("\nTo use in future sessions, run: set_github_env.bat")
    else:  # Unix-like
        generate_shell_script(config)
        print("\nTo use in future sessions, run: source set_github_env.sh")

    print("\n✓ Setup complete! GitHub App credentials are now available as environment variables.")
    print("\nSecurity Note: The generated script files contain sensitive credentials.")
    print("Make sure they are not committed to version control.")


if __name__ == "__main__":
    main()
