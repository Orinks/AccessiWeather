---
date: 2026-04-20
topic: zone-metadata-enrichment
---

# Zone Metadata Enrichment Service (Phase 0 data layer)

> **Status:** This document is scoped as **Phase 0** of the [Forecast Products Dialog (AFD + HWO + SPS)](2026-04-20-nws-text-products-registry-requirements.md) feature, ships as **PR 1** bundled with it. PR 1 delivers: zone enrichment on save, lazy drift correction, alert-path zone reuse, and the tabbed Forecast Products dialog that is the first user-visible consumer of `cwa_office`.

## Problem Frame

AccessiWeather resolves NWS zone identifiers (forecast zone, CWA office, county) from latitude/longitude on every weather refresh via the NWS `/points` endpoint. The resolved IDs are used by `weather_client_nws.py` for alert fetching and then discarded — `cwa` and `forecastZone` are stripped by `_transform_point_data` in [api/nws/point_location.py:86-141](src/accessiweather/api/nws/point_location.py), and `fireWeatherZone`, `county`, `radarStation`, `timeZone` are extracted but only used transiently. This prevents any per-location feature from starting from a known CWA office, marine zone, or county zone without re-resolving from coordinates.

Enriching each saved location with its NWS zone metadata at save-time (with lazy backfill and opportunistic drift correction) removes that friction and makes the Text Products Registry (AFD / HWO / SPS) a straightforward consumer on top.

## Requirements

Throughout this document: `forecast_zone_id`, `cwa_office`, `county_zone_id`, `fire_zone_id`, `radar_station`, `timezone` refer to the persisted fields on the `Location` record. `forecastZone`, `cwa`, `county`, `fireWeatherZone`, `radarStation`, `timeZone` refer to the raw field names in the NWS `/points` API response.

**Data capture**
- R1. On save of a new location where the location is US (per existing `country_code == "US"` / continental-Alaska-Hawaii bbox detection in [display/presentation/forecast.py:40-50](src/accessiweather/display/presentation/forecast.py)), fetch NWS `/points` once and persist the full set of zone-metadata fields on the `Location` record: `forecast_zone_id` (from `forecastZone`), `cwa_office` (from `cwa`), `county_zone_id` (from `county`), `fire_zone_id` (from `fireWeatherZone`), `radar_station` (from `radarStation`), `timezone` (from `timeZone`). All fields are `Optional[str]`, default `None`.
- R2. For non-US locations, do not attempt NWS zone resolution. Persisted zone fields remain null.
- R3. If the `/points` call fails at save-time, save the location immediately with zone fields null. Never block the save or prompt the user. The error is logged at debug level only.

**Backfill and drift correction**
- R4. On each successful `/points` response during weather refresh, compare each freshly returned field against its stored counterpart. If a stored field is null, populate it. If a stored field differs from a non-null fresh value, overwrite silently and persist the config. **Never overwrite a populated stored value with null** (treat null/missing fresh values as "no update"). **If the `/points` call itself raises an exception, skip the drift check for that cycle; retry on the next refresh.**
- R5. Locations saved before this feature shipped get their zone fields populated opportunistically via R4 the first time their weather is refreshed. No explicit migration step.

**Consumption**
- R6. Alert fetching in `weather_client_nws.py` uses stored zone values when present, skipping the redundant per-refresh zone resolution path. Specifically:
  - `alert_radius_type="county"` (default) path uses stored `county_zone_id` when present.
  - `alert_radius_type="zone"` path uses stored `forecast_zone_id` when present.
  - Either path falls back to the existing `/points`-derived resolution when the stored value is null.
