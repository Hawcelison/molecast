# Molecast Cleanup Audit

Audit date: 2026-04-29

Scope guard: this audit classifies the current dirty working tree only. It does not delete, rewrite, commit, or clean any files.

Requirements alignment: I did not find a standalone project requirements document in the repo by filename/content search. The repo README states the baseline as "Local Docker-based weather dashboard built with FastAPI, HTMX, and SQLite" (`README.md:3`). This audit also aligns with the supplied cleanup requirements: local Docker hosting, NWS-backed severe weather alerts, 60 second refresh, external local test alerts, NWS-style top banners, saved state, responsive UI, modular alert audio/flashing/settings, multi-client readiness, and ZIP/package cleanliness.

## 1. Current Git Status Summary

Tracked modified files:

- `backend/app/services/alert_scoring.py`
- `backend/app/services/alert_service.py`
- `backend/app/static/css/app.css`
- `backend/app/static/js/app.js`
- `backend/app/static/js/test-alerts.js`
- `backend/app/templates/dashboard.html`
- `backend/requirements.txt`
- `test/alerts_test.json`

Untracked paths:

- `audit/`
- `backend/app/alerts/`
- `backend/app/static/js/modules/`
- `backend/app/static/sounds/`
- `tests/manual/`
- `tests/unit/test_alert_catalog.py`
- `tests/unit/test_alert_geocodes.py`
- `tests/unit/test_alert_normalize.py`
- `tests/unit/test_alert_scoring.py`
- `tests/unit/test_alert_service_nws_zones.py`

Ignored/generated files observed with `git status --short --ignored`:

- `data/logs/molecast.log`
- `data/logs/molecast.log.2026-04-28`
- `test/alerts_test.json.bak`
- multiple `__pycache__/` and `*.pyc` files under `backend/`, `tests/`, and `tools/`

## 2. File-By-File Classification

