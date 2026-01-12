"""
Path validation utilities for secure file path handling.

This module provides security-focused path validation functions to prevent
command injection, path traversal, and other file-based security vulnerabilities.

Typical usage:
    from accessiweather.utils.path_validator import validate_executable_path

    # Validate an MSI installer path
    msi_path = validate_executable_path(
        downloaded_file,
        expected_suffix=".msi",
        expected_parent=update_cache_dir
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Exception raised when a security validation check fails."""


def validate_file_extension(
    file_path: Path | str,
    expected_suffix: str,
) -> None:
    """
    Validate that a file has the expected extension.

    Args:
        file_path: Path to validate
        expected_suffix: Required file extension (e.g., ".msi", ".zip", ".bat")

    Raises:
        ValueError: If the file extension doesn't match the expected suffix

    """
    path = Path(file_path)
    if path.suffix.lower() != expected_suffix.lower():
        raise ValueError(f"Invalid file type: expected {expected_suffix}, got {path.suffix}")


def validate_file_exists(file_path: Path | str) -> None:
    """
    Validate that a file exists.

    Args:
        file_path: Path to validate

    Raises:
        FileNotFoundError: If the file doesn't exist

    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")


def validate_no_path_traversal(file_path: Path | str) -> None:
    """
    Check for path traversal attempts in a file path.

    This function checks for common path traversal patterns that could
    be used to access files outside the intended directory.

    Args:
        file_path: Path to validate

    Raises:
        SecurityError: If path traversal patterns are detected

    """
    path = Path(file_path)

    # Check for ".." in path components
    if ".." in path.parts:
        raise SecurityError(f"Path traversal detected in: {path}")

    # Additional check: ensure resolved path doesn't escape when combined with resolve()
    # This is a defense-in-depth measure
    try:
        resolved = path.resolve()
        # Check if any part contains suspicious patterns
        resolved_str = str(resolved)
        if ".." in resolved_str:
            raise SecurityError(f"Path traversal detected after resolution: {resolved}")
    except (OSError, RuntimeError) as e:
        # resolve() can fail on invalid paths
        raise SecurityError(f"Invalid path during resolution: {path}") from e


def validate_path_within_directory(
    file_path: Path | str,
    expected_parent: Path | str,
) -> None:
    """
    Verify that a file path is within an expected parent directory.

    This function ensures that after resolving symlinks and relative paths,
    the file is located within the expected parent directory.

    Args:
        file_path: Path to validate
        expected_parent: Expected parent directory

    Raises:
        SecurityError: If the path is outside the expected directory

    """
    path = Path(file_path).resolve()
    parent = Path(expected_parent).resolve()

    try:
        path.relative_to(parent)
    except ValueError as e:
        raise SecurityError(f"Path {path} is outside expected directory {parent}") from e


def validate_no_suspicious_characters(file_path: Path | str) -> None:
    """
    Check for suspicious characters in a filename.

    Windows doesn't allow certain characters in filenames: < > : " | ? *
    This function validates that the filename (not the full path) doesn't
    contain these suspicious characters.

    Args:
        file_path: Path to validate

    Raises:
        SecurityError: If suspicious characters are found in the filename

    """
    path = Path(file_path)

    # Windows filename restrictions (excluding backslash which is valid in paths)
    suspicious_chars = ["<", ">", ":", '"', "|", "?", "*"]

    # Check only the filename, not the full path
    if any(char in path.name for char in suspicious_chars):
        raise SecurityError(f"Suspicious characters in filename: {path.name}")


def validate_executable_path(
    file_path: Path | str,
    expected_suffix: str,
    expected_parent: Path | str | None = None,
) -> Path:
    """
    Comprehensively validate a file path before subprocess execution.

    This function performs multiple security checks to ensure the file path
    is safe for use in subprocess operations. It validates the extension,
    checks for file existence, resolves to an absolute path, checks for
    path traversal attempts, verifies the path is within the expected
    directory (if provided), and checks for suspicious characters.

    Args:
        file_path: Path to validate
        expected_suffix: Required file extension (e.g., ".msi", ".zip", ".bat")
        expected_parent: If provided, ensure file is within this directory

    Returns:
        Resolved absolute Path object

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file extension is invalid
        SecurityError: If any security validation fails

    Example:
        >>> cache_dir = Path.home() / ".config" / "accessiweather" / "update_cache"
        >>> msi_path = validate_executable_path(
        ...     "update.msi",
        ...     expected_suffix=".msi",
        ...     expected_parent=cache_dir
        ... )
        >>> subprocess.Popen(["msiexec", "/i", str(msi_path)])

    """
    path = Path(file_path)

    # 1. Check file exists
    validate_file_exists(path)

    # 2. Verify extension
    validate_file_extension(path, expected_suffix)

    # 3. Resolve to absolute path (also resolves symlinks)
    resolved_path = path.resolve()

    # 4. Check for path traversal attempts
    validate_no_path_traversal(path)

    # 5. Verify within expected parent directory (if provided)
    if expected_parent:
        validate_path_within_directory(resolved_path, expected_parent)

    # 6. Check for suspicious characters
    validate_no_suspicious_characters(resolved_path)

    logger.debug("Path validation successful: %s", resolved_path)
    return resolved_path
