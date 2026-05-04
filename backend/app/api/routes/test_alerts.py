import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import constants
from app.alerts.test_targets import normalize_test_alert_targets
from app.alerts.test_alert_loader import resolve_relative_time_fields
from app.config import settings
from app.dependencies import get_db
from app.logging_config import get_logger
from app.services import location_service
from app.services.alert_service import active_alert_service
from app.services.alert_time import has_invalid_alert_time, now_utc


router = APIRouter(prefix="/test-alerts", tags=["test-alerts"])
logger = get_logger()
SEVERITY_VALUES = {"Extreme", "Severe", "Moderate", "Minor", "Unknown"}
URGENCY_VALUES = {"Immediate", "Expected", "Future", "Past", "Unknown"}
CERTAINTY_VALUES = {"Observed", "Likely", "Possible", "Unlikely", "Unknown"}
VALIDATION_STATUS = status.HTTP_400_BAD_REQUEST


def _validation_error(detail: str) -> HTTPException:
    return HTTPException(status_code=VALIDATION_STATUS, detail=detail)


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z") or has_invalid_alert_time(value):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _validate_choice(alert_id: str, field_name: str, value: Any, allowed_values: set[str]) -> None:
    if value not in allowed_values:
        raise _validation_error(
            f"Alert {alert_id} {field_name} must be one of: {', '.join(sorted(allowed_values))}."
        )


def _validate_geometry_ring(alert_id: str, ring: Any) -> None:
    if not isinstance(ring, list) or len(ring) < 4:
        raise _validation_error(f"Alert {alert_id} invalid geometry: polygon ring needs at least 4 coordinate pairs.")
    for position in ring:
        if not isinstance(position, list | tuple) or len(position) < 2:
            raise _validation_error(f"Alert {alert_id} geometry positions must be [longitude, latitude].")
        longitude, latitude = position[0], position[1]
        if (
            isinstance(longitude, bool)
            or isinstance(latitude, bool)
            or not isinstance(longitude, int | float)
            or not isinstance(latitude, int | float)
        ):
            raise _validation_error(f"Alert {alert_id} geometry longitude/latitude must be numbers.")
        if longitude < -180 or longitude > 180:
            raise _validation_error(f"Alert {alert_id} invalid longitude.")
        if latitude < -90 or latitude > 90:
            raise _validation_error(f"Alert {alert_id} invalid latitude.")
    if ring[0][0] != ring[-1][0] or ring[0][1] != ring[-1][1]:
        raise _validation_error(f"Alert {alert_id} geometry polygon ring must be closed.")
    unique_points = {(float(position[0]), float(position[1])) for position in ring[:-1]}
    if len(unique_points) < 3:
        raise _validation_error(f"Alert {alert_id} invalid geometry: polygon needs at least 3 points.")


def _validate_polygon_rings(alert_id: str, polygon: Any) -> None:
    if not isinstance(polygon, list) or not polygon:
        raise _validation_error(f"Alert {alert_id} geometry coordinates must include at least one ring.")
    for ring in polygon:
        _validate_geometry_ring(alert_id, ring)


def _validate_polygon_geometry(alert_id: str, geometry: dict[str, Any] | None) -> None:
    if geometry is None:
        return
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        _validate_polygon_rings(alert_id, coordinates)
        return
    if geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise _validation_error(f"Alert {alert_id} geometry MultiPolygon must include at least one polygon.")
        for polygon in coordinates:
            _validate_polygon_rings(alert_id, polygon)
        return
    raise _validation_error(f"Alert {alert_id} geometry must be a GeoJSON Polygon or MultiPolygon.")


