"""
Tests for SignatureVerifier.

Covers: GPG signature verification, signature download with retry logic,
valid/invalid signatures, malformed signatures, network error handling,
and edge cases like missing files and wrong public keys.
"""

import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Import hypothesis for property-based testing (optional)
try:
    from hypothesis import (
        HealthCheck,
        given,
        settings,
        strategies as st,
    )

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

    # Create dummy decorators and module for when hypothesis is not available
    def given(*args, **kwargs):
        return pytest.mark.skip(reason="hypothesis not installed")

    def settings(*args, **kwargs):
        return lambda f: f

    class HealthCheck:
        function_scoped_fixture = "dummy"

    # Create dummy strategies module
    class _DummyStrategies:
        @staticmethod
        def binary(*args, **kwargs):
            return None

        @staticmethod
        def text(*args, **kwargs):
            return None

        @staticmethod
        def integers(*args, **kwargs):
            return None

        @staticmethod
        def floats(*args, **kwargs):
            return None

        @staticmethod
        def lists(*args, **kwargs):
            return None

        @staticmethod
        def characters(*args, **kwargs):
            return None

    st = _DummyStrategies()

# Add src to path for proper imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Provide minimal stubs to avoid requiring external deps during collection
# aiohttp stub with ClientSession and exception types
_aiohttp_stub = types.ModuleType("aiohttp")


class _ClientSessionStub:
    def __init__(self, *args, **kwargs):
        pass

    async def get(self, *args, **kwargs):  # pragma: no cover - replaced by tests
        raise NotImplementedError

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _ClientTimeoutStub:
    def __init__(self, total=None):
        self.total = total


class _ClientErrorStub(Exception):
    pass


_aiohttp_stub.ClientSession = _ClientSessionStub
_aiohttp_stub.ClientTimeout = _ClientTimeoutStub
_aiohttp_stub.ClientError = _ClientErrorStub
sys.modules.setdefault("aiohttp", _aiohttp_stub)

# pgpy stub with minimal types for testing
_pgpy_stub = types.ModuleType("pgpy")


class _PGPKeyStub:
    def __init__(self, key_data: str = ""):
        self.key_data = key_data

    @staticmethod
    def from_blob(data: str):
        return _PGPKeyStub(data), None

    def verify(self, file_content: bytes, signature):
        # Default behavior - override in tests
        return True


class _PGPSignatureStub:
    def __init__(self, sig_data: bytes = b""):
        self.sig_data = sig_data

    @staticmethod
    def from_blob(data: bytes):
        return _PGPSignatureStub(data)


_pgpy_stub.PGPKey = _PGPKeyStub
_pgpy_stub.PGPSignature = _PGPSignatureStub
sys.modules.setdefault("pgpy", _pgpy_stub)

# Import the signature verification module
from accessiweather.services.update_service.signature_verification import (  # noqa: E402
    ACCESSIWEATHER_PUBLIC_KEY,
    SignatureVerifier,
)


# -----------------------------
# Test fixtures
# -----------------------------
@pytest.fixture
def temp_test_file(tmp_path: Path) -> Path:
    """Create a temporary test file with known content."""
    test_file = tmp_path / "test_artifact.exe"
    test_file.write_bytes(b"Test artifact content for signature verification")
    return test_file


@pytest.fixture
def test_signature_data() -> bytes:
    """Return test signature data."""
    return b"-----BEGIN PGP SIGNATURE-----\n\nTest signature data\n-----END PGP SIGNATURE-----"


@pytest.fixture
def test_public_key() -> str:
    """Return test public key."""
    return """-----BEGIN PGP PUBLIC KEY BLOCK-----

mQINBGTestKey...
-----END PGP PUBLIC KEY BLOCK-----"""


@pytest.fixture
def mock_aiohttp_response():
    """Create a mock aiohttp response."""

    class MockResponse:
        def __init__(self, status: int = 200, data: bytes = b""):
            self.status = status
            self._data = data

        async def read(self):
            return self._data

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    return MockResponse


