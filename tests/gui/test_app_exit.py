"""Tests for the AccessiWeatherApp.OnExit method."""

import unittest
from unittest.mock import MagicMock, patch

from accessiweather.gui.app import AccessiWeatherApp


class TestAccessiWeatherAppExit(unittest.TestCase):
    """Tests for the AccessiWeatherApp.OnExit method."""

    def setUp(self):
        """Set up the test."""
        self.app = AccessiWeatherApp(False)  # False means don't redirect stdout/stderr

    def tearDown(self):
        """Clean up after the test."""
        # Ensure we don't leave any references to the app
        self.app = None

    @patch("accessiweather.utils.thread_manager.ThreadManager.instance")
    @patch("accessiweather.gui.app.logging")
    def test_onexit_calls_thread_manager(self, mock_logging, mock_thread_manager_instance):
        """Test that OnExit calls ThreadManager.instance().stop_all_threads()."""
        # Set up mocks
        mock_thread_manager = MagicMock()
        mock_thread_manager.stop_all_threads.return_value = []  # No remaining threads
        mock_thread_manager_instance.return_value = mock_thread_manager

        # Call the method under test
        self.app.OnExit()

        # Verify that ThreadManager.instance().stop_all_threads() was called with the correct timeout
        mock_thread_manager.stop_all_threads.assert_called_once_with(timeout=3.0)

        # Verify logging calls
        mock_logging.info.assert_any_call("Application exit initiated")
        mock_logging.info.assert_any_call("Application exit completed successfully")

    @patch("accessiweather.utils.thread_manager.ThreadManager.instance")
    @patch("accessiweather.gui.app.logging")
    def test_onexit_saves_configuration(self, mock_logging, mock_thread_manager_instance):
        """Test that OnExit saves configuration before stopping threads."""
        # Set up mocks
        mock_thread_manager = MagicMock()
        mock_thread_manager_instance.return_value = mock_thread_manager

        # Create a mock WeatherApp with _save_config method
        mock_weather_app = MagicMock()
        mock_weather_app._save_config = MagicMock()

        # Mock GetTopWindow to return our mock WeatherApp
        self.app.GetTopWindow = MagicMock(return_value=mock_weather_app)

        # Mock isinstance to return True for WeatherApp check
        # Mock hasattr to return True for _save_config check
        with (
            patch("accessiweather.gui.app.isinstance", return_value=True),
            patch("accessiweather.gui.app.hasattr", return_value=True),
        ):

            # Call the method under test
            self.app.OnExit()

            # Verify that _save_config was called
            mock_weather_app._save_config.assert_called_once_with(show_errors=False)

            # Verify that configuration was saved before stopping threads
            call_order = mock_logging.debug.call_args_list
            save_config_call_index = -1
            stop_threads_call_index = -1

            for i, call in enumerate(call_order):
                args = call[0]
                if len(args) > 0:
                    if "Saving configuration" in args[0]:
                        save_config_call_index = i
                    elif "Stopping all background threads" in args[0]:
                        stop_threads_call_index = i

            # Assert that save_config was called before stop_threads
            self.assertLess(save_config_call_index, stop_threads_call_index)

    @patch("accessiweather.utils.thread_manager.ThreadManager.instance")
    @patch("accessiweather.gui.app.logging")
    def test_onexit_handles_exceptions(self, mock_logging, mock_thread_manager_instance):
        """Test that OnExit handles exceptions gracefully."""
        # Set up mocks
        mock_thread_manager = MagicMock()
        mock_thread_manager.stop_all_threads.side_effect = Exception("Test exception")
        mock_thread_manager_instance.return_value = mock_thread_manager

        # Call the method under test
        result = self.app.OnExit()

        # Verify that the exception was logged
        mock_logging.error.assert_any_call(
            "Error stopping threads during exit: Test exception", exc_info=True
        )

        # Verify that the warning about errors was logged
        mock_logging.warning.assert_any_call("Application exit completed with some errors")

        # Verify that super().OnExit() was still called (by checking the return value)
        self.assertIsNotNone(result)

    @patch("accessiweather.utils.thread_manager.ThreadManager.instance")
    @patch("accessiweather.gui.app.logging")
    def test_onexit_handles_config_save_exception(self, mock_logging, mock_thread_manager_instance):
        """Test that OnExit handles exceptions during config save."""
        # Set up mocks
        mock_thread_manager = MagicMock()
        mock_thread_manager.stop_all_threads.return_value = []  # No remaining threads
        mock_thread_manager_instance.return_value = mock_thread_manager

        # Create a mock WeatherApp with _save_config method that raises an exception
        mock_weather_app = MagicMock()
        mock_weather_app._save_config.side_effect = Exception("Config save error")

        # Mock GetTopWindow to return our mock WeatherApp
        self.app.GetTopWindow = MagicMock(return_value=mock_weather_app)

        # Mock isinstance to return True for WeatherApp check
        # Mock hasattr to return True for _save_config check
        with (
            patch("accessiweather.gui.app.isinstance", return_value=True),
            patch("accessiweather.gui.app.hasattr", return_value=True),
        ):
            # Call the method under test
            result = self.app.OnExit()

            # Verify that the exception was logged
            mock_logging.error.assert_any_call(
                "Error saving configuration during exit: Config save error", exc_info=True
            )

            # Verify that thread manager was still called despite the config save error
            mock_thread_manager.stop_all_threads.assert_called_once_with(timeout=3.0)

            # Verify that the warning about errors was logged
            mock_logging.warning.assert_any_call("Application exit completed with some errors")

            # Verify that super().OnExit() was still called (by checking the return value)
            self.assertIsNotNone(result)

    @patch("accessiweather.utils.thread_manager.ThreadManager.instance")
    @patch("accessiweather.gui.app.logging")
    def test_onexit_handles_remaining_threads(self, mock_logging, mock_thread_manager_instance):
        """Test that OnExit handles the case when some threads don't stop cleanly."""
        # Set up mocks
        mock_thread_manager = MagicMock()
        # Simulate some threads not stopping cleanly
        mock_thread_manager.stop_all_threads.return_value = ["Thread-1", "Thread-2"]
        mock_thread_manager_instance.return_value = mock_thread_manager

        # Call the method under test
        result = self.app.OnExit()

        # Verify that the warning was logged
        mock_logging.warning.assert_any_call(
            "Some threads did not stop cleanly: ['Thread-1', 'Thread-2']"
        )

        # Verify that the warning about errors was logged
        mock_logging.warning.assert_any_call("Application exit completed with some errors")

        # Verify that super().OnExit() was still called (by checking the return value)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