| File/path | Classification | Reason |
|---|---|---|
| `backend/app/alerts/__init__.py` | KEEP | New alert domain package marker. |
| `backend/app/alerts/catalog.py` | KEEP | Loads hazard catalog and exposes backend color/priority/icon lookup. Intended single source of truth. |
| `backend/app/alerts/data/__init__.py` | KEEP | Required for packaged resource loading. |
| `backend/app/alerts/data/nws_hazards.json` | KEEP | Backend hazard catalog data. Package it and use it as source of truth. |
| `backend/app/alerts/enums.py` | KEEP BUT REVIEW | Contains source/provider enum concepts, but current code does not appear to import it yet. |
| `backend/app/alerts/geocodes.py` | KEEP | SAME/UGC parser preserves strings and C/Z distinction. |
| `backend/app/alerts/models.py` | KEEP | New `MolecastAlert` domain model covers broad NWS fields. |
| `backend/app/alerts/normalize.py` | KEEP | New NWS feature normalization preserving raw fields, parameters, geocode, and catalog fields. |
| `backend/app/alerts/scoring.py` | KEEP | New alert scoring implementation. |
| `backend/app/services/alert_scoring.py` | COMPATIBILITY WRAPPER | Re-exports `app.alerts.scoring`; old imports still exist in tests and service code. |
| `backend/app/services/alert_service.py` | KEEP BUT REVIEW | Still owns provider, ingestion orchestration, active alert cache, NWS parsing, and old DTO conversion. Should be split or converted after migration. |
| `backend/app/services/test_alert_loader.py` | KEEP BUT REVIEW | Canonical local test alert loader, but path resolution and validation overlap with route code. |
| `backend/app/services/alert_matcher.py` | KEEP BUT REVIEW | Still old service-layer matcher; no new `app.alerts` equivalent exists. |
| `backend/app/services/alert_presentation.py` | KEEP | Backend presentation DTO builder used by `/api/alerts/active`. |
| `backend/app/services/alert_time.py` | KEEP | UTC parsing/validation remains shared and tested. |
| `backend/app/alert_ingestion.py` | KEEP | Startup ingestion loop entrypoint. |
| `backend/app/api/routes/alerts.py` | KEEP BUT REVIEW | Thin enough, but still depends on old service module and presentation builder. |
| `backend/app/api/routes/test_alerts.py` | KEEP BUT REVIEW | Local editor API works, but contains duplicated loader/path/time/count validation logic. |
| `backend/app/static/js/modules/alerts-api.js` | KEEP | Frontend API boundary; uses backend endpoint only. |
| `backend/app/static/js/modules/alert-banners.js` | KEEP BUT REVIEW | Main top-banner renderer. Contains duplicate priority/event sets that should come from backend DTOs/catalog. |
| `backend/app/static/js/modules/alert-audio.js` | KEEP BUT REVIEW | Modular audio behavior. Contains local sound/event mapping that should align with backend `sound_profile`. |
| `backend/app/static/js/modules/alert-flash.js` | KEEP | Modular flashing behavior with reduced-motion/settings checks. |
| `backend/app/static/js/modules/alert-icons.js` | KEEP BUT REVIEW | Duplicate icon/event mapping remains despite backend `icon` field. |
| `backend/app/static/js/modules/settings-store.js` | KEEP | Persistent UI settings in localStorage. |
| `backend/app/static/sounds/airraid.mp3` | KEEP BUT REVIEW | Required by alert audio module. Confirm license/source before packaging. |
| `backend/app/static/sounds/default.mp3` | KEEP BUT REVIEW | Required by alert audio module. Confirm license/source before packaging. |
| `backend/app/static/sounds/tornado.mp3` | KEEP BUT REVIEW | Required by alert audio module. Confirm license/source before packaging. |
| `backend/app/static/js/nws-colors.js` | REMOVE CANDIDATE | Legacy hard-coded frontend color map; keep until backend DTO color coverage is confirmed everywhere. |
| `backend/app/static/js/app.js` | KEEP BUT REVIEW | Dashboard card renderer plus polling; partly duplicates banner color/render logic. |
| `backend/app/static/js/test-alerts.js` | KEEP BUT REVIEW | Test editor client. Uses legacy `NWS_DEFAULT_ALERT_COLOR`; depends on `nws-colors.js`. |
| `backend/app/static/css/app.css` | KEEP BUT REVIEW | Modified for dashboard/banner UI. Needs responsive visual check. |
| `backend/app/templates/dashboard.html` | KEEP | Wires banner controls/container and modular scripts. |
| `backend/requirements.txt` | KEEP BUT REVIEW | Modified dependency file. Confirm new deps are required and package-friendly. |
| `test/alerts_test.json` | KEEP | Canonical external local test-alert file. |
| `tests/unit/test_alert_catalog.py` | KEEP | Covers hazard catalog. |
| `tests/unit/test_alert_geocodes.py` | KEEP | Covers SAME/UGC leading zero and C/Z behavior. |
| `tests/unit/test_alert_normalize.py` | KEEP | Covers NWS normalization and field preservation. |
| `tests/unit/test_alert_scoring.py` | KEEP | Covers new scoring plus compatibility wrapper. |
| `tests/unit/test_alert_service_nws_zones.py` | KEEP | Covers point/zone NWS provider behavior and fallback to test alerts. |
| `tests/manual/alert-banner-modules.md` | KEEP | Manual checklist for alert banners/audio/flashing until JS tests exist. |
| `audit/*.txt`, `audit/*.patch` | KEEP BUT REVIEW | Useful evidence snapshots for cleanup, but should not ship in final app ZIP unless audit artifacts are intentionally included. |
| `audit/MOLECAST_CLEANUP_AUDIT.md` | KEEP | This requested audit. |
| `test/alerts_test.json.bak` | GENERATED/JUNK | Backup file from editor save. Already ignored by `*.bak`; remove only when allowed. |
| `**/__pycache__/`, `*.pyc` | GENERATED/JUNK | Python bytecode. Already ignored by `.gitignore`; remove only when allowed. |
| `data/logs/*.log*` | GENERATED/JUNK | Runtime logs. Already ignored. |
| `node_modules/` seen in audit snapshot | GENERATED/JUNK | Should stay ignored and excluded from package/ZIP. Not currently shown as untracked in current status. |

