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


def _directory_entry(call_sign, *, status="NORMAL", feeds=None, **overrides):
    entry = {
        "callsign": call_sign,
        "state_name": "Texas",
        "state_slug": "TX",
        "city": "Austin",
        "frequency": "162.400",
        "status": status,
        "latitude": 30.3,
        "longitude": -97.7,
        "feeds": [
            {"stream_url": url}
            for url in (feeds if feeds is not None else [f"https://example.com/{call_sign}"])
        ],
    }
    entry.update(overrides)
    return entry


def test_directory_fetches_all_stations_endpoint_once():
    session = MagicMock()
    session.get.return_value = _response([_directory_entry("WXK27"), _directory_entry("KHB34")])
    client = WeatherIndexClient(session=session)

    first = client.get_all_stations()
    second = client.get_all_stations()

    assert [station.call_sign for station in first] == ["WXK27", "KHB34"]
    assert first == second
    session.get.assert_called_once()
    url = session.get.call_args.args[0]
    assert url.endswith("/v1/stations/all")


def test_directory_station_converts_to_player_station():
    session = MagicMock()
    session.get.return_value = _response([_directory_entry("WXK27", status="OUT OF SERVICE")])
    client = WeatherIndexClient(session=session)

    station = client.get_all_stations()[0].to_station()

    assert station is not None
    assert station.call_sign == "WXK27"
    assert station.name == "Austin, TX"
    assert station.state == "TX"
    assert station.frequency == 162.4
    assert (station.lat, station.lon) == (30.3, -97.7)
    assert station.is_out_of_service is True


def test_directory_skips_stations_without_feeds_or_call_sign():
    session = MagicMock()
    session.get.return_value = _response(
        [
            _directory_entry("WXK27", feeds=[]),
            {"city": "Nowhere", "feeds": [{"stream_url": "https://example.com/x"}]},
            _directory_entry("KHB34"),
        ]
    )
    client = WeatherIndexClient(session=session)

    assert [station.call_sign for station in client.get_all_stations()] == ["KHB34"]


def test_directory_feeds_are_used_for_stream_urls_without_detail_request():
    session = MagicMock()
    session.get.return_value = _response(
        [_directory_entry("WXK27", feeds=["https://example.com/a", "https://example.com/b"])]
    )
    client = WeatherIndexClient(session=session)
    client.get_all_stations()

    urls = client.get_stream_urls("wxk27")

    assert urls == ["https://example.com/a", "https://example.com/b"]
    session.get.assert_called_once()


def test_station_missing_from_directory_falls_back_to_detail_endpoint():
    session = MagicMock()
    session.get.side_effect = [
        _response([_directory_entry("WXK27")]),
        _response({"feeds": [{"stream_url": "https://example.com/detail"}]}),
    ]
    client = WeatherIndexClient(session=session)
    client.get_all_stations()

    assert client.get_stream_urls("KHB34") == ["https://example.com/detail"]
    assert session.get.call_args.args[0].endswith("/v1/stations/KHB34")


def test_directory_failure_uses_on_disk_copy(tmp_path):
    cache_path = tmp_path / "stations.json"
    session = MagicMock()
    session.get.return_value = _response([_directory_entry("WXK27")])
    WeatherIndexClient(session=session, directory_cache_path=cache_path).get_all_stations()
    assert cache_path.exists()

    failing_session = MagicMock()
    failing_session.get.side_effect = requests.ConnectionError()
    client = WeatherIndexClient(session=failing_session, directory_cache_path=cache_path)

    stations = client.get_all_stations()

    assert [station.call_sign for station in stations] == ["WXK27"]
    assert client.has_station_directory() is True


def test_directory_failure_without_cache_returns_empty():
    session = MagicMock()
    session.get.side_effect = requests.ConnectionError()
    client = WeatherIndexClient(session=session)

    assert client.get_all_stations() == []
    assert client.has_station_directory() is False