def _validate_affected_zones(alert_id: str, affected_zones: Any) -> None:
    if affected_zones is None:
        return
    if not isinstance(affected_zones, list):
        raise _validation_error(f"Alert {alert_id} affectedZones must be an array.")
    for zone_url in affected_zones:
        if not isinstance(zone_url, str) or not zone_url.strip():
            raise _validation_error(f"Alert {alert_id} affectedZones values must be non-empty strings.")
        parsed = urlparse(zone_url.strip())
        path_parts = [part for part in parsed.path.split("/") if part]
        valid_url = (
            parsed.scheme in {"http", "https"}
            and parsed.netloc == "api.weather.gov"
            and len(path_parts) == 3
            and path_parts[0] == "zones"
            and path_parts[1] in {"forecast", "county", "fire"}
            and _valid_zone_id(path_parts[2])
        )
        if not valid_url:
            raise _validation_error(f"Alert {alert_id} affectedZones must contain NWS zone URLs.")


def _validate_geocode(alert_id: str, geocode: Any) -> None:
    if geocode is None:
        return
    if not isinstance(geocode, dict):
        raise _validation_error(f"Alert {alert_id} geocode must be a JSON object or null.")
    for field_name in ("UGC", "SAME"):
        value = geocode.get(field_name)
        if value is None:
            continue
        if not isinstance(value, list):
            raise _validation_error(f"Alert {alert_id} geocode.{field_name} must be an array.")
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise _validation_error(f"Alert {alert_id} geocode.{field_name} values must be non-empty strings.")


def _valid_zone_id(zone_id: str) -> bool:
    if len(zone_id) != 6:
        return False
    return zone_id[:2].isalpha() and zone_id[2] in {"C", "Z"} and zone_id[3:].isdigit()


def _validate_relative_time(alert_id: str, relative_time: Any) -> bool:
    if relative_time is None:
        return False
    if not isinstance(relative_time, dict):
        raise _validation_error(f"Alert {alert_id} relative_time must be a JSON object.")

    for field_name in ("effective_minutes_from_now", "expires_minutes_from_now"):
        value = relative_time.get(field_name)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise _validation_error(f"Alert {alert_id} relative_time.{field_name} must be a number.")

    if relative_time["expires_minutes_from_now"] <= relative_time["effective_minutes_from_now"]:
        raise _validation_error(
            f"Alert {alert_id} relative_time.expires_minutes_from_now must be after effective_minutes_from_now."
        )
    return True


