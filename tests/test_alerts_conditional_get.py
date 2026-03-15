"""Tests for conditional GET (ETag / Last-Modified) in NWS alert polling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from accessiweather.api.nws.alerts_discussions import NwsAlertsDiscussions


@pytest.fixture()
def discussions():
    """Create a NwsAlertsDiscussions instance with a mocked wrapper."""
    wrapper = MagicMock()
    wrapper.user_agent = "TestAgent"
    wrapper.contact_info = "test@example.com"
    wrapper.core_client.BASE_URL = "https://api.weather.gov"
    return NwsAlertsDiscussions(wrapper)


def _mock_response(status_code=200, json_data=None, headers=None):
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = httpx.Headers(headers or {})
    resp.raise_for_status = MagicMock()
    return resp


class TestConditionalGet:
    """Tests for _fetch_alerts_conditional."""

    def test_first_request_stores_etag_and_last_modified(self, discussions):
        resp = _mock_response(
            200,
            json_data={"features": []},
            headers={"ETag": '"abc123"', "Last-Modified": "Wed, 11 Mar 2026 12:00:00 GMT"},
        )
        with patch("accessiweather.api.nws.alerts_discussions.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(
                return_value=MagicMock(get=MagicMock(return_value=resp))
            )
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = discussions._fetch_alerts_conditional(
                "https://api.weather.gov/alerts/active?point=40,-90"
            )

        assert result == {"features": []}
        assert discussions._alert_etag == '"abc123"'
        assert discussions._alert_last_modified == "Wed, 11 Mar 2026 12:00:00 GMT"
        assert discussions._cached_alert_response == {"features": []}

    def test_304_returns_cached_data(self, discussions):
        # Pre-populate cached state
        discussions._alert_etag = '"abc123"'
        discussions._alert_last_modified = "Wed, 11 Mar 2026 12:00:00 GMT"
        discussions._cached_alert_response = {"features": [{"id": "cached"}]}

        resp = _mock_response(304)
        with patch("accessiweather.api.nws.alerts_discussions.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = resp
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = discussions._fetch_alerts_conditional(
                "https://api.weather.gov/alerts/active?point=40,-90"
            )

        assert result == {"features": [{"id": "cached"}]}
        # Verify conditional headers were sent
        call_args = mock_client.get.call_args
        headers = call_args[1].get("headers", call_args[0][1] if len(call_args[0]) > 1 else {})
        if isinstance(headers, dict):
            assert headers.get("If-None-Match") == '"abc123"'
            assert headers.get("If-Modified-Since") == "Wed, 11 Mar 2026 12:00:00 GMT"

    def test_subsequent_request_sends_conditional_headers(self, discussions):
        # Pre-populate cached state
        discussions._alert_etag = '"etag-value"'
        discussions._alert_last_modified = "Mon, 09 Mar 2026 08:00:00 GMT"
        discussions._cached_alert_response = {"features": []}

        resp = _mock_response(
            200,
            json_data={"features": [{"id": "new"}]},
            headers={"ETag": '"etag-new"', "Last-Modified": "Wed, 11 Mar 2026 14:00:00 GMT"},
        )
        with patch("accessiweather.api.nws.alerts_discussions.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = resp
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = discussions._fetch_alerts_conditional(
                "https://api.weather.gov/alerts/active?point=40,-90"
            )

        # Verify conditional headers sent
        call_kwargs = mock_client.get.call_args[1]
        sent_headers = call_kwargs["headers"]
        assert sent_headers["If-None-Match"] == '"etag-value"'
        assert sent_headers["If-Modified-Since"] == "Mon, 09 Mar 2026 08:00:00 GMT"

        # Verify new data is returned and cached
        assert result == {"features": [{"id": "new"}]}
        assert discussions._alert_etag == '"etag-new"'
        assert discussions._alert_last_modified == "Wed, 11 Mar 2026 14:00:00 GMT"
        assert discussions._cached_alert_response == {"features": [{"id": "new"}]}

    def test_graceful_degradation_no_caching_headers(self, discussions):
        """When server returns 200 without ETag/Last-Modified, conditional GET state is not set."""
        resp = _mock_response(200, json_data={"features": [{"id": "fresh"}]}, headers={})
        with patch("accessiweather.api.nws.alerts_discussions.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(
                return_value=MagicMock(get=MagicMock(return_value=resp))
            )
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = discussions._fetch_alerts_conditional(
                "https://api.weather.gov/alerts/active?point=40,-90"
            )

        assert result == {"features": [{"id": "fresh"}]}
        assert discussions._alert_etag is None
        assert discussions._alert_last_modified is None
        # Response is still cached for potential future 304
        assert discussions._cached_alert_response == {"features": [{"id": "fresh"}]}

    def test_first_request_no_conditional_headers_sent(self, discussions):
        """First request should not include If-None-Match or If-Modified-Since."""
        resp = _mock_response(200, json_data={"features": []}, headers={})
        with patch("accessiweather.api.nws.alerts_discussions.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = resp
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            discussions._fetch_alerts_conditional(
                "https://api.weather.gov/alerts/active?point=40,-90"
            )

        call_kwargs = mock_client.get.call_args[1]
        sent_headers = call_kwargs["headers"]
        assert "If-None-Match" not in sent_headers
        assert "If-Modified-Since" not in sent_headers

    def test_reset_conditional_cache(self, discussions):
        """reset_conditional_cache clears all conditional GET state."""
        discussions._alert_etag = '"abc"'
        discussions._alert_last_modified = "some date"
        discussions._cached_alert_response = {"features": []}

        discussions.reset_conditional_cache()

        assert discussions._alert_etag is None
        assert discussions._alert_last_modified is None
        assert discussions._cached_alert_response is None


class TestHardcodedAlertPollInterval:
    """Test that alert poll interval uses the constant."""

    def test_constant_value(self):
        from accessiweather.constants import ALERT_POLL_INTERVAL_SECONDS

        assert ALERT_POLL_INTERVAL_SECONDS == 60

    def test_event_check_interval_removed_from_settings(self):
        """event_check_interval_minutes should not be on AppSettings."""
        from accessiweather.models.config import AppSettings

        assert not hasattr(AppSettings(), "event_check_interval_minutes")

    def test_old_config_with_event_check_interval_loads_without_error(self):
        """Configs with the removed key should load silently."""
        from accessiweather.models.config import AppSettings

        old_config = {"event_check_interval_minutes": 5, "update_interval_minutes": 10}
        settings = AppSettings.from_dict(old_config)
        assert settings.update_interval_minutes == 10
        # The old key is silently ignored
        assert not hasattr(settings, "event_check_interval_minutes")