# -----------------------------
# Test _verify_gpp_signature static method
# -----------------------------
def test_verify_gpg_signature_valid(
    temp_test_file: Path, test_signature_data: bytes, test_public_key: str
):
    """Test successful GPG signature verification."""
    # Mock pgpy module at the import level
    mock_pgpy = MagicMock()
    mock_key = Mock()
    mock_key.verify.return_value = True
    mock_pgpy.PGPKey.from_blob.return_value = (mock_key, None)
    mock_pgpy.PGPSignature.from_blob.return_value = Mock()

    with patch.dict("sys.modules", {"pgpy": mock_pgpy}):
        result = SignatureVerifier._verify_gpg_signature(
            temp_test_file,
            test_signature_data,
            test_public_key,
        )

        assert result is True
        assert temp_test_file.exists()  # File should not be deleted on success
        mock_key.verify.assert_called_once()


def test_verify_gpg_signature_invalid(
    temp_test_file: Path, test_signature_data: bytes, test_public_key: str
):
    """Test GPG signature verification failure with invalid signature."""
    # Mock pgpy module at the import level
    mock_pgpy = MagicMock()
    mock_key = Mock()
    mock_key.verify.return_value = False
    mock_pgpy.PGPKey.from_blob.return_value = (mock_key, None)
    mock_pgpy.PGPSignature.from_blob.return_value = Mock()

    with patch.dict("sys.modules", {"pgpy": mock_pgpy}):
        result = SignatureVerifier._verify_gpg_signature(
            temp_test_file,
            test_signature_data,
            test_public_key,
        )

        assert result is False
        assert not temp_test_file.exists()  # File should be deleted on failure


def test_verify_gpg_signature_malformed_signature(temp_test_file: Path, test_public_key: str):
    """Test GPG signature verification with malformed signature data."""
    # Mock pgpy module at the import level
    mock_pgpy = MagicMock()
    mock_pgpy.PGPKey.from_blob.return_value = (Mock(), None)
    mock_pgpy.PGPSignature.from_blob.side_effect = Exception("Invalid signature format")

    with patch.dict("sys.modules", {"pgpy": mock_pgpy}):
        result = SignatureVerifier._verify_gpg_signature(
            temp_test_file,
            b"malformed signature data",
            test_public_key,
        )

        assert result is False
        assert not temp_test_file.exists()  # File should be deleted on error


def test_verify_gpg_signature_wrong_public_key(temp_test_file: Path, test_signature_data: bytes):
    """Test GPG signature verification with wrong public key."""
    # Mock pgpy module at the import level
    mock_pgpy = MagicMock()
    mock_pgpy.PGPKey.from_blob.side_effect = Exception("Invalid public key format")

    with patch.dict("sys.modules", {"pgpy": mock_pgpy}):
        result = SignatureVerifier._verify_gpg_signature(
            temp_test_file,
            test_signature_data,
            "invalid key data",
        )

        assert result is False
        assert not temp_test_file.exists()  # File should be deleted on error


