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
