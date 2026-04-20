---
title: "PR 1: Zone Metadata Enrichment + Forecast Products Dialog (AFD + HWO + SPS)"
type: feat
status: active
date: 2026-04-20
origin:
  - docs/brainstorms/2026-04-20-zone-metadata-enrichment-requirements.md
  - docs/brainstorms/2026-04-20-nws-text-products-registry-requirements.md
ideation: docs/ideation/2026-04-20-api-endpoints-ideation.md
---

# PR 1: Zone Metadata Enrichment + Forecast Products Dialog (AFD + HWO + SPS)

## Overview

PR 1 is one bundled shipping moment delivering two tightly-coupled changes:

- **Phase A — Zone Metadata Enrichment** (data layer): saved `Location` records gain six NWS zone fields captured at save-time from `/points`, lazily drift-corrected on each weather refresh, and reused by the alert-fetch path. Fields: `forecast_zone_id`, `cwa_office`, `county_zone_id`, `fire_zone_id`, `radar_station`, `timezone`. Edit Location exposes two of them read-only; the rest are plumbing.
- **Phase B — Forecast Products Dialog** (first visible consumer): the existing per-location "Discussion" button becomes "Forecast Products", opening a three-tabbed dialog with AFD, HWO, and SPS. Background fetch across all saved US locations pre-warms the dialog and drives two new notification streams (HWO updates, informational SPS) with alert-dedupe against the existing alert pipeline.

Phase A on its own is invisible; Phase B is the feature. Bundling makes drift correction testable end-to-end and gives us one release cycle, one user-visible changelog entry.

## Problem Frame

Screen-reader-first users get forecaster reasoning today only via the single-product Discussion dialog (AFD). Two equally text-friendly per-WFO products are completely missing:

- **HWO**: structured 7-day hazard horizon, updated roughly daily.
- **SPS**: ad-hoc advisories. Live-API verification confirmed two populations — event-style SPS (hail, dense fog) already appear on `/alerts/active` and users see them today; **informational SPS** (fire-weather, pollen, coordination statements) appear on `/products/types/SPS` but never on `/alerts/active` and are invisible to AccessiWeather users. Verified example: WFO PHI issued a 2000-char fire-weather SPS on 2026-04-16 that never reached the alerts feed.

Separately, NWS zone identifiers (`cwa`, `forecastZone`, etc.) are resolved from lat/lon on every refresh and immediately discarded — `_transform_point_data` at `src/accessiweather/api/nws/point_location.py:86-141` explicitly strips `cwa` and `forecastZone`. Any per-location feature that needs the CWA office (like Forecast Products) has to re-derive it by parsing URLs out of grid data. Persisting zone metadata on the `Location` record removes this friction and unlocks both PR 1 and downstream features (Marine Context, fire-weather products, climatology).

## Requirements Trace

Phase A (Zone Enrichment):
- **A-R1.** On save of a new US location, fetch `/points` once and persist six `Optional[str]` zone fields on the `Location` record.
- **A-R2.** Non-US locations never attempt NWS zone resolution; fields stay null.
- **A-R3.** `/points` failure at save-time never blocks the save; fields stay null, debug-logged.
- **A-R4.** Each successful refresh-time `/points` response drift-corrects stored fields: null → populate; differing non-null → overwrite; missing/null fresh value → no update. Persisted via main-thread bounce.
- **A-R5.** Locations saved before this feature populate opportunistically via A-R4; no migration step.
- **A-R6.** Alert fetch uses stored `county_zone_id` / `forecast_zone_id` when present; falls back to fresh resolution when null.
- **A-R7.** Forecast Products Dialog consumes stored `cwa_office` (no extra resolution).
- **A-R8.** Edit Location dialog gains a read-only "NWS Zone Information" section showing `forecast_zone_id` and `cwa_office`.
- **A-R9.** Null/non-US states in Edit Location render without noise per spec.

Phase B (Forecast Products):
- **B-R1.** Fetch, parse, and cache AFD / HWO / SPS per saved US location with populated `cwa_office` via a generalized `get_nws_text_product(product_type, cwa_office)` async fetcher.
- **B-R2.** Per-product TTLs via the existing `Cache` layer: AFD 3600s, HWO 7200s, SPS 900s. Keys: `nws_text_product:{product_type}:{cwa_office}`.
- **B-R3.** Background-fetch all three products for every saved US location during the existing refresh cycle; failure isolation per `(product_type, location)`.
- **B-R4.** Skip fetch for non-US locations and US locations where `cwa_office` is still null (self-heals after next refresh).
- **B-R5.** Rename per-location "Discussion" → "Forecast Products" (button, menu, `QUICK_ACTION_LABELS`). Nationwide branch unchanged.
- **B-R6.** Dialog is a `wx.Notebook` hosting three `ForecastProductPanel` instances. Per-tab: raw-product `wx.TextCtrl`, AI "Plain Language Summary" button (hidden-until-clicked per existing design), issuance-time `wx.StaticText`, SPS `wx.Choice` for multi-product selection.
- **B-R7.** Empty-state and error-state copy rendered in content panels (tabs always visible; `wx.Notebook` lacks per-tab disable on Windows).
- **B-R8.** Non-US locations: main-window "Forecast Products" button `Disable()`d with adjacent `wx.StaticText` "NWS products are US-only".
- **B-R9.** Existing AFD notification (content, logic, cold-start baseline) unchanged.
- **B-R10.** Two new notification streams: `notify_hwo_update` (default ON), `notify_sps_issued` (default ON). SPS dedupes against `/alerts/active` by zone intersection.
- **B-R11.** Notification content: SPS uses `headline` with `productText` fallback; HWO attempts `summarize_discussion_change` and falls back to generic copy.

## Scope Boundaries

- Raw-blob reading only — no semantic heading navigation for AFD; wxPython doesn't expose `StaticText` as HTML-`<h2>`-equivalent to screen readers.
- No NWS products beyond AFD / HWO / SPS (marine CWF/NSH/OFF, aviation, climate → future features).
- No changes to Nationwide discussion view; the `"Nationwide"` branch of `_on_discussion` is untouched.
- No AI features beyond reusing existing tl;dr per-tab.
- Zone metadata beyond `cwa_office` (county, fire, radar, timezone) is captured but not surfaced in UI this release.
- No "View full statement" deep-link from alert details (SPS alert `description` already carries the content).
- No marine-mode auto-activation (deferred to Marine & Water Context Module).
- Single-hash alert state bug (`docs/alert_audit_report.md` §3) and hour-boundary rate-limit burst (§7) are NOT fixed here; coordinated separately. PR 1 follows the §7 guidance by using a sliding-window rate limit for new product streams, not a calendar-hour counter.
- No config `schema_version` bump; defensive `.get()` with defaults matches the existing `country_code` / `marine_mode` precedent.
- No manual "Refresh zone data" button.

### Deferred to Separate Tasks

- `ConfigManager.save_config` in-process locking (research flagged it has no lock; PR 1 mitigates via `wx.CallAfter` main-thread bounce): track as follow-up issue.
- Marine zone ID capture: deferred until the Marine & Water Context Module lands; it requires an additional NWS call outside the `/points`-already-fetched pass.

## Context & Research

### Relevant Code and Patterns

