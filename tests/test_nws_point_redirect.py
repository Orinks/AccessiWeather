"""NWS point precision redirects must resolve to actual weather metadata."""

import httpx

from accessiweather.api_client import NoaaApiClient


def test_point_precision_redirect_resolves_before_caching(monkeypatch):
    requested = []
    metadata = {"properties": {"forecast": "https://api.weather.gov/gridpoints/OKX/33,35/forecast"}}

    def respond(request):
        requested.append(request.url.path)
        if request.url.path == "/points/40.710335,-73.99308":
            return httpx.Response(
                301,
                headers={"Location": "/points/40.7103,-73.9931"},
                json={"status": 301, "title": "Adjusting Precision Of Point Coordinate"},
            )
        return httpx.Response(200, json=metadata)

    original_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    client = NoaaApiClient(enable_caching=True)
    assert client.get_point_data(40.710335, -73.99308) == metadata
    assert client.get_point_data(40.710335, -73.99308) == metadata
    assert requested == ["/points/40.710335,-73.99308", "/points/40.7103,-73.9931"]
