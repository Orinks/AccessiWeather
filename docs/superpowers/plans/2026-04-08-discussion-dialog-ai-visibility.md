# Discussion Dialog AI Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide the AI summary and model-info fields in the discussion dialog until the user requests an explanation, then reveal them appropriately for loading, success, and error states.

**Architecture:** Keep the existing wx controls and event flow, but centralize visibility/state transitions in small helper methods on `DiscussionDialog`. Drive the change with tests first so the dialog's initial, loading, success, and error states are locked down before touching implementation.

**Tech Stack:** Python, wxPython, pytest, unittest.mock

---

## File map

- Modify: `src/accessiweather/ui/dialogs/discussion_dialog.py`
  - Add helper methods to show/hide the AI section and synchronize button visibility.
  - Update initial, loading, success, and error states.
- Modify: `tests/test_discussion_dialog.py`
  - Add focused tests for the dialog state transitions.

### Task 1: Lock down the desired dialog states with tests

**Files:**
- Modify: `tests/test_discussion_dialog.py`
- Test: `tests/test_discussion_dialog.py`

- [ ] **Step 1: Write the failing tests**

Add focused state tests like this near the discussion-dialog tests:

```python
class _VisibleControl:
    def __init__(self):
        self.visible = True
        self.enabled = True
        self.value = ""

    def Show(self):
        self.visible = True

    def Hide(self):
        self.visible = False

    def IsShown(self):
        return self.visible

    def Enable(self):
        self.enabled = True

    def Disable(self):
        self.enabled = False

    def SetValue(self, value):
        self.value = value


class _FakeSizer:
    def __init__(self):
        self.layout_calls = 0

    def Layout(self):
        self.layout_calls += 1


def _build_dialog_state():
    dialog = SimpleNamespace()
    dialog.explanation_header = _VisibleControl()
    dialog.explanation_display = _VisibleControl()
    dialog.model_info_label = _VisibleControl()
    dialog.model_info = _VisibleControl()
    dialog.explain_button = _VisibleControl()
    dialog.regenerate_button = _VisibleControl()
    dialog._sizer = _FakeSizer()
    dialog.GetSizer = lambda: dialog._sizer
    dialog._set_status = MagicMock()
    return dialog


def test_setup_initial_state_hides_ai_fields():
    from accessiweather.ui.dialogs import discussion_dialog

    dialog = _build_dialog_state()
    dialog.discussion_display = _VisibleControl()
    dialog.explain_button.Disable()

    discussion_dialog.DiscussionDialog._setup_initial_state(dialog)

    assert dialog.explanation_header.IsShown() is False
    assert dialog.explanation_display.IsShown() is False
    assert dialog.model_info_label.IsShown() is False
    assert dialog.model_info.IsShown() is False
    assert dialog.regenerate_button.IsShown() is False


def test_on_explain_reveals_summary_area_with_loading_text():
    from accessiweather.ui.dialogs import discussion_dialog

    dialog = _build_dialog_state()
    dialog._current_discussion = "Forecast text"
    dialog._is_explaining = False
    dialog.app = SimpleNamespace(run_async=MagicMock())
    dialog._do_explain = MagicMock(return_value="task")

    discussion_dialog.DiscussionDialog._on_explain(dialog, None)

    assert dialog.explanation_header.IsShown() is True
    assert dialog.explanation_display.IsShown() is True
    assert dialog.explanation_display.value == "Generating plain language summary..."
    assert dialog.model_info_label.IsShown() is False
    assert dialog.model_info.IsShown() is False
    assert dialog.regenerate_button.IsShown() is False


def test_on_explain_complete_shows_summary_model_info_and_regenerate():
    from accessiweather.ui.dialogs import discussion_dialog

    dialog = _build_dialog_state()
    dialog._is_explaining = True

    discussion_dialog.DiscussionDialog._on_explain_complete(
        dialog,
        "Plain explanation",
        "openrouter/auto",
        123,
        0.0,
        False,
    )

    assert dialog.explanation_header.IsShown() is True
    assert dialog.explanation_display.IsShown() is True
    assert dialog.explanation_display.value == "Plain explanation"
    assert dialog.model_info_label.IsShown() is True
    assert dialog.model_info.IsShown() is True
    assert dialog.regenerate_button.IsShown() is True
    assert dialog.explain_button.IsShown() is False


def test_on_explain_error_shows_error_text_and_regenerate_only():
    from accessiweather.ui.dialogs import discussion_dialog

    dialog = _build_dialog_state()
    dialog._is_explaining = True

    discussion_dialog.DiscussionDialog._on_explain_error(dialog, "boom")

    assert dialog.explanation_header.IsShown() is True
    assert dialog.explanation_display.IsShown() is True
    assert "Failed to generate explanation: boom" in dialog.explanation_display.value
    assert dialog.model_info_label.IsShown() is False
    assert dialog.model_info.IsShown() is False
    assert dialog.regenerate_button.IsShown() is True
    assert dialog.explain_button.IsShown() is False
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
pytest tests/test_discussion_dialog.py -k "setup_initial_state_hides_ai_fields or on_explain_reveals_summary_area_with_loading_text or on_explain_complete_shows_summary_model_info_and_regenerate or on_explain_error_shows_error_text_and_regenerate_only" -v
```