def _resolve_test_alert_file() -> Path:
    configured_path = Path(constants.TEST_ALERTS_FILE)
    candidates = [
        configured_path,
        Path.cwd() / configured_path,
        Path.cwd().parent / configured_path,
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return Path.cwd().parent / configured_path


def _validate_test_alert_payload(payload: Any) -> dict[str, Any]:
    # The editor saves the raw document, but users often retry by PUT-ing the
    # full GET response. Accept both to keep the local tool forgiving.
    if isinstance(payload, dict) and isinstance(payload.get("payload"), dict):
        payload = payload["payload"]

    if not isinstance(payload, dict):
        raise _validation_error("Payload must be a JSON object.")

    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        raise _validation_error("Payload must include an alerts array.")

    seen_ids: set[str] = set()
    for index, alert in enumerate(alerts):
        if not isinstance(alert, dict):
            raise _validation_error(f"Alert at index {index} must be a JSON object.")

        alert_id = alert.get("id")
        if not isinstance(alert_id, str) or not alert_id.strip():
            raise _validation_error(f"Alert at index {index} must include a non-empty string id.")
        if alert_id in seen_ids:
            raise _validation_error(f"Duplicate alert id: {alert_id}")
        seen_ids.add(alert_id)

        event = alert.get("event")
        if not isinstance(event, str) or not event.strip():
            raise _validation_error(f"Alert {alert_id} must include a non-empty string event.")

        alert["source"] = "test"

        enabled = alert.get("enabled")
        if enabled is None:
            alert["enabled"] = False
            enabled = False
        elif not isinstance(enabled, bool):
            raise _validation_error(f"Alert {alert_id} enabled must be true or false.")

        has_relative_time = _validate_relative_time(alert_id, alert.get("relative_time"))
        if not has_relative_time:
            parsed_times: dict[str, datetime] = {}
            for field_name in ("effective", "expires"):
                value = alert.get(field_name)
                if value in (None, ""):
                    raise _validation_error(f"Alert {alert_id} {field_name} is required.")
                parsed_value = _parse_utc(value)
                if parsed_value is None:
                    raise _validation_error(
                        f"Alert {alert_id} {field_name} must be an ISO UTC timestamp ending in Z."
                    )
                parsed_times[field_name] = parsed_value
            if parsed_times["expires"] <= parsed_times["effective"] and not (
                enabled is False and parsed_times["expires"] <= now_utc()
            ):
                raise _validation_error(f"Alert {alert_id} expires must be after effective.")

        _validate_choice(alert_id, "severity", alert.get("severity"), SEVERITY_VALUES)
        _validate_choice(alert_id, "urgency", alert.get("urgency"), URGENCY_VALUES)
        _validate_choice(alert_id, "certainty", alert.get("certainty"), CERTAINTY_VALUES)

        area_desc = alert.get("areaDesc")
        if not isinstance(area_desc, str) or not area_desc.strip():
            logger.warning("Test alert saved with blank areaDesc: id=%s", alert_id)

        geometry = alert.get("geometry")
        if geometry is not None and not isinstance(geometry, dict):
            raise _validation_error(f"Alert {alert_id} geometry must be a JSON object or null.")
        _validate_polygon_geometry(alert_id, geometry)
        _validate_affected_zones(alert_id, alert.get("affectedZones"))
        _validate_geocode(alert_id, alert.get("geocode"))
        try:
            normalized_targets = normalize_test_alert_targets(alert.get("targets"))
        except ValueError as exc:
            raise _validation_error(f"Alert {alert_id} {exc}") from exc
        if normalized_targets is None:
            alert.pop("targets", None)
        else:
            alert["targets"] = normalized_targets

        parameters = alert.get("parameters")
        if parameters is not None and not isinstance(parameters, dict):
            raise _validation_error(f"Alert {alert_id} parameters must be a JSON object or null.")

    return payload


def _read_payload(alert_file: Path) -> dict[str, Any]:
    if not alert_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test alert file not found: {alert_file}",
        )

    try:
        payload = json.loads(alert_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.exception("Unable to parse test alert file for editor: file=%s", alert_file)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test alert file contains invalid JSON: {exc}",
        ) from exc
    except OSError as exc:
        logger.exception("Unable to read test alert file for editor: file=%s", alert_file)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to read test alert file: {exc}",
        ) from exc

    alerts = payload.get("alerts")
    if isinstance(alerts, list):
        for alert in alerts:
            if isinstance(alert, dict):
                alert["source"] = "test"
    return payload


def _count_active_test_alerts(alerts: list[Any]) -> int:
    current_time = now_utc()
    active_count = 0
    for alert in alerts:
        if not isinstance(alert, dict) or alert.get("enabled") is not True:
            continue
        effective, expires = resolve_relative_time_fields(alert, current_time)
        effective_at = _parse_utc(effective)
        expires_at = _parse_utc(expires)
        if effective_at is not None and current_time < effective_at:
            continue
        if expires_at is not None and current_time > expires_at:
            continue
        active_count += 1
    return active_count


def _active_source_counts(db: Session, *, refresh: bool = False) -> dict[str, Any]:
    active_location = location_service.get_active_location(db, settings)
    if refresh:
        alerts, refreshed_at = active_alert_service.refresh_active_alerts(active_location)
    else:
        alerts, refreshed_at = active_alert_service.get_active_alerts(active_location)
    test_count = sum(1 for alert in alerts if alert.source == "test")
    nws_count = sum(1 for alert in alerts if alert.source == "nws")
    return {
        "test": test_count,
        "nws": nws_count,
        "total": len(alerts),
        "refreshed_at": refreshed_at,
    }


