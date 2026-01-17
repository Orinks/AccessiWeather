# Information Priority Ordering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a comprehensive information priority ordering system that controls how weather data is presented based on verbosity level, user-configurable category ordering, and context-aware severe weather prioritization.

**Architecture:** Create a `PriorityEngine` class that determines display order based on active alerts and user preferences. Modify `WeatherPresenter` and presentation builders to accept priority/verbosity settings. Add new settings fields and UI controls to the Display tab.

**Tech Stack:** Python dataclasses, Toga UI widgets, existing WeatherPresenter pattern

---

## Task 1: Add Priority Settings to AppSettings Model

**Files:**
- Modify: `src/accessiweather/models/config.py:10-83`
- Test: `tests/test_priority_settings.py` (new)

**Step 1: Write the failing test**

```python
# tests/test_priority_settings.py
"""Tests for priority ordering settings."""

import pytest
from accessiweather.models.config import AppSettings


class TestPrioritySettings:
    """Test priority ordering settings in AppSettings."""

    def test_default_verbosity_level(self):
        """Default verbosity should be 'standard'."""
        settings = AppSettings()
        assert settings.verbosity_level == "standard"

    def test_default_category_order(self):
        """Default category order should be temperature first."""
        settings = AppSettings()
        expected = [
            "temperature",
            "precipitation",
            "wind",
            "humidity_pressure",
            "visibility_clouds",
            "uv_index",
        ]
        assert settings.category_order == expected

    def test_default_severe_weather_override(self):
        """Severe weather override should be enabled by default."""
        settings = AppSettings()
        assert settings.severe_weather_override is True

    def test_verbosity_level_options(self):
        """Verbosity level should accept valid options."""
        for level in ["minimal", "standard", "detailed"]:
            settings = AppSettings(verbosity_level=level)
            assert settings.verbosity_level == level

    def test_settings_to_dict_includes_priority_fields(self):
        """to_dict should include priority ordering fields."""
        settings = AppSettings()
        data = settings.to_dict()
        assert "verbosity_level" in data
        assert "category_order" in data
        assert "severe_weather_override" in data

    def test_settings_from_dict_loads_priority_fields(self):
        """from_dict should load priority ordering fields."""
        data = {
            "verbosity_level": "minimal",
            "category_order": ["wind", "temperature"],
            "severe_weather_override": False,
        }
        settings = AppSettings.from_dict(data)
        assert settings.verbosity_level == "minimal"
        assert settings.category_order == ["wind", "temperature"]
        assert settings.severe_weather_override is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_priority_settings.py -v`
Expected: FAIL with "AttributeError: 'AppSettings' object has no attribute 'verbosity_level'"

**Step 3: Write minimal implementation**

Add to `src/accessiweather/models/config.py` AppSettings class (after line 82):

```python
    # Priority ordering settings
    verbosity_level: str = "standard"  # "minimal", "standard", "detailed"
    category_order: list[str] = field(
        default_factory=lambda: [
            "temperature",
            "precipitation",
            "wind",
            "humidity_pressure",
            "visibility_clouds",
            "uv_index",
        ]
    )
    severe_weather_override: bool = True
```

Update `to_dict()` method to include:
```python
            "verbosity_level": self.verbosity_level,
            "category_order": self.category_order,
            "severe_weather_override": self.severe_weather_override,
```

Update `from_dict()` method to include:
```python
            verbosity_level=data.get("verbosity_level", "standard"),
            category_order=data.get(
                "category_order",
                ["temperature", "precipitation", "wind", "humidity_pressure", "visibility_clouds", "uv_index"],
            ),
            severe_weather_override=cls._as_bool(data.get("severe_weather_override"), True),
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_priority_settings.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/accessiweather/models/config.py tests/test_priority_settings.py
git commit -m "feat: add priority ordering settings to AppSettings"
```

---

## Task 2: Create Priority Engine Module

**Files:**
- Create: `src/accessiweather/display/priority_engine.py`
- Test: `tests/test_priority_engine.py` (new)

**Step 1: Write the failing test**

