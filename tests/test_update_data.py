"""Checks how replaced routes are matched, using made-up routes measured in feet."""

import pandas as pd
from geopandas import GeoDataFrame
from shapely import LineString

from bike_routes.update_data import RouteRepository, normalize_street

INSTALLED = "2020-06-01"


def route(
    start: float,
    end: float,
    facilitycl: str = "I",
    instdate: str | None = "2000-01-01",
    ret_date: str | None = None,
    offset: float = 0,
) -> dict:
    """A route running east along a street, `offset` feet north of the others."""
    return {
        "geometry": LineString([(start, offset), (end, offset)]),
        "facilitycl": facilitycl,
        "instdate": pd.Timestamp(instdate) if instdate else pd.NaT,
        "ret_date": pd.Timestamp(ret_date) if ret_date else pd.NaT,
    }


def find_replaced(*routes: dict) -> list[str | None]:
    """The facility class each route replaced."""
    temporal = GeoDataFrame(list(routes), crs="EPSG:2263")
    replaced = RouteRepository().find_replaced_facilities(temporal)
    return [None if pd.isna(code) else code for code in replaced]


def test_same_place_same_day() -> None:
    assert find_replaced(
        route(0, 1000, "II", ret_date=INSTALLED),
        route(0, 1000, "I", instdate=INSTALLED),
    ) == [None, "II"]


def test_within_window() -> None:
    assert find_replaced(
        route(0, 1000, "II", ret_date="2020-05-01"),
        route(0, 1000, "I", instdate=INSTALLED),
    ) == [None, "II"]


def test_outside_window() -> None:
    assert find_replaced(
        route(0, 1000, "II", ret_date="2019-06-01"),
        route(0, 1000, "I", instdate=INSTALLED),
    ) == [None, None]


def test_other_side_of_street() -> None:
    assert find_replaced(
        route(0, 1000, "II", ret_date=INSTALLED, offset=40),
        route(0, 1000, "I", instdate=INSTALLED),
    ) == [None, "II"]


def test_parallel_street() -> None:
    assert find_replaced(
        route(0, 1000, "II", ret_date=INSTALLED, offset=300),
        route(0, 1000, "I", instdate=INSTALLED),
    ) == [None, None]


def test_split_into_different_segments() -> None:
    assert find_replaced(
        route(0, 400, "II", ret_date=INSTALLED),
        route(400, 1000, "II", ret_date=INSTALLED),
        route(0, 1000, "I", instdate=INSTALLED),
    ) == [None, None, "II"]


def test_mostly_new() -> None:
    """An extension of a route that was retired doesn't count as replacing it."""
    assert find_replaced(
        route(0, 500, "II", ret_date=INSTALLED),
        route(0, 1000, "I", instdate=INSTALLED),
    ) == [None, None]


def test_crossing_street() -> None:
    crossing = {
        **route(0, 0, "II", ret_date=INSTALLED),
        "geometry": LineString([(500, -1000), (500, 1000)]),
    }
    assert find_replaced(crossing, route(0, 1000, "I", instdate=INSTALLED)) == [
        None,
        None,
    ]


def test_prefers_closest_in_time() -> None:
    assert find_replaced(
        route(0, 1000, "III", ret_date="2020-05-01"),
        route(0, 1000, "II", ret_date=INSTALLED, offset=40),
        route(0, 1000, "I", instdate=INSTALLED),
    ) == [None, None, "II"]


def test_prefers_closest_in_shape() -> None:
    """A short route is covered by all of its neighbors, so pick the one that's in the same spot."""
    assert find_replaced(
        route(-500, 0, "III", ret_date=INSTALLED),
        route(0, 30, "II", ret_date=INSTALLED),
        route(30, 500, "III", ret_date=INSTALLED),
        route(0, 30, "I", instdate=INSTALLED),
    ) == [None, None, None, "II"]


def test_doesnt_replace_itself() -> None:
    assert find_replaced(route(0, 1000, instdate=INSTALLED, ret_date=INSTALLED)) == [
        None
    ]


def test_missing_install_date() -> None:
    assert find_replaced(
        route(0, 1000, "II", ret_date=INSTALLED),
        route(0, 1000, "I", instdate=None),
    ) == [None, None]


def test_normalize_street() -> None:
    assert normalize_street("Park Avenue") == "PARK AV"
    assert normalize_street("  w 4  street ") == "W 4 ST"
    assert normalize_street(None) == ""
