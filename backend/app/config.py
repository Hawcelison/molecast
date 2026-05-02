from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import constants


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(
        default=constants.APP_NAME,
        validation_alias="APP_NAME",
    )
    app_version: str = Field(
        default=constants.APP_VERSION,
        validation_alias="APP_VERSION",
    )
    app_env: str = Field(
        default=constants.APP_ENV,
        validation_alias="APP_ENV",
    )
    debug: bool = Field(default=False, validation_alias="DEBUG")
    database_url: str = Field(
        default=constants.DATABASE_URL,
        validation_alias="DATABASE_URL",
    )
    data_dir: Path = Field(
        default=Path(constants.DATA_DIR),
        validation_alias="DATA_DIR",
    )
    default_location_city: str = Field(
        default=constants.DEFAULT_LOCATION_CITY,
        validation_alias="DEFAULT_LOCATION_CITY",
    )
    default_location_state: str = Field(
        default=constants.DEFAULT_LOCATION_STATE,
        validation_alias="DEFAULT_LOCATION_STATE",
    )
    default_location_county: str = Field(
        default=constants.DEFAULT_LOCATION_COUNTY,
        validation_alias="DEFAULT_LOCATION_COUNTY",
    )
    default_location_postal_code: str = Field(
        default=constants.DEFAULT_LOCATION_POSTAL_CODE,
        validation_alias="DEFAULT_LOCATION_POSTAL_CODE",
    )
    default_location_display_name: str = Field(
        default=constants.DEFAULT_LOCATION_DISPLAY_NAME,
        validation_alias="DEFAULT_LOCATION_DISPLAY_NAME",
    )
    default_location_latitude: float = Field(
        default=constants.DEFAULT_LOCATION_LATITUDE,
        validation_alias="DEFAULT_LOCATION_LATITUDE",
    )
    default_location_longitude: float = Field(
        default=constants.DEFAULT_LOCATION_LONGITUDE,
        validation_alias="DEFAULT_LOCATION_LONGITUDE",
    )
    default_location_zoom: int = Field(
        default=constants.DEFAULT_LOCATION_ZOOM,
        validation_alias="DEFAULT_LOCATION_ZOOM",
    )
    weather_refresh_seconds: int = Field(
        default=constants.WEATHER_REFRESH_SECONDS,
        validation_alias="WEATHER_REFRESH_SECONDS",
    )
    alert_refresh_seconds: int = Field(
        default=constants.ALERT_REFRESH_SECONDS,
        validation_alias="ALERT_REFRESH_SECONDS",
    )
    nws_active_alerts_url: str = Field(
        default=constants.NWS_ACTIVE_ALERTS_URL,
        validation_alias="NWS_ACTIVE_ALERTS_URL",
    )
    nws_user_agent: str = Field(
        default=constants.NWS_USER_AGENT,
        validation_alias="NWS_USER_AGENT",
    )
    geocoder_provider: str = Field(
        default=constants.GEOCODER_PROVIDER,
        validation_alias="GEOCODER_PROVIDER",
    )
    census_geocoder_base_url: str = Field(
        default=constants.CENSUS_GEOCODER_BASE_URL,
        validation_alias="CENSUS_GEOCODER_BASE_URL",
    )
    census_geocoder_benchmark: str = Field(
        default=constants.CENSUS_GEOCODER_BENCHMARK,
        validation_alias="CENSUS_GEOCODER_BENCHMARK",
    )
    geocoder_timeout_seconds: int = Field(
        default=constants.GEOCODER_TIMEOUT_SECONDS,
        validation_alias="GEOCODER_TIMEOUT_SECONDS",
        gt=0,
    )
    geocoder_user_agent: str = Field(
        default=constants.GEOCODER_USER_AGENT,
        validation_alias="GEOCODER_USER_AGENT",
    )
    test_alerts_file: Path = Field(
        default=Path(constants.TEST_ALERTS_FILE),
        validation_alias="TEST_ALERTS_FILE",
    )
    log_retention_days: int = Field(
        default=constants.LOG_RETENTION_DAYS,
        validation_alias="LOG_RETENTION_DAYS",
    )
    log_level: str = Field(
        default=constants.LOG_LEVEL,
        validation_alias="LOG_LEVEL",
    )
    log_file_name: str = Field(
        default=constants.LOG_FILE_NAME,
        validation_alias="LOG_FILE_NAME",
    )
    mapbox_token: str = Field(
        default=constants.MAPBOX_TOKEN,
        validation_alias="MAPBOX_TOKEN",
    )
    rainviewer_api_url: str = Field(
        default=constants.RAINVIEWER_API_URL,
        validation_alias="RAINVIEWER_API_URL",
    )
    radar_frame_interval_ms: int = Field(
        default=constants.RADAR_FRAME_INTERVAL_MS,
        validation_alias="RADAR_FRAME_INTERVAL_MS",
    )
    radar_opacity: float = Field(
        default=constants.RADAR_OPACITY,
        validation_alias="RADAR_OPACITY",
    )
    county_boundaries_geojson_url: str = Field(
        default=constants.COUNTY_BOUNDARIES_GEOJSON_URL,
        validation_alias="COUNTY_BOUNDARIES_GEOJSON_URL",
    )
    county_boundaries_line_color: str = Field(
        default=constants.COUNTY_BOUNDARIES_LINE_COLOR,
        validation_alias="COUNTY_BOUNDARIES_LINE_COLOR",
    )
    county_boundaries_line_opacity: float = Field(
        default=constants.COUNTY_BOUNDARIES_LINE_OPACITY,
        validation_alias="COUNTY_BOUNDARIES_LINE_OPACITY",
    )
    county_boundaries_line_width: int = Field(
        default=constants.COUNTY_BOUNDARIES_LINE_WIDTH,
        validation_alias="COUNTY_BOUNDARIES_LINE_WIDTH",
    )

    @property
    def app_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def templates_dir(self) -> Path:
        return self.app_dir / "templates"

    @property
    def static_dir(self) -> Path:
        return self.app_dir / "static"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def log_file_path(self) -> Path:
        return self.log_dir / self.log_file_name

    @property
    def effective_log_level(self) -> str:
        if self.debug:
            return constants.DEBUG_LOG_LEVEL
        return self.log_level

    @property
    def safe_debug_status(self) -> dict[str, bool | str]:
        return {
            "enabled": self.debug,
            "log_level": self.effective_log_level,
        }

    @property
    def safe_version_info(self) -> dict[str, str]:
        return {
            "version": self.app_version,
            "source": constants.APP_VERSION_ENV_VAR,
            "scheme": constants.APP_VERSION_SCHEME,
        }

    @property
    def default_location_data(self) -> dict[str, str | float | bool]:
        return {
            "label": self.default_location_display_name,
            "name": self.default_location_display_name,
            "city": self.default_location_city,
            "state": self.default_location_state,
            "county": self.default_location_county,
            "zip_code": self.default_location_postal_code,
            "latitude": self.default_location_latitude,
            "longitude": self.default_location_longitude,
            "default_zoom": self.default_location_zoom,
            "is_primary": True,
        }

    @property
    def frontend_config(self) -> dict[str, dict[str, str | bool]]:
        return {
            "mapbox": {
                "enabled": bool(self.mapbox_token),
                "token": self.mapbox_token,
            },
            "radar": {
                "enabled": True,
                "apiUrl": self.rainviewer_api_url,
                "frameIntervalMs": self.radar_frame_interval_ms,
                "opacity": self.radar_opacity,
            },
            "countyBoundaries": {
                "enabled": True,
                "geoJsonUrl": self.county_boundaries_geojson_url,
                "lineColor": self.county_boundaries_line_color,
                "lineOpacity": self.county_boundaries_line_opacity,
                "lineWidth": self.county_boundaries_line_width,
            },
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
