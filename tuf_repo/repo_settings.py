"""TUF Repository settings for AccessiWeather.

This module contains configuration settings for the TUF update repository.
"""

from pathlib import Path

from tufup.repo import DEFAULT_KEY_MAP

# Repository configuration
APP_NAME = "accessiweather"
MODULE_DIR = Path(__file__).resolve().parent

# Directories
REPO_DIR = MODULE_DIR / "repository"
KEYS_DIR = MODULE_DIR / "keystore"
BUILD_DIR = MODULE_DIR.parent / "build"

# TUF metadata URLs (will be hosted on orinks.net)
METADATA_BASE_URL = "https://orinks.net/updates/metadata"
TARGET_BASE_URL = "https://orinks.net/updates/targets"

# Key configuration
KEY_NAME = "accessiweather_key"
PRIVATE_KEY_PATH = KEYS_DIR / KEY_NAME
KEY_MAP = {role_name: [KEY_NAME] for role_name in DEFAULT_KEY_MAP}
ENCRYPTED_KEYS: list[
    str
] = []  # For simplicity, keys are not encrypted (not recommended for production)
THRESHOLDS = {"root": 1, "targets": 1, "snapshot": 1, "timestamp": 1}
EXPIRATION_DAYS = {"root": 365, "targets": 30, "snapshot": 7, "timestamp": 1}

# Ensure directories exist
REPO_DIR.mkdir(exist_ok=True)
KEYS_DIR.mkdir(exist_ok=True)

# Repository structure
METADATA_DIR = REPO_DIR / "metadata"
TARGETS_DIR = REPO_DIR / "targets"

METADATA_DIR.mkdir(exist_ok=True)
TARGETS_DIR.mkdir(exist_ok=True)

print(f"Repository directory: {REPO_DIR}")
print(f"Keystore directory: {KEYS_DIR}")
print(f"Build directory: {BUILD_DIR}")
