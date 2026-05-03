# HUD-USPS ZIP-County Crosswalk 2025 Q4

Source:

- HUD-USPS ZIP Crosswalk API
- Endpoint: `https://www.huduser.gov/hudapi/public/usps`
- Query: `type=2`, `query=All`, `year=2025`, `quarter=4`
- Crosswalk type: `zip-county`
- Downloaded for Molecast v0.5.3 on 2026-05-03.

Files:

- `hud_usps_zip_county_2025_q4_raw.json`
  - Raw token-free HUD API response.
  - SHA-256: `6edbb396d01a5ed511b14b1bbfac4c1e5ca8834311518ce8c8fc405edfaded2f`
- `ZIP_COUNTY_2025_Q4.csv`
  - Converted CSV used by `scripts/import_location_lookup.py`.
  - Rows: 54,571
  - SHA-256: `e6d281058e333003b4fe0a0364f9f129949a94fcf53d325450467f0161b8cbcd`

The HUD API requires a token. Do not commit tokens, write tokens to files, or include tokens in logs, README files, changelogs, source code, or shell history.

Limitations:

- HUD-USPS ZIP-County rows relate ZIP Codes to counties using address ratios.
- ZIP Codes can map to multiple counties; Molecast chooses one deterministic primary county.
- Molecast ignores HUD city fields and does not store them as authoritative postal city names.
- This import enriches existing Molecast lookup rows only. It does not add HUD-only ZIPs without coordinates.
