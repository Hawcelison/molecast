#!/usr/bin/env python3
"""
Molecast Local Alert Test Manager

Purpose:
- Enable/disable local test alerts
- Refresh effective/expires using current UTC time
- Keep test alert JSON valid and easy to manage
"""

import argparse
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALERT_FILE = PROJECT_ROOT / "test" / "alerts_test.json"


def utc_iso(dt: datetime) -> str:
    return (
        dt.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_data() -> dict:
    if not ALERT_FILE.exists():
        raise FileNotFoundError(f"Could not find {ALERT_FILE}")

    with ALERT_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_data(data: dict) -> None:
    with ALERT_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")

    print(f"Saved: {ALERT_FILE}")


def find_alert(data: dict, alert_id: str) -> dict:
    for alert in data.get("alerts", []):
        if alert.get("id") == alert_id:
            return alert

    raise ValueError(f"Alert ID not found: {alert_id}")


def list_alerts(data: dict) -> None:
    print(f"Alert file: {ALERT_FILE}")
    for alert in data.get("alerts", []):
        status = "ON " if alert.get("enabled") else "OFF"
        print(f"[{status}] {alert.get('id')} - {alert.get('event')}")


def disable_all(data: dict) -> None:
    for alert in data.get("alerts", []):
        alert["enabled"] = False


def set_active_window(alert: dict, before_hours: int, after_hours: int) -> None:
    now = datetime.now(timezone.utc)

    alert["enabled"] = True
    alert["effective"] = utc_iso(now - timedelta(hours=before_hours))
    alert["expires"] = utc_iso(now + timedelta(hours=after_hours))


def clone_alert(
    data: dict,
    source_id: str,
    new_id: str,
    new_event: str | None,
) -> None:
    source = find_alert(data, source_id)
    cloned = deepcopy(source)

    cloned["id"] = new_id
    cloned["enabled"] = False

    if new_event:
        cloned["event"] = new_event
        cloned["headline"] = f"TEST: {new_event} for Kalamazoo County, MI"
        cloned["description"] = (
            f"TEST {new_event} centered near "
            "4222 Fireside Ave, Portage, MI 49002."
        )

    data.setdefault("alerts", []).append(cloned)


def remove_alert(data: dict, alert_id: str) -> None:
    original_count = len(data.get("alerts", []))

    data["alerts"] = [
        alert for alert in data.get("alerts", [])
        if alert.get("id") != alert_id
    ]

    if len(data["alerts"]) == original_count:
        raise ValueError(f"Alert ID not found: {alert_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage Molecast local test alerts."
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list")

    enable = sub.add_parser("enable")
    enable.add_argument("alert_id")

    disable = sub.add_parser("disable")
    disable.add_argument("alert_id")

    active = sub.add_parser("active")
    active.add_argument("alert_id")
    active.add_argument(
        "--before",
        type=int,
        default=1,
        help="Hours before current UTC for effective",
    )
    active.add_argument(
        "--after",
        type=int,
        default=2,
        help="Hours after current UTC for expires",
    )

    sub.add_parser("disable-all")

    clone = sub.add_parser("clone")
    clone.add_argument("source_id")
    clone.add_argument("new_id")
    clone.add_argument("--event", default=None)

    remove = sub.add_parser("remove")
    remove.add_argument("alert_id")

    args = parser.parse_args()
    data = load_data()

    if args.command == "list":
        list_alerts(data)
        return

    if args.command == "enable":
        find_alert(data, args.alert_id)["enabled"] = True

    elif args.command == "disable":
        find_alert(data, args.alert_id)["enabled"] = False

    elif args.command == "active":
        alert = find_alert(data, args.alert_id)
        set_active_window(alert, args.before, args.after)

    elif args.command == "disable-all":
        disable_all(data)

    elif args.command == "clone":
        clone_alert(data, args.source_id, args.new_id, args.event)

    elif args.command == "remove":
        remove_alert(data, args.alert_id)

    save_data(data)


if __name__ == "__main__":
    main()
