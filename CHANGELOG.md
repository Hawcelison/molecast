# Changelog

Molecast release notes will be tracked here.

## 0.4.1 - 2026-05-03

- Improved map-pick preview responsiveness by aborting stale in-flight preview requests when a new preview selection starts.
- Suppressed duplicate in-flight preview requests for the same rounded coordinate.
- Stopped map-pick mode before dispatching preview work for a selected point.
- Preserved explicit Save behavior and kept preview actions from mutating the active location.

## 0.4.0 - 2026-05-03

- Added map-click location preview from the active location editor.
- Added `Pick from map` / `Cancel pick` behavior for temporary map-pick mode.
- Reused `POST /api/location/points/preview` for clicked-coordinate previews.
- Populated preview fields with coordinates, local ZIP/city metadata when available, and NWS office/grid/zone metadata.
- Preserved explicit Save behavior through `PUT /api/location/active`, including map recentering and alert refresh after Save.
- Kept normal alert banner click/focus behavior when map-pick mode is inactive.
- Kept `test/alerts_test.json` clean during validation.

## 0.3.2 - 2026-05-03

- Improved `/health` readiness behavior to include database readiness.
- Stabilized active location editor preview behavior.
- Prevented intentional preview cancellation from surfacing as failed or user-facing errors.
- Improved test alert editor hygiene so opening and validation flows do not dirty `test/alerts_test.json`.
- Added and updated tests for health readiness and test alert loader hygiene.

## 0.3.1 - 2026-05-02

- Improved active location autocomplete status feedback while searches are running.
- Added address-provider searching and longer-than-usual status messages for slower address lookups.
- Added compact ZIP, City, and Address type labels to autocomplete suggestions.
- Added clearer no-results and non-blocking address-provider unavailable states.
- Preserved explicit Save behavior and existing ZIP lookup, city search, and address search flows.

## 0.3.0 - 2026-05-02

- Added ZIP, city, and address autocomplete to the active location editor.
- Reused `/api/location/search` and `/api/location/points/preview` for suggestion and preview behavior.
- Added address suggestions through the Census geocoder provider while keeping local ZIP/city search first.
- Limited address provider calls to address-like input and degraded gracefully on provider validation or availability errors.
- Kept suggestion selection as field population only; explicit Save is still required.

## 0.2.0 - 2026-05-02

- Added ZIP lookup for the active location editor through `GET /api/location/zip/{zip_code}`.
- Kept `/api/location/lookup/{zip_code}` as a hidden legacy alias.
- Returned both `zip` and `zip_code` in ZIP lookup responses.
- Populated active location editor fields from ZIP lookup while keeping Save as an explicit user action.
- Added focused unit coverage for ZIP lookup behavior.

Future release automation should update `APP_VERSION` and append release notes in the same change.
