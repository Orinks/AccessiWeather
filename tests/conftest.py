"""
Pytest configuration and shared fixtures.

This conftest provides minimal, focused fixtures for fast unit testing.
All external API calls should be mocked - no live network requests in unit tests.
"""

from __future__ import annotations

import os
import sys
import tempfile

# ---------------------------------------------------------------------------
# Provide stub wx module when wxPython is not installed (headless servers).
# This allows tests that mock wx to import accessiweather.ui submodules
# without requiring a full wxPython build.
# ---------------------------------------------------------------------------
if "wx" not in sys.modules:
    try:
        import wx  # noqa: F401
    except ImportError:
        import types
        from unittest.mock import MagicMock

        # Build a minimal wx stub module with real base classes so that
        # subclassing (e.g. class MainWindow(wx.Frame)) and patch.object work.
        _wx = types.ModuleType("wx")
        _wx.__package__ = "wx"
        _wx.__path__ = []

        class _WxStubBase:
            """Patchable base class standing in for wx widgets."""

            def __init__(self, *args, **kwargs):
                pass

        _wx.Frame = _WxStubBase
        _wx.Panel = _WxStubBase
        _wx.Dialog = _WxStubBase
        _wx.App = _WxStubBase
        _wx.Window = _WxStubBase
        _wx.Control = _WxStubBase
        _wx.TaskBarIcon = _WxStubBase
        _wx.Menu = MagicMock
        _wx.MenuBar = MagicMock
        _wx.BoxSizer = MagicMock
        _wx.StaticText = MagicMock
        _wx.TextCtrl = MagicMock
        _wx.Button = MagicMock
        _wx.Choice = MagicMock
        _wx.CheckBox = MagicMock
        _wx.Timer = MagicMock
        _wx.Icon = MagicMock
        _wx.Bitmap = MagicMock
        _wx.Image = MagicMock

        # Common constants
        _wx.EVT_CLOSE = MagicMock()
        _wx.EVT_MENU = MagicMock()
        _wx.EVT_BUTTON = MagicMock()
        _wx.EVT_TIMER = MagicMock()
        _wx.ID_ANY = -1
        _wx.ID_OK = 5100
        _wx.ID_CANCEL = 5101
        _wx.OK = 0x0004
        _wx.CANCEL = 0x0010
        _wx.HORIZONTAL = 0x0004
        _wx.VERTICAL = 0x0008
        _wx.EXPAND = 0x2000
        _wx.ALL = 0x0F
        _wx.DEFAULT_FRAME_STYLE = 0
        _wx.ICON_INFORMATION = 0
        _wx.ICON_WARNING = 0
        _wx.ICON_ERROR = 0
        _wx.CallAfter = MagicMock()

        # wx sub-modules
        _wx_lib = types.ModuleType("wx.lib")
        _wx_lib.__package__ = "wx.lib"
        _wx_lib.__path__ = []

        _wx_lib_sized = types.ModuleType("wx.lib.sized_controls")
        _wx_lib_sized.SizedFrame = _WxStubBase
        _wx_lib_sized.SizedPanel = _WxStubBase
        _wx_lib_sized.SizedDialog = _WxStubBase

        _wx_lib_newevent = types.ModuleType("wx.lib.newevent")
        _wx_lib_newevent.NewEvent = lambda: (MagicMock, MagicMock())
        _wx_lib_newevent.NewCommandEvent = lambda: (MagicMock, MagicMock())

        _wx_adv = types.ModuleType("wx.adv")
        _wx_adv.TaskBarIcon = _WxStubBase

        _wx_html2 = types.ModuleType("wx.html2")
        _wx_html2.WebView = MagicMock

        # Wire sub-modules as attributes so `wx.adv`, `wx.lib` etc. resolve
        _wx.lib = _wx_lib
        _wx.adv = _wx_adv
        _wx.html2 = _wx_html2

        sys.modules["wx"] = _wx
        sys.modules["wx.lib"] = _wx_lib
        sys.modules["wx.lib.sized_controls"] = _wx_lib_sized
        sys.modules["wx.lib.newevent"] = _wx_lib_newevent
        sys.modules["wx.adv"] = _wx_adv
        sys.modules["wx.html2"] = _wx_html2

# Provide stub sound_lib when not installed
if "sound_lib" not in sys.modules:
    try:
        import sound_lib  # noqa: F401
    except ImportError:
        import types
        from unittest.mock import MagicMock

        _sl = types.ModuleType("sound_lib")
        _sl.__package__ = "sound_lib"
        _sl.__path__ = []

        _sl_output = types.ModuleType("sound_lib.output")
        _sl_output.Output = MagicMock

        _sl_stream = types.ModuleType("sound_lib.stream")
        _sl_stream.FileStream = MagicMock()

        _sl.output = _sl_output
        _sl.stream = _sl_stream

        sys.modules["sound_lib"] = _sl
        sys.modules["sound_lib.output"] = _sl_output
        sys.modules["sound_lib.stream"] = _sl_stream

