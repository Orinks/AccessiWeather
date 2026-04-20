---
date: 2026-04-20
topic: nws-text-products-registry
---

# Forecast Products Dialog (AFD + HWO + SPS)

> **Phase 0 dependency:** This feature bundles in one PR with [Zone Metadata Enrichment](2026-04-20-zone-metadata-enrichment-requirements.md). Phase 0 captures `cwa_office` per saved location; this feature is the first user-visible consumer. Together they form **PR 1**.

## Problem Frame

AccessiWeather's screen-reader-first users get forecaster reasoning today only via the per-location **Discussion dialog** (Area Forecast Discussion, hereafter **AFD**) — one text product, one dialog. Two other per-WFO text products that are equally screen-reader-friendly are invisible to the app:

- **HWO (Hazardous Weather Outlook)** — daily 7-day hazard horizon from the local WFO. Structured probability grid of hazard categories (Day 1 specific hazards for today; Days 2-7 probabilistic outlook). Distinct from AFD: AFD is discursive forecaster reasoning; HWO is structured probable hazards up to a week ahead that don't yet warrant watches/warnings.
- **SPS (Special Weather Statement)** — ad-hoc text advisories below warning/watch threshold. SPS products fall into two populations, verified against live NWS API data:
  - **Event-style SPS** (hail, dense fog, radar-indicated hazards): issued as both `/products/types/SPS` AND CAP alerts on `/alerts/active`. Users already see these via the existing alert stream; the alert's `description` field contains the core meteorological content.
  - **Informational SPS** (fire-weather statements, pollen, multi-zone advisory text, coordination statements): issued as `/products/types/SPS` but NOT as CAP alerts. Example verified: WFO PHI issued a 2000-char fire-weather SPS on 2026-04-16 that never appeared in `/alerts/active`. **These are completely invisible to AccessiWeather users today.**

This feature brings all three products into a tabbed per-location **Forecast Products dialog**. Event-style SPS continue to notify through the existing alert pipeline (no duplication); the tab is the reference surface for both SPS populations. Informational SPS become visible for the first time.

Additionally, the existing AFD dialog's "Plain Language Summary" (AI tl;dr via OpenRouter at [ai_explainer.py](src/accessiweather/ai_explainer.py), consumed by [ui/dialogs/discussion_dialog.py](src/accessiweather/ui/dialogs/discussion_dialog.py)) is reused across all three tabs.

## Requirements

**Data layer**
- R1. Fetch, parse, and cache three NWS text products per saved US location using the `cwa_office` field populated by Phase 0:
  - AFD via `/products/types/AFD/locations/{cwa_office}` — existing async implementation at [weather_client_nws.py:769](src/accessiweather/weather_client_nws.py) (`get_nws_discussion`) already extracts `issuanceTime` for the background-refresh path. Extend this async fetcher (generalize or add siblings — see Outstanding Questions). The sync wrapper at [alerts_and_products.py:150](src/accessiweather/api_client/alerts_and_products.py) is NOT the target — it lacks issuance-time extraction.
  - HWO via `/products/types/HWO/locations/{cwa_office}` (new).
  - SPS via `/products/types/SPS/locations/{cwa_office}` (new). Multiple concurrent SPS products may exist; show all in the tab as numbered entries sorted newest-first.
- R2. Cache TTLs: AFD 1h, HWO 2h, SPS 15min. Cache keyed per `(product_type, cwa_office)`. Planning picks cache layer (extend [cache.py](src/accessiweather/cache.py) with per-key TTL or new per-product cache). `NationalDiscussionService` in [services/national_discussion_service.py](src/accessiweather/services/national_discussion_service.py) does NOT generalize (sync, single-TTL, location-agnostic).
- R3. Background-fetch all three products for **all saved US locations** during the app's existing weather refresh cycle. Enables SPS/HWO notifications across the user's full location set; pre-warms the dialog for instant open. Failure isolation: each `(product_type, location)` fetch runs independently; one failure never cascades to another.
- R4. Fetch is skipped for non-US locations (per Phase 0's `_is_us_location` check in [display/presentation/forecast.py:40-50](src/accessiweather/display/presentation/forecast.py)) and for US locations where `cwa_office` is still null (Phase 0 hasn't populated yet — self-heals on next refresh).

