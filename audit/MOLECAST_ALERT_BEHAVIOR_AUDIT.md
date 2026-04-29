# Molecast Alert Behavior Audit

Date: 2026-04-29
Scope: runtime alert behavior now that the modular alerts pipeline is active.
Constraint: audit only; no implementation changes made.

## Summary

Molecast mostly has the right backend shape for a unified alert stream: real NWS alerts and local test alerts both enter `parse_nws_alerts()`, both pass through normalization, location matching, timestamp filtering, scoring, and presentation, and the merged list is sorted before being returned.

The main gap is the public alert DTO. The modular normalizer computes catalog-driven `priority`, `color_hex`, `icon`, and `sound_profile`, but the API schema does not expose `color_hex`, `icon`, `sound_profile`, or catalog `priority` as top-level frontend fields. `color_hex`, `icon`, and `priority` are copied into `raw_properties`; `sound_profile` is not preserved in the returned DTO. Because of that, the dashboard still relies on frontend fallback maps for color, icon, high-priority classification, and audio profile selection.

Runtime validation on the running Docker app passed for endpoint availability, but the current runtime stream had zero active alerts, so populated alert rendering could not be observed live without changing the test alert file.

## Pass/Fail Checklist

| Area | Status | Evidence |
| --- | --- | --- |
| Docker container is up | PASS | `docker compose -f docker/docker-compose.yml ps` showed `molecast` Up, port `5000:5000`. |
| `/health` returns 200 | PASS | `curl http://localhost:5000/health` returned `200`. |
| `/api/alerts/active` returns 200 | PASS | `curl http://localhost:5000/api/alerts/active` returned `200`. |
| `/test-alerts` page loads | PASS | `curl http://localhost:5000/test-alerts` returned `200`. |
| Test alert status endpoint loads | PASS | `/api/test-alerts/status` returned `200`; reported `test_total=15`, `test_enabled=0`, `test_active=0`, `nws_active=0`. |
| NWS alerts fetched | PASS | `NwsAlertProvider.fetch_active_alerts()` fetches point alerts, then county/forecast/fire zone alerts from `/points` metadata. See `backend/app/services/alert_service.py:35-58`, `82-103`, `122-149`. |
| Test alerts loaded from external file | PASS | `TestAlertLoader.load_enabled_alert_features()` resolves and reads the configured file, filters enabled entries, and converts them into NWS-like GeoJSON features. See `backend/app/alerts/test_alert_loader.py:16-77`, `79-91`, `103-151`. |
| NWS and test alerts share normalization path | PASS | `_load_active_alerts()` calls `parse_nws_alerts(..., source="test")` and `parse_nws_alerts(..., source="nws")`; `parse_nws_alerts()` calls `normalize_nws_feature_collection()`. See `backend/app/services/alert_service.py:274-292`, `295-409`. |
| Both streams share matching/scoring/filtering | PASS | `parse_nws_alerts()` applies location matching, timestamp validation, expired/future filtering, scoring, schema validation, and sorting regardless of `source`. See `backend/app/services/alert_service.py:310-409`. |
| Merge happens before final sort | PASS | `sort_alerts_by_priority([*live_alerts, *test_alerts])` is applied after the merge. See `backend/app/services/alert_service.py:292`. |
| Cross-stream dedupe happens after merge | FAIL | NWS point/zone payloads are deduped before normalization inside `NwsAlertProvider`; there is no dedupe after merging NWS and test alerts. See `backend/app/services/alert_service.py:58`, `134-149`, `292`. |
| Test alerts bypass priority/color/icon logic | PASS backend, PARTIAL API | Test alerts enter the normalizer and get catalog `priority`, `color_hex`, `icon`, and `sound_profile`; however the API drops most of these as top-level fields. See `backend/app/alerts/normalize.py:120-124`, `backend/app/schemas/alert.py:13-48`. |
| DTO includes required identity/text/timing/match fields | PASS | `WeatherAlert` includes `id`, `source`, `event`, `headline`, `description`, `areaDesc`, `severity`, `urgency`, `certainty`, `effective`, `expires`, `raw_properties`, `match`, and priority ranks. See `backend/app/schemas/alert.py:13-31`. |
| DTO includes color/icon/sound fields | FAIL | `AlertPresentation` does not define `color`, `color_hex`, `icon`, `priority`, or `sound_profile`. See `backend/app/schemas/alert.py:13-48`. |
| Frontend renders test and NWS banners through same path | PASS | `MolecastAlertBanners.render()` filters, sorts, renders, expands new alerts, triggers audio, and evaluates flashing without source-specific branching. See `backend/app/static/js/modules/alert-banners.js:373-424`. |
| Test audio special case is intentional | PASS | Test sources are blocked from audio unless `testAudioEnabled` is true. This is an allowed difference. See `backend/app/static/js/modules/alert-audio.js:82-100`. |
| Other `source === "test"` behavior in dashboard | PASS | No dashboard rendering/color/icon/flash special-case was found for `source === "test"` beyond the test-audio gate. |
| Browser console checklist | NOT RUN | No browser automation or manual console session was available in this audit. JS syntax checks passed for `app.js`, `alert-banners.js`, `alert-audio.js`, and `alert-icons.js`. |

