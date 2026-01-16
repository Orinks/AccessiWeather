# GPG Signature Verification for Update Downloads

## Overview

AccessiWeather implements GPG (GNU Privacy Guard) signature verification for update downloads to ensure the integrity and authenticity of releases. This security enhancement runs automatically after SHA256 checksum validation, providing defense-in-depth protection against man-in-the-middle attacks and compromised download servers.

**Key Features:**

- Detached GPG signature verification using PGPy (pure Python implementation)
- Automatic signature detection and download from GitHub releases
- Retry logic with exponential backoff for network resilience
- Graceful fallback when signatures are unavailable
- Cross-platform support (Windows, macOS, Linux) without external dependencies

**Status:** ⚠️ CURRENTLY DISABLED - The PGPy dependency has been removed. See "Enabling Signature Verification" below to re-enable.

---

## Enabling Signature Verification

To enable GPG signature verification:

1. **Add PGPy dependency** to `pyproject.toml`:
   ```toml
   dependencies = [
       # ... other deps ...
       "PGPy~=0.5.4",
   ]
   ```
   Also add to `[tool.briefcase.app.accessiweather]` requires section.

2. **Generate a GPG key pair** (see Key Generation section below)

3. **Embed the public key** in `src/accessiweather/services/update_service/signature_verification.py`

4. **Uncomment the verification call** in `src/accessiweather/services/update_service/downloads.py`

5. **Add private key to CI** as GitHub secret `GPG_PRIVATE_KEY`

---

## How It Works

### Architecture

The signature verification system consists of three main components:

```
GitHub Release → ReleaseManager → DownloadManager → SignatureVerifier
                      ↓                   ↓                 ↓
                 Find .sig/.asc    Download artifact   Verify signature
                 asset URL         + signature file    with embedded key
```

### Workflow

1. **Release Detection** (`releases.py:find_signature_asset`)
   - Scans GitHub release assets for signature files (`.sig` or `.asc` extensions)
   - Matches signature file to platform-specific installer artifact
   - Populates `UpdateInfo.signature_url` field

2. **Download Flow** (`downloads.py:_download_asset`)
   - Downloads platform-specific installer (e.g., `AccessiWeather-0.4.3-windows.msi`)
   - Verifies SHA256 checksum against `checksums.txt`
   - **NEW:** Downloads signature file (e.g., `AccessiWeather-0.4.3-windows.msi.sig`)
   - Verifies GPG signature using embedded public key

3. **Signature Verification** (`signature_verification.py:SignatureVerifier`)
   - Loads embedded AccessiWeather release signing public key
   - Parses detached signature using PGPy library
   - Verifies signature against downloaded installer file
   - Deletes file and returns `False` if verification fails

### Code Example

```python
from accessiweather.services.update_service.signature_verification import SignatureVerifier

# Verify a downloaded file
success = await SignatureVerifier.download_and_verify_signature(
    file_path=Path("/tmp/AccessiWeather-0.4.3-windows.msi"),
    signature_url="https://github.com/.../AccessiWeather-0.4.3-windows.msi.sig"
)

if success:
    print("Signature verified - safe to install")
else:
    print("Signature verification failed - do not install")
```

### Integration Points

**UpdateInfo dataclass** (`github_update_service.py`):
```python
@dataclass
class UpdateInfo:
    version: str
    release_notes: str
    download_url: str
    checksums_url: str | None = None
    signature_url: str | None = None  # NEW: Signature file URL
    file_size: int | None = None
```

**DownloadManager** (`downloads.py`):
```python
async def _download_asset(
    self,
    url: str,
    dest_path: Path,
    checksums_url: str | None = None,
    signature_url: str | None = None,  # NEW: Optional signature verification
    progress_callback: Callable[[int, int], None] | None = None,
) -> bool:
    # ... download and verify checksums ...

    # NEW: Verify GPG signature if signature_url provided
    if signature_url:
        if not await SignatureVerifier.download_and_verify_signature(
            dest_path, signature_url
        ):
            return False

    return True
```

---

## Public Key Management

### Embedded Public Key

The AccessiWeather release signing public key is embedded as a string constant in `signature_verification.py`:

```python
ACCESSIWEATHER_PUBLIC_KEY = """-----BEGIN PGP PUBLIC KEY BLOCK-----

mQINBGExample1EAD...
(ASCII-armored public key)
...
-----END PGP PUBLIC KEY BLOCK-----"""
```

**Why Embed the Key?**

- Ensures the application always has the correct verification key
- No external key server dependencies (no network calls for key retrieval)
- Simplifies Briefcase packaging (no external keyring files)
- Prevents key substitution attacks

