# Design Document: Seasonal Weather Display Enhancement

**Feature:** Seasonal Weather Display Enhancement
**Branch:** `feat/seasonal-current-conditions`
**Date:** December 7, 2025
**Status:** Draft

---

## Overview

This design document specifies how to integrate seasonal weather data into AccessiWeather's display layer. The core infrastructure (data models, API clients, season detection) is already implemented. This feature focuses on:

1. Ensuring seasonal data flows through to the presentation layer
2. Adding property-based tests for seasonal logic
3. Implementing feels-like temperature selection logic

### Design Goals

1. **Leverage Existing Infrastructure**: Use existing seasonal fields in models and API clients
2. **Minimal Changes**: Extend existing formatters rather than creating new components
3. **Graceful Degradation**: Continue displaying basic weather when seasonal data is unavailable
4. **Testability**: Add property-based tests for seasonal logic

---

## Architecture

### Existing Components (No Changes Needed)

```
┌─────────────────────────────────────────────────────────────┐
│                     AccessiWeather App                       │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Weather Client (Orchestrator)                 │ │
│  │  - Already fetches seasonal data from providers         │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Data Models (Already Have Seasonal Fields)      │ │
│  │  - CurrentConditions: snow_depth, wind_chill, etc.      │ │
│  │  - ForecastPeriod: frost_risk, heat_index_max, etc.     │ │
│  │  - HourlyForecastPeriod: feels_like, visibility, etc.   │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Season Detection (Already Implemented)          │ │
│  │  - Season enum: WINTER, SPRING, SUMMER, FALL            │ │
│  │  - get_season(date, latitude) function                  │ │
│  │  - get_hemisphere(latitude) function                    │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Components to Enhance

```
┌─────────────────────────────────────────────────────────────┐
│         Presentation Layer (ENHANCE)                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │    display/presentation/current_conditions.py           │ │
│  │  - Add seasonal fields to CurrentConditionsPresentation │ │
│  │  - Format snow_depth, wind_chill, frost_risk            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │    display/presentation/formatters.py                   │ │
│  │  - Add format_snow_depth() function                     │ │
│  │  - Add format_frost_risk() function                     │ │
│  │  - Enhance format_temperature_with_feels_like()         │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Components and Interfaces

### 1. Enhanced Formatters

**Location**: `src/accessiweather/display/presentation/formatters.py`

**New Functions**:

```python
def format_snow_depth(
    snow_depth_in: float | None,
    snow_depth_cm: float | None,
    unit_pref: TemperatureUnit,
) -> str | None:
    """
    Format snow depth for display.

    Args:
        snow_depth_in: Snow depth in inches
        snow_depth_cm: Snow depth in centimeters
        unit_pref: Unit preference (imperial/metric/both)

    Returns:
        Formatted string like "6 in" or "15 cm" or None if no data
    """
    pass

def format_frost_risk(frost_risk: str | None) -> str | None:
    """
    Format frost risk level for display.

    Args:
        frost_risk: Risk level ("None", "Low", "Moderate", "High")

    Returns:
        Formatted string or None if no data
    """
    pass

def select_feels_like_temperature(
    current: CurrentConditions,
) -> tuple[float | None, float | None, str | None]:
    """
    Select the appropriate feels-like temperature based on conditions.

    Logic:
    - If temp < 50°F and wind > 3 mph: use wind_chill
    - If temp > 80°F and humidity > 40%: use heat_index
    - Otherwise: use existing feels_like or actual temp

    Args:
        current: Current weather conditions

    Returns:
        Tuple of (feels_like_f, feels_like_c, reason)
        reason is "wind chill", "heat index", or None
    """
    pass
```

### 2. Enhanced Current Conditions Presentation

**Location**: `src/accessiweather/display/presentation/current_conditions.py`

**Changes**:
- Add seasonal fields to `CurrentConditionsPresentation` dataclass
- Include snow_depth, frost_risk in fallback_text when available
- Use `select_feels_like_temperature()` for feels-like display

---

## Data Models

### Existing Seasonal Fields (No Changes)

The following fields already exist in `src/accessiweather/models/weather.py`:

**CurrentConditions**:
- `snow_depth_in`, `snow_depth_cm` - Snow depth
- `wind_chill_f`, `wind_chill_c` - Wind chill
- `heat_index_f`, `heat_index_c` - Heat index
- `frost_risk` - Frost risk level
- `visibility_miles`, `visibility_km` - Visibility
- `uv_index` - UV index

**ForecastPeriod**:
- `snow_depth`, `frost_risk`, `ice_risk`
- `heat_index_max_f`, `heat_index_min_f`
- `wind_chill_min_f`, `wind_chill_max_f`
- `feels_like_high`, `feels_like_low`

**HourlyForecastPeriod**:
- `snow_depth`, `frost_risk`
- `heat_index_f`, `wind_chill_f`
- `feels_like`, `visibility_miles`

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Season Detection Consistency

*For any* date and latitude, the `get_season()` function should return a season that matches calendar-based definitions, with Southern Hemisphere seasons flipped (December = summer, June = winter).

**Validates: Requirements 1.1, 1.2**

### Property 2: Seasonal Data Display Completeness

*For any* CurrentConditions with seasonal fields populated (snow_depth, wind_chill, heat_index, frost_risk, visibility), the formatted output should include those values when they are not None.

**Validates: Requirements 2.1, 2.2, 2.3, 3.1, 4.1**

### Property 3: Graceful Degradation

*For any* CurrentConditions with all seasonal fields set to None, the formatter should produce valid output without errors and without placeholder text for missing seasonal data.

**Validates: Requirements 5.1, 5.2**

### Property 4: Feels-Like Temperature Selection

*For any* CurrentConditions:
- When temperature < 50°F and wind_speed > 3 mph, feels-like should use wind_chill
- When temperature > 80°F and humidity > 40%, feels-like should use heat_index
- Otherwise, feels-like should use actual temperature or existing feels_like value

**Validates: Requirements 6.1, 6.2, 6.3**

---

## Error Handling

### Graceful Degradation Strategy

1. **Missing Seasonal Data**: When seasonal fields are None, skip them in display
2. **Invalid Values**: If a seasonal value fails validation, treat as None
3. **No Crashes**: Formatters should never raise exceptions for missing data

---

## Testing Strategy

### Property-Based Testing

The feature uses Hypothesis for property-based testing. Each property test should run a minimum of 100 iterations.

**Test File**: `tests/test_seasonal_display_properties.py`

**Properties to Test**:
1. Season detection (Property 1)
2. Seasonal data display (Property 2)
3. Graceful degradation (Property 3)
4. Feels-like selection (Property 4)

### Unit Tests

Unit tests cover specific examples and edge cases:
- Season detection at boundary dates (March 1, June 1, etc.)
- Hemisphere flip verification
- Formatter output for specific seasonal values

---

## Implementation Notes

### What's Already Done

1. ✅ Season enum and detection functions in `models/weather.py`
2. ✅ Seasonal fields in all data models
3. ✅ Open-Meteo client requests seasonal parameters
4. ✅ UV index formatting with categories
5. ✅ Basic feels-like temperature formatting

### What Needs to Be Done

1. Add `format_snow_depth()` function
2. Add `format_frost_risk()` function
3. Add `select_feels_like_temperature()` function
4. Enhance current conditions presentation to include seasonal fields
5. Add property-based tests for seasonal logic

---

**Document Status:** Ready for Review