## Findings

### 1. API DTO drops backend catalog fields needed by the frontend

Severity: High

The normalizer computes:

- `priority`
- `color_hex`
- `icon`
- `sound_profile`

See `backend/app/alerts/normalize.py:120-124`.

But `WeatherAlert` and `AlertPresentation` do not expose `color_hex`, `icon`, `priority`, or `sound_profile` as top-level fields. See `backend/app/schemas/alert.py:13-48`.

`_weather_alert_data()` copies `color_hex`, `icon`, and `priority` into `raw_properties`, but not `sound_profile`, then validates into `WeatherAlert`, whose schema discards any undeclared top-level fields. See `backend/app/services/alert_service.py:412-446`.

Impact:

- Frontend banner/card color falls back to `nws-colors.js`.
- Frontend icons fall back to `alert-icons.js` event maps.
- Audio ignores backend `sound_profile` because it is not present in the API alert object.
- Test alerts still follow the same backend normalization path, but the frontend cannot fully consume the normalized backend DTO.

### 2. No dedupe after merging NWS and test streams

Severity: Medium

NWS point/zone feeds are deduped inside `NwsAlertProvider._dedupe_features()`, before the NWS stream is parsed. See `backend/app/services/alert_service.py:58`, `134-149`.

After NWS and test alerts are parsed, `_load_active_alerts()` concatenates and sorts the two lists but does not dedupe across sources. See `backend/app/services/alert_service.py:274-292`.

Impact:

- If a local test alert intentionally or accidentally mirrors a live NWS alert ID/event/timing, both will display.
- This may be acceptable for test visibility, but it does not satisfy the requested "deduping and sorting happen after merge" requirement.

### 3. Frontend high-priority and flashing policy still duplicates backend catalog intent

Severity: Medium

`alert-banners.js` carries its own `HIGH_PRIORITY_EVENTS` list and severity/urgency rules for assertive/live behavior. See `backend/app/static/js/modules/alert-banners.js:3-12`, `157-169`, `435-452`.

The backend hazard catalog already contains related policy fields such as `priority`, `default_sound`, `flash`, and `aria_live` in `backend/app/alerts/data/nws_hazards.json`.

Impact:

- Backend and frontend can diverge as the catalog grows.
- Test and NWS alerts still share the same browser path, but the browser is not fully driven by backend-normalized DTO policy.

### 4. Frontend color/icon/audio fallback maps remain active

Severity: Medium

Color fallback:

- `nws-colors.js` has event and severity color maps. See `backend/app/static/js/nws-colors.js:4-42`.
- `app.js` and `alert-banners.js` prefer top-level `alert.color_hex`, then call `getAlertColor()`. See `backend/app/static/js/app.js:19-27`, `backend/app/static/js/modules/alert-banners.js:73-81`.

Icon fallback:

- `alert-icons.js` has event and named-icon maps. See `backend/app/static/js/modules/alert-icons.js:2-55`.

Audio fallback:

- `alert-audio.js` has profile maps and event-based routing. See `backend/app/static/js/modules/alert-audio.js:4-80`.

Impact:

- These fallbacks are useful while the DTO is incomplete.
- They should not remain the primary source of truth once backend DTO fields are exposed.

### 5. Runtime stream currently has no active alerts

Severity: Low

Live `/api/alerts/active` returned:

- `location_label`: `Portage, MI 49002`
- `refresh_interval_seconds`: `60`
- `alert_count`: `0`

`/api/test-alerts/status` returned:

- `test_total`: `15`
- `test_enabled`: `0`
- `test_active`: `0`
- `nws_active`: `0`

