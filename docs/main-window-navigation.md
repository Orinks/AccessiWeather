# Main Window Navigation Reference

This document is the canonical reference for AccessiWeather's current top-level main-window section model. Update it whenever the visible order, focus targets, or jump shortcuts change.

## Canonical top-level order

Visible top-level order:

1. Location selector
2. Current Conditions
3. Hourly Forecast / near-term
4. Daily Forecast
5. Weather Alerts
6. Event Center

This order must stay aligned across:

- visible UI layout
- F6 cycle order
- direct-jump shortcuts
- user-facing docs
- contributor guidance

## Top-level navigation

### F6 cycle

F6 cycles through the visible top-level sections in on-screen order.

Current cycle order:

1. Location selector
2. Current Conditions
3. Hourly Forecast / near-term
4. Daily Forecast
5. Weather Alerts
6. Event Center (when visible)

If Event Center is hidden, F6 skips it.

### Direct jumps

Ctrl+1 through Ctrl+5 jump directly to the main forecast sections:

- Ctrl+1 → Current Conditions
- Ctrl+2 → Hourly Forecast / near-term
- Ctrl+3 → Daily Forecast
- Ctrl+4 → Weather Alerts
- Ctrl+5 → Event Center

If Event Center is hidden, Ctrl+5 does nothing until the user enables View > Event Center again.

## Focus targets

Each section jump should land on the primary readable control for that section:

- Location selector → location dropdown
- Current Conditions → current conditions text region
- Hourly Forecast / near-term → hourly forecast text region
- Daily Forecast → daily forecast text region
- Weather Alerts → alerts list
- Event Center → event center text region

## Event Center behavior

The Event Center is:

- embedded in the main window
- visible by default
- toggleable from View > Event Center
- a read-only multiline review surface with plain timestamped entries

When visible:

- it participates in F6 cycling
- Ctrl+5 focuses it

When hidden:

- F6 skips it
- Ctrl+5 does nothing
- the View menu checkbox controls whether it is shown again

## What gets logged

The Event Center is intended for user-facing reviewable text, not internal debug state.

Current first-pass contents include:

- mobility briefings and spoken/surfaced summaries
- reviewable notification or event text that the app surfaces to the user

Entries should preserve the same user-facing wording, or a very close reviewable equivalent.

## Hourly / near-term behavior

The Hourly Forecast / near-term section may include a one-sentence mobility briefing for roughly the next 90 minutes.

When present:

- the mobility briefing appears at the top of the hourly section
- the regular hourly outlook summary remains below it

This means the mobility briefing supplements the hourly outlook instead of replacing it.
