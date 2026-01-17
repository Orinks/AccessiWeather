# Information Priority Ordering System

## Overview

A comprehensive system for controlling how weather information is presented to screen reader users, with context-aware reordering, user-configurable category ordering, and verbosity control.

## Goals

- Present weather information in optimal order for screen reader users
- Automatically prioritize relevant data during severe weather
- Give users control over information ordering
- Reduce verbosity without losing important details
- Apply consistently across all weather views and data sources

## Core Architecture

### Three Integrated Components

1. **Priority Engine** - Determines display order based on:
   - Active severe weather alerts (highest priority)
   - User's category ordering preference
   - Current weather conditions

2. **Category System** - Orderable categories:
   - Temperature (current, feels like, high/low)
   - Precipitation (chance, amount, type)
   - Wind (speed, gusts, direction)
   - Humidity & Pressure
   - Visibility & Cloud Cover
   - UV Index

3. **Verbosity Controller** - Three levels:
   - **Minimal**: Just the essentials (temp, conditions, precipitation chance)
   - **Standard**: Key details per category (current default behavior)
   - **Detailed**: Full information including feels-like, dewpoint, trends

### Component Interaction

When weather is refreshed:
1. Priority Engine checks for active alerts
2. If severe weather exists, elevates related categories (e.g., wind during high wind warning)
3. Applies user's category order
4. Verbosity Controller filters detail level per category

## Taskbar Integration

When dynamic taskbar text is enabled, the tooltip displays weather info using:
- Same verbosity level as main UI
- Priority-ordered content
- Condensed format suitable for tooltip constraints

### Tooltip Content by Verbosity

- **Minimal**: "72°F Sunny"
- **Standard**: "72°F Sunny, 10% rain, Wind 8mph"
- **Detailed**: Full conditions summary with feels-like temp

## Severe Weather Priority Rules

When alerts are active, the system silently reorders categories (no alert text added to weather display - alerts have their own table):

- Wind Warning → Wind category moves to top
- Flash Flood → Precipitation moves to top
- Heat Advisory → Temperature and UV prioritized
- Winter Storm → Precipitation + Temperature prioritized

### Alert Severity Tiers

- **Warnings** (highest): Always override user ordering
- **Watches**: Elevate related categories but respect some user preference
- **Advisories**: Subtle elevation, mostly preserve user order

### Alert-to-Category Mapping

```
heat_alerts → ["temperature", "uv"]
wind_alerts → ["wind"]
flood_alerts → ["precipitation"]
winter_alerts → ["precipitation", "temperature"]
```

## User Configuration Interface

### Settings Location

New "Display Priority" section in the Settings dialog.

### Controls

1. **Verbosity dropdown:**
   - Minimal / Standard / Detailed
   - Preview text shows example output for selected level

2. **Category Order list:**
   - Displays all categories in current order
   - Up/Down buttons to reorder (keyboard accessible)
   - "Reset to Default" button
   - Screen reader announces: "Temperature, position 1 of 7. Use Up/Down to reorder"

3. **Severe Weather Override toggle:**
   - "Automatically prioritize severe weather info" (default: on)
   - When off, user's category order is always respected

### Default Category Order

1. Temperature
2. Precipitation
3. Wind
4. Humidity & Pressure
5. Visibility & Cloud Cover
6. UV Index

### Persistence

- Settings stored in user config JSON
- Applied immediately on change (no restart required)
- Syncs to taskbar tooltip in real-time

## Application to Weather Views

### Current Conditions View

- Text content reordered by category priority
- Verbosity controls which fields are included
- Active alerts influence order silently

### Forecast View (hourly + extended)

- Each time period's description follows category priority
- Verbosity determines detail level
- Structure unchanged

### What Stays the Same

- Tab switches between Current Conditions and Forecast
- Alerts table remains the place to view alert details
- All existing layout and navigation

### What Changes

- Order of information based on conditions + user preference
- Amount of detail based on verbosity setting
- Tooltip content reflects same ordering

## Multi-Source Compatibility

### Data Source Considerations

1. **National Weather Service (NWS)**
   - Full alert integration for context-aware reordering
   - All weather categories available

2. **Open-Meteo**
   - No native alerts - uses only user's category order
   - All weather categories available
   - International users get consistent priority experience

3. **Visual Crossing**
   - Has alerts when API key configured
   - Map Visual Crossing alert types to same category mappings
   - Falls back to user order when no alerts

### Unified Category Data

The existing data fusion layer normalizes fields across sources. Priority ordering operates on these normalized categories.

### Verbosity Graceful Degradation

If a source lacks data for a category:
- Skip that category in output
- Don't show empty placeholders
- Maintain order for available categories

## Implementation Approach

### Components to Modify

1. **WeatherPresenter** (`src/accessiweather/weather_presenter.py`)
   - Add priority ordering logic to text formatting methods
   - Add verbosity filtering
   - Accept category order and verbosity from settings

2. **Settings/Config**
   - Add `verbosity_level`: "minimal" | "standard" | "detailed"
   - Add `category_order`: list of category identifiers
   - Add `severe_weather_override`: boolean

3. **Settings Dialog**
   - New "Display Priority" section
   - Verbosity dropdown
   - Category reorder list with Up/Down buttons
   - Override toggle

4. **Taskbar Manager**
   - Update tooltip generation to use priority ordering
   - Apply verbosity to tooltip content

### No Changes Needed

- View layouts
- Data fetching
- Alert notification system
- Keyboard navigation
