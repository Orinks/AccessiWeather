# AccessiWeather UI Accessibility Guide

The desktop UI lives in `rust/crates/aw-app/src/ui/` and uses wxDragon
(wxWidgets) native controls. Screen reader announcements go through
`rust/crates/aw-app/src/screen_reader.rs`, backed by prism/prismer.

## Controls and labels

- Give every interactive control a clear visible label and a useful accessible name.
- Use native controls rather than drawing replacements for buttons, lists, or text fields.
- Keep labels specific: say what an input accepts and what a button does.
- Keep control order consistent with Tab and Shift+Tab navigation.

The Add Location dialog in
[`location_dialog.rs`](../rust/crates/aw-app/src/ui/location_dialog.rs)
sets names with the wxDragon `set_name` API:

```rust
name_input.set_name("Location name input");
search_input.set_name("Search for a city, town, postal code, or coordinates");
results.set_name("Search results");
```

These statements illustrate existing controls in that dialog, not a standalone program.

## Focus and keyboard interaction

Choose an intentional initial focus when opening a dialog, using `set_focus()`.
For example, Add Location focuses its name field. On validation failure,
return focus to the field that needs correction. Preserve standard dialog
confirmation and cancellation behavior, and check that closing a dialog returns
the user to a useful place in its parent.

Every action needs a keyboard route. Check Tab, Shift+Tab, arrow keys, Enter,
Escape, menu accelerators, and shortcuts where applicable. See the
[User Manual](user_manual.md) for the app's current shortcuts.

## Announcements

Use `crate::screen_reader::announce(text)` for status that is not otherwise
conveyed by the focused control. It ignores empty text and does nothing when
no backend is available. Keep messages brief and avoid announcing the same
change both as a focus event and as a separate status message.

Do not make audio cues the only way to communicate a warning or result.
Keep the corresponding text available in the UI.

## Verification

1. Open each changed dialog and check its initial focus.
2. Complete its workflow without a pointer.
3. Check names, values, selection changes, validation errors, and status messages
   with a screen reader on the target platform.
4. Check that long labels, larger fonts, and resized windows do not hide controls.
5. Confirm focus after closing or cancelling the dialog.

A successful build or smoke test does not verify screen reader output.
Use the Cargo commands in [TESTING.md](../TESTING.md) for automated checks
and record manual platform checks separately.
