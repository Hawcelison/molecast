import json
from pathlib import Path
from typing import Any

from app.config import Settings
from app.logging_config import get_logger
from app.models.location import Location
from app.services.alert_time import now_utc, parse_alert_time_utc


class TestAlertLoader:
    def __init__(self, app_settings: Settings) -> None:
        self.settings = app_settings
        self.logger = get_logger()

    def load_enabled_alert_features(self, location: Location) -> list[dict[str, Any]]:
        alert_file = self._resolve_alert_file()
        if alert_file is None:
            self.logger.warning(
                "Test alert file not found: %s",
                self.settings.test_alerts_file,
            )
            return []

        try:
            payload = json.loads(alert_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.logger.exception("Test alert file is malformed JSON: %s", alert_file)
            return []
        except OSError:
            self.logger.exception("Unable to read test alert file: %s", alert_file)
            return []

        raw_alerts = payload.get("alerts")
        if not isinstance(raw_alerts, list):
            self.logger.warning("Test alert file has no alerts array: %s", alert_file)
            return []

        enabled_ids = [
            raw_alert.get("id")
            for raw_alert in raw_alerts
            if isinstance(raw_alert, dict) and raw_alert.get("enabled") is True
        ]
        comparison_time = now_utc()
        self.logger.debug(
            "Reading test alerts: file=%s total=%s enabled=%s now_utc=%s",
            alert_file,
            len(raw_alerts),
            enabled_ids,
            comparison_time.isoformat(),
        )

        features: list[dict[str, Any]] = []
        for raw_alert in raw_alerts:
            if not isinstance(raw_alert, dict):
                self.logger.debug("Skipping malformed test alert entry: %r", raw_alert)
                continue

            if raw_alert.get("enabled") is not True:
                self.logger.debug(
                    "Skipping disabled test alert: id=%s effective=%s expires=%s",
                    raw_alert.get("id"),
                    raw_alert.get("effective"),
                    raw_alert.get("expires"),
                )
                continue

            feature = self._build_feature(raw_alert, location)
            if feature is not None:
                features.append(feature)

        self.logger.debug(
            "Loaded enabled test alert features: file=%s count=%s",
            alert_file,
            len(features),
        )
        return features

    def _resolve_alert_file(self) -> Path | None:
        configured_path = self.settings.test_alerts_file
        candidates = [
            configured_path,
            Path.cwd() / configured_path,
            Path.cwd().parent / configured_path,
        ]

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        return None

    def alert_file_mtime(self) -> float | None:
        alert_file = self._resolve_alert_file()
        if alert_file is None:
            return None
        try:
            return alert_file.stat().st_mtime
        except OSError:
            self.logger.exception("Unable to stat test alert file: %s", alert_file)
            return None

    def _build_feature(
        self,
        raw_alert: dict[str, Any],
        location: Location,
    ) -> dict[str, Any] | None:
        alert_id = raw_alert.get("id")
        event = raw_alert.get("event")
        if not alert_id or not event:
            self.logger.warning("Skipping enabled test alert missing id or event.")
            return None

        area_desc = raw_alert.get("areaDesc") or location.county or location.state
        properties = {
            "id": alert_id,
            "source": raw_alert.get("source") or "test",
            "event": event,
            "severity": raw_alert.get("severity"),
            "urgency": raw_alert.get("urgency"),
            "certainty": raw_alert.get("certainty"),
            "headline": raw_alert.get("headline"),
            "description": raw_alert.get("description"),
            "instruction": raw_alert.get("instruction"),
            "areaDesc": area_desc,
            "effective": raw_alert.get("effective"),
            "expires": raw_alert.get("expires"),
            "parameters": raw_alert.get("parameters"),
        }
        effective_at = parse_alert_time_utc(properties["effective"])
        expires_at = parse_alert_time_utc(properties["expires"])
        self.logger.debug(
            "Prepared enabled test alert: id=%s event=%s effective=%s parsed_effective=%s "
            "expires=%s parsed_expires=%s geometry=%s parameters=%s",
            alert_id,
            event,
            properties["effective"],
            effective_at.isoformat() if effective_at else None,
            properties["expires"],
            expires_at.isoformat() if expires_at else None,
            "present" if raw_alert.get("geometry") else "missing",
            "present" if raw_alert.get("parameters") else "missing",
        )

        return {
            "type": "Feature",
            "id": alert_id,
            "source": "test",
            "properties": properties,
            "geometry": raw_alert.get("geometry"),
        }