## 3. Backend Alert Architecture Map

Current backend flow:

1. `backend/app/main.py` lifespan starts `run_alert_ingestion(settings)` with `asyncio.create_task`.
2. `backend/app/alert_ingestion.py` loops forever, sleeps `settings.alert_refresh_seconds`, opens a DB session, loads the active location, and calls `active_alert_service.refresh_active_alerts`.
3. `backend/app/services/alert_service.py` owns `NwsAlertProvider`, `ActiveAlertService`, live NWS fetch, point metadata lookup, zone alert fetch, dedupe, local test alert merge, old `parse_nws_alerts`, cache lifecycle, and final priority sorting.
4. `backend/app/services/test_alert_loader.py` reads `settings.test_alerts_file` and converts enabled local test alerts into NWS-like GeoJSON features.
5. `backend/app/services/alert_matcher.py` matches by geometry, county, and fallback state text.
6. `backend/app/services/alert_scoring.py` is now a compatibility wrapper around `backend/app/alerts/scoring.py`.
7. `backend/app/services/alert_presentation.py` builds API presentation DTO fields for `/api/alerts/active`.
8. `backend/app/api/routes/alerts.py` returns `ActiveAlertsResponse` using `active_alert_service.get_active_alerts` and `build_alert_presentations`.

New backend domain package:

- `backend/app/alerts/models.py`: broad `MolecastAlert` domain model.
- `backend/app/alerts/normalize.py`: NWS GeoJSON feature collection normalizer.
- `backend/app/alerts/geocodes.py`: SAME/UGC parser.
- `backend/app/alerts/catalog.py` plus `data/nws_hazards.json`: hazard color/priority/icon/sound catalog.
- `backend/app/alerts/scoring.py`: score/rank/sort helpers.

Architecture gap: the new `app.alerts.normalize.MolecastAlert` pipeline is not yet wired into `ActiveAlertService` or `/api/alerts/active`. The active API still returns `app.schemas.alert.WeatherAlert`/`AlertPresentation`, so new NWS field coverage is currently tested in the new package but not exposed through the live dashboard DTO.

## 4. Frontend Alert Architecture Map

Current frontend flow:

1. `backend/app/templates/base.html` loads legacy globals: `nws-colors.js`, map/radar JS, then `app.js`.
2. `backend/app/templates/dashboard.html` adds modular alert scripts: `settings-store.js`, `alerts-api.js`, `alert-icons.js`, `alert-flash.js`, `alert-audio.js`, `alert-banners.js`.
3. `backend/app/static/js/modules/alerts-api.js` fetches `/api/alerts/active` only.
4. `backend/app/static/js/app.js` polls active alerts, renders the existing alert card list, and delegates top banners to `MolecastAlertBanners`.
5. `backend/app/static/js/modules/alert-banners.js` renders top banners, controls, expand/collapse, live-region behavior, scroll, audio triggers, and flashing triggers.
6. `backend/app/static/js/modules/settings-store.js` persists alert UI settings in `localStorage`.
7. `backend/app/static/js/modules/alert-audio.js` chooses and rate-limits local sound profiles.
8. `backend/app/static/js/modules/alert-flash.js` flashes page background unless reduced motion or disabled.
9. `backend/app/static/js/modules/alert-icons.js` maps backend icon names or event names to visible symbols.