- **Location model**: `src/accessiweather/models/weather.py:124-141`. Field-addition precedent: `country_code`, `marine_mode`.
- **Config round-trip**: `src/accessiweather/models/config.py:700-745`. Pattern: conditional spread on serialize, defensive `.get()` on deserialize.
- **LocationOperations template**: `src/accessiweather/config/locations.py:59-70` (`update_location_marine_mode` is the lazy-update analogue).
- **Point transform pinch-point**: `src/accessiweather/api/nws/point_location.py:86-141`. `_transform_point_data` strips `cwa`, `forecastZone`, `gridId` — must be extended, or a sibling method added.
- **NWS async fetcher**: `src/accessiweather/weather_client_nws.py:769-844` (`get_nws_discussion`). Shape to generalize.
- **Alert callers using `/points`**: `src/accessiweather/weather_client_nws.py:873-941` (county path, zone path).
- **Cache**: `src/accessiweather/cache.py:46-165`. `Cache.set(key, value, ttl=N)` already supports per-key TTL; no new cache class needed. `WeatherAlert` cache at `:422-455` drops `affectedZones` (bad for SPS dedupe — extend additively).
- **NationalDiscussionService**: `src/accessiweather/services/national_discussion_service.py:55-85`. Single-TTL, location-agnostic — NOT generalizable for multi-location AFD/HWO/SPS. Untouched.
- **Timer infrastructure**: `src/accessiweather/app_timer_manager.py:121-158` (two timers — full refresh + lightweight event-check). Product notifications piggyback on the existing notification-event path; no third timer.
- **Multi-location pre-warm**: `src/accessiweather/ui/main_window.py:1273-1290` (`_pre_warm_other_locations`). Extend to also fetch the three products per US location with populated `cwa_office`.
- **Active-location fetch**: `src/accessiweather/ui/main_window.py:1108-1186` (`_fetch_weather_data`). Add product fetch + notification check after weather-data success.
- **Main-window entry point**: `src/accessiweather/ui/main_window.py:674-686` (`_on_discussion`). Non-Nationwide branch becomes `_on_forecast_products`; Nationwide branch unchanged.
- **Labels registry**: `src/accessiweather/ui/main_window.py:31-40` (`QUICK_ACTION_LABELS`). Single-line rename propagates.
- **Notifications state & cold-start**: `src/accessiweather/notifications/notification_event_manager.py:182-222` (`NotificationState`), `:404-455` (`_check_discussion_update` cold-start pattern), `:427-435` (first-fetch baseline silent store).
- **Runtime state**: `src/accessiweather/runtime_state.py:14-37` (`_DEFAULT_RUNTIME_STATE`), `:297-340` (section converters). All three must be updated in parallel or state round-trips silently drop fields.
- **AI explainer**: `src/accessiweather/ai_explainer.py:746-941` (`explain_afd`). Does NOT cache results today (`explain_weather` does, pattern at `:741`). Refactor introduces caching.
- **Existing dialog template**: `src/accessiweather/ui/dialogs/discussion_dialog.py`. Shape to adapt — per-tab mirrors its content area; AI visibility follows `docs/superpowers/specs/2026-04-08-discussion-dialog-ai-visibility-design.md` (hidden until Explain clicked; Explain/Regenerate mutually exclusive; error fills the AI box rather than hiding it).
- **Nationwide notebook precedent**: `docs/nationwide_discussions.md` — nested `wx.Notebook` with per-tab `wx.TextCtrl(style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)`.
- **Edit Location dialog**: `src/accessiweather/ui/dialogs/location_dialog.py:81-125`. Fixed `size=(420, 200)` at `:89` — must switch to Fit-based or content clips.
- **Settings notifications tab**: `src/accessiweather/ui/dialogs/settings_tabs/notifications.py:110-125` (existing `notify_discussion_update` section). New toggles mirror that shape; intro copy must be rewritten (two defaults become ON).
- **US detection**: `src/accessiweather/display/presentation/forecast.py:40-51` (`_is_us_location`).
- **Test conventions**: `tests/conftest.py:19-100` — wx stub via `_WxStubBase`; no Toga backend despite stale CLAUDE.md text. Flat `tests/test_*.py`; `tests/gui/` for GUI-specific. Pattern mock: `test_dialog_accessibility.py`.

### Institutional Learnings

- **Hour-boundary rate-limit burst** (`docs/alert_audit_report.md` §7): calendar-hour reset causes bursts at the top of the hour. PR 1's per-stream rate limit uses a sliding window (timestamp comparison), not calendar buckets.
- **Single-hash alert state** (`docs/alert_audit_report.md` §3): don't reduce SPS dedupe to a single-value hash; keep the richer `last_sps_product_ids` collection shape.
- **AFD cold-start pattern** (`notification_event_manager.py:427-435`): first-fetch stores baseline silently via defensive `.get()`. Reused verbatim for HWO and SPS.
- **Runtime-state parallel update rule**: every new `notification_events` sub-key must appear in `_DEFAULT_RUNTIME_STATE` **and** both section converters (`_runtime_section_to_legacy_shape`, `_legacy_shape_to_runtime_section`) or round-trips silently drop data.
- **Location additive-field precedent**: `country_code`, `marine_mode` were added without `schema_version` bumps; PR 1 follows identically for six new Optional[str] fields.
- **Accessibility pattern**: adjacent `wx.StaticText` is what screen readers announce. `SetName()` is ignored. Use descriptive widget-level `label=` strings plus adjacent StaticText for context.

### External References

Not used. Repo patterns are thick; brainstorms were already grounded in live-API probes (PHI fire-weather SPS). External research would add no practical value.

## Key Technical Decisions

- **Bundle Phase A + Phase B as PR 1** — Phase A alone has no visible value; bundling gives drift correction an end-to-end testable consumer and one release cycle.
- **Extend `_transform_point_data` to expose all six zone fields** (not a parallel raw-response path) — single source of truth; cleaner integration; reuses existing URL-extraction helpers at `point_location.py:145-205`.
- **Alert-path integration at the call-site** (`weather_client_nws.py:873-941`), not inside `point_location.py` — county and zone paths are different shapes; call-site branching is clearer than wrapping the helper.
- **Drift persistence via `wx.CallAfter` bounce to main thread** — `ConfigManager.save_config` has no in-process lock (research finding); the main-thread bounce is the simplest correct fix for PR 1. A proper `threading.Lock` on `ConfigManager` is deferred to a separate task.
- **Edit Location dialog: switch to Fit-based sizer with `SetMinSize((420, -1))`** — fixed `size=(420, 200)` clips with added rows. Fit-based protects future row additions.
- **Zone info grouped in `wx.StaticBox` "NWS Zone Information"**, placed after marine-mode checkbox, before OK/Cancel. Non-focusable StaticText rows, skipped by Tab.
- **Edit-Location drift reflection: snapshot-at-open** — live mutation of an open dialog risks focus/accessibility regressions for no observable win.
- **Generalize to `get_nws_text_product(product_type, cwa_office)`** in `weather_client_nws.py`; keep `get_nws_discussion` as a thin wrapper for call-site backward compat — the three endpoints share shape, parallel methods would triplicate code.
- **Reuse existing `Cache` with per-key TTL** (keys `nws_text_product:{product_type}:{cwa_office}`) — no new cache class; `Cache.set(..., ttl=N)` already supports this.
- **Background fetch: extend `_pre_warm_other_locations` for non-active locations and add a product-fetch step to `_fetch_weather_data` for the active location** — piggybacks on the existing multi-location iteration; `app_timer_manager.py` stays product-agnostic.
- **AI explainer: add `explain_text_product(product_text, product_type, location_name, ...)` with a prompt lookup table**; make `explain_afd` a thin wrapper. Add per-product result caching keyed `(product_type, location_name, text_hash, style)` with 5-minute TTL — matches the `explain_weather` cache. Fixes the incidental `explain_afd` no-cache regression.
- **`ForecastProductPanel` is a reusable `wx.Panel`** taking `(product_type, fetch_callable, notification_state_reader)`; `ForecastProductsDialog` hosts three instances in `wx.Notebook`.
- **SPS multi-product `wx.Choice`** above the TextCtrl; hidden via `Sizer.Show(False) + Layout()` when only one SPS is active.
- **Tab-switch focus: `EVT_NOTEBOOK_PAGE_CHANGED` handler + `wx.CallAfter(panel.product_textctrl.SetFocus)`**. Dialog open: `wx.CallAfter` on AFD tab's TextCtrl after `Show()`.
- **SPS dedupe**: at SPS fetch time, read currently-cached NWS alerts for the location, filter `event == "Special Weather Statement"`, compare zone intersections. To enable this, `WeatherAlert` serializer at `cache.py:422-455` gains an additive `affected_zones: list[str]` field (backward-compatible, populated from `alert_geocode.py`). Fallback if intersection data missing: substring match on `headline`. Performance: O(products × alerts × zones), realistically < 5 × 10 × 20 — trivial per fetch.
- **Per-stream rate limit: 30 minutes per `(product_type, location)`** using sliding-window timestamp compare (NOT calendar-hour; avoids the §7 burst pattern). Implemented as `last_notified_at: dict[(product_type, location_id), datetime]` on `NotificationEventManager` — ephemeral, not persisted to runtime state.
- **HWO empty vs error states**: 200 + empty `@graph` → "Hazardous Weather Outlook not currently available for {cwa_office}."; exception/non-200 → "Failed to fetch — try again." with retry button.
- **HWO diffing**: attempt `summarize_discussion_change` first; fall back to generic "Hazardous Weather Outlook updated for {cwa_office} — tap to view." when the summary is empty or below a length heuristic.
- **SPS silent expiration**: when a previously-seen SPS product ID disappears from `@graph`, remove it from `NotificationState.last_sps_product_ids` with no notification. Matches the existing discussion-cleared pattern.
- **No `schema_version` bump anywhere** — every new field (6 Location, ~4 NotificationState, 2 runtime-state sub-sections, `WeatherAlert.affected_zones`) uses defensive `.get()` with null/default.

