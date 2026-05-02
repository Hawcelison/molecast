# Changelog

Molecast release notes will be tracked here.

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