Frontend gap: banner rendering, card rendering, icon choice, high-priority event lists, audio profile mapping, and legacy color fallback still contain local logic. That is acceptable as compatibility scaffolding, but final architecture should make backend DTOs authoritative for event metadata and leave the frontend mostly rendering DTO fields.

## 5. Duplicate Logic Audit

Alert scoring:

- New source: `backend/app/alerts/scoring.py`.
- Compatibility wrapper: `backend/app/services/alert_scoring.py`.
- Old service dependency remains: `backend/app/services/alert_service.py` imports from `app.services.alert_scoring`.
- Status: duplicate module path, not duplicate implementation. Keep wrapper until imports move to `app.alerts.scoring`.

Alert service/ingestion:

- Main active service remains `backend/app/services/alert_service.py`.
- Background loop is `backend/app/alert_ingestion.py`.
- New `app.alerts` has normalization/scoring/catalog/geocodes, but no provider/service/ingestion owner yet.
- Status: partial refactor. Do not remove old service until provider, cache, matching, test alert merge, lifecycle, and route DTOs move or are wrapped.

Test alert loading:

- Runtime loader: `backend/app/services/test_alert_loader.py`.
- Editor route duplicates path resolution, reading, active counting, UTC parsing, and validation: `backend/app/api/routes/test_alerts.py`.
- Status: real duplication. Consolidate around one service/repository for canonical file path, read/write, validation, and active count.

NWS provider:

- Only provider implementation found: `NwsAlertProvider` in `backend/app/services/alert_service.py`.
- No new `backend/app/alerts/provider.py` or equivalent exists.
- Status: no duplicate provider, but provider is in old service layer and should be moved before removing old service.

SAME/UGC parsing:

- New parser: `backend/app/alerts/geocodes.py`.
- Old active alert parser does not parse SAME/UGC for API DTOs; it leaves raw geocode inside `raw_properties`.
- Status: no duplicate parser, but active runtime path is not yet using normalized SAME/UGC output.

Hazard colors/catalog:

- Backend catalog source: `backend/app/alerts/data/nws_hazards.json` via `backend/app/alerts/catalog.py`.
- Frontend hard-coded colors remain in `backend/app/static/js/nws-colors.js`.
- Frontend hard-coded icons remain in `backend/app/static/js/modules/alert-icons.js`.
- Frontend hard-coded high-priority events remain in `backend/app/static/js/modules/alert-banners.js`.
- Frontend audio profile mapping remains in `backend/app/static/js/modules/alert-audio.js`.
- Status: duplicate hazard metadata remains. Backend catalog should be authoritative.

Alert banner rendering:

- Top banners: `backend/app/static/js/modules/alert-banners.js`.
- Alert cards: `backend/app/static/js/app.js`.
- Status: separate UI surfaces, but both render alert color/title/source/expiry. Keep both only if dashboard needs both card list and top banners.

Audio/flashing/settings:

- Audio: `alert-audio.js`.
- Flashing: `alert-flash.js`.
- Settings: `settings-store.js`.
- Banner controls: `alert-banners.js`.
- Status: modular but tightly coupled through globals. No direct duplicate settings store found.

## 6. Import Audit

Old `app.services` alert imports found:

- `backend/app/alert_ingestion.py`: `app.services.location_service`, `app.services.alert_service.AlertFetchError`, `active_alert_service`.
- `backend/app/api/routes/alerts.py`: `app.services.location_service`, `app.services.alert_presentation.build_alert_presentations`, `app.services.alert_service.AlertFetchError`, `active_alert_service`.
- `backend/app/api/routes/test_alerts.py`: `app.services.location_service`, `app.services.alert_service.active_alert_service`, `app.services.alert_time`.
- `backend/app/services/alert_service.py`: `app.services.alert_matcher`, `app.services.alert_scoring`, `app.services.alert_time`, `app.services.test_alert_loader`.
- `backend/app/services/test_alert_loader.py`: `app.services.alert_time`.
- `backend/app/services/alert_presentation.py`: `app.services.alert_time`.
- Tests: `tests/unit/test_alert_scoring.py`, `tests/unit/test_alert_service_nws_zones.py`, `tests/unit/test_alert_time.py`, `tests/unit/test_alert_service_time_validation.py`, `tests/unit/test_alert_presentation.py`.

