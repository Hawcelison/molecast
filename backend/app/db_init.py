from app.config import Settings, settings
from app.database import Base, SessionLocal, engine
from app.models import Location
from app.services.location_service import ensure_active_location


def init_database(app_settings: Settings = settings) -> None:
    app_settings.data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        ensure_active_location(db, app_settings)

    create_location_indexes()


def create_location_indexes() -> None:
    for index in Location.__table__.indexes:
        if index.name == "ix_locations_single_primary":
            index.create(bind=engine, checkfirst=True)