Impact:

- Endpoint availability is verified.
- Populated banner/card/audio/flash behavior was audited from code, not observed live.

## API Output Assessment

Required frontend fields:

| Field | Status | Notes |
| --- | --- | --- |
| `id` | Present | `WeatherAlert.id`. |
| `source` | Present | `WeatherAlert.source`; test alerts are marked `test`. |
| `event` | Present | `WeatherAlert.event`. |
| `headline` | Present | `WeatherAlert.headline`. |
| `description` | Present | `WeatherAlert.description`. |
| `areaDesc` | Present | `WeatherAlert.areaDesc`. |
| `severity` | Present | `WeatherAlert.severity`. |
| `urgency` | Present | `WeatherAlert.urgency`. |
| `certainty` | Present | `WeatherAlert.certainty`. |
| `effective` | Present | UTC datetime validation exists. |
| `expires` | Present | UTC datetime validation exists. |
| `color` / `color_hex` | Missing top-level | `raw_properties.color_hex` exists when normalized; not top-level. |
| `icon` | Missing top-level | `raw_properties.icon` exists when normalized; not top-level. |
| `priority` / `priority_score` | Partial | `priority_score` top-level exists; catalog `priority` only in `raw_properties.priority`. |
| `sound_profile` | Missing | Computed by normalizer but not preserved in API DTO. |
| match info | Present | `match.match_type`, `matched_value`, `confidence`. |
| test label/source marker | Partial | `source="test"` present; no top-level `is_test` or display label beyond Source detail. |

## Frontend Behavior Assessment

Banner rendering:

- Uses one unified `MolecastAlertBanners.render()` path for every alert object.
- Sorts by `priority` or `priority_score`.
- Expands new alerts automatically by adding all new IDs to `expandedAlertIds`.
- Scrolls to the banner container when new alerts arrive unless reduced motion is preferred.

Alert card rendering:

- `app.js` renders all alerts through one path if `#alerts-list` exists.
- Current dashboard template no longer includes `#alerts-list`; the primary dashboard surface is the top banner container.

Color handling:

- Prefers `alert.color_hex`.
- Falls back to `nws-colors.js`.
- Because the API does not expose top-level `color_hex`, fallback is currently the effective runtime path.

Icon handling:

- Prefers `alert.icon`.
- Falls back to event maps.
- Because the API does not expose top-level `icon`, fallback is currently the effective runtime path.

Sound handling:

- Uses one `playForAlert()` path.
- Requires alert audio enabled, session unlock, not silenced, and not acknowledged.
- Test alerts additionally require `testAudioEnabled`, which is allowed.
- Because the API does not expose `sound_profile`, event fallback is currently the effective runtime path.

Flashing:

- Applies to severe/extreme alerts unless acknowledged, disabled, or reduced motion is preferred.
- No test-source-specific bypass was found.

Minimized/expanded behavior:

- Alerts are compact by default unless their ID is in `expandedAlertIds`.
- New alerts auto-expand.
- Existing expanded IDs are preserved across refresh if still present.

## Allowed Test Differences

Observed allowed differences:

- Test alerts are marked with `source="test"`.
- The UI displays `Source: test` in banner/card details.
- Test audio requires the explicit `Test audio` setting in addition to the main `Alert audio` setting.

No other dashboard behavior was found that treats `source="test"` differently for rendering, sorting, color, icon, flashing, expansion, or matching.

## Duplicate/Fallback Logic Classification

| Logic | Location | Classification | Notes |
| --- | --- | --- | --- |
| Event/severity color map | `backend/app/static/js/nws-colors.js` | Safe fallback for now; should migrate to backend DTO | Keep until `color_hex` is top-level and trusted. |
| Card/banner color fallback | `backend/app/static/js/app.js`, `backend/app/static/js/modules/alert-banners.js` | Safe fallback for now | Should become a defensive fallback only after DTO migration. |
| Icon event map | `backend/app/static/js/modules/alert-icons.js` | Safe fallback for now; should migrate to backend DTO | Keep named-icon rendering, but event-to-icon policy should come from backend catalog. |
| Audio event/profile map | `backend/app/static/js/modules/alert-audio.js` | Should migrate to backend DTO | Browser can still map profile names to sound file URLs, but event-to-profile policy should come from `sound_profile`. |
| High-priority event list | `backend/app/static/js/modules/alert-banners.js` | Should migrate to backend DTO | Backend catalog priority/aria/flash policy should drive this. |
| Flash severe/extreme heuristic | `backend/app/static/js/modules/alert-banners.js` | Should migrate to backend DTO | Catalog has `flash`; expose it to avoid duplicated policy. |
| Backend hazard catalog | `backend/app/alerts/data/nws_hazards.json` | Source of truth | This should become the primary source for color/icon/priority/sound/flash/aria fields. |
| Backend severity fallback ranks | `backend/app/alerts/scoring.py`, `backend/app/alerts/catalog.py` | Safe fallback for now | Useful for unknown events and malformed/partial alerts. |