New `app.alerts` imports found:

- `backend/app/services/alert_scoring.py`: imports and re-exports `app.alerts.scoring`.
- `backend/app/alerts/scoring.py`: imports `app.alerts.models.AlertPriority`.
- `backend/app/alerts/normalize.py`: imports `app.alerts.catalog`, `app.alerts.geocodes`, `app.alerts.models`.
- `backend/app/alerts/catalog.py`: loads `app.alerts.data.nws_hazards.json`.
- Tests: `tests/unit/test_alert_scoring.py`, `tests/unit/test_alert_geocodes.py`, `tests/unit/test_alert_catalog.py`, `tests/unit/test_alert_normalize.py`.

Files still depending on old alert service modules:

- Runtime-critical: `backend/app/main.py`, `backend/app/alert_ingestion.py`, `backend/app/api/routes/alerts.py`, `backend/app/api/routes/test_alerts.py`, `backend/app/services/alert_service.py`, `backend/app/services/test_alert_loader.py`, `backend/app/services/alert_presentation.py`.
- Tests: `tests/unit/test_alert_service_nws_zones.py`, `tests/unit/test_alert_service_time_validation.py`, `tests/unit/test_alert_presentation.py`, `tests/unit/test_alert_time.py`, compatibility part of `tests/unit/test_alert_scoring.py`.

Conclusion: old service modules cannot be removed now. `alert_scoring.py` can remain as a wrapper. `alert_service.py` needs either migration or wrapper conversion after the runtime path no longer imports its internals.

## 7. Ingestion/Process Audit

Alert ingestion loops:

- Backend ingestion loop count: 1. `run_alert_ingestion` in `backend/app/alert_ingestion.py` contains the only backend `while True` alert refresh loop found.
- Frontend alert polling loop count: 1. `backend/app/static/js/app.js` schedules `loadAlerts` with `setTimeout` using the backend refresh interval, defaulting to 60 seconds.
- Non-ingestion timers: radar animation interval, alert audio repeat interval, alert flashing interval, map/county-boundary init retries.

Startup entrypoint:

- `backend/app/main.py` lifespan creates the ingestion task with `asyncio.create_task(run_alert_ingestion(settings))`.
- Shutdown calls `stop_alert_ingestion(alert_ingestion_task)`.

Old and new schedulers:

- No second backend alert scheduler was found.
- Old cache/lifecycle logic remains inside `ActiveAlertService`.
- New `app.alerts` modules do not define a scheduler.

## 8. NWS Field Coverage Audit

Coverage legend:

- PRESENT: normalized into `MolecastAlert` by `backend/app/alerts/normalize.py`.
- PARTIAL: present only in raw data, old active DTO, or indirectly; not consistently first-class through the live `/api/alerts/active` DTO.
- MISSING: no direct coverage found.

