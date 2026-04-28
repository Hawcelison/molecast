import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import SessionLocal
from app.db_init import init_database
from app.services.location_service import ensure_default_location


def main() -> None:
    init_database(settings)
    with SessionLocal() as db:
        ensure_default_location(db, settings)


if __name__ == "__main__":
    main()
