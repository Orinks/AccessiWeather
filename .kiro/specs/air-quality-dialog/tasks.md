# Implementation Plan

- [x] 1. Create Air Quality Dialog UI component





  - [ ] 1.1 Create `src/accessiweather/dialogs/air_quality_dialog.py` with AirQualityDialog class
    - Implement `__init__` accepting app, location_name, environmental data, and settings
    - Create dialog window with title "Air Quality - {location_name}"


    - Add aria_label and aria_description to all interactive elements
    - _Requirements: 1.2, 1.3, 5.1, 5.2_
  - [ ] 1.2 Implement summary section in dialog
    - Display current AQI value and category


    - Display dominant pollutant if available
    - Display health guidance based on category
    - Display last updated timestamp
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [-] 1.3 Implement hourly forecast section in dialog

    - Display trend (improving/worsening/stable)

    - Display peak AQI time and value

    - Display best time for outdoor activities (if AQI < 100)
    - Limit display to 24 hours maximum
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - [ ] 1.4 Implement pollutant details section in dialog
    - Display individual pollutant measurements with human-readable names
    - Indicate dominant pollutant
    - _Requirements: 4.1, 4.2, 4.3_
  - [ ] 1.5 Implement dialog close functionality
    - Add Close button that dismisses dialog
    - Return focus to main window on close
    - _Requirements: 6.1, 6.2_
  - [ ]* 1.6 Write unit tests for AirQualityDialog
    - Test dialog creation with valid data
    - Test dialog creation with no data
    - Test close button functionality
    - Test accessibility attributes
    - _Requirements: 1.2, 1.3, 5.1, 5.2, 6.1, 6.2_

- [ ] 2. Add presentation functions for dialog content
  - [ ] 2.1 Create `format_air_quality_summary()` function
    - Accept EnvironmentalConditions and AppSettings
    - Return formatted summary string with AQI, category, pollutant, guidance, timestamp
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [ ] 2.2 Create `format_pollutant_details()` function
    - Accept HourlyAirQuality data
    - Return formatted pollutant breakdown with human-readable names
    - Indicate dominant pollutant
    - _Requirements: 4.1, 4.2, 4.3_
  - [ ]* 2.3 Write property test for summary contains AQI and category
    - **Property 2: Summary contains AQI and category**
    - **Validates: Requirements 2.1**
  - [ ]* 2.4 Write property test for dominant pollutant appears when available
    - **Property 3: Dominant pollutant appears when available**
    - **Validates: Requirements 2.2**
  - [ ]* 2.5 Write property test for health guidance matches AQI category
    - **Property 4: Health guidance matches AQI category**
    - **Validates: Requirements 2.3**
  - [ ]* 2.6 Write property test for pollutant names are human-readable
    - **Property 9: Pollutant names are human-readable**
    - **Validates: Requirements 4.2, 4.3**
  - [ ]* 2.7 Write property test for formatting function is deterministic
    - **Property 11: Formatting function is deterministic**
    - **Validates: Requirements 8.1, 8.2**

- [ ] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Enhance hourly forecast formatting
  - [ ] 4.1 Update `format_hourly_air_quality()` to support dialog display
    - Ensure output limited to 24 hours
    - Include time, AQI, and category for each hour
    - _Requirements: 3.1, 3.2_
  - [ ]* 4.2 Write property test for hourly forecast limited to 24 hours
    - **Property 5: Hourly forecast limited to 24 hours**
    - **Validates: Requirements 3.1**
  - [ ]* 4.3 Write property test for trend correctly identifies direction
    - **Property 6: Trend correctly identifies direction**
    - **Validates: Requirements 3.3**
  - [ ]* 4.4 Write property test for peak AQI is maximum value
    - **Property 7: Peak AQI is maximum value**
    - **Validates: Requirements 3.4**
  - [ ]* 4.5 Write property test for best time has AQI below threshold
    - **Property 8: Best time has AQI below threshold**
    - **Validates: Requirements 3.5**

- [ ] 5. Integrate Air Quality menu item
  - [ ] 5.1 Add `on_view_air_quality()` event handler in `weather_handlers.py`
    - Check for current location, show info dialog if none
    - Check for air quality data, show info dialog if unavailable
    - Create and show AirQualityDialog
    - _Requirements: 1.4, 2.5_
  - [ ] 5.2 Add Air Quality command to View menu in `ui_builder.py`
    - Create toga.Command with text "Air Quality…"
    - Add to toga.Group.VIEW
    - Wire to on_view_air_quality handler
    - _Requirements: 1.1_
  - [ ]* 5.3 Write property test for location name appears in dialog
    - **Property 1: Location name appears in dialog**
    - **Validates: Requirements 1.3**
  - [ ]* 5.4 Write unit tests for menu integration
    - Test Air Quality command exists in View menu
    - Test handler shows dialog with correct location
    - Test handler shows info dialog when no location selected
    - _Requirements: 1.1, 1.2, 1.4_

- [ ] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Fix duplicate air quality display in Current Conditions
  - [ ] 7.1 Create `format_air_quality_brief()` function
    - Return concise summary: AQI value, category, and trend only
    - No detailed hourly breakdown
    - _Requirements: 7.2_
  - [ ] 7.2 Update `update_weather_displays()` in `weather_handlers.py`
    - Replace current air quality sections with single brief summary
    - Remove duplicate "Air quality update" and "Hourly forecast" sections
    - Use `format_air_quality_brief()` for Current Conditions display
    - _Requirements: 7.1, 7.3_
  - [ ]* 7.3 Write property test for no duplicate air quality sections
    - **Property 10: No duplicate air quality sections**
    - **Validates: Requirements 7.1, 7.3**
  - [ ]* 7.4 Write unit tests for brief summary format
    - Test brief summary contains AQI, category, trend
    - Test brief summary does not contain detailed hourly data
    - _Requirements: 7.2_

- [ ] 8. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
