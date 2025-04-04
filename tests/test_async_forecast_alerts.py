"""Tests for asynchronous forecast and alert fetching."""

import queue
import threading
import time
from unittest.mock import MagicMock  # Removed unused patch

import pytest
import wx

from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.gui.async_fetchers import AlertsFetcher, ForecastFetcher


@pytest.fixture
def wx_app():
    """Create a wx App for testing."""
    app = wx.App(False)
    yield app
    app.Destroy()


@pytest.fixture
def frame(wx_app):
    """Create a frame for testing."""
    frame = wx.Frame(None)
    yield frame
    frame.Destroy()


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    mock_client = MagicMock(spec=NoaaApiClient)
    mock_client.get_forecast.return_value = {"properties": {"periods": []}}
    mock_client.get_alerts.return_value = {"features": []}
    return mock_client


@pytest.fixture
def event_queue():
    """Create an event queue for testing."""
    return queue.Queue()


def test_forecast_fetch_success(wx_app):
    """Test successful forecast fetch."""
    with frame(wx_app):  # Removed unused 'frm' variable
        mock_client = mock_api_client()
        expected_forecast = {"properties": {"periods": [{"name": "Today", "temperature": 75}]}}
        mock_client.get_forecast.return_value = expected_forecast

        fetcher = ForecastFetcher(mock_client)
        callback_finished_event = threading.Event()

        def on_success(forecast_data):
            assert forecast_data == expected_forecast
            callback_finished_event.set()

        fetcher.fetch(35.0, -80.0, on_success=on_success)

        start_time = time.time()
        timeout = 10
        processed_event = False
        while time.time() - start_time < timeout:
            if callback_finished_event.wait(timeout=0.01):
                processed_event = True
                break
            wx.YieldIfNeeded()
        assert processed_event, "Callback did not finish within the timeout."

        mock_client.get_forecast.assert_called_once_with(35.0, -80.0)


def test_forecast_fetch_error(wx_app):
    """Test forecast fetch error handling."""
    with frame(wx_app):  # Removed unused 'frm' variable
        mock_client = mock_api_client()
        error_message = "Network error fetching forecast"
        mock_client.get_forecast.side_effect = ApiClientError(error_message)

        fetcher = ForecastFetcher(mock_client)
        callback_finished_event = threading.Event()

        def on_error(error):
            assert error == f"Unable to retrieve forecast data: {error_message}"
            callback_finished_event.set()

        fetcher.fetch(35.0, -80.0, on_error=on_error)

        start_time = time.time()
        timeout = 10
        processed_event = False
        while time.time() - start_time < timeout:
            if callback_finished_event.wait(timeout=0.01):
                processed_event = True
                break
            wx.YieldIfNeeded()
        assert processed_event, "Error callback did not finish within the timeout."

        mock_client.get_forecast.assert_called_once_with(35.0, -80.0)


def test_alerts_fetch_success(wx_app):
    """Test successful alerts fetch."""
    with frame(wx_app):  # Removed unused 'frm' variable
        mock_client = mock_api_client()
        expected_alerts = {"features": [{"properties": {"event": "Test Alert"}}]}
        mock_client.get_alerts.return_value = expected_alerts

        fetcher = AlertsFetcher(mock_client)
        callback_finished_event = threading.Event()

        def on_success(alerts_data):
            assert alerts_data == expected_alerts
            callback_finished_event.set()

        fetcher.fetch(35.0, -80.0, on_success=on_success)

        start_time = time.time()
        timeout = 10
        processed_event = False
        while time.time() - start_time < timeout:
            if callback_finished_event.wait(timeout=0.01):
                processed_event = True
                break
            wx.YieldIfNeeded()
        assert processed_event, "Callback did not finish within the timeout."

        mock_client.get_alerts.assert_called_once_with(35.0, -80.0)


def test_alerts_fetch_error(wx_app):
    """Test alerts fetch error handling."""
    with frame(wx_app):  # Removed unused 'frm' variable
        mock_client = mock_api_client()
        error_message = "Network error fetching alerts"
        mock_client.get_alerts.side_effect = ApiClientError(error_message)

        fetcher = AlertsFetcher(mock_client)
        callback_finished_event = threading.Event()

        def on_error(error):
            assert error == f"Unable to retrieve alerts data: {error_message}"
            callback_finished_event.set()

        fetcher.fetch(35.0, -80.0, on_error=on_error)

        start_time = time.time()
        timeout = 10
        processed_event = False
        while time.time() - start_time < timeout:
            if callback_finished_event.wait(timeout=0.01):
                processed_event = True
                break
            wx.YieldIfNeeded()
        assert processed_event, "Error callback did not finish within the timeout."

        mock_client.get_alerts.assert_called_once_with(35.0, -80.0)
