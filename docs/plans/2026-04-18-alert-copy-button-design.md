# Alert Dialog: Copy-to-Clipboard Button — Design

**Date:** 2026-04-18
**Status:** Approved, ready for implementation
**Scope:** Add a "Copy to clipboard" button to the Alert dialog that works in both display styles (separate and combined) and copies a single, identical text block regardless of which style the user picked.

---

## Problem

Users sometimes want to share or save an alert — paste it into an email, a note, a screen-reader log. Today, to copy an alert's content they have to focus each field in turn, select all, copy, then manually concatenate. A single button lets them grab the whole thing at once.

## Goals

1. A **Copy to clipboard** button in the Alert dialog, present in both display styles.
2. **Identical output** from both styles — copying in separate mode produces the same text as copying in combined mode.
3. **Audible / visible feedback** when copy succeeds (or fails), suitable for screen readers.
4. **Graceful failure** if the system clipboard is held by another app — log + transient "Copy failed" label, no popup, no exception.

## Non-goals

- No keyboard-accelerator-only triggering — `Ctrl+C` is reserved for TextCtrl selection copy; we do not steal it. The button's own `Alt+Y` mnemonic is the keyboard path.
- No scope creep into other dialogs. Copy buttons elsewhere are out of scope.
- No "copy with custom format" settings. One format, everywhere.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Copy payload | `_build_combined_text(alert, settings)` in both modes | Mode-independent output; reuses tested helper |
| Button placement | Left of Close in the existing button sizer | Preserves tab order content → Copy → Close |
| Feedback | Button-label flip: "Cop&y to clipboard" ↔ "Copied!" / "Copy failed" for 2s | Screen readers announce `OBJECT_NAMECHANGE`; no extra widget |
| Keyboard accelerator | `Alt+Y` via `&` in label | Avoids conflict with Close's `Alt+C` |
| Button id | `wx.ID_COPY` | Standard wx id; stock accelerators behave |
| Failure handling | Log warning + flash "Copy failed" | No exception bubbles, no popup, no crash |

---

## Section 1 — Button wiring

`src/accessiweather/ui/dialogs/alert_dialog.py` currently has two methods that each build their own close-button sizer:

- `_create_separate_ui(panel, main_sizer)` ends with a close-button block.
- `_create_combined_ui(panel, main_sizer)` ends with a close-button block.

Extract to a new shared helper `_add_action_buttons(panel, main_sizer)`:

```python
def _add_action_buttons(self, panel, main_sizer):
    button_sizer = wx.BoxSizer(wx.HORIZONTAL)
    button_sizer.AddStretchSpacer()

    self.copy_btn = wx.Button(panel, wx.ID_COPY, "Cop&y to clipboard")
    self.copy_btn.SetName("Copy alert text to clipboard")
    self.copy_btn.Bind(wx.EVT_BUTTON, self._on_copy)
    button_sizer.Add(self.copy_btn, 0, wx.RIGHT, 10)

    close_btn = wx.Button(panel, wx.ID_CLOSE, "&Close")
    close_btn.Bind(wx.EVT_BUTTON, self._on_close)
    button_sizer.Add(close_btn, 0)

    main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)
```

Both UI builders replace their close-button block with a single `self._add_action_buttons(panel, main_sizer)` call. Tab order inside the sizer: Copy → Close.

## Section 2 — Copy payload and handler

Payload is `_build_combined_text(alert, settings)` — already exists and already tested. Expose it through a named instance entry point so it's clear at the button wiring site what the copy content is:

```python
@staticmethod
def _copy_payload(alert, settings) -> str:
    """Text placed on the clipboard when the Copy button is pressed.

    Identical in both display styles, per the feature's Q1.
    """
    return AlertDialog._build_combined_text(alert, settings)
```

The handler:

```python
def _on_copy(self, event):
    text = self._copy_payload(self.alert, self.settings)
    if not wx.TheClipboard.Open():
        logger.warning("Alert copy: could not open clipboard")
        self._flash_button(self.copy_btn, "Copy failed", "Cop&y to clipboard")
        return
    try:
        wx.TheClipboard.SetData(wx.TextDataObject(text))
    finally:
        wx.TheClipboard.Close()
    self._flash_button(self.copy_btn, "Copied!", "Cop&y to clipboard")
```

Label-flip helpers:

```python
def _flash_button(self, btn, temp_label, revert, ms=2000):
    btn.SetLabel(temp_label)
    btn.GetParent().Layout()
    wx.CallLater(ms, self._revert_button_label, btn, revert)

def _revert_button_label(self, btn, revert):
    if btn:
        btn.SetLabel(revert)
        btn.GetParent().Layout()
```

`wx.CallLater` is non-blocking; dialog remains responsive during the 2 s window. The `if btn` guard defends against post-destroy firings (the timer could still fire after the user clicks Close).

## Section 3 — Tests (TDD)

Two new test files, red-green-refactor.

**1. `tests/test_alert_dialog_copy_text.py`** — pure, no wx.

- `_copy_payload(alert, settings)` returns the same string as `_build_combined_text(alert, settings)`.
- Given a realistic alert, the payload contains the headline, description, instruction, `Issued:`, `Expires:`.
- Given the same alert, the payload is byte-identical regardless of whether `settings.alert_display_style == "separate"` or `"combined"`.

**2. `tests/test_alert_dialog_copy_integration.py`** — wx, reuses the `hidden_parent` fixture pattern from `test_alert_dialog_dispatch.py`.

- Construct dialog in both modes: `dlg.copy_btn` exists, id is `wx.ID_COPY`, label is `"Cop&y to clipboard"`, SetName is set.
- Call `dlg._on_copy(None)`; open `wx.TheClipboard`; read back `wx.TextDataObject`; assert text equals `AlertDialog._copy_payload(alert, settings)`.
- Assert `dlg.copy_btn.GetLabel() == "Copied!"` synchronously after the call.
- Failure path: monkey-patch `wx.TheClipboard.Open` to return `False`; call `_on_copy`; assert label flips to `"Copy failed"`, no exception. Restore the patch.

**What is deliberately NOT tested:**

- The 2 s `wx.CallLater` revert — timer-based assertions are flaky and the revert is a leaf detail.
- NVDA/JAWS announcement — no automated hook in the harness.
- `Alt+Y` accelerator routing — trusting wx.

## Section 4 — Manual check

Task 7's eyeball checklist grows one line per mode:

- In separate mode: click Copy, paste into Notepad, confirm the pasted block matches what the combined view shows.
- In combined mode: same thing; confirm identical paste to the separate-mode paste.
- Hold clipboard elsewhere (e.g., with a clipboard-locker utility) and click Copy; confirm button flashes "Copy failed" and the app doesn't crash.

---

## Rollout

- Single commit series on `feature/alert-copy-button` → PR to `dev`.
- CHANGELOG bullet: "You can now grab the whole alert — headline, details, instructions, timestamps — in one click with the new Copy to clipboard button in the alert dialog. Works the same whether you use separate fields or the combined view."

## Future work (out of scope)

- Copy buttons on other read-heavy dialogs (forecast discussion, air quality, aviation weather). Would use the same pattern if requested.
- A per-user preference for copy format (plain vs Markdown). Additive later if someone wants it.
