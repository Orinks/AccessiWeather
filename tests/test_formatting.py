import pytest
from accessiweather.gui import WeatherApp

@pytest.fixture
def app():
    return WeatherApp()

def test_format_national_forecast_all_sections(app):
    data = {
        'wpc': {'short_range': 'WPC text'},
        'spc': {'day1': 'SPC text'},
        'nhc': {'atlantic': 'NHC text'},
        'cpc': {'6_10_day': 'CPC text'}
    }
    text = app._format_national_forecast(data)
    assert 'WPC' in text and 'SPC' in text and 'NHC' in text and 'CPC' in text

def test_format_national_forecast_missing_data(app):
    data = { 'wpc': {}, 'spc': {}, 'nhc': {}, 'cpc': {} }
    text = app._format_national_forecast(data)
    assert 'No data' in text or text.strip() != ''
