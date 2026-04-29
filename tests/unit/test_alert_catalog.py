from app.alerts.catalog import (
    DEFAULT_COLOR_HEX,
    get_event_color,
    get_event_icon,
    get_event_priority,
    get_hazard_catalog,
    get_hazard_entry,
)


def test_hazard_catalog_loads_required_events() -> None:
    catalog = get_hazard_catalog()

    assert "tornado warning" in catalog
    assert "winter weather advisory" in catalog
    assert catalog["tornado warning"]["event"] == "Tornado Warning"


def test_known_event_returns_expected_color() -> None:
    assert get_event_color("Tornado Warning") == "#FF0000"
    assert get_hazard_entry(" tornado   warning ")["color_name"] == "Red"


def test_unknown_event_falls_back_safely() -> None:
    assert get_hazard_entry("Unknown Local Event") is None
    assert get_event_color("Unknown Local Event") == DEFAULT_COLOR_HEX
    assert get_event_color("Unknown Local Event", severity="Severe") == "#FFA500"
    assert get_event_priority("Unknown Local Event") == 100
    assert get_event_priority("Unknown Local Event", severity="Extreme") == 500
    assert get_event_icon("Unknown Local Event") == "alert-circle"

