# Advanced Coordinates Dialog (#315)

**Title:** Add advanced coordinates dialog for manual location entry

## Motivation
- Reduce input errors by guiding users through format validation before saving coordinates.
- Provide an accessible workflow for screen reader users who currently rely on terse inline hints.
- Set the groundwork for supporting multiple coordinate formats without overwhelming the primary dialog.

## Proposed Solution
1. Launch a secondary modal dialog when the Advanced button is pressed, allowing users to enter latitude and longitude in dedicated inputs.
2. Validate entries in real time, showing descriptive error states and clarifying accepted formats (decimal degrees and degrees with cardinal indicators).
3. Offer helper text summarizing conversion tips and link to documentation for acquiring coordinates.
4. Persist choices back to the main dialog only after validation succeeds, so the Save workflow remains unchanged.

## References
- `src/accessiweather/dialogs/location_dialog.py:6` - module comment linking the dialog work to #315.
- `src/accessiweather/dialogs/location_dialog.py:335` - interim informational dialog guiding users and referencing #315.

## Alternatives Considered
- Expanding the existing dialog inline rather than using a modal. Rejected to avoid cluttering the primary workflow and to keep keyboard navigation predictable.
- Deferring the feature to the configuration screen. Rejected because users typically need advanced coordinates when creating locations, not editing configuration.

## Accessibility Considerations
- Ensure the advanced modal traps focus and announces its purpose and instructions clearly.
- Provide explicit input labels, error messages, and examples that screen readers can parse.
- Support keyboard-only workflows, including predictable tab order and shortcut to confirm/cancel.

## Labels
- `dialog`
- `accessibility`
- `enhancement`

## Milestone
- Target `v0.5.0` (first release after core dialog polish) for delivery.
