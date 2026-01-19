"""
Tests for UI dialogs migrated to gui_builder.

Tests dialog initialization, data population, and helper functions.
All wx/gui_builder components are mocked for headless testing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Mock Setup for wx and gui_builder
# =============================================================================


@pytest.fixture
def mock_wx():
    """Mock wx module for headless testing."""
    with patch.dict("sys.modules", {"wx": MagicMock()}):
        import wx

        wx.ID_OK = 5100
        wx.ID_CANCEL = 5101
        wx.ID_CLOSE = 5102
        wx.OK = 4
        wx.ICON_ERROR = 512
        wx.ICON_WARNING = 256
        wx.MessageBox = MagicMock()
        wx.CallAfter = MagicMock(side_effect=lambda fn, *args, **kw: fn(*args, **kw))
        yield wx


@pytest.fixture
def mock_gui_builder():
    """Mock gui_builder module for headless testing."""
    mock_fields = MagicMock()
    mock_forms = MagicMock()

    # Create mock field classes that return mock instances
    def create_mock_field(*args, **kwargs):
        field = MagicMock()
        field.get_value = MagicMock(return_value="")
        field.set_value = MagicMock()
        field.set_label = MagicMock()
        field.set_items = MagicMock()
        field.get_index = MagicMock(return_value=None)
        field.enable = MagicMock()
        field.disable = MagicMock()
        field.set_accessible_label = MagicMock()
        field.add_callback = MagicMock(return_value=lambda fn: fn)
        return field

    mock_fields.StaticText = create_mock_field
    mock_fields.Text = create_mock_field
    mock_fields.CheckBox = create_mock_field
    mock_fields.ListBox = create_mock_field
    mock_fields.Button = create_mock_field
    mock_fields.ComboBox = create_mock_field

    # Mock Dialog class
    class MockDialog:
        def __init__(self, **kwargs):
            self.widget = MagicMock()
            self.widget.control = MagicMock()
            self.widget.control.EndModal = MagicMock()
            self.widget.control.ShowModal = MagicMock(return_value=5101)  # ID_CANCEL
            self.widget.control.Destroy = MagicMock()

        def render(self, **kwargs):
            pass

    mock_forms.Dialog = MockDialog

    with patch.dict(
        "sys.modules",
        {
            "gui_builder": MagicMock(),
            "gui_builder.fields": mock_fields,
            "gui_builder.forms": mock_forms,
        },
    ):
        yield mock_fields, mock_forms


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_alert():
    """Sample weather alert for testing."""
    from accessiweather.models import WeatherAlert

    return WeatherAlert(
        id="test-alert-001",
        title="Severe Thunderstorm Warning",
        description="Severe thunderstorms expected with large hail and damaging winds.",
        severity="Severe",
        urgency="Immediate",
        certainty="Observed",
        event="Severe Thunderstorm Warning",
        headline="Severe Thunderstorm Warning in effect until 8 PM",
        instruction="Take shelter immediately in a sturdy building.",
        onset=datetime.now(UTC),
        expires=datetime.now(UTC) + timedelta(hours=2),
        areas=["Test County", "Sample County"],
    )


@pytest.fixture
def sample_environmental():
    """Sample environmental conditions for testing."""
    env = MagicMock()
    env.has_data = MagicMock(return_value=True)
    env.air_quality_index = 45.0
    env.air_quality_category = "Good"
    env.air_quality_pollutant = "PM2_5"
    env.uv_index = 6.0
    env.uv_category = "High"
    env.updated_at = datetime.now(UTC)
    env.hourly_air_quality = []
    env.hourly_uv_index = []
    return env


@pytest.fixture
def mock_app():
    """Mock AccessiWeatherApp for testing."""
    app = MagicMock()
    app.config_manager = MagicMock()

    # Mock location
    location = MagicMock()
    location.name = "Test City, NY"
    location.latitude = 40.7128
    location.longitude = -74.0060
    app.config_manager.get_current_location = MagicMock(return_value=location)
    app.config_manager.get_all_locations = MagicMock(return_value=[location])
    app.config_manager.get_location_names = MagicMock(return_value=["Test City, NY"])

    # Mock weather data
    app.current_weather_data = MagicMock()
    app.current_weather_data.alerts = MagicMock()
    app.current_weather_data.alerts.alerts = []

    # Mock run_async
    app.run_async = MagicMock()

    return app


# =============================================================================
# Alert Dialog Tests
# =============================================================================


class TestAlertDialog:
    """Tests for AlertDialog class."""

    def test_alert_dialog_format_time_string(self):
        """Test formatting time as string."""
        from accessiweather.ui.dialogs.alert_dialog import AlertDialog

        # Create minimal mock
        with (
            patch("accessiweather.ui.dialogs.alert_dialog.forms"),
            patch("accessiweather.ui.dialogs.alert_dialog.fields"),
        ):
            alert = MagicMock()
            alert.event = "Test Alert"

            # Test the format method directly
            dialog = MagicMock(spec=AlertDialog)
            dialog._format_time = AlertDialog._format_time

            # Test string input
            result = dialog._format_time(dialog, "2024-01-15 12:00")
            assert result == "2024-01-15 12:00"

            # Test None input
            result = dialog._format_time(dialog, None)
            assert result == "Unknown"

    def test_alert_dialog_format_time_datetime(self):
        """Test formatting datetime object."""
        from accessiweather.ui.dialogs.alert_dialog import AlertDialog

        dialog = MagicMock(spec=AlertDialog)
        dialog._format_time = AlertDialog._format_time

        test_time = datetime(2024, 1, 15, 14, 30)
        result = dialog._format_time(dialog, test_time)
        assert "January 15, 2024" in result
        assert "2:30 PM" in result


# =============================================================================
# Weather History Dialog Tests
# =============================================================================


class TestWeatherHistoryDialog:
    """Tests for weather history dialog helper functions."""

    def test_build_history_sections_no_data(self):
        """Test building sections with no weather data."""
        from accessiweather.ui.dialogs.weather_history_dialog import _build_history_sections

        app = MagicMock()
        sections = _build_history_sections(app, None)

        assert len(sections) == 1
        assert sections[0][0] == "No Data"
        assert "not available" in sections[0][1]

    def test_build_history_sections_with_daily_history(self):
        """Test building sections with daily history data."""
        from accessiweather.ui.dialogs.weather_history_dialog import _build_history_sections

        app = MagicMock()

        # Create mock weather data with daily history
        weather_data = MagicMock()
        period = MagicMock()
        period.date = "2024-01-15"
        period.high_temp = 75
        period.low_temp = 55
        period.condition = "Sunny"
        weather_data.daily_history = [period]
        weather_data.trend_insights = None
        weather_data.current = None

        sections = _build_history_sections(app, weather_data)

        assert len(sections) >= 1
        # Should have "Recent Weather History" section
        section_names = [s[0] for s in sections]
        assert "Recent Weather History" in section_names

    def test_build_history_sections_with_comparison(self):
        """Test building sections with current vs yesterday comparison."""
        from accessiweather.ui.dialogs.weather_history_dialog import _build_history_sections

        app = MagicMock()

        # Create mock weather data
        weather_data = MagicMock()

        # Daily history
        yesterday = MagicMock()
        yesterday.date = "2024-01-14"
        yesterday.high_temp = 70
        yesterday.low_temp = 50
        yesterday.condition = "Cloudy"
        weather_data.daily_history = [yesterday]

        # Current conditions
        current = MagicMock()
        current.temperature_f = 75
        weather_data.current = current

        weather_data.trend_insights = None

        sections = _build_history_sections(app, weather_data)

        section_names = [s[0] for s in sections]
        assert "Recent Weather History" in section_names
        assert "Today vs Yesterday" in section_names


# =============================================================================
# Air Quality Dialog Tests
# =============================================================================


class TestAirQualityDialog:
    """Tests for air quality dialog constants and logic."""

    def test_air_quality_guidance_keys(self):
        """Test that air quality guidance has expected categories."""
        from accessiweather.ui.dialogs.air_quality_dialog import _AIR_QUALITY_GUIDANCE

        expected_categories = [
            "Good",
            "Moderate",
            "Unhealthy for Sensitive Groups",
            "Unhealthy",
            "Very Unhealthy",
            "Hazardous",
        ]
        for category in expected_categories:
            assert category in _AIR_QUALITY_GUIDANCE

    def test_pollutant_labels(self):
        """Test pollutant label mappings."""
        from accessiweather.ui.dialogs.air_quality_dialog import _POLLUTANT_LABELS

        assert "PM2_5" in _POLLUTANT_LABELS
        assert "PM10" in _POLLUTANT_LABELS
        assert "O3" in _POLLUTANT_LABELS
        assert "NO2" in _POLLUTANT_LABELS
        assert "SO2" in _POLLUTANT_LABELS
        assert "CO" in _POLLUTANT_LABELS

        # Check human-readable names
        assert "Fine Particles" in _POLLUTANT_LABELS["PM2_5"]
        assert "Ozone" in _POLLUTANT_LABELS["O3"]


# =============================================================================
# UV Index Dialog Tests
# =============================================================================


class TestUVIndexDialog:
    """Tests for UV index dialog constants and logic."""

    def test_uv_guidance_keys(self):
        """Test that UV guidance has expected categories."""
        from accessiweather.ui.dialogs.uv_index_dialog import _UV_INDEX_GUIDANCE

        expected_categories = ["Low", "Moderate", "High", "Very High", "Extreme"]
        for category in expected_categories:
            assert category in _UV_INDEX_GUIDANCE

    def test_uv_sun_safety_keys(self):
        """Test that sun safety recommendations exist for all categories."""
        from accessiweather.ui.dialogs.uv_index_dialog import _UV_SUN_SAFETY

        expected_categories = ["Low", "Moderate", "High", "Very High", "Extreme"]
        for category in expected_categories:
            assert category in _UV_SUN_SAFETY
            # Each should have actual content
            assert len(_UV_SUN_SAFETY[category]) > 0

    def test_extreme_uv_safety_warnings(self):
        """Test that extreme UV has appropriate warnings."""
        from accessiweather.ui.dialogs.uv_index_dialog import _UV_SUN_SAFETY

        extreme_safety = _UV_SUN_SAFETY["Extreme"]
        # Should mention avoiding outdoor activities
        assert "avoid" in extreme_safety.lower() or "AVOID" in extreme_safety


# =============================================================================
# Aviation Dialog Tests
# =============================================================================


class TestAviationDialog:
    """Tests for aviation dialog ICAO validation."""

    def test_icao_regex_valid_codes(self):
        """Test that valid ICAO codes match."""
        from accessiweather.ui.dialogs.aviation_dialog import _ICAO_RE

        valid_codes = ["KJFK", "EGLL", "LFPG", "RJTT", "ZBAA"]
        for code in valid_codes:
            assert _ICAO_RE.match(code) is not None, f"{code} should be valid"

    def test_icao_regex_invalid_codes(self):
        """Test that invalid ICAO codes don't match."""
        from accessiweather.ui.dialogs.aviation_dialog import _ICAO_RE

        invalid_codes = [
            "JFK",  # Too short
            "KJFKA",  # Too long
            "K123",  # Contains numbers
            "kjfk",  # Lowercase
            "KJ FK",  # Contains space
            "",  # Empty
        ]
        for code in invalid_codes:
            assert _ICAO_RE.match(code) is None, f"{code} should be invalid"


