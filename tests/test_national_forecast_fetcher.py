import pytest
from unittest.mock import MagicMock, patch
import threading
from accessiweather.national_forecast_fetcher import NationalForecastFetcher

class DummyWeatherService:
    def get_national_forecast_data(self, force_refresh=False):
        return {"wpc": {"short_range": "WPC text"}}

def test_fetch_success(monkeypatch):
    service = DummyWeatherService()
    fetcher = NationalForecastFetcher(service)
    results = {}
    def on_success(data):
        results['data'] = data
    fetcher.fetch(on_success=on_success)
    # Wait for thread to finish
    fetcher.thread.join()
    assert results['data']["wpc"]["short_range"] == "WPC text"

def test_fetch_error(monkeypatch):
    class ErrorService:
        def get_national_forecast_data(self, force_refresh=False):
            raise Exception("fail")
    fetcher = NationalForecastFetcher(ErrorService())
    results = {}
    def on_error(msg):
        results['error'] = msg
    fetcher.fetch(on_error=on_error)
    fetcher.thread.join()
    assert "fail" in results['error']

def test_fetch_cancel(monkeypatch):
    import time
    class SlowService:
        def get_national_forecast_data(self, force_refresh=False):
            time.sleep(0.5)
            return {"dummy": True}
    fetcher = NationalForecastFetcher(SlowService())
    fetcher.fetch()
    fetcher._stop_event.set()
    fetcher.thread.join()
    assert fetcher._stop_event.is_set()
