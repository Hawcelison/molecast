# Census ZCTA Gazetteer Reference Data

Source file:

- `2025_Gaz_zcta_national.zip`
- Census download URL: `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_zcta_national.zip`
- Downloaded for Molecast v0.5.1 on 2026-05-03.
- SHA-256: `51516a4283bab5cd2376eec75609ddc4b363a18297e8adeeaac7b03cf7c84dbe`

The importer reads the ZIP directly:

```bash
PYTHONPATH=backend .venv/bin/python scripts/import_location_lookup.py \
  --input backend/app/data/zip_codes.json \
  --source-name molecast-seed-zip-codes-json \
  --source-version phase-1-seed \
  --zcta-input data/reference/census/2025_Gaz_zcta_national.zip \
  --zcta-source-year 2025 \
  --zcta-source-version 2025_Gaz_zcta_national \
  --zcta-dataset-version 2025_Gazetteer_ZCTA \
  --sentinel-zip 10001 \
  --sentinel-zip 90210
```

Limitations:

- ZCTA is not the same as USPS ZIP Code.
- ZCTA is an approximate Census geography.
- Not every valid USPS ZIP Code is represented by a ZCTA.
- This data improves broad ZIP-style map centering, but it is not final USPS ZIP validation.

## County Reference Data

Molecast v0.5.2 HUD-USPS ZIP-County enrichment expects a Census county Gazetteer reference file when enriching county names and state abbreviations:

- `2025_Gaz_counties_national.zip`
- Census download URL: `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_counties_national.zip`
- Expected local path: `data/reference/census/2025_Gaz_counties_national.zip`
- Downloaded for Molecast v0.5.3 on 2026-05-03.
- SHA-256: `4c90d0f805779923b5958ab13d0c1e9b99fe4932b786bfcf75dd739bb2dcb4ea`

The importer uses county `GEOID` to map HUD `COUNTY` values to county names and `USPS` state abbreviations. If the HUD county FIPS is not present in this reference, Molecast may still preserve `county_fips` and derivable state data, but it will not fake a county name.
