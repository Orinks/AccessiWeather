"""Checksum lookup, parsing, and verification helpers for update downloads."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class ChecksumVerificationError(Exception):
    """Raised when a downloaded artifact fails checksum verification."""


def find_checksum_asset(
    release: dict[str, Any],
    artifact_name: str,
) -> dict[str, Any] | None:
    """
    Find a checksum asset (.sha256, .sha512) matching the given artifact.

    Looks for files named like ``<artifact_name>.sha256`` or a generic
    ``checksums.sha256`` / ``SHA256SUMS`` file that may contain the hash.
    """
    assets = release.get("assets", [])
    lower_artifact = artifact_name.lower()

    for ext in (".sha256", ".sha512"):
        for asset in assets:
            name = asset.get("name", "").lower()
            if name == lower_artifact + ext:
                return asset

    generic_names = (
        "checksums.sha256",
        "sha256sums",
        "checksums.sha512",
        "sha512sums",
        "checksums.txt",
    )
    for asset in assets:
        name = asset.get("name", "").lower()
        if name in generic_names:
            return asset

    return None


def parse_checksum_file(content: str, artifact_name: str) -> tuple[str, str] | None:
    """
    Parse a checksum file and extract the hash for the given artifact.

    Supports a single-hash file and BSD/GNU checksum files.
    """
    lines = content.strip().splitlines()
    lower_artifact = artifact_name.lower()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        hex_hash = parts[0]

        algo = _algorithm_for_hash_length(len(hex_hash))
        if algo is None:
            continue

        if len(parts) == 1 and len(lines) == 1:
            return algo, hex_hash.lower()

        if len(parts) == 2:
            filename = parts[1].lstrip("*").strip()
            if filename.lower() == lower_artifact:
                return algo, hex_hash.lower()

    return None


def verify_file_checksum(file_path: Path, algorithm: str, expected_hash: str) -> bool:
    """Verify a file's checksum against an expected hash."""
    try:
        h = hashlib.new(algorithm)
    except ValueError as err:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}") from err

    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)

    actual = h.hexdigest().lower()
    return actual == expected_hash.lower()


def _algorithm_for_hash_length(hash_len: int) -> str | None:
    if hash_len == 64:
        return "sha256"
    if hash_len == 128:
        return "sha512"
    if hash_len == 32:
        return "md5"
    return None
