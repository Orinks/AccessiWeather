"""Tests for SignatureVerifier."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from accessiweather.services.update_service.signature_verification import (
    SignatureVerifier,
)


@pytest.fixture
def tmp_file(tmp_path):
    """Create a temporary file for verification tests."""
    f = tmp_path / "update.zip"
    f.write_bytes(b"fake update content")
    return f


class TestVerifyGpgSignature:
    def test_pgpy_not_installed(self, tmp_file):
        with patch.dict("sys.modules", {"pgpy": None}):
            # Force ImportError by making import fail
            import builtins

            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "pgpy":
                    raise ImportError("No module named 'pgpy'")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = SignatureVerifier._verify_gpg_signature(tmp_file, b"sig", "pubkey")
                assert result is False

    def test_verification_success(self, tmp_file):
        mock_pgpy = MagicMock()
        mock_key = MagicMock()
        mock_pgpy.PGPKey.from_blob.return_value = (mock_key, None)
        mock_sig = MagicMock()
        mock_pgpy.PGPSignature.from_blob.return_value = mock_sig
        # Make verify return truthy
        mock_key.verify.return_value = True

        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pgpy":
                return mock_pgpy
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = SignatureVerifier._verify_gpg_signature(tmp_file, b"sig", "pubkey")
            assert result is True

    def test_verification_failure_deletes_file(self, tmp_file):
        mock_pgpy = MagicMock()
        mock_key = MagicMock()
        mock_pgpy.PGPKey.from_blob.return_value = (mock_key, None)
        mock_sig = MagicMock()
        mock_pgpy.PGPSignature.from_blob.return_value = mock_sig
        mock_key.verify.return_value = False  # falsy = failed

        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pgpy":
                return mock_pgpy
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = SignatureVerifier._verify_gpg_signature(tmp_file, b"sig", "pubkey")
            assert result is False
            assert not tmp_file.exists()

    def test_verification_exception_deletes_file(self, tmp_file):
        mock_pgpy = MagicMock()
        mock_pgpy.PGPKey.from_blob.side_effect = Exception("corrupt key")

        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pgpy":
                return mock_pgpy
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = SignatureVerifier._verify_gpg_signature(tmp_file, b"sig", "pubkey")
            assert result is False
            assert not tmp_file.exists()


class TestDownloadAndVerifySignature:
    def test_file_not_exists(self, tmp_path):
        missing = tmp_path / "missing.zip"
        result = asyncio.get_event_loop().run_until_complete(
            SignatureVerifier.download_and_verify_signature(missing, "https://example.com/sig")
        )
        assert result is False

    def test_successful_download_and_verify(self, tmp_file):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"signature data"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch.object(
                SignatureVerifier, "_verify_gpg_signature", return_value=True
            ) as mock_verify,
        ):
            result = asyncio.get_event_loop().run_until_complete(
                SignatureVerifier.download_and_verify_signature(
                    tmp_file, "https://example.com/sig", max_retries=1
                )
            )
            assert result is True
            mock_verify.assert_called_once()

    def test_http_error_retries(self, tmp_file):
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = asyncio.get_event_loop().run_until_complete(
                SignatureVerifier.download_and_verify_signature(
                    tmp_file, "https://example.com/sig", max_retries=2, retry_delay=0.0
                )
            )
            assert result is False

    def test_empty_signature(self, tmp_file):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b""

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.get_event_loop().run_until_complete(
                SignatureVerifier.download_and_verify_signature(
                    tmp_file, "https://example.com/sig", max_retries=1
                )
            )
            assert result is False

    def test_timeout_retries(self, tmp_file):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = asyncio.get_event_loop().run_until_complete(
                SignatureVerifier.download_and_verify_signature(
                    tmp_file, "https://example.com/sig", max_retries=2, retry_delay=0.0
                )
            )
            assert result is False

    def test_network_error_retries(self, tmp_file):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = asyncio.get_event_loop().run_until_complete(
                SignatureVerifier.download_and_verify_signature(
                    tmp_file, "https://example.com/sig", max_retries=2, retry_delay=0.0
                )
            )
            assert result is False

    def test_unexpected_error(self, tmp_file):
        mock_client = AsyncMock()
        mock_client.get.side_effect = RuntimeError("unexpected")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.get_event_loop().run_until_complete(
                SignatureVerifier.download_and_verify_signature(
                    tmp_file, "https://example.com/sig", max_retries=1
                )
            )
            assert result is False
