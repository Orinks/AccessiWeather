"""
Cross-platform file permission management for sensitive files.

This module provides secure file permission setting for configuration files that may
contain user preferences, location data, and other semi-sensitive information. While
API keys are stored in the system keyring via SecureStorage, the JSON config file still
benefits from restricted access as a defense-in-depth measure.

Security Model:
    - POSIX systems (Linux/macOS): Use chmod to set 0o600 (owner read/write only)
    - Windows: Use icacls.exe to remove inherited permissions and grant only current user
    - Permission failures are logged but non-blocking to support restricted filesystems

The fail-safe design ensures config saves succeed even if permission setting fails
(e.g., on network drives, read-only filesystems, or restricted environments).

Typical usage:
    >>> from pathlib import Path
    >>> from accessiweather.config.file_permissions import set_secure_file_permissions
    >>> config_file = Path("~/.config/app/config.json")
    >>> if set_secure_file_permissions(config_file):
    ...     logger.info("Config file secured")
    ... else:
    ...     logger.warning("Could not secure config file, but save succeeded")
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Final

logger = logging.getLogger("accessiweather.config.permissions")

# Permission constants
# 0o600 = Owner read/write only (rw-------): Owner can read/write, group/others have no access
# This is the standard secure permission for sensitive config files on POSIX systems
POSIX_PERMISSIONS: Final = 0o600

# Subprocess timeout for Windows icacls command
# 5 seconds is generous - icacls typically completes in <100ms, but we allow headroom
# for slow filesystems or heavily-loaded systems
SUBPROCESS_TIMEOUT: Final = 5  # seconds


def set_secure_file_permissions(file_path: Path | str) -> bool:
    """
    Set restrictive file permissions to protect sensitive configuration files.

    This function restricts file access to only the current user, implementing
    defense-in-depth security for configuration files that may contain user
    preferences, location data, and other semi-sensitive information.

    Platform-specific implementations:
        - POSIX systems (Linux/macOS): Sets permissions to 0o600 using os.chmod()
          This translates to: rw------- (owner can read/write, no access for others)

        - Windows: Uses icacls.exe to:
          1. Remove inherited permissions (/inheritance:r)
          2. Grant only current user full control (/grant:r USERNAME:(F))
          This achieves equivalent security to POSIX 0o600

    Fail-safe design:
        Permission failures are logged at debug level but do NOT raise exceptions.
        The function returns False on failure but allows the calling code to continue.
        This ensures config saves succeed even in restricted environments such as:
        - Network drives with limited permission support
        - Read-only filesystems (after initial save)
        - Corporate environments with group policy restrictions
        - Container/sandbox environments

    Args:
        file_path: Path to the file to protect. Can be either a Path object or
                  a string path. String paths will be automatically converted to Path.

    Returns:
        bool: True if permissions were set successfully, False otherwise.
              A False return indicates the file is still accessible but may not
              have restrictive permissions applied.

    Raises:
        No exceptions are raised - all errors are caught and logged.

    Example:
        >>> from pathlib import Path
        >>> config_file = Path("~/.config/app/config.json")
        >>> if set_secure_file_permissions(config_file):
        ...     logger.info("Config file secured with restrictive permissions")
        ... else:
        ...     logger.warning("Could not secure config file, but save succeeded")

    Note:
        This function should be called AFTER writing the config file, typically
        following an atomic rename operation to ensure the file exists before
        attempting to set permissions.

    """
    # Convert string to Path if needed for consistent handling
    # This allows callers to pass either Path objects or string paths
    if isinstance(file_path, str):
        file_path = Path(file_path)

    # Validate file exists before attempting to set permissions
    # Setting permissions on a non-existent file would fail, so we check first
    if not file_path.exists():
        logger.debug(f"Cannot set permissions on non-existent file: {file_path}")
        return False

    # Dispatch to platform-specific implementation
    # os.name == "nt" indicates Windows (NT kernel)
    # All other systems (Linux, macOS, BSD, etc.) use POSIX permissions
    try:
        if os.name == "nt":
            return _set_windows_permissions(file_path)
        return _set_posix_permissions(file_path)
    except Exception as e:
        # Catch any unexpected errors to maintain fail-safe behavior
        # This is a safety net - platform-specific functions handle their own errors,
        # but we catch anything unexpected here to ensure no exceptions propagate
        logger.debug(f"Unexpected error setting permissions on {file_path}: {e}", exc_info=True)
        return False


def _set_posix_permissions(file_path: Path) -> bool:
    """
    Set POSIX file permissions to 0o600 (owner read/write only).

    This function uses os.chmod() to set the file mode to 0o600, which translates to:
        - Owner: read + write (rw-)
        - Group: no access (---)
        - Others: no access (---)

    This is the standard secure permission for sensitive files on POSIX-compliant
    systems (Linux, macOS, BSD, etc.). It ensures only the file owner can access
    the file, preventing other users on the system from reading or modifying it.

    Args:
        file_path: Path object pointing to the file to protect

    Returns:
        bool: True if permissions were set successfully, False on any error

    Errors handled:
        - PermissionError: Insufficient privileges to change permissions
        - OSError: Filesystem doesn't support permission changes (e.g., FAT32)
        - Exception: Any other unexpected error

    Note:
        All errors are logged at debug level with full traceback (exc_info=True)
        to aid in troubleshooting while keeping normal operation quiet.

    """
    try:
        # Use os.chmod to set the file mode to 0o600 (owner read/write only)
        os.chmod(file_path, POSIX_PERMISSIONS)
        logger.debug(f"Set POSIX permissions (0o600) on {file_path}")
        return True

    except PermissionError as e:
        # User doesn't have permission to change the file's permissions
        # This can happen if the file is owned by another user or if running
        # with insufficient privileges
        logger.debug(
            f"Permission denied setting POSIX permissions on {file_path}: {e}",
            exc_info=True,
        )
        return False

    except OSError as e:
        # Filesystem doesn't support POSIX permissions (e.g., FAT32, some network drives)
        # or other OS-level error occurred
        logger.debug(f"OS error setting POSIX permissions on {file_path}: {e}", exc_info=True)
        return False

    except Exception as e:
        # Catch-all for any unexpected errors (e.g., path becomes invalid during operation)
        logger.debug(
            f"Unexpected error setting POSIX permissions on {file_path}: {e}",
            exc_info=True,
        )
        return False


def _set_windows_permissions(file_path: Path) -> bool:
    """
    Set Windows file permissions to restrict access to current user only.

    This function uses the Windows icacls.exe command-line utility to configure
    file ACLs (Access Control Lists) for secure, user-only access. This achieves
    security equivalent to POSIX 0o600 permissions.

    Implementation details:
        Uses subprocess.run() to execute icacls.exe with the following flags:
        1. /inheritance:r - Remove all inherited permissions from parent directories
        2. /grant:r USERNAME:(F) - Grant (replacing existing) full control to current user

        The (F) permission set includes:
        - (R) Read data
        - (W) Write data
        - (M) Modify (write + delete)
        - (X) Execute (not applicable for config files, but included in Full)
        - (D) Delete
        - Permission to read/change permissions and ownership

    Why icacls instead of pywin32/win32security:
        - No external dependencies (icacls is built into Windows since Vista)
        - Simpler implementation using subprocess
        - Sufficient for our security requirements
        - Consistent with project's "avoid unnecessary dependencies" principle

    Args:
        file_path: Path object pointing to the file to protect

    Returns:
        bool: True if permissions were set successfully, False on any error

    Errors handled:
        - CalledProcessError: icacls command failed (e.g., access denied)
        - TimeoutExpired: Command took longer than SUBPROCESS_TIMEOUT (5 seconds)
        - FileNotFoundError: icacls.exe not found (extremely rare on modern Windows)
        - Exception: Any other unexpected error

    Security considerations:
        - Uses USERNAME environment variable to identify current user
        - CREATE_NO_WINDOW flag prevents console window flash in GUI mode
        - Timeout prevents indefinite hangs on slow/unresponsive filesystems
        - All output captured to prevent console spam

    Note:
        All errors are logged at debug level (or warning for missing icacls)
        with full traceback to aid troubleshooting while keeping normal operation quiet.

    """
    # Get current username from the Windows environment
    # USERNAME is a standard Windows environment variable set by the system
    username = os.environ.get("USERNAME")
    if not username:
        # This should never happen on a normal Windows system, but we check defensively
        logger.debug("USERNAME environment variable not set, cannot set Windows permissions")
        return False

    # Convert Path object to string for subprocess.run()
    # subprocess expects string paths in the command list
    file_str = str(file_path)

    try:
        # Execute icacls.exe to configure Windows ACLs (Access Control Lists)
        #
        # Command breakdown:
        #   icacls <file>           - ACL configuration utility (built into Windows)
        #   /inheritance:r          - Remove inherited permissions from parent directory
        #                             This ensures only explicitly set permissions apply
        #   /grant:r                - Grant permissions, replacing any existing permissions
        #   USERNAME:(F)            - Give current user Full control permission set
        #
        # The (F) permission includes Read, Write, Modify, Execute, Delete, and permission
        # management - equivalent to complete ownership, matching POSIX 0o600 security
        subprocess.run(
            ["icacls", file_str, "/inheritance:r", "/grant:r", f"{username}:(F)"],
            check=True,  # Raise CalledProcessError if icacls returns non-zero
            capture_output=True,  # Capture stdout/stderr to prevent console spam
            text=True,  # Decode output as text instead of bytes
            timeout=SUBPROCESS_TIMEOUT,  # Prevent indefinite hangs (5 second limit)
            # Prevent console window flash when running in GUI mode (e.g., Briefcase app)
            # CREATE_NO_WINDOW flag is Windows-specific, hence the os.name check
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        logger.debug(f"Set Windows permissions (user-only) on {file_path}")
        return True

    except subprocess.CalledProcessError as e:
        # icacls returned non-zero exit code (command failed)
        # Common causes: Access denied, file locked, filesystem doesn't support ACLs
        logger.debug(f"icacls failed to set permissions on {file_path}: {e.stderr}", exc_info=True)
        return False

    except subprocess.TimeoutExpired:
        # Command took longer than SUBPROCESS_TIMEOUT (5 seconds)
        # This can happen on network drives or heavily-loaded systems
        logger.debug(
            f"icacls timed out setting permissions on {file_path} (>{SUBPROCESS_TIMEOUT}s)",
            exc_info=True,
        )
        return False

    except FileNotFoundError:
        # icacls.exe not found in PATH (extremely rare on Windows Vista+)
        # This would indicate a severely damaged Windows installation
        logger.warning(
            f"icacls.exe not found on system, cannot set Windows permissions on {file_path}"
        )
        return False

    except Exception as e:
        # Catch-all for unexpected errors (e.g., path becomes invalid, memory issues)
        logger.debug(
            f"Unexpected error setting Windows permissions on {file_path}: {e}",
            exc_info=True,
        )
        return False