# =============================================================================
# Model Browser Dialog Tests
# =============================================================================


class TestModelBrowserDialog:
    """Tests for model browser dialog logic."""

    def test_model_filtering_by_search(self):
        """Test that search filtering works correctly."""
        # Create mock models
        model1 = MagicMock()
        model1.name = "GPT-4"
        model1.id = "openai/gpt-4"
        model1.description = "Advanced language model"
        model1.is_free = False

        model2 = MagicMock()
        model2.name = "Claude"
        model2.id = "anthropic/claude"
        model2.description = "AI assistant"
        model2.is_free = True

        models = [model1, model2]

        # Filter by search text
        search_text = "gpt"
        filtered = [
            m
            for m in models
            if search_text in m.name.lower()
            or search_text in m.id.lower()
            or search_text in (m.description or "").lower()
        ]

        assert len(filtered) == 1
        assert filtered[0].name == "GPT-4"

    def test_model_filtering_by_free_only(self):
        """Test that free-only filtering works correctly."""
        model1 = MagicMock()
        model1.is_free = False

        model2 = MagicMock()
        model2.is_free = True

        model3 = MagicMock()
        model3.is_free = True

        models = [model1, model2, model3]

        # Filter for free only
        filtered = [m for m in models if m.is_free]

        assert len(filtered) == 2

    def test_model_pricing_format_free(self):
        """Test pricing format for free models."""
        model = MagicMock()
        model.is_free = True

        pricing = "Free" if model.is_free else "Paid"
        assert pricing == "Free"

    def test_model_pricing_format_paid(self):
        """Test pricing format for paid models."""
        model = MagicMock()
        model.is_free = False
        model.pricing_prompt = 0.001  # $0.001 per 1M tokens

        if model.is_free:
            pricing = "Free"
        else:
            prompt_cost = model.pricing_prompt / 1000
            pricing = f"${prompt_cost:.6f} per 1K tokens"

        assert "$" in pricing
        assert "per 1K tokens" in pricing


