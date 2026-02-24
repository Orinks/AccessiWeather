"""Tests for AccessiWeatherApp notifier property accessors."""

from accessiweather.app import AccessiWeatherApp


def test_notifier_property_getter_returns_private_notifier():
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    sentinel = object()
    app._notifier = sentinel

    assert app.notifier is sentinel


def test_notifier_property_setter_updates_private_notifier():
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    sentinel = object()

    app.notifier = sentinel

    assert app._notifier is sentinel
