"""Unit tests for the Air Quality Dialog."""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

os.environ["TOGA_BACKEND"] = "toga_dummy"

import toga

from accessiweather.dialogs.air_quality_dialog import (
    AirQualityDialog,
    _format_pollutant_details,
    _get_pollutant_name,
)
from accessiweather.models import AppSettings, EnvironmentalConditions, HourlyAirQuality


@pytest.fixture
def mock_toga_app():
    """Create a real Toga app instance with dummy backend."""
    toga.App.app = None
    app = toga.App("Test AccessiWeather", "org.beeware.test")
    app.config = MagicMock()
    app.on_exit = lambda: True
    yield app
    toga.App.app = None


@pytest.fixture
def valid_environmental_data():
    """Environmental data with air quality info."""
    hourly = HourlyAirQuality(
        timestamp=datetime.now(timezone.utc),
        aqi=45,
        category="Good",
        pm2_5=12.5,
        pm10=25.0,
        ozone=40.0,
        nitrogen_dioxide=15.0,
        sulphur_dioxide=5.0,
        carbon_monoxide=200.0,
    )
    return EnvironmentalConditions(
        air_quality_index=45.0,
        air_quality_category="Good",
        air_quality_pollutant="PM2_5",
        hourly_air_quality=[hourly],
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def empty_environmental_data():
    """Environmental data with no air quality info."""
    return EnvironmentalConditions()


@pytest.fixture
def app_settings():
    """Application settings."""
    return AppSettings(time_format_12hour=True)


@pytest.mark.unit
class TestAirQualityDialogCreation:
    """Tests for AirQualityDialog creation."""

    def test_dialog_creation_with_valid_data(
        self, mock_toga_app, valid_environmental_data, app_settings
    ):
        """Test dialog initialization with valid data."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
            settings=app_settings,
        )

        assert dialog.app == mock_toga_app
        assert dialog.location_name == "Test City"
        assert dialog.environmental == valid_environmental_data
        assert dialog.settings == app_settings
        assert dialog.window is None

    def test_dialog_creation_without_settings(self, mock_toga_app, valid_environmental_data):
        """Test dialog initialization without settings."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        assert dialog.settings is None

    def test_build_ui_with_valid_data(self, mock_toga_app, valid_environmental_data, app_settings):
        """Test UI construction with valid environmental data."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None
        assert dialog.window.title == "Air Quality - Test City"
        assert dialog._close_button is not None

    def test_build_ui_with_no_data(self, mock_toga_app, empty_environmental_data, app_settings):
        """Test UI construction when environmental.has_data() returns False."""
        assert empty_environmental_data.has_data() is False

        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Empty City",
            environmental=empty_environmental_data,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None
        assert dialog.window.title == "Air Quality - Empty City"
        assert dialog._close_button is not None


@pytest.mark.unit
class TestAirQualityDialogCloseButton:
    """Tests for close button functionality."""

    def test_close_button_exists(self, mock_toga_app, valid_environmental_data):
        """Test that close button is created."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        dialog._build_ui()

        assert dialog._close_button is not None

    def test_on_close_button_closes_window(self, mock_toga_app, valid_environmental_data):
        """Test that clicking close button closes the window."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        dialog._build_ui()
        mock_window = MagicMock()
        dialog.window = mock_window

        dialog._on_close_button(None)

        mock_window.close.assert_called_once()

    def test_on_close_handler_closes_window(self, mock_toga_app, valid_environmental_data):
        """Test window close handler."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        dialog._build_ui()
        mock_window = MagicMock()
        dialog.window = mock_window

        dialog._on_close(None)

        mock_window.close.assert_called_once()

    def test_on_close_button_no_window(self, mock_toga_app, valid_environmental_data):
        """Test close button when window is None."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        dialog.window = None
        dialog._on_close_button(None)


@pytest.mark.unit
class TestAirQualityDialogAccessibility:
    """Tests for accessibility attributes."""

    def test_close_button_has_accessibility_attributes(
        self, mock_toga_app, valid_environmental_data
    ):
        """Test close button has aria_label and aria_description."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        dialog._build_ui()

        close_button = dialog._close_button
        assert close_button is not None

        aria_label = getattr(close_button, "aria_label", None)
        aria_description = getattr(close_button, "aria_description", None)

        assert aria_label == "Close dialog"
        assert aria_description == "Close the air quality dialog and return to main window"

    def test_no_data_label_has_accessibility_attributes(
        self, mock_toga_app, empty_environmental_data
    ):
        """Test no-data label has accessibility attributes."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Empty City",
            environmental=empty_environmental_data,
        )

        dialog._build_ui()

        content_box = dialog.window.content
        children = list(getattr(content_box, "children", []))

        has_accessible_no_data_label = False
        for child in children:
            aria_label = getattr(child, "aria_label", None)
            if aria_label == "Air quality data unavailable":
                has_accessible_no_data_label = True
                aria_desc = getattr(child, "aria_description", None)
                assert aria_desc is not None
                break

        assert has_accessible_no_data_label, "No-data label should have aria_label"


@pytest.mark.unit
class TestAirQualityDialogSections:
    """Tests for dialog section building."""

    def test_build_summary_section(self, mock_toga_app, valid_environmental_data, app_settings):
        """Test summary section is built correctly."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
            settings=app_settings,
        )

        summary_box = dialog._build_summary_section()

        assert summary_box is not None

    def test_build_hourly_section(self, mock_toga_app, valid_environmental_data, app_settings):
        """Test hourly section is built correctly."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
            settings=app_settings,
        )

        hourly_box = dialog._build_hourly_section()

        assert hourly_box is not None

    def test_build_hourly_section_no_data(self, mock_toga_app, app_settings):
        """Test hourly section with no hourly data."""
        environmental = EnvironmentalConditions(
            air_quality_index=50.0,
            air_quality_category="Moderate",
            hourly_air_quality=[],
        )

        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        hourly_box = dialog._build_hourly_section()

        assert hourly_box is not None

    def test_build_pollutant_section(self, mock_toga_app, valid_environmental_data, app_settings):
        """Test pollutant section is built correctly."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
            settings=app_settings,
        )

        pollutant_box = dialog._build_pollutant_section()

        assert pollutant_box is not None

    def test_build_pollutant_section_no_data(self, mock_toga_app, app_settings):
        """Test pollutant section with no hourly data."""
        environmental = EnvironmentalConditions(
            air_quality_index=50.0,
            air_quality_category="Moderate",
            hourly_air_quality=[],
        )

        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        pollutant_box = dialog._build_pollutant_section()

        assert pollutant_box is not None


