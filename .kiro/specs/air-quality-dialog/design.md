# Design Document: Air Quality Dialog

## Overview

This feature adds a dedicated Air Quality Dialog accessible from the View menu, providing comprehensive air quality information. The dialog presents current AQI data, hourly forecasts with trend analysis, and detailed pollutant breakdowns. Additionally, this feature consolidates the air quality display in the main window's Current Conditions section to eliminate duplication.

### Completed Implementation (from previous work)

The following components are already implemented:
- `HourlyAirQuality` model with timestamp, AQI, category, and pollutant measurements
- `fetch_hourly_air_quality()` API client method fetching up to 120 hours from Open-Meteo
- `format_hourly_air_quality()` presentation function with trend analysis
- Basic hourly forecast display in Current Conditions section
- Comprehensive test coverage (19 tests)

### New Implementation Required

- Air Quality Dialog UI component
- View menu integration
- Dialog-specific presentation formatting
- Pollutant details section
- Fix duplicate air quality display in Current Conditions

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        View Menu                                 │
│  ┌─────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │   Refresh   │  │ Weather History  │  │   Air Quality     │  │
│  └─────────────┘  └──────────────────┘  └─────────┬─────────┘  │
└───────────────────────────────────────────────────┼─────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Air Quality Dialog                            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Summary Section                                              ││
│  │ - Current AQI & Category                                     ││
│  │ - Dominant Pollutant                                         ││
│  │ - Health Guidance                                            ││
│  │ - Last Updated                                               ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Hourly Forecast Section                                      ││
│  │ - Trend (Improving/Worsening/Stable)                         ││
│  │ - Peak AQI Time                                              ││
│  │ - Best Time for Outdoor Activities                           ││
│  │ - Hourly breakdown (up to 24 hours)                          ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Pollutant Details Section                                    ││
│  │ - PM2.5, PM10, Ozone, NO2, SO2, CO values                    ││
│  │ - Dominant pollutant indicator                               ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      [Close]                                 ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. AirQualityDialog (New)

Location: `src/accessiweather/dialogs/air_quality_dialog.py`

```python
class AirQualityDialog:
    """Modal dialog for comprehensive air quality information."""

    def __init__(
        self,
        app: AccessiWeatherApp,
        location_name: str,
        environmental: EnvironmentalConditions,
        settings: AppSettings | None = None,
    ) -> None:
        """Initialize the air quality dialog."""
        ...

    async def show_and_focus(self) -> None:
        """Display the dialog and set focus for accessibility."""
        ...

    def _build_summary_section(self) -> toga.Box:
        """Build the current AQI summary section."""
        ...

    def _build_hourly_section(self) -> toga.Box:
        """Build the hourly forecast section."""
        ...

    def _build_pollutant_section(self) -> toga.Box:
        """Build the pollutant details section."""
        ...

    def _on_close(self, widget: toga.Widget) -> None:
        """Handle dialog close."""
        ...
```

### 2. Dialog Presentation Functions (New)

Location: `src/accessiweather/display/presentation/environmental.py`

```python
def format_air_quality_summary(
    environmental: EnvironmentalConditions,
    settings: AppSettings | None = None,
) -> str:
    """Format current air quality as a summary string for the dialog."""
    ...

def format_pollutant_details(
    hourly_data: list[HourlyAirQuality],
) -> str:
    """Format pollutant measurements into readable text."""
    ...

def format_air_quality_brief(
    environmental: EnvironmentalConditions,
    settings: AppSettings | None = None,
) -> str:
    """Format a brief air quality summary for Current Conditions section."""
    ...
```

### 3. Event Handler (New)

Location: `src/accessiweather/handlers/weather_handlers.py`

```python
async def on_view_air_quality(app: AccessiWeatherApp, widget: toga.Widget) -> None:
    """Show air quality dialog."""
    ...
```

### 4. Menu Integration (Modification)

Location: `src/accessiweather/ui_builder.py`

Add new command to `create_menu_system()`:
```python
air_quality_cmd = toga.Command(
    lambda widget: asyncio.create_task(event_handlers.on_view_air_quality(app, widget)),
    text="Air Quality…",
    tooltip="View detailed air quality information",
    group=toga.Group.VIEW,
)
```

## Data Models

### Existing Models (No Changes Required)

```python
@dataclass
class HourlyAirQuality:
    """Single hour of air quality forecast data."""
    timestamp: datetime
    aqi: int
    category: str
    pm2_5: float | None = None
    pm10: float | None = None
    ozone: float | None = None
    nitrogen_dioxide: float | None = None
    sulphur_dioxide: float | None = None
    carbon_monoxide: float | None = None

@dataclass
class EnvironmentalConditions:
    """Air quality and pollen conditions."""
    air_quality_index: float | None = None
    air_quality_category: str | None = None
    air_quality_pollutant: str | None = None
    hourly_air_quality: list[HourlyAirQuality] = field(default_factory=list)
    # ... other fields
```

### Presentation Data Classes

