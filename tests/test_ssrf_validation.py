"""Regression tests for SSRF prevention via URL validation."""

import pytest

from accessiweather.utils.url_validation import SSRFError, validate_backend_url


class TestSSRFValidation:
    """Verify that SSRF payloads are rejected by validate_backend_url."""

    def test_should_accept_valid_https_url(self):
        assert (
            validate_backend_url("https://soundpack-backend.fly.dev")
            == "https://soundpack-backend.fly.dev"
        )

    def test_should_reject_http_scheme(self):
        with pytest.raises(SSRFError, match="Only HTTPS"):
            validate_backend_url("http://example.com")

    def test_should_reject_ftp_scheme(self):
        with pytest.raises(SSRFError, match="Only HTTPS"):
            validate_backend_url("ftp://example.com/file")

    def test_should_reject_file_scheme(self):
        with pytest.raises(SSRFError, match="Only HTTPS"):
            validate_backend_url("file:///etc/passwd")

    def test_should_reject_empty_url(self):
        with pytest.raises(SSRFError, match="must not be empty"):
            validate_backend_url("")

    def test_should_reject_localhost(self):
        with pytest.raises(SSRFError, match="Localhost"):
            validate_backend_url("https://localhost/admin")

    def test_should_reject_127_0_0_1(self):
        with pytest.raises(SSRFError, match="Localhost"):
            validate_backend_url("https://127.0.0.1/admin")

    def test_should_reject_ipv6_loopback(self):
        with pytest.raises(SSRFError):
            validate_backend_url("https://::1/admin")

    def test_should_reject_private_10_x(self):
        with pytest.raises(SSRFError, match="private|Private"):
            validate_backend_url("https://10.0.0.1/secret")

    def test_should_reject_private_172_16(self):
        with pytest.raises(SSRFError, match="private|Private"):
            validate_backend_url("https://172.16.0.1/secret")

    def test_should_reject_private_192_168(self):
        with pytest.raises(SSRFError, match="private|Private"):
            validate_backend_url("https://192.168.1.1/secret")

    def test_should_reject_link_local_169_254(self):
        with pytest.raises(SSRFError, match="private|Private"):
            validate_backend_url("https://169.254.169.254/latest/meta-data/")

    def test_should_reject_0_0_0_0(self):
        with pytest.raises(SSRFError, match="Localhost"):
            validate_backend_url("https://0.0.0.0/")

    def test_should_reject_no_scheme(self):
        with pytest.raises(SSRFError, match="Only HTTPS"):
            validate_backend_url("example.com")


class TestGitHubBackendClientSSRF:
    """Verify that GitHubBackendClient rejects SSRF URLs at construction."""

    def test_should_reject_http_backend_url(self):
        from accessiweather.services.github_backend_client import GitHubBackendClient

        with pytest.raises(SSRFError, match="Only HTTPS"):
            GitHubBackendClient(backend_url="http://evil.internal")

    def test_should_reject_private_ip_backend_url(self):
        from accessiweather.services.github_backend_client import GitHubBackendClient

        with pytest.raises(SSRFError, match="private|Private"):
            GitHubBackendClient(backend_url="https://10.0.0.1")

    def test_should_accept_valid_backend_url(self):
        from accessiweather.services.github_backend_client import GitHubBackendClient

        client = GitHubBackendClient(backend_url="https://soundpack-backend.fly.dev")
        assert client.backend_url == "https://soundpack-backend.fly.dev"
