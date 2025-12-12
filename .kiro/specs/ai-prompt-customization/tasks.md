# Implementation Plan

- [x] 1. Extend configuration with prompt settings

  - [x] 1.1 Add `custom_system_prompt` and `custom_instructions` fields to `AppSettings`

    - Add optional string fields with None defaults
    - Ensure backward compatibility with existing configs

    - _Requirements: 1.4, 2.4_

  - [x] 1.2 Write property test for configuration round-trip

    - **Property 3: Configuration persistence round-trip**
    - **Validates: Requirements 1.4, 2.4**

- [x] 2. Modify AIExplainer to support custom prompts

  - [x] 2.1 Add custom prompt parameters to AIExplainer constructor

    - Add `custom_system_prompt` and `custom_instructions` parameters
    - Store as instance attributes

    - _Requirements: 1.2, 2.1_

  - [x] 2.2 Implement `get_effective_system_prompt()` method

    - Return custom prompt if configured, otherwise default
    - Rename existing `_build_system_prompt` to `_build_default_system_prompt`
    - _Requirements: 1.2, 1.3_

  - [x] 2.3 Write property test for custom system prompt usage

    - **Property 1: Custom system prompt used when configured**
    - **Validates: Requirements 1.2**

  - [x] 2.4 Write property test for default prompt fallback

    - **Property 2: Default prompt used when custom is empty**
    - **Validates: Requirements 1.3**

  - [x] 2.5 Modify `_build_prompt()` to include custom instructions

    - Append custom instructions after weather data when configured
    - Skip instructions section when empty/None
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 2.6 Write property test for custom instructions inclusion

    - **Property 4: Custom instructions appended to prompt**
    - **Property 5: Custom instructions positioned after weather data**
    - **Property 6: Empty instructions not included**
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x] 2.7 Add `get_default_system_prompt()` static method

    - Return the default system prompt text for UI display
    - _Requirements: 1.5_

  - [x] 2.8 Add `get_prompt_preview()` method

    - Generate preview with sample weather data
    - Return dict with system_prompt and user_prompt

    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 2.9 Write property test for preview with custom instructions

    - **Property 8: Preview includes custom instructions**
    - **Validates: Requirements 4.3**

- [x] 3. Checkpoint - Ensure all tests pass

  - All tests pass ✓

- [x] 4. Add prompt customization UI to settings dialog

  - [x] 4.1 Create prompt customization section in settings dialog

    - Add MultilineTextInput for custom system prompt
    - Add MultilineTextInput for custom instructions
    - Show default prompt as placeholder text
    - _Requirements: 1.1, 1.5, 2.1_

  - [x] 4.2 Add reset buttons for prompts

    - "Reset System Prompt" button clears custom_system_prompt
    - "Reset Instructions" button clears custom_instructions
    - Show confirmation message after reset
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 4.3 Write property test for reset behavior

    - **Property 7: Reset restores defaults**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [x] 4.4 Add preview button and dialog

    - "Preview Prompt" button shows preview dialog
    - Display both system and user prompts
    - _Requirements: 4.1, 4.2_

  - [x] 4.5 Add accessibility attributes to all form elements

    - Add aria-label and aria-description to text inputs
    - Add aria-label to buttons
    - Use ARIA live regions for announcements
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 4.6 Write property test for accessibility attributes

    - **Property 9: Accessibility attributes present**
    - **Validates: Requirements 5.1, 5.2**

- [x] 5. Wire up settings to AIExplainer

  - [x] 5.1 Pass custom prompts from settings to AIExplainer

    - Update AIExplainer instantiation to include custom prompts
    - Ensure settings changes are reflected in new explanations
    - _Requirements: 1.2, 2.1_

- [x] 6. Final Checkpoint - Ensure all tests pass

  - All 25 property-based tests pass ✓
  - Feature committed and pushed to `feature/ai-prompt-customization` branch
