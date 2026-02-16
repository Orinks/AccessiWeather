"""Tests for URL validation utilities (SSRF prevention)."""

import socket
from unittest.mock import patch

import pytest

from accessiweather.utils.url_validation import SSRFError, validate_backend_url


class TestValidateBackendUrl:
    """Tests for validate_backend_url."""

    def test_valid_https_url(self):
        result = validate_backend_url("https://api.example.com/v1")
        assert result == "https://api.example.com/v1"

    def test_strips_whitespace(self):
        result = validate_backend_url("  https://api.example.com  ")
        assert result == "https://api.example.com"

    def test_rejects_empty_string(self):
        with pytest.raises(SSRFError, match="must not be empty"):
            validate_backend_url("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(SSRFError, match="must not be empty"):
            validate_backend_url("   ")

    def test_rejects_http(self):
        with pytest.raises(SSRFError, match="Only HTTPS"):
            validate_backend_url("http://example.com")

    def test_rejects_ftp(self):
        with pytest.raises(SSRFError, match="Only HTTPS"):
            validate_backend_url("ftp://example.com")

    def test_rejects_no_scheme(self):
        with pytest.raises(SSRFError, match="Only HTTPS"):
            validate_backend_url("example.com")

    def test_rejects_localhost(self):
        with pytest.raises(SSRFError, match="Localhost"):
            validate_backend_url("https://localhost/api")

    def test_rejects_127_0_0_1(self):
        with pytest.raises(SSRFError, match="Localhost"):
            validate_backend_url("https://127.0.0.1/api")

    def test_rejects_ipv6_loopback(self):
        # urlparse can't extract hostname from bare ::1, so it fails as "no valid hostname"
        with pytest.raises(SSRFError):
            validate_backend_url("https://::1/api")

    def test_rejects_0_0_0_0(self):
        with pytest.raises(SSRFError, match="Localhost"):
            validate_backend_url("https://0.0.0.0/api")

    def test_rejects_private_ip_10(self):
        with pytest.raises(SSRFError, match="private|Private"):
            validate_backend_url("https://10.0.0.1/api")

    def test_rejects_private_ip_192_168(self):
        with pytest.raises(SSRFError, match="private|Private"):
            validate_backend_url("https://192.168.1.1/api")

    def test_rejects_private_ip_172_16(self):
        with pytest.raises(SSRFError, match="private|Private"):
            validate_backend_url("https://172.16.0.1/api")

    def test_rejects_link_local(self):
        with pytest.raises(SSRFError, match="private|Private"):
            validate_backend_url("https://169.254.1.1/api")

    def test_rejects_no_hostname(self):
        with pytest.raises(SSRFError, match="valid hostname"):
            validate_backend_url("https:///path")

    def test_rejects_hostname_resolving_to_private(self):
        """Hostname that resolves to a private IP should be rejected."""
        fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0))]
        with patch("accessiweather.utils.url_validation.socket.getaddrinfo", return_value=fake_addrinfo), pytest.raises(SSRFError, match="resolves to private"):
            validate_backend_url("https://evil.example.com/api")

    def test_allows_unresolvable_hostname(self):
        """If DNS fails, allow it (will fail at request time)."""
        with patch(
            "accessiweather.utils.url_validation.socket.getaddrinfo",
            side_effect=socket.gaierror("Name resolution failed"),
        ):
            result = validate_backend_url("https://nonexistent.example.com")
            assert result == "https://nonexistent.example.com"

    def test_allows_public_ip(self):
        """Public IPs should be allowed."""
        fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 0))]
        with patch("accessiweather.utils.url_validation.socket.getaddrinfo", return_value=fake_addrinfo):
            result = validate_backend_url("https://dns.google.com")
            assert result == "https://dns.google.com"
