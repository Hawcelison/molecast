# Changelog

Molecast release notes will be tracked here.

## 0.7.0 - 2026-05-04

- Added the backend active-scope alert summary foundation at `GET /api/alerts/summary?scope=active`.
- Defaulted alert summary scope to active and built active summary counts from the same active-location alert stream used by `/api/alerts/active`.
- Preserved `/api/alerts/active` behavior so alert banners remain active-location only.
- Added shared summary/counting logic for total, warning, watch, advisory, other, highest alert, scope metadata, partial status, and errors.
- Preserved NWS/test alert source identity in summary highest-alert metadata.
- Returned an intentional `501 Not Implemented` for `scope=saved` because saved-location aggregation is the next phase.
- Kept `test/alerts_test.json` clean during validation.

## 0.6.2 - 2026-05-03

- Added saved-location rename/edit polish to the existing saved-location panel.
- Added compact inline Edit controls for saved locations.
- Supported editing saved-location label and name through `PUT /api/locations/{id}`.
- Prevented blank saved-location labels in the UI.
- Refreshed the saved-location list after a successful rename.
- Updated active saved-location rename handling so `MOLECAST_CONFIG.activeLocation` and the visible active display update without recentering the map or refreshing alerts.
- Preserved inactive rename behavior without activating the row.
- Kept active Delete hidden and preserved Save to saved locations, Activate, Delete, ZIP lookup, city/address search, map-pick preview, explicit Save, and test-alert hygiene.
- Made no backend API changes in this release.

## 0.6.1 - 2026-05-03

- Added the frontend saved-location panel inside the existing active location editor.
- Loaded saved locations through `GET /api/locations` and showed active status, label/name, city/state/ZIP, and optional last-used details.
- Added `Save to saved locations` for saving the current draft through `POST /api/locations` without activating it.
- Added saved-location activation through `POST /api/locations/{id}/activate` while reusing the active Save post-update behavior for config, map recentering, active marker updates, and alert refresh.
- Added confirmed inactive saved-location deletion through `DELETE /api/locations/{id}`.
- Hid Delete for the active saved location and handled active-delete `409 Conflict` responses with friendly UI messaging.
- Preserved ZIP lookup, city/address search, map-pick preview, explicit Save behavior, radar, alert refresh, and test-alert fixture hygiene.
- Made no backend API changes in this release.

## 0.6.0 - 2026-05-03

- Added the backend/API foundation for saved locations using the existing `locations` table.
- Added `source_method`, `last_used_at`, and `county_fips` to the location model and API responses.
- Added safe schema evolution for saved-location metadata, including legacy source backfill and primary-location `last_used_at` backfill.
- Removed ZIP-code dedupe from saved-location creation so multiple saved locations can share a ZIP when labels or coordinates differ.
- Preserved `PUT /api/location/active` compatibility while updating the current primary row instead of finding rows by ZIP.
- Added `PUT /api/locations/{id}` for saved-location updates.
- Added `POST /api/locations/{id}/activate` for activating a saved location while preserving a single primary location.
- Hardened `DELETE /api/locations/{id}` so inactive saved locations can be deleted and active deletion returns `409 Conflict`.
- Updated `GET /api/locations` ordering to return the active location first, then `last_used_at` descending, then label/name.
- Kept the frontend saved-location panel out of this phase; that compact editor panel is next.

## 0.5.3 - 2026-05-03

- Added the real Census 2025 county Gazetteer reference file for county FIPS to county/state mapping.
- Added real HUD-USPS ZIP-County 2025 Q4 source data and converted the token-free HUD API response to the documented CSV import format.
- Rebuilt `backend/app/data/location_lookup.sqlite3` with HUD county/state enrichment and updated `backend/app/data/location_lookup_manifest.json`.
- Enriched 33,719 ZIP/ZCTA lookup rows with county/state/`county_fips` where available.
- Preserved curated seed city/state/county metadata for `49002` and `49005`.
- Preserved Census ZCTA latitude/longitude metadata and kept HUD city fields ignored so Molecast does not fake postal city names.
- Confirmed `10001` now resolves to NY / New York / `county_fips=36061`, and `90210` resolves to CA / Los Angeles / `county_fips=06037`.
- Kept `test/alerts_test.json` clean and confirmed the HUD token was not written to files.

## 0.5.2 - 2026-05-03

- Added explicit/offline importer support for HUD-USPS ZIP-County enrichment as a foundation for county/state metadata on ZCTA-backed lookup rows.
- Added Census county Gazetteer parser support for county FIPS to county/state mapping.
- Added deterministic multi-county ZIP ranking using `RES_RATIO`, `TOT_RATIO`, `BUS_RATIO`, `OTH_RATIO`, then `COUNTY`.
- Preserved curated seed city/state/county metadata and Census ZCTA latitude/longitude metadata during enrichment.
- Ignored HUD city fields so Molecast does not fake postal city names.
- Propagated `county_fips` through ZIP lookup schemas and routes.
- Added source instructions under `data/reference/census/` and `data/reference/hud_usps/`.
- Did not rebuild the real nationwide lookup database in this phase because HUD-USPS and Census county source files are not present yet; real HUD data import is next.

## 0.5.1 - 2026-05-03

- Imported public Census 2025 Gazetteer ZCTA data into the local ZIP lookup database.
- Added Census source data under `data/reference/census/`.
- Rebuilt `backend/app/data/location_lookup.sqlite3` from seed ZIPs plus Census ZCTA data, increasing `zip_locations` from 2 rows to 33,792 rows.
- Preserved existing `49002` and `49005` seed behavior while adding broad local/offline ZIP/ZCTA coordinate lookup for ZIP-like map centering.
- Allowed ZCTA-only lookup rows to return null city, state, and county metadata when the Census Gazetteer does not provide those fields.
- Documented ZCTA limitations: Census approximation, not USPS ZIP validation, and not every USPS ZIP has a ZCTA.
- Kept address lookup provider-based and kept `test/alerts_test.json` clean.

## 0.5.0 - 2026-05-03

- Added ZIP lookup metadata foundation for full USA ZIP support.
- Extended the local lookup schema, repository, and ZIP API response with source, version, and import metadata.
- Added CSV import support while preserving the existing JSON seed import and atomic SQLite rebuild behavior.
- Regenerated the bundled lookup database with the current small `49002` and `49005` seed rows only.
- Preserved existing `49002` and `49005` ZIP lookup behavior and the legacy `/api/location/lookup/{zip_code}` route.
- Added tests for CSV import, metadata fields, non-Michigan fixture ZIPs, unknown and invalid ZIP behavior, city search from imported data, and ZIP lookup hygiene.
- Kept address lookup provider-based; no nationwide ZIP dataset was imported in this release.

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