**UI — Forecast Products dialog**
- R5. Rename the existing main-window "Discussion" button to **"Forecast Products"** (updating the menu item label, accessibility-announced label, and `QUICK_ACTION_LABELS` key). The existing Nationwide-dialog branch at [main_window.py:675-686](src/accessiweather/ui/main_window.py) remains unchanged — only the per-location AFD branch's entry point is renamed. Extract a reusable `ForecastProductPanel` wx component (TextCtrl + AI summary button + model info label + issuance-time label); host three instances inside a `wx.Notebook` in the renamed dialog.
- R6. Each tab contains:
  - A single `wx.TextCtrl` (read-only, multi-line, scrollable) showing the **raw product text** as issued by the WFO. No section parsing — wxPython lacks a semantic heading widget that screen readers navigate as HTML `<h2>`. Users read linearly (Say-All) or use arrow/page keys.
  - A **"Plain Language Summary"** button invoking the AI summary flow. `ai_explainer.explain_afd` has an AFD-specific system prompt — planning decides between (a) parallel `explain_hwo` / `explain_sps` methods or (b) refactoring to a generic `explain_text_product(product_type, text, location_name, style)` with a prompt lookup table. Existing `custom_system_prompt` / `custom_instructions` settings apply to all three product types.
  - An issuance-time label: `"Issued: {time}"` converted to the user's OS timezone via `datetime.astimezone()`.
  - For SPS specifically, if multiple products are active: a `wx.Choice` above the TextCtrl lists each product by issuance time / headline; selecting one updates the TextCtrl.
- R7. Tab content states (wx.Notebook does NOT support per-tab disable on Windows — `EnableTab` is AuiNotebook-only; states are communicated via content panel text, not tab label):
  - All three tabs always visible and selectable.
  - **SPS empty (common case, `@graph` is `[]`):** panel displays "No Special Weather Statements currently active for {cwa_office}."
  - **HWO empty (uncommon for active US WFOs; may indicate API failure):** panel displays "Hazardous Weather Outlook not currently available for {cwa_office}." (See Outstanding Questions for distinguishing empty vs. error.)
  - **AFD empty (rare):** panel displays "Area Forecast Discussion not currently available for {cwa_office}."
  - **Fetch failed (API error):** panel displays "Failed to fetch — try again." with a retry button.
  - **`cwa_office` null for selected location:** all three panels display "NWS text products will populate after the next weather refresh."
  - Initial focus on dialog open: AFD tab's TextCtrl. On tab switch: focus moves to the selected tab's TextCtrl.
- R8. Non-US locations: the main-window **"Forecast Products" button is `Disable()`d**. Adjacent `wx.StaticText` below the button reads "NWS products are US-only" (per project memory: accessible labels come from adjacent StaticText, not `SetName` or tooltip). The StaticText is only shown when the selected location is non-US.

**Notifications**
- R9. The existing AFD update notification (via [notifications/notification_event_manager.py](src/accessiweather/notifications/notification_event_manager.py), gated by `notify_discussion_update`) is preserved: content, notification logic, issuance-time tracking, and AI summary behavior are all unchanged. Only the entry-point label rename (R5) is a user-visible AFD-related change.
- R10. Two new notification streams with per-stream Settings toggles in [ui/dialogs/settings_tabs/notifications.py](src/accessiweather/ui/dialogs/settings_tabs/notifications.py):
  - `notify_hwo_update` — fires when HWO content changes between fetches. **Default ON** (HWO is distinct from AFD: structured 7-day hazard grid vs. discursive reasoning; daily cadence is an acknowledged tradeoff).
  - `notify_sps_issued` — fires when a new SPS product appears that does NOT have a corresponding active Special Weather Statement alert on `/alerts/active` (deduping against the alerts pipeline). **Default ON** (the value is Case B — informational SPS that never reach the alerts feed). Dedupe rule: at SPS fetch time, if an active alert exists with `event == "Special Weather Statement"` AND its zones/affected area intersect the SPS product's scope, suppress the notification; the alert pipeline already surfaces it.
  - Settings section intro text must be updated — currently reads "These are optional updates beyond standard alerts and are off unless you turn them on," which would be factually wrong with both defaults ON. New text spells out the asymmetric behavior.
  - Cold-start / first-fetch policy: the first time we see content for a product type on a location, store the baseline silently — do NOT notify. Matches existing AFD pattern at `notification_event_manager.py:427-435`. Covers app first install, long absence, newly added locations.
  - A conservative per-stream rate limit (suggested: 30 min per product type per location) prevents storms after prolonged absence. The existing alert rate-limiter applies to alerts only, not product-update events — planning sets the exact per-stream value.
  - `NotificationState` gains `last_hwo_issuance_time`, `last_hwo_text`, `last_sps_issuance_time`, `last_sps_product_id` fields — additive, backward-compatible via defensive `.get()`. The [runtime_state.py](src/accessiweather/runtime_state.py) translation layer (`_runtime_section_to_legacy_shape` / `_legacy_shape_to_runtime_section`) and `_DEFAULT_RUNTIME_STATE` gain parallel `hwo` and `sps` sub-sections. No `schema_version` bump.
