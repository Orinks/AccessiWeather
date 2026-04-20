---
date: 2026-04-20
topic: api-endpoints
focus: underutilized endpoints across NWS, Open-Meteo, Pirate Weather, Visual Crossing
---

# Ideation: Underutilized Weather API Endpoints

## Codebase Context

AccessiWeather is a wxPython, text-first accessible weather app. Sources integrated: NWS, Open-Meteo, Pirate Weather (in-flight), Visual Crossing, AVWX. Text-over-graphics rule; graceful degradation when a source lacks a category; 5-min TTL cache keyed by location+conditions. Flagship in-flight feature: 90-minute mobility briefing using Pirate Weather minutely.

**Currently utilized endpoints:**
- NWS: `/points`, `/gridpoints` forecast + hourly, `/stations/observations`, `/alerts/active` (point + zone + state)
- Open-Meteo: `/forecast` (current/daily/hourly), `/geocoding`, `/archive` (only for history dialog)
- Pirate Weather: `/forecast` (current + daily + hourly unified); `minutely` block parsed but UI ignores; `flags` metadata ignored
- Visual Crossing: `/timeline`, air quality parsed but not displayed, `/history` method exists but UI gap
- AVWX: METAR/TAF

**Underutilized/unused endpoints:**
Pirate Weather `minutely`, Pirate Weather `flags`, VC AQI (parsed, no UI), VC `/history`, VC `/timelineBatch`, VC events API, VC stations API, Open-Meteo Archive (minimal use), Open-Meteo Marine, Open-Meteo Air Quality, Open-Meteo Pollen, Open-Meteo Ensemble, Open-Meteo Flood, Open-Meteo Solar Radiation / Evapotranspiration, NWS AFD / HWO / SPS text products, NWS marine text forecasts (CWF/NSH/OFF), NWS `/zones`, NWS `/products` catalog, NHC off-season products.

**Established constraints (from past learnings):**
- Text-over-graphics rule: no standalone radar/charts
- Graceful degradation: skip category when source lacks data
- Alert prerequisite work required before adding new alert types (single-hash state bug, hour-boundary rate-limit burst per `docs/alert_audit_report.md`)
- Pirate Weather fallback order: PW → Open-Meteo → VC
- Non-goals: model-comparison UI, raw diagnostic view, always-on hazard panels

## Ranked Ideas

