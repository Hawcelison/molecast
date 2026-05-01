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


@dataclass(frozen=True)
class CityLocationRecord:
    primary_city: str
    state: str
    county: str | None
    latitude: float
    longitude: float
    default_zoom: int
    source: str | None
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

    def search_zip_prefix(self, query: str, limit: int) -> list[ZipLocationRecord]:
        if not self.db_path.exists():
            return []

        try:
            with self._connect() as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
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
                    WHERE zip_code LIKE ?
                    ORDER BY
                        CASE WHEN zip_code = ? THEN 0 ELSE 1 END,
                        zip_code ASC,
                        primary_city ASC,
                        state ASC
                    LIMIT ?
                    """,
                    (f"{query}%", query, limit),
                ).fetchall()
        except sqlite3.Error:
            return []

        return [self._zip_record_from_row(row) for row in rows]

    def search_city_prefix(
        self,
        query: str,
        limit: int,
        state: str | None = None,
    ) -> list[CityLocationRecord]:
        if not self.db_path.exists():
            return []

        where_clause = "LOWER(primary_city) LIKE LOWER(?)"
        parameters: list[str | int] = [f"{query}%"]
        if state:
            where_clause += " AND state = ?"
            parameters.append(state)
        parameters.extend([query, limit])

        try:
            with self._connect() as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    f"""
                    SELECT
                        primary_city,
                        state,
                        county,
                        latitude,
                        longitude,
                        default_zoom,
                        source,
                        confidence
                    FROM city_locations
                    WHERE {where_clause}
                    ORDER BY
                        CASE WHEN LOWER(primary_city) = LOWER(?) THEN 0 ELSE 1 END,
                        primary_city ASC,
                        state ASC,
                        county ASC
                    LIMIT ?
                    """,
                    tuple(parameters),
                ).fetchall()
        except sqlite3.Error:
            return []

        return [self._city_record_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        db_uri = f"file:{self.db_path.resolve().as_posix()}?mode=ro"
        return sqlite3.connect(db_uri, uri=True)

    def _zip_record_from_row(self, row: sqlite3.Row) -> ZipLocationRecord:
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

    def _city_record_from_row(self, row: sqlite3.Row) -> CityLocationRecord:
        return CityLocationRecord(
            primary_city=row["primary_city"],
            state=row["state"],
            county=row["county"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            default_zoom=row["default_zoom"] or 9,
            source=row["source"],
            confidence=row["confidence"],
        )
