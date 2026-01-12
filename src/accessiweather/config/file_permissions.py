"""Cross-platform file permission management for sensitive files."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Final

logger = logging.getLogger("accessiweather.config.permissions")

# Constants
POSIX_PERMISSIONS: Final = 0o600  # Owner read/write only
SUBPROCESS_TIMEOUT: Final = 5  # seconds


def set_secure_file_permissions(file_path: Path | str) -> bool:
    """
    Set restrictive file permissions (owner read/write only).

    This function restricts file access to only the current user:
    - On POSIX systems (Linux/macOS): Sets permissions to 0o600
    - On Windows: Uses icacls to remove inheritance and grant only current user

    Permission failures are logged but non-blocking - the function returns False
    but does not raise exceptions. This ensures config saves can succeed even if
    permission setting fails (e.g., on network drives or restricted filesystems).

    Args:
        file_path: Path to the file to protect (Path object or string)

    Returns:
        bool: True if permissions were set successfully, False otherwise

    Example:
        >>> config_file = Path("~/.config/app/config.json")
        >>> if set_secure_file_permissions(config_file):
        ...     logger.info("Config file secured")
        ... else:
        ...     logger.warning("Could not secure config file")

    """
    # Convert string to Path if needed
    if isinstance(file_path, str):
        file_path = Path(file_path)

    # Validate file exists
    if not file_path.exists():
        logger.debug(f"Cannot set permissions on non-existent file: {file_path}")
        return False

    # Platform-specific implementation
    try:
        if os.name == "nt":
            return _set_windows_permissions(file_path)
        else:
            return _set_posix_permissions(file_path)
    except Exception as e:
        # Catch any unexpected errors to maintain fail-safe behavior
        logger.debug(
            f"Unexpected error setting permissions on {file_path}: {e}", exc_info=True
        )
        return False


def _set_posix_permissions(file_path: Path) -> bool:
    """
    Set POSIX file permissions to 0o600 (owner read/write only).

    Args:
        file_path: Path to the file

    Returns:
        bool: True if successful, False otherwise

    """
    try:
        os.chmod(file_path, POSIX_PERMISSIONS)
        logger.debug(f"Set POSIX permissions (0o600) on {file_path}")
        return True

    except PermissionError as e:
        logger.debug(
            f"Permission denied setting POSIX permissions on {file_path}: {e}",
            exc_info=True,
        )
        return False

    except OSError as e:
        logger.debug(
            f"OS error setting POSIX permissions on {file_path}: {e}", exc_info=True
        )
        return False

    except Exception as e:
        logger.debug(
            f"Unexpected error setting POSIX permissions on {file_path}: {e}",
            exc_info=True,
        )
        return False


def _set_windows_permissions(file_path: Path) -> bool:
    """
    Set Windows file permissions to restrict access to current user only.

    Uses icacls.exe to:
    1. Remove inherited permissions (/inheritance:r)
    2. Grant current user full control (/grant:r %USERNAME%:(F))

    This is equivalent to POSIX 0o600 permissions.

    Args:
        file_path: Path to the file

    Returns:
        bool: True if successful, False otherwise

    """
    # Get current username from environment
    username = os.environ.get("USERNAME")
    if not username:
        logger.debug("USERNAME environment variable not set, cannot set Windows permissions")
        return False

    # Convert Path to string for subprocess
    file_str = str(file_path)

    try:
        # Run icacls command to set restrictive permissions
        # /inheritance:r = Remove inherited permissions
        # /grant:r = Grant permissions, replacing existing
        # (F) = Full control (Read, Write, Modify, Execute, Delete)
        result = subprocess.run(
            ["icacls", file_str, "/inheritance:r", "/grant:r", f"{username}:(F)"],
            check=True,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            # Prevent console window flash on Windows GUI apps
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        logger.debug(f"Set Windows permissions (user-only) on {file_path}")
        return True

    except subprocess.CalledProcessError as e:
        logger.debug(
            f"icacls failed to set permissions on {file_path}: {e.stderr}", exc_info=True
        )
        return False

    except subprocess.TimeoutExpired:
        logger.debug(
            f"icacls timed out setting permissions on {file_path} (>{SUBPROCESS_TIMEOUT}s)",
            exc_info=True,
        )
        return False

    except FileNotFoundError:
        # icacls.exe not found (extremely rare on modern Windows)
        logger.warning(
            f"icacls.exe not found on system, cannot set Windows permissions on {file_path}"
        )
        return False

    except Exception as e:
        logger.debug(
            f"Unexpected error setting Windows permissions on {file_path}: {e}",
            exc_info=True,
        )
        return False
