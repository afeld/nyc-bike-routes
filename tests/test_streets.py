from bike_routes.streets import normalize_street


def test_normalize_street() -> None:
    assert normalize_street("Park Avenue") == "PARK AV"
    assert normalize_street("  w 4  street ") == "W 4 ST"
    assert normalize_street(None) == ""