- R11. Notification content follows existing `format_accessible_message` pattern.
  - **SPS notifications** source the headline from the NWS product metadata `headline` field when present, falling back to the first non-empty line of `productText` when `headline` is null. Body format: `"{headline} — {cwa_office}"`. 160-character budget (Windows toast constraint); truncate with ellipsis.
  - **HWO update notifications** use the existing `summarize_discussion_change` pattern adapted for HWO's structured grid if feasible, else generic "Hazardous Weather Outlook updated for {cwa_office} — tap to view."

## Success Criteria

- A US user opens Forecast Products and sees three tabs pre-populated with the latest AFD, HWO, and (if any) active SPS products for their location's CWA office. No perceptible load time on open.
- A user receives a desktop notification when their WFO issues an informational SPS that is NOT in the alerts feed (verified against the Case B example: a fire-weather SPS that appears on `/products/types/SPS` but not `/alerts/active`).
- A user does NOT receive duplicate notifications when their WFO issues an event-style SPS that IS also in the alerts feed — the alert pipeline handles it, the Registry dedupes.
- An SPS tab with no active advisories displays "No Special Weather Statements currently active for {cwa_office}" — users understand nothing is active, not that the feature is broken.
- AFD content, notification, issuance-time tracking, and AI summary behavior are unchanged; only the entry-point button/menu label is renamed.
- A non-US user sees the main-window Forecast Products button as `Disable()`d with an adjacent StaticText "NWS products are US-only" announced by screen readers.
- After closing the app for 18 hours and reopening, the user sees no notification storm — first-fetch baseline stores silently; only genuinely unseen changes fire within the rate-limit window.
- AI "Plain Language Summary" works on any of the three tabs, translating meteorology jargon into plain English.

## Scope Boundaries

