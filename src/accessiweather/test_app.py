"""Test app for debugging weather data fetching issues."""

import logging
import sys

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .config import ConfigManager
from .models import Location
from .weather_client import WeatherClient

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


class TestWeatherApp(toga.App):
    """Test app for debugging weather issues."""

    def startup(self):
        """Initialize the test app."""
        logger.info("Starting test weather app")

        # Create main window
        self.main_window = toga.MainWindow(title="Weather Test")

        # Create UI
        main_box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        # Status label
        self.status_label = toga.Label("Ready to test weather fetching...", style=Pack(padding=10))
        main_box.add(self.status_label)

        # Test button
        test_button = toga.Button(
            "Test Weather Fetch", on_press=self.test_weather_fetch, style=Pack(padding=10)
        )
        main_box.add(test_button)

        # Results display
        self.results_display = toga.MultilineTextInput(
            readonly=True, style=Pack(height=400, padding=10)
        )
        main_box.add(self.results_display)

        self.main_window.content = main_box
        self.main_window.show()

        # Initialize components
        self.config_manager = ConfigManager(self)
        self.weather_client = WeatherClient(user_agent="AccessiWeather-Test/1.0")

        # Create test location
        self.test_location = Location("Philadelphia, PA", 39.9526, -75.1652)

        logger.info("Test app initialized")

    async def test_weather_fetch(self, widget):
        """Test weather data fetching."""
        logger.info("Starting weather fetch test")

        try:
            self.status_label.text = "Fetching weather data..."
            self.results_display.value = "Starting weather fetch...\n"

            # Test weather client
            logger.info("Testing weather client...")
            weather_data = await self.weather_client.get_weather_data(self.test_location)

            self.results_display.value += f"Weather data fetched successfully!\n"
            self.results_display.value += (
                f"Has current data: {weather_data.current and weather_data.current.has_data()}\n"
            )
            self.results_display.value += (
                f"Has forecast data: {weather_data.forecast and weather_data.forecast.has_data()}\n"
            )
            self.results_display.value += (
                f"Has alerts: {weather_data.alerts and weather_data.alerts.has_alerts()}\n"
            )

            if weather_data.current:
                self.results_display.value += (
                    f"Temperature: {weather_data.current.temperature_f}°F\n"
                )
                self.results_display.value += f"Condition: {weather_data.current.condition}\n"
                self.results_display.value += f"Wind direction: {weather_data.current.wind_direction} (type: {type(weather_data.current.wind_direction)})\n"

            # Test formatter
            logger.info("Testing formatter...")
            try:
                from .formatters import WeatherFormatter
                from .models import AppSettings

                settings = AppSettings()
                formatter = WeatherFormatter(settings)

                self.results_display.value += "\n--- TESTING FORMATTER ---\n"

                # Test current conditions formatting
                current_text = formatter.format_current_conditions(
                    weather_data.current, weather_data.location
                )
                self.results_display.value += f"Current conditions formatted successfully!\n"
                self.results_display.value += f"Length: {len(current_text)} characters\n"

                # Show first 200 characters
                preview = current_text[:200] + "..." if len(current_text) > 200 else current_text
                self.results_display.value += f"Preview: {preview}\n"

                self.status_label.text = "Weather fetch and formatting successful!"

            except Exception as format_error:
                logger.error(f"Formatter error: {format_error}")
                self.results_display.value += f"\n❌ Formatter error: {format_error}\n"
                self.status_label.text = f"Formatter error: {format_error}"

        except Exception as e:
            logger.error(f"Weather fetch error: {e}")
            self.results_display.value += f"\n❌ Weather fetch error: {e}\n"
            self.status_label.text = f"Error: {e}"
            import traceback

            self.results_display.value += f"\nTraceback:\n{traceback.format_exc()}\n"


def main():
    """Main entry point for test app."""
    return TestWeatherApp(
        "Weather Test",
        "net.orinks.accessiweather.test",
        description="Test app for weather debugging",
    )


if __name__ == "__main__":
    main().main_loop()
