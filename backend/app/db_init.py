from sqlalchemy import inspect, text

from app.config import Settings, settings
from app.database import Base, SessionLocal, engine
from app.models import Location
from app.services.location_service import ensure_active_location


def init_database(app_settings: Settings = settings) -> None:
    app_settings.data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_location_schema(bind=engine)

    with SessionLocal() as db:
        ensure_active_location(db, app_settings)

    create_location_indexes()


def create_location_indexes() -> None:
    for index in Location.__table__.indexes:
        if index.name == "ix_locations_single_primary":
            index.create(bind=engine, checkfirst=True)


LOCATION_SCHEMA_COLUMNS = {
    "name": "VARCHAR(120)",
    "county_fips": "VARCHAR(10)",
    "timezone": "VARCHAR(80)",
    "default_zoom": "INTEGER NOT NULL DEFAULT 9",
    "nws_office": "VARCHAR(20)",
    "nws_grid_x": "INTEGER",
    "nws_grid_y": "INTEGER",
    "forecast_zone": "VARCHAR(80)",
    "county_zone": "VARCHAR(80)",
    "fire_weather_zone": "VARCHAR(80)",
    "nws_points_updated_at": "DATETIME",
    "source_method": "VARCHAR(30) DEFAULT 'legacy'",
    "last_used_at": "DATETIME",
}


def ensure_location_schema(bind=engine) -> None:
    inspector = inspect(bind)
    if "locations" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("locations")}
    missing_columns = [
        (column_name, column_sql)
        for column_name, column_sql in LOCATION_SCHEMA_COLUMNS.items()
        if column_name not in existing_columns
    ]
    with bind.begin() as connection:
        for column_name, column_sql in missing_columns:
            connection.execute(text(f"ALTER TABLE locations ADD COLUMN {column_name} {column_sql}"))
        available_columns = existing_columns | {column_name for column_name, _column_sql in missing_columns}
        if "source_method" in available_columns:
            connection.execute(
                text("UPDATE locations SET source_method = 'legacy' WHERE source_method IS NULL")
            )
        if "last_used_at" in available_columns:
            connection.execute(
                text(
                    """
                    UPDATE locations
                    SET last_used_at = updated_at
                    WHERE is_primary = 1 AND last_used_at IS NULL
                    """
                )
            )