def _write_payload(alert_file: Path, payload: dict[str, Any]) -> None:
    alert_file.parent.mkdir(parents=True, exist_ok=True)
    existing_stat = alert_file.stat() if alert_file.exists() else None

    if alert_file.exists():
        backup_file = alert_file.with_suffix(alert_file.suffix + ".bak")
        shutil.copy2(alert_file, backup_file)
        if existing_stat is not None:
            os.chown(backup_file, existing_stat.st_uid, existing_stat.st_gid)
            os.chmod(backup_file, existing_stat.st_mode)

    with alert_file.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")

    if existing_stat is not None:
        os.chown(alert_file, existing_stat.st_uid, existing_stat.st_gid)
        os.chmod(alert_file, existing_stat.st_mode)


@router.get("")
def get_test_alerts():
    alert_file = _resolve_test_alert_file()
    logger.debug("Reading test alert editor payload: file=%s", alert_file)
    payload = _read_payload(alert_file)

    alerts = payload.get("alerts", [])
    return {
        "file_path": str(alert_file),
        "loaded_at": now_utc(),
        "alert_count": len(alerts) if isinstance(alerts, list) else 0,
        "alerts": alerts if isinstance(alerts, list) else [],
        "payload": payload,
    }


@router.get("/status")
def get_test_alert_status(refresh: bool = True, db: Session = Depends(get_db)):
    alert_file = _resolve_test_alert_file()
    payload = _read_payload(alert_file)
    alerts = payload.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = []

    source_counts = _active_source_counts(db, refresh=refresh)
    stat = alert_file.stat() if alert_file.exists() else None
    last_saved = datetime.fromtimestamp(stat.st_mtime, UTC) if stat else None
    test_active = source_counts["test"]
    nws_active = source_counts["nws"]

    return {
        "test_file": str(alert_file),
        "test_total": len(alerts),
        "test_enabled": sum(1 for alert in alerts if isinstance(alert, dict) and alert.get("enabled") is True),
        "test_active": test_active,
        "nws_active": nws_active,
        "total_active": source_counts["total"],
        "last_loaded": now_utc(),
        "last_saved": last_saved,
        "active_refreshed_at": source_counts["refreshed_at"],
        "sources": {
            "test": test_active,
            "nws": nws_active,
        },
    }


@router.put("")
def save_test_alerts(payload: dict[str, Any], db: Session = Depends(get_db)):
    alert_file = _resolve_test_alert_file()
    validated_payload = _validate_test_alert_payload(payload)
    alert_count = len(validated_payload["alerts"])
    enabled_count = sum(1 for alert in validated_payload["alerts"] if alert.get("enabled") is True)

    try:
        _write_payload(alert_file, validated_payload)
    except OSError as exc:
        logger.exception("Failed to save test alert file: file=%s", alert_file)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to save test alert file: {exc}",
        ) from exc

    logger.info(
        "Saved test alert file: file=%s alerts=%s enabled=%s backup=%s",
        alert_file,
        alert_count,
        enabled_count,
        alert_file.with_suffix(alert_file.suffix + ".bak"),
    )
    refresh_result = _refresh_active_alerts(db)

    return {
        "file_path": str(alert_file),
        "saved_at": now_utc(),
        "alert_count": alert_count,
        "enabled_count": enabled_count,
        "refresh": refresh_result,
    }


@router.post("/refresh")
def refresh_test_alerts(db: Session = Depends(get_db)):
    return _refresh_active_alerts(db)


def _refresh_active_alerts(db: Session) -> dict[str, Any]:
    active_location = location_service.get_active_location(db, settings)
    alerts, refreshed_at = active_alert_service.refresh_active_alerts(active_location)
    test_alert_count = sum(1 for alert in alerts if alert.source == "test")
    logger.info(
        "Test alert refresh triggered: location_id=%s active_alerts=%s active_test_alerts=%s refreshed_at=%s",
        active_location.id,
        len(alerts),
        test_alert_count,
        refreshed_at.isoformat(),
    )
    return {
        "refreshed_at": refreshed_at,
        "active_alert_count": len(alerts),
        "active_test_alert_count": test_alert_count,
    }
