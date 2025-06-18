"""Tests for WeatherService national forecast data functionality."""

import time
from unittest.mock import patch

import pytest

from accessiweather.api_client import ApiClientError

from .conftest import SAMPLE_NATIONAL_DISCUSSION_DATA


def test_get_national_forecast_data_success(weather_service):
    """Test getting national forecast data successfully."""
    # Mock the NationalDiscussionScraper.fetch_all_discussions method
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.return_value = SAMPLE_NATIONAL_DISCUSSION_DATA

        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()

        # Verify cache was updated
        assert weather_service.national_data_cache == SAMPLE_NATIONAL_DISCUSSION_DATA
        assert weather_service.national_data_timestamp > 0


def test_get_national_forecast_data_with_cache(weather_service):
    """Test getting national forecast data from cache."""
    # Set up cache
    weather_service.national_data_cache = SAMPLE_NATIONAL_DISCUSSION_DATA
    weather_service.national_data_timestamp = time.time()

    # Mock the scraper to verify it's not called
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_not_called()


def test_get_national_forecast_data_with_force_refresh(weather_service):
    """Test getting national forecast data with force_refresh=True."""
    # Set up cache
    weather_service.national_data_cache = {"old": "data"}
    weather_service.national_data_timestamp = time.time()

    # Mock the scraper
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.return_value = SAMPLE_NATIONAL_DISCUSSION_DATA

        result = weather_service.get_national_forecast_data(force_refresh=True)

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()

        # Verify cache was updated
        assert weather_service.national_data_cache == SAMPLE_NATIONAL_DISCUSSION_DATA


def test_get_national_forecast_data_with_expired_cache(weather_service):
    """Test getting national forecast data with expired cache."""
    # Set up expired cache (timestamp from 2 hours ago)
    weather_service.national_data_cache = {"old": "data"}
    weather_service.national_data_timestamp = time.time() - 7200  # 2 hours ago

    # Mock the scraper
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.return_value = SAMPLE_NATIONAL_DISCUSSION_DATA

        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()

        # Verify cache was updated
        assert weather_service.national_data_cache == SAMPLE_NATIONAL_DISCUSSION_DATA


def test_get_national_forecast_data_error_no_cache(weather_service):
    """Test getting national forecast data when scraper raises an error and no cache exists."""
    # Ensure no cache
    weather_service.national_data_cache = None

    # Mock the scraper to raise an exception
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.side_effect = Exception("Scraper Error")

        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_national_forecast_data()

        assert "Unable to retrieve nationwide forecast data" in str(exc_info.value)
        mock_fetch.assert_called_once()


def test_get_national_forecast_data_error_with_cache(weather_service):
    """Test getting national forecast data when scraper raises an error but cache exists."""
    # Set up cache
    weather_service.national_data_cache = SAMPLE_NATIONAL_DISCUSSION_DATA
    weather_service.national_data_timestamp = time.time() - 7200  # Expired cache (2 hours ago)

    # Mock the scraper to raise an exception
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.side_effect = Exception("Scraper Error")

        # Should return cached data even though it's expired
        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()