## Risks

- Frontend behavior can diverge from backend catalog behavior because key DTO fields are not exposed.
- Test alerts and NWS alerts share the backend path, but cross-source dedupe is absent after merge.
- `sound_profile` is currently a dead backend-normalized field for the API consumer.
- Runtime validation did not include active alert rendering because no alerts were active and test alerts were disabled.
- The working tree already had `test/alerts_test.json` modified before this report was written; this audit did not change it.
- Focused pytest checks could not be run on host or in container because `pytest` is not installed in either environment.

## Recommended Next Steps

1. Extend `WeatherAlert` / `AlertPresentation` to expose top-level `color_hex`, `icon`, `priority`, `sound_profile`, and optionally `flash` / `aria_live`.
2. Update `_weather_alert_data()` to carry those normalized fields into the DTO, not only `raw_properties`.
3. Add a post-merge dedupe step after `[*live_alerts, *test_alerts]`, with an explicit policy for whether `source="test"` may intentionally coexist with a matching NWS alert.
4. Update frontend modules to prefer backend DTO fields and demote event maps to defensive fallback only.
5. Add focused tests proving a test alert and an NWS alert flow through the same DTO shape, including color/icon/sound/priority fields.
6. Run a live browser smoke test with one enabled active test alert: verify banner color, icon, auto-expand, flash, source marker, and audio gating.

## Files to Inspect or Change in the Next Implementation Phase

- `backend/app/schemas/alert.py`
- `backend/app/services/alert_service.py`
- `backend/app/alerts/normalize.py`
- `backend/app/alerts/presentation.py`
- `backend/app/alerts/data/nws_hazards.json`
- `backend/app/static/js/modules/alert-banners.js`
- `backend/app/static/js/modules/alert-audio.js`
- `backend/app/static/js/modules/alert-icons.js`
- `backend/app/static/js/nws-colors.js`
- `backend/app/static/js/app.js`
- `tests/unit/test_active_alerts_route.py`
- `tests/unit/test_alert_normalize.py`
- `tests/unit/test_alert_service_nws_zones.py`

## Validation Commands Run

```text
docker compose -f docker/docker-compose.yml ps
curl -sS -o /tmp/molecast-health.out -w "%{http_code}\n" http://localhost:5000/health
curl -sS -o /tmp/molecast-alerts-active.json -w "%{http_code}\n" http://localhost:5000/api/alerts/active
curl -sS -o /tmp/molecast-test-alerts.html -w "%{http_code}\n" http://localhost:5000/test-alerts
curl -sS -o /tmp/molecast-test-alerts-status.json -w "%{http_code}\n" http://localhost:5000/api/test-alerts/status
jq '{location_id, location_label, refreshed_at, refresh_interval_seconds, alert_count:(.alerts|length)}' /tmp/molecast-alerts-active.json
jq '{test_file,test_total,test_enabled,test_active,nws_active,total_active,sources,active_refreshed_at}' /tmp/molecast-test-alerts-status.json
node --check backend/app/static/js/app.js
node --check backend/app/static/js/modules/alert-banners.js
node --check backend/app/static/js/modules/alert-audio.js
node --check backend/app/static/js/modules/alert-icons.js
python3 -m pytest tests/unit/test_alert_normalize.py tests/unit/test_active_alerts_route.py tests/unit/test_alert_service_nws_zones.py
docker compose -f docker/docker-compose.yml exec -T molecast python -m pytest tests/unit/test_alert_normalize.py tests/unit/test_active_alerts_route.py tests/unit/test_alert_service_nws_zones.py
```

Pytest result:

- Host: failed before tests, `/usr/bin/python3: No module named pytest`.
- Container: failed before tests, `/usr/local/bin/python: No module named pytest`.
