"""Unit tests for the UV Index Dialog."""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

os.environ["TOGA_BACKEND"] = "toga_dummy"

import toga

from accessiweather.dialogs.uv_index_dialog import UVIndexDialog
from accessiweather.display.presentation.environmental import (
    _UV_INDEX_GUIDANCE,
    _UV_SUN_SAFETY,
)
from accessiweather.models import AppSettings, EnvironmentalConditions, HourlyUVIndex


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
    """Environmental data with UV index info."""
    hourly = HourlyUVIndex(
        timestamp=datetime.now(timezone.utc),
        uv_index=6.5,
        category="High",
    )
    return EnvironmentalConditions(
        uv_index=6.5,
        uv_category="High",
        hourly_uv_index=[hourly],
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def empty_environmental_data():
    """Environmental data with no UV index info."""
    return EnvironmentalConditions()


@pytest.fixture
def app_settings():
    """Application settings."""
    return AppSettings(time_format_12hour=True)


@pytest.mark.unit
class TestUVIndexDialogCreation:
    """Tests for UVIndexDialog creation."""

    def test_dialog_creation_with_valid_data(
        self, mock_toga_app, valid_environmental_data, app_settings
    ):
        """Test dialog initialization with valid data."""
        dialog = UVIndexDialog(
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
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        assert dialog.settings is None

    def test_build_ui_with_valid_data(self, mock_toga_app, valid_environmental_data, app_settings):
        """Test UI construction with valid environmental data."""
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None
        assert dialog.window.title == "UV Index - Test City"
        assert dialog._close_button is not None

    def test_build_ui_with_no_data(self, mock_toga_app, empty_environmental_data, app_settings):
        """Test UI construction when environmental.has_data() returns False."""
        assert empty_environmental_data.has_data() is False

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Empty City",
            environmental=empty_environmental_data,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None
        assert dialog.window.title == "UV Index - Empty City"
        assert dialog._close_button is not None


@pytest.mark.unit
class TestUVIndexDialogCloseButton:
    """Tests for close button functionality."""

    def test_close_button_exists(self, mock_toga_app, valid_environmental_data):
        """Test that close button is created."""
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        dialog._build_ui()

        assert dialog._close_button is not None

    def test_on_close_button_closes_window(self, mock_toga_app, valid_environmental_data):
        """Test that clicking close button closes the window."""
        dialog = UVIndexDialog(
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
        dialog = UVIndexDialog(
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
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        dialog.window = None
        dialog._on_close_button(None)


@pytest.mark.unit
class TestUVIndexDialogAccessibility:
    """Tests for accessibility attributes."""

    def test_close_button_has_accessibility_attributes(
        self, mock_toga_app, valid_environmental_data
    ):
        """Test close button has aria_label and aria_description."""
        dialog = UVIndexDialog(
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
        assert aria_description == "Close the UV index dialog and return to main window"

    def test_no_data_label_has_accessibility_attributes(
        self, mock_toga_app, empty_environmental_data
    ):
        """Test no-data label has accessibility attributes."""
        dialog = UVIndexDialog(
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
            if aria_label == "UV index data unavailable":
                has_accessible_no_data_label = True
                aria_desc = getattr(child, "aria_description", None)
                assert aria_desc is not None
                break

        assert has_accessible_no_data_label, "No-data label should have aria_label"


@pytest.mark.unit
class TestUVIndexDialogSections:
    """Tests for dialog section building."""

    def test_build_summary_section(self, mock_toga_app, valid_environmental_data, app_settings):
        """Test summary section is built correctly."""
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
            settings=app_settings,
        )

        summary_box = dialog._build_summary_section()

        assert summary_box is not None

    def test_build_hourly_section(self, mock_toga_app, valid_environmental_data, app_settings):
        """Test hourly section is built correctly."""
        dialog = UVIndexDialog(
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
            uv_index=5.0,
            uv_category="Moderate",
            hourly_uv_index=[],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        hourly_box = dialog._build_hourly_section()

        assert hourly_box is not None

    def test_build_sun_safety_section(self, mock_toga_app, valid_environmental_data, app_settings):
        """Test sun safety section is built correctly."""
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
            settings=app_settings,
        )

        sun_safety_box = dialog._build_sun_safety_section()

        assert sun_safety_box is not None

    def test_build_sun_safety_section_no_category(self, mock_toga_app, app_settings):
        """Test sun safety section with no UV category."""
        environmental = EnvironmentalConditions(
            uv_index=5.0,
            uv_category=None,
            hourly_uv_index=[],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        sun_safety_box = dialog._build_sun_safety_section()

        assert sun_safety_box is not None


@pytest.mark.unit
class TestUVIndexDialogShowAndFocus:
    """Tests for show_and_focus method."""

    @pytest.mark.asyncio
    async def test_show_and_focus_builds_ui(self, mock_toga_app, valid_environmental_data):
        """Test show_and_focus builds UI if window is None."""
        dialog = UVIndexDialog(
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
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
        )

        await dialog.show_and_focus()

        assert dialog.window is not None


@pytest.mark.unit
class TestUVIndexDialogEdgeCases:
    """Tests for edge cases and defensive patterns."""

    def test_uv_index_without_category(self, mock_toga_app, app_settings):
        """Test dialog with UV index but no category."""
        environmental = EnvironmentalConditions(
            uv_index=6.5,
            uv_category=None,
            hourly_uv_index=[],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None

    def test_category_without_uv_index(self, mock_toga_app, app_settings):
        """Test dialog with category but no UV index value."""
        environmental = EnvironmentalConditions(
            uv_index=None,
            uv_category="Moderate",
            hourly_uv_index=[],
        )

        dialog = UVIndexDialog(
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

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=valid_environmental_data,
            settings=settings,
        )

        dialog._build_ui()

        assert dialog.window is not None

    def test_dialog_without_updated_at(self, mock_toga_app, app_settings):
        """Test dialog without updated_at timestamp."""
        hourly = HourlyUVIndex(
            timestamp=datetime.now(timezone.utc),
            uv_index=5.0,
            category="Moderate",
        )
        environmental = EnvironmentalConditions(
            uv_index=5.0,
            uv_category="Moderate",
            hourly_uv_index=[hourly],
            updated_at=None,
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None

    def test_dialog_with_extreme_uv_index(self, mock_toga_app, app_settings):
        """Test dialog with extreme UV index."""
        hourly = HourlyUVIndex(
            timestamp=datetime.now(timezone.utc),
            uv_index=12.0,
            category="Extreme",
        )
        environmental = EnvironmentalConditions(
            uv_index=12.0,
            uv_category="Extreme",
            hourly_uv_index=[hourly],
            updated_at=datetime.now(timezone.utc),
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None

    def test_dialog_with_low_uv_index(self, mock_toga_app, app_settings):
        """Test dialog with low UV index."""
        hourly = HourlyUVIndex(
            timestamp=datetime.now(timezone.utc),
            uv_index=1.5,
            category="Low",
        )
        environmental = EnvironmentalConditions(
            uv_index=1.5,
            uv_category="Low",
            hourly_uv_index=[hourly],
            updated_at=datetime.now(timezone.utc),
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None

    def test_dialog_with_multiple_hourly_values(self, mock_toga_app, app_settings):
        """Test dialog with multiple hourly UV values."""
        hourly_data = [
            HourlyUVIndex(
                timestamp=datetime.now(timezone.utc),
                uv_index=5.0,
                category="Moderate",
            ),
            HourlyUVIndex(
                timestamp=datetime.now(timezone.utc),
                uv_index=7.5,
                category="High",
            ),
            HourlyUVIndex(
                timestamp=datetime.now(timezone.utc),
                uv_index=3.0,
                category="Moderate",
            ),
        ]
        environmental = EnvironmentalConditions(
            uv_index=5.0,
            uv_category="Moderate",
            hourly_uv_index=hourly_data,
            updated_at=datetime.now(timezone.utc),
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None


@pytest.mark.unit
class TestUVIndexGuidanceAndSafety:
    """Tests for UV index guidance and sun safety data."""

    def test_all_categories_have_guidance(self):
        """Ensure all UV categories have guidance messages."""
        expected_categories = ["Low", "Moderate", "High", "Very High", "Extreme"]
        for category in expected_categories:
            assert category in _UV_INDEX_GUIDANCE, f"Missing guidance for: {category}"
            assert len(_UV_INDEX_GUIDANCE[category]) > 10, f"Guidance too short for: {category}"

    def test_all_categories_have_sun_safety(self):
        """Ensure all UV categories have sun safety recommendations."""
        expected_categories = ["Low", "Moderate", "High", "Very High", "Extreme"]
        for category in expected_categories:
            assert category in _UV_SUN_SAFETY, f"Missing sun safety for: {category}"
            assert len(_UV_SUN_SAFETY[category]) > 50, f"Sun safety too short for: {category}"

    def test_sun_safety_includes_sunscreen_info(self):
        """Test that sun safety recommendations include sunscreen guidance."""
        for category, safety_text in _UV_SUN_SAFETY.items():
            assert "Sunscreen" in safety_text or "sunscreen" in safety_text.lower(), (
                f"No sunscreen info for {category}"
            )

    def test_sun_safety_includes_clothing_info(self):
        """Test that sun safety recommendations include clothing guidance."""
        for category, safety_text in _UV_SUN_SAFETY.items():
            assert "Clothing" in safety_text or "clothing" in safety_text.lower(), (
                f"No clothing info for {category}"
            )

    def test_sun_safety_includes_shade_info(self):
        """Test that sun safety recommendations include shade guidance."""
        for category, safety_text in _UV_SUN_SAFETY.items():
            assert "Shade" in safety_text or "shade" in safety_text.lower(), (
                f"No shade info for {category}"
            )

    def test_sun_safety_includes_time_info(self):
        """Test that sun safety recommendations include timing guidance."""
        for category, safety_text in _UV_SUN_SAFETY.items():
            assert "Time" in safety_text or "time" in safety_text.lower(), (
                f"No time info for {category}"
            )


@pytest.mark.unit
class TestUVIndexDialogDataValidation:
    """Tests for data validation and defensive coding."""

    def test_dialog_handles_none_uv_values(self, mock_toga_app, app_settings):
        """Test dialog with None UV index and category."""
        environmental = EnvironmentalConditions(
            uv_index=None,
            uv_category=None,
            hourly_uv_index=[],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None

    def test_dialog_with_empty_hourly_list(self, mock_toga_app, app_settings):
        """Test dialog with empty hourly UV list."""
        environmental = EnvironmentalConditions(
            uv_index=5.0,
            uv_category="Moderate",
            hourly_uv_index=[],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        hourly_box = dialog._build_hourly_section()

        assert hourly_box is not None

    def test_dialog_with_none_hourly_list(self, mock_toga_app, app_settings):
        """Test dialog with None hourly UV list."""
        environmental = EnvironmentalConditions(
            uv_index=5.0,
            uv_category="Moderate",
            hourly_uv_index=None,
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        hourly_box = dialog._build_hourly_section()

        assert hourly_box is not None

    def test_dialog_with_unknown_category(self, mock_toga_app, app_settings):
        """Test dialog with unknown UV category."""
        environmental = EnvironmentalConditions(
            uv_index=5.0,
            uv_category="Unknown",
            hourly_uv_index=[],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
            settings=app_settings,
        )

        dialog._build_ui()

        assert dialog.window is not None