**Security Trade-offs:**

- ✅ **Pro:** Key is authenticated by the application binary itself
- ✅ **Pro:** Works offline, no keyserver availability issues
- ⚠️ **Con:** Key rotation requires application update (acceptable for desktop apps)
- ⚠️ **Con:** If application binary is compromised, key is also compromised (inherent risk)

### Key Generation (Release Process)

**Initial Setup:**

```bash
# Generate release signing key (one-time setup)
gpg --full-generate-key
# Choose: RSA and RSA, 4096 bits, no expiration
# Use identity: AccessiWeather Release Signing <releases@accessiweather.example>

# Export public key (add to signature_verification.py)
gpg --armor --export releases@accessiweather.example > public_key.asc

# Export private key (store securely, never commit!)
gpg --armor --export-secret-keys releases@accessiweather.example > private_key.asc
# Add private key to GitHub Actions secrets as GPG_PRIVATE_KEY
```

**Per-Release Signing:**

```bash
# Sign release artifact (in CI/CD pipeline)
gpg --detach-sign --armor --output AccessiWeather-0.4.3-windows.msi.asc \
    AccessiWeather-0.4.3-windows.msi

# Upload both files to GitHub release
# - AccessiWeather-0.4.3-windows.msi
# - AccessiWeather-0.4.3-windows.msi.asc (or .sig for binary signature)
```

### Key Rotation Procedure

**When to Rotate:**

- Scheduled rotation (every 2-3 years for best practice)
- Private key compromise suspected
- Team member with key access leaves project
- Upgrading to stronger cryptographic algorithms

**How to Rotate:**

1. **Generate new key pair:**
   ```bash
   gpg --full-generate-key
   # New identity: AccessiWeather Release Signing 2026 <releases@accessiweather.example>
   ```

2. **Update embedded public key:**
   - Export new public key: `gpg --armor --export releases@accessiweather.example`
   - Replace `ACCESSIWEATHER_PUBLIC_KEY` in `signature_verification.py`
   - Commit and release new version with updated key

3. **Sign future releases with new key:**
   - Update GitHub Actions secret `GPG_PRIVATE_KEY` with new private key
   - Sign all future releases with new key

4. **Transition period:**
   - Old application versions will not verify signatures from new key (expected)
   - Users must update to version with new embedded key to verify future releases
   - Consider overlap period: sign releases with both keys temporarily

**Backward Compatibility:**

- Old app versions cannot verify new signatures (they have old key)
- Solution: Release signing key rotation as part of a major version update
- Document in release notes: "This version includes updated signature verification key"

---

## Testing

### Test Structure

The signature verification feature has comprehensive test coverage across three testing paradigms:

**Test File:** `tests/test_signature_verification.py`

```
test_signature_verification.py
├── Unit Tests (17 tests)
│   ├── Valid signature verification
│   ├── Invalid signature detection
│   ├── Malformed signature handling
│   ├── Wrong public key rejection
│   ├── Missing file error handling
│   ├── HTTP error handling (404, 500)
│   ├── Timeout and retry logic
│   ├── Empty response handling
│   └── Exponential backoff verification
│
└── Property Tests (8 tests, requires Hypothesis)
    ├── Various file contents (0-100KB)
    ├── Various signature formats (1B-10KB)
    ├── Various public keys (10-5000 chars)
    ├── Retry configurations (0-5 retries, 0.001-2.0s delay)
    ├── URL format variations
    ├── HTTP error codes (400-599)
    ├── File sizes (0-10MB)
    └── Eventual success after N failures
```

**Integration Tests:** `tests/test_github_update_service.py` (8 tests)
- `find_signature_asset` method with `.sig` and `.asc` extensions
- `UpdateInfo.signature_url` population
- End-to-end download with signature verification
- Graceful skip when signature unavailable

### Running Tests

**Unit tests only:**
```bash
pytest tests/test_signature_verification.py -v
```

**Integration tests:**
```bash
pytest tests/test_github_update_service.py -v -k signature
```

**Property-based tests** (requires `pip install hypothesis`):
```bash
# Fast (10 examples per test)
pytest tests/test_signature_verification.py -v --hypothesis-profile=dev

# Thorough (100 examples per test)
pytest tests/test_signature_verification.py -v --hypothesis-profile=ci
```

**Full test suite:**
```bash
pytest -v
```

### Test Configuration

**Hypothesis profiles** (`tests/conftest.py`):
- `dev`: Fast feedback, 10 examples per test
- `default`: Balanced, 50 examples per test
- `ci`: Thorough CI validation, 100 examples per test
- `debug`: Verbose output for debugging failures