| Field | Coverage | Notes |
|---|---|---|
| `id` | PRESENT | New model and old DTO both include `id`. |
| `canonical_id` | PRESENT | New model includes it; banner code can read it. Old active DTO does not expose it. |
| `raw_id` | PRESENT | New model includes it. |
| `source` | PRESENT | New model and old DTO include it. |
| `sent` | PRESENT | New model includes it. Old active DTO does not. |
| `effective` | PRESENT | New model and old DTO include it. |
| `onset` | PRESENT | New model includes it. Old active DTO does not. |
| `expires` | PRESENT | New model and old DTO include it. |
| `ends` | PRESENT | New model includes it. Old active DTO does not. |
| `eventEndingTime` | PRESENT | New model maps it from `parameters`. |
| `status` | PRESENT | New model includes it. |
| `messageType` | PRESENT | New model includes it. |
| `references` | PRESENT | New model includes it. |
| `event` | PRESENT | New model and old DTO include it. |
| `eventCode` | PRESENT | New model includes normalized dict. |
| `category` | PRESENT | New model includes list. |
| `response` | PRESENT | New model includes list. |
| `severity` | PRESENT | New model and old DTO include it. |
| `urgency` | PRESENT | New model and old DTO include it. |
| `certainty` | PRESENT | New model and old DTO include it. |
| `headline` | PRESENT | New model and old DTO include it. |
| `description` | PRESENT | New model and old DTO include it. |
| `instruction` | PARTIAL | New model includes it. Old active DTO only keeps it in `raw_properties`; presentation tags inspect raw fields. |
| `sender` | PRESENT | New model includes it. |
| `senderName` | PRESENT | New model includes it. |
| `web` | PRESENT | New model includes it. |
| `contact` | PRESENT | New model includes it. |
| `areaDesc` | PRESENT | New model and old DTO include it. |
| `geometry` | PRESENT | New model and old DTO include it. |
| `affectedZones` | PRESENT | New model includes list. |
| `geocode` | PRESENT | New model includes normalized geocode plus raw geocode. |
| `SAME` | PRESENT | Parsed under new `geocode.same`; raw preserved. |
| `UGC` | PRESENT | Parsed under new `geocode.ugc`; raw preserved. |
| `parameters` | PRESENT | New model includes normalized `dict[str, list[str]]`; old DTO preserves raw only. |
| `raw_properties` | PRESENT | New model and old DTO preserve it. |
| `raw_feature` | PRESENT | New model preserves it. Old active DTO does not. |

Runtime API warning: field coverage is strong in the new normalizer, but `/api/alerts/active` still uses old `WeatherAlert`/`AlertPresentation`, so many PRESENT fields are not yet exposed to the dashboard.

## 9. SAME/UGC Audit

SAME preservation:

- `parse_same` accepts exactly six digits via regex and stores `original` as `str(value)`.
- Leading zeroes are preserved: `tests/unit/test_alert_geocodes.py` asserts `"026077"` remains `"026077"` and county FIPS remains `"077"`.

UGC C/Z handling:

- `parse_ugc` matches `^([A-Z]{2})([CZ])(\d{3}|ALL)$`.
- It maps `C` to `county` and `Z` to `zone`.
- Tests cover `MIC077`, `MIZ072`, `MICALL`, and `MIZ000`.

Tests:

- `tests/unit/test_alert_geocodes.py` covers direct SAME and UGC parsing.
- `tests/unit/test_alert_normalize.py` covers normalized geocode preservation inside a NWS feature.

Int conversion bugs:

- No Python `int()` conversion of SAME/UGC codes was found in backend alert/geocode paths.
- JavaScript `Number.parseInt` uses found in alert banner color hex parsing and test editor hour offsets, not SAME/UGC code parsing.
- Current SAME/UGC path is string-safe. Keep it that way.

## 10. Hazard Catalog/Color Audit

Intended single source of truth:

- `backend/app/alerts/data/nws_hazards.json` loaded through `backend/app/alerts/catalog.py`.

Remaining hard-coded color/catalog-like maps:

- `backend/app/static/js/nws-colors.js`: `NWS_EVENT_COLORS`, `NWS_SEVERITY_COLORS`, `DEFAULT_ALERT_COLOR`.
- `backend/app/static/js/modules/alert-icons.js`: event icon map and named icon map.
- `backend/app/static/js/modules/alert-banners.js`: `HIGH_PRIORITY_EVENTS`.
- `backend/app/static/js/modules/alert-audio.js`: `PROFILE_SOUNDS`, event-to-profile rules.
- `backend/app/alerts/catalog.py`: `SEVERITY_COLOR_FALLBACKS` and severity priority fallback are acceptable backend fallback logic, but should stay centralized.

