"""GPG signature verification for update downloads."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# Embedded public key for AccessiWeather release signing
# This is a placeholder public key - replace with actual AccessiWeather release signing key
ACCESSIWEATHER_PUBLIC_KEY = """-----BEGIN PGP PUBLIC KEY BLOCK-----

mQINBGExample1EAD...
(Placeholder - Replace with actual public key)
...
-----END PGP PUBLIC KEY BLOCK-----"""


class SignatureVerifier:
    """Handles GPG signature verification for update downloads."""

    @staticmethod
    def _verify_gpg_signature(
        file_path: Path, signature_data: bytes, public_key: str
    ) -> bool:
        """
        Verify a detached GPG signature against a file.

        Args:
            file_path: Path to the file to verify
            signature_data: Raw bytes of the detached signature
            public_key: ASCII-armored public key to verify against

        Returns:
            True if signature is valid, False otherwise

        """
        try:
            import pgpy
        except ImportError:
            logger.error(
                "PGPy library not available - cannot verify signature for %s",
                file_path,
            )
            return False

        try:
            # Load public key
            pub_key, _ = pgpy.PGPKey.from_blob(public_key)

            # Load signature
            signature = pgpy.PGPSignature.from_blob(signature_data)

            # Read file content
            with open(file_path, "rb") as file_obj:
                file_content = file_obj.read()

            # Verify signature
            verification = pub_key.verify(file_content, signature)

            if not verification:
                logger.error(
                    "GPG signature verification failed for %s",
                    file_path,
                )
                file_path.unlink(missing_ok=True)
                return False

            logger.info(
                "GPG signature verified successfully for %s",
                file_path,
            )
            return True

        except Exception as exc:
            logger.error(
                "GPG signature verification error for %s: %s",
                file_path,
                exc,
            )
            file_path.unlink(missing_ok=True)
            return False