```python
@dataclass
class AirQualityDialogData:
    """Data structure for air quality dialog content."""
    location_name: str
    summary_text: str
    hourly_text: str
    pollutant_text: str
    has_data: bool
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Location name appears in dialog

*For any* location name provided to the dialog, the dialog title or header SHALL contain that location name.

**Validates: Requirements 1.3**

### Property 2: Summary contains AQI and category

*For any* EnvironmentalConditions with a non-null air_quality_index and air_quality_category, the formatted summary SHALL contain both the AQI value and the category text.

**Validates: Requirements 2.1**

### Property 3: Dominant pollutant appears when available

*For any* EnvironmentalConditions with a non-null air_quality_pollutant, the formatted summary SHALL contain the human-readable pollutant name.

**Validates: Requirements 2.2**

### Property 4: Health guidance matches AQI category

*For any* AQI category from the set {Good, Moderate, Unhealthy for Sensitive Groups, Unhealthy, Very Unhealthy, Hazardous}, the formatted summary SHALL contain the corresponding health guidance text.

**Validates: Requirements 2.3**

### Property 5: Hourly forecast limited to 24 hours

*For any* list of HourlyAirQuality entries with length > 24, the formatted hourly output SHALL contain at most 24 hour entries.

**Validates: Requirements 3.1**

### Property 6: Trend correctly identifies direction

*For any* sequence of at least 3 HourlyAirQuality entries, the trend SHALL be:
- "Worsening" if AQI increases by more than 20 from first to third entry
- "Improving" if AQI decreases by more than 20 from first to third entry
- "Stable" otherwise

**Validates: Requirements 3.3**

### Property 7: Peak AQI is maximum value

*For any* non-empty list of HourlyAirQuality entries, the reported peak AQI SHALL equal the maximum AQI value in the list.

**Validates: Requirements 3.4**

### Property 8: Best time has AQI below threshold

*For any* list of HourlyAirQuality entries where at least one entry has AQI < 100, the reported best time SHALL correspond to an entry with AQI < 100.

**Validates: Requirements 3.5**

### Property 9: Pollutant names are human-readable

*For any* pollutant code in {PM2_5, PM10, O3, NO2, SO2, CO}, the formatted output SHALL use the human-readable name {PM2.5, PM10, Ozone, Nitrogen Dioxide, Sulfur Dioxide, Carbon Monoxide} respectively, and SHALL indicate the dominant pollutant.

**Validates: Requirements 4.2, 4.3**

### Property 10: No duplicate air quality sections

*For any* weather data displayed in Current Conditions, the air quality information SHALL appear in exactly one section (not both "Air quality update" and "Hourly forecast" with overlapping content).

**Validates: Requirements 7.1, 7.3**

### Property 11: Formatting function is deterministic

*For any* EnvironmentalConditions and AppSettings, calling the formatting function twice with identical inputs SHALL produce identical output strings.

**Validates: Requirements 8.1, 8.2**

## Error Handling

### No Location Selected
When the user opens the Air Quality dialog without a location selected:
- Display an informative dialog: "No location selected. Please select a location first."
- Do not attempt to show the Air Quality dialog

### No Air Quality Data Available
When air quality data is unavailable for the current location:
- Display the dialog with a message: "Air quality data is not available for this location."
- Show the Close button to dismiss

### API Errors
When fetching air quality data fails:
- Log the error
- Display cached data if available
- Show appropriate error message if no cached data exists

## Testing Strategy

### Dual Testing Approach

This feature uses both unit tests and property-based tests:
- **Unit tests**: Verify specific examples, edge cases, and UI integration
- **Property-based tests**: Verify universal properties hold across all valid inputs

### Property-Based Testing Framework

Use **Hypothesis** (Python's property-based testing library) for property tests.

Configuration:
- Minimum 100 iterations per property test
- Each test tagged with: `**Feature: air-quality-dialog, Property {number}: {property_text}**`

### Test Files

1. `tests/test_air_quality_dialog.py` - Dialog UI tests
2. `tests/test_air_quality_presentation.py` - Presentation function tests (including property tests)
3. `tests/test_air_quality_integration.py` - Integration tests

### Unit Test Coverage

- Dialog creation and display
- Menu command registration
- Close button functionality
- Escape key handling
- Accessibility attributes (aria_label, aria_description)
- Edge cases (no location, no data)

### Property Test Coverage

Each correctness property (1-11) will have a corresponding property-based test that:
1. Generates random valid inputs using Hypothesis strategies
2. Calls the function under test
3. Asserts the property holds

Example strategy for HourlyAirQuality:
```python
@st.composite
def hourly_air_quality(draw):
    return HourlyAirQuality(
        timestamp=draw(st.datetimes()),
        aqi=draw(st.integers(min_value=0, max_value=500)),
        category=draw(st.sampled_from([
            "Good", "Moderate", "Unhealthy for Sensitive Groups",
            "Unhealthy", "Very Unhealthy", "Hazardous"
        ])),
        pm2_5=draw(st.floats(min_value=0, max_value=500) | st.none()),
        pm10=draw(st.floats(min_value=0, max_value=500) | st.none()),
        ozone=draw(st.floats(min_value=0, max_value=500) | st.none()),
        nitrogen_dioxide=draw(st.floats(min_value=0, max_value=500) | st.none()),
        sulphur_dioxide=draw(st.floats(min_value=0, max_value=500) | st.none()),
        carbon_monoxide=draw(st.floats(min_value=0, max_value=50000) | st.none()),
    )
```
