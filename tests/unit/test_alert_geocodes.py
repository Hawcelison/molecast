from app.alerts.geocodes import normalize_geocodes, parse_same, parse_ugc


def test_parse_same_preserves_leading_zero() -> None:
    same = parse_same("026077")

    assert same.original == "026077"
    assert same.valid is True
    assert same.state_fips == "26"
    assert same.county_fips == "077"
    assert same.errors == []


def test_parse_same_rejects_invalid_value() -> None:
    same = parse_same("26077")

    assert same.original == "26077"
    assert same.valid is False
    assert same.state_fips is None
    assert same.county_fips is None
    assert same.errors


def test_parse_ugc_county_code() -> None:
    ugc = parse_ugc("MIC077")

    assert ugc.original == "MIC077"
    assert ugc.valid is True
    assert ugc.prefix == "MI"
    assert ugc.type == "C"
    assert ugc.code == "077"
    assert ugc.kind == "county"
    assert ugc.errors == []


def test_parse_ugc_zone_code() -> None:
    ugc = parse_ugc("MIZ072")

    assert ugc.original == "MIZ072"
    assert ugc.valid is True
    assert ugc.prefix == "MI"
    assert ugc.type == "Z"
    assert ugc.code == "072"
    assert ugc.kind == "zone"


def test_parse_ugc_rejects_invalid_value() -> None:
    ugc = parse_ugc("MI077")

    assert ugc.original == "MI077"
    assert ugc.valid is False
    assert ugc.prefix is None
    assert ugc.type is None
    assert ugc.code is None
    assert ugc.kind is None
    assert ugc.errors


def test_parse_ugc_preserves_special_codes() -> None:
    county_all = parse_ugc("MICALL")
    zone_zero = parse_ugc("MIZ000")

    assert county_all.valid is True
    assert county_all.code == "ALL"
    assert county_all.kind == "county"
    assert zone_zero.valid is True
    assert zone_zero.code == "000"
    assert zone_zero.kind == "zone"


def test_normalize_geocodes_with_same_and_ugc_arrays() -> None:
    geocodes = normalize_geocodes(
        {
            "SAME": ["026077"],
            "UGC": ["MIC077", "MIZ072"],
        }
    )

    assert [same.original for same in geocodes.same] == ["026077"]
    assert geocodes.same[0].state_fips == "26"
    assert [ugc.original for ugc in geocodes.ugc] == ["MIC077", "MIZ072"]
    assert [ugc.kind for ugc in geocodes.ugc] == ["county", "zone"]


def test_normalize_geocodes_preserves_unknown_fields() -> None:
    raw = {
        "SAME": ["026077"],
        "UGC": ["MIC077"],
        "FIPS6": ["026077"],
        "custom": {"source": "fixture"},
    }

    geocodes = normalize_geocodes(raw)

    assert geocodes.raw == raw
    assert geocodes.raw["FIPS6"] == ["026077"]
    assert geocodes.raw["custom"] == {"source": "fixture"}

