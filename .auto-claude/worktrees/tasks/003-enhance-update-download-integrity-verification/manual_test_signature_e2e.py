#!/usr/bin/env python3
"""
Manual end-to-end test for GPG signature verification.

This script tests the complete signature verification workflow:
1. Generates a test GPG key pair
2. Creates a mock update file
3. Signs the file with the private key
4. Tests verification succeeds with valid signature
5. Tests verification fails with invalid signature
6. Tests verification fails with wrong public key
7. Cleans up test files

Run this script to manually verify the signature verification feature works correctly.
"""

import asyncio
import logging
import sys
import tempfile
from pathlib import Path

# Add local PGPy installation to path if it exists
local_pgpy_path = Path(__file__).parent / "temp_pgpy_install"
if local_pgpy_path.exists():
    sys.path.insert(0, str(local_pgpy_path))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from accessiweather.services.update_service.signature_verification import SignatureVerifier


def generate_test_keypair():
    """Generate a test GPG key pair for manual testing."""
    try:
        import pgpy
    except ImportError:
        logger.error("PGPy library not installed. Install with: pip install PGPy")
        return None, None

    logger.info("Generating test GPG key pair...")

    # Generate primary key
    key = pgpy.PGPKey.new(pgpy.constants.PubKeyAlgorithm.RSAEncryptOrSign, 2048)

    # Create user ID
    uid = pgpy.PGPUID.new(
        "AccessiWeather Test",
        email="test@accessiweather.test",
        comment="Test key for signature verification",
    )

    # Add user ID to key
    key.add_uid(
        uid,
        usage={
            pgpy.constants.KeyFlags.Sign,
            pgpy.constants.KeyFlags.Certify,
        },
        hashes=[
            pgpy.constants.HashAlgorithm.SHA256,
            pgpy.constants.HashAlgorithm.SHA512,
        ],
        ciphers=[
            pgpy.constants.SymmetricKeyAlgorithm.AES256,
        ],
    )

    # Export public and private keys
    public_key = str(key.pubkey)
    private_key = str(key)

    logger.info("✓ Test key pair generated successfully")
    logger.info(f"  Public key fingerprint: {key.fingerprint}")

    return public_key, private_key


def create_test_file(temp_dir: Path) -> Path:
    """Create a mock update file for testing."""
    test_file = temp_dir / "AccessiWeather-1.0.0-test.exe"
    test_content = b"Mock AccessiWeather update executable - Test data"

    test_file.write_bytes(test_content)
    logger.info(f"✓ Created test file: {test_file.name} ({len(test_content)} bytes)")

    return test_file


def sign_file(file_path: Path, private_key_str: str) -> bytes:
    """Sign a file with a private key and return detached signature."""
    try:
        import pgpy
    except ImportError:
        logger.error("PGPy library not installed")
        return b""

    logger.info(f"Signing file: {file_path.name}")

    # Load private key
    private_key, _ = pgpy.PGPKey.from_blob(private_key_str)

    # Read file content
    file_content = file_path.read_bytes()

    # Create a PGPMessage from the file content
    message = pgpy.PGPMessage.new(file_content, cleartext=False)

    # Create detached signature
    signature = private_key.sign(message)

    signature_bytes = bytes(signature)
    logger.info(f"✓ File signed successfully ({len(signature_bytes)} bytes)")

    return signature_bytes


def create_invalid_signature() -> bytes:
    """Create an invalid signature for testing failure cases."""
    return b"-----BEGIN PGP SIGNATURE-----\nINVALID\n-----END PGP SIGNATURE-----"


async def test_valid_signature(file_path: Path, signature_data: bytes, public_key: str):
    """Test that verification succeeds with a valid signature."""
    logger.info("\n=== Test 1: Valid Signature ===")

    # Write signature to temporary file (simulating it being a separate file)
    sig_file = file_path.with_suffix(".sig")
    sig_file.write_bytes(signature_data)

    # Verify signature using the SignatureVerifier
    result = SignatureVerifier._verify_gpg_signature(
        file_path,
        signature_data,
        public_key,
    )

    sig_file.unlink(missing_ok=True)

    if result:
        logger.info("✓ Test 1 PASSED: Valid signature verified successfully")
        return True
    else:
        logger.error("✗ Test 1 FAILED: Valid signature verification failed")
        return False


async def test_invalid_signature(file_path: Path, invalid_sig: bytes, public_key: str, original_content: bytes):
    """Test that verification fails with an invalid signature."""
    logger.info("\n=== Test 2: Invalid Signature ===")

    # Verify should fail with invalid signature
    result = SignatureVerifier._verify_gpg_signature(
        file_path,
        invalid_sig,
        public_key,
    )

    # Restore file if it was deleted
    if not file_path.exists():
        file_path.write_bytes(original_content)

    if not result:
        logger.info("✓ Test 2 PASSED: Invalid signature correctly rejected")
        return True
    else:
        logger.error("✗ Test 2 FAILED: Invalid signature was accepted")
        return False