def test_verify_gpg_signature_pgpy_not_available(
    temp_test_file: Path, test_signature_data: bytes, test_public_key: str
):
    """Test GPG signature verification when PGPy library is not available."""

    def mock_import(name, *args, **kwargs):
        if name == "pgpy":
            raise ImportError("No module named 'pgpy'")
        return __import__(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        result = SignatureVerifier._verify_gpg_signature(
            temp_test_file,
            test_signature_data,
            test_public_key,
        )

        assert result is False
        assert temp_test_file.exists()  # File should not be deleted when library is missing


def test_verify_gpg_signature_file_read_error(
    test_signature_data: bytes, test_public_key: str, tmp_path: Path
):
    """Test GPG signature verification with file read error."""
    nonexistent_file = tmp_path / "nonexistent.exe"

    # Mock pgpy module at the import level
    mock_pgpy = MagicMock()
    mock_pgpy.PGPKey.from_blob.return_value = (Mock(), None)
    mock_pgpy.PGPSignature.from_blob.return_value = Mock()

    with patch.dict("sys.modules", {"pgpy": mock_pgpy}):
        result = SignatureVerifier._verify_gpg_signature(
            nonexistent_file,
            test_signature_data,
            test_public_key,
        )

        assert result is False


# -----------------------------
# Test download_and_verify_signature async method
# -----------------------------
@pytest.mark.asyncio
async def test_download_and_verify_signature_success(
    temp_test_file: Path, test_signature_data: bytes, test_public_key: str, mock_aiohttp_response
):
    """Test successful signature download and verification."""
    mock_response = mock_aiohttp_response(status=200, data=test_signature_data)

    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        mock_session.get.return_value = mock_get_ctx
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        with patch.object(
            SignatureVerifier, "_verify_gpg_signature", return_value=True
        ) as mock_verify:
            result = await SignatureVerifier.download_and_verify_signature(
                temp_test_file,
                "https://example.com/artifact.sig",
                public_key=test_public_key,
            )

            assert result is True
            mock_verify.assert_called_once_with(
                temp_test_file, test_signature_data, test_public_key
            )


@pytest.mark.asyncio
async def test_download_and_verify_signature_file_not_found(tmp_path: Path, test_public_key: str):
    """Test signature verification when artifact file doesn't exist."""
    nonexistent_file = tmp_path / "missing.exe"

    result = await SignatureVerifier.download_and_verify_signature(
        nonexistent_file,
        "https://example.com/artifact.sig",
        public_key=test_public_key,
    )

    assert result is False


@pytest.mark.asyncio
async def test_download_and_verify_signature_http_404(
    temp_test_file: Path, test_public_key: str, mock_aiohttp_response
):
    """Test signature download with HTTP 404 response."""
    mock_response = mock_aiohttp_response(status=404, data=b"")

    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        mock_session.get.return_value = mock_get_ctx
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        result = await SignatureVerifier.download_and_verify_signature(
            temp_test_file,
            "https://example.com/nonexistent.sig",
            public_key=test_public_key,
            max_retries=1,
        )

        assert result is False


@pytest.mark.asyncio
async def test_download_and_verify_signature_empty_response(
    temp_test_file: Path, test_public_key: str, mock_aiohttp_response
):
    """Test signature download with empty signature file."""
    mock_response = mock_aiohttp_response(status=200, data=b"")

    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        mock_session.get.return_value = mock_get_ctx
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        result = await SignatureVerifier.download_and_verify_signature(
            temp_test_file,
            "https://example.com/empty.sig",
            public_key=test_public_key,
        )

        assert result is False


@pytest.mark.asyncio
async def test_download_and_verify_signature_timeout_with_retry(
    temp_test_file: Path, test_signature_data: bytes, test_public_key: str, mock_aiohttp_response
):
    """Test signature download with timeout and successful retry."""
    mock_success_response = mock_aiohttp_response(status=200, data=test_signature_data)

    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()

        # First call times out, second succeeds
        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError("Request timeout")
            # Return async context manager
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_success_response
            mock_ctx.__aexit__.return_value = None
            return mock_ctx

        mock_session.get.side_effect = mock_get
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        with patch.object(SignatureVerifier, "_verify_gpg_signature", return_value=True):
            result = await SignatureVerifier.download_and_verify_signature(
                temp_test_file,
                "https://example.com/artifact.sig",
                public_key=test_public_key,
                max_retries=2,
                retry_delay=0.01,  # Short delay for testing
            )

            assert result is True
            assert call_count == 2  # First timeout, then success


@pytest.mark.asyncio
async def test_download_and_verify_signature_max_retries_exceeded(
    temp_test_file: Path, test_public_key: str
):
    """Test signature download when max retries are exceeded."""
    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()
        mock_session.get.side_effect = asyncio.TimeoutError("Request timeout")
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        result = await SignatureVerifier.download_and_verify_signature(
            temp_test_file,
            "https://example.com/artifact.sig",
            public_key=test_public_key,
            max_retries=2,
            retry_delay=0.01,  # Short delay for testing
        )

        assert result is False
        assert mock_session.get.call_count == 2  # Max retries


@pytest.mark.asyncio
async def test_download_and_verify_signature_client_error(
    temp_test_file: Path, test_public_key: str
):
    """Test signature download with network client error."""
    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()

        # Import the actual exception type from the stub
        from aiohttp import ClientError

        mock_session.get.side_effect = ClientError("Network error")
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        result = await SignatureVerifier.download_and_verify_signature(
            temp_test_file,
            "https://example.com/artifact.sig",
            public_key=test_public_key,
            max_retries=1,
        )

        assert result is False


@pytest.mark.asyncio
async def test_download_and_verify_signature_unexpected_exception(
    temp_test_file: Path, test_public_key: str
):
    """Test signature download with unexpected exception."""
    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Unexpected error")
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        result = await SignatureVerifier.download_and_verify_signature(
            temp_test_file,
            "https://example.com/artifact.sig",
            public_key=test_public_key,
        )

        assert result is False


@pytest.mark.asyncio
async def test_download_and_verify_signature_verification_fails(
    temp_test_file: Path, test_signature_data: bytes, test_public_key: str, mock_aiohttp_response
):
    """Test successful download but verification failure."""
    mock_response = mock_aiohttp_response(status=200, data=test_signature_data)

    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        mock_session.get.return_value = mock_get_ctx
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        with patch.object(
            SignatureVerifier, "_verify_gpg_signature", return_value=False
        ) as mock_verify:
            result = await SignatureVerifier.download_and_verify_signature(
                temp_test_file,
                "https://example.com/artifact.sig",
                public_key=test_public_key,
            )

            assert result is False
            mock_verify.assert_called_once()


@pytest.mark.asyncio
async def test_download_and_verify_signature_default_public_key(
    temp_test_file: Path, test_signature_data: bytes, mock_aiohttp_response
):
    """Test signature verification uses default public key when not specified."""
    mock_response = mock_aiohttp_response(status=200, data=test_signature_data)

    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        mock_session.get.return_value = mock_get_ctx
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        with patch.object(
            SignatureVerifier, "_verify_gpg_signature", return_value=True
        ) as mock_verify:
            result = await SignatureVerifier.download_and_verify_signature(
                temp_test_file,
                "https://example.com/artifact.sig",
                # Not specifying public_key, should use default
            )

            assert result is True
            # Verify that the default ACCESSIWEATHER_PUBLIC_KEY was used
            call_args = mock_verify.call_args
            assert call_args[0][2] == ACCESSIWEATHER_PUBLIC_KEY


@pytest.mark.asyncio
async def test_download_and_verify_signature_exponential_backoff(
    temp_test_file: Path, test_signature_data: bytes, test_public_key: str, mock_aiohttp_response
):
    """Test that retry delay follows exponential backoff pattern."""
    mock_success_response = mock_aiohttp_response(status=200, data=test_signature_data)

    with (
        patch(
            "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
        ) as mock_session_class,
        patch(
            "accessiweather.services.update_service.signature_verification.asyncio.sleep"
        ) as mock_sleep,
    ):
        mock_session = MagicMock()

        # Fail twice, then succeed
        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise asyncio.TimeoutError("Request timeout")
            # Return async context manager
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_success_response
            mock_ctx.__aexit__.return_value = None
            return mock_ctx

        mock_session.get.side_effect = mock_get
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        with patch.object(SignatureVerifier, "_verify_gpg_signature", return_value=True):
            result = await SignatureVerifier.download_and_verify_signature(
                temp_test_file,
                "https://example.com/artifact.sig",
                public_key=test_public_key,
                max_retries=3,
                retry_delay=1.0,
            )

            assert result is True
            # Check exponential backoff: delay * 2^0, delay * 2^1
            assert mock_sleep.call_count == 2
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert sleep_calls[0] == 1.0  # 1.0 * 2^0
            assert sleep_calls[1] == 2.0  # 1.0 * 2^1


# -----------------------------
# Property-based tests with Hypothesis
# -----------------------------
@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
@pytest.mark.property
@given(
    file_content=st.binary(min_size=0, max_size=1024 * 100),  # Up to 100KB for tests
)
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_verify_gpg_signature_various_file_contents(
    file_content: bytes, tmp_path: Path, test_signature_data: bytes, test_public_key: str
):
    """Property test: verify GPG signature handles various file contents correctly."""
    test_file = tmp_path / f"test_artifact_{hash(file_content)}.bin"
    test_file.write_bytes(file_content)

    # Mock pgpy module at the import level
    mock_pgpy = MagicMock()
    mock_key = Mock()
    mock_key.verify.return_value = True
    mock_pgpy.PGPKey.from_blob.return_value = (mock_key, None)
    mock_pgpy.PGPSignature.from_blob.return_value = Mock()

    with patch.dict("sys.modules", {"pgpy": mock_pgpy}):
        result = SignatureVerifier._verify_gpg_signature(
            test_file,
            test_signature_data,
            test_public_key,
        )

        # Valid signature should pass for any file content
        assert result is True
        assert test_file.exists()  # File should remain after successful verification
        mock_key.verify.assert_called_once()


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
@pytest.mark.property
@given(
    signature_data=st.binary(min_size=1, max_size=10240),  # 1 byte to 10KB
)
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_verify_gpg_signature_various_signature_formats(
    signature_data: bytes, tmp_path: Path, test_public_key: str
):
    """Property test: verify GPG signature handles various signature data formats."""
    test_file = tmp_path / "test_artifact.exe"
    test_file.write_bytes(b"Test content")

    # Mock pgpy module to handle arbitrary signature data
    mock_pgpy = MagicMock()
    mock_key = Mock()
    mock_key.verify.return_value = True
    mock_pgpy.PGPKey.from_blob.return_value = (mock_key, None)

    # Simulate that some signature formats are invalid
    if b"-----BEGIN PGP SIGNATURE-----" in signature_data:
        mock_pgpy.PGPSignature.from_blob.return_value = Mock()
        expected_result = True
    else:
        # Invalid format
        mock_pgpy.PGPSignature.from_blob.side_effect = Exception("Invalid signature format")
        expected_result = False

    with patch.dict("sys.modules", {"pgpy": mock_pgpy}):
        result = SignatureVerifier._verify_gpg_signature(
            test_file,
            signature_data,
            test_public_key,
        )

        if expected_result:
            assert result is True
            assert test_file.exists()
        else:
            # Should handle malformed signatures gracefully
            assert result is False
            assert not test_file.exists()  # File deleted on failure


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
@pytest.mark.property
@given(
    public_key=st.text(min_size=10, max_size=5000),
)
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_verify_gpg_signature_various_public_keys(
    public_key: str, tmp_path: Path, test_signature_data: bytes
):
    """Property test: verify GPG signature handles various public key formats."""
    test_file = tmp_path / "test_artifact.exe"
    test_file.write_bytes(b"Test content")

    # Mock pgpy module
    mock_pgpy = MagicMock()

    # Simulate valid PGP key format check
    if "-----BEGIN PGP PUBLIC KEY BLOCK-----" in public_key:
        mock_key = Mock()
        mock_key.verify.return_value = True
        mock_pgpy.PGPKey.from_blob.return_value = (mock_key, None)
        mock_pgpy.PGPSignature.from_blob.return_value = Mock()
        expected_result = True
    else:
        # Invalid key format
        mock_pgpy.PGPKey.from_blob.side_effect = Exception("Invalid public key format")
        expected_result = False

    with patch.dict("sys.modules", {"pgpy": mock_pgpy}):
        result = SignatureVerifier._verify_gpg_signature(
            test_file,
            test_signature_data,
            public_key,
        )

        if expected_result:
            assert result is True
            assert test_file.exists()
        else:
            # Should handle invalid keys gracefully
            assert result is False
            assert not test_file.exists()  # File deleted on failure


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
@pytest.mark.property
@pytest.mark.asyncio
@given(
    max_retries=st.integers(min_value=0, max_value=5),
    retry_delay=st.floats(min_value=0.001, max_value=2.0, allow_nan=False, allow_infinity=False),
)
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_property_download_retry_configuration(
    max_retries: int, retry_delay: float, tmp_path: Path, test_public_key: str
):
    """Property test: verify retry logic works with various configurations."""
    test_file = tmp_path / "test_artifact.exe"
    test_file.write_bytes(b"Test content")

    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()
        # Always fail to test retry behavior
        mock_session.get.side_effect = asyncio.TimeoutError("Request timeout")
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        result = await SignatureVerifier.download_and_verify_signature(
            test_file,
            "https://example.com/artifact.sig",
            public_key=test_public_key,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

        # Should always fail (timeout) but not crash
        assert result is False
        # Should have attempted max_retries times
        assert mock_session.get.call_count == max(1, max_retries)


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
@pytest.mark.property
@pytest.mark.asyncio
@given(
    url_path=st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_./"
        ),
        min_size=1,
        max_size=200,
    ),
)
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_property_download_various_urls(
    url_path: str,
    tmp_path: Path,
    test_signature_data: bytes,
    test_public_key: str,
    mock_aiohttp_response,
):
    """Property test: verify signature download handles various URL formats."""
    test_file = tmp_path / "test_artifact.exe"
    test_file.write_bytes(b"Test content")

    # Construct a valid URL with the generated path
    url = f"https://example.com/{url_path.lstrip('/')}"

    mock_response = mock_aiohttp_response(status=200, data=test_signature_data)

    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        mock_session.get.return_value = mock_get_ctx
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        with patch.object(SignatureVerifier, "_verify_gpg_signature", return_value=True):
            result = await SignatureVerifier.download_and_verify_signature(
                test_file,
                url,
                public_key=test_public_key,
                max_retries=1,
            )

            # Should handle any valid URL format
            assert result is True
            mock_session.get.assert_called_once()


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
@pytest.mark.property
@given(
    status_codes=st.lists(
        st.integers(min_value=400, max_value=599),
        min_size=1,
        max_size=3,
    ),
)
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@pytest.mark.asyncio
async def test_property_download_various_error_status_codes(
    status_codes: list, tmp_path: Path, test_public_key: str, mock_aiohttp_response
):
    """Property test: verify signature download handles various HTTP error status codes."""
    test_file = tmp_path / "test_artifact.exe"
    test_file.write_bytes(b"Test content")

    # Use the first status code for testing
    status_code = status_codes[0]
    mock_response = mock_aiohttp_response(status=status_code, data=b"")

    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        mock_session.get.return_value = mock_get_ctx
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        result = await SignatureVerifier.download_and_verify_signature(
            test_file,
            "https://example.com/artifact.sig",
            public_key=test_public_key,
            max_retries=1,
        )

        # Should handle all error status codes gracefully
        assert result is False


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
@pytest.mark.property
@given(
    file_size=st.integers(min_value=0, max_value=1024 * 1024 * 10),  # 0 to 10MB
)
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_verify_gpg_signature_various_file_sizes(
    file_size: int, tmp_path: Path, test_signature_data: bytes, test_public_key: str
):
    """Property test: verify GPG signature handles files of various sizes."""
    test_file = tmp_path / "test_artifact_large.bin"

    # Create file with specified size (filled with pattern to save memory)
    chunk_size = 8192
    with test_file.open("wb") as f:
        remaining = file_size
        pattern = b"A" * min(chunk_size, remaining)
        while remaining > 0:
            write_size = min(chunk_size, remaining)
            f.write(pattern[:write_size])
            remaining -= write_size

    assert test_file.stat().st_size == file_size

    # Mock pgpy module
    mock_pgpy = MagicMock()
    mock_key = Mock()
    mock_key.verify.return_value = True
    mock_pgpy.PGPKey.from_blob.return_value = (mock_key, None)
    mock_pgpy.PGPSignature.from_blob.return_value = Mock()

    with patch.dict("sys.modules", {"pgpy": mock_pgpy}):
        result = SignatureVerifier._verify_gpg_signature(
            test_file,
            test_signature_data,
            test_public_key,
        )

        # Should handle files of any size
        assert result is True
        assert test_file.exists()
        mock_key.verify.assert_called_once()


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
@pytest.mark.property
@given(
    num_failures=st.integers(min_value=0, max_value=3),
)
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@pytest.mark.asyncio
async def test_property_download_retry_with_eventual_success(
    num_failures: int,
    tmp_path: Path,
    test_signature_data: bytes,
    test_public_key: str,
    mock_aiohttp_response,
):
    """Property test: verify retry logic eventually succeeds after N failures."""
    test_file = tmp_path / "test_artifact.exe"
    test_file.write_bytes(b"Test content")

    mock_success_response = mock_aiohttp_response(status=200, data=test_signature_data)

    with patch(
        "accessiweather.services.update_service.signature_verification.aiohttp.ClientSession"
    ) as mock_session_class:
        mock_session = MagicMock()

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= num_failures:
                raise asyncio.TimeoutError("Request timeout")
            # Return async context manager
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_success_response
            mock_ctx.__aexit__.return_value = None
            return mock_ctx

        mock_session.get.side_effect = mock_get
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session_class.return_value = mock_session

        with patch.object(SignatureVerifier, "_verify_gpg_signature", return_value=True):
            result = await SignatureVerifier.download_and_verify_signature(
                test_file,
                "https://example.com/artifact.sig",
                public_key=test_public_key,
                max_retries=num_failures + 1,  # Ensure we have enough retries
                retry_delay=0.01,
            )

            # Should succeed after num_failures attempts
            assert result is True
            assert call_count == num_failures + 1