Expected: FAIL because `DiscussionDialog` does not yet hide/show the AI controls that way.

- [ ] **Step 3: Commit the failing-test checkpoint only if you want an explicit red-state commit**

```bash
git add tests/test_discussion_dialog.py
git commit -m "test: cover discussion dialog AI visibility states"
```

### Task 2: Implement the dialog state helpers and wire them into the existing flow

**Files:**
- Modify: `src/accessiweather/ui/dialogs/discussion_dialog.py`
- Test: `tests/test_discussion_dialog.py`

- [ ] **Step 1: Write the minimal implementation helpers**

Update widget creation so the explanation header is stored on `self`, then add helpers like this:

```python
self.explanation_header = wx.StaticText(panel, label="Plain Language Summary:")
main_sizer.Add(self.explanation_header, 0, wx.LEFT | wx.RIGHT, 10)
```

```python
def _layout_dialog(self) -> None:
    sizer = self.GetSizer()
    if sizer:
        sizer.Layout()


def _show_ai_summary_section(self) -> None:
    self.explanation_header.Show()
    self.explanation_display.Show()


def _hide_ai_summary_section(self) -> None:
    self.explanation_header.Hide()
    self.explanation_display.Hide()


def _show_model_info(self) -> None:
    self.model_info_label.Show()
    self.model_info.Show()


def _hide_model_info(self) -> None:
    self.model_info_label.Hide()
    self.model_info.Hide()


def _set_post_explain_buttons(self, has_attempted_explanation: bool) -> None:
    if has_attempted_explanation:
        self.explain_button.Hide()
        self.regenerate_button.Show()
    else:
        self.explain_button.Show()
        self.regenerate_button.Hide()
    self._layout_dialog()
```

- [ ] **Step 2: Update the initial state to hide AI controls before first generation**

Change `_setup_initial_state()` to:

```python
def _setup_initial_state(self) -> None:
    self.discussion_display.SetValue("Loading...")
    self.explanation_display.SetValue("")
    self.model_info.SetValue("")
    self._hide_ai_summary_section()
    self._hide_model_info()
    self._set_post_explain_buttons(has_attempted_explanation=False)
    self.explain_button.Disable()
```

- [ ] **Step 3: Update the loading, success, and error handlers**

Adjust `_on_explain()`, `_on_explain_complete()`, and `_on_explain_error()` like this:

```python
def _on_explain(self, event) -> None:
    if not self._current_discussion or self._is_explaining:
        return

    self._is_explaining = True
    self._show_ai_summary_section()
    self._hide_model_info()
    self.regenerate_button.Hide()
    self.explain_button.Disable()
    self.explanation_display.SetValue("Generating plain language summary...")
    self._layout_dialog()
    self._set_status("Generating AI explanation...")
    self.app.run_async(self._do_explain())
```

```python
def _on_explain_complete(...):
    self._is_explaining = False
    self._show_ai_summary_section()
    self.explanation_display.SetValue(explanation)
    ...
    self._show_model_info()
    self._set_post_explain_buttons(has_attempted_explanation=True)
    self.regenerate_button.Enable()
    self._set_status(f"Explanation generated using {model_used}.")
```

```python
def _on_explain_error(self, error: str) -> None:
    self._is_explaining = False
    self._show_ai_summary_section()
    self._hide_model_info()
    self.explanation_display.SetValue(
        f"Failed to generate explanation: {error}\n\n"
        "Please check your OpenRouter API key in Settings."
    )
    self._set_post_explain_buttons(has_attempted_explanation=True)
    self.regenerate_button.Enable()
    self._set_status("Explanation failed.")
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run:

```bash
pytest tests/test_discussion_dialog.py -k "setup_initial_state_hides_ai_fields or on_explain_reveals_summary_area_with_loading_text or on_explain_complete_shows_summary_model_info_and_regenerate or on_explain_error_shows_error_text_and_regenerate_only" -v
```

Expected: PASS

- [ ] **Step 5: Run the full discussion-dialog test file**

Run:

```bash
pytest tests/test_discussion_dialog.py -v
```

Expected: PASS

- [ ] **Step 6: Commit the implementation**

```bash
git add src/accessiweather/ui/dialogs/discussion_dialog.py tests/test_discussion_dialog.py
git commit -m "feat: streamline discussion dialog AI visibility"
```

## Self-review

- Spec coverage: initial hidden AI state, loading reveal, success reveal, failure reveal, and regenerate behavior are all covered by Tasks 1 and 2.
- Placeholder scan: no TODO/TBD placeholders remain.
- Type consistency: helper and method names match the dialog file's current structure and use existing wx control names.
