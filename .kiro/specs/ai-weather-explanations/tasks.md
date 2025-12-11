# Implementation Plan

- [x] 1. Set up project dependencies and configuration models
  - Add `openai>=1.0.0` dependency to `pyproject.toml`
  - Extend `AppSettings` dataclass with AI configuration fields
  - Add default values for AI settings
  - _Requirements: 3.1, 3.5_

- [ ]* 1.1 Write property test for settings persistence
  - **Property 4: Settings persistence round-trip**
  - **Validates: Requirements 3.5**

- [x] 2. Implement core AIExplainer module
  - Create `src/accessiweather/ai_explainer.py` with `AIExplainer` class
  - Implement `__init__` with API key, model, and cache parameters
  - Create custom exception classes (AIExplainerError, InsufficientCreditsError, RateLimitError, InvalidAPIKeyError)
  - Implement `ExplanationResult` and `ExplanationStyle` dataclasses
  - _Requirements: 1.2, 2.1, 2.2, 2.5, 5.1, 5.2, 5.3, 5.4_

- [ ]* 2.1 Write property test for model selection
  - **Property 2: Model selection matches configuration**
  - **Validates: Requirements 2.1, 2.2, 2.5**

- [x] 3. Implement prompt construction logic
  - Create `WeatherContext` dataclass for structured weather data
  - Implement `_build_prompt()` method to convert weather data to natural language
  - Include all required fields (temperature, conditions, humidity, wind, visibility)
  - Add conditional alert inclusion logic
  - Add accessibility optimization instructions to system prompt
  - _Requirements: 4.1, 4.2, 4.3_

- [ ]* 3.1 Write property test for prompt field inclusion
  - **Property 5: Prompt includes all required weather fields**
  - **Validates: Requirements 4.1**

- [ ]* 3.2 Write property test for alert inclusion
  - **Property 6: Alerts included when present**
  - **Validates: Requirements 4.2**

- [x] 4. Implement OpenRouter API integration
  - Initialize OpenAI client with OpenRouter base URL
  - Implement `_call_openrouter()` method with proper headers
  - Add 30-second timeout handling
  - Parse API response into `OpenRouterResponse` dataclass
  - Extract model used, token counts, and content
  - _Requirements: 1.2, 2.1, 2.2, 2.5_

- [x] 5. Implement response formatting and markdown handling
  - Create `_format_response()` method
  - Implement markdown stripping logic for plain text mode
  - Implement markdown preservation for HTML mode
  - Check HTML rendering setting from app config
  - _Requirements: 4.4, 4.5_

- [ ]* 5.1 Write property test for markdown formatting
  - **Property 7: Markdown formatting follows HTML setting**
  - **Validates: Requirements 4.4, 4.5**

- [x] 6. Implement caching layer integration
  - Integrate with existing `cache.py` infrastructure
  - Generate cache keys from weather data and location
  - Implement 5-minute TTL for explanations
  - Add cache lookup in `explain_weather()` method
  - Store successful explanations in cache
  - _Requirements: 2.4_

- [ ]* 6.1 Write property test for cache behavior
  - **Property 3: Cache prevents duplicate API calls**
  - **Validates: Requirements 2.4**

- [x] 7. Implement comprehensive error handling
  - Add try-except blocks for all error categories
  - Map API errors to custom exceptions
  - Create user-friendly error messages without technical details
  - Implement detailed error logging
  - Add network error detection
  - Handle insufficient credits error specifically
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ]* 7.1 Write property test for error message formatting
  - **Property 9: Error messages are user-friendly**
  - **Validates: Requirements 5.1**

- [ ]* 7.2 Write property test for error logging
  - **Property 10: Errors logged without user exposure**
  - **Validates: Requirements 5.6**

- [x] 8. Implement data source selection logic
  - Create method to compare timestamps across weather data sources
  - Select most recent data source for explanation
  - Handle missing timestamp gracefully
  - _Requirements: 4.6_

- [ ]* 8.1 Write property test for data source selection
  - **Property 8: Most recent data source selected**
  - **Validates: Requirements 4.6**

