from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ZipLocationRecord:
    zip_code: str
    primary_city: str
    state: str
    county: str | None
    county_fips: str | None
    latitude: float
    longitude: float
    timezone: str | None
    default_zoom: int
    source: str | None
    source_year: str | None
    location_type: str | None
    is_zcta: bool
    confidence: str | None


class LocationLookupRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def lookup_zip(self, zip_code: str) -> ZipLocationRecord | None:
        if not self.db_path.exists():
            return None

        try:
            with self._connect() as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(
                    """
                    SELECT
                        zip_code,
                        primary_city,
                        state,
                        county,
                        county_fips,
                        latitude,
                        longitude,
                        timezone,
                        default_zoom,
                        source,
                        source_year,
                        location_type,
                        is_zcta,
                        confidence
                    FROM zip_locations
                    WHERE zip_code = ?
                    """,
                    (zip_code,),
                ).fetchone()
        except sqlite3.Error:
            return None

        if row is None:
            return None

        return ZipLocationRecord(
            zip_code=row["zip_code"],
            primary_city=row["primary_city"],
            state=row["state"],
            county=row["county"],
            county_fips=row["county_fips"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            timezone=row["timezone"],
            default_zoom=row["default_zoom"] or 9,
            source=row["source"],
            source_year=row["source_year"],
            location_type=row["location_type"],
            is_zcta=bool(row["is_zcta"]),
            confidence=row["confidence"],
        )

    def _connect(self) -> sqlite3.Connection:
        db_uri = f"file:{self.db_path.resolve().as_posix()}?mode=ro"
        return sqlite3.connect(db_uri, uri=True)