## Open Questions

### Resolved During Planning

All planning-deferred questions from both brainstorms are resolved above under **Key Technical Decisions**.

### Deferred to Implementation

- Exact `length-heuristic` threshold for HWO summarizer fallback — tune during implementation by running `summarize_discussion_change` against a couple of live HWO products.
- Exact intro-text wording for the Settings notifications section — writer's call during implementation; constraint: must accurately reflect "HWO + SPS default ON; others default OFF".
- `ForecastProductPanel` minimum size tuning — pick once the three panels are visible together in the Notebook on Windows; may need `SetMinSize` adjustments.
- Exact copy of the "Plain Language Summary" prompts for HWO and SPS — iterate against a handful of live products to get meteorology-jargon translation quality right.
- Whether to extend `_is_us_location` bboxes to include Puerto Rico / territories — if NWS `/points` returns valid data there, the enrichment path can stay as-is; confirm at implementation.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```text
                                   ┌────────────────────────────────────┐
                                   │  Saved Location (JSON config)      │
                                   │  + forecast_zone_id, cwa_office,   │
                                   │    county_zone_id, fire_zone_id,   │
                                   │    radar_station, timezone         │
                                   └────────────┬───────────────────────┘
                                                │  (read on every fetch)
         ┌──────────────────────────────────────┼──────────────────────────────────────┐
         │                                      │                                      │
         ▼                                      ▼                                      ▼
  Alert fetch (reuses               Forecast Products background fetch         Edit Location dialog
  county/forecast zone IDs,         (active loc + pre-warm others)             (shows forecast_zone_id,
   skips redundant /points)                     │                               cwa_office read-only)
                                                ▼
                             get_nws_text_product(product_type, cwa_office)
                             ┌─────────────┬─────────────┬─────────────┐
                             │   AFD       │   HWO       │   SPS       │
                             │  TTL 3600s  │  TTL 7200s  │  TTL 900s   │
                             └─────┬───────┴──────┬──────┴──────┬──────┘
                                   │              │             │
                 ┌─────────────────┼──────────────┼─────────────┤
                 │                 │              │             │
                 ▼                 ▼              ▼             ▼
   ForecastProductsDialog    AFD notify     HWO notify     SPS notify
     (wx.Notebook:           (unchanged)    (diff +         (new ID +
      AFD | HWO | SPS)                       rate limit     alert-dedupe +
         │                                   30 min)         rate limit 30 min)
         ▼
   ForecastProductPanel × 3
     - raw TextCtrl (readonly, multi-line)
     - wx.Choice (SPS multi-product only)
     - "Issued:" StaticText
     - "Plain Language Summary" (hidden AI)
```

Key seams:
- Zone enrichment writes on save; drift-corrects on refresh; reads everywhere.
- `get_nws_text_product` is the one async fetcher; `get_nws_discussion` becomes a thin wrapper.
- Notification dedupe lives at SPS fetch time, not at alert arrival.

## Implementation Units

- [ ] **Unit 1: Location model + config round-trip + point-transform exposure**

  **Goal:** Data surface for zone metadata — model fields, JSON round-trip, and getting the six fields out of `/points` in the first place.

  **Requirements:** A-R1, A-R2, A-R3 (data-shape pieces).

  **Dependencies:** None.

  **Files:**
  - Modify: `src/accessiweather/models/weather.py` (add six `Optional[str]` zone fields to `Location`)
  - Modify: `src/accessiweather/models/config.py` (`AppConfig.to_dict`/`from_dict` round-trip — conditional spread on serialize, defensive `.get()` on deserialize, matching `country_code` precedent)
  - Modify: `src/accessiweather/api/nws/point_location.py` (extend `_transform_point_data` ~86-141 to include `cwa`, `forecastZone`, `gridId` alongside existing `county`, `fireWeatherZone`, `timeZone`, `radarStation`)
  - Test: `tests/test_models_config_location_zones.py` (new)

  **Approach:**
  - Field naming mirrors existing snake_case: `forecast_zone_id`, `cwa_office`, `county_zone_id`, `fire_zone_id`, `radar_station`, `timezone`. All default `None`.
  - Serializer omits a field when its value is null (conditional-spread pattern at `config.py:700-745`).
  - `_transform_point_data` change is additive — existing keys continue; new keys appear.

  **Patterns to follow:**
  - `country_code`, `marine_mode` additions to `Location` (locate via git blame on `weather.py`).
  - Conditional-spread serialize + `.get()` deserialize at `models/config.py:700-745`.

  **Test scenarios:**
  - Happy path: `Location` with all six fields populated round-trips through JSON identically.
  - Happy path: `Location` with all six fields null round-trips without producing null keys in the JSON.
  - Happy path: legacy JSON without the six fields deserializes, yields all-null zone fields on the `Location`.
  - Happy path: `_transform_point_data` returns `cwa`, `forecastZone`, `gridId` alongside existing fields given a realistic point-endpoint response fixture.
  - Edge case: partial population (only `cwa_office` populated) round-trips without emitting null keys for the rest.

  **Verification:**
  - `Location` can carry zone metadata through save/load.
  - `_transform_point_data` no longer strips the fields PR 1 needs.
  - No existing tests regress.