See `tests/PROPERTY_TESTS.md` for detailed property test documentation.

### Writing New Tests

**Pattern for signature verification tests:**

```python
@pytest.mark.asyncio
async def test_signature_verification_feature(tmp_path):
    """Test description."""
    # Setup: Create test file
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"test content")

    # Mock signature download
    with patch("aiohttp.ClientSession") as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"mock signature")

        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

        # Test
        result = await SignatureVerifier.download_and_verify_signature(
            test_file, "https://example.com/test.sig"
        )

        # Assert
        assert result is False  # Mock signature won't verify
```

---

## Troubleshooting

### Common Issues

#### Issue: "PGPy library not available - cannot verify signature"

**Symptom:** Application logs show signature verification failures with ImportError.

**Cause:** PGPy library not installed (dependency missing).

**Solution:**
1. Verify PGPy is in `pyproject.toml` dependencies:
   ```toml
   [project.dependencies]
   PGPy = "~=0.5.4"
   ```
2. Reinstall dependencies:
   ```bash
   pip install -e .
   ```
3. Verify import works:
   ```bash
   python -c "import pgpy; print('OK')"
   ```

---

#### Issue: "GPG signature verification failed"

**Symptom:** Valid signature files are rejected during download.

**Causes & Solutions:**

**1. Wrong public key embedded:**
- Verify `ACCESSIWEATHER_PUBLIC_KEY` matches the key used to sign releases
- Export actual signing key: `gpg --armor --export releases@accessiweather.example`
- Compare with embedded key in `signature_verification.py`

**2. Signature file format mismatch:**
- Check signature file extension: `.sig` (binary) or `.asc` (ASCII-armored)
- PGPy supports both formats, but file must be valid OpenPGP signature
- Test signature manually:
  ```bash
  gpg --verify AccessiWeather-0.4.3-windows.msi.asc AccessiWeather-0.4.3-windows.msi
  ```

**3. File modified after signing:**
- Ensure file is not modified between signing and verification
- Verify SHA256 checksum first (signature verification runs after checksum)
- Even a single byte change will fail signature verification

**4. PGPy version compatibility:**
- Check PGPy version: `pip show PGPy`
- Note: PGPy 0.5.4 is the latest available version on PyPI
- Solution: Pin to tested version in `pyproject.toml`: `PGPy = "~=0.5.4"`

---

#### Issue: "Failed to download signature from URL: HTTP 404"

**Symptom:** Signature file not found on GitHub release.

**Causes & Solutions:**

**1. Signature file not uploaded to release:**
- Check GitHub release assets include `.sig` or `.asc` files
- Signature file name must match artifact name + `.sig`/`.asc` extension
  - ✅ `AccessiWeather-0.4.3-windows.msi.sig`
  - ❌ `signature.sig` (wrong name)

**2. Signature file naming convention:**
- `ReleaseManager.find_signature_asset` looks for exact match:
  ```
  Artifact: AccessiWeather-0.4.3-windows.msi
  Signature: AccessiWeather-0.4.3-windows.msi.sig
  ```
- Check asset names match this pattern

**3. Signature URL construction issue:**
- Debug by logging `signature_url` in `check_for_updates`
- Verify URL points to actual GitHub asset download URL
- Format: `https://github.com/owner/repo/releases/download/v0.4.3/file.sig`

---

#### Issue: Signature verification times out

**Symptom:** Download times out with "Timeout downloading signature" warning.

**Cause:** Slow network, large signature file, or server issues.

**Solution:**
1. Increase timeout in `download_and_verify_signature`:
   ```python
   timeout=aiohttp.ClientTimeout(total=30)  # Default, can increase to 60
   ```
2. Check signature file size (should be <10KB for detached signatures)
3. Retry logic will attempt up to 3 times with exponential backoff

---

#### Issue: Tests fail with "hypothesis not installed"

**Symptom:** Property tests are skipped with warning.

**Cause:** Hypothesis library not installed (optional dependency).

**Solution:**
- Property tests are **optional** and gracefully skipped if Hypothesis unavailable
- To run property tests, install Hypothesis:
  ```bash
  pip install hypothesis
  # or
  pip install -e ".[dev]"
  ```
- Non-property tests will still run and pass

---

### Debugging Tips

**Enable verbose logging:**

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Test signature verification manually:**

```python
from pathlib import Path
from accessiweather.services.update_service.signature_verification import SignatureVerifier

# Test with actual files
file_path = Path("AccessiWeather-0.4.3-windows.msi")
signature_data = Path("AccessiWeather-0.4.3-windows.msi.sig").read_bytes()
public_key = SignatureVerifier.ACCESSIWEATHER_PUBLIC_KEY

result = SignatureVerifier._verify_gpg_signature(file_path, signature_data, public_key)
print(f"Verification result: {result}")
```

