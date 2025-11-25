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


- [ ] 1.2 Write property test for heading navigation sequence
  - **Property 2: Heading navigation sequence**
  - **Validates: Requirements 1.2**
  - Generate random forecast data
  - Verify headings appear in chronological order

  - Run 100+ iterations

- [ ] 1.3 Write unit tests for forecast rendering edge cases
  - Test with empty forecast data


  - Test with single day forecast
  - Test with maximum days (14)
  - Test fallback behavior when accessibility attributes unavailable
  - _Requirements: 1.1, 1.4_

- [ ] 2. Enhance system tray functionality for Windows 11
  - Update `initialize_system_tray()` in `ui_builder.py` to return success status
  - Add Windows 11 specific compatibility checks

  - Ensure system tray icon is visible (not hidden in overflow)
  - Add meaningful tooltip text to system tray icon
  - Improve window show/hide toggle logic in system tray commands
  - Add fallback handling when system tray unavailable
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2.1 Write property test for system tray state consistency

  - **Property 4: System tray minimize behavior**
  - **Validates: Requirements 2.1, 2.2, 4.1**
  - Generate random application states (window visible/hidden, tray enabled/disabled)
  - Trigger minimize actions
  - Verify window and tray icon states are consistent

  - Run 100+ iterations

- [ ] 2.2 Write unit tests for system tray initialization
  - Test successful initialization
  - Test initialization failure handling
  - Test system tray unavailable scenario
  - Test context menu creation
  - _Requirements: 2.1, 2.2, 2.4_

- [x] 3. Improve window management and Escape key handling

  - Enhance `handle_window_close()` in `app_helpers.py` for better minimize-to-tray logic
  - Add window visibility state tracking to `AccessiWeatherApp`
  - Implement `handle_escape_key()` function with modal dialog detection
  - Add global Escape key handler to main window
  - Ensure Escape closes dialogs without minimizing main window
  - Add fallback to taskbar minimize when system tray unavailable
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_


- [ ] 3.1 Write property test for Escape key context awareness
  - **Property 6: Escape key context awareness**
  - **Validates: Requirements 4.2**
  - Generate random UI states (with/without modal dialogs)
  - Trigger Escape key
  - Verify correct behavior (dialog close vs window minimize)

  - Run 100+ iterations

- [ ] 3.2 Write property test for fallback minimize behavior
  - **Property 8: Fallback minimize behavior**
  - **Validates: Requirements 4.4, 4.5**


  - Generate states where system tray is unavailable or disabled
  - Trigger minimize actions
  - Verify window minimizes to taskbar instead of hiding
  - Run 100+ iterations

- [ ] 3.3 Write unit tests for window management
  - Test minimize-to-tray when enabled

  - Test minimize-to-taskbar when tray disabled
  - Test window restore from tray
  - Test Escape key with open dialog
  - Test Escape key without dialog


  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 4. Add desktop shortcut creation for Windows installer


  - Update `pyproject.toml` Briefcase configuration for Windows
  - Add desktop shortcut creation option to MSI installer

  - Ensure shortcut uses correct application icon
  - Set proper working directory and launch parameters
  - Add shortcut removal during uninstallation
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_


- [ ] 4.1 Write unit tests for desktop shortcut configuration
  - Test shortcut file properties (Windows only, may need mocking)
  - Test icon path resolution
  - Test working directory configuration
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 5. Update UI to use new forecast rendering
  - Modify `create_weather_display_section()` in `ui_builder.py`
  - Replace `forecast_display` MultilineTextInput with structured Box container
  - Update event handlers to work with new forecast structure
  - Ensure forecast updates refresh the structured display
  - Test with real weather data
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 5.1 Write integration tests for forecast display workflow
  - Test complete forecast display with real weather data structure
  - Test forecast updates and refreshes
  - Test accessibility attribute presence
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Update documentation and changelog
  - Update README.md to remove "Screen reader parsing" from Known Issues
  - Update README.md to remove "Escape key" from Known Issues
  - Add entries to CHANGELOG.md under "Unreleased" section:
    - Added: "Heading navigation for forecast days - screen readers can now jump between days using heading shortcuts (H key)"
    - Added: "Desktop shortcut creation during Windows installation"
    - Fixed: "System tray functionality on Windows 11 - minimize to tray now works reliably"
    - Fixed: "Escape key minimize behavior - now consistently minimizes to tray across all scenarios"
  - Use human-authentic writing style (avoid AI patterns like "enhanced", "optimized", "streamlined")
  - _Requirements: All_

- [ ] 7.1 Write manual testing checklist for accessibility
  - Create checklist for NVDA testing (heading navigation with H key)
  - Create checklist for JAWS testing (heading announcement)
  - Create checklist for Windows 11 Narrator testing
  - Create checklist for system tray visibility on Windows 11
  - Create checklist for desktop shortcut verification

- [ ] 8. Final checkpoint - Verify all functionality
  - Ensure all tests pass, ask the user if questions arise.