- [ ] **Unit 2: Zone enrichment on save**

  **Goal:** First-time population of zone fields when a user adds a US location.

  **Requirements:** A-R1, A-R2, A-R3.

  **Dependencies:** Unit 1.

  **Files:**
  - Modify: `src/accessiweather/config/locations.py` (extend `add_location` path to trigger enrichment for US locations)
  - Create: `src/accessiweather/services/zone_enrichment_service.py` (new; orchestrates `/points` fetch + mapping to Location fields)
  - Test: `tests/test_zone_enrichment_service.py` (new)

  **Approach:**
  - `ZoneEnrichmentService.enrich_location(location) -> Location` returns a new `Location` with fields populated (or unchanged on failure/non-US).
  - Call the existing point-location helper rather than raw HTTP — reuses transform + caching.
  - Non-US bypass via `_is_us_location(location)` at `src/accessiweather/display/presentation/forecast.py:40-51`.
  - On network exception or non-200: return `location` unchanged, debug-log.
  - `LocationOperations.add_location` calls the service before persisting; if enrichment returned populated fields they're saved; otherwise the location saves with zone fields null.

  **Patterns to follow:**
  - `LocationOperations.update_location_marine_mode` at `src/accessiweather/config/locations.py:59-70` — mutate-then-persist.
  - `src/accessiweather/services/national_discussion_service.py` for service-module shape.

  **Test scenarios:**
  - Happy path: adding a US location with a working `/points` call persists all six fields.
  - Happy path: adding a non-US location never calls `/points`; zone fields stay null.
  - Error path: `/points` raises `httpx.HTTPError` → location still saves; fields null; debug log emitted.
  - Error path: `/points` returns non-200 → location still saves; fields null.
  - Edge case: `/points` returns 200 with some zone fields missing from payload → populated fields saved; absent fields stay null.
  - Edge case: save flow never prompts the user or blocks on `/points` (assert no modal dialog spawned during failure).

  **Verification:**
  - Adding any US location yields a `Location` record with six zone fields populated (when `/points` succeeds).
  - Adding a non-US location or saving during a `/points` outage still succeeds.

