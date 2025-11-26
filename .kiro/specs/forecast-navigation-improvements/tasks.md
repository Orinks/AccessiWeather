# Implementation Plan

- [x] 1. Implement forecast display with heading navigation
  - Create new forecast rendering function that uses structured widgets instead of plain text
  - Add `render_forecast_with_headings()` function in `ui_builder.py`
  - Use `toga.Box` with `toga.Label` widgets for each forecast day
  - Set `aria_role="heading"` and `aria_level=2` on day labels
  - Include try-except blocks for platforms without accessibility attribute support
  - Preserve fallback to plain text if structured rendering fails
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 1.1 Write property test for forecast heading structure
  - **Property 1: Forecast heading structure preservation**
  - **Validates: Requirements 1.1, 1.4**
  - Generate random forecast data with 0-14 days
  - Verify each day has corresponding heading widget with correct attributes
  - Run 100+ iterations

- [x] 1.2 Write property test for heading navigation sequence
  - **Property 2: Heading navigation sequence**
  - **Validates: Requirements 1.2**
  - Generate random forecast data
  - Verify headings appear in chronological order
  - Run 100+ iterations

- [x] 1.3 Write unit tests for forecast rendering edge cases
  - Test with empty forecast data
  - Test with single day forecast
  - Test with maximum days (14)
  - Test fallback behavior when accessibility attributes unavailable
  - _Requirements: 1.1, 1.4_

- [x] 2. Update UI to use new forecast rendering
  - Modify `create_weather_display_section()` in `ui_builder.py`
  - Replace `forecast_display` MultilineTextInput with structured Box container
  - Update event handlers to work with new forecast structure
  - Ensure forecast updates refresh the structured display
  - Test with real weather data
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2.1 Write integration tests for forecast display workflow
  - Test complete forecast display with real weather data structure
  - Test forecast updates and refreshes
  - Test accessibility attribute presence
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 3. Checkpoint - Ensure all tests pass


  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update documentation and changelog
  - Update README.md to remove "Screen reader parsing" from Known Issues
  - Add entries to CHANGELOG.md under "Unreleased" section:
    - Added: "Heading navigation for forecast days - screen readers can now jump between days using heading shortcuts (H key)"
  - Use human-authentic writing style (avoid AI patterns like "enhanced", "optimized", "streamlined")
  - _Requirements: All_

- [x] 4.1 Write manual testing checklist for accessibility


  - Create checklist for NVDA testing (heading navigation with H key)
  - Create checklist for JAWS testing (heading announcement)
  - Create checklist for Windows 11 Narrator testing


- [x] 5. Final checkpoint - Verify all functionality

  - Ensure all tests pass, ask the user if questions arise.

---

## Removed Tasks

### Desktop Shortcut Creation (Requirement 3) - REMOVED

**Reason:** After researching Briefcase documentation (v0.3.25), desktop shortcut creation is not supported through configuration. The WiX MSI template only creates Start Menu shortcuts by default. Adding desktop shortcuts would require:

1. Forking the `briefcase-windows-app-template` repository
2. Modifying the `.wxs` WiX template to add a `DesktopFolder` shortcut component
3. Maintaining a custom template branch

This adds significant maintenance burden for a minor convenience feature. Users can manually create desktop shortcuts by right-clicking the Start Menu entry.

**Alternative:** Document in README that users can create desktop shortcuts manually from the Start Menu.