Cleanup target: backend should emit `color_hex`, `icon`, `priority`, `sound_profile`, and any assertive/flash flags from the catalog. Frontend should treat `nws-colors.js` and local event maps as fallback-only, then remove them after DTO coverage and tests are complete.

## 11. Frontend Audit

`/api/alerts/active` usage:

- Confirmed in `backend/app/static/js/modules/alerts-api.js`.
- `backend/app/static/js/app.js` calls `window.MolecastAlertsApi.fetchActiveAlerts()`.

No frontend NWS API calls:

- No `api.weather.gov` frontend fetch was found.
- `api.weather.gov` appears in backend config/constants and external Mapbox script URLs only for Mapbox assets in templates, not alert ingestion.

Frontend modules:

- Banners: `backend/app/static/js/modules/alert-banners.js`.
- API boundary: `backend/app/static/js/modules/alerts-api.js`.
- Audio: `backend/app/static/js/modules/alert-audio.js`.
- Flashing: `backend/app/static/js/modules/alert-flash.js`.
- Persistent settings: `backend/app/static/js/modules/settings-store.js`.
- Icons: `backend/app/static/js/modules/alert-icons.js`.
- Legacy colors: `backend/app/static/js/nws-colors.js`.

Review items:

- `alert-banners.js` sorts client-side by `priority`/`priority_score`; backend should remain authoritative for order.
- `app.js` and `alert-banners.js` both render alert UI. Decide whether both surfaces are required.
- `alert-audio.js` profile names do not fully align with catalog values: catalog examples use `default`/`tornado`, while audio module recognizes `standard_alert`/`tornado_siren`/`air_raid`/`ebs_purge`.

## 12. Test Audit

Tracked existing tests:

- `tests/integration/test_health.py`
- `tests/unit/test_alert_presentation.py`
- `tests/unit/test_alert_service_time_validation.py`
- `tests/unit/test_alert_time.py`
- `tests/unit/test_weather_service.py`

New untracked unit tests:

- `tests/unit/test_alert_catalog.py`
- `tests/unit/test_alert_geocodes.py`
- `tests/unit/test_alert_normalize.py`
- `tests/unit/test_alert_scoring.py`
- `tests/unit/test_alert_service_nws_zones.py`

New untracked manual tests:

- `tests/manual/alert-banner-modules.md`

Missing or recommended tests:

- Runtime integration test proving `/api/alerts/active` exposes backend catalog fields needed by frontend (`color_hex`, `icon`, `sound_profile`, `canonical_id`, possibly `priority`).
- Test that active runtime ingestion uses normalized SAME/UGC where intended, not only raw properties.
- Test for test alert route/service consolidation once duplicated path/read/write logic is moved.
- Frontend unit tests for `alerts-api.js`, banner rendering, settings persistence, audio gating, reduced-motion flashing behavior, and no direct NWS calls.
- Packaging test or script that builds a ZIP excluding logs, caches, backups, node_modules, local DB runtime files, and audit scratch artifacts unless intentionally included.
- Multi-client readiness test or design proof for shared alert state if acknowledged/silenced state must be server-side rather than per-browser localStorage.

## 13. Cleanup Plan

Safe files to keep:

- `backend/app/alerts/**`
- `backend/app/static/js/modules/**`
- `backend/app/static/sounds/*.mp3` after license/source review
- new unit tests and manual checklist
- modified dashboard/template/CSS files after visual verification
- `test/alerts_test.json` as canonical external local test alert file

Files to convert to wrappers:

- `backend/app/services/alert_scoring.py`: already a wrapper. Keep until old imports are gone.
- `backend/app/services/alert_service.py`: eventually split into provider, active alert lifecycle, parser/normalizer adapter, and compatibility wrapper. Do not convert yet.
- Potential future wrappers: `alert_matcher.py`, `test_alert_loader.py`, and `alert_presentation.py` only after new homes exist and runtime imports migrate.