### 1. NWS Text Products Registry (AFD + HWO + SPS)
**Description:** One fetcher+parser framework over NWS `/products` normalizing Area Forecast Discussion, Hazardous Weather Outlook, and Special Weather Statements into a common `TextProduct` dataclass. Surfaces forecaster narrative inline (auto-summary of AFD "KEY MESSAGES"/"SHORT TERM"), 7-day HWO horizon, and SPS quiet channel for non-warning advisories.
**Rationale:** Text-native products are accessibility gold — the nationwide forecast integration proved the pattern. Three high-value products, one pipeline. Each future product type becomes ~20 lines.
**Downsides:** Requires CWA office resolution per location (cheap with zone enrichment). Product text is jargon-heavy without an AI summary pass.
**Confidence:** 85%
**Complexity:** Medium
**Status:** Explored (brainstorm 2026-04-20 → `docs/brainstorms/2026-04-20-nws-text-products-registry-requirements.md`; bundles with #6 as PR 1)

### 2. Pirate Weather Minutely Nowcast
**Description:** Wire the already-parsed `minutely` block into a `PrecipNowcast` service powering (a) a passive text banner ("Light rain starting in 12 min, lasting ~20 min") and (b) opt-in threshold notification. Distinct from the in-flight 90-min mobility briefing — the low-effort always-on equivalent.
**Rationale:** Data parsed and thrown away today. Text equivalent to the radar loop we refuse to draw. Zero new API cost.
**Downsides:** Pirate Weather API key required; graceful degradation when absent.
**Confidence:** 90%
**Complexity:** Low
**Status:** Unexplored

### 3. Climatology Baseline — "Is This Normal?" Layer
**Description:** A `ClimatologyBaseline` service wrapping Open-Meteo Archive that, for any (location, date, metric), returns percentile, 30-year normal, record high/low, and sigma anomaly. Unlocks: inline "unusual for this date" tags on current conditions and forecast days, real data in the history dialog, seasonal context enrichment for AI explanations, "first freeze of the season" pattern alerts.
**Rationale:** Archive currently used only for one-off history comparison — wire once, unlock five features. Answers the question sighted users absorb passively ("is 92°F hot for April?") that blind users must currently leave the app to ask.
**Downsides:** History feature doc explicitly flagged caching as future work — baseline aggregation needs its own cache strategy (30-day TTL, keyed by location+date).
**Confidence:** 80%
**Complexity:** Medium
**Status:** Unexplored

### 4. Environmental Exposure Index (AQI + Pollen + UV)
**Description:** Unified `ExposureProfile` combining Open-Meteo Air Quality + Open-Meteo Pollen + Open-Meteo Solar/UV + Visual Crossing AQI (already parsed, no UI today) into a per-hour composite. Three modes: inline daily briefing line, threshold-only notifications ("tree pollen spiked from low to high"), and a configurable personal sensitivity profile.
**Rationale:** Three unused endpoints plus a clear user audience — allergy/asthma/COPD users who have high overlap with accessibility needs. Text summary is the right ergonomic for this audience, not a chart.
**Downsides:** Roadmap already lists AQ/pollen alerting — notification mode requires the alerts prerequisite work (single-hash bug, hour-boundary burst) before shipping.
**Confidence:** 85%
**Complexity:** Medium
**Status:** Unexplored

### 5. Ensemble Confidence Layer
**Description:** Fetch Open-Meteo Ensemble for every forecast view; compute member spread; attach optional confidence suffix to hourly/daily cells ("68°F, high confidence" / "chance 40%, models disagree"). Surface as a single line in AI explanations and mobility briefing — not as a comparison UI.
**Rationale:** The April 2026 mobility briefing design explicitly scopes a "confidence/disagreement line" as a deferred enhancement. This builds that primitive cleanly. Respects the "no model-comparison UI" non-goal.
**Downsides:** Ensemble endpoint heavier than standard forecast; add targeted caching. Only Open-Meteo provides ensembles — graceful degradation when other sources primary.
**Confidence:** 70%
**Complexity:** Medium
**Status:** Unexplored

### 6. Zone Metadata Enrichment Service
**Description:** At save-time, call NWS `/zones` once per location and persist: forecast zone ID, county FIPS, fire zone, marine zone, CWA office, timezone. All subsequent product/alert lookups use zone IDs directly.
**Rationale:** Quiet plumbing with disproportionate downstream dividend: zone-scoped alert keying (helps fix the single-hash alert bug), correct office routing for #1's AFD/HWO/SPS fetches, auto-activation of marine mode from water zones, county-boundary awareness. Prerequisite or co-requisite for #1 and #7.
**Downsides:** Low user-visibility on its own — value realized only through dependent features. Must handle US-only gracefully (skip for international Open-Meteo locations).
**Confidence:** 80%
**Complexity:** Low
**Status:** Explored (brainstorm 2026-04-20)

### 7. Marine & Water Context Module
**Description:** Unified `WaterContext` combining Open-Meteo Marine (wave height, period, swell direction, sea surface temp), NWS marine text forecasts (CWF/NSH/OFF), Open-Meteo Flood (`river_discharge` vs. climatology), and year-round NHC products. Auto-activates when zone enrichment detects coastal or near-river location; manual opt-in otherwise.
**Rationale:** Open-Meteo Marine has no wrapper at all. NWS marine text forecasts are text-native. Four unused endpoints into one gated module with graceful hiding when irrelevant.
**Downsides:** Discoverability — inland non-flood users should never see this. Depends on zone enrichment (#6) for clean auto-activation.
**Confidence:** 70%
**Complexity:** Medium-High
**Status:** Unexplored

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | "What Changed Since Last Check" delta briefing | Presentation layer on cached data — not an endpoint-leverage play |
| 2 | "Dictate a Location" freeform lookup | UX reshape; uses already-integrated endpoint |
| 3 | Auto-retire stale locations | Not endpoint-related; trivial local housekeeping |
| 4 | Unified WeatherStation abstraction | Abstraction-first; no concrete user win; tech debt, not a feature |
| 5 | Source Provenance pipeline (PW `flags`) | Invisible plumbing — user asked for user-facing value |
| 6 | Event-Based Historical Recall (VC events API) | Misgrounded — VC events API targets real-estate monitoring, not weather history |
| 7 | Global Travel Briefing Mode | Large scope; positioning reframe more than endpoint play |
| 8 | "Best Window" Task Planner (solar+ET) | Bold but speculative user value; better as brainstorm after a building block lands |
| 9 | "Safe to run an errand?" confidence query | Duplicates survivor #5 (Ensemble Confidence Layer) |
| 10 | Solar-Commute "sun in your eyes" line | Clever but niche; merge into #4 later |
| 11 | Proactive Pattern Alerts | Depends on alerts prerequisite work + climatology baseline (#3) |
| 12 | Batch Pre-Fetch Orchestrator | Infrastructure; not a feature v1 survivors depend on |
| — | Merged duplicates | AFD digest/auto-summary, HWO horizon, SPS channel → #1; minute-zero banner, proactive precip ping, next-60-minutes → #2; same-day-last-year, "unusual for this date" → #3; allergen briefing, auto-detected allergy days, AQI-when-bad, breathing index → #4; forecaster confidence briefing → #5; marine zone briefing, marine-mode auto-activation, silent flood-watch → #7 |

## Session Log
- 2026-04-20: Initial ideation — 41 generated across 4 frames (user pain, inversion/automation, reframing, leverage/compounding), 7 survived.
- 2026-04-20: Brainstormed #6 (Zone Metadata Enrichment) → `docs/brainstorms/2026-04-20-zone-metadata-enrichment-requirements.md`.
- 2026-04-20: Brainstormed #1 (NWS Text Products Registry) → `docs/brainstorms/2026-04-20-nws-text-products-registry-requirements.md`. Bundled with #6 as PR 1. Mid-brainstorm discovery via live NWS API probe: SPS products fall into two populations (Case A issued as alerts, Case B informational-only); Case B is the unmet need and belongs in the dialog's SPS tab. An interim split (separate SPS alert-details doc) was briefly written and discarded after verification showed the alert `description` already covers Case A content.
