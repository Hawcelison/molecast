from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Location(Base):
    """Saved weather dashboard location."""

    __tablename__ = "locations"
    __table_args__ = (
        Index(
            "ix_locations_single_primary",
            "is_primary",
            unique=True,
            sqlite_where=text("is_primary = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(80), nullable=False)
    county_fips: Mapped[str | None] = mapped_column(String(10), nullable=True)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    timezone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    default_zoom: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    nws_office: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nws_grid_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nws_grid_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forecast_zone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    county_zone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fire_weather_zone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    nws_points_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_method: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        default="legacy",
        server_default=text("'legacy'"),
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
