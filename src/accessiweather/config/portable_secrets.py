"""Encrypted portable secrets bundle helpers."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

BUNDLE_VERSION = 1
KDF_ITERATIONS = 390000
SALT_SIZE = 16


class PortableSecretsError(Exception):
    """Raised when encrypted portable secrets cannot be processed."""


def _derive_fernet_key(passphrase: str, salt: bytes, iterations: int = KDF_ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_secret_bundle(secrets: dict[str, str], passphrase: str) -> dict[str, Any]:
    """Encrypt a secrets dictionary for portability."""
    if not passphrase:
        raise PortableSecretsError("Passphrase is required")

    payload_bytes = json.dumps(secrets, separators=(",", ":")).encode("utf-8")
    salt = os.urandom(SALT_SIZE)
    key = _derive_fernet_key(passphrase, salt)
    token = Fernet(key).encrypt(payload_bytes)

    return {
        "version": BUNDLE_VERSION,
        "cipher": "fernet",
        "kdf": {
            "name": "pbkdf2-sha256",
            "iterations": KDF_ITERATIONS,
            "salt": base64.b64encode(salt).decode("ascii"),
        },
        "token": token.decode("ascii"),
    }


def decrypt_secret_bundle(envelope: dict[str, Any], passphrase: str) -> dict[str, str]:
    """Decrypt an encrypted secret bundle envelope."""
    if not passphrase:
        raise PortableSecretsError("Passphrase is required")

    if envelope.get("version") != BUNDLE_VERSION:
        raise PortableSecretsError(
            f"Unsupported encrypted bundle version: {envelope.get('version')}"
        )

    kdf = envelope.get("kdf")
    if not isinstance(kdf, dict):
        raise PortableSecretsError("Invalid encrypted bundle metadata")

    try:
        salt = base64.b64decode(str(kdf["salt"]))
        iterations = int(kdf.get("iterations", KDF_ITERATIONS))
        token = str(envelope["token"]).encode("ascii")
    except Exception as exc:
        raise PortableSecretsError(f"Invalid encrypted bundle fields: {exc}") from exc

    try:
        key = _derive_fernet_key(passphrase, salt, iterations=iterations)
        payload = Fernet(key).decrypt(token)
        data = json.loads(payload.decode("utf-8"))
    except InvalidToken as exc:
        raise PortableSecretsError("Invalid passphrase or corrupted bundle") from exc
    except Exception as exc:
        raise PortableSecretsError(f"Failed to decrypt encrypted bundle: {exc}") from exc

    if not isinstance(data, dict):
        raise PortableSecretsError("Invalid decrypted bundle payload")

    normalized: dict[str, str] = {}
    for key_name, value in data.items():
        if isinstance(key_name, str) and isinstance(value, str):
            normalized[key_name] = value

    return normalized
