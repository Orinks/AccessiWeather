"""Regression tests: SSL/TLS certificate verification cannot be disabled."""

import ssl

import pytest

from accessiweather.weather_gov_api_client.client import AuthenticatedClient, Client


class TestSSLVerificationEnforced:
    """Ensure verify_ssl=False is rejected at construction time."""

    def test_client_rejects_verify_ssl_false(self):
        """Should reject Client(verify_ssl=False) to prevent MITM attacks."""
        with pytest.raises(ValueError, match="SSL verification cannot be disabled"):
            Client(base_url="https://example.com", verify_ssl=False)

    def test_authenticated_client_rejects_verify_ssl_false(self):
        """Should reject AuthenticatedClient(verify_ssl=False) to prevent MITM attacks."""
        with pytest.raises(ValueError, match="SSL verification cannot be disabled"):
            AuthenticatedClient(
                base_url="https://example.com",
                token="test-token",
                verify_ssl=False,
            )

    def test_client_allows_verify_ssl_true(self):
        """Should allow verify_ssl=True (default)."""
        client = Client(base_url="https://example.com", verify_ssl=True)
        assert client._verify_ssl is True

    def test_client_default_verify_ssl_is_true(self):
        """Default verify_ssl should be True."""
        client = Client(base_url="https://example.com")
        assert client._verify_ssl is True

    def test_client_allows_custom_ca_bundle_path(self):
        """Should allow a custom CA bundle path string."""
        client = Client(base_url="https://example.com", verify_ssl="/path/to/ca-bundle.crt")
        assert client._verify_ssl == "/path/to/ca-bundle.crt"

    def test_client_allows_ssl_context(self):
        """Should allow an ssl.SSLContext for custom verification."""
        ctx = ssl.create_default_context()
        client = Client(base_url="https://example.com", verify_ssl=ctx)
        assert client._verify_ssl is ctx