- **Section-parsing / heading-navigation for AFD is NOT in scope.** Raw-blob reading is the default; wxPython doesn't have semantic heading widgets equivalent to HTML `<h2>` navigable via screen-reader H-key.
- **No additional NWS products beyond AFD / HWO / SPS.** Marine text products (CWF, NSH), aviation products, climate summaries are scope for future features (Marine & Water Context, ideation #7).
- **No changes to the Nationwide discussion view.** The `_on_discussion` branch that routes to `NationwideDiscussionDialog` when location name is "Nationwide" is unaffected.
- **No new AI features beyond reusing existing tl;dr on all three tabs.** Per-product prompt routing (parallel methods or generic refactor) is the only `ai_explainer.py` change.
- **Zone metadata beyond `cwa_office` is not consumed.** `county_zone_id`, `fire_zone_id`, `radar_station`, `timezone` captured by Phase 0 are plumbing for other features.
- **No "View full statement" deep-link from alert details.** Verified that SPS alert `description` fields contain the meteorological content already; deep-linking to `productText` for event-style SPS adds little value. Users who want more context use the SPS tab in the dialog.
- **No caching of AI summaries beyond existing in-memory cache.** The `explain_afd` cache behavior applies to the generalized explainer.

## Key Decisions

- **All three products in one tabbed dialog, bundled with Phase 0 as PR 1** — original product instinct. Event-style SPS continue through alerts (no duplication); the tab is reference + discovery for informational (Case B) SPS that would otherwise be invisible.
- **SPS notification dedupes against alerts** — prevents double-notification for Case A SPS while preserving the novel-capability value for Case B. Planning verifies the dedupe check is cheap enough to run per SPS fetch.
- **HWO notification Default ON, SPS notification Default ON** — both deliver distinct value not present today: HWO's 7-day hazard horizon, SPS Case B's informational advisories.
- **Background-fetch all three for all saved US locations** — enables notifications across the user's full location set; pre-warms the dialog.
- **Content panel empty-states instead of disabled tabs** — wx.Notebook doesn't support per-tab disable on Windows.
- **Non-US button disabled with adjacent StaticText reason** — project's accessibility pattern is adjacent StaticText for accessible labels, not tooltip or `SetName`.
- **Extract ForecastProductPanel component, host in wx.Notebook** — avoids state triplication in the existing DiscussionDialog's single-instance AI summary wiring.
- **Raw-blob reading, no heading navigation** — wx desktop apps don't expose StaticText as semantic headings to screen readers the way HTML does.
- **Issuance-time in user OS timezone** — users plan in their own timezone; station-local adds cognitive load without benefit.
- **First-fetch baseline storage (no notify)** — prevents notification storms on fresh install, new locations, post-absence reopen.

## Dependencies / Assumptions

- **Phase 0 Zone Metadata Enrichment** populates `cwa_office` on saved US `Location` records. This Registry is the first user-visible consumer.
- NWS `/products/types/{TYPE}/locations/{CWA}` endpoint shape stable across AFD, HWO, SPS — same `@graph[0].id` → `products/{id}.productText` + `issuanceTime` pattern already used by `get_nws_discussion` at [weather_client_nws.py:769](src/accessiweather/weather_client_nws.py) and verified against live PHI endpoint.
- `/alerts/active?event=Special Weather Statement` returns alerts that, when matched against SPS products by zone/area, reliably identify the Case A subset. Verified SPS products without alerts (Case B: fire-weather) and SPS alerts without matching product listings both exist.
- `NotificationEventManager` state persistence extends backward-compatibly via defensive `.get()` — proven pattern for `last_discussion_issuance_time` at `notification_event_manager.py:208-222`.
- `_DEFAULT_RUNTIME_STATE` in [runtime_state.py:14-37](src/accessiweather/runtime_state.py) gains `hwo` and `sps` sub-sections under `notification_events`; `_runtime_section_to_legacy_shape` and `_legacy_shape_to_runtime_section` (lines 297-340) are updated in parallel. No `schema_version` bump.
- OpenRouter integration at `ai_explainer.py` can be refactored to a generic `explain_text_product` OR extended with parallel methods; either is feasible per the feasibility review.

## Outstanding Questions

### Deferred to Planning

- [Affects R1][Technical] Whether to add `get_nws_hwo` / `get_nws_sps` paired with existing `get_nws_discussion`, OR generalize into `get_nws_text_product(product_type, cwa_office)`. The async path at [weather_client_nws.py:769](src/accessiweather/weather_client_nws.py) is the target.
- [Affects R2][Technical] Cache layer choice — extend `cache.py` with per-key TTL support OR build a new per-product cache.
- [Affects R3][Technical] Integration point for per-location-set background fetch — `_fetch_weather_data` at [main_window.py:1108](src/accessiweather/ui/main_window.py) (active location only) vs. [app_timer_manager.py](src/accessiweather/app_timer_manager.py) (all locations) vs. extending `_pre_warm_other_locations` at `main_window.py:1182`.
- [Affects R6][Technical] AI explainer refactor — add parallel methods OR generic `explain_text_product(product_type, ...)`. Confirm behavior with user-set `custom_system_prompt` / `custom_instructions`.
- [Affects R6][Technical] SPS multi-product `wx.Choice` widget — confirm screen-reader announcement behavior when the selected product changes.
- [Affects R7][Technical] wx.Notebook focus management — `SetFocus()` via `wx.CallAfter` pattern replicated per-tab.
- [Affects R10][Technical] SPS alert-dedupe check — compare SPS product zones against active alerts' `affectedZones`. Planning validates the match is reliable (zone codes should align since both come from NWS) and measures performance cost per fetch.
- [Affects R10][Technical] Per-stream rate limit exact value (suggested 30 min per product type per location).
- [Affects R7][UX] HWO empty-state copy — if observed fetch-success rate approaches 100% for active US WFOs, consider splitting "not yet issued today" vs. "fetch failed" states.
- [Affects R11][UX] HWO update-notification diffing — `summarize_discussion_change` was designed for AFD narrative; applying to HWO's structured grid may produce low-quality summaries. Planning evaluates and falls back to generic wording if needed.
- [Affects R11][UX] SPS expiration — when an active SPS disappears from `@graph`, fire a silent "cleared" state change (no notification) matching the existing discussion-cleared pattern.

## Next Steps
-> `/ce:plan` for the bundled **PR 1**: Phase 0 Zone Metadata Enrichment + Forecast Products Dialog (AFD + HWO + SPS).
