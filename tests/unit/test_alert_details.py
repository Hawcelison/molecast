from app.alerts.details import build_nws_details


def test_build_nws_details_extracts_arrays_and_preserves_strings() -> None:
    details = build_nws_details(
        {
            "tornadoDetection": ["RADAR INDICATED"],
            "maxWindGust": ["070 MPH"],
            "VTEC": [
                "/O.NEW.KGRR.TO.W.0049.260101T0000Z-260101T0100Z/",
                "/O.NEW.KGRR.SV.W.0012.260101T0000Z-260101T0100Z/",
            ],
        }
    )

    assert details["tornadoDetection"] == "RADAR INDICATED"
    assert details["maxWindGust"] == "070 MPH"
    assert details["VTEC"] == [
        "/O.NEW.KGRR.TO.W.0049.260101T0000Z-260101T0100Z/",
        "/O.NEW.KGRR.SV.W.0012.260101T0000Z-260101T0100Z/",
    ]


def test_build_nws_details_handles_missing_and_empty_parameters() -> None:
    details = build_nws_details(
        {
            "tornadoDetection": [""],
            "hailSize": None,
        }
    )

    assert details["tornadoDetection"] is None
    assert details["hailSize"] is None
    assert details["WEAHandling"] is None


def test_build_nws_details_accepts_alternate_casing_and_plain_strings() -> None:
    details = build_nws_details(
        {
            "tornadodetection": "OBSERVED",
            "weahandling": "IMMEDIATE",
            "eventmotiondescription": "MOVING EAST AT 35 MPH",
        }
    )

    assert details["tornadoDetection"] == "OBSERVED"
    assert details["WEAHandling"] == "IMMEDIATE"
    assert details["eventMotionDescription"] == "MOVING EAST AT 35 MPH"