- R7. The [Forecast Products Dialog (AFD + HWO + SPS)](2026-04-20-nws-text-products-registry-requirements.md) bundled in PR 1 uses stored `cwa_office` for all three product lookups. Future features (Marine & Water Context #7, fire-weather products, etc.) can rely on the corresponding stored fields being populated for any US saved location that has been refreshed at least once.

**User visibility**
- R8. The Edit Location dialog ([ui/dialogs/location_dialog.py:81-125](src/accessiweather/ui/dialogs/location_dialog.py)) gains a read-only informational section displaying the stored `forecast_zone_id` and `cwa_office` with label-prefixed format using `wx.StaticText`:
  - `Forecast Zone: NCZ027`
  - `NWS Office: RAH`
  - (Other captured fields — county, fire zone, radar station, timezone — are NOT surfaced in this release; they're plumbing for downstream features.)
  - Pattern matches the existing name-label at line 97. No refresh button; no editability. The dialog's fixed `size=(420, 200)` at line 89 must be resized or switched to a Fit-based sizer to accommodate the added rows.
- R9. Null-state display:
  - **Non-US location** (R2 path): the two zone rows are hidden entirely — showing them with a "Not applicable" message would be noise in the common international case.
  - **US location, zone fields null** (R3 failed or pre-feature save not yet refreshed): displays "Forecast Zone: Not yet resolved — will populate after next weather refresh" / "NWS Office: Not yet resolved — ...".
  - **US location, one of two fields populated** (rare partial response): display the populated value; display the other field with the US-null message above.

## Success Criteria

- A saved US location that has been refreshed at least once has non-null `forecast_zone_id`, `cwa_office`, `county_zone_id`, `fire_zone_id`, `radar_station`, `timezone` in the persisted JSON config (excepting genuine NWS coverage gaps).
- Alert fetch under the default `alert_radius_type="county"` no longer re-resolves the county zone from lat/lon for locations with stored values.
- The NWS Text Products Registry consumes `cwa_office` directly at fetch time; its planning doc needs no zone-resolution scope.
- Edit Location dialog announces the cached forecast zone and CWA office via screen reader as label-prefixed values.
- A boundary change (simulated by editing stored values in config and re-opening) is silently corrected on the next weather refresh — user sees the updated values in Edit Location without any manual action.
- No new user-facing failure modes introduced: save works on flaky networks, save works for non-US locations, save works for coordinates with genuine NWS coverage gaps.

## Scope Boundaries

- **Marine Mode auto-activation is NOT included.** The Marine Mode checkbox in Edit Location remains a manual user toggle. Marine zone ID isn't among the captured fields in this release — that's deferred to the Marine & Water Context Module (ideation #7), which will extend capture when it lands. (Rationale: marine zone requires a separate NWS call today; adding it would expand scope beyond the `/points`-already-fetched pass.)
- **Single-hash alert bug is NOT addressed here.** Per [docs/alert_audit_report.md](docs/alert_audit_report.md) that bug is about severity-history tracking (deque), not zone-based keying. Coordinate separately.
- **Boundary polygon storage and travel-mode "you crossed into a different zone" detection are NOT in scope.**
- **No manual "Refresh zone data" button.** Opportunistic validation on refresh handles drift.
- **No config schema version bump.** Defensive `.get()` with null defaults matches the existing pattern in `AppConfig.to_dict` / `AppSettings.from_dict`.
- **Fields beyond forecast zone + CWA office are NOT surfaced in the UI in this release.** They're captured but hidden until a downstream feature uses them. Surfacing can be added incrementally.

## Key Decisions

- **Bundle with Forecast Products Dialog (AFD + HWO + SPS) as PR 1** — Phase 0 alone has limited user-visible value (alert-path zone reuse reduces API load, but is invisible). The full Forecast Products dialog is the first real consumer and makes drift correction end-to-end testable. One shipping moment.
- **Broaden capture to all six `/points`-returned fields** — marginal cost is near zero since `/points` is already fetched and the fields are already parsed. Amortizes across current (AFD + HWO + SPS) and future (Marine Context, fire-weather products) consumers.
- **Save without zones, retry lazily** — never block the user on `/points` availability. Self-healing and network-tolerant.
- **Opportunistic validation over TTL or startup scan** — reuse the `/points` call already happening every refresh. Zero extra API cost; drift corrects when the user next refreshes that location.
- **Label-prefixed raw IDs in UI** — "Forecast Zone: NCZ027" gives screen-reader users honest, copy-pasteable support context without the scope of fetching human-readable zone names.
- **Expose only forecast zone + CWA office in UI for this release** — remaining fields are plumbing; surfacing them would add dialog rows with no current user value.
- **Extend existing `Location` dataclass rather than introduce a side cache** — zones are per-location metadata, not cache. Single source of truth.

## Dependencies / Assumptions

- Assumes the NWS `/points` response field names (`forecastZone`, `cwa`, `county`, `fireWeatherZone`, `radarStation`, `timeZone`) remain stable. All six are already exposed by the generated API client at [weather_gov_api_client/models/point.py](src/accessiweather/weather_gov_api_client/models/point.py).
- Assumes `Location` dataclass in [models/weather.py:124-141](src/accessiweather/models/weather.py) can gain six optional fields without breaking the existing config round-trip (consistent with how `country_code` and `marine_mode` were added — defensive `.get()` with null defaults in `AppConfig.to_dict` / `from_dict`).
- The Text Products Registry brainstorm/plan is a direct sibling of this work and will share the same PR.

## Outstanding Questions

### Deferred to Planning
- [Affects R1/R4][Technical] `api/nws/point_location.py:86-141` currently strips `cwa` and `forecastZone` from the transformed point response — only `county`, `fireWeatherZone`, `timeZone`, `radarStation` pass through. The transform must be extended to include all six zone fields, OR the new enrichment path must read from the raw point response directly. Planning picks the cleaner integration.
- [Affects R6][Technical] Exact integration point — whether to short-circuit in `weather_client_nws.py` at the alert-fetch callers (lines 873-941) or push the stored-value preference into `point_location.py`. The county-path (873-890) and zone-path (915-941) have different shapes; planning resolves.
- [Affects R4][Technical] Whether the opportunistic persist-on-drift should fire synchronously during the weather refresh or be queued. `LocationOperations.update_location_marine_mode` at [config/locations.py:59-70](src/accessiweather/config/locations.py) is the closest template (synchronous `save_config()`). Also: thread-safety of `save_config` from the refresh thread needs verification.
- [Affects R8][Technical] `EditLocationDialog` fixed `size=(420, 200)` at [ui/dialogs/location_dialog.py:89](src/accessiweather/ui/dialogs/location_dialog.py) will clip content with two added rows. Resize or switch to Fit-based sizer.
- [Affects R8][Design] Announcement order of the two fields, tab-order position relative to the marine-mode checkbox, and whether to group under a `wx.StaticBox` with a section heading like "NWS Zone Information". Small UX decisions resolvable during planning.
- [Affects R8][Design] Whether an already-open Edit Location dialog should reflect drift-corrected values live or read only from the snapshot taken at dialog open. Minor edge case; default to snapshot-at-open unless planning surfaces a user-visible problem.

## Next Steps
-> `/ce:plan` for the combined **PR 1**: Phase 0 Zone Metadata Enrichment + Forecast Products Dialog (AFD + HWO + SPS). The plan treats Phase 0 as the data layer and the Forecast Products dialog as the first user-visible consumer.
