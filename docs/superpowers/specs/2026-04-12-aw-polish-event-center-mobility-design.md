# AccessiWeather polish design: Event Center, section jumps, and near-term mobility briefing

Date: 2026-04-12
Project: AccessiWeather
Status: Draft design approved in chat, written for review

## Summary

This design focuses AccessiWeather polish on presentation, prioritization, and reviewability rather than adding broad new feature surface. The first wave adds a PortkeyDrop-style, toggleable Event Center to the main window, plus stable section-jump keyboard navigation. The second wave adds one speech-first 90-minute mobility briefing that answers the practical question blind users often need most: whether it is a good time to leave now or shortly.

The later waves add a short confidence/disagreement line and contextual hazard cards only when those signals are relevant. Documentation and contributor guidance are updated alongside the UI changes so visible labels, section order, and shortcut behavior stay aligned with the real application instead of drifting into stale docs.

## Goals

1. Ensure important spoken alerts and summaries are always reviewable after the fact.
2. Make the main window faster to navigate by keyboard and screen reader.
3. Provide one compact near-term mobility briefing covering the next 90 minutes.
4. Surface confidence/disagreement and hazard context only when they materially help decision-making.
5. Tighten docs so contributors and agents work from the app's actual UI model and real labels.

## Non-goals

1. Do not add a new standalone briefing window.
2. Do not build a complex filtered log browser in the first pass.
3. Do not expose raw model-comparison detail screens.
4. Do not add persistent hazard panels that always occupy space even when irrelevant.
5. Do not attempt a repo-wide documentation rewrite beyond the touched UI areas.

## Current context

The current codebase already contains useful groundwork:

- AccessiWeather has notification-heavy recent work, increasing the value of a reviewable spoken/event history.
- A history shortcut already exists, which suggests the app already accepts the idea of revisiting prior information.
- Forecast confidence plumbing already exists in the weather client layer.
- Display prioritization logic already includes themes tied to flood, fog, smoke, and visibility.
- Open-Meteo, Pirate Weather, and Visual Crossing already expose much of the near-term weather data needed for a short mobility briefing.
- Existing accessibility docs are partially outdated in architecture assumptions and do not yet serve as a precise canonical map of the real top-level UI model.

## Canonical top-level section model

This design introduces and documents one canonical section order for the main window. The visible labels and docs must match this order exactly.

1. Current conditions
2. Hourly / near-term
3. Daily forecast
4. Alerts
5. Event Center

This order is the basis for:

- F6 section cycling
- Ctrl+1 through Ctrl+5 direct jumps
- visible UI ordering
- docs and contributor guidance
- screen reader expectations

If the Event Center is hidden, it is removed from F6 traversal until shown again.

## Feature 1: Reviewable Event Center

### UX

AccessiWeather gains a PortkeyDrop-style Event Center embedded in the main window. It is visible by default, but toggleable on and off by the user like PortkeyDrop's activity log panel.

The first implementation uses a read-only multiline text control with plain timestamped lines appended at the bottom. This is intentionally simple and screen-reader-stable.

### Day-one contents

On first release, the Event Center records only:

1. spoken alerts / notifications
2. spoken summaries / briefings

It does not yet attempt to record every internal state change, source swap, or refresh event. The goal is to preserve user-relevant spoken output, not to become a debug console.

### Event entry format

Event entries are plain text lines with timestamps, appended in chronological order. Example:

[6:05 PM] Alert: Severe thunderstorm warning until 6:45 PM.
[6:07 PM] Briefing: Dry for 35 minutes, then light rain likely; gusts increase after 6:30 PM; visibility stays good; thunder risk low.

No grouping, filtering, category chips, or reverse-chronological ordering is required in the first pass.

### Behavior rules

- The Event Center is part of the normal main-window layout, not a separate dialog.
- The panel can be shown or hidden by the user.
- When visible, it participates in top-level navigation.
- When hidden, F6 skips it.
- Ctrl+5 should reveal and focus the Event Center if it is hidden.
- Spoken alerts and spoken summaries should be written to the Event Center using the same user-facing text, or a very close reviewable equivalent.