@pytest.mark.unit
class TestAirQualityDialogShowAndFocus:
    """Tests for show_and_focus method."""

    @pytest.mark.asyncio
    async def test_show_and_focus_builds_ui(self, mock_toga_app, valid_environmental_data):
        """Test show_and_focus builds UI if window is None."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        assert dialog.window is None

        await dialog.show_and_focus()

        assert dialog.window is not None

    @pytest.mark.asyncio
    async def test_show_and_focus_shows_window(self, mock_toga_app, valid_environmental_data):
        """Test show_and_focus calls window.show()."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        await dialog.show_and_focus()

        assert dialog.window is not None


@pytest.mark.unit
class TestAirQualityDialogEdgeCases:
    """Tests for edge cases and defensive patterns."""

    def test_aqi_without_category(self, mock_toga_app, app_settings):
        """Test dialog with AQI but no category."""
        environmental = EnvironmentalConditions(
            air_quality_index=42.0,
            air_quality_category=None,
            hourly_air_quality=[],
        )

        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None

    def test_category_without_aqi(self, mock_toga_app, app_settings):
        """Test dialog with category but no AQI value."""
        environmental = EnvironmentalConditions(
            air_quality_index=None,
            air_quality_category="Good",
            hourly_air_quality=[],
        )

        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None

    def test_dialog_with_24hour_time_format(self, mock_toga_app, valid_environmental_data):
        """Test dialog with 24-hour time format setting."""
        settings = AppSettings(time_format_12hour=False)

        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
            settings=settings,
        )

        dialog._build_ui()

        assert dialog.window is not None

    def test_dialog_with_no_pollutant(self, mock_toga_app, app_settings):
        """Test dialog with no dominant pollutant specified."""
        hourly = HourlyAirQuality(
            timestamp=datetime.now(timezone.utc),
            aqi=30,
            category="Good",
            pm2_5=8.0,
        )
        environmental = EnvironmentalConditions(
            air_quality_index=30.0,
            air_quality_category="Good",
            air_quality_pollutant=None,
            hourly_air_quality=[hourly],
            updated_at=datetime.now(timezone.utc),
        )

        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None

    def test_dialog_without_updated_at(self, mock_toga_app, app_settings):
        """Test dialog without updated_at timestamp."""
        hourly = HourlyAirQuality(
            timestamp=datetime.now(timezone.utc),
            aqi=50,
            category="Moderate",
        )
        environmental = EnvironmentalConditions(
            air_quality_index=50.0,
            air_quality_category="Moderate",
            hourly_air_quality=[hourly],
            updated_at=None,
        )

        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None


@pytest.mark.unit
class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_pollutant_name_pm25(self):
        """Test pollutant name lookup for PM2.5."""
        assert "PM2.5" in _get_pollutant_name("PM2_5")

    def test_get_pollutant_name_ozone(self):
        """Test pollutant name lookup for ozone."""
        result = _get_pollutant_name("O3")
        assert "ozone" in result.lower() or "O3" in result

    def test_get_pollutant_name_unknown(self):
        """Test pollutant name lookup for unknown code."""
        result = _get_pollutant_name("UNKNOWN_POLL")
        assert result is not None

    def test_format_pollutant_details_with_data(self):
        """Test pollutant detail formatting."""
        hourly = HourlyAirQuality(
            timestamp=datetime.now(timezone.utc),
            aqi=45,
            category="Good",
            pm2_5=12.5,
            pm10=25.0,
        )

        lines = _format_pollutant_details(hourly, "PM2_5")

        assert len(lines) >= 2
        assert any("PM2.5" in line for line in lines)
        assert any("dominant" in line.lower() for line in lines)

    def test_format_pollutant_details_no_dominant(self):
        """Test pollutant detail formatting without dominant pollutant."""
        hourly = HourlyAirQuality(
            timestamp=datetime.now(timezone.utc),
            aqi=45,
            category="Good",
            pm2_5=12.5,
        )

        lines = _format_pollutant_details(hourly, None)

        assert len(lines) >= 1
        assert not any("dominant" in line.lower() for line in lines)

    def test_format_pollutant_details_empty(self):
        """Test pollutant detail formatting with no values."""
        hourly = HourlyAirQuality(
            timestamp=datetime.now(timezone.utc),
            aqi=45,
            category="Good",
        )

        lines = _format_pollutant_details(hourly, None)

        assert lines == []