- [x] 9. Implement cost estimation and usage tracking
  - Create method to estimate token counts before API call
  - Calculate estimated cost based on model pricing
  - Implement session usage tracking (accumulate token counts)
  - Add cost display logic (show "No cost" for free models)
  - Include token counts in ExplanationResult
  - _Requirements: 7.1, 7.3, 7.4, 7.5_

- [ ]* 9.1 Write property test for usage accumulation
  - **Property 13: Session usage accumulates correctly**
  - **Validates: Requirements 7.4**

- [ ]* 9.2 Write property test for free model cost display
  - **Property 14: Free model cost display**
  - **Validates: Requirements 7.5**

- [x] 10. Add "Explain Weather" button to weather display
  - Modify `ui_builder.py` to add button to current weather view
  - Implement conditional rendering based on `enable_ai_explanations` setting
  - Add `on_press` handler to trigger explanation generation
  - Include proper `aria-label` and `aria-description` attributes
  - _Requirements: 1.1, 1.5, 8.3_

- [ ]* 10.1 Write property test for button visibility
  - **Property 1: Button visibility follows AI enablement setting**
  - **Validates: Requirements 1.1, 1.5**

- [ ]* 10.2 Write property test for accessibility attributes
  - **Property 15: Accessibility attributes present**
  - **Validates: Requirements 8.3**

- [x] 11. Create explanation dialog component
  - Create `src/accessiweather/dialogs/explanation_dialog.py`
  - Build dialog with explanation text, location, and timestamp
  - Implement focus management (set focus to explanation text)
  - Add ARIA live region for loading state
  - Add ARIA live region for error announcements
  - Use semantic HTML with proper heading structure
  - _Requirements: 1.3, 1.4, 8.1, 8.2, 8.4, 8.5_

- [ ]* 11.1 Write property test for dialog focus management
  - **Property 16: Dialog focus management**
  - **Validates: Requirements 8.1**

- [ ]* 11.2 Write property test for loading state announcement
  - **Property 17: Loading state announced**
  - **Validates: Requirements 8.4**

- [ ]* 11.3 Write property test for error announcements
  - **Property 18: Error announcements accessible**
  - **Validates: Requirements 8.5**

- [x] 12. Implement explanation generation flow
  - Wire button press to AIExplainer.explain_weather()
  - Show loading indicator while generating
  - Handle async operation with asyncio.to_thread()
  - Display result in explanation dialog on success
  - Show error dialog on failure
  - _Requirements: 1.2, 1.3_

- [x] 13. Add AI settings section to settings dialog
  - Modify `src/accessiweather/dialogs/settings_dialog.py`
  - Add "Enable AI Explanations" toggle switch
  - Add password field for OpenRouter API key (mask input)
  - Add dropdown for model preference (Auto Free, Auto Paid, specific models)
  - Add dropdown for explanation style (Brief, Standard, Detailed)
  - Add "Test API Key" button with validation
  - Add link to OpenRouter pricing page
  - Display usage information
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 7.2_

- [x] 14. Implement settings validation and persistence
  - Validate API key format (starts with "sk-or-")
  - Implement `validate_api_key()` method with test API call
  - Save settings to config file on change
  - Implement reactive UI updates when toggle changes
  - _Requirements: 3.2, 3.4, 3.5_

- [x] 15. Add API key security measures
  - Mask API key in UI (show only last 4 characters)
  - Never log full API key values
  - Validate format before storage
  - _Requirements: 3.5_

- [x] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 17. Write integration tests for real API calls
  - Test free model access without API key
  - Test paid model access with valid API key
  - Test rate limiting behavior
  - Test error scenarios (invalid key, network issues)
  - Mark tests with `@pytest.mark.integration` to skip in CI
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ]* 18. Write unit tests for UI components
  - Test button rendering with various settings
  - Test dialog content structure
  - Test settings UI validation
  - Test focus management
  - _Requirements: 1.1, 1.3, 1.4, 1.5, 3.1, 3.3_

- [ ]* 19. Write unit tests for error handling
  - Test each error type produces correct exception
  - Test user messages don't contain technical details
  - Test logging captures full error context
  - Test fallback behavior
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 20. Update documentation
  - Add AI explanations section to README
  - Document OpenRouter setup process
  - Add screenshots of new UI elements
  - Document cost considerations
  - _Requirements: All_

- [ ] 21. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