### Why this shape

This follows the strongest PortkeyDrop lesson: spoken information should be reviewable without forcing users into a separate workflow. A simple embedded pane is lower risk and more discoverable than a dedicated history dialog.

## Feature 2: Section-jump navigation

### Keyboard model

AccessiWeather adds two complementary top-level navigation mechanisms:

1. F6 cycles through the visible top-level sections in on-screen order.
2. Ctrl+1 through Ctrl+5 jump directly to top-level sections.

Number mapping must follow the visible order exactly:

- Ctrl+1: Current conditions
- Ctrl+2: Hourly / near-term
- Ctrl+3: Daily forecast
- Ctrl+4: Alerts
- Ctrl+5: Event Center

### Focus behavior

Each jump should move focus to a reliable control or focus target inside the destination section. If a section is represented by a composite region, the app should focus the section's primary readable widget, not a random nested control.

The F6 cycle should always respect the real visible order, not an internal historical ordering.

### Hidden Event Center behavior

If the Event Center is hidden and the user presses Ctrl+5, the app should reveal the Event Center and move focus into it. This is better than announcing a dead destination because it keeps the shortcut meaningful and learnable.

## Feature 3: 90-minute mobility briefing

### Product goal

The mobility briefing is the strongest user-facing improvement because it gives blind users the same practical departure-timing advantage that charts often give sighted users.

The question it answers is not "what is all the weather data?" but "what matters for the next 90 minutes if I am deciding whether to leave now or soon?"

### Placement

The mobility briefing belongs in the Hourly / near-term area. It is not a separate window or mode.

It should also be eligible to be spoken and written to the Event Center.

### Output style

The briefing should be one concise, speech-first summary. Example:

"Dry for 35 minutes, then light rain likely; gusts increase after 6 PM; visibility stays good; thunder risk low."

It should suppress irrelevant items rather than reading a rigid template.

### Source fallback order

For minute-level or sub-hourly generation, use this fallback order:

1. Pirate Weather
2. Open-Meteo
3. Visual Crossing

If minute-level or sub-hourly data is weak or unavailable, degrade gracefully to the best available near-term/hourly summary.

### First-pass content scope

The 90-minute mobility briefing should only mention items that directly affect near-term mobility:

- precipitation start / stop timing
- meaningful precipitation intensity changes
- wind or gust worsening
- visibility degradation or staying good
- thunder risk when relevant

It should not try to narrate every modeled field. Marine/coastal, flood, smoke, or fire specifics belong primarily to the later hazard-card phase unless they materially affect the 90-minute mobility message itself.

### Briefing generation principles

- Prefer one high-value sentence over a checklist.
- Mention timing when known.
- Mention worsening changes, not static values alone.
- Omit categories that are steady and unimportant.
- Preserve graceful degradation when only hourly or partial data is available.

## Feature 4: Confidence / disagreement line

### UX

AccessiWeather adds a short, explanation-first confidence line near the relevant forecast summary. This should not be a separate model comparison view.

Example output:

- Confidence: High
- Confidence: Moderate — precipitation timing differs between sources
- Confidence: Low — sources disagree on rain timing and wind increase

### Purpose

The goal is to help users understand when the near-term forecast is straightforward versus when source disagreement makes it less certain. The line should explain the reason for lower confidence in plain language.

### Scope

This feature comes after Event Center, navigation, and the mobility briefing. It should reuse the existing confidence plumbing where possible instead of introducing a parallel scoring system.

## Feature 5: Contextual hazard cards

### UX

Hazard cards appear only when relevant. They are not persistent clutter and should not duplicate the entire forecast.

Initial hazard classes:

- storm proximity / thunder concern
- smoke / fire / air-quality visibility concern
- flood / flash flood concern
- marine / coastal concern

### Content rules

Each hazard card should answer:

- what the risk is
- why it matters now
- what time window matters, if known

### Priority

Hazard cards come after:

1. Event Center
2. section-jump navigation
3. mobility briefing
4. confidence/disagreement line

That keeps the early work focused on broadly useful presentation improvements before more conditional hazard surfacing.

## Accessibility and interaction requirements