**Check PGPy directly:**

```python
import pgpy

# Load public key
pub_key, _ = pgpy.PGPKey.from_file("public_key.asc")
print(f"Key ID: {pub_key.fingerprint}")

# Load signature
signature = pgpy.PGPSignature.from_file("file.sig")
print(f"Signature type: {signature.type}")

# Verify
with open("file.bin", "rb") as f:
    verification = pub_key.verify(f.read(), signature)
    print(f"Valid: {bool(verification)}")
```

---

## Security Considerations

### Threat Model

**Protected Against:**
- ✅ Man-in-the-middle attacks (attacker intercepts and replaces download)
- ✅ Compromised CDN/mirror (attacker serves malicious file from mirror)
- ✅ Compromised `checksums.txt` file (attacker modifies checksums)
- ✅ Replay attacks (old vulnerable version resigned)

**Not Protected Against:**
- ❌ Compromised release signing key (attacker has private key)
- ❌ Compromised application binary (embedded public key also compromised)
- ❌ Build process compromise (malicious code in signed artifact)

### Best Practices

**Key Security:**
1. **Never commit private keys to repository**
   - Store in GitHub Actions secrets or secure key management system
   - Use hardware security key (YubiKey) for added protection
   - Limit access to release signing key

2. **Rotate keys periodically**
   - Scheduled rotation every 2-3 years
   - Immediate rotation if compromise suspected
   - Document rotation in release notes

3. **Verify builds before signing**
   - Review code changes in release
   - Test build artifacts before signing
   - Use reproducible builds when possible

**Error Handling:**
1. **Graceful degradation**
   - Signature verification failures are logged but don't crash the app
   - Falls back to checksum-only verification if signature unavailable
   - User-friendly error messages (no cryptographic details exposed)

2. **File cleanup on failure**
   - Downloaded file is deleted if signature verification fails
   - Prevents installation of unverified updates

3. **Logging best practices**
   - Log signature verification success/failure
   - Don't log private keys or sensitive cryptographic material
   - Include file paths and URLs for debugging

### Defense in Depth

Signature verification is **layer 3** of update integrity verification:

1. **Layer 1:** HTTPS download (protects transport)
2. **Layer 2:** SHA256 checksum verification (detects corruption/tampering)
3. **Layer 3:** GPG signature verification (proves authenticity)

All three layers work together to ensure secure updates.

---

## Future Enhancements

**Potential improvements for future versions:**

1. **Hardware Security Module (HSM) integration**
   - Use HSM for release signing key storage
   - Higher security for private key protection

2. **Multiple signing keys**
   - Support multiple embedded public keys for overlap during rotation
   - Verify against any valid key (OR logic)

3. **Key pinning with fallback**
   - Pin to specific key fingerprint
   - Allow fallback to secondary key during rotation

4. **Signature timestamp verification**
   - Verify signature creation timestamp
   - Reject signatures older than N days (prevent replay)

5. **User notification on verification failure**
   - Show user-facing dialog when signature verification fails
   - Provide actionable guidance (retry download, contact support)

6. **Signature caching**
   - Cache verified signatures to avoid re-verification
   - Speed up repeated installations (testing, rollback)

---

## References

### Internal Documentation
- [GPG Library Research](./.auto-claude/specs/003-enhance-update-download-integrity-verification/GPG_LIBRARY_RESEARCH.md) - Library selection rationale
- [Property Tests](../tests/PROPERTY_TESTS.md) - Property-based testing guide
- [Implementation Plan](./.auto-claude/specs/003-enhance-update-download-integrity-verification/implementation_plan.json) - Phase-by-phase implementation

### Code References
- `src/accessiweather/services/update_service/signature_verification.py` - Core verification logic
- `src/accessiweather/services/update_service/downloads.py` - Integration with download flow
- `src/accessiweather/services/update_service/releases.py` - Signature asset detection
- `tests/test_signature_verification.py` - Unit and property tests
- `tests/test_github_update_service.py` - Integration tests

### External Resources
- [PGPy Documentation](https://pgpy.readthedocs.io/) - Python PGP library
- [OpenPGP Specification (RFC 4880)](https://tools.ietf.org/html/rfc4880) - GPG standard
- [GnuPG Documentation](https://gnupg.org/documentation/) - GPG usage guide
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/) - Property-based testing

---

*Last Updated: 2026-01-12*
*Status: Feature implemented and tested (phase 6 of 7)*
*Maintainer: AccessiWeather Development Team*
