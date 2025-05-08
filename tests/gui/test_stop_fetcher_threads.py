"""Tests for the WeatherAppSystemHandlers._stop_fetcher_threads method."""

import unittest
from unittest.mock import MagicMock, patch

from accessiweather.gui.handlers.system_handlers import WeatherAppSystemHandlers


class TestStopFetcherThreads(unittest.TestCase):
    """Tests for the WeatherAppSystemHandlers._stop_fetcher_threads method."""

    def setUp(self):
        """Set up the test."""
        # Create a mock WeatherAppSystemHandlers instance
        self.handlers = MagicMock(spec=WeatherAppSystemHandlers)

        # Set up the timer
        self.handlers.timer = MagicMock()
        self.handlers.timer.IsRunning.return_value = True

    def test_stop_fetcher_threads_all_present(self):
        """Test that _stop_fetcher_threads stops all fetcher threads when they are all present."""
        # Set up all fetcher attributes
        fetcher_attrs = [
            "forecast_fetcher",
            "alerts_fetcher",
            "discussion_fetcher",
            "current_conditions_fetcher",
            "hourly_forecast_fetcher",
            "national_forecast_fetcher",
        ]

        for attr in fetcher_attrs:
            fetcher = MagicMock()
            setattr(self.handlers, attr, fetcher)

        # Call the method under test
        with patch("accessiweather.gui.handlers.system_handlers.logger") as mock_logger:
            WeatherAppSystemHandlers._stop_fetcher_threads(self.handlers)

        # Verify that all fetchers were stopped
        for attr in fetcher_attrs:
            fetcher = getattr(self.handlers, attr)
            fetcher.stop.assert_called_once()

        # Verify that the timer was stopped
        self.handlers.timer.Stop.assert_called_once()

        # Verify that success was logged
        mock_logger.debug.assert_any_call("All fetchers and timers stopped successfully")

    def test_stop_fetcher_threads_some_missing(self):
        """Test that _stop_fetcher_threads handles missing fetchers gracefully."""
        # Set up only some fetcher attributes
        self.handlers.forecast_fetcher = MagicMock()
        self.handlers.alerts_fetcher = MagicMock()
        # Other fetchers are missing

        # Call the method under test
        with patch("accessiweather.gui.handlers.system_handlers.logger") as mock_logger:
            WeatherAppSystemHandlers._stop_fetcher_threads(self.handlers)

        # Verify that existing fetchers were stopped
        self.handlers.forecast_fetcher.stop.assert_called_once()
        self.handlers.alerts_fetcher.stop.assert_called_once()

        # Verify that the timer was stopped
        self.handlers.timer.Stop.assert_called_once()

        # Verify that missing fetchers were logged
        mock_logger.debug.assert_any_call("discussion_fetcher not found in instance")
        mock_logger.debug.assert_any_call("current_conditions_fetcher not found in instance")
        mock_logger.debug.assert_any_call("hourly_forecast_fetcher not found in instance")
        mock_logger.debug.assert_any_call("national_forecast_fetcher not found in instance")

        # Verify that success was logged
        mock_logger.debug.assert_any_call("All fetchers and timers stopped successfully")

    def test_stop_fetcher_threads_fetcher_exception(self):
        """Test that _stop_fetcher_threads handles exceptions from fetchers gracefully."""
        # Set up fetchers with one that raises an exception
        self.handlers.forecast_fetcher = MagicMock()
        self.handlers.alerts_fetcher = MagicMock()
        self.handlers.alerts_fetcher.stop.side_effect = Exception("Test exception")
        self.handlers.discussion_fetcher = MagicMock()

        # Call the method under test
        with patch("accessiweather.gui.handlers.system_handlers.logger") as mock_logger:
            WeatherAppSystemHandlers._stop_fetcher_threads(self.handlers)

        # Verify that all fetchers were attempted to be stopped
        self.handlers.forecast_fetcher.stop.assert_called_once()
        self.handlers.alerts_fetcher.stop.assert_called_once()
        self.handlers.discussion_fetcher.stop.assert_called_once()

        # Verify that the timer was stopped
        self.handlers.timer.Stop.assert_called_once()

        # Verify that the exception was logged
        mock_logger.error.assert_any_call(
            "Error stopping alerts_fetcher: Test exception", exc_info=True
        )

        # Verify that warning was logged
        mock_logger.warning.assert_any_call("Completed fetcher shutdown with 1 errors")

    def test_stop_fetcher_threads_timer_exception(self):
        """Test that _stop_fetcher_threads handles exceptions from timer gracefully."""
        # Set up fetchers
        self.handlers.forecast_fetcher = MagicMock()
        self.handlers.alerts_fetcher = MagicMock()

        # Make timer.Stop raise an exception
        self.handlers.timer.Stop.side_effect = Exception("Timer exception")

        # Call the method under test
        with patch("accessiweather.gui.handlers.system_handlers.logger") as mock_logger:
            WeatherAppSystemHandlers._stop_fetcher_threads(self.handlers)

        # Verify that all fetchers were stopped
        self.handlers.forecast_fetcher.stop.assert_called_once()
        self.handlers.alerts_fetcher.stop.assert_called_once()

        # Verify that the timer was attempted to be stopped
        self.handlers.timer.Stop.assert_called_once()

        # Verify that the exception was logged
        mock_logger.error.assert_any_call(
            "Error stopping main timer: Timer exception", exc_info=True
        )

        # Verify that warning was logged
        mock_logger.warning.assert_any_call("Completed fetcher shutdown with 1 errors")

    def test_stop_fetcher_threads_no_timer(self):
        """Test that _stop_fetcher_threads handles missing timer gracefully."""
        # Set up fetchers
        self.handlers.forecast_fetcher = MagicMock()
        self.handlers.alerts_fetcher = MagicMock()

        # Remove timer
        delattr(self.handlers, "timer")

        # Call the method under test
        with patch("accessiweather.gui.handlers.system_handlers.logger") as mock_logger:
            WeatherAppSystemHandlers._stop_fetcher_threads(self.handlers)

        # Verify that all fetchers were stopped
        self.handlers.forecast_fetcher.stop.assert_called_once()
        self.handlers.alerts_fetcher.stop.assert_called_once()

        # Verify that missing timer was logged
        mock_logger.debug.assert_any_call("No main timer found in instance")

        # Verify that success was logged
        mock_logger.debug.assert_any_call("All fetchers and timers stopped successfully")


if __name__ == "__main__":
    unittest.main()