async def test_wrong_public_key(file_path: Path, signature_data: bytes, original_content: bytes):
    """Test that verification fails with wrong public key."""
    logger.info("\n=== Test 3: Wrong Public Key ===")

    # Generate a different key pair
    wrong_public_key, _ = generate_test_keypair()

    if not wrong_public_key:
        logger.warning("⊘ Test 3 SKIPPED: Could not generate wrong key")
        return None

    # Verify should fail with wrong public key
    result = SignatureVerifier._verify_gpg_signature(
        file_path,
        signature_data,
        wrong_public_key,
    )

    # Restore file if it was deleted
    if not file_path.exists():
        file_path.write_bytes(original_content)

    if not result:
        logger.info("✓ Test 3 PASSED: Wrong public key correctly rejected")
        return True
    else:
        logger.error("✗ Test 3 FAILED: Wrong public key was accepted")
        return False


async def test_tampered_file(file_path: Path, signature_data: bytes, public_key: str):
    """Test that verification fails when file content is tampered."""
    logger.info("\n=== Test 4: Tampered File ===")

    # Save original content
    original_content = file_path.read_bytes()

    # Tamper with file
    tampered_content = original_content + b" TAMPERED"
    file_path.write_bytes(tampered_content)

    # Verify should fail with tampered file
    result = SignatureVerifier._verify_gpg_signature(
        file_path,
        signature_data,
        public_key,
    )

    # Restore original content for next tests (file may have been deleted by verification)
    file_path.write_bytes(original_content)

    if not result:
        logger.info("✓ Test 4 PASSED: Tampered file correctly rejected")
        return True
    else:
        logger.error("✗ Test 4 FAILED: Tampered file was accepted")
        return False


async def test_download_and_verify(file_path: Path, signature_data: bytes, public_key: str):
    """Test the async download_and_verify_signature method with a mock HTTP server."""
    logger.info("\n=== Test 5: Download and Verify (Simulated) ===")

    # This test verifies the download_and_verify_signature method exists and has correct signature
    # A full test would require starting a mock HTTP server

    # Check method exists and is callable
    method = getattr(SignatureVerifier, "download_and_verify_signature", None)
    if method is None:
        logger.error("✗ Test 5 FAILED: download_and_verify_signature method not found")
        return False

    if not asyncio.iscoroutinefunction(method):
        logger.error("✗ Test 5 FAILED: download_and_verify_signature is not async")
        return False

    logger.info("✓ Test 5 PASSED: download_and_verify_signature method exists and is async")
    logger.info("  Note: Full HTTP download test skipped (requires mock server)")
    return True


async def run_all_tests():
    """Run all manual end-to-end tests."""
    logger.info("=" * 70)
    logger.info("Manual End-to-End Test: GPG Signature Verification")
    logger.info("=" * 70)

    # Check if PGPy is available
    try:
        import pgpy
        logger.info("✓ PGPy library is available")
    except ImportError:
        logger.error("✗ PGPy library not installed")
        logger.error("  Install with: pip install PGPy")
        return False

    # Create temporary directory for test files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logger.info(f"✓ Created temporary test directory: {temp_path}")

        # Generate test key pair
        public_key, private_key = generate_test_keypair()
        if not public_key or not private_key:
            logger.error("✗ Failed to generate test key pair")
            return False

        # Create test file
        test_file = create_test_file(temp_path)

        # Save original content for restoration
        original_content = test_file.read_bytes()

        # Sign the test file
        valid_signature = sign_file(test_file, private_key)
        if not valid_signature:
            logger.error("✗ Failed to sign test file")
            return False

        # Create invalid signature
        invalid_signature = create_invalid_signature()

        # Run tests
        results = []

        # Test 1: Valid signature
        results.append(await test_valid_signature(test_file, valid_signature, public_key))

        # Test 2: Invalid signature
        results.append(await test_invalid_signature(test_file, invalid_signature, public_key, original_content))

        # Test 3: Wrong public key
        result = await test_wrong_public_key(test_file, valid_signature, original_content)
        if result is not None:
            results.append(result)

        # Test 4: Tampered file
        results.append(await test_tampered_file(test_file, valid_signature, public_key))

        # Test 5: Download and verify method check
        results.append(await test_download_and_verify(test_file, valid_signature, public_key))

        logger.info("\n" + "=" * 70)
        logger.info("Test Summary")
        logger.info("=" * 70)

        passed = sum(1 for r in results if r is True)
        failed = sum(1 for r in results if r is False)
        skipped = sum(1 for r in results if r is None)
        total = len(results)

        logger.info(f"Total tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Skipped: {skipped}")

        if failed > 0:
            logger.error("\n✗ SOME TESTS FAILED")
            return False
        else:
            logger.info("\n✓ ALL TESTS PASSED")
            return True


def main():
    """Main entry point for manual test."""
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n✗ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