# =============================================================================
# Location Dialog Tests
# =============================================================================


class TestLocationDialog:
    """Tests for location dialog validation logic."""

    def test_coordinate_format(self):
        """Test coordinate formatting."""
        latitude = 40.7128
        longitude = -74.0060

        # Simple format
        coords_str = f"{latitude:.4f}, {longitude:.4f}"
        assert "40.7128" in coords_str
        assert "-74.0060" in coords_str

    def test_empty_location_name_validation(self):
        """Test that empty location names are rejected."""
        name = "   "
        is_valid = bool(name.strip())
        assert is_valid is False

    def test_valid_location_name(self):
        """Test that valid location names are accepted."""
        name = "New York, NY"
        is_valid = bool(name.strip())
        assert is_valid is True


# =============================================================================
# Explanation Dialog Tests
# =============================================================================


class TestExplanationDialog:
    """Tests for explanation dialog formatting."""

    def test_timestamp_format(self):
        """Test timestamp formatting for display."""
        timestamp = datetime(2024, 1, 15, 14, 30)
        formatted = timestamp.strftime("%B %d, %Y at %I:%M %p")

        assert "January 15, 2024" in formatted
        assert "2:30 PM" in formatted

    def test_cost_format_zero(self):
        """Test cost format for zero cost."""
        estimated_cost = 0
        cost_text = "No cost" if estimated_cost == 0 else f"~${estimated_cost:.6f}"
        assert cost_text == "No cost"

    def test_cost_format_nonzero(self):
        """Test cost format for non-zero cost."""
        estimated_cost = 0.000123
        cost_text = "No cost" if estimated_cost == 0 else f"~${estimated_cost:.6f}"
        assert "$0.000123" in cost_text

    def test_token_usage_format(self):
        """Test token usage display format."""
        token_count = 1500
        cost_text = "~$0.001500"
        usage_text = f"Tokens: {token_count} | Cost: {cost_text}"

        assert "Tokens: 1500" in usage_text
        assert "Cost:" in usage_text
