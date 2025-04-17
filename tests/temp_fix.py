# Import faulthandler setup first to enable faulthandler


import queue
from unittest.mock import MagicMock, patch

import unittest
import queue
from unittest.mock import MagicMock, patch
import wx  # type: ignore
from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.gui.weather_app import WeatherApp

class AsyncForecastAlertsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App() if not wx.GetApp() else wx.GetApp()

    def setUp(self):
        self.frame = wx.Frame(None)
        self.mock_api_client = MagicMock(spec=NoaaApiClient)
        self.mock_api_client.get_forecast.return_value = {
            "properties": {"periods": [{"name": "Default", "temperature": 0}]}
        }
        self.mock_api_client.get_alerts.return_value = {"features": []}
        self.mock_location_service = MagicMock()
        self.mock_location_service.get_current_location.return_value = ("Test Location", 35.0, -80.0)
        self.event_queue = queue.Queue()

    def tearDown(self):
        wx.CallAfter(self.frame.Hide)
        wx.SafeYield()
        wx.CallAfter(self.frame.Destroy)
        wx.SafeYield()

    # Test methods will be implemented below...


    def test_forecast_fetched_asynchronously(self):
        with patch.object(WeatherApp, "UpdateWeatherData", return_value=None):
            app = WeatherApp(
                self.frame,
                weather_service=MagicMock(),
                location_service=MagicMock(),
                notification_service=MagicMock(),
                api_client=self.mock_api_client,
            )

        def track_status(text):
            self.event_queue.put(("status", text))
        app.SetStatusText = track_status

        expected_forecast = {"properties": {"periods": [{"name": "Async Today", "temperature": 75}]}}
        self.mock_api_client.get_forecast.return_value = expected_forecast
        waiter = AsyncEventWaiter()
        original_on_forecast = app._on_forecast_fetched

        def patched_on_forecast(forecast_data):
            self.event_queue.put(("forecast_fetched", forecast_data))
            original_on_forecast(forecast_data)
            waiter.callback(forecast_data)
        app._on_forecast_fetched = patched_on_forecast

        app.updating = False
        app.UpdateWeatherData()
        result = waiter.wait(timeout_ms=5000)
        self.assertEqual(result, expected_forecast)
        self.mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)
        status_events = []
        forecast_event = None
        while not self.event_queue.empty():
            event_item = self.event_queue.get(block=False)
            if event_item[0] == "status":
                status_events.append(event_item[1])
            elif event_item[0] == "forecast_fetched":
                forecast_event = event_item
        self.assertTrue(status_events, "No status update events found")
        self.assertIn(
            "Updating weather data for Test Location", status_events[0],
            f"First status was '{status_events[0]}'"
        )
        self.assertTrue(
            any("Ready" in s or "Async Today" in s for s in status_events),
            f"Completion status not found in {status_events}"
        )
        self.assertIsNotNone(forecast_event, "Forecast fetched event not found")
        self.assertEqual(forecast_event[1], expected_forecast)


    def test_alerts_fetched_asynchronously(self):
        with patch("accessiweather.gui.ui_manager.UIManager"):
            with patch.object(WeatherApp, "UpdateWeatherData", return_value=None):
                app = WeatherApp(
                    self.frame,
                    weather_service=MagicMock(),
                    location_service=self.mock_location_service,
                    api_client=self.mock_api_client,
                    notification_service=MagicMock(),
                )

        def track_status(text):
            self.event_queue.put(("status", text))
        app.SetStatusText = track_status

        expected_alerts = {
            "features": [
                {"properties": {"headline": "Async Alert", "description": "Async Description"}}
            ]
        }
        self.mock_api_client.get_alerts.return_value = expected_alerts
        waiter = AsyncEventWaiter()
        original_on_alerts = app._on_alerts_fetched

        def patched_on_alerts(alerts_data):
            self.event_queue.put(("alerts_fetched", alerts_data))
            original_on_alerts(alerts_data)
            waiter.callback(alerts_data)
        app._on_alerts_fetched = patched_on_alerts

        app.ui_manager._UpdateAlertsDisplay = MagicMock(return_value=[])
        def mock_fetch(lat, lon, on_success=None, on_error=None, precise_location=True, radius=25):
            if on_success:
                on_success(expected_alerts)
            return True
        app.alerts_fetcher.fetch = mock_fetch

        app.updating = False
        app.UpdateWeatherData()
        result = waiter.wait(timeout_ms=5000)
        self.assertEqual(result, expected_alerts)
        status_events = []
        alerts_event = None
        while not self.event_queue.empty():
            event_item = self.event_queue.get(block=False)
            if event_item[0] == "status":
                status_events.append(event_item[1])
            elif event_item[0] == "alerts_fetched":
                alerts_event = event_item
        self.assertTrue(status_events, "No status update events found")
        self.assertIn(
            "Updating weather data for Test Location", status_events[0],
            f"First status was '{status_events[0]}'"
        )
        self.assertIsNotNone(alerts_event, "Alerts fetched event not found")
        self.assertEqual(alerts_event[1], expected_alerts)


    def test_forecast_error_handling(self):
        with patch("accessiweather.gui.ui_manager.UIManager"):
            with patch.object(WeatherApp, "UpdateWeatherData", return_value=None):
                app = WeatherApp(
                    self.frame,
                    weather_service=MagicMock(),
                    location_service=self.mock_location_service,
                    api_client=self.mock_api_client,
                    notification_service=MagicMock(),
                )

        def track_status(text):
            self.event_queue.put(("status", text))
        app.SetStatusText = track_status

        error_message = "API forecast network error"
        waiter = AsyncEventWaiter()
        original_on_error = app._on_forecast_error

        def patched_on_error(error):
            self.event_queue.put(("forecast_error", str(error)))
            original_on_error(error)
            waiter.callback(error)
        app._on_forecast_error = patched_on_error

        def mock_fetch(lat, lon, on_success=None, on_error=None):
            if on_error:
                on_error(error_message)
            return True
        app.forecast_fetcher.fetch = mock_fetch

        app.updating = False
        app.UpdateWeatherData()
        result = waiter.wait(timeout_ms=5000)
        self.assertIsNotNone(result)
        self.assertIn(error_message, str(result))
        status_events = []
        error_event = None
        while not self.event_queue.empty():
            event_item = self.event_queue.get(block=False)
            if event_item[0] == "status":
                status_events.append(event_item[1])
            elif event_item[0] == "forecast_error":
                error_event = event_item
        self.assertTrue(status_events, "No status update events found")
        self.assertIn(
            "Updating weather data for Test Location", status_events[0],
            f"First status was '{status_events[0]}'"
        )
        self.assertIsNotNone(error_event, "Forecast error event not found")
        self.assertIn(error_message, error_event[1])


    def test_alerts_error_handling(self):
        with patch("accessiweather.gui.ui_manager.UIManager"):
            with patch.object(WeatherApp, "UpdateWeatherData", return_value=None):
                app = WeatherApp(
                    self.frame,
                    weather_service=MagicMock(),
                    location_service=self.mock_location_service,
                    api_client=self.mock_api_client,
                    notification_service=MagicMock(),
                )

        def track_status(text):
            self.event_queue.put(("status", text))
        app.SetStatusText = track_status

        error_message = "API alerts network error"
        waiter = AsyncEventWaiter()
        original_on_error = app._on_alerts_error

        def patched_on_error(error):
            self.event_queue.put(("alerts_error", str(error)))
            original_on_error(error)
            waiter.callback(error)
        app._on_alerts_error = patched_on_error

        def mock_fetch(lat, lon, on_success=None, on_error=None, precise_location=True, radius=25):
            if on_error:
                on_error(error_message)
            return True
        app.alerts_fetcher.fetch = mock_fetch

        app.alerts_list = MagicMock()
        app.alerts_list.DeleteAllItems = MagicMock()
        app.alerts_list.InsertItem = MagicMock(return_value=0)
        app.alerts_list.SetItem = MagicMock()

        app.updating = False
        app.UpdateWeatherData()
        result = waiter.wait(timeout_ms=5000)
        self.assertIsNotNone(result)
        self.assertIn(error_message, str(result))
        status_events = []
        error_event = None
        while not self.event_queue.empty():
            event_item = self.event_queue.get(block=False)
            if event_item[0] == "status":
                status_events.append(event_item[1])
            elif event_item[0] == "alerts_error":
                error_event = event_item
        self.assertTrue(status_events, "No status update events found")
        self.assertIn(
            "Updating weather data for Test Location", status_events[0],
            f"First status was '{status_events[0]}'"
        )
        self.assertIsNotNone(error_event, "Alerts error event not found")
        self.assertIn(error_message, error_event[1])


    def test_concurrent_fetching(self):
        with patch("accessiweather.gui.ui_manager.UIManager"):
            with patch.object(WeatherApp, "UpdateWeatherData", return_value=None):
                app = WeatherApp(
                    self.frame,
                    weather_service=MagicMock(),
                    location_service=self.mock_location_service,
                    api_client=self.mock_api_client,
                    notification_service=MagicMock(),
                )

        def track_status(text):
            self.event_queue.put(("status", text))
        app.SetStatusText = track_status

        forecast_data = {
            "properties": {"periods": [{"name": "Concurrent Today", "temperature": 70}]}
        }
        alerts_data = {
            "features": [{"properties": {"headline": "Concurrent Alert"}}]
        }
        forecast_waiter = AsyncEventWaiter()
        alerts_waiter = AsyncEventWaiter()
        original_on_forecast = app._on_forecast_fetched
        def patched_on_forecast(data):
            original_on_forecast(data)
            forecast_waiter.callback(data)
        app._on_forecast_fetched = patched_on_forecast
        original_on_alerts = app._on_alerts_fetched
        def patched_on_alerts(data):
            original_on_alerts(data)
            alerts_waiter.callback(data)
        app._on_alerts_fetched = patched_on_alerts
        app.ui_manager._UpdateForecastDisplay = MagicMock()
        app.ui_manager._UpdateAlertsDisplay = MagicMock(return_value=[])
        def mock_forecast_fetch(lat, lon, on_success=None, on_error=None):
            if on_success:
                on_success(forecast_data)
            return True
        def mock_alerts_fetch(lat, lon, on_success=None, on_error=None, precise_location=True, radius=25):
            if on_success:
                on_success(alerts_data)
            return True
        app.forecast_fetcher.fetch = mock_forecast_fetch
        app.alerts_fetcher.fetch = mock_alerts_fetch
        app.updating = False
        app.UpdateWeatherData()
        forecast_result = forecast_waiter.wait(timeout_ms=5000)
        alerts_result = alerts_waiter.wait(timeout_ms=5000)
        self.assertEqual(forecast_result, forecast_data)
        self.assertEqual(alerts_result, alerts_data)
        status_events = []
        while not self.event_queue.empty():
            event_item = self.event_queue.get(block=False)
            if event_item[0] == "status":
                status_events.append(event_item[1])
        self.assertTrue(status_events, "No status update events found")
        self.assertIn("Ready", status_events[-1], f"Final status '{status_events[-1]}' unexpected.")

if __name__ == "__main__":
    unittest.main()