```python
# tests/test_priority_engine.py
"""Tests for the priority ordering engine."""

import pytest
from accessiweather.display.priority_engine import PriorityEngine, WeatherCategory
from accessiweather.models import WeatherAlert, WeatherAlerts


class TestWeatherCategory:
    """Test WeatherCategory enum."""

    def test_all_categories_defined(self):
        """All expected categories should be defined."""
        expected = [
            "temperature",
            "precipitation",
            "wind",
            "humidity_pressure",
            "visibility_clouds",
            "uv_index",
        ]
        for cat in expected:
            assert hasattr(WeatherCategory, cat.upper())


class TestPriorityEngine:
    """Test PriorityEngine class."""

    def test_default_order_with_no_alerts(self):
        """Without alerts, use default category order."""
        engine = PriorityEngine()
        order = engine.get_category_order(alerts=None)
        assert order[0] == WeatherCategory.TEMPERATURE

    def test_wind_alert_prioritizes_wind(self):
        """Wind warning should move wind category to top."""
        engine = PriorityEngine()
        alert = WeatherAlert(
            title="Wind Advisory",
            description="High winds expected",
            event="Wind Advisory",
            severity="Moderate",
        )
        alerts = WeatherAlerts(alerts=[alert])
        order = engine.get_category_order(alerts=alerts)
        assert order[0] == WeatherCategory.WIND

    def test_heat_alert_prioritizes_temperature_and_uv(self):
        """Heat advisory should prioritize temperature and UV."""
        engine = PriorityEngine()
        alert = WeatherAlert(
            title="Heat Advisory",
            description="Extreme heat expected",
            event="Heat Advisory",
            severity="Severe",
        )
        alerts = WeatherAlerts(alerts=[alert])
        order = engine.get_category_order(alerts=alerts)
        assert order[0] == WeatherCategory.TEMPERATURE
        assert WeatherCategory.UV_INDEX in order[:3]

    def test_flood_alert_prioritizes_precipitation(self):
        """Flood watch should move precipitation to top."""
        engine = PriorityEngine()
        alert = WeatherAlert(
            title="Flash Flood Watch",
            description="Flooding possible",
            event="Flash Flood Watch",
            severity="Severe",
        )
        alerts = WeatherAlerts(alerts=[alert])
        order = engine.get_category_order(alerts=alerts)
        assert order[0] == WeatherCategory.PRECIPITATION

    def test_winter_alert_prioritizes_precipitation_and_temperature(self):
        """Winter storm should prioritize precipitation and temperature."""
        engine = PriorityEngine()
        alert = WeatherAlert(
            title="Winter Storm Warning",
            description="Heavy snow expected",
            event="Winter Storm Warning",
            severity="Severe",
        )
        alerts = WeatherAlerts(alerts=[alert])
        order = engine.get_category_order(alerts=alerts)
        assert order[0] == WeatherCategory.PRECIPITATION
        assert order[1] == WeatherCategory.TEMPERATURE

    def test_custom_order_respected(self):
        """Custom category order should be respected when no alerts."""
        custom_order = ["wind", "temperature", "precipitation"]
        engine = PriorityEngine(category_order=custom_order)
        order = engine.get_category_order(alerts=None)
        assert order[0] == WeatherCategory.WIND
        assert order[1] == WeatherCategory.TEMPERATURE

    def test_override_disabled_uses_user_order(self):
        """When override is disabled, always use user's order."""
        custom_order = ["wind", "temperature"]
        engine = PriorityEngine(
            category_order=custom_order,
            severe_weather_override=False,
        )
        alert = WeatherAlert(
            title="Heat Advisory",
            description="Heat",
            event="Heat Advisory",
            severity="Severe",
        )
        alerts = WeatherAlerts(alerts=[alert])
        order = engine.get_category_order(alerts=alerts)
        assert order[0] == WeatherCategory.WIND  # User order respected

    def test_verbosity_minimal_fields(self):
        """Minimal verbosity should return limited fields."""
        engine = PriorityEngine(verbosity_level="minimal")
        fields = engine.get_fields_for_category(WeatherCategory.TEMPERATURE)
        assert "temperature" in fields
        assert "feels_like" not in fields

    def test_verbosity_standard_fields(self):
        """Standard verbosity should return normal fields."""
        engine = PriorityEngine(verbosity_level="standard")
        fields = engine.get_fields_for_category(WeatherCategory.TEMPERATURE)
        assert "temperature" in fields
        assert "feels_like" in fields

    def test_verbosity_detailed_fields(self):
        """Detailed verbosity should return all fields."""
        engine = PriorityEngine(verbosity_level="detailed")
        fields = engine.get_fields_for_category(WeatherCategory.TEMPERATURE)
        assert "temperature" in fields
        assert "feels_like" in fields
        assert "dewpoint" in fields
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_priority_engine.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'accessiweather.display.priority_engine'"

**Step 3: Write minimal implementation**

```python
# src/accessiweather/display/priority_engine.py
"""Priority ordering engine for weather information display."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import WeatherAlerts

# Alert event keywords mapped to categories they affect
ALERT_CATEGORY_MAP = {
    # Heat-related
    "heat": ["temperature", "uv_index"],
    "excessive heat": ["temperature", "uv_index"],
    # Wind-related
    "wind": ["wind"],
    "high wind": ["wind"],
    "gale": ["wind"],
    "hurricane": ["wind", "precipitation"],
    "tropical storm": ["wind", "precipitation"],
    "tornado": ["wind"],
    # Precipitation/flood-related
    "flood": ["precipitation"],
    "flash flood": ["precipitation"],
    "rain": ["precipitation"],
    "thunderstorm": ["precipitation", "wind"],
    "severe thunderstorm": ["precipitation", "wind"],
    # Winter-related
    "winter storm": ["precipitation", "temperature"],
    "winter weather": ["precipitation", "temperature"],
    "blizzard": ["precipitation", "temperature", "wind"],
    "ice storm": ["precipitation", "temperature"],
    "freeze": ["temperature"],
    "frost": ["temperature"],
    "cold": ["temperature"],
    "snow": ["precipitation", "temperature"],
    # Visibility-related
    "fog": ["visibility_clouds"],
    "dense fog": ["visibility_clouds"],
    "smoke": ["visibility_clouds"],
}

# Fields per category per verbosity level
CATEGORY_FIELDS = {
    "temperature": {
        "minimal": ["temperature"],
        "standard": ["temperature", "feels_like"],
        "detailed": ["temperature", "feels_like", "dewpoint", "heat_index", "wind_chill"],
    },
    "precipitation": {
        "minimal": ["precipitation_chance"],
        "standard": ["precipitation_chance", "precipitation_amount"],
        "detailed": ["precipitation_chance", "precipitation_amount", "precipitation_type", "snowfall"],
    },
    "wind": {
        "minimal": ["wind_speed"],
        "standard": ["wind_speed", "wind_direction"],
        "detailed": ["wind_speed", "wind_direction", "wind_gusts"],
    },
    "humidity_pressure": {
        "minimal": ["humidity"],
        "standard": ["humidity", "pressure"],
        "detailed": ["humidity", "pressure", "pressure_trend"],
    },
    "visibility_clouds": {
        "minimal": [],
        "standard": ["visibility"],
        "detailed": ["visibility", "cloud_cover"],
    },
    "uv_index": {
        "minimal": [],
        "standard": ["uv_index"],
        "detailed": ["uv_index"],
    },
}


class WeatherCategory(Enum):
    """Weather information categories for priority ordering."""

    TEMPERATURE = "temperature"
    PRECIPITATION = "precipitation"
    WIND = "wind"
    HUMIDITY_PRESSURE = "humidity_pressure"
    VISIBILITY_CLOUDS = "visibility_clouds"
    UV_INDEX = "uv_index"

    @classmethod
    def from_string(cls, value: str) -> "WeatherCategory":
        """Convert string to WeatherCategory."""
        return cls(value.lower())


class PriorityEngine:
    """Determines display order and field selection for weather information."""

    DEFAULT_ORDER = [
        "temperature",
        "precipitation",
        "wind",
        "humidity_pressure",
        "visibility_clouds",
        "uv_index",
    ]

    def __init__(
        self,
        verbosity_level: str = "standard",
        category_order: list[str] | None = None,
        severe_weather_override: bool = True,
    ):
        """Initialize the priority engine with user preferences."""
        self.verbosity_level = verbosity_level
        self.category_order = category_order or self.DEFAULT_ORDER.copy()
        self.severe_weather_override = severe_weather_override

    def get_category_order(
        self,
        alerts: "WeatherAlerts | None" = None,
    ) -> list[WeatherCategory]:
        """Get the ordered list of categories based on alerts and preferences."""
        # Start with user's preferred order
        base_order = [WeatherCategory.from_string(cat) for cat in self.category_order]

        # If no alerts or override disabled, return user order
        if not alerts or not self.severe_weather_override:
            return self._ensure_all_categories(base_order)

        # Check for active alerts and adjust order
        active_alerts = alerts.get_active_alerts()
        if not active_alerts:
            return self._ensure_all_categories(base_order)

        # Find categories to prioritize based on alert events
        priority_categories: list[str] = []
        for alert in active_alerts:
            event = (alert.event or alert.title or "").lower()
            for keyword, categories in ALERT_CATEGORY_MAP.items():
                if keyword in event:
                    for cat in categories:
                        if cat not in priority_categories:
                            priority_categories.append(cat)

        if not priority_categories:
            return self._ensure_all_categories(base_order)

        # Build new order: priority categories first, then remaining in user order
        new_order: list[WeatherCategory] = []
        for cat_str in priority_categories:
            cat = WeatherCategory.from_string(cat_str)
            if cat not in new_order:
                new_order.append(cat)

        for cat in base_order:
            if cat not in new_order:
                new_order.append(cat)

        return self._ensure_all_categories(new_order)

    def _ensure_all_categories(
        self, order: list[WeatherCategory]
    ) -> list[WeatherCategory]:
        """Ensure all categories are present in the order."""
        all_cats = set(WeatherCategory)
        present = set(order)
        missing = all_cats - present
        return order + list(missing)

    def get_fields_for_category(self, category: WeatherCategory) -> list[str]:
        """Get the fields to display for a category based on verbosity."""
        cat_fields = CATEGORY_FIELDS.get(category.value, {})
        return cat_fields.get(self.verbosity_level, cat_fields.get("standard", []))

    def should_include_field(self, category: WeatherCategory, field: str) -> bool:
        """Check if a field should be included based on verbosity."""
        fields = self.get_fields_for_category(category)
        return field in fields
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_priority_engine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/accessiweather/display/priority_engine.py tests/test_priority_engine.py
git commit -m "feat: add PriorityEngine for category ordering and verbosity"
```

---

## Task 3: Update Current Conditions Presentation to Use Priority Engine

**Files:**
- Modify: `src/accessiweather/display/presentation/current_conditions.py`
- Test: `tests/test_current_conditions_priority.py` (new)

**Step 1: Write the failing test**

```python
# tests/test_current_conditions_priority.py
"""Tests for priority ordering in current conditions presentation."""

import pytest
from accessiweather.display.presentation.current_conditions import build_current_conditions
from accessiweather.display.priority_engine import PriorityEngine
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Location,
    WeatherAlert,
    WeatherAlerts,
)
from accessiweather.utils import TemperatureUnit


class TestCurrentConditionsPriority:
    """Test priority ordering in current conditions."""

    @pytest.fixture
    def location(self):
        return Location(name="Test City", latitude=40.0, longitude=-75.0)

    @pytest.fixture
    def current_conditions(self):
        return CurrentConditions(
            temperature_f=75.0,
            temperature_c=24.0,
            feels_like_f=78.0,
            humidity=65,
            wind_speed=15,
            wind_direction="NW",
            pressure_in=30.1,
            visibility_mi=10.0,
            uv_index=6,
            condition="Partly Cloudy",
        )

    def test_minimal_verbosity_reduces_metrics(self, location, current_conditions):
        """Minimal verbosity should show fewer metrics."""
        settings = AppSettings(verbosity_level="minimal")
        result = build_current_conditions(
            current_conditions,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        # Should have temperature but not feels_like as separate metric
        metric_labels = [m.label for m in result.metrics]
        assert "Temperature" in metric_labels
        # In minimal mode, feels_like should not appear as separate metric
        assert len(result.metrics) < 10  # Fewer than detailed

    def test_detailed_verbosity_includes_more_metrics(self, location, current_conditions):
        """Detailed verbosity should include all available metrics."""
        settings = AppSettings(verbosity_level="detailed")
        result = build_current_conditions(
            current_conditions,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        metric_labels = [m.label for m in result.metrics]
        assert "Temperature" in metric_labels
        assert len(result.metrics) > 5  # More comprehensive

    def test_wind_alert_reorders_metrics(self, location, current_conditions):
        """Wind alert should put wind info near the top."""
        settings = AppSettings(severe_weather_override=True)
        alerts = WeatherAlerts(alerts=[
            WeatherAlert(
                title="High Wind Warning",
                description="Dangerous winds",
                event="High Wind Warning",
                severity="Severe",
            )
        ])
        result = build_current_conditions(
            current_conditions,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
            alerts=alerts,
        )
        metric_labels = [m.label for m in result.metrics]
        # Wind should appear in first 3 metrics
        wind_idx = next(i for i, l in enumerate(metric_labels) if "Wind" in l)
        assert wind_idx < 3

    def test_custom_category_order_respected(self, location, current_conditions):
        """Custom category order should affect metric ordering."""
        settings = AppSettings(
            category_order=["wind", "temperature", "precipitation"]
        )
        result = build_current_conditions(
            current_conditions,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        metric_labels = [m.label for m in result.metrics]
        # Wind should come before temperature
        wind_idx = next((i for i, l in enumerate(metric_labels) if "Wind" in l), 999)
        temp_idx = next((i for i, l in enumerate(metric_labels) if "Temperature" in l), 999)
        assert wind_idx < temp_idx
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_current_conditions_priority.py -v`
Expected: FAIL with assertion errors (metrics not reordered)

**Step 3: Write minimal implementation**

Modify `src/accessiweather/display/presentation/current_conditions.py`:

Add import at top:
```python
from ..priority_engine import PriorityEngine, WeatherCategory
from ...models import WeatherAlerts
```

Modify `build_current_conditions` function signature to accept alerts:
```python
def build_current_conditions(
    current: CurrentConditions,
    location: Location,
    unit_pref: TemperatureUnit,
    *,
    settings: AppSettings | None = None,
    environmental: EnvironmentalConditions | None = None,
    trends: Iterable[TrendInsight] | None = None,
    hourly_forecast: HourlyForecast | None = None,
    air_quality: AirQualityPresentation | None = None,
    alerts: WeatherAlerts | None = None,  # NEW PARAMETER
) -> CurrentConditionsPresentation:
```

Add priority engine initialization after extracting settings:
```python
    # Priority engine setup
    verbosity_level = getattr(settings, "verbosity_level", "standard") if settings else "standard"
    category_order = getattr(settings, "category_order", None) if settings else None
    severe_weather_override = getattr(settings, "severe_weather_override", True) if settings else True

    priority_engine = PriorityEngine(
        verbosity_level=verbosity_level,
        category_order=category_order,
        severe_weather_override=severe_weather_override,
    )
    ordered_categories = priority_engine.get_category_order(alerts=alerts)
```

Modify metrics building to use category ordering:
```python
    # Build metrics by category in priority order
    metrics: list[Metric] = []
    category_metrics = {
        WeatherCategory.TEMPERATURE: _build_basic_metrics(...),  # temperature subset
        WeatherCategory.WIND: [...],  # wind metrics
        # etc.
    }

    for category in ordered_categories:
        if category in category_metrics:
            for metric in category_metrics[category]:
                if priority_engine.should_include_field(category, metric.label.lower()):
                    metrics.append(metric)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_current_conditions_priority.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/accessiweather/display/presentation/current_conditions.py tests/test_current_conditions_priority.py
git commit -m "feat: integrate PriorityEngine into current conditions presentation"
```

---

## Task 4: Update Forecast Presentation to Use Priority Engine

**Files:**
- Modify: `src/accessiweather/display/presentation/forecast.py`
- Test: `tests/test_forecast_priority.py` (new)

**Step 1: Write the failing test**

```python
# tests/test_forecast_priority.py
"""Tests for priority ordering in forecast presentation."""

import pytest
from datetime import datetime, UTC
from accessiweather.display.presentation.forecast import build_forecast, build_hourly_summary
from accessiweather.models import (
    AppSettings,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
)
from accessiweather.utils import TemperatureUnit


class TestForecastPriority:
    """Test priority ordering in forecast presentation."""

    @pytest.fixture
    def location(self):
        return Location(name="Test City", latitude=40.0, longitude=-75.0)

    @pytest.fixture
    def forecast(self):
        return Forecast(
            periods=[
                ForecastPeriod(
                    name="Today",
                    temperature=75,
                    temperature_unit="F",
                    short_forecast="Sunny",
                    wind_speed="10 mph",
                    wind_direction="NW",
                    precipitation_probability=20,
                    uv_index=6,
                )
            ],
            generated_at=datetime.now(UTC),
        )

    @pytest.fixture
    def hourly_forecast(self):
        return HourlyForecast(
            periods=[
                HourlyForecastPeriod(
                    start_time=datetime.now(UTC),
                    temperature_f=75.0,
                    short_forecast="Sunny",
                    wind_speed=10,
                    precipitation_probability=20,
                )
            ]
        )

    def test_minimal_verbosity_forecast(self, location, forecast, hourly_forecast):
        """Minimal verbosity should reduce forecast detail."""
        settings = AppSettings(verbosity_level="minimal")
        result = build_forecast(
            forecast,
            hourly_forecast,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        # Should have basic info
        assert result.periods[0].temperature is not None
        # Fallback text should be shorter
        assert len(result.fallback_text) < 500

    def test_detailed_verbosity_forecast(self, location, forecast, hourly_forecast):
        """Detailed verbosity should include all forecast info."""
        settings = AppSettings(verbosity_level="detailed")
        result = build_forecast(
            forecast,
            hourly_forecast,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        # Should have all available fields
        assert result.periods[0].temperature is not None
        assert result.periods[0].wind is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_forecast_priority.py -v`
Expected: FAIL (if verbosity not yet affecting output)

**Step 3: Write minimal implementation**

Modify `build_forecast` to respect verbosity settings by filtering which fields are included in the period presentation and fallback text.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_forecast_priority.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/accessiweather/display/presentation/forecast.py tests/test_forecast_priority.py
git commit -m "feat: integrate PriorityEngine into forecast presentation"
```

---

## Task 5: Update WeatherPresenter to Pass Alerts for Priority

**Files:**
- Modify: `src/accessiweather/display/weather_presenter.py`
- Test: `tests/test_weather_presenter_priority.py` (new)

**Step 1: Write the failing test**

```python
# tests/test_weather_presenter_priority.py
"""Tests for priority ordering in WeatherPresenter."""

import pytest
from accessiweather.display.weather_presenter import WeatherPresenter
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Location,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)


class TestWeatherPresenterPriority:
    """Test WeatherPresenter uses priority ordering."""

    def test_presenter_passes_alerts_to_current_conditions(self):
        """WeatherPresenter should pass alerts for priority calculation."""
        settings = AppSettings(severe_weather_override=True)
        presenter = WeatherPresenter(settings)

        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed=15,
            condition="Windy",
        )
        alerts = WeatherAlerts(alerts=[
            WeatherAlert(
                title="High Wind Warning",
                description="Dangerous winds",
                event="High Wind Warning",
                severity="Severe",
            )
        ])

        weather_data = WeatherData(
            location=location,
            current=current,
            alerts=alerts,
        )

        result = presenter.present(weather_data)
        # Wind should be prioritized in the metrics
        metric_labels = [m.label for m in result.current_conditions.metrics]
        wind_idx = next((i for i, l in enumerate(metric_labels) if "Wind" in l), 999)
        assert wind_idx < 3  # Wind should be near top
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_weather_presenter_priority.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Modify `WeatherPresenter._build_current_conditions` to pass alerts:
```python
def _build_current_conditions(self, ...):
    return build_current_conditions(
        ...,
        alerts=weather_data.alerts,  # Pass alerts for priority
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_weather_presenter_priority.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/accessiweather/display/weather_presenter.py tests/test_weather_presenter_priority.py
git commit -m "feat: WeatherPresenter passes alerts for priority ordering"
```

---

## Task 6: Update TaskbarIconUpdater to Use Priority Ordering

**Files:**
- Modify: `src/accessiweather/taskbar_icon_updater.py`
- Test: `tests/test_taskbar_priority.py` (new)

**Step 1: Write the failing test**

```python
# tests/test_taskbar_priority.py
"""Tests for priority ordering in taskbar tooltip."""

import pytest
from accessiweather.taskbar_icon_updater import TaskbarIconUpdater
from accessiweather.models import CurrentConditions, Location, WeatherData


class TestTaskbarPriority:
    """Test taskbar tooltip uses priority ordering."""

    def test_tooltip_respects_verbosity_minimal(self):
        """Minimal verbosity should produce short tooltip."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="minimal",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed=15,
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # Minimal should be short
        assert len(tooltip) < 50

    def test_tooltip_respects_verbosity_detailed(self):
        """Detailed verbosity should include more info."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="detailed",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            feels_like_f=78.0,
            humidity=65,
            wind_speed=15,
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # Detailed should include more info
        assert "75" in tooltip  # Temperature
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_taskbar_priority.py -v`
Expected: FAIL with "unexpected keyword argument 'verbosity_level'"

**Step 3: Write minimal implementation**

Add `verbosity_level` parameter to `TaskbarIconUpdater.__init__` and `update_settings`.
Modify `format_tooltip` to adjust content based on verbosity.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_taskbar_priority.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/accessiweather/taskbar_icon_updater.py tests/test_taskbar_priority.py
git commit -m "feat: TaskbarIconUpdater supports verbosity level"
```

---

## Task 7: Add Display Priority Tab to Settings Dialog

**Files:**
- Modify: `src/accessiweather/dialogs/settings_tabs.py`
- Test: `tests/test_settings_priority_tab.py` (new)

**Step 1: Write the failing test**

```python
# tests/test_settings_priority_tab.py
"""Tests for Display Priority settings tab."""

import pytest
from unittest.mock import MagicMock
import toga


class TestDisplayPriorityTab:
    """Test Display Priority tab UI components."""

    def test_verbosity_dropdown_exists(self):
        """Settings dialog should have verbosity dropdown."""
        from accessiweather.dialogs.settings_tabs import create_display_priority_tab

        dialog = MagicMock()
        dialog.current_settings = MagicMock()
        dialog.current_settings.verbosity_level = "standard"
        dialog.current_settings.category_order = ["temperature", "wind"]
        dialog.current_settings.severe_weather_override = True
        dialog.option_container = MagicMock()
        dialog.option_container.content = []

        create_display_priority_tab(dialog)

        assert hasattr(dialog, "verbosity_selection")
        assert hasattr(dialog, "category_order_list")
        assert hasattr(dialog, "severe_weather_override_switch")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings_priority_tab.py -v`
Expected: FAIL with "cannot import name 'create_display_priority_tab'"

**Step 3: Write minimal implementation**

Add new function to `settings_tabs.py`:

```python
def create_display_priority_tab(dialog):
    """Build the Display Priority tab for information ordering settings."""
    priority_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
    dialog.display_priority_tab = priority_box

    # Verbosity Level
    priority_box.add(
        toga.Label(
            "Information Verbosity:",
            style=Pack(margin_bottom=8, font_weight="bold"),
        )
    )
    priority_box.add(
        toga.Label(
            "Control how much detail is shown in weather displays:",
            style=Pack(margin_bottom=10, font_size=9),
        )
    )

    verbosity_options = [
        "Minimal (essentials only)",
        "Standard (recommended)",
        "Detailed (all available info)",
    ]
    dialog.verbosity_display_to_value = {
        "Minimal (essentials only)": "minimal",
        "Standard (recommended)": "standard",
        "Detailed (all available info)": "detailed",
    }
    dialog.verbosity_value_to_display = {
        v: k for k, v in dialog.verbosity_display_to_value.items()
    }

    dialog.verbosity_selection = toga.Selection(
        items=verbosity_options,
        style=Pack(margin_bottom=15),
        id="verbosity_selection",
    )
    dialog.verbosity_selection.aria_label = "Verbosity level selection"
    dialog.verbosity_selection.aria_description = (
        "Choose how much weather information to display. "
        "Minimal shows only essentials, Detailed shows everything available."
    )

    current_verbosity = getattr(dialog.current_settings, "verbosity_level", "standard")
    dialog.verbosity_selection.value = dialog.verbosity_value_to_display.get(
        current_verbosity, "Standard (recommended)"
    )
    priority_box.add(dialog.verbosity_selection)

    # Category Order
    priority_box.add(
        toga.Label(
            "Category Order:",
            style=Pack(margin_top=15, margin_bottom=8, font_weight="bold"),
        )
    )
    priority_box.add(
        toga.Label(
            "Drag categories to reorder, or use Up/Down buttons:",
            style=Pack(margin_bottom=10, font_size=9),
        )
    )

    # Category list with reorder buttons
    order_row = toga.Box(style=Pack(direction=ROW, margin_bottom=10))

    current_order = getattr(
        dialog.current_settings,
        "category_order",
        ["temperature", "precipitation", "wind", "humidity_pressure", "visibility_clouds", "uv_index"],
    )

    category_display_names = {
        "temperature": "Temperature",
        "precipitation": "Precipitation",
        "wind": "Wind",
        "humidity_pressure": "Humidity & Pressure",
        "visibility_clouds": "Visibility & Clouds",
        "uv_index": "UV Index",
    }

    dialog.category_order_list = toga.Selection(
        items=[category_display_names.get(c, c) for c in current_order],
        style=Pack(flex=1, margin_right=10),
        id="category_order_list",
    )
    dialog.category_order_list.aria_label = "Category order"
    dialog.category_order_list.aria_description = (
        "Select a category and use Up/Down buttons to change its position."
    )
    order_row.add(dialog.category_order_list)

    button_col = toga.Box(style=Pack(direction=COLUMN))
    dialog.category_up_button = toga.Button(
        "Up",
        on_press=dialog._on_category_up,
        style=Pack(margin_bottom=5, width=60),
    )
    dialog.category_down_button = toga.Button(
        "Down",
        on_press=dialog._on_category_down,
        style=Pack(width=60),
    )
    button_col.add(dialog.category_up_button)
    button_col.add(dialog.category_down_button)
    order_row.add(button_col)

    priority_box.add(order_row)

    dialog.reset_order_button = toga.Button(
        "Reset to Default Order",
        on_press=dialog._on_reset_category_order,
        style=Pack(margin_bottom=15, width=180),
    )
    priority_box.add(dialog.reset_order_button)

    # Severe Weather Override
    priority_box.add(
        toga.Label(
            "Severe Weather Behavior:",
            style=Pack(margin_top=15, margin_bottom=8, font_weight="bold"),
        )
    )

    dialog.severe_weather_override_switch = toga.Switch(
        "Automatically prioritize severe weather info",
        value=getattr(dialog.current_settings, "severe_weather_override", True),
        style=Pack(margin_bottom=10),
        id="severe_weather_override_switch",
    )
    dialog.severe_weather_override_switch.aria_label = "Severe weather override toggle"
    dialog.severe_weather_override_switch.aria_description = (
        "When enabled, relevant weather categories are automatically moved to the top "
        "during active severe weather alerts."
    )
    priority_box.add(dialog.severe_weather_override_switch)

    priority_box.add(
        toga.Label(
            "Example: During a Wind Warning, wind info appears first.",
            style=Pack(margin_bottom=10, font_size=9, font_style="italic"),
        )
    )

    dialog.option_container.content.append("Display Priority", priority_box)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_settings_priority_tab.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/accessiweather/dialogs/settings_tabs.py tests/test_settings_priority_tab.py
git commit -m "feat: add Display Priority tab to settings dialog"
```

---

## Task 8: Wire Up Settings Dialog to Save Priority Settings

**Files:**
- Modify: `src/accessiweather/dialogs/settings_dialog.py`
- Modify: `src/accessiweather/dialogs/settings_handlers.py`

**Step 1: Write the failing test**

```python
# tests/test_settings_save_priority.py
"""Tests for saving priority settings."""

import pytest
from unittest.mock import MagicMock


class TestSavePrioritySettings:
    """Test saving priority settings from dialog."""

    def test_save_collects_priority_settings(self):
        """Save should collect verbosity, order, and override settings."""
        from accessiweather.dialogs.settings_handlers import collect_settings_from_dialog

        dialog = MagicMock()
        dialog.verbosity_selection = MagicMock()
        dialog.verbosity_selection.value = "Standard (recommended)"
        dialog.verbosity_display_to_value = {"Standard (recommended)": "standard"}

        dialog.category_order_list = MagicMock()
        dialog.category_order_list.items = ["Temperature", "Wind"]
        dialog.category_display_to_value = {
            "Temperature": "temperature",
            "Wind": "wind",
        }

        dialog.severe_weather_override_switch = MagicMock()
        dialog.severe_weather_override_switch.value = True

        settings = collect_settings_from_dialog(dialog)

        assert settings["verbosity_level"] == "standard"
        assert settings["category_order"] == ["temperature", "wind"]
        assert settings["severe_weather_override"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings_save_priority.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Update `settings_handlers.py` to collect priority settings when saving.
Update `settings_dialog.py` to include handlers for category reordering.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_settings_save_priority.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/accessiweather/dialogs/settings_dialog.py src/accessiweather/dialogs/settings_handlers.py tests/test_settings_save_priority.py
git commit -m "feat: wire up priority settings save in dialog"
```

---

## Task 9: Integration Test - Full Priority Flow

**Files:**
- Test: `tests/test_priority_integration.py` (new)

**Step 1: Write the integration test**

```python
# tests/test_priority_integration.py
"""Integration tests for complete priority ordering flow."""

import pytest
from accessiweather.display.weather_presenter import WeatherPresenter
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    Location,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)


class TestPriorityIntegration:
    """Integration tests for priority ordering."""

    def test_full_flow_with_alerts(self):
        """Test complete flow from settings to presentation with alerts."""
        # Setup settings with custom order
        settings = AppSettings(
            verbosity_level="standard",
            category_order=["temperature", "precipitation", "wind"],
            severe_weather_override=True,
        )

        presenter = WeatherPresenter(settings)

        # Create weather data with wind alert
        location = Location(name="Test City", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed=45,
            wind_direction="NW",
            condition="Very Windy",
        )
        alerts = WeatherAlerts(alerts=[
            WeatherAlert(
                title="High Wind Warning",
                description="Dangerous winds up to 60 mph",
                event="High Wind Warning",
                severity="Severe",
            )
        ])

        weather_data = WeatherData(
            location=location,
            current=current,
            alerts=alerts,
        )

        # Present the data
        result = presenter.present(weather_data)

        # Verify wind is prioritized
        metrics = result.current_conditions.metrics
        metric_labels = [m.label for m in metrics]
        wind_idx = next((i for i, l in enumerate(metric_labels) if "Wind" in l), 999)

        # Wind should be in top 3 due to alert override
        assert wind_idx < 3

    def test_full_flow_no_alerts_uses_custom_order(self):
        """Without alerts, custom order should be respected."""
        settings = AppSettings(
            verbosity_level="standard",
            category_order=["wind", "temperature", "precipitation"],
            severe_weather_override=True,
        )

        presenter = WeatherPresenter(settings)

        location = Location(name="Test City", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed=10,
            condition="Clear",
        )

        weather_data = WeatherData(
            location=location,
            current=current,
        )

        result = presenter.present(weather_data)

        # Wind should come before temperature per custom order
        metrics = result.current_conditions.metrics
        metric_labels = [m.label for m in metrics]
        wind_idx = next((i for i, l in enumerate(metric_labels) if "Wind" in l), 999)
        temp_idx = next((i for i, l in enumerate(metric_labels) if "Temperature" in l), 999)

        assert wind_idx < temp_idx

    def test_minimal_verbosity_reduces_output(self):
        """Minimal verbosity should produce less detailed output."""
        minimal_settings = AppSettings(verbosity_level="minimal")
        detailed_settings = AppSettings(verbosity_level="detailed")

        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            feels_like_f=78.0,
            humidity=65,
            wind_speed=10,
            pressure_in=30.1,
            visibility_mi=10.0,
            uv_index=6,
            condition="Clear",
        )

        weather_data = WeatherData(location=location, current=current)

        minimal_result = WeatherPresenter(minimal_settings).present(weather_data)
        detailed_result = WeatherPresenter(detailed_settings).present(weather_data)

        # Minimal should have fewer metrics
        assert len(minimal_result.current_conditions.metrics) < len(detailed_result.current_conditions.metrics)
```

**Step 2: Run integration test**

Run: `pytest tests/test_priority_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_priority_integration.py
git commit -m "test: add integration tests for priority ordering"
```

---

## Task 10: Update Main App to Initialize Priority Settings

**Files:**
- Modify: `src/accessiweather/app.py` (or main app initialization)

**Step 1: Verify settings are loaded and passed correctly**

Ensure the main application passes the new settings fields to the WeatherPresenter and TaskbarIconUpdater.

**Step 2: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS

**Step 3: Manual testing**

1. Launch app
2. Open Settings > Display Priority
3. Change verbosity to Minimal
4. Verify weather display shows less info
5. Reorder categories
6. Verify order changes in display
7. Test with active alert simulation

**Step 4: Final commit**

```bash
git add .
git commit -m "feat: complete information priority ordering implementation"
```

---

## Summary

This plan implements the Information Priority Ordering system in 10 tasks:

1. **Settings Model** - Add new fields to AppSettings
2. **Priority Engine** - Create core ordering/verbosity logic
3. **Current Conditions** - Integrate priority into current conditions
4. **Forecast** - Integrate priority into forecast display
5. **WeatherPresenter** - Pass alerts for context-aware ordering
6. **TaskbarIconUpdater** - Support verbosity in tooltips
7. **Settings Tab** - UI for configuring priority settings
8. **Settings Handlers** - Wire up save/load
9. **Integration Tests** - End-to-end verification
10. **App Integration** - Final wiring and manual testing

Each task follows TDD: write failing test, implement, verify, commit.
