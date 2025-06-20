"""Integration tests for the nationwide view feature.

This module contains integration tests for the nationwide view feature,
testing the interaction between components.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.api_client import ApiClientError
from accessiweather.national_forecast_fetcher import NationalForecastFetcher
from accessiweather.services.national_discussion_scraper import NationalDiscussionScraper
from accessiweather.services.weather_service import WeatherService

# Sample test data
SAMPLE_NATIONAL_DATA = {
    "wpc": {"summary": "WPC test summary", "full": "WPC test full discussion"},
    "spc": {"summary": "SPC test summary", "full": "SPC test full discussion"},
}

EXPECTED_FORMATTED_DATA = {"national_discussion_summaries": SAMPLE_NATIONAL_DATA}


@pytest.fixture
def app():
    """Create a wxPython app for testing."""
    app = wx.App()
    yield app
    app.Destroy()


@pytest.fixture
def mock_scraper():
    """Create a mock NationalDiscussionScraper for testing."""
    scraper = MagicMock(spec=NationalDiscussionScraper)
    scraper.fetch_all_discussions.return_value = SAMPLE_NATIONAL_DATA
    return scraper


@pytest.fixture
def mock_weather_service(mock_scraper):
    """Create a mock WeatherService with a mock scraper for testing."""
    with patch(
        "accessiweather.services.weather_service.national_forecast.NationalDiscussionScraper",
        return_value=mock_scraper,
    ):
        service = WeatherService(MagicMock())
        yield service


@pytest.fixture
def mock_weather_service_direct():
    """Create a directly mocked WeatherService for testing."""
    service = MagicMock(spec=WeatherService)
    service.get_national_forecast_data.return_value = EXPECTED_FORMATTED_DATA
    return service


@pytest.fixture
def fetcher(mock_weather_service_direct):
    """Create a NationalForecastFetcher with a mock service for testing."""
    return NationalForecastFetcher(mock_weather_service_direct)


class TestNationwideIntegration:
    """Integration tests for the nationwide view feature."""

    def test_weather_service_nationwide_data(self, mock_weather_service, mock_scraper):
        """Test WeatherService fetches nationwide data correctly."""
        # Get nationwide data
        national_data = mock_weather_service.get_national_forecast_data()

        # Verify the scraper was called
        mock_scraper.fetch_all_discussions.assert_called_once()

        # Verify the data structure
        assert "national_discussion_summaries" in national_data
        assert "wpc" in national_data["national_discussion_summaries"]
        assert "spc" in national_data["national_discussion_summaries"]
        assert (
            national_data["national_discussion_summaries"]["wpc"]["summary"] == "WPC test summary"
        )
        assert (
            national_data["national_discussion_summaries"]["spc"]["full"]
            == "SPC test full discussion"
        )

    def test_weather_service_caching(self, mock_weather_service, mock_scraper):
        """Test WeatherService caches nationwide data correctly."""
        # First call should use the scraper
        mock_weather_service.get_national_forecast_data()
        assert mock_scraper.fetch_all_discussions.call_count == 1

        # Second call should use the cache
        mock_weather_service.get_national_forecast_data()
        assert mock_scraper.fetch_all_discussions.call_count == 1

        # Force refresh should call the scraper again
        mock_weather_service.get_national_forecast_data(force_refresh=True)
        assert mock_scraper.fetch_all_discussions.call_count == 2

    def test_weather_service_error_handling(self, mock_weather_service, mock_scraper):
        """Test WeatherService handles errors correctly."""
        # Set up the scraper to raise an exception
        mock_scraper.fetch_all_discussions.side_effect = Exception("Test error")

        # First call with no cache should raise an error
        with pytest.raises(ApiClientError):
            mock_weather_service.get_national_forecast_data()

        # Set up a cache value
        mock_weather_service.national_data_cache = SAMPLE_NATIONAL_DATA
        mock_weather_service.national_data_timestamp = time.time()

        # Now the call should return the cached data even though the scraper fails
        result = mock_weather_service.get_national_forecast_data()
        assert result["national_discussion_summaries"] == SAMPLE_NATIONAL_DATA

    def test_national_forecast_fetcher(self, fetcher, mock_weather_service_direct, app):
        """Test NationalForecastFetcher calls callback with correct data."""
        # Create a mock callback
        callback = MagicMock()

        # Mock wx.CallAfter to directly call the function
        with patch("wx.CallAfter", side_effect=lambda func, *args: func(*args)):
            # Call fetch
            fetcher.fetch(on_success=callback)

            # Wait for the thread to complete
            time.sleep(0.1)

            # Verify the service method was called
            mock_weather_service_direct.get_national_forecast_data.assert_called_once_with(
                force_refresh=False
            )

            # Verify the callback was called with the correct data
            callback.assert_called_once_with(EXPECTED_FORMATTED_DATA)

    def test_national_forecast_fetcher_error(self, fetcher, mock_weather_service_direct, app):
        """Test NationalForecastFetcher handles errors correctly."""
        # Set up the service to raise an exception
        mock_weather_service_direct.get_national_forecast_data.side_effect = Exception("Test error")

        # Create a mock error callback
        error_callback = MagicMock()

        # Mock wx.CallAfter to directly call the function
        with patch("wx.CallAfter", side_effect=lambda func, *args: func(*args)):
            # Call fetch
            fetcher.fetch(on_error=error_callback)

            # Wait for the thread to complete
            time.sleep(0.1)

            # Verify the service method was called
            mock_weather_service_direct.get_national_forecast_data.assert_called_once_with(
                force_refresh=False
            )

            # Verify the error callback was called with an error message
            error_callback.assert_called_once()
            assert "Test error" in error_callback.call_args[0][0]

    def test_national_forecast_fetcher_cancellation(self, fetcher, mock_weather_service_direct):
        """Test NationalForecastFetcher can be cancelled."""

        # Create a blocking service method that we can cancel
        def blocking_get(*args, **kwargs):
            time.sleep(10)  # This would block for 10 seconds
            return EXPECTED_FORMATTED_DATA

        mock_weather_service_direct.get_national_forecast_data.side_effect = blocking_get

        # Start a fetch operation in a separate thread
        thread = threading.Thread(target=fetcher.fetch)
        thread.daemon = True
        thread.start()

        # Give the thread time to start
        time.sleep(0.1)

        # Cancel the operation
        fetcher.cancel()

        # Verify the stop event was set
        assert fetcher._stop_event.is_set()

        # Wait for the thread to complete (should be quick due to cancellation)
        thread.join(timeout=1.0)
        assert not thread.is_alive()

    @patch("accessiweather.services.weather_service.national_forecast.NationalDiscussionScraper")
    def test_end_to_end_flow(self, mock_scraper_class, app):
        """Test the end-to-end flow from service to fetcher to callback."""
        # Set up the mock scraper
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.fetch_all_discussions.return_value = SAMPLE_NATIONAL_DATA
        mock_scraper_class.return_value = mock_scraper_instance

        # Create a real WeatherService with a mock API client
        weather_service = WeatherService(MagicMock())

        # Create a real NationalForecastFetcher with the real service
        fetcher = NationalForecastFetcher(weather_service)

        # Create a mock callback
        callback = MagicMock()

        # Mock wx.CallAfter to directly call the function
        with patch("wx.CallAfter", side_effect=lambda func, *args: func(*args)):
            # Call fetch
            fetcher.fetch(on_success=callback)

            # Wait for the thread to complete
            time.sleep(0.2)

            # Verify the scraper was called
            mock_scraper_instance.fetch_all_discussions.assert_called_once()

            # Verify the callback was called with the correct data structure
            callback.assert_called_once()
            data = callback.call_args[0][0]
            assert "national_discussion_summaries" in data
            assert "wpc" in data["national_discussion_summaries"]
            assert "spc" in data["national_discussion_summaries"]
