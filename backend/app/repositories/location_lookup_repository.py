from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path


EARTH_RADIUS_MILES = 3958.7613


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

    def find_nearest_zip(
        self,
        latitude: float,
        longitude: float,
        max_distance_miles: float = 35.0,
    ) -> ZipLocationRecord | None:
        if not self.db_path.exists():
            return None

        latitude = float(latitude)
        longitude = float(longitude)
        max_distance_miles = float(max_distance_miles)
        if not (
            math.isfinite(latitude)
            and -90 <= latitude <= 90
            and math.isfinite(longitude)
            and -180 <= longitude <= 180
            and math.isfinite(max_distance_miles)
            and max_distance_miles > 0
        ):
            return None

        latitude_delta = max_distance_miles / 69.0
        longitude_delta = max_distance_miles / max(69.0 * math.cos(math.radians(latitude)), 1.0)

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
                    WHERE latitude BETWEEN ? AND ?
                      AND longitude BETWEEN ? AND ?
                    """,
                    (
                        latitude - latitude_delta,
                        latitude + latitude_delta,
                        longitude - longitude_delta,
                        longitude + longitude_delta,
                    ),
                ).fetchall()
        except sqlite3.Error:
            return None

        nearest_row: sqlite3.Row | None = None
        nearest_distance = max_distance_miles
        for row in rows:
            distance = haversine_miles(latitude, longitude, row["latitude"], row["longitude"])
            if distance <= nearest_distance:
                nearest_row = row
                nearest_distance = distance

        return self._zip_record_from_row(nearest_row) if nearest_row is not None else None

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


def haversine_miles(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    delta_latitude = math.radians(latitude_b - latitude_a)
    delta_longitude = math.radians(longitude_b - longitude_a)
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)

    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_longitude / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(value))
