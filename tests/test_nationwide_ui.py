import pytest
from accessiweather.gui import WeatherApp
from unittest.mock import MagicMock, patch

# Assuming WeatherApp is your main app class

@pytest.fixture
def app(monkeypatch):
    # Patch fetcher and service
    monkeypatch.setattr(WeatherApp, 'national_forecast_fetcher', MagicMock())
    monkeypatch.setattr(WeatherApp, '_format_national_forecast', MagicMock(return_value='formatted'))
    app = WeatherApp()
    return app

def test_nationwide_selection_triggers_fetch(app):
    app.selected_location = ('Nationwide', 0, 0)
    app._FetchWeatherData(app.selected_location)
    app.national_forecast_fetcher.fetch.assert_called()

def test_nationwide_success_updates_ui(app):
    app.selected_location = ('Nationwide', 0, 0)
    app._on_national_forecast_fetched({'wpc': {'short_range': 'test'}})
    app._format_national_forecast.assert_called()
    assert app.forecast_text.GetValue() == 'formatted'

def test_nationwide_error_updates_ui(app):
    app.selected_location = ('Nationwide', 0, 0)
    app._on_national_forecast_error('fail')
    assert 'Error' in app.forecast_text.GetValue()

def test_alerts_not_fetched_for_nationwide(app):
    app.selected_location = ('Nationwide', 0, 0)
    app._FetchWeatherData(app.selected_location)
    # Alerts fetcher should not be called
    if hasattr(app, 'alerts_fetcher'):
        app.alerts_fetcher.fetch.assert_not_called()
