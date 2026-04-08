# Discussion Dialog AI Visibility Design

## Goal
When no AI explanation has been generated yet, the discussion dialog should not show the AI summary field or model-information field. The dialog should show only the `Explain with AI` button. After the user requests an explanation, the AI summary textbox should appear. If generation succeeds, the textbox shows the generated explanation and the regenerate button appears. If generation fails, the textbox should still appear and show the error message.

## Recommended approach
Use the existing controls and change only their visibility and state.

Why this approach:
- minimal layout risk in an existing wx dialog
- preserves current button handlers and async flow
- avoids rebuilding controls dynamically, which is more fragile for accessibility and focus behavior

## UI behavior

### Initial state
- Show the forecast discussion section as today.
- Hide the plain-language summary label.
- Hide the plain-language summary textbox.
- Hide the model-information label and textbox.
- Show `Explain with AI`.
- Hide `Regenerate Explanation`.

### During generation
- Reveal the plain-language summary label and textbox.
- Put `Generating plain language summary...` into the AI textbox.
- Keep model-information controls hidden until success.
- Keep `Regenerate Explanation` hidden.
- Disable `Explain with AI` while the request is running.

### On success
- Keep the AI summary controls visible.
- Fill the AI textbox with the generated explanation.
- Reveal model-information controls.
- Reveal `Regenerate Explanation`.
- Hide `Explain with AI`, since regenerate becomes the follow-up action.

### On failure
- Keep the AI summary controls visible.
- Fill the AI textbox with the error message.
- Keep model-information controls hidden.
- Reveal `Regenerate Explanation` so the user can retry immediately.
- Hide `Explain with AI` after the first attempt, for consistency with the success state.

## Implementation notes
- Add helper methods for AI section visibility/state so the dialog does not scatter `Show/Hide/Layout` calls across multiple handlers.
- Keep existing async explanation flow intact.
- Preserve current screen-reader-friendly naming on the text controls.
- Re-layout the dialog after visibility changes.

## Testing
- Add/update dialog tests to cover:
  - initial state hides AI summary and model info
  - starting explanation reveals summary area with loading text
  - success reveals summary, model info, and regenerate button while hiding explain
  - failure reveals summary with error text, keeps model info hidden, and shows regenerate

## Scope
This change is limited to the discussion dialog presentation and its tests. It does not change explanation generation, model selection, or prompt behavior.
