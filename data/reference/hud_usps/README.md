# HUD-USPS ZIP Crosswalk Reference Data

Molecast v0.5.2 supports offline enrichment from the HUD-USPS ZIP-County crosswalk.

Expected source file convention:

- `data/reference/hud_usps/<year>_<quarter>/ZIP_COUNTY_<year>_<quarter>.csv`
- Example: `data/reference/hud_usps/2025_Q4/ZIP_COUNTY_2025_Q4.csv`
- Source page: `https://www.huduser.gov/portal/datasets/usps_crosswalk.html`

The importer reads the CSV directly:

```bash
PYTHONPATH=backend .venv/bin/python scripts/import_location_lookup.py \
  --input backend/app/data/zip_codes.json \
  --source-name molecast-seed-zip-codes-json \
  --source-version phase-1-seed \
  --zcta-input data/reference/census/2025_Gaz_zcta_national.zip \
  --zcta-source-year 2025 \
  --zcta-source-version 2025_Gaz_zcta_national \
  --zcta-dataset-version 2025_Gazetteer_ZCTA \
  --hud-zip-county-input data/reference/hud_usps/2025_Q4/ZIP_COUNTY_2025_Q4.csv \
  --hud-source-year 2025 \
  --hud-source-quarter Q4 \
  --hud-source-version HUD_USPS_2025_Q4 \
  --hud-dataset-version HUD_USPS_ZIP_COUNTY_2025_Q4 \
  --county-reference-input data/reference/census/2025_Gaz_counties_national.zip \
  --sentinel-zip 49002 \
  --sentinel-zip 49005 \
  --sentinel-zip 10001 \
  --sentinel-zip 90210
```

Limitations:

- HUD-USPS ZIP-County rows relate ZIP Codes to counties using address ratios.
- ZIP Codes can map to multiple counties; Molecast chooses one deterministic primary county.
- Molecast ignores HUD `USPS_ZIP_PREF_CITY` and does not store HUD city names.
- This data enriches existing lookup rows only. It does not add HUD-only ZIPs without coordinates.
- Import is explicit and offline. The app never downloads or imports this data on startup.