Files to remove only after grep confirms no imports/usages:

- `backend/app/static/js/nws-colors.js`, after backend DTO color coverage and test editor fallback use are migrated.
- Frontend event maps in `alert-icons.js`, `alert-banners.js`, and `alert-audio.js`, after backend catalog fields are complete and exposed.
- Any old service modules only after `rg "app\\.services\\.alert_|from app\\.services\\.alert"` shows no runtime/test dependency except intended wrappers.
- Audit scratch files under `audit/*.txt` and `audit/*.patch` only if they are not needed as review evidence.

Generated files to ignore/delete when allowed:

- `test/alerts_test.json.bak`
- `**/__pycache__/`
- `*.pyc`
- `data/logs/*.log*`
- `node_modules/`

Recommended `.gitignore` changes:

- Current `.gitignore` already covers `__pycache__/`, `*.pyc`, `.pytest_cache/`, `node_modules/`, `*.bak`, `*.log`, `data/logs/`, env files, and common OS/IDE files.
- Consider adding `audit/*.patch`, `audit/git-*.txt`, `audit/*before-cleanup*.txt`, and `audit/untracked-files.txt` if these are intended as local scratch artifacts rather than committed audit deliverables.
- Consider explicitly ignoring packaged ZIP output, for example `dist/`, `build/`, `*.zip`, unless release ZIPs are intentionally versioned.
- Consider ignoring local SQLite runtime files such as `data/*.sqlite3`, while deciding whether seed/sample DBs belong in the repo.

## 14. Recommended Commit Sequence

1. Commit backend alert domain foundations: `backend/app/alerts/**` plus `tests/unit/test_alert_catalog.py`, `tests/unit/test_alert_geocodes.py`, `tests/unit/test_alert_normalize.py`, and scoring wrapper/test if desired.
2. Commit NWS provider and active-service changes: `backend/app/services/alert_service.py`, `tests/unit/test_alert_service_nws_zones.py`, and any time-validation updates.
3. Commit local test alert editor/runtime changes: `test/alerts_test.json`, `backend/app/static/js/test-alerts.js`, and route/loader changes after duplicate logic is consolidated or accepted.
4. Commit frontend alert modules: `dashboard.html`, `app.css`, `app.js`, `backend/app/static/js/modules/**`, `backend/app/static/sounds/**`, and `tests/manual/alert-banner-modules.md`.
5. Commit dependency/package updates: `backend/requirements.txt`, package data handling for `nws_hazards.json`, and `.gitignore` cleanup.
6. Commit audit/docs separately if desired: `audit/MOLECAST_CLEANUP_AUDIT.md`; exclude scratch audit patches/status files unless needed for review history.

## 15. Risks If Cleanup Is Done Too Aggressively

- Removing `backend/app/services/alert_service.py` now would break the startup ingestion task, `/api/alerts/active`, `/api/test-alerts`, and several tests.
- Removing `backend/app/services/alert_scoring.py` now would break old imports even though the implementation moved cleanly.
- Removing `nws-colors.js` now may break test editor and legacy dashboard color fallback behavior before all DTO fields are guaranteed.
- Deleting untracked `backend/app/alerts/**` would lose the new normalization, catalog, scoring, and SAME/UGC work.
- Deleting untracked tests would remove the only coverage for the new alert domain package.
- Treating sound files as junk would break alert audio profiles.
- Cleaning backups/logs/cache is safe only when explicitly allowed; current instruction forbids deletion.
- Moving test alert path logic too quickly can break the canonical external file requirement (`test/alerts_test.json`) and Docker bind-mount behavior.
- Collapsing frontend saved state to server state too early can break current per-browser persistence before a multi-client state model is designed.
- Packaging without explicit ignore rules may include logs, bytecode, backups, audit scratch files, node_modules, or local SQLite runtime data in the final ZIP.
