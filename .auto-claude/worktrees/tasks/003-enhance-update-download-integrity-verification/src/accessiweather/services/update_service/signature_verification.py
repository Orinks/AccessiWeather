"""GPG signature verification for update downloads."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import aiohttp

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
    def _verify_gpg_signature(file_path: Path, signature_data: bytes, public_key: str) -> bool:
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

    @staticmethod
    async def download_and_verify_signature(
        file_path: Path,
        signature_url: str,
        public_key: str = ACCESSIWEATHER_PUBLIC_KEY,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> bool:
        """
        Download signature file and verify it against the downloaded file.

        This method downloads a detached signature file (.sig or .asc) from the given URL
        and verifies it against the file at file_path using GPG signature verification.
        Includes retry logic with exponential backoff for network failures.

        Args:
            file_path: Path to the file to verify
            signature_url: URL to download the signature file from
            public_key: ASCII-armored public key to verify against (defaults to ACCESSIWEATHER_PUBLIC_KEY)
            max_retries: Maximum number of download retry attempts (default: 3)
            retry_delay: Initial delay in seconds between retries (default: 1.0, doubles each retry)

        Returns:
            True if signature was downloaded and verified successfully, False otherwise

        """
        if not file_path.exists():
            logger.error(
                "File does not exist for signature verification: %s",
                file_path,
            )
            return False

        for attempt in range(max_retries):
            try:
                # Download signature file
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(
                        signature_url,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response,
                ):
                    if response.status != 200:
                        logger.warning(
                            "Failed to download signature from %s: HTTP %d (attempt %d/%d)",
                            signature_url,
                            response.status,
                            attempt + 1,
                            max_retries,
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (2**attempt))
                            continue
                        return False

                    signature_data = await response.read()

                    if not signature_data:
                        logger.error(
                            "Downloaded empty signature file from %s",
                            signature_url,
                        )
                        return False

                    logger.info(
                        "Downloaded signature file from %s (%d bytes)",
                        signature_url,
                        len(signature_data),
                    )

                    # Verify the signature
                    return SignatureVerifier._verify_gpg_signature(
                        file_path,
                        signature_data,
                        public_key,
                    )

            except asyncio.TimeoutError:
                logger.warning(
                    "Timeout downloading signature from %s (attempt %d/%d)",
                    signature_url,
                    attempt + 1,
                    max_retries,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2**attempt))
                    continue
                return False

            except aiohttp.ClientError as exc:
                logger.warning(
                    "Network error downloading signature from %s: %s (attempt %d/%d)",
                    signature_url,
                    exc,
                    attempt + 1,
                    max_retries,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2**attempt))
                    continue
                return False

            except Exception as exc:
                logger.error(
                    "Unexpected error downloading signature from %s: %s",
                    signature_url,
                    exc,
                )
                return False

        return False
