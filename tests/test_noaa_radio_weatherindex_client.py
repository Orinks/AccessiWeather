"""Focused tests for NOAA radio WeatherIndex station feed lookup."""

from __future__ import annotations

from unittest.mock import MagicMock

import requests

from accessiweather.noaa_radio.weatherindex_client import WeatherIndexClient


def _response(payload, status_code=200):
    response = MagicMock()
    response.json.return_value = payload
    response.status_code = status_code
    response.raise_for_status.side_effect = None
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


def test_fetches_v1_station_detail_endpoint():
    session = MagicMock()
    session.get.return_value = _response({"feeds": []})
    client = WeatherIndexClient(session=session)

    client.get_stream_urls("WXK27")

    session.get.assert_called_once()
    url = session.get.call_args.kwargs.get("url") or session.get.call_args.args[0]
    assert url.endswith("/v1/stations/WXK27")


def test_parses_stream_urls_from_top_level_feeds():
    session = MagicMock()
    session.get.return_value = _response(
        {
            "feeds": [
                {"stream_url": "https://example.com/1"},
                {"stream_url": "https://example.com/2"},
            ]
        }
    )
    client = WeatherIndexClient(session=session)

    assert client.get_stream_urls("WXK27") == [
        "https://example.com/1",
        "https://example.com/2",
    ]


def test_returns_empty_when_feeds_missing():
    session = MagicMock()
    session.get.return_value = _response({"call_sign": "WXK27"})
    client = WeatherIndexClient(session=session)

    assert client.get_stream_urls("WXK27") == []


def test_returns_empty_when_feeds_empty():
    session = MagicMock()
    session.get.return_value = _response({"feeds": []})
    client = WeatherIndexClient(session=session)

    assert client.get_stream_urls("WXK27") == []


def test_returns_empty_on_404():
    session = MagicMock()
    session.get.return_value = _response({}, status_code=404)
    client = WeatherIndexClient(session=session)

    assert client.get_stream_urls("WXK27") == []


def test_returns_empty_on_request_exception():
    session = MagicMock()
    session.get.side_effect = requests.RequestException("boom")
    client = WeatherIndexClient(session=session)

    assert client.get_stream_urls("WXK27") == []


def test_caches_urls_by_call_sign():
    session = MagicMock()
    session.get.return_value = _response({"feeds": [{"stream_url": "https://example.com/live"}]})
    client = WeatherIndexClient(session=session)

    first = client.get_stream_urls("WXK27")
    second = client.get_stream_urls("wxk27")

    assert first == ["https://example.com/live"]
    assert second == ["https://example.com/live"]
    session.get.assert_called_once()