- [ ] **Unit 3: Opportunistic drift correction on refresh**

  **Goal:** Lazy backfill + boundary-change self-healing during the regular weather refresh.

  **Requirements:** A-R4, A-R5.

  **Dependencies:** Unit 1.

  **Files:**
  - Modify: `src/accessiweather/weather_client_nws.py` (after each successful `/points` response in the refresh path, invoke drift-correction hook)
  - Modify: `src/accessiweather/config/locations.py` (new `LocationOperations.update_zone_metadata(location_id, fields_dict)`)
  - Modify: `src/accessiweather/services/zone_enrichment_service.py` (from Unit 2: add `diff_and_update(location, fresh_point_data) -> dict[str, str] | None`)
  - Test: `tests/test_zone_enrichment_drift.py` (new)

  **Approach:**
  - Diff rule: for each of the six fields, if stored is null and fresh is non-null → populate. If both non-null and they differ → overwrite. If fresh is null/missing → no update (never overwrite populated with null).
  - If `/points` call itself raises, skip drift this cycle; retry on next refresh (A-R4 explicit).
  - Persistence: call `LocationOperations.update_zone_metadata(...)` via `wx.CallAfter` from the refresh thread. This avoids racing with user-initiated `save_config` calls on the main thread. `ConfigManager.save_config` has no in-process lock (research finding) — `wx.CallAfter` is the smallest correct fix.

  **Execution note:** Write tests for the diff rule first; getting "never overwrite populated with null" wrong is the subtle bug this unit exists to prevent.

  **Patterns to follow:**
  - `update_location_marine_mode` at `src/accessiweather/config/locations.py:59-70` for mutate-then-persist.
  - `wx.CallAfter` usage in `src/accessiweather/notifications/notification_event_manager.py` for thread bounce.

  **Test scenarios:**
  - Happy path: stored field null + fresh non-null → diff returns that field; update persists it.
  - Happy path: stored and fresh both non-null and equal → no update, no persist.
  - Happy path: stored and fresh both non-null and differ → diff returns the changed field; update overwrites.
  - Edge case: stored non-null + fresh null/missing → diff returns empty; stored value preserved.
  - Edge case: stored all six null + fresh all six present (legacy location first refresh) → all six populated in one call.
  - Error path: `/points` raises → drift-correction skipped silently; no crash; retry on next cycle.
  - Integration: drift write from the refresh thread is funneled via `wx.CallAfter` to the main thread (mock `wx.CallAfter`; assert it's invoked with the persist callable).

  **Verification:**
  - Simulating a stored `cwa_office = "PHI"` with `/points` returning `cwa = "OKX"` causes stored value to flip to "OKX" on next refresh.
  - Simulating `/points` omitting `cwa` does NOT null out a populated stored `cwa_office`.
  - No crashes from concurrent refresh cycles.

- [ ] **Unit 4: Alert-path stored-zone reuse**

  **Goal:** Skip redundant `/points` resolution in the alert-fetch path when stored zones are present.

  **Requirements:** A-R6.

  **Dependencies:** Units 1 and 3 (so stored values are populated in practice).

  **Files:**
  - Modify: `src/accessiweather/weather_client_nws.py` (county path ~873-890, zone path ~915-941)
  - Test: `tests/test_weather_client_nws_alerts_zone_reuse.py` (new)

  **Approach:**
  - `alert_radius_type="county"` path: prefer `location.county_zone_id` when present; else fall back to fresh resolution.
  - `alert_radius_type="zone"` path: prefer `location.forecast_zone_id` when present; else fall back.
  - No change to alert response shape; the only diff is whether we made an extra `/points` roundtrip.

  **Patterns to follow:**
  - Existing caller structure at `weather_client_nws.py:873-941`.

  **Test scenarios:**
  - Happy path (county): stored `county_zone_id` present → alerts fetched with that zone; no `/points` call.
  - Happy path (zone): stored `forecast_zone_id` present → alerts fetched with that zone; no `/points` call.
  - Happy path (fallback): stored fields null → existing `/points` resolution runs.
  - Error path: stored zone ID present but NWS returns 404 for that zone → surfaces as alert-fetch error; no silent downgrade (consistent with today's behavior on bad zones).
  - Integration: after first successful refresh, the second refresh's alert fetch makes one fewer HTTP call than the first (verify via mock assertion).

  **Verification:**
  - Measure API calls per refresh before/after: drops by one per refresh once zones are populated.
  - Default `alert_radius_type="county"` stops re-resolving from lat/lon on populated locations.

- [ ] **Unit 5: Edit Location dialog — "NWS Zone Information" section + Fit-based sizing**

  **Goal:** User-visible read-only surface for `forecast_zone_id` and `cwa_office`.

  **Requirements:** A-R8, A-R9.

  **Dependencies:** Unit 1.

  **Files:**
  - Modify: `src/accessiweather/ui/dialogs/location_dialog.py` (~81-125)
  - Test: `tests/gui/test_location_dialog_zone_info.py` (new)

  **Approach:**
  - Add a `wx.StaticBox` labeled "NWS Zone Information" below the marine-mode checkbox, above OK/Cancel.
  - Inside: two `wx.StaticText` rows, label-prefixed: "Forecast Zone: NCZ027", "NWS Office: RAH".
  - Null/non-US state rules (from A-R9):
    - Non-US: entire StaticBox `Show(False)` — hidden.
    - US + both fields null: both rows show "Not yet resolved — will populate after next weather refresh".
    - US + partial (one field populated): show populated value in that row; null message in the other.
  - Remove fixed `size=(420, 200)` at `:89`; call `self.Fit()` after sizer population. Add `self.SetMinSize((420, -1))` to preserve baseline width.
  - Tab order: Name → Marine Mode → OK → Cancel. StaticText rows are skipped by Tab (non-focusable).
  - Snapshot-at-open: values read from the Location passed to the constructor; no live binding.

  **Patterns to follow:**
  - Existing `EditLocationDialog` sizer/label style.
  - wxPython accessibility rule: adjacent `wx.StaticText` announces to screen readers; label prefix IS the accessible label.

  **Test scenarios:**
  - Happy path (US populated): both zone rows render with "Forecast Zone: NCZ027" and "NWS Office: RAH".
  - Happy path (non-US): StaticBox not shown — querying `IsShown()` returns False.
  - Edge case (US null): both rows show the "Not yet resolved" message.
  - Edge case (US partial): one row shows value; the other shows "Not yet resolved".
  - Edge case (sizing): dialog fits content without clipping after adding rows (assert `GetSize()` height exceeds original 200).
  - Accessibility: each StaticText's `GetLabel()` returns the label-prefixed string (the accessible announcement).

  **Verification:**
  - Dialog opens for US and non-US locations without truncation.
  - Screen reader reads the forecast zone and CWA office when focus lands near the StaticBox.

- [ ] **Unit 6: Generalized `get_nws_text_product` fetcher + `ForecastProductService`**

  **Goal:** One async fetcher for AFD/HWO/SPS + a service that caches results per `(product_type, cwa_office)` with per-type TTLs.

  **Requirements:** B-R1, B-R2, B-R4.

  **Dependencies:** Unit 1 (needs `cwa_office` persisted).

  **Files:**
  - Modify: `src/accessiweather/weather_client_nws.py` (add `get_nws_text_product(product_type: Literal["AFD","HWO","SPS"], cwa_office: str) -> TextProduct | list[TextProduct] | None`; refactor `get_nws_discussion` to call it internally for AFD)
  - Create: `src/accessiweather/services/forecast_product_service.py` (new; `ForecastProductService.get(product_type, location) -> TextProduct | list[TextProduct] | None` with cache read-through)
  - Create: `src/accessiweather/models/text_product.py` (new `TextProduct` dataclass: `product_type`, `product_id`, `cwa_office`, `issuance_time`, `product_text`, `headline: str | None`)
  - Test: `tests/test_weather_client_nws_text_product.py` (new)
  - Test: `tests/test_forecast_product_service.py` (new)

  **Approach:**
  - Endpoint: `products/types/{product_type}/locations/{cwa_office}`; response shape per research: `@graph[]` with `id`, each fetched via `products/{id}` for `productText` + `issuanceTime`.
  - AFD and HWO: always take the first (newest) product from `@graph`. Return a single `TextProduct` or `None` if `@graph` empty.
  - SPS: return ALL entries from `@graph` sorted newest-first (multiple concurrent SPSs common).
  - TTLs via `Cache.set(..., ttl=...)`: AFD 3600, HWO 7200, SPS 900.
  - Cache keys: `nws_text_product:{product_type}:{cwa_office}`.
  - Skip fetch when `cwa_office` is None or `_is_us_location` returns False.
  - Error handling: network / non-200 raises `TextProductFetchError` (new sentinel) — caller distinguishes from "empty `@graph`" (returns `None` / `[]`).

  **Execution note:** Start with failing tests for the generic fetcher covering both single-product (AFD/HWO) and multi-product (SPS) shapes.

  **Patterns to follow:**
  - `get_nws_discussion` at `src/accessiweather/weather_client_nws.py:769-844` for async + `issuanceTime` extraction.
  - `src/accessiweather/cache.py` for per-key TTL usage.
  - `src/accessiweather/services/national_discussion_service.py` for service-module shape (untouched, not generalized).

  **Test scenarios:**
  - Happy path: AFD fetch returns one `TextProduct` with `issuance_time`, `product_text`, `headline`.
  - Happy path: HWO fetch returns one `TextProduct`.
  - Happy path: SPS fetch with three active products returns a list of three `TextProduct` sorted newest-first.
  - Happy path: SPS fetch with empty `@graph` returns empty list (not error).
  - Edge case: AFD fetch with empty `@graph` returns None.
  - Edge case: `cwa_office = None` → returns None without making HTTP calls.
  - Error path: HTTP 500 raises `TextProductFetchError`.
  - Error path: timeout raises `TextProductFetchError`.
  - Integration: repeated calls within the TTL window hit cache (assert single HTTP call).
  - Integration: per-type TTL — AFD still cached at t+30min; SPS refetches at t+16min.

  **Verification:**
  - Three live product types fetch with distinct TTLs through one code path.
  - `get_nws_discussion` call-sites continue to work (thin wrapper preserves signature).

- [ ] **Unit 7: AI `explain_text_product` generalization + per-product cache**

  **Goal:** Reuse the existing tl;dr across all three tabs; fix the incidental `explain_afd` no-cache gap.

  **Requirements:** B-R6 (AI button per tab).

  **Dependencies:** Unit 6 (receives `TextProduct`).

  **Files:**
  - Modify: `src/accessiweather/ai_explainer.py` (add `explain_text_product(product_text, product_type, location_name, style, preserve_markdown)`; refactor `explain_afd` to a thin wrapper; add result cache)
  - Test: `tests/test_ai_explainer_text_product.py` (new)

  **Approach:**
  - Prompt lookup table at module level: `_SYSTEM_PROMPTS: dict[str, str]` keyed by product type. AFD prompt preserved verbatim to keep existing behavior untouched. HWO and SPS prompts mirror the AFD shape (objective bullets) with domain-specific phrasing.
  - Caching: match `explain_weather`'s pattern at `ai_explainer.py:741` — cache key `(product_type, location_name, hash(product_text), style)` with 300s TTL on `self.cache`.
  - Custom prompt / custom instructions (`AppSettings.custom_system_prompt`, `custom_instructions`) apply to all three product types (append as today).

  **Patterns to follow:**
  - `explain_weather` at `ai_explainer.py:741` for cache shape.
  - `explain_afd` at `:746-941` for prompt structure.

  **Test scenarios:**
  - Happy path (AFD): `explain_text_product(product_type="AFD", ...)` returns a result whose prompt matches the current AFD prompt byte-for-byte.
  - Happy path (HWO): returns result using the HWO system prompt.
  - Happy path (SPS): returns result using the SPS system prompt.
  - Happy path (cache): repeated call with same inputs returns `cached=True` and does NOT call the LLM.
  - Happy path (custom prompt): `AppSettings.custom_system_prompt` set → it replaces the product-specific system prompt (or appends per existing rule); assert final prompt contains custom text.
  - Edge case: `explain_afd` wrapper still returns the expected `ExplanationResult`.
  - Error path: LLM error propagates as today (no silent fallback).

  **Verification:**
  - AFD tab's "Plain Language Summary" behaves identically to today.
  - HWO and SPS tabs produce sensible plain-language summaries against live products.

- [ ] **Unit 8: `ForecastProductPanel` + `ForecastProductsDialog` + main-window rename + non-US button state**

  **Goal:** The user-visible dialog and its entry point, wired and accessible.

  **Requirements:** B-R5, B-R6, B-R7, B-R8, B-R9 (AFD unchanged).

  **Dependencies:** Unit 6 (data), Unit 7 (AI).

  **Files:**
  - Create: `src/accessiweather/ui/dialogs/forecast_product_panel.py` (new reusable `wx.Panel` subclass)
  - Create: `src/accessiweather/ui/dialogs/forecast_products_dialog.py` (new `wx.Dialog` hosting `wx.Notebook`)
  - Modify: `src/accessiweather/ui/main_window.py` (`QUICK_ACTION_LABELS` at ~37; `_on_discussion` non-Nationwide branch at 674-686 renamed/routed to `_on_forecast_products`; add adjacent `wx.StaticText` "NWS products are US-only" below the Forecast Products button, shown only when non-US selection)
  - Modify: `src/accessiweather/ui/main_window.py` (existing test-notification menu at ~415 — update label if it references "Discussion" in a user-visible way)
  - Test: `tests/gui/test_forecast_product_panel.py` (new)
  - Test: `tests/gui/test_forecast_products_dialog.py` (new)

  **Approach:**
  - `ForecastProductPanel.__init__(parent, product_type, product_loader, ai_explainer)`:
    - Header `wx.StaticText` (product full name — "Area Forecast Discussion", etc.)
    - Optional `wx.Choice` for SPS multi-product (hidden via `Sizer.Show(False) + Layout()` when only one SPS or non-SPS).
    - `wx.TextCtrl(style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)` for raw product text.
    - `wx.StaticText` "Issued: {local time}".
    - "Plain Language Summary" `wx.Button` — hidden-until-clicked design per `docs/superpowers/specs/2026-04-08-discussion-dialog-ai-visibility-design.md`.
    - Hidden AI result TextCtrl + model-info StaticText + Regenerate button; shown after first Explain click.
    - Retry button when fetch failed.
  - Empty/error state strings embedded in the content panel (not tab label) per B-R7.
  - `ForecastProductsDialog`:
    - `wx.Dialog` with `wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER`.
    - `wx.Notebook` with three `ForecastProductPanel` instances: AFD, HWO, SPS.
    - `EVT_NOTEBOOK_PAGE_CHANGED` → `wx.CallAfter(panel.product_textctrl.SetFocus)`.
    - Dialog open: `wx.CallAfter` focus on AFD tab's TextCtrl after `Show()`.
    - ESC closes via `EVT_CHAR_HOOK` (match existing DiscussionDialog).
  - Main window:
    - `QUICK_ACTION_LABELS["discussion"] = "Forecast &Products"` at `main_window.py:37`.
    - `_on_discussion` keeps Nationwide branch; non-Nationwide branch routes to `_on_forecast_products` which opens `ForecastProductsDialog`.
    - Adjacent `wx.StaticText` labeled "NWS products are US-only" positioned below the Forecast Products button, `Show(False)` by default, `Show(True)` when a non-US location is selected; button `Disable()` in the same state transition.

  **Execution note:** Write accessibility assertions first — each button and TextCtrl must have its announce string verified before wiring behavior.

  **Patterns to follow:**
  - `src/accessiweather/ui/dialogs/discussion_dialog.py` for dialog shape, AI visibility pattern at lines 283-394.
  - `docs/nationwide_discussions.md` for nested `wx.Notebook` precedent.
  - Accessibility: adjacent `wx.StaticText` for context; descriptive `label=` strings on buttons; do NOT rely on `SetName()`.

  **Test scenarios:**
  - Happy path: dialog opens with three tabs; AFD tab focused; TextCtrl has latest AFD text.
  - Happy path: tab switch to HWO moves focus to HWO TextCtrl.
  - Happy path (SPS multi): three SPS products → `wx.Choice` visible with three entries; selecting another swaps TextCtrl content.
  - Happy path (SPS single): one SPS product → `wx.Choice` hidden.
  - Edge case: SPS empty → panel displays "No Special Weather Statements currently active for {cwa_office}".
  - Edge case: HWO 200 + empty `@graph` → "Hazardous Weather Outlook not currently available for {cwa_office}".
  - Error path: HWO fetch raised → "Failed to fetch Hazardous Weather Outlook — try again." with retry button; retry click re-invokes loader.
  - Edge case: `cwa_office` null for selected location → all three panels show "NWS text products will populate after the next weather refresh."
  - Happy path (non-US button): selecting a non-US location → Forecast Products button `Disable()`d; adjacent StaticText "NWS products are US-only" shown.
  - Happy path (renames): `QUICK_ACTION_LABELS["discussion"]` is "Forecast &Products"; menu item label matches.
  - Integration: Nationwide location selection routes to existing NationwideDiscussionDialog, NOT ForecastProductsDialog.
  - Accessibility: each TextCtrl and button has an accessible label derivable from adjacent StaticText or its own `label=` string.

  **Verification:**
  - Dialog opens, reads, and navigates with a screen reader.
  - AFD content, AFD cold-start baseline, and AFD notification behavior are unchanged (existing tests still pass).

- [ ] **Unit 9: Background product fetch hooks + state extensions + alert affected-zones**

  **Goal:** Pre-warm the dialog across all saved US locations and prepare the state surface for new notifications.

  **Requirements:** B-R3, B-R4, B-R10 (state-shape pieces).

  **Dependencies:** Unit 6 (fetch), Unit 1 (stored zones).

  **Files:**
  - Modify: `src/accessiweather/ui/main_window.py` (extend `_pre_warm_other_locations` at ~1273-1290 to also call `ForecastProductService` for each of AFD/HWO/SPS per US location with populated `cwa_office`; add product fetch + dispatch step after `_fetch_weather_data` success at ~1108-1186 for the active location)
  - Modify: `src/accessiweather/notifications/notification_event_manager.py` (extend `NotificationState` dataclass with `last_hwo_issuance_time`, `last_hwo_text`, `last_hwo_summary_signature`, `last_sps_product_ids: set[str]`)
  - Modify: `src/accessiweather/runtime_state.py` (add `hwo` and `sps` sub-sections to `_DEFAULT_RUNTIME_STATE` at 14-37; parallel entries in `_runtime_section_to_legacy_shape` and `_legacy_shape_to_runtime_section` at 297-340)
  - Modify: `src/accessiweather/cache.py` (extend `WeatherAlert` serializer at 422-455 with additive `affected_zones: list[str]` field, defensive `.get()` on deserialize)
  - Test: `tests/test_main_window_product_prewarm.py` (new)
  - Test: `tests/test_notification_state_hwo_sps_fields.py` (new)
  - Test: `tests/test_runtime_state_hwo_sps.py` (new)
  - Test: `tests/test_cache_weather_alert_affected_zones.py` (new)

  **Approach:**
  - Pre-warm iterates all saved locations; for each US location with populated `cwa_office`, request AFD + HWO + SPS through `ForecastProductService`. Failures per `(product_type, location)` are swallowed and debug-logged — one failure NEVER cascades.
  - Active-location: the existing `_fetch_weather_data` success branch triggers the same three product fetches plus the HWO / SPS notification checks (Units 10 and 11). AFD notification stays in `_check_discussion_update` unchanged.
  - State-shape changes are additive; no `schema_version` bump; reload of a legacy runtime_state.json `.get()`s defaults for the new fields.
  - `WeatherAlert.affected_zones` is additive — older cache entries deserialize to empty list; new writes persist the real zone list from `alert_geocode.py`.

  **Patterns to follow:**
  - `src/accessiweather/ui/main_window.py:1273-1290` iteration shape.
  - `src/accessiweather/notifications/notification_event_manager.py:182-222` for additive `NotificationState` field pattern.
  - `src/accessiweather/runtime_state.py:297-340` parallel-update rule for converters.
  - `src/accessiweather/cache.py:422-455` for additive `WeatherAlert` serializer extension.

  **Test scenarios:**
  - Happy path: three saved US locations with populated `cwa_office` → pre-warm issues 9 product fetches (3 × 3 types).
  - Happy path: one non-US location + two US → 6 product fetches total (non-US skipped).
  - Edge case: US location with `cwa_office = None` → 0 product fetches for that location.
  - Error path: one location's HWO fetch fails → the other two product types for that location still attempt; other locations unaffected.
  - Happy path (state): `NotificationState` with all new fields populated round-trips through runtime_state JSON.
  - Happy path (state): legacy runtime_state.json (no `hwo` / `sps` sections) loads with defaults; new fields null/empty.
  - Happy path (alerts): `WeatherAlert.affected_zones` serializes and deserializes identically when populated.
  - Happy path (alerts legacy): cache entry without `affected_zones` deserializes with `affected_zones = []`.
  - Integration: pre-warm failure for HWO of location A does not prevent SPS fetch for location A or any fetch for location B.

  **Verification:**
  - Opening Forecast Products dialog after initial refresh cycle shows pre-populated content with no perceptible load time.
  - Runtime state round-trips cleanly.
  - Existing alert cache hits continue to work; new `affected_zones` populates on re-fetch.

- [ ] **Unit 10: HWO update notification stream**

  **Goal:** Fire a notification when a WFO's HWO content has meaningfully changed.

  **Requirements:** B-R10 (HWO portion), B-R11 (HWO content).

  **Dependencies:** Units 6 and 9.

  **Files:**
  - Modify: `src/accessiweather/notifications/notification_event_manager.py` (new `_check_hwo_update(location, hwo_product)` method following `_check_discussion_update` at 404-455; cold-start baseline following 427-435)
  - Modify: `src/accessiweather/notifications/notification_event_manager.py` (add ephemeral `self._last_product_notified_at: dict[tuple[str, str], datetime]` for per-stream rate limiting)
  - Test: `tests/test_notification_hwo_update.py` (new)

  **Approach:**
  - On each new HWO fetch per location, compare `issuance_time` and a content signature (hash of `product_text` normalized for whitespace) against stored state.
  - First-fetch path: store silently. No notification (matches AFD pattern at 427-435).
  - Subsequent change: fire notification — content via `summarize_discussion_change(stored_text, new_text)` if it returns a usable summary; else "Hazardous Weather Outlook updated for {cwa_office} — tap to view."
  - Rate-limit check: compare `now - self._last_product_notified_at[("HWO", location_id)] >= timedelta(minutes=30)`; skip notification if within window, but always persist the new baseline so we don't re-trigger forever.
  - Gated by `notify_hwo_update` setting (default ON).

  **Patterns to follow:**
  - `_check_discussion_update` at `notification_event_manager.py:404-455`.
  - Cold-start silent-store pattern at `:427-435`.
  - `format_accessible_message` helper for notification body formatting.

  **Test scenarios:**
  - Happy path (cold start): first HWO fetch for a location → baseline stored, `dispatch_notification` NOT called.
  - Happy path (content change): second fetch with new `issuance_time` and changed `product_text` → notification dispatched with summarizer output if non-empty.
  - Happy path (summarizer fallback): summarizer returns empty/short → generic "Hazardous Weather Outlook updated for {cwa_office} — tap to view." dispatched.
  - Edge case (unchanged): second fetch with same `issuance_time` → no notification, no state update.
  - Edge case (rate limited): change arrives within 30 min of last notification → state updates, notification suppressed.
  - Edge case (disabled): `notify_hwo_update = False` → no dispatch regardless of change.
  - Edge case (None): HWO fetch returned None (empty @graph) → no-op, no crash.
  - Integration: multi-location — notifications fire independently per `(HWO, location)` rate bucket.

  **Verification:**
  - WFO issuing an HWO update triggers a desktop notification.
  - Notification content is sensible (summarizer output or generic fallback).
  - After a prolonged app closure, reopening produces at most one HWO notification per location within 30 min.

- [ ] **Unit 11: SPS notification stream with alert dedupe**

  **Goal:** Surface informational SPS (Case B) as notifications while never duplicating event-style SPS (Case A) that the alert pipeline already shows.

  **Requirements:** B-R10 (SPS portion), B-R11 (SPS content).

  **Dependencies:** Units 6 and 9 (needs `affected_zones` on cached alerts).

  **Files:**
  - Modify: `src/accessiweather/notifications/notification_event_manager.py` (new `_check_sps_new(location, sps_products, cached_alerts)` method)
  - Test: `tests/test_notification_sps_dedupe.py` (new)

  **Approach:**
  - Input: list of `TextProduct` (SPS) + currently-cached `WeatherAlerts` for the location.
  - For each SPS product not in `NotificationState.last_sps_product_ids`:
    1. Filter cached alerts to `event == "Special Weather Statement"`.
    2. Intersect the SPS product's zone scope (derived from `TextProduct` — typically in `wmoCollectiveId` / affected-zones metadata in the `/products/{id}` response; capture this in Unit 6's `TextProduct` dataclass) with each alert's `affected_zones`.
    3. If any alert zones intersect → Case A; add ID to `last_sps_product_ids` silently (dedupe), no notification.
    4. If no intersection → Case B; fire notification with `headline` (or first non-empty line of `productText` if headline null), body format `"{headline} — {cwa_office}"`, truncate at 160 chars.
  - Rate-limit check: `("SPS", location_id)` bucket, same 30-min sliding window.
  - Expiration: for product IDs present in `last_sps_product_ids` but not in the latest fetch, remove silently (no notification).
  - Gated by `notify_sps_issued` setting (default ON).
  - Fallback when zone data unavailable (shouldn't happen with Unit 9's `affected_zones` extension, but defensive): substring match on `headline` between SPS product and active alerts.

  **Execution note:** Write failing tests for both Case A and Case B against the live-verified PHI fire-weather example before implementation — getting the dedupe wrong is the one user-visible regression that would undermine the feature.

  **Patterns to follow:**
  - Cold-start silent-store at `notification_event_manager.py:427-435`.
  - `format_accessible_message` for notification body.

  **Test scenarios:**
  - Happy path (Case B): SPS product with zones `[PHZ007, PHZ008]`; no active alerts for those zones → notification dispatched with headline.
  - Happy path (Case A): SPS product with zones `[PHZ007]`; active alert with `affected_zones=[PHZ007, PHZ008]` and `event="Special Weather Statement"` → suppressed; ID added to seen.
  - Happy path (cold start): first fetch with three SPS → all IDs recorded; no notifications.
  - Happy path (expiration): previously-seen SPS disappears from `@graph` → removed from `last_sps_product_ids`; no notification.
  - Edge case (headline null): SPS headline null → body uses first non-empty line of `productText`, truncated at 160 chars with ellipsis.
  - Edge case (rate limited): new Case B SPS within 30 min of last → state updates, notification suppressed.
  - Edge case (disabled): `notify_sps_issued = False` → no dispatch.
  - Edge case (fallback): `affected_zones` empty on both SPS and alert → headline substring match used.
  - Integration: Case A + Case B in same fetch → only Case B notifies; both IDs recorded in state.
  - Integration (realistic): replay live-verified PHI fire-weather product from 2026-04-16 — notification fires because alerts feed has no matching SSS.

  **Verification:**
  - The verified PHI fire-weather SPS scenario produces exactly one notification.
  - Event-style SPS that are also in `/alerts/active` produce zero notifications from this stream (the alert pipeline handles them).
  - Closing the app for 18 hours and reopening does not produce a notification storm.

- [ ] **Unit 12: Settings notifications tab — new toggles + intro copy rewrite**

  **Goal:** User-facing controls for the two new notification streams and honest section copy.

  **Requirements:** B-R10 (settings surface).

  **Dependencies:** Unit 9 (`NotificationState` shape), Units 10–11 (consumers).

  **Files:**
  - Modify: `src/accessiweather/ui/dialogs/settings_tabs/notifications.py` (~110-125; add `notify_hwo_update` and `notify_sps_issued` checkboxes as siblings to `notify_discussion_update`; rewrite section intro `wx.StaticText`)
  - Modify: `src/accessiweather/models/config.py` (`AppSettings` — new bool fields with defaults: `notify_hwo_update=True`, `notify_sps_issued=True`; round-trip via `_as_bool` pattern)
  - Test: `tests/test_settings_notification_toggles.py` (new)

  **Approach:**
  - New intro copy: "Updates beyond standard alerts. HWO and SPS updates are on by default since they deliver information not in the alerts feed. Others are off unless you turn them on."
  - Checkbox labels (descriptive — screen readers read them directly):
    - `Notify on Hazardous Weather Outlook updates`
    - `Notify on Special Weather Statement (informational)`
  - Wire through `save()` and `load()` at existing `~258` and `~297` lines following the `notify_discussion_update` pattern.

  **Patterns to follow:**
  - Existing `notify_discussion_update` row at `settings_tabs/notifications.py:116-125`.
  - `AppSettings._as_bool(data.get("...", <default>), <default>)` at `models/config.py`.

  **Test scenarios:**
  - Happy path: fresh config loads with both new toggles checked (defaults ON).
  - Happy path: saving with `notify_hwo_update=False` persists to JSON; reload round-trips.
  - Happy path: legacy config (no new keys) loads with both defaults ON.
  - Accessibility: both checkboxes have label strings that describe intent without relying on nearby context.
  - Happy path (intro copy): rendered text reflects the two defaults-ON behavior (assert against exact string).

  **Verification:**
  - User can toggle each stream independently and the setting sticks.
  - Intro copy accurately describes default behavior.

## System-Wide Impact

- **Interaction graph:** `/points` response now flows into `Location` persistence (save + drift) and into the alert-fetch path. Text-product fetches flow into the dialog (synchronous on open), the notification pipeline (per-stream checks), and two new settings toggles. Main-window `_on_discussion` is forked: Nationwide branch untouched, non-Nationwide routed to new `_on_forecast_products`. `wx.CallAfter` carries drift-correction persistence from refresh thread to main thread.
- **Error propagation:** Per-product + per-location fetch failures are isolated and debug-logged — never cascade. `/points` failures at save-time or during drift are swallowed silently (location still saves or no update). LLM errors in `explain_text_product` surface into the AI result TextCtrl per the hidden-until-clicked visibility design; they do not close the dialog.
- **State lifecycle risks:** Two runtime-state sub-sections added; both converters must be updated in parallel or `hwo` / `sps` fields silently drop on round-trip (mitigated by Unit 9 tests). `ConfigManager.save_config` has no in-process lock — drift writes are funneled via `wx.CallAfter` to avoid racing with user-initiated saves; a proper lock is deferred. Cold-start baseline for HWO and SPS uses the AFD pattern: first fetch stores silently, so long absences never burst notifications. Rate-limit buckets are sliding-window, not calendar-reset, avoiding the `docs/alert_audit_report.md` §7 pattern.
- **API surface parity:** Six new `Location` fields, four new `NotificationState` fields, two new `runtime_state.notification_events` sub-sections, one new `WeatherAlert.affected_zones` field, two new `AppSettings` bools — all additive, all backward-compatible via defensive `.get()`. No `schema_version` bump.
- **Integration coverage:** Unit 9 and Unit 11 both require real multi-module integration tests (pre-warm iteration + dispatch, SPS dedupe against cached alerts). Unit tests alone won't prove correctness for these. The PHI fire-weather live-verified example from 2026-04-16 is captured as a fixture for Unit 11.
- **Unchanged invariants:** Nationwide discussion dialog, AFD notification content and cadence, AFD issuance-time tracking, AFD AI-summary behavior, `schema_version`, `get_nws_discussion`'s public signature. Alert fetching returns the same shape; only the internal resolution path changes. Discussion dialog's AI visibility design (`docs/superpowers/specs/2026-04-08`) is mirrored exactly in the new panel.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| SPS zone-intersection dedupe misclassifies a Case A as Case B (double-notification) | Unit 11 replays the live-verified PHI 2026-04-16 example as a fixture; tests assert Case A → 0 notifications, Case B → 1; fallback heuristic (headline substring match) catches obvious misses. |
| SPS dedupe misclassifies a Case B as Case A (silent miss of novel capability) | Zone-intersection threshold is "any zone overlap" (conservative toward notification); headline fallback also favors notifying when ambiguous. |
| `ConfigManager.save_config` race between refresh thread and user save | `wx.CallAfter` bounce to main thread for drift persistence (Unit 3). Proper `threading.Lock` deferred to separate task. |
| Runtime state converters updated in only one direction | Unit 9 tests assert round-trip both ways; documented as "parallel update rule" in Context & Research. |
| `_pre_warm_other_locations` becomes slow with many saved locations × three products | Per-type TTL caching (AFD 1h, HWO 2h, SPS 15min) absorbs repeat calls; failure isolation prevents cascade; realistic location counts (< 20) and cache hits keep the cost bounded. Measurable via existing log timing. |
| HWO summarizer quality low on structured grid text | Length-heuristic fallback to generic copy in Unit 10; tune threshold during implementation against live products. |
| `WeatherAlert.affected_zones` not populated for legacy cache entries | Additive field with `.get()` default `[]`; dedupe falls back to headline substring match when empty. |
| wx.Notebook focus-on-tab-switch inconsistent across screen readers | `wx.CallAfter(panel.product_textctrl.SetFocus)` is the most reliable pattern in wxPython; validate manually on NVDA + JAWS before shipping. |
| Edit Location Fit-based sizer regresses on small DPI | `SetMinSize((420, -1))` preserves baseline width; validate at 100%/125%/150% DPI. |
| CLAUDE.md's Toga references mislead future agents | Project memory already flags this; docs cleanup is out of scope for PR 1 but a reasonable follow-up issue. |

## Documentation / Operational Notes

- **CHANGELOG.md** entry required (user-facing):
  - "Forecast Products dialog: AFD, HWO, and SPS in one tabbed view per location"
  - "New notifications: Hazardous Weather Outlook updates and informational Special Weather Statements"
  - "Zone metadata caching: faster alerts, fewer API calls"
- **Release note callouts:** default-ON for HWO and SPS notifications is a behavioral change from today — mention explicitly so upgraders know they can opt out.
- **No new keys in `.env.example`.** No new dependencies.
- **Monitoring:** pre-warm fetch timing and SPS dedupe outcomes are debug-logged; no new user-facing telemetry.
- **Rollout:** single shipping moment. No feature flag — the change is binary per user (they open the dialog or they don't). Revert path is `git revert` of the merge.

## Sources & References

- **Origin — Zone Enrichment:** [docs/brainstorms/2026-04-20-zone-metadata-enrichment-requirements.md](../brainstorms/2026-04-20-zone-metadata-enrichment-requirements.md)
- **Origin — Text Products Registry:** [docs/brainstorms/2026-04-20-nws-text-products-registry-requirements.md](../brainstorms/2026-04-20-nws-text-products-registry-requirements.md)
- **Upstream ideation:** [docs/ideation/2026-04-20-api-endpoints-ideation.md](../ideation/2026-04-20-api-endpoints-ideation.md)
- **Related audit (alert bug context):** [docs/alert_audit_report.md](../alert_audit_report.md) §3 and §7
- **Related design (AI visibility):** [docs/superpowers/specs/2026-04-08-discussion-dialog-ai-visibility-design.md](../superpowers/specs/2026-04-08-discussion-dialog-ai-visibility-design.md)
- **Related design (nationwide notebook precedent):** [docs/nationwide_discussions.md](../nationwide_discussions.md)
- **Key source code touchpoints:**
  - `src/accessiweather/models/weather.py:124-141`
  - `src/accessiweather/models/config.py:700-745`
  - `src/accessiweather/config/locations.py:59-70`
  - `src/accessiweather/api/nws/point_location.py:86-141`
  - `src/accessiweather/weather_client_nws.py:769-844, 873-941`
  - `src/accessiweather/cache.py:46-165, 422-455`
  - `src/accessiweather/notifications/notification_event_manager.py:182-222, 404-455`
  - `src/accessiweather/runtime_state.py:14-37, 297-340`
  - `src/accessiweather/ai_explainer.py:741, 746-941`
  - `src/accessiweather/ui/dialogs/discussion_dialog.py`
  - `src/accessiweather/ui/dialogs/location_dialog.py:81-125`
  - `src/accessiweather/ui/dialogs/settings_tabs/notifications.py:110-125`
  - `src/accessiweather/ui/main_window.py:31-40, 674-686, 1108-1290`
  - `src/accessiweather/display/presentation/forecast.py:40-51`
  - `tests/conftest.py:19-100` (wx stub pattern)