1. The Event Center must be screen-reader readable as a standard multiline read-only text region.
2. F6 and Ctrl+1 through Ctrl+5 must be documented with exact labels and exact section order.
3. Docs must match visible UI labels and ordering exactly.
4. Any new quick navigation or action labels touched during this work should be reviewed for user-facing clarity.
5. The implementation should prefer stable, predictable focus targets over clever navigation logic.

## Documentation requirements

The design requires a canonical contributor-facing reference for the real top-level UI model that covers:

- visible top-level section names
- top-level section order
- F6 cycle behavior
- Ctrl+1 through Ctrl+5 destinations
- Event Center behavior
- what gets spoken and what gets logged

The existing documentation should be updated only where needed to keep touched areas truthful. This is not a full-docs rewrite, but the touched docs must be made accurate.

The docs cleanup should also include review of overly vague quick-action labels in the touched UI surfaces, since mismatched or unclear labels make both accessibility and contributor guidance worse.

## Recommended implementation order

1. Introduce a canonical top-level section model and documented order.
2. Add the toggleable main-window Event Center pane.
3. Route spoken alerts and spoken summaries into the Event Center.
4. Add F6 visible-section cycling.
5. Add Ctrl+1 through Ctrl+5 direct jumps using the canonical order.
6. Add the 90-minute mobility briefing in the Hourly / near-term area.
7. Add a short confidence/disagreement line near the relevant forecast summary.
8. Add contextual hazard cards only when relevant.
9. Update docs and contributor guidance for the touched areas as part of each phase, not all at the end.

## Testing strategy

### Event Center

- Verify spoken alerts are appended to the Event Center.
- Verify spoken summaries / briefings are appended to the Event Center.
- Verify append order is chronological.
- Verify toggle off hides the pane.
- Verify toggle on restores it.
- Verify Ctrl+5 reveals and focuses the Event Center when hidden.

### Section navigation

- Verify F6 cycles only through visible sections.
- Verify F6 order matches on-screen order.
- Verify Ctrl+1 through Ctrl+5 map to the documented sections exactly.
- Verify the destination focus target is useful and screen-reader stable.

### Mobility briefing

- Verify the briefing appears in the near-term area.
- Verify irrelevant categories are omitted.
- Verify fallback order behaves as designed when minute/sub-hourly data is partial.
- Verify the spoken briefing text is suitable for Event Center capture.

### Confidence / disagreement

- Verify high-confidence cases do not over-explain.
- Verify disagreement cases mention the actual reason in plain language.
- Verify placement is near the relevant summary rather than in an isolated diagnostics area.

### Hazard cards

- Verify cards appear only when relevant.
- Verify they communicate risk, relevance, and timing.
- Verify they do not duplicate the whole forecast.

### Documentation

- Verify docs match the visible labels and order exactly.
- Verify shortcut docs match real runtime behavior.
- Verify contributor guidance references the app's real UI model rather than outdated assumptions.

## Risks and mitigations

### Risk: Event Center becomes noisy
Mitigation: day-one scope is limited to spoken alerts and spoken summaries only.

### Risk: navigation shortcuts drift from actual UI order
Mitigation: define one canonical section order and make shortcuts/docs derive from it.

### Risk: mobility briefing becomes verbose or chart-like
Mitigation: constrain it to the departure-timing question for the next 90 minutes.

### Risk: confidence line becomes model trivia
Mitigation: keep it explanation-first and user-facing, not diagnostic.

### Risk: hazard surfacing adds clutter
Mitigation: show hazard cards only when contextually relevant.

## Open follow-up items intentionally deferred

These are acknowledged but not required for the first implementation slice:

- richer Event Center filtering and grouping
- broader event capture beyond spoken alerts and summaries
- deeper review of quick action labels outside the touched UI surfaces
- more advanced hazard ranking or per-region hazard configuration

## Recommendation

Implement the work as a user-visible polish sequence anchored by a very small shared model:

- one canonical top-level section order
- one simple Event Center entry format
- one near-term mobility briefing output shape

That keeps the first pass practical, accessible, and easy to document while leaving room for later refinement without redoing the interaction model.