# Provide stub gui_builder when not installed
if "gui_builder" not in sys.modules:
    try:
        import gui_builder  # noqa: F401
    except ImportError:
        from unittest.mock import MagicMock

        sys.modules["gui_builder"] = MagicMock()
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set test environment variables before any imports
os.environ["ACCESSIWEATHER_TEST_MODE"] = "1"
os.environ["PYTEST_CURRENT_TEST"] = "true"

# Configure hypothesis for fast CI runs
from hypothesis import settings as hypothesis_settings

hypothesis_settings.register_profile("ci", max_examples=25, deadline=None)
hypothesis_settings.register_profile("dev", max_examples=50, deadline=None)
hypothesis_settings.register_profile("thorough", max_examples=200, deadline=None)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

if TYPE_CHECKING:
    from accessiweather.models import Location


# =============================================================================
# Location Fixtures
# =============================================================================


@pytest.fixture
def sample_location() -> Location:
    """Return a sample US location for testing."""
    from accessiweather.models import Location

    return Location(
        name="Test City, NY",
        latitude=40.7128,
        longitude=-74.0060,
        country_code="US",
    )


@pytest.fixture
def international_location() -> Location:
    """Return a sample international location (outside US)."""
    from accessiweather.models import Location

    return Location(
        name="London, UK",
        latitude=51.5074,
        longitude=-0.1278,
        country_code="GB",
    )


# =============================================================================
# Weather Data Fixtures
# =============================================================================


@pytest.fixture
def sample_current_conditions():
    """Sample current weather conditions."""
    from accessiweather.models import CurrentConditions

    return CurrentConditions(
        temperature_f=72.0,
        temperature_c=22.2,
        condition="Partly Cloudy",
        humidity=65,
        wind_speed_mph=10.0,
        wind_speed_kph=16.1,
        wind_direction="NW",
        pressure_in=30.05,
        pressure_mb=1017.0,
        feels_like_f=74.0,
        feels_like_c=23.3,
    )


@pytest.fixture
def sample_forecast():
    """Sample weather forecast."""
    from accessiweather.models import Forecast, ForecastPeriod

    periods = [
        ForecastPeriod(
            name="Today",
            temperature=75,
            temperature_unit="F",
            short_forecast="Sunny",
            detailed_forecast="Sunny with highs near 75.",
        ),
        ForecastPeriod(
            name="Tonight",
            temperature=55,
            temperature_unit="F",
            short_forecast="Clear",
            detailed_forecast="Clear skies with lows around 55.",
        ),
    ]
    return Forecast(periods=periods, generated_at=datetime.now(UTC))


@pytest.fixture
def sample_hourly_forecast():
    """Sample hourly forecast."""
    from accessiweather.models import HourlyForecast, HourlyForecastPeriod

    now = datetime.now(UTC)
    periods = [
        HourlyForecastPeriod(
            start_time=now + timedelta(hours=i),
            temperature=70 + i,
            temperature_unit="F",
            short_forecast="Partly Cloudy",
        )
        for i in range(24)
    ]
    return HourlyForecast(periods=periods, generated_at=now)


@pytest.fixture
def sample_weather_alert():
    """Sample weather alert."""
    from accessiweather.models import WeatherAlert

    return WeatherAlert(
        id="test-alert-001",
        title="Heat Advisory",
        description="Heat advisory in effect from noon to 8 PM.",
        severity="Moderate",
        urgency="Expected",
        certainty="Likely",
        event="Heat Advisory",
        headline="Heat Advisory issued",
        onset=datetime.now(UTC),
        expires=datetime.now(UTC) + timedelta(hours=8),
    )


@pytest.fixture
def sample_weather_alerts(sample_weather_alert):
    """Sample weather alerts collection."""
    from accessiweather.models import WeatherAlerts

    return WeatherAlerts(alerts=[sample_weather_alert])


@pytest.fixture
def sample_weather_data(sample_location, sample_current_conditions, sample_forecast):
    """Complete sample weather data."""
    from accessiweather.models import WeatherAlerts, WeatherData

    return WeatherData(
        location=sample_location,
        current=sample_current_conditions,
        forecast=sample_forecast,
        alerts=WeatherAlerts(alerts=[]),
    )


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def temp_config_dir(tmp_path):
    """Temporary directory for configuration files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def mock_app():
    """Mock app for ConfigManager tests."""
    app = MagicMock()
    app.paths = MagicMock()
    app.paths.config = Path(tempfile.mkdtemp())
    return app


# =============================================================================
# HTTP Mocking Fixtures
# =============================================================================


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for API tests."""
    with patch("httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = client_instance
        mock.return_value.__aexit__.return_value = None
        yield client_instance


@pytest.fixture
def mock_httpx_response():
    """Create mock HTTP responses for testing."""

    def _create_response(status_code: int = 200, json_data: dict | None = None):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            from httpx import HTTPStatusError

            response.raise_for_status.side_effect = HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=response
            )
        return response

    return _create_response


# =============================================================================
# Async Test Helpers
# =============================================================================


@pytest.fixture
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()
